"""
SOC Intelligence Orchestrator
FASE 14.3.2.4 - WF-02 / WF-03 Context Bridge

Resolve resultados LAB do WF-02 contra versoes
JA EXISTENTES no PostgreSQL.

Nao executa process_event().
Nao insere ocorrencias, versoes ou filas.
Nao realiza despacho operacional.
"""

import copy
import json

from psycopg.rows import tuple_row

from src.context.context_builder import build_context

from src.dedup.persistence import (
    canonical_json,
    connect_db,
    sha256,
)


class ContextBridgeError(ValueError):
    """Falha na correspondencia entre WF-02 e PostgreSQL."""


EXPECTED_CASES = (
    ("NEW_EVENT", 1, True),
    ("EXACT_REPEAT", 1, False),
    ("MATERIAL_UPDATE", 2, True),
)


def resolve_existing_contexts(wf02_items):
    """
    Recebe os tres resultados auditados do WF-02.

    Retorna:
      - contexto historico da versao 1;
      - repeticao exata suprimida;
      - contexto atual da versao 2.

    Toda proveniencia de banco e conferida por SELECT.
    """

    if not isinstance(wf02_items, list):
        raise ContextBridgeError(
            "Entrada WF-02 deve ser uma lista."
        )

    if len(wf02_items) != 3:
        raise ContextBridgeError(
            "LAB: esperados exatamente tres resultados WF-02."
        )

    items = sorted(
        copy.deepcopy(wf02_items),
        key=lambda item: item.get(
            "collection_sequence", -1
        ),
    )

    prepared = []

    # ------------------------------------------------------
    # 1. VALIDAR TODOS OS RESULTADOS ANTES DO BANCO
    # ------------------------------------------------------

    for index, item in enumerate(items):

        expected_status, expected_version, expected_ai = (
            EXPECTED_CASES[index]
        )

        if (
            not isinstance(item, dict)
            or item.get("schema_version") != "1.0"
            or item.get("environment") != "LAB"
            or item.get("processor") != "WF-02"
            or item.get("collection_sequence") != index + 1
            or item.get("dispatch_status") != "MOCK_ONLY"
            or item.get("real_execution_started") is not False
        ):
            raise ContextBridgeError(
                "Contrato WF-02 invalido."
            )

        audit = item.get("audit")
        dedup = item.get("deduplication")
        decision = item.get("decision")

        if not all(
            isinstance(value, dict)
            for value in (audit, dedup, decision)
        ):
            raise ContextBridgeError(
                "Auditoria ou decisao WF-02 ausente."
            )

        if (
            audit.get("status") != "VALIDATED"
            or audit.get("persistence") != "NOT_ENABLED"
            or audit.get("notification_sent") is not False
            or audit.get("ai_executed") is not False
        ):
            raise ContextBridgeError(
                "Estado de auditoria nao autorizado."
            )

        if (
            item.get("sample_case") != expected_status
            or dedup.get("status") != expected_status
            or dedup.get("investigation_version")
            != expected_version
            or decision.get("should_analyze") is not expected_ai
        ):
            raise ContextBridgeError(
                "Sequencia de deduplicacao inconsistente."
            )

        normalized = item.get("normalized_event")

        if not isinstance(normalized, dict):
            raise ContextBridgeError(
                "Evento normalizado ausente."
            )

        if normalized.get("source") != "SOC-LAB":
            raise ContextBridgeError(
                "Somente a fonte SOC-LAB e permitida."
            )

        # O WF-02 JavaScript utiliza JSON canonico.
        # Essa representacao NAO e um digest SHA-256.

        js_signature = item.get("content_signature")

        if not isinstance(js_signature, str):
            raise ContextBridgeError(
                "Assinatura WF-02 ausente."
            )

        try:
            js_payload = json.loads(js_signature)
        except (ValueError, TypeError) as exc:
            raise ContextBridgeError(
                "Assinatura JSON WF-02 invalida."
            ) from exc

        if (
            js_payload != normalized
            or js_signature != canonical_json(normalized)
        ):
            raise ContextBridgeError(
                "Conteudo canonico WF-02 divergente."
            )

        prepared.append({
            "case": expected_status,
            "version": expected_version,
            "normalized_event": normalized,
            "database_signature": sha256(normalized),
        })

    # Uma repeticao exata precisa representar o mesmo conteudo.

    if (
        prepared[0]["normalized_event"]
        != prepared[1]["normalized_event"]
    ):
        raise ContextBridgeError(
            "EXACT_REPEAT possui conteudo divergente."
        )

    if (
        prepared[0]["database_signature"]
        == prepared[2]["database_signature"]
    ):
        raise ContextBridgeError(
            "Atualizacao material sem alteracao de conteudo."
        )

    # ------------------------------------------------------
    # 2. LOCALIZAR VERSOES JA EXISTENTES NO POSTGRESQL
    # ------------------------------------------------------

    resolved = []

    for entry in (prepared[0], prepared[2]):

        event = entry["normalized_event"]

        with connect_db() as conn:

            with conn.cursor(row_factory=tuple_row) as cur:

                cur.execute(
                    """
                    SELECT
                        q.id,
                        v.normalized_event,
                        v.content_signature
                    FROM public.analysis_queue AS q
                    JOIN public.investigations AS i
                      ON i.id = q.investigation_id
                    JOIN public.investigation_versions AS v
                      ON v.investigation_id = i.id
                     AND v.version_number =
                         q.investigation_version
                    WHERE i.source = %s
                      AND i.source_event_id = %s
                      AND i.event_type = %s
                      AND q.investigation_version = %s
                      AND v.content_signature = %s
                    """,
                    (
                        event["source"],
                        event["source_event_id"],
                        event["event_type"],
                        entry["version"],
                        entry["database_signature"],
                    ),
                )

                rows = cur.fetchall()

        if len(rows) != 1:
            raise ContextBridgeError(
                "Versao persistida nao encontrada de forma unica."
            )

        queue_id, saved_event, saved_signature = rows[0]

        if (
            saved_event != event
            or saved_signature != entry["database_signature"]
        ):
            raise ContextBridgeError(
                "Evento persistido diverge do WF-02."
            )

        # O context_builder recupera os dados autoritativos
        # da investigacao e verifica a versao solicitada.

        context = build_context(queue_id)

        if (
            context["event"] != event
            or context["requested_version"] != entry["version"]
            or context["provenance"]["content_signature"]
            != entry["database_signature"]
            or context["dispatch_status"] != "MOCK_ONLY"
            or context["ai_executed"] is not False
            or context["notification_sent"] is not False
        ):
            raise ContextBridgeError(
                "Contexto WF-03 divergente."
            )

        resolved.append({
            "source_case": entry["case"],
            "queue_id": queue_id,
            "context": context,
        })

    historical, current = resolved

    if (
        historical["context"]["investigation_id"]
        != current["context"]["investigation_id"]
        or historical["context"]["is_historical_version"] is not True
        or historical["context"]["eligible_for_context_review"]
        is not False
        or current["context"]["is_historical_version"] is not False
        or current["context"]["eligible_for_context_review"]
        is not True
    ):
        raise ContextBridgeError(
            "Versionamento ou elegibilidade inconsistente."
        )

    # ------------------------------------------------------
    # 3. CONTRATO DE SAIDA
    # ------------------------------------------------------

    return {
        "schema_version": "1.0",
        "environment": "LAB",
        "processor": "WF02-WF03-BRIDGE",
        "integration_mode": "EXISTING_POSTGRESQL_LAB",
        "persistence_action": "READ_ONLY_LOOKUP",
        "runtime_database_query": True,
        "contexts": resolved,
        "skipped": [{
            "source_case": "EXACT_REPEAT",
            "reason": "NO_NEW_ANALYSIS",
            "investigation_version": 1,
        }],
        "real_execution_started": False,
        "notification_sent": False,
        "operational_dispatch_allowed": False,
    }
