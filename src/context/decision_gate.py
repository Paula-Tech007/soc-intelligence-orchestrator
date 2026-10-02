"""
SOC Intelligence Orchestrator - Context Decision Gate.

Componente deterministico e exclusivamente local.

Nao consulta HTTP, PostgreSQL ou Ollama.
Nao autoriza execucao automatica de IA ou despacho operacional.
"""


READY = "READY_FOR_AI_REVIEW"
HISTORICAL = "HISTORICAL_CONTEXT"
BLOCKED = "BLOCKED_BY_POLICY"


def _decision(decision, reason_code, queue_id=None):
    """Contrato de saida seguro e padronizado."""

    return {
        "schema_version": "1.0",
        "environment": "LAB",
        "processor": "CONTEXT_DECISION_GATE",
        "queue_id": queue_id,
        "decision": decision,
        "reason_code": reason_code,
        "eligible_for_ai_review": decision == READY,
        "ai_execution_allowed": False,
        "operational_dispatch_allowed": False,
        "human_review_required": True,
        "notification_sent": False,
    }


def evaluate_context(envelope):
    """
    Avalia um envelope produzido pela ponte HTTP local.

    Uma resposta invalida resulta sempre em BLOCKED_BY_POLICY.

    READY_FOR_AI_REVIEW indica somente elegibilidade para
    continuidade do processo de revisao. Nao executa IA.
    """

    if not isinstance(envelope, dict):
        return _decision(BLOCKED, "INVALID_ENVELOPE")

    context = envelope.get("context")

    queue_id = None

    if isinstance(context, dict):
        candidate = context.get("queue_id")

        if type(candidate) is int and candidate > 0:
            queue_id = candidate

    # Primeira barreira: seguranca do envelope HTTP.

    if (
        envelope.get("integration_mode")
        != "LOCAL_POSTGRES_READ_ONLY"
        or envelope.get("real_database_query") is not True
        or envelope.get("operational_dispatch_allowed") is not False
        or envelope.get("human_review_required") is not True
    ):
        return _decision(BLOCKED, "INVALID_HTTP_CONTRACT", queue_id)

    if not isinstance(context, dict):
        return _decision(BLOCKED, "MISSING_CONTEXT")

    # Segunda barreira: contrato investigativo LAB.

    if (
        context.get("schema_version") != "1.0"
        or context.get("environment") != "LAB"
        or context.get("processor") != "WF-03"
        or queue_id is None
        or not isinstance(context.get("source_event_id"), str)
        or not context["source_event_id"].strip()
        or context.get("dispatch_status") != "MOCK_ONLY"
        or context.get("ai_executed") is not False
        or context.get("notification_sent") is not False
    ):
        return _decision(BLOCKED, "INVALID_CONTEXT_CONTRACT", queue_id)

    queue_status = context.get("queue_status")
    context_status = context.get("context_status")

    requested = context.get("requested_version")
    current = context.get("current_version")

    historical = context.get("is_historical_version")
    eligible = context.get("eligible_for_context_review")

    if (
        not isinstance(queue_status, str)
        or not queue_status.strip()
        or type(requested) is not int
        or type(current) is not int
        or requested < 1
        or current < requested
        or type(historical) is not bool
        or type(eligible) is not bool
    ):
        return _decision(BLOCKED, "INVALID_VERSION_FIELDS", queue_id)

    if historical != (requested < current):
        return _decision(BLOCKED, "INCONSISTENT_VERSION", queue_id)

    # A elegibilidade deve corresponder exatamente ao WF-03.
    expected_eligible = (
        queue_status == "PENDING"
        and not historical
    )

    if eligible != expected_eligible:
        return _decision(BLOCKED, "INCONSISTENT_ELIGIBILITY", queue_id)

    expected_status = (
        "HISTORICAL_VERSION"
        if historical
        else "READY_FOR_REVIEW"
        if expected_eligible
        else "NOT_PENDING"
    )

    if context_status != expected_status:
        return _decision(BLOCKED, "INCONSISTENT_CONTEXT_STATUS", queue_id)

    # Versoes anteriores sao preservadas apenas para rastreabilidade.

    if historical:
        return _decision(HISTORICAL, "SUPERSEDED_VERSION", queue_id)

    # Uma versao atual com fila nao pendente nao pode seguir para IA.

    if queue_status != "PENDING":
        return _decision(BLOCKED, "QUEUE_NOT_PENDING", queue_id)

    return _decision(READY, "CURRENT_PENDING_CONTEXT", queue_id)