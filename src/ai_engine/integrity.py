"""
SOC Intelligence Orchestrator - Fase 13.5.2.

Assinatura independente da analise do WF-04.

Escopo atual: LAB / MOCK.
Nao acessa PostgreSQL ou Ollama.
Nao realiza despacho operacional.
"""

import copy
import hashlib
import json
import re


def sha256_json(value):
    """Gera SHA-256 de uma estrutura JSON canonica."""

    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def validate_result(result):

    if not isinstance(result, dict):
        raise ValueError("Resultado WF-04 invalido.")

    expected = {
        "schema_version": "1.0",
        "environment": "LAB",
        "processor": "WF-04",
        "dispatch_status": "MOCK_ONLY",
        "status": "ANALYSIS_COMPLETED",
        "fixture_type": "MOCK_AI_RESPONSE",
        "real_ollama_call": False,
        "real_execution_started": False,
        "ready_for_operational_dispatch": False,
        "notification_sent": False,
        "ai_executed": True,
        "requires_human_review": True,
    }

    for field, value in expected.items():

        if result.get(field) != value:
            raise ValueError(
                "Campo invalido: " + field
            )

    for field in (
        "investigation_id",
        "source_event_id",
        "model",
    ):

        value = result.get(field)

        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                "Identificacao invalida: " + field
            )

    version = result.get("investigation_version")
    queue_id = result.get("queue_id")

    if type(version) is not int or version < 1:
        raise ValueError("Versao invalida.")

    if type(queue_id) is not int or queue_id < 1:
        raise ValueError("Queue ID invalido.")

    provenance = result.get("provenance")

    if not isinstance(provenance, dict):
        raise ValueError("Proveniencia ausente.")

    if provenance.get("version") != version:
        raise ValueError(
            "Versao da proveniencia divergente."
        )

    signature = provenance.get("content_signature")

    if not isinstance(signature, str) or not re.fullmatch(
        r"[a-f0-9]{64}",
        signature,
    ):
        raise ValueError(
            "Assinatura de contexto invalida."
        )

    analysis = result.get("analysis")

    if not isinstance(analysis, dict):
        raise ValueError("Analise ausente.")

    required_fields = {
        "summary",
        "assessment",
        "evidence_ids",
        "limitations",
        "review_actions",
    }

    if set(analysis) != required_fields:
        raise ValueError(
            "Estrutura da analise divergente."
        )

    for field in ("summary", "assessment"):

        value = analysis[field]

        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                "Texto obrigatorio invalido: " + field
            )

    for field in (
        "evidence_ids",
        "limitations",
        "review_actions",
    ):

        values = analysis[field]

        if (
            not isinstance(values, list)
            or not values
            or not all(
                isinstance(value, str) and value.strip()
                for value in values
            )
        ):
            raise ValueError(
                "Lista invalida: " + field
            )

    if len(set(analysis["evidence_ids"])) != len(
        analysis["evidence_ids"]
    ):
        raise ValueError(
            "Referencias de evidencias duplicadas."
        )

    return True


def build_integrity_record(result):
    """
    Cria assinaturas para um resultado MOCK validado.

    content_signature: recebido da proveniencia.
    analysis_signature: calculado sobre a analise.
    result_key: calculado sobre a identidade logica.
    """

    validate_result(result)

    identity = {
        "environment": result["environment"],
        "investigation_id": result["investigation_id"],
        "source_event_id": result["source_event_id"],
        "queue_id": result["queue_id"],
        "investigation_version": result[
            "investigation_version"
        ],
        "content_signature": result[
            "provenance"
        ]["content_signature"],
        "model": result["model"],
        "execution_mode": "MOCK_AI_RESPONSE",
    }

    analysis_payload = copy.deepcopy(
        result["analysis"]
    )

    record = {
        "schema_version": "1.0",
        "integrity_processor": "WF-04-INTEGRITY",
        "environment": "LAB",
        "execution_mode": "MOCK_AI_RESPONSE",
        "identity": identity,
        "analysis": analysis_payload,
        "content_signature": identity[
            "content_signature"
        ],
        "analysis_signature": sha256_json(
            analysis_payload
        ),
        "result_key": sha256_json(identity),
        "verified_against_database": False,
        "operational_dispatch_allowed": False,
    }

    return record


def verify_integrity_record(record):
    """Confere se identidade e analise ainda correspondem."""

    if not isinstance(record, dict):
        raise ValueError(
            "Registro de integridade invalido."
        )

    if (
        record.get("integrity_processor")
        != "WF-04-INTEGRITY"
        or record.get("environment") != "LAB"
        or record.get("execution_mode")
        != "MOCK_AI_RESPONSE"
        or record.get("verified_against_database") is not False
        or record.get("operational_dispatch_allowed") is not False
    ):
        raise ValueError(
            "Registro fora do escopo LAB/MOCK."
        )

    identity = record.get("identity")

    if not isinstance(identity, dict):
        raise ValueError("Identidade ausente.")

    if (
        record.get("content_signature")
        != identity.get("content_signature")
    ):
        raise ValueError(
            "Assinatura do contexto divergente."
        )

    if (
        record.get("result_key")
        != sha256_json(identity)
    ):
        raise ValueError(
            "Chave de resultado divergente."
        )

    if (
        record.get("analysis_signature")
        != sha256_json(record.get("analysis"))
    ):
        raise ValueError(
            "Analise alterada apos assinatura."
        )

    return True


class IntegrityRegistry:
    """
    Registro temporario de resultados assinados.

    Identifica reprocessamentos na mesma execucao.
    Nao substitui uma tabela persistente no PostgreSQL.
    """

    def __init__(self):
        self._records = {}

    def register(self, record):

        verify_integrity_record(record)

        key = record["result_key"]

        if key not in self._records:

            self._records[key] = copy.deepcopy(record)

            return "NEW_RESULT"

        previous = self._records[key]

        if (
            previous["analysis_signature"]
            != record["analysis_signature"]
        ):
            raise ValueError(
                "INTEGRITY_CONFLICT: mesma chave logica "
                "com analise diferente."
            )

        return "ALREADY_REGISTERED"
