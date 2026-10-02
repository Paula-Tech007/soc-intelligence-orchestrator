"""Phase 09 - Offline tests for the explicit Runtime AI adapter."""

import copy
import json
import unittest

from types import SimpleNamespace
from unittest.mock import call, patch

from test_generic_integrated_mock_report import synthetic_envelope

from src.context.local_runtime_ai import run_local_runtime_ai


class FakeModel:
    def __init__(self, evidence_ids=None, raw=None):
        self.calls = 0
        self.evidence_ids = evidence_ids or ["LAB-ALT-EV-01"]
        self.raw = raw

    def invoke(self, messages):
        self.calls += 1

        content = self.raw

        if content is None:
            content = json.dumps({
                "summary": "Synthetic LAB review.",
                "assessment": "Human review required.",
                "evidence_ids": self.evidence_ids,
                "limitations": ["Synthetic context only."],
                "review_actions": ["Review registered evidence."],
            })

        return SimpleNamespace(content=content)


class RuntimeAITests(unittest.TestCase):

    def setUp(self):
        self.historical = synthetic_envelope(1, 31, 4)
        self.current = synthetic_envelope(2, 32, 5)

        self.model = FakeModel([
            item["evidence_id"]
            for item in self.current["context"]["event"]["evidence"]
        ])

        fetch_patch = patch(
            "src.context.local_runtime_ai.fetch_local_context",
            side_effect=[self.historical, self.current],
        )

        self.fetch = fetch_patch.start()
        self.addCleanup(fetch_patch.stop)

        ollama_patch = patch("src.ai_engine.engine.ChatOllama")
        self.ollama = ollama_patch.start()
        self.addCleanup(ollama_patch.stop)

    def execute(self):
        return run_local_runtime_ai(
            31,
            32,
            allow_model_execution=True,
            model=self.model,
        )

    def test_01_disabled_by_default_without_http(self):
        with self.assertRaises(PermissionError):
            run_local_runtime_ai(31, 32, model=self.model)

        self.fetch.assert_not_called()
        self.assertEqual(self.model.calls, 0)

    def test_02_successful_review_and_distinct_identity(self):
        result = self.execute()

        self.assertEqual(self.fetch.call_args_list, [call(31), call(32)])
        self.assertEqual(result["pipeline_status"], "COMPLETED")
        self.assertEqual(result["historical_status"], "SKIPPED")
        self.assertEqual(result["current_status"], "ANALYSIS_COMPLETED")
        self.assertEqual(result["execution_mode"], "INJECTED_TEST_MODEL")
        self.assertEqual(result["report_status"], "NOT_GENERATED")
        self.assertEqual(len(result["analysis_signature"]), 64)
        self.assertIs(result["human_review_required"], True)
        self.assertIs(result["real_ollama_call"], False)
        self.assertIs(result["verified_against_database"], False)
        self.assertIs(result["notification_sent"], False)
        self.assertIs(result["operational_dispatch_allowed"], False)
        self.assertEqual(self.model.calls, 1)
        self.ollama.assert_not_called()

    def test_03_historical_promotion_is_rejected(self):
        self.historical["context"]["is_historical_version"] = False

        with self.assertRaises(ValueError):
            self.execute()

        self.assertEqual(self.model.calls, 0)
        self.ollama.assert_not_called()

    def test_04_cross_investigation_is_rejected(self):
        self.current["context"]["investigation_id"] = "OTHER-INV"

        with self.assertRaises(ValueError):
            self.execute()

        self.assertEqual(self.model.calls, 0)
        self.ollama.assert_not_called()

    def test_05_invalid_model_json_is_rejected(self):
        self.model.raw = "INVALID_JSON"

        with self.assertRaises(ValueError):
            self.execute()

        self.assertEqual(self.model.calls, 1)
        self.ollama.assert_not_called()

    def test_06_invented_evidence_is_rejected(self):
        self.model.evidence_ids = ["NONEXISTENT-EVIDENCE"]

        with self.assertRaises(ValueError):
            self.execute()

        self.assertEqual(self.model.calls, 1)
        self.ollama.assert_not_called()


if __name__ == "__main__":
    unittest.main()