"""
Etapa 14 - Coletor de telemetria segura.

Nao executa HTTP, Ollama, PostgreSQL ou notificacoes.
Nao escreve arquivos e nao envia eventos externamente.

Recebe exclusivamente resultados ja produzidos pelo
pipeline integrado LAB/MOCK.

Utiliza uma allowlist de campos para impedir que contexto,
evidencias, hashes, tokens ou respostas completas sejam
copiados para a telemetria.
"""

from typing import Any


ALLOWED_GATE_DECISIONS = frozenset({
    "READY_FOR_AI_REVIEW",
    "HISTORICAL_CONTEXT",
    "BLOCKED_BY_POLICY",
})

ALLOWED_REVIEW_STATUSES = frozenset({
    "MOCK_ANALYSIS_COMPLETED",
    "HISTORICAL_SKIPPED",
    "BLOCKED",
})

ALLOWED_INTEGRITY_STATUSES = frozenset({
    "VERIFIED_IN_MEMORY",
    "NOT_APPLICABLE",
})


def collect_review_telemetry(
    result: dict[str, Any],
    *,
    duration_ms: int,
) -> dict[str, Any]:
    """Extrai somente metricas autorizadas do resultado MOCK."""

    if not isinstance(result, dict):
        raise TypeError("Resultado deve ser um dicionario.")

    if (
        type(duration_ms) is not int
        or duration_ms < 0
    ):
        raise ValueError("Duracao invalida.")

    gate = result.get("gate_decision")

    if not isinstance(gate, dict):
        raise ValueError("Contrato do Gate invalido.")

    gate_decision = gate.get("decision")
    review_status = result.get("review_status")
    integrity_status = result.get("integrity_status")

    if gate_decision not in ALLOWED_GATE_DECISIONS:
        raise ValueError("Decisao do Gate desconhecida.")

    if review_status not in ALLOWED_REVIEW_STATUSES:
        raise ValueError("Status de revisao desconhecido.")

    if integrity_status not in ALLOWED_INTEGRITY_STATUSES:
        raise ValueError("Status de integridade desconhecido.")

    if (
        result.get("real_ollama_call") is not False
        or result.get("operational_dispatch_allowed") is not False
        or result.get("ready_for_operational_dispatch") is not False
        or result.get("notification_sent") is not False
        or result.get("human_review_required") is not True
    ):
        raise ValueError("Resultado fora das restricoes LAB.")

    wf04 = result.get("wf04_result")

    if review_status == "MOCK_ANALYSIS_COMPLETED":

        if (
            gate_decision != "READY_FOR_AI_REVIEW"
            or integrity_status != "VERIFIED_IN_MEMORY"
            or not isinstance(wf04, dict)
            or type(wf04.get("cache_hit")) is not bool
        ):
            raise ValueError("Contrato de analise MOCK inconsistente.")

        cache_hit = wf04["cache_hit"]

    else:
        if (
            wf04 is not None
            or integrity_status != "NOT_APPLICABLE"
        ):
            raise ValueError("Contrato de revisao ignorada inconsistente.")

        if (
            review_status == "HISTORICAL_SKIPPED"
            and gate_decision != "HISTORICAL_CONTEXT"
        ):
            raise ValueError("Historico inconsistente.")

        if (
            review_status == "BLOCKED"
            and gate_decision != "BLOCKED_BY_POLICY"
        ):
            raise ValueError("Bloqueio inconsistente.")

        cache_hit = None

    # A saida e construida do zero.
    # Nenhum objeto do resultado original e copiado.
    return {
        "schema_version": "1.0",
        "environment": "LAB",
        "pipeline_status": "COMPLETED",
        "gate_decision": gate_decision,
        "review_status": review_status,
        "integrity_status": integrity_status,
        "cache_hit": cache_hit,
        "duration_ms": duration_ms,
        "error_category": None,
    }
