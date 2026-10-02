"""
Phase 09 - Authenticated Runtime AI -> integrity -> HTML.

One model invocation. No database writes or operational dispatch.
"""

from src.ai_engine.runtime_integrity import (
    build_runtime_integrity,
    verify_runtime_integrity,
)
from src.context.local_runtime_ai import run_local_runtime_ai
from src.reports.runtime_ai_report import build_runtime_ai_report


def run_local_runtime_ai_report(
    historical_queue_id,
    current_queue_id,
    *,
    allow_model_execution=False,
    model=None,
):
    if allow_model_execution is not True:
        raise PermissionError(
            "Runtime AI requires explicit enablement."
        )

    runtime = run_local_runtime_ai(
        historical_queue_id,
        current_queue_id,
        allow_model_execution=True,
        model=model,
    )

    required = {
        "pipeline_status": "COMPLETED",
        "report_status": "NOT_GENERATED",
        "human_review_required": True,
        "human_review_completed": False,
        "operational_dispatch_allowed": False,
        "notification_sent": False,
        "verified_against_database": False,
        "persistence_status": "NOT_ATTEMPTED",
    }

    if not isinstance(runtime, dict):
        raise ValueError("Runtime AI result missing.")

    for key, expected in required.items():
        value = runtime.get(key)

        if value != expected or (
            type(expected) is bool and type(value) is not bool
        ):
            raise ValueError("Invalid runtime result: " + key)

    record = build_runtime_integrity(runtime)

    if verify_runtime_integrity(runtime, record) is not True:
        raise ValueError("Runtime integrity verification failed.")

    html = build_runtime_ai_report(runtime, record)

    if (
        not isinstance(html, str)
        or not html.startswith("<!DOCTYPE html>")
    ):
        raise ValueError("Runtime AI HTML generation failed.")

    return {
        "schema_version": "1.0",
        "environment": "LAB",
        "processor": "LOCAL_RUNTIME_AI_REPORT",
        "pipeline_status": "COMPLETED",
        "execution_mode": runtime["execution_mode"],
        "runtime": runtime,
        "integrity_record": record,
        "integrity_status": "VERIFIED_IN_MEMORY",
        "report_status": "AWAITING_HUMAN_REVIEW",
        "html": html,
        "human_review_required": True,
        "human_review_completed": False,
        "verified_against_database": False,
        "persistence_status": "NOT_ATTEMPTED",
        "operational_dispatch_allowed": False,
        "notification_sent": False,
    }