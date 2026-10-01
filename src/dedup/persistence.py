"""
SOC INTELLIGENCE ORCHESTRATOR
Modulo: WF-02 / Persistencia e Deduplicacao

Ambiente: LAB
Banco: PostgreSQL

Responsabilidades:
- Normalizar eventos.
- Gerar identidade e assinatura deterministicas.
- Controlar repeticoes entre execucoes.
- Versionar alteracoes materiais.
- Registrar evidencias e auditoria.
- Criar tarefas de analise apenas quando necessario.
- Processar cada ocorrencia em uma transacao.

Nenhuma integracao externa e executada neste modulo.
"""

import hashlib
import json

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


# ==========================================================
# CONFIGURACAO
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ENV_FILE = PROJECT_ROOT / ".env"

VALID_SEVERITIES = {
    "low",
    "medium",
    "high",
    "critical",
}


# ==========================================================
# CARREGAMENTO DA CONFIGURACAO
# ==========================================================

def load_config() -> dict[str, str]:

    if not ENV_FILE.is_file():
        raise FileNotFoundError(
            "Arquivo .env do projeto nao encontrado."
        )

    config = {}

    for line in ENV_FILE.read_text(
        encoding="utf-8"
    ).splitlines():

        line = line.strip()

        if not line or line.startswith("#"):
            continue

        key, separator, value = line.partition("=")

        if separator:
            config[key.strip()] = value.strip()

    password = config.get("SOC_DB_PASSWORD")

    if not password:
        raise RuntimeError(
            "SOC_DB_PASSWORD nao configurada."
        )

    return config


def connect_db():

    config = load_config()

    return psycopg.connect(
        host="127.0.0.1",
        port=15432,
        dbname="soc_intelligence",
        user="soc_lab",
        password=config["SOC_DB_PASSWORD"],
        connect_timeout=5,
        autocommit=True,
        row_factory=dict_row,
    )


# ==========================================================
# NORMALIZACAO E ASSINATURAS
# ==========================================================

def canonicalize(value: Any) -> Any:

    if isinstance(value, dict):

        return {
            key: canonicalize(value[key])
            for key in sorted(value)
        }

    if isinstance(value, list):

        return [
            canonicalize(item)
            for item in value
        ]

    return value


def canonical_json(value: Any) -> str:

    return json.dumps(
        canonicalize(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256(value: Any) -> str:

    content = canonical_json(value).encode("utf-8")

    return hashlib.sha256(content).hexdigest()


def utc_now() -> str:

    return datetime.now(
        timezone.utc
    ).isoformat()


def normalize_event(payload: dict) -> dict:

    if not isinstance(payload, dict):
        raise ValueError("Payload deve ser um objeto JSON.")

    if payload.get("environment") != "LAB":
        raise ValueError("Somente ambiente LAB permitido.")

    # Aceita a estrutura produzida pelo WF-01.
    event = payload.get("raw_event", payload)

    if not isinstance(event, dict):
        raise ValueError("Evento invalido.")

    source = payload.get("source") or event.get("source")

    required = {
        "source": source,
        "source_event_id": event.get("source_event_id"),
        "occurred_at": event.get("occurred_at"),
        "event_type": event.get("event_type"),
        "severity": event.get("severity"),
    }

    missing = [
        key
        for key, value in required.items()
        if not isinstance(value, str) or not value.strip()
    ]

    if missing:
        raise ValueError(
            "Campos obrigatorios ausentes: "
            + ", ".join(missing)
        )

    if event["severity"] not in VALID_SEVERITIES:
        raise ValueError("Severidade invalida.")

    entity = event.get("entity")

    if not isinstance(entity, dict):
        raise ValueError("Entity deve ser um objeto.")

    evidence = event.get("evidence")

    if not isinstance(evidence, list) or not evidence:
        raise ValueError("Evento sem evidencias.")

    ids = []

    for item in evidence:

        if not isinstance(item, dict):
            raise ValueError("Evidencia invalida.")

        evidence_id = item.get("evidence_id")

        if not isinstance(evidence_id, str) or not evidence_id:
            raise ValueError("Evidencia sem evidence_id.")

        ids.append(evidence_id)

    if len(set(ids)) != len(ids):
        raise ValueError(
            "Identificadores de evidencias duplicados."
        )

    normalized_evidence = sorted(
        [canonicalize(item) for item in evidence],
        key=lambda item: item["evidence_id"],
    )

    return {
        "source": source,
        "source_event_id": event["source_event_id"],
        "occurred_at": event["occurred_at"],
        "event_type": event["event_type"],
        "severity": event["severity"],
        "entity": canonicalize(entity),
        "evidence": normalized_evidence,
    }


def identify_changes(
    previous: dict,
    current: dict,
) -> tuple[list[str], list[str]]:

    fields = [
        "occurred_at",
        "severity",
        "entity",
        "evidence",
    ]

    changed = [
        field
        for field in fields
        if canonical_json(previous.get(field))
        != canonical_json(current.get(field))
    ]

    previous_ids = {
        item["evidence_id"]
        for item in previous.get("evidence", [])
    }

    new_ids = sorted({
        item["evidence_id"]
        for item in current["evidence"]
        if item["evidence_id"] not in previous_ids
    })

    return sorted(changed), new_ids


# ==========================================================
# PERSISTENCIA TRANSACIONAL
# ==========================================================

def process_event(payload: dict) -> dict:

    normalized = normalize_event(payload)

    collection_id = payload.get("collection_id")

    sequence = payload.get("collection_sequence")

    ingested_at = payload.get(
        "ingested_at",
        utc_now(),
    )

    if not isinstance(collection_id, str) or not collection_id:
        raise ValueError("collection_id obrigatorio.")

    if type(sequence) is not int or sequence <= 0:
        raise ValueError("collection_sequence invalido.")

    identity = [
        normalized["source"],
        normalized["source_event_id"],
        normalized["event_type"],
    ]

    identity_key = canonical_json(identity)

    content_signature = sha256(normalized)

    # Uma conexao independente e aberta para cada chamada.
    # A transacao controla todas as alteracoes da ocorrencia.

    with connect_db() as connection:

        with connection.transaction():

            with connection.cursor() as cursor:

                # --------------------------------------------------
                # SERIALIZAR O PROCESSAMENTO DA MESMA IDENTIDADE
                # --------------------------------------------------

                cursor.execute(
                    """
                    SELECT pg_advisory_xact_lock(
                        hashtextextended(%s, 0)
                    )
                    """,
                    (identity_key,),
                )

                # --------------------------------------------------
                # PROTEGER CONTRA REENTREGA DA MESMA COLETA
                # --------------------------------------------------

                cursor.execute(
                    """
                    SELECT
                        eo.investigation_id,
                        eo.content_signature,
                        i.source,
                        i.source_event_id,
                        i.event_type
                    FROM event_occurrences AS eo
                    JOIN investigations AS i
                      ON i.id = eo.investigation_id
                    WHERE eo.collection_id = %s
                      AND eo.collection_sequence = %s
                    """,
                    (collection_id, sequence),
                )

                previous_delivery = cursor.fetchone()

                if previous_delivery:

                    previous_identity = [
                        previous_delivery["source"],
                        previous_delivery["source_event_id"],
                        previous_delivery["event_type"],
                    ]

                    identity_matches = (
                        previous_identity == identity
                    )

                    content_matches = (
                        previous_delivery["content_signature"]
                        == content_signature
                    )

                    if not identity_matches or not content_matches:
                        raise ValueError(
                            "REPLAY_CONFLICT: identificador de entrega "
                            "ja utilizado com identidade ou conteudo "
                            "diferente. Nenhuma alteracao foi gravada."
                        )

                    return {
                        "status": "ALREADY_PROCESSED",
                        "should_analyze": False,
                        "reason": "Entrega ja registrada.",
                        "investigation_id": str(
                            previous_delivery["investigation_id"]
                        ),
                        "identity_key": identity_key,
                        "content_signature": content_signature,
                        "persistence": "POSTGRESQL",
                    }

                # --------------------------------------------------
                # BUSCAR INVESTIGACAO EXISTENTE
                # --------------------------------------------------

                cursor.execute(
                    """
                    SELECT *
                    FROM investigations
                    WHERE source = %s
                      AND source_event_id = %s
                      AND event_type = %s
                    FOR UPDATE
                    """,
                    tuple(identity),
                )

                investigation = cursor.fetchone()

                changed_fields = []
                new_evidence_ids = []

                # --------------------------------------------------
                # PRIMEIRA OCORRENCIA
                # --------------------------------------------------

                if investigation is None:

                    status = "NEW_EVENT"
                    should_analyze = True
                    version = 1
                    occurrence_count = 1

                    cursor.execute(
                        """
                        INSERT INTO investigations (
                            source,
                            source_event_id,
                            event_type,
                            current_signature,
                            latest_event,
                            investigation_version,
                            occurrence_count
                        )
                        VALUES (
                            %s, %s, %s, %s, %s, 1, 1
                        )
                        RETURNING id
                        """,
                        (
                            *identity,
                            content_signature,
                            Jsonb(normalized),
                        ),
                    )

                    investigation_id = cursor.fetchone()["id"]

                else:

                    investigation_id = investigation["id"]

                    occurrence_count = (
                        investigation["occurrence_count"] + 1
                    )

                    # Verificar todas as versoes conhecidas, nao
                    # apenas a versao mais recente.

                    cursor.execute(
                        """
                        SELECT version_number
                        FROM investigation_versions
                        WHERE investigation_id = %s
                          AND content_signature = %s
                        """,
                        (
                            investigation_id,
                            content_signature,
                        ),
                    )

                    known_version = cursor.fetchone()

                    # ----------------------------------------------
                    # EVENTO REPETIDO
                    # ----------------------------------------------

                    if known_version:

                        status = "EXACT_REPEAT"
                        should_analyze = False

                        version = investigation[
                            "investigation_version"
                        ]

                        cursor.execute(
                            """
                            UPDATE investigations
                            SET occurrence_count = %s,
                                last_seen_at = NOW()
                            WHERE id = %s
                            """,
                            (
                                occurrence_count,
                                investigation_id,
                            ),
                        )

                    # ----------------------------------------------
                    # ALTERACAO MATERIAL
                    # ----------------------------------------------

                    else:

                        status = "MATERIAL_UPDATE"
                        should_analyze = True

                        version = (
                            investigation["investigation_version"] + 1
                        )

                        changed_fields, new_evidence_ids = (
                            identify_changes(
                                investigation["latest_event"],
                                normalized,
                            )
                        )

                        cursor.execute(
                            """
                            UPDATE investigations
                            SET current_signature = %s,
                                latest_event = %s,
                                investigation_version = %s,
                                occurrence_count = %s,
                                last_seen_at = NOW(),
                                updated_at = NOW()
                            WHERE id = %s
                            """,
                            (
                                content_signature,
                                Jsonb(normalized),
                                version,
                                occurrence_count,
                                investigation_id,
                            ),
                        )

                # --------------------------------------------------
                # REGISTRAR NOVA VERSAO E EVIDENCIAS
                # --------------------------------------------------

                if should_analyze:

                    cursor.execute(
                        """
                        INSERT INTO investigation_versions (
                            investigation_id,
                            version_number,
                            content_signature,
                            normalized_event,
                            changed_fields
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            investigation_id,
                            version,
                            content_signature,
                            Jsonb(normalized),
                            Jsonb(changed_fields),
                        ),
                    )

                    for evidence in normalized["evidence"]:

                        cursor.execute(
                            """
                            INSERT INTO evidences (
                                investigation_id,
                                evidence_id,
                                evidence_data
                            )
                            VALUES (%s, %s, %s)
                            ON CONFLICT (
                                investigation_id,
                                evidence_id
                            )
                            DO UPDATE SET
                                evidence_data =
                                EXCLUDED.evidence_data
                            """,
                            (
                                investigation_id,
                                evidence["evidence_id"],
                                Jsonb(evidence),
                            ),
                        )

                    # Fila idempotente por versao de investigacao.
                    # Nao executa IA neste momento.

                    cursor.execute(
                        """
                        INSERT INTO analysis_queue (
                            investigation_id,
                            investigation_version,
                            status
                        )
                        VALUES (%s, %s, 'PENDING')
                        ON CONFLICT (
                            investigation_id,
                            investigation_version
                        )
                        DO NOTHING
                        """,
                        (
                            investigation_id,
                            version,
                        ),
                    )

                # --------------------------------------------------
                # REGISTRAR OCORRENCIA
                # --------------------------------------------------

                cursor.execute(
                    """
                    INSERT INTO event_occurrences (
                        investigation_id,
                        collection_id,
                        collection_sequence,
                        content_signature,
                        classification,
                        ingested_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        investigation_id,
                        collection_id,
                        sequence,
                        content_signature,
                        status,
                        ingested_at,
                    ),
                )

                # --------------------------------------------------
                # REGISTRAR AUDITORIA
                # --------------------------------------------------

                cursor.execute(
                    """
                    INSERT INTO audit_log (
                        investigation_id,
                        workflow_name,
                        action,
                        details
                    )
                    VALUES (%s, 'WF-02', %s, %s)
                    """,
                    (
                        investigation_id,
                        status,
                        Jsonb({
                            "collection_id": collection_id,
                            "collection_sequence": sequence,
                            "version": version,
                            "occurrence_count": occurrence_count,
                            "should_analyze": should_analyze,
                            "changed_fields": changed_fields,
                            "new_evidence_ids": new_evidence_ids,
                        }),
                    ),
                )

                # Todas as gravacoes acima pertencem a uma
                # unica transacao PostgreSQL.

                return {
                    "status": status,
                    "should_analyze": should_analyze,
                    "investigation_id": str(investigation_id),
                    "investigation_version": version,
                    "occurrence_count": occurrence_count,
                    "identity_key": identity_key,
                    "content_signature": content_signature,
                    "changed_fields": changed_fields,
                    "new_evidence_ids": new_evidence_ids,
                    "target_workflow": (
                        "WF-03" if should_analyze else None
                    ),
                    "persistence": "POSTGRESQL",
                    "dispatch_status": "MOCK_ONLY",
                    "ai_executed": False,
                    "notification_sent": False,
                }