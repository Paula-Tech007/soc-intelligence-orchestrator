"""Synthetic Stage 19 pipeline demonstration."""

import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ai_engine.cache import AnalysisCache
from src.context.local_mock_composer import run_local_mock_pipeline
from src.observability.memory_trace_registry import MemoryTraceRegistry


def main():
    fixture = ROOT / "tests" / "fixtures" / "wf03_context_snapshot.json"
    snapshots = json.loads(fixture.read_text(encoding="utf-8"))

    if not isinstance(snapshots, list) or len(snapshots) != 2:
        raise ValueError("Expected two synthetic snapshots.")

    versions = {item["requested_version"]: item for item in snapshots}

    if set(versions) != {1, 2}:
        raise ValueError("Invalid synthetic fixture versions.")

    def envelope(version):
        return {
            "integration_mode": "LOCAL_POSTGRES_READ_ONLY",
            "real_database_query": True,
            "operational_dispatch_allowed": False,
            "human_review_required": True,
            "context": copy.deepcopy(versions[version]),
        }

    # Reuse exported LAB snapshots; no live database query.
    historical = envelope(1)
    current = envelope(2)

    cache = AnalysisCache()
    registry = MemoryTraceRegistry()

    first = run_local_mock_pipeline(
        historical, current, cache=cache, registry=registry
    )
    second = run_local_mock_pipeline(
        historical, current, cache=cache, registry=registry
    )

    checks = {
        "pipeline": first["pipeline_status"] == "COMPLETED",
        "historical": first["historical_status"] == "SKIPPED",
        "current": first["current_status"] == "ANALYSIS_COMPLETED",
        "integrity": first["integrity_status"] == "VERIFIED_IN_MEMORY",
        "first_registration": (
            first["registration"]["status"] == "MEMORY_NEW_RESULT"
        ),
        "idempotent_registration": (
            second["registration"]["status"]
            == "MEMORY_ALREADY_REGISTERED"
        ),
        "cache_reused": second["cache_hit"] is True,
        "one_memory_record": registry.count() == 1,
        "same_signature": (
            first["analysis_signature"] == second["analysis_signature"]
        ),
        "human_review": first["human_review_required"] is True,
        "no_dispatch": first["operational_dispatch_allowed"] is False,
        "no_notification": first["notification_sent"] is False,
        "no_database_verification": first["verified_against_database"] is False,
        "no_persistence": first["persistence_status"] == "NOT_ATTEMPTED",
        "no_live_ollama": first["real_ollama_call"] is False,
        "html_generated": (
            isinstance(first["html"], str)
            and "<!DOCTYPE html>" in first["html"]
        ),
    }

    for name, passed in checks.items():
        if not passed:
            raise RuntimeError("Demonstration failed: " + name)

    output = (
        Path(tempfile.gettempdir())
        / "soc-intelligence-orchestrator"
        / "lab-0001-stage19.html"
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(first["html"], encoding="utf-8")

    print()
    print("=== SOC INTELLIGENCE ORCHESTRATOR ===")

    for name in checks:
        print("[OK]", name)

    print("[OK] HTML:", output)
    print("RESULT: PIPELINE COMPLETED")


if __name__ == "__main__":
    main()