"""Testes offline da telemetria segura."""

import unittest

from src.observability.collector import (
    collect_review_telemetry,
)


def make_result(
    *,
    gate="READY_FOR_AI_REVIEW",
    review="MOCK_ANALYSIS_COMPLETED",
    integrity="VERIFIED_IN_MEMORY",
    wf04=None,
):
    if wf04 is None and review == "MOCK_ANALYSIS_COMPLETED":
        wf04 = {"cache_hit": False}

    return {
        "gate_decision": {"decision": gate},
        "review_status": review,
        "integrity_status": integrity,
        "wf04_result": wf04,
        "real_ollama_call": False,
        "operational_dispatch_allowed": False,
        "ready_for_operational_dispatch": False,
        "notification_sent": False,
        "human_review_required": True,
    }


class TestObservabilityCollector(unittest.TestCase):

    def test_current_mock_cache_miss(self):
        result = make_result()

        telemetry = collect_review_telemetry(
            result,
            duration_ms=125,
        )

        self.assertEqual(
            telemetry["gate_decision"],
            "READY_FOR_AI_REVIEW",
        )
        self.assertIs(telemetry["cache_hit"], False)
        self.assertEqual(telemetry["duration_ms"], 125)

    def test_current_mock_cache_hit(self):
        result = make_result(wf04={"cache_hit": True})

        telemetry = collect_review_telemetry(
            result,
            duration_ms=5,
        )

        self.assertIs(telemetry["cache_hit"], True)

    def test_historical_has_no_cache_metric(self):
        result = make_result(
            gate="HISTORICAL_CONTEXT",
            review="HISTORICAL_SKIPPED",
            integrity="NOT_APPLICABLE",
        )

        telemetry = collect_review_telemetry(
            result,
            duration_ms=3,
        )

        self.assertIsNone(telemetry["cache_hit"])
        self.assertEqual(
            telemetry["integrity_status"],
            "NOT_APPLICABLE",
        )

    def test_blocked_has_no_cache_metric(self):
        result = make_result(
            gate="BLOCKED_BY_POLICY",
            review="BLOCKED",
            integrity="NOT_APPLICABLE",
        )

        telemetry = collect_review_telemetry(
            result,
            duration_ms=2,
        )

        self.assertIsNone(telemetry["cache_hit"])

    def test_sensitive_content_is_never_copied(self):
        marker = "PRIVATE_TEST_MARKER_DO_NOT_EXPORT"

        result = make_result(
            wf04={
                "cache_hit": False,
                "secret": marker,
                "prompt": marker,
                "evidence": [marker],
            },
        )

        result["authorization"] = marker
        result["integrity_record"] = {"hash": marker}
        result["context"] = {"raw_event": marker}

        telemetry = collect_review_telemetry(
            result,
            duration_ms=10,
        )

        self.assertNotIn(marker, repr(telemetry))

        self.assertEqual(
            set(telemetry),
            {
                "schema_version",
                "environment",
                "pipeline_status",
                "gate_decision",
                "review_status",
                "integrity_status",
                "cache_hit",
                "duration_ms",
                "error_category",
            },
        )

    def test_invalid_duration_is_rejected(self):
        result = make_result()

        for value in (-1, True, 1.5, "10", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    collect_review_telemetry(
                        result,
                        duration_ms=value,
                    )

    def test_invalid_safety_contract_is_rejected(self):
        result = make_result()
        result["operational_dispatch_allowed"] = True

        with self.assertRaises(ValueError):
            collect_review_telemetry(
                result,
                duration_ms=1,
            )

    def test_missing_cache_contract_is_rejected(self):
        result = make_result(wf04={"status": "COMPLETED"})

        with self.assertRaises(ValueError):
            collect_review_telemetry(
                result,
                duration_ms=1,
            )


if __name__ == "__main__":
    unittest.main()
