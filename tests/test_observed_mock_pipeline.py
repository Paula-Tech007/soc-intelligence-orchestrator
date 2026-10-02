"""Testes offline da instrumentacao opcional."""

import unittest

from unittest.mock import patch, sentinel

from src.observability.pipeline import (
    run_observed_mock_review,
)


def make_result(
    *,
    gate="READY_FOR_AI_REVIEW",
    review="MOCK_ANALYSIS_COMPLETED",
    integrity="VERIFIED_IN_MEMORY",
    cache_hit=False,
):
    wf04 = None

    if review == "MOCK_ANALYSIS_COMPLETED":
        wf04 = {
            "cache_hit": cache_hit,
            "internal_evidence": "DO_NOT_EXPORT",
        }

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


class TestObservedMockPipeline(unittest.TestCase):

    def execute(self, result, *, start=1_000_000_000, end=1_125_000_000):
        with (
            patch(
                "src.observability.pipeline.run_integrated_mock_review",
                return_value=result,
            ) as integrated,
            patch(
                "src.observability.pipeline.perf_counter_ns",
                side_effect=[start, end],
            ),
        ):
            output = run_observed_mock_review(13)
            integrated.assert_called_once_with(13, cache=None)

        return output

    def test_preserves_original_result_identity(self):
        result = make_result()

        output = self.execute(result)

        self.assertIs(output["result"], result)
        self.assertEqual(output["telemetry"]["duration_ms"], 125)

    def test_cache_miss(self):
        output = self.execute(make_result(cache_hit=False))

        self.assertIs(output["telemetry"]["cache_hit"], False)

    def test_cache_hit(self):
        output = self.execute(make_result(cache_hit=True))

        self.assertIs(output["telemetry"]["cache_hit"], True)

    def test_historical_context(self):
        result = make_result(
            gate="HISTORICAL_CONTEXT",
            review="HISTORICAL_SKIPPED",
            integrity="NOT_APPLICABLE",
        )

        output = self.execute(result)

        self.assertIsNone(output["telemetry"]["cache_hit"])
        self.assertEqual(
            output["telemetry"]["review_status"],
            "HISTORICAL_SKIPPED",
        )

    def test_blocked_context(self):
        result = make_result(
            gate="BLOCKED_BY_POLICY",
            review="BLOCKED",
            integrity="NOT_APPLICABLE",
        )

        output = self.execute(result)

        self.assertEqual(
            output["telemetry"]["gate_decision"],
            "BLOCKED_BY_POLICY",
        )
        self.assertIsNone(output["telemetry"]["cache_hit"])

    def test_cache_is_forwarded_unchanged(self):
        result = make_result()

        with (
            patch(
                "src.observability.pipeline.run_integrated_mock_review",
                return_value=result,
            ) as integrated,
            patch(
                "src.observability.pipeline.perf_counter_ns",
                side_effect=[0, 2_000_000],
            ),
        ):
            output = run_observed_mock_review(
                13,
                cache=sentinel.original_cache,
            )

        integrated.assert_called_once_with(
            13,
            cache=sentinel.original_cache,
        )
        self.assertIs(output["result"], result)

    def test_sensitive_content_not_exported(self):
        result = make_result()
        result["context"] = {
            "token": "PRIVATE_TEST_MARKER",
        }

        output = self.execute(result)

        self.assertNotIn(
            "PRIVATE_TEST_MARKER",
            repr(output["telemetry"]),
        )
        self.assertNotIn(
            "DO_NOT_EXPORT",
            repr(output["telemetry"]),
        )

    def test_pipeline_failure_is_propagated(self):
        with (
            patch(
                "src.observability.pipeline.run_integrated_mock_review",
                side_effect=ValueError("PRIVATE_TEST_MARKER"),
            ),
            patch(
                "src.observability.pipeline.collect_review_telemetry",
            ) as collector,
            patch(
                "src.observability.pipeline.perf_counter_ns",
                return_value=100,
            ),
        ):
            with self.assertRaises(ValueError):
                run_observed_mock_review(13)

            collector.assert_not_called()

    def test_invalid_safety_contract_never_returns_success(self):
        result = make_result()
        result["operational_dispatch_allowed"] = True

        with self.assertRaises(ValueError):
            self.execute(result)

    def test_clock_regression_is_clamped_to_zero(self):
        result = make_result()

        output = self.execute(
            result,
            start=2_000_000,
            end=1_000_000,
        )

        self.assertEqual(
            output["telemetry"]["duration_ms"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
