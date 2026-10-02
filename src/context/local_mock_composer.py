"""
Stage 19 - Single-call synthetic LAB/MOCK composition.

Consumes a validated historical/current envelope pair.
No network, database access, live LLM or operational dispatch.
"""

import copy
from time import perf_counter_ns

from src.ai_engine.cache import AnalysisCache
from src.ai_engine.review_integrity import run_verified_mock_review
from src.context.decision_gate import evaluate_context
from src.observability.collector import collect_review_telemetry
from src.observability.memory_trace_registry import MemoryTraceRegistry
from src.observability.persistence_traceability import (
    build_memory_traceability,
)
from src.reports.integrated_mock_adapter import (
    assemble_integrated_mock_contract,
)
from src.reports.report_builder import build_report


def run_local_mock_pipeline(
    historical_envelope,
    current_envelope,
    *,
    cache=None,
    registry=None,
):
    """Run one investigation pair through the existing MOCK components."""

    historical_envelope = copy.deepcopy(historical_envelope)
    current_envelope = copy.deepcopy(current_envelope)

    if (
        not isinstance(historical_envelope, dict)
        or not isinstance(current_envelope, dict)
    ):
        raise ValueError("Two LAB context envelopes are required.")

    historical_context = historical_envelope.get("context")
    current_context = current_envelope.get("context")

    if (
        not isinstance(historical_context, dict)
        or not isinstance(current_context, dict)
    ):
        raise ValueError("Both investigation contexts are required.")

    historical_gate = evaluate_context(historical_envelope)
    current_gate = evaluate_context(current_envelope)

    if (
        historical_gate.get("decision") != "HISTORICAL_CONTEXT"
        or current_gate.get("decision") != "READY_FOR_AI_REVIEW"
    ):
        raise ValueError("Invalid historical/current context pairing.")

    for field in ("investigation_id", "source_event_id"):
        value = historical_context.get(field)
        if (
            not isinstance(value, str)
            or not value.strip()
            or value != current_context.get(field)
        ):
            raise ValueError("Investigation identity mismatch.")

    historical_version = historical_context.get("requested_version")
    current_version = current_context.get("requested_version")

    if (
        type(historical_version) is not int
        or type(current_version) is not int
        or current_version != historical_version + 1
        or historical_context.get("current_version") != current_version
        or current_context.get("current_version") != current_version
        or historical_context.get("queue_id")
        == current_context.get("queue_id")
    ):
        raise ValueError("Investigation version mismatch.")

    if cache is None:
        cache = AnalysisCache()

    if registry is None:
        registry = MemoryTraceRegistry()

    if type(cache) is not AnalysisCache:
        raise TypeError("Expected an AnalysisCache instance.")

    if type(registry) is not MemoryTraceRegistry:
        raise TypeError("Expected a MemoryTraceRegistry instance.")

    event = current_context.get("event")
    evidence = event.get("evidence") if isinstance(event, dict) else None

    if (
        not isinstance(evidence, list)
        or not evidence
        or not all(isinstance(item, dict) for item in evidence)
    ):
        raise ValueError("Current context has no valid evidence list.")

    # Authoritative references originate in the supplied context,
    # never in generated model output.
    expected_evidence_ids = tuple(
        item.get("evidence_id") for item in evidence
    )

    if (
        any(
            not isinstance(value, str) or not value.strip()
            for value in expected_evidence_ids
        )
        or len(set(expected_evidence_ids))
        != len(expected_evidence_ids)
        or current_context.get("evidence_count")
        != len(expected_evidence_ids)
    ):
        raise ValueError("Invalid trusted evidence allowlist.")

    def observe(envelope):
        started = perf_counter_ns()
        result = run_verified_mock_review(envelope, cache=cache)
        elapsed = max(0, perf_counter_ns() - started) // 1_000_000

        return {
            "result": result,
            "telemetry": collect_review_telemetry(
                result,
                duration_ms=elapsed,
            ),
        }

    historical = observe(historical_envelope)

    # Historical processing must terminate without analysis.
    if (
        historical["result"]["review_status"] != "HISTORICAL_SKIPPED"
        or historical["result"]["wf04_result"] is not None
    ):
        raise ValueError("Historical version was not skipped.")

    current = observe(current_envelope)

    contract = assemble_integrated_mock_contract(
        historical,
        current,
        historical_envelope=historical_envelope,
        current_envelope=current_envelope,
    )

    integrity_record = current["result"]["integrity_record"]

    trace = build_memory_traceability(
        contract,
        integrity_record,
        expected_evidence_ids=expected_evidence_ids,
    )

    # Complete validation before changing the in-memory registry.
    html = build_report(
        contract,
        expected_evidence_ids=expected_evidence_ids,
    )

    receipt = registry.register(
        trace,
        trusted_contract=contract,
        integrity_record=integrity_record,
        expected_evidence_ids=expected_evidence_ids,
    )

    return {
        "schema_version": "1.0",
        "environment": "LAB",
        "processor": "LOCAL_MOCK_COMPOSER",
        "integration_mode": "IN_MEMORY_MOCK",
        "pipeline_status": "COMPLETED",
        "investigation_id": trace["identity"]["investigation_id"],
        "source_event_id": trace["identity"]["source_event_id"],
        "historical_queue_id": historical_context["queue_id"],
        "current_queue_id": current_context["queue_id"],
        "historical_status": contract["results"][0]["status"],
        "current_status": contract["results"][1]["status"],
        "cache_hit": current["telemetry"]["cache_hit"],
        "integrity_status": "VERIFIED_IN_MEMORY",
        "analysis_signature": trace["analysis_signature"],
        "result_key": trace["result_key"],
        "report_status": "AWAITING_HUMAN_REVIEW",
        "html": html,
        "traceability": copy.deepcopy(trace),
        "registration": copy.deepcopy(receipt),
        "persistence_status": "NOT_ATTEMPTED",
        "verified_against_database": False,
        "human_review_required": True,
        "operational_dispatch_allowed": False,
        "notification_sent": False,
        "real_ollama_call": False,
    }
