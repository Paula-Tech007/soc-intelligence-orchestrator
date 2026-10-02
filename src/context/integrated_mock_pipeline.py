"""
Pipeline integrado de revisao MOCK para SOC-LAB.

A fonte HTTP e definida exclusivamente pelo cliente local existente.

Nao realiza persistencia, notificacoes ou despacho operacional.
O motor utilizado pelo orquestrador e exclusivamente MOCK.
"""

from src.context.local_http_client import (
    MAX_QUEUE_ID,
    ContextClientError,
    fetch_local_context,
)

from src.ai_engine.review_integrity import (
    run_verified_mock_review,
)


def run_integrated_mock_review(queue_id: int, *, cache=None):
    """
    Executa o pipeline completo:

    HTTP Client -> Decision Gate -> WF-04 MOCK -> Integridade.

    O cliente HTTP valida o envelope antes que ele chegue
    ao orquestrador.

    Falhas de transporte ou contrato encerram a chamada.
    """

    if (
        type(queue_id) is not int
        or not 1 <= queue_id <= MAX_QUEUE_ID
    ):
        raise ValueError("queue_id invalido.")

    envelope = fetch_local_context(queue_id)

    context = envelope.get("context")

    if (
        not isinstance(context, dict)
        or context.get("queue_id") != queue_id
    ):
        raise ContextClientError(
            "Identidade da queue divergente."
        )

    result = run_verified_mock_review(
        envelope,
        cache=cache,
    )

    if result["queue_id"] != queue_id:
        raise ValueError(
            "Identidade da resposta integrada divergente."
        )

    if (
        result["real_ollama_call"] is not False
        or result["operational_dispatch_allowed"] is not False
        or result["ready_for_operational_dispatch"] is not False
        or result["notification_sent"] is not False
        or result["human_review_required"] is not True
    ):
        raise ValueError(
            "Resposta integrada fora das restricoes LAB."
        )

    return result
