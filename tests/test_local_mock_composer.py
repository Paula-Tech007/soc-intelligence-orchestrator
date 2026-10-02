"""
Stage 19 - Offline integration tests for the local MOCK composer.
"""

import copy
import unittest
from unittest.mock import patch

from test_generic_integrated_mock_report import synthetic_envelope

from src.ai_engine.cache import AnalysisCache
from src.context.local_mock_composer import run_local_mock_pipeline
from src.observability.memory_trace_registry import MemoryTraceRegistry


class LocalMockComposerTests(unittest.TestCase):

    def setUp(self):
        self.historical = synthetic_envelope(1, 31, 4)
        self.current = synthetic_envelope(2, 32, 5)

        model_patch = patch("src.ai_engine.engine.ChatOllama")
        self.model = model_patch.start()
        self.addCleanup(model_patch.stop)

        http_patch = patch(
            "src.context.local_http_client.httpx.get",
            side_effect=AssertionError("HTTP must not be called"),
        )
        self.http = http_patch.start()
        self.addCleanup(http_patch.stop)

    def execute(self, **kwargs):
        return run_local_mock_pipeline(
            self.historical,
            self.current,
            **kwargs,
        )

    def test_01_complete_synthetic_execution(self):
        result = self.execute()

        self.assertEqual(result["pipeline_status"], "COMPLETED")
        self.assertEqual(result["historical_status"], "SKIPPED")
        self.assertEqual(
            result["current_status"], "ANALYSIS_COMPLETED"
        )
        self.assertEqual(result["current_queue_id"], 32)
        self.assertIn("<!DOCTYPE html>", result["html"])
        self.assertIn("LAB-ALT-EV-01", result["html"])
        self.assertEqual(
            result["registration"]["status"], "MEMORY_NEW_RESULT"
        )
        self.assertEqual(
            result["integrity_status"], "VERIFIED_IN_MEMORY"
        )
        self.assertIs(result["verified_against_database"], False)
        self.assertIs(result["operational_dispatch_allowed"], False)
        self.assertIs(result["notification_sent"], False)
        self.assertIs(result["human_review_required"], True)
        self.model.assert_not_called()
        self.http.assert_not_called()

    def test_02_input_envelopes_are_not_mutated(self):
        original_h = copy.deepcopy(self.historical)
        original_c = copy.deepcopy(self.current)

        self.execute()

        self.assertEqual(self.historical, original_h)
        self.assertEqual(self.current, original_c)

    def test_03_cache_and_registry_repetition(self):
        cache = AnalysisCache()
        registry = MemoryTraceRegistry()

        first = self.execute(cache=cache, registry=registry)
        second = self.execute(cache=cache, registry=registry)

        self.assertIs(first["cache_hit"], False)
        self.assertIs(second["cache_hit"], True)
        self.assertEqual(
            first["analysis_signature"],
            second["analysis_signature"],
        )
        self.assertEqual(
            first["registration"]["status"], "MEMORY_NEW_RESULT"
        )
        self.assertEqual(
            second["registration"]["status"],
            "MEMORY_ALREADY_REGISTERED",
        )
        self.assertEqual(registry.count(), 1)
        self.model.assert_not_called()
        self.http.assert_not_called()

    def test_04_identity_mismatch_fails_closed(self):
        self.current["context"]["investigation_id"] = "OTHER-INV"

        with self.assertRaises(ValueError):
            self.execute()

        self.model.assert_not_called()
        self.http.assert_not_called()

    def test_05_historical_promotion_fails_closed(self):
        self.historical["context"]["is_historical_version"] = False

        with self.assertRaises(ValueError):
            self.execute()

        self.model.assert_not_called()
        self.http.assert_not_called()

    def test_06_duplicate_evidence_fails_closed(self):
        evidence = self.current["context"]["event"]["evidence"]
        evidence[1]["evidence_id"] = evidence[0]["evidence_id"]

        with self.assertRaises(ValueError):
            self.execute()

        self.model.assert_not_called()
        self.http.assert_not_called()


if __name__ == "__main__":
    unittest.main()
