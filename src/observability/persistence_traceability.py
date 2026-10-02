"""
Stage 16 - Rastreabilidade controlada em memoria.

Recebe um contrato integrado WF-05 e o registro SHA-256
original do pipeline MOCK.

Nao conecta ao PostgreSQL, nao grava dados,
nao executa Ollama e nao realiza despacho operacional.

A saida nao representa comprovante de persistencia.
"""

import copy

from src.ai_engine.integrity import (
    build_integrity_record,
    verify_integrity_record,
)

from src.reports.report_builder import validate_contract


class MemoryTraceabilityError(ValueError):
    """Contrato de rastreabilidade ausente ou divergente."""


def build_memory_traceability(contract, integrity_record):
    """
    Constroi metadados auditaveis sem persistencia.

    O registro original precisa corresponder exatamente
    ao WF-04 atual contido no contrato integrado.
    """

    if not isinstance(contract, dict):
        raise MemoryTraceabilityError(
            "Contrato integrado invalido."
        )

    if not isinstance(integrity_record, dict):
        raise MemoryTraceabilityError(
            "Registro SHA-256 ausente."
        )

    try:
        historical, current = validate_contract(contract)
    except (ValueError, KeyError, TypeError) as exc:
        raise MemoryTraceabilityError(
            "Contrato WF-05 invalido."
        ) from exc

    if (
        historical.get("status") != "SKIPPED"
        or historical.get("ai_executed") is not False
        or historical.get("analysis") is not None
        or current.get("status") != "ANALYSIS_COMPLETED"
        or current.get("ai_executed") is not True
    ):
        raise MemoryTraceabilityError(
            "Controle historico/atual inconsistente."
        )

    if (
        contract.get("environment") != "LAB"
        or contract.get("fixture_type") != "MOCK_AI_RESPONSE"
        or contract.get("real_ollama_call") is not False
        or contract.get("ready_for_operational_dispatch")
        is not False
    ):
        raise MemoryTraceabilityError(
            "Execucao fora das restricoes LAB/MOCK."
        )

    current_result = copy.deepcopy(current)

    # O contrato de transporte WF-05 permite reconstruir
    # apenas as flags adicionadas pela ponte de integridade.
    # A analise e a proveniencia nao sao modificadas.
    current_result.update({
        "fixture_type": "MOCK_AI_RESPONSE",
        "real_ollama_call": False,
        "ready_for_operational_dispatch": False,
    })

    try:
        if verify_integrity_record(integrity_record) is not True:
            raise MemoryTraceabilityError(
                "Registro SHA-256 nao confirmado."
            )

        expected_record = build_integrity_record(
            current_result
        )

        if integrity_record != expected_record:
            raise MemoryTraceabilityError(
                "Registro SHA-256 divergente do resultado WF-04."
            )

    except (ValueError, KeyError, TypeError) as exc:
        raise MemoryTraceabilityError(
            "Falha na verificacao de integridade."
        ) from exc

    identity = copy.deepcopy(
        expected_record["identity"]
    )

    # Saida com lista fechada de metadados.
    # Nao incluir analise, evento original, HTML,
    # token, credencial ou resposta HTTP.
    return {
        "schema_version": "1.0",
        "environment": "LAB",
        "processor": "WF-05-TRACEABILITY",
        "integration_mode": "IN_MEMORY_MOCK",
        "identity": identity,
        "historical_control": {
            "queue_id": historical["queue_id"],
            "investigation_version": historical[
                "investigation_version"
            ],
            "status": "SKIPPED",
            "ai_executed": False,
        },
        "content_signature": expected_record[
            "content_signature"
        ],
        "analysis_signature": expected_record[
            "analysis_signature"
        ],
        "result_key": expected_record["result_key"],
        "integrity_status": "VERIFIED_IN_MEMORY",
        "persistence_status": "NOT_ATTEMPTED",
        "database_record_id": None,
        "verification_method": "SHA256_IN_MEMORY",
        "verified_against_database": False,
        "human_review_required": True,
        "operational_dispatch_allowed": False,
        "notification_sent": False,
    }
