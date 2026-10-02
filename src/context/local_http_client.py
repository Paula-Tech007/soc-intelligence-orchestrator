"""
SOC Intelligence Orchestrator — Local HTTP Context Client.

Consome exclusivamente a ponte FastAPI em localhost.
Nao escreve no banco e nao executa despacho operacional.
"""

import os

import httpx


LOCAL_CONTEXT_URL = "http://127.0.0.1:8765/lab/context"
MAX_QUEUE_ID = 2147483647


class ContextClientError(Exception):
    """Falha controlada no consumo ou contrato HTTP do LAB."""


def fetch_local_context(queue_id: int) -> dict:
    """
    Recupera e valida um contexto do WF-03.

    Retorna o envelope HTTP completo.
    Contextos historicos permanecem identificados como historicos.
    """

    if (
        isinstance(queue_id, bool)
        or not isinstance(queue_id, int)
        or not 1 <= queue_id <= MAX_QUEUE_ID
    ):
        raise ValueError("queue_id fora do intervalo permitido.")

    token = os.environ.get("SOC_BRIDGE_HTTP_TOKEN", "")

    if len(token) < 32:
        raise ContextClientError(
            "Credencial HTTP local indisponivel."
        )

    try:
        response = httpx.get(
            f"{LOCAL_CONTEXT_URL}/{queue_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
            follow_redirects=False,
            trust_env=False,
        )
    except httpx.RequestError as exc:
        raise ContextClientError(
            "Nao foi possivel consultar a ponte HTTP local."
        ) from None

    # Nao incluir resposta HTTP, token, URL ou detalhes de banco
    # nas mensagens de erro ao consumidor.
    if response.status_code != 200:
        raise ContextClientError(
            f"Consulta nao concluida. HTTP {response.status_code}."
        )

    try:
        result = response.json()
    except (ValueError, TypeError):
        raise ContextClientError(
            "Resposta HTTP nao contem JSON valido."
        ) from None

    if not isinstance(result, dict):
        raise ContextClientError(
            "Envelope HTTP invalido."
        )

    if (
        result.get("integration_mode") != "LOCAL_POSTGRES_READ_ONLY"
        or result.get("real_database_query") is not True
        or result.get("operational_dispatch_allowed") is not False
        or result.get("human_review_required") is not True
    ):
        raise ContextClientError(
            "Contrato de integracao HTTP invalido."
        )

    context = result.get("context")

    if not isinstance(context, dict):
        raise ContextClientError(
            "Contexto investigativo ausente."
        )

    if (
        context.get("environment") != "LAB"
        or context.get("processor") != "WF-03"
        or type(context.get("queue_id")) is not int
        or context["queue_id"] != queue_id
        or not isinstance(context.get("source_event_id"), str)
        or not context["source_event_id"].strip()
        or context.get("dispatch_status") != "MOCK_ONLY"
        or context.get("ai_executed") is not False
        or context.get("notification_sent") is not False
    ):
        raise ContextClientError(
            "Contrato investigativo invalido."
        )

    requested = context.get("requested_version")
    current = context.get("current_version")
    historical = context.get("is_historical_version")
    review = context.get("eligible_for_context_review")

    if (
        type(requested) is not int
        or type(current) is not int
        or requested < 1
        or current < requested
        or type(historical) is not bool
        or type(review) is not bool
        or historical != (requested < current)
    ):
        raise ContextClientError(
            "Controle de versoes inconsistente."
        )

    if historical and review:
        raise ContextClientError(
            "Contexto historico indevidamente elegivel."
        )

    return result