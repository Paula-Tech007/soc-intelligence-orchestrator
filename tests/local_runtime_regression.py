"""
Phase 08 - Optional authenticated local runtime regression.

Requires PostgreSQL LAB, local FastAPI and temporary DPAPI token.
Not included in offline GitHub Actions.
"""

import unittest
from unittest.mock import patch

from src.ai_engine.cache import AnalysisCache
from src.context.local_runtime_composer import run_local_runtime_pipeline
from src.observability.memory_trace_registry import MemoryTraceRegistry


class LocalRuntimeRegression(unittest.TestCase):

    @patch("src.ai_engine.engine.ChatOllama")
    def test_live_database_context_to_html(self, ollama):
        cache = AnalysisCache()
        registry = MemoryTraceRegistry()

        first = run_local_runtime_pipeline(
            12, 13, cache=cache, registry=registry
        )

        self.assertEqual(first["pipeline_status"], "COMPLETED")
        self.assertEqual(
            first["context_transport"],
            "AUTHENTICATED_LOCAL_HTTP",
        )
        self.assertIs(first["runtime_database_query"], True)
        self.assertEqual(first["historical_status"], "SKIPPED")
        self.assertEqual(
            first["current_status"], "ANALYSIS_COMPLETED"
        )
        self.assertEqual(
            first["integrity_status"], "VERIFIED_IN_MEMORY"
        )
        self.assertEqual(
            first["report_status"], "AWAITING_HUMAN_REVIEW"
        )
        self.assertIn("<!DOCTYPE html>", first["html"])
        self.assertIs(first["verified_against_database"], False)
        self.assertIs(first["operational_dispatch_allowed"], False)
        self.assertIs(first["notification_sent"], False)
        self.assertIs(first["real_ollama_call"], False)

        second = run_local_runtime_pipeline(
            12, 13, cache=cache, registry=registry
        )

        self.assertIs(first["cache_hit"], False)
        self.assertIs(second["cache_hit"], True)
        self.assertEqual(
            second["registration"]["status"],
            "MEMORY_ALREADY_REGISTERED",
        )
        self.assertEqual(registry.count(), 1)

        ollama.assert_not_called()

        print("[OK] Phase 08 authenticated local E2E passed.")


if __name__ == "__main__":
    unittest.main(verbosity=2)