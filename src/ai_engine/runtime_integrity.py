"""Phase 09 - In-memory integrity for local Runtime AI results."""

import copy
import re

from src.ai_engine.integrity import sha256_json


def build_runtime_integrity(runtime):
    if not isinstance(runtime, dict):
        raise ValueError("Invalid Runtime AI payload.")

    mode = runtime.get("execution_mode")

    if mode not in ("LOCAL_OLLAMA", "INJECTED_TEST_MODEL"):
        raise ValueError("Unknown execution mode.")

    expected_real = mode == "LOCAL_OLLAMA"

    required = {
        "environment": "LAB",
        "processor": "LOCAL_RUNTIME_AI",
        "pipeline_status": "COMPLETED",
        "historical_status": "SKIPPED",
        "current_status": "ANALYSIS_COMPLETED",
        "runtime_database_query": True,
        "context_transport": "AUTHENTICATED_LOCAL_HTTP",
        "real_ollama_call": expected_real,
        "human_review_required": True,
        "human_review_completed": False,
        "operational_dispatch_allowed": False,
        "notification_sent": False,
        "verified_against_database": False,
        "persistence_status": "NOT_ATTEMPTED",
        "integrity_status": "ANALYSIS_SHA256_CALCULATED",
    }

    for key, expected in required.items():
        if runtime.get(key) != expected or (
            isinstance(expected, bool)
            and type(runtime.get(key)) is not bool
        ):
            raise ValueError("Invalid runtime field: " + key)

    result = runtime.get("wf04_result")

    if not isinstance(result, dict):
        raise ValueError("Missing WF-04 result.")

    wf04_required = {
        "environment": "LAB",
        "processor": "WF-04",
        "status": "ANALYSIS_COMPLETED",
        "dispatch_status": "MOCK_ONLY",
        "ai_executed": True,
        "requires_human_review": True,
        "notification_sent": False,
        "real_execution_started": False,
    }

    for key, expected in wf04_required.items():
        if result.get(key) != expected or (
            isinstance(expected, bool)
            and type(result.get(key)) is not bool
        ):
            raise ValueError("Invalid WF-04 field: " + key)

    if (
        type(runtime.get("current_queue_id")) is not int
        or runtime["current_queue_id"] < 1
        or type(runtime.get("historical_queue_id")) is not int
        or runtime["historical_queue_id"] < 1
        or runtime["historical_queue_id"] == runtime["current_queue_id"]
        or result.get("queue_id") != runtime["current_queue_id"]
        or type(result.get("investigation_version")) is not int
        or result["investigation_version"] < 2
    ):
        raise ValueError("Invalid investigation identity.")

    for field in ("investigation_id", "source_event_id", "model"):
        value = result.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Missing identity: " + field)

    provenance = result.get("provenance")

    if (
        not isinstance(provenance, dict)
        or provenance.get("version") != result["investigation_version"]
        or not isinstance(provenance.get("content_signature"), str)
        or not re.fullmatch(
            r"[a-f0-9]{64}",
            provenance["content_signature"],
        )
    ):
        raise ValueError("Invalid content provenance.")

    analysis = result.get("analysis")

    if not isinstance(analysis, dict) or set(analysis) != {
        "summary",
        "assessment",
        "evidence_ids",
        "limitations",
        "review_actions",
    }:
        raise ValueError("Invalid structured analysis.")

    for key in ("summary", "assessment"):
        if not isinstance(analysis[key], str) or not analysis[key].strip():
            raise ValueError("Invalid analysis text.")

    for key in ("evidence_ids", "limitations", "review_actions"):
        value = analysis[key]
        if (
            not isinstance(value, list)
            or not value
            or not all(isinstance(v, str) and v.strip() for v in value)
        ):
            raise ValueError("Invalid analysis list: " + key)

    if len(set(analysis["evidence_ids"])) != len(analysis["evidence_ids"]):
        raise ValueError("Duplicate evidence references.")

    signature = sha256_json(analysis)

    if runtime.get("analysis_signature") != signature:
        raise ValueError("Analysis SHA-256 mismatch.")

    identity = {
        "execution_mode": mode,
        "investigation_id": result["investigation_id"],
        "source_event_id": result["source_event_id"],
        "queue_id": result["queue_id"],
        "investigation_version": result["investigation_version"],
        "content_signature": provenance["content_signature"],
        "model": result["model"],
    }

    return {
        "schema_version": "1.0",
        "environment": "LAB",
        "execution_mode": mode,
        "identity": copy.deepcopy(identity),
        "analysis": copy.deepcopy(analysis),
        "result_key": sha256_json(identity),
        "analysis_signature": signature,
        "verified_against_database": False,
        "persistence_status": "NOT_ATTEMPTED",
        "operational_dispatch_allowed": False,
    }


def verify_runtime_integrity(runtime, record):
    """Check record hashes and correspondence with its WF-04 source."""

    if not isinstance(record, dict):
        raise ValueError("Missing integrity record.")

    expected = build_runtime_integrity(runtime)

    if record != expected:
        raise ValueError("Runtime integrity verification failed.")

    return True