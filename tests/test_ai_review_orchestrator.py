import copy
import json
import unittest

from pathlib import Path
from unittest.mock import patch

from src.ai_engine.cache import AnalysisCache
from src.ai_engine.integrity import validate_result

from src.ai_engine.review_orchestrator import (
    run_mock_review,
)


FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "wf03_context_snapshot.json"
)


def envelope(version):
    snapshots = json.loads(
        FIXTURE.read_text(encoding="utf-8")
    )

    context = next(
        copy.deepcopy(item)
        for item in snapshots
        if item["requested_version"] == version
    )

    return {
        "integration_mode": "LOCAL_POSTGRES_READ_ONLY",
        "real_database_query": True,
        "operational_dispatch_allowed": False,
        "human_review_required": True,
        "context": context,
    }


class TestAIReviewOrchestrator(unittest.TestCase):

    def assert_safe(self, result):
        self.assertFalse(result["real_ollama_call"])
        self.assertFalse(result["operational_dispatch_allowed"])
        self.assertFalse(
            result["ready_for_operational_dispatch"]
        )
        self.assertFalse(result["notification_sent"])
        self.assertTrue(result["human_review_required"])

    @patch(
        "src.ai_engine.review_orchestrator._FixedMockModel"
    )
    def test_historical_never_constructs_model(self, model):
        result = run_mock_review(envelope(1))

        self.assertEqual(
            result["review_status"],
            "HISTORICAL_SKIPPED",
        )
        self.assertIsNone(result["wf04_result"])
        self.assertFalse(result["model_invoked_this_call"])
        self.assert_safe(result)
        model.assert_not_called()

    @patch(
        "src.ai_engine.review_orchestrator._FixedMockModel"
    )
    def test_invalid_contract_never_constructs_model(self, model):
        data = envelope(2)
        data["operational_dispatch_allowed"] = True

        result = run_mock_review(data)

        self.assertEqual(result["review_status"], "BLOCKED")
        self.assertIsNone(result["wf04_result"])
        self.assert_safe(result)
        model.assert_not_called()

    @patch(
        "src.ai_engine.review_orchestrator._FixedMockModel"
    )
    def test_invalid_evidence_never_constructs_model(self, model):
        data = envelope(2)
        data["context"]["event"]["evidence"] = []

        result = run_mock_review(data)

        self.assertEqual(result["review_status"], "BLOCKED")
        self.assertIsNone(result["wf04_result"])
        model.assert_not_called()

    @patch("src.ai_engine.engine.ChatOllama")
    def test_current_uses_only_mock(self, ollama):
        result = run_mock_review(envelope(2))

        self.assertEqual(
            result["review_status"],
            "MOCK_ANALYSIS_COMPLETED",
        )

        wf04 = result["wf04_result"]

        self.assertTrue(validate_result(wf04))
        self.assertTrue(wf04["ai_executed"])
        self.assertFalse(wf04["real_ollama_call"])
        self.assertEqual(
            wf04["fixture_type"],
            "MOCK_AI_RESPONSE",
        )
        self.assertTrue(result["model_invoked_this_call"])
        self.assert_safe(result)
        ollama.assert_not_called()

    def test_current_cites_only_existing_evidence(self):
        data = envelope(2)

        expected = {
            item["evidence_id"]
            for item in data["context"]["event"]["evidence"]
        }

        result = run_mock_review(data)

        actual = set(
            result["wf04_result"]["analysis"]["evidence_ids"]
        )

        self.assertEqual(actual, expected)
        self.assert_safe(result)

    @patch("src.ai_engine.engine.ChatOllama")
    def test_cache_prevents_second_mock_invocation(self, ollama):
        cache = AnalysisCache()
        data = envelope(2)

        first = run_mock_review(data, cache=cache)
        second = run_mock_review(data, cache=cache)

        self.assertTrue(first["model_invoked_this_call"])
        self.assertFalse(second["model_invoked_this_call"])

        self.assertFalse(first["wf04_result"]["cache_hit"])
        self.assertTrue(second["wf04_result"]["cache_hit"])

        self.assert_safe(first)
        self.assert_safe(second)
        ollama.assert_not_called()

    def test_input_is_not_mutated(self):
        data = envelope(2)
        original = copy.deepcopy(data)

        run_mock_review(data)

        self.assertEqual(data, original)

    def test_non_pending_is_blocked(self):
        data = envelope(2)
        context = data["context"]

        context["queue_status"] = "COMPLETED"
        context["eligible_for_context_review"] = False
        context["context_status"] = "NOT_PENDING"

        result = run_mock_review(data)

        self.assertEqual(result["review_status"], "BLOCKED")
        self.assertIsNone(result["wf04_result"])
        self.assertFalse(result["model_invoked_this_call"])
        self.assert_safe(result)


if __name__ == "__main__":
    unittest.main()
