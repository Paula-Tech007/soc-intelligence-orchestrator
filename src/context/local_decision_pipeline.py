"""
Integra o consumidor HTTP local ao Context Decision Gate.

Nao executa IA, notificacoes ou operacoes no banco.
"""

from src.context.local_http_client import (
    MAX_QUEUE_ID,
    ContextClientError,
    fetch_local_context,
)

from src.context.decision_gate import (
    BLOCKED,
    evaluate_context,
)


def review_local_context(queue_id: int) -> dict:
    """
    Recupera contexto LAB e produz uma decisao estruturada.

    Falhas de transporte ou contrato encerram o processamento
    com BLOCKED_BY_POLICY. Nunca acionam uma IA automaticamente.
    """

    if (
        type(queue_id) is not int
        or not 1 <= queue_id <= MAX_QUEUE_ID
    ):
        raise ValueError("queue_id invalido.")

    try:
        envelope = fetch_local_context(queue_id)

    except ContextClientError:
        blocked = evaluate_context(None)

        # Mensagem padronizada: nao repassar detalhes de rede,
        # tokens ou diagnosticos internos da API.
        return {
            **blocked,
            "queue_id": queue_id,
            "reason_code": "CONTEXT_FETCH_FAILED",
        }

    decision = evaluate_context(envelope)

    # Garantia adicional: a identidade da queue nao pode mudar.
    if decision["queue_id"] != queue_id:
        return {
            **evaluate_context(None),
            "queue_id": queue_id,
            "reason_code": "QUEUE_ID_MISMATCH",
        }

    assert decision["ai_execution_allowed"] is False
    assert decision["operational_dispatch_allowed"] is False
    assert decision["notification_sent"] is False

    return decision