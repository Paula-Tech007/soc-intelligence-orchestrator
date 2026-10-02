"""
Phase 09 - Explicit local Runtime AI integration.

Reuses the authenticated HTTP client, Decision Gate,
WF-04 review adapter and existing Ollama engine.

No persistence, notifications or operational dispatch.
The MOCK report/integrity contracts remain untouched.
"""

from src.ai_engine.engine import analyze
from src.ai_engine.integrity import sha256_json
from src.ai_engine.review_adapter import prepare_mock_review_context
from src.context.local_http_client import (
    MAX_QUEUE_ID,
    fetch_local_context,
)


def run_local_runtime_ai(
    historical_queue_id,
    current_queue_id,
    *,
    allow_model_execution=False,
    model=None,
):
    """Run an explicitly enabled LAB context review."""

    # Default is deny, even before contacting the local API.
    if allow_model_execution is not True:
        raise PermissionError("Runtime AI requires explicit enablement.")

    for queue_id in (historical_queue_id, current_queue_id):
        if type(queue_id) is not int or not 1 <= queue_id <= MAX_QUEUE_ID:
            raise ValueError("Invalid queue_id.")

    if historical_queue_id == current_queue_id:
        raise ValueError("Investigation queues must be distinct.")

    historical_envelope = fetch_local_context(historical_queue_id)
    current_envelope = fetch_local_context(current_queue_id)

    historical = prepare_mock_review_context(historical_envelope)
    current = prepare_mock_review_context(current_envelope)

    if (
        historical["review_status"] != "HISTORICAL_SKIPPED"
        or historical["wf04_context"] is not None
        or current["review_status"] != "MOCK_CONTEXT_PREPARED"
    ):
        raise ValueError("Invalid historical/current review pairing.")

    h = historical_envelope["context"]
    c = current_envelope["context"]

    for field in ("investigation_id", "source_event_id"):
        if (
            not isinstance(h.get(field), str)
            or not h[field].strip()
            or h[field] != c.get(field)
        ):
            raise ValueError("Investigation identity mismatch.")

    if (
        h.get("queue_id") != historical_queue_id
        or c.get("queue_id") != current_queue_id
        or type(h.get("requested_version")) is not int
        or type(c.get("requested_version")) is not int
        or c["requested_version"] != h["requested_version"] + 1
        or h.get("current_version") != c["requested_version"]
        or c.get("current_version") != c["requested_version"]
    ):
        raise ValueError("Investigation version mismatch.")

    context = current["wf04_context"]

    # model=None uses the existing localhost-only ChatOllama engine.
    # Injected models are reserved for isolated offline tests.
    result = analyze(context, model=model)

    if (
        result.get("status") != "ANALYSIS_COMPLETED"
        or result.get("queue_id") != current_queue_id
        or result.get("investigation_id") != h["investigation_id"]
        or result.get("source_event_id") != h["source_event_id"]
        or result.get("investigation_version") != c["requested_version"]
        or result.get("provenance") != c.get("provenance")
        or result.get("requires_human_review") is not True
        or result.get("notification_sent") is not False
        or result.get("dispatch_status") != "MOCK_ONLY"
        or result.get("real_execution_started") is not False
    ):
        raise ValueError("Runtime AI result contract mismatch.")

    analysis = result.get("analysis")
    if not isinstance(analysis, dict):
        raise ValueError("Structured analysis missing.")

    allowed_ids = {
        item["evidence_id"]
        for item in context["event"]["evidence"]
    }

    cited_ids = analysis.get("evidence_ids")

    if (
        not isinstance(cited_ids, list)
        or not cited_ids
        or not set(cited_ids).issubset(allowed_ids)
    ):
        raise ValueError("Invalid evidence references.")

    return {
        "schema_version": "1.0",
        "environment": "LAB",
        "processor": "LOCAL_RUNTIME_AI",
        "execution_mode": (
            "LOCAL_OLLAMA" if model is None else "INJECTED_TEST_MODEL"
        ),
        "pipeline_status": "COMPLETED",
        "context_transport": "AUTHENTICATED_LOCAL_HTTP",
        "runtime_database_query": True,
        "historical_queue_id": historical_queue_id,
        "historical_status": "SKIPPED",
        "current_queue_id": current_queue_id,
        "current_status": "ANALYSIS_COMPLETED",
        "wf04_result": result,
        "analysis_signature": sha256_json(analysis),
        "integrity_status": "ANALYSIS_SHA256_CALCULATED",
        "verified_against_database": False,
        "persistence_status": "NOT_ATTEMPTED",
        "report_status": "NOT_GENERATED",
        "human_review_required": True,
        "human_review_completed": False,
        "real_ollama_call": model is None,
        "operational_dispatch_allowed": False,
        "notification_sent": False,
    }