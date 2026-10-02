"""
Phase 08 - Local authenticated runtime database consumer.

Reuses the existing FastAPI HTTP client and Stage 19 composer.
No new database connection, live LLM or operational dispatch.
"""

from src.context.local_http_client import (
    MAX_QUEUE_ID,
    ContextClientError,
    fetch_local_context,
)
from src.context.local_mock_composer import run_local_mock_pipeline


def run_local_runtime_pipeline(
    historical_queue_id,
    current_queue_id,
    *,
    cache=None,
    registry=None,
):
    """Retrieve two contexts at runtime and execute the LAB/MOCK pipeline."""

    for queue_id in (historical_queue_id, current_queue_id):
        if type(queue_id) is not int or not 1 <= queue_id <= MAX_QUEUE_ID:
            raise ValueError("Invalid runtime queue_id.")

    if historical_queue_id == current_queue_id:
        raise ValueError("Runtime queues must be distinct.")

    # Both calls use the existing authenticated localhost-only HTTP client.
    historical = fetch_local_context(historical_queue_id)
    current = fetch_local_context(current_queue_id)

    for envelope, expected_queue in (
        (historical, historical_queue_id),
        (current, current_queue_id),
    ):
        if not isinstance(envelope, dict):
            raise ContextClientError("Invalid runtime HTTP envelope.")

        context = envelope.get("context")

        if (
            envelope.get("integration_mode") != "LOCAL_POSTGRES_READ_ONLY"
            or envelope.get("real_database_query") is not True
            or envelope.get("operational_dispatch_allowed") is not False
            or envelope.get("human_review_required") is not True
            or not isinstance(context, dict)
            or type(context.get("queue_id")) is not int
            or context["queue_id"] != expected_queue
        ):
            raise ContextClientError("Runtime context contract mismatch.")

    # Existing composer independently verifies the Gate, identity,
    # historical/current pairing, evidence, signatures and WF-05.
    result = run_local_mock_pipeline(
        historical,
        current,
        cache=cache,
        registry=registry,
    )

    if (
        result.get("pipeline_status") != "COMPLETED"
        or result.get("historical_queue_id") != historical_queue_id
        or result.get("current_queue_id") != current_queue_id
        or result.get("operational_dispatch_allowed") is not False
        or result.get("notification_sent") is not False
        or result.get("real_ollama_call") is not False
        or result.get("verified_against_database") is not False
    ):
        raise ValueError("Integrated runtime result is inconsistent.")

    return {
        **result,
        "context_transport": "AUTHENTICATED_LOCAL_HTTP",
        "runtime_database_query": True,
        # The database supplied context at runtime.
        # WF-04 integrity remains verified IN MEMORY, not in PostgreSQL.
    }