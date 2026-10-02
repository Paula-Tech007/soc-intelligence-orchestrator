"""Phase 08 - Offline regression for the authenticated runtime consumer."""

import copy
import unittest
from unittest.mock import call, patch

from test_generic_integrated_mock_report import synthetic_envelope

from src.ai_engine.cache import AnalysisCache
from src.context.local_http_client import ContextClientError
from src.context.local_runtime_composer import run_local_runtime_pipeline
from src.observability.memory_trace_registry import MemoryTraceRegistry


class LocalRuntimeComposerTests(unittest.TestCase):

    def setUp(self):
        self.historical = synthetic_envelope(1, 31, 4)
        self.current = synthetic_envelope(2, 32, 5)

        fetch_patch = patch(
            "src.context.local_runtime_composer.fetch_local_context",
            side_effect=[self.historical, self.current],
        )
        self.fetch = fetch_patch.start()
        self.addCleanup(fetch_patch.stop)

        model_patch = patch("src.ai_engine.engine.ChatOllama")
        self.model = model_patch.start()
        self.addCleanup(model_patch.stop)

    def execute(self, **kwargs):
        return run_local_runtime_pipeline(31, 32, **kwargs)

    def test_01_authenticated_context_pair_composes_report(self):
        result = self.execute()

        self.assertEqual(self.fetch.call_args_list, [call(31), call(32)])
        self.assertEqual(result["pipeline_status"], "COMPLETED")
        self.assertEqual(result["historical_status"], "SKIPPED")
        self.assertEqual(result["current_status"], "ANALYSIS_COMPLETED")
        self.assertEqual(
            result["context_transport"], "AUTHENTICATED_LOCAL_HTTP"
        )
        self.assertIs(result["runtime_database_query"], True)
        self.assertIn("<!DOCTYPE html>", result["html"])
        self.assertIn("LAB-ALT-EV-01", result["html"])
        self.assertIs(result["verified_against_database"], False)
        self.assertIs(result["operational_dispatch_allowed"], False)
        self.assertIs(result["notification_sent"], False)
        self.assertIs(result["real_ollama_call"], False)
        self.model.assert_not_called()

    def test_02_queue_id_validation_precedes_network(self):
        for args in ((True, 32), (0, 32), (31, 31), (31, "32")):
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    run_local_runtime_pipeline(*args)

        self.fetch.assert_not_called()
        self.model.assert_not_called()

    def test_03_http_failure_closes_pipeline(self):
        self.fetch.side_effect = ContextClientError(
            "Local HTTP unavailable."
        )

        with self.assertRaises(ContextClientError):
            self.execute()

        self.model.assert_not_called()

    def test_04_returned_queue_mismatch_is_rejected(self):
        self.current["context"]["queue_id"] = 99

        with self.assertRaises(ContextClientError):
            self.execute()

        self.model.assert_not_called()

    def test_05_cross_investigation_pair_is_rejected(self):
        self.current["context"]["investigation_id"] = "OTHER-INV"

        with self.assertRaises(ValueError):
            self.execute()

        self.model.assert_not_called()

    def test_06_cache_and_registry_remain_idempotent(self):
        cache = AnalysisCache()
        registry = MemoryTraceRegistry()

        self.fetch.side_effect = [
            copy.deepcopy(self.historical),
            copy.deepcopy(self.current),
            copy.deepcopy(self.historical),
            copy.deepcopy(self.current),
        ]

        first = self.execute(cache=cache, registry=registry)
        second = self.execute(cache=cache, registry=registry)

        self.assertIs(first["cache_hit"], False)
        self.assertIs(second["cache_hit"], True)
        self.assertEqual(
            first["registration"]["status"], "MEMORY_NEW_RESULT"
        )
        self.assertEqual(
            second["registration"]["status"],
            "MEMORY_ALREADY_REGISTERED",
        )
        self.assertEqual(registry.count(), 1)
        self.model.assert_not_called()


if __name__ == "__main__":
    unittest.main()