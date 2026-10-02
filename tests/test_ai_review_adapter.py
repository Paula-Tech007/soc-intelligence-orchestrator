"""
Testes offline do adaptador Decision Gate -> WF-04.

Utiliza os snapshots oficiais do projeto.
Nenhum modelo, banco ou servidor e iniciado.
"""

import copy
import json
import unittest

from pathlib import Path
from unittest.mock import patch

from src.ai_engine.engine import validate_context

from src.ai_engine.review_adapter import (
    prepare_mock_review_context,
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

    snapshot = next(
        item
        for item in snapshots
        if item["requested_version"] == version
    )

    return {
        "integration_mode": "LOCAL_POSTGRES_READ_ONLY",
        "real_database_query": True,
        "operational_dispatch_allowed": False,
        "human_review_required": True,
        "context": copy.deepcopy(snapshot),
    }


class TestAIReviewAdapter(unittest.TestCase):

    def assert_safe(self, result):
        self.assertFalse(result["ai_executed"])
        self.assertFalse(result["real_ollama_call"])
        self.assertFalse(result["operational_dispatch_allowed"])
        self.assertFalse(result["notification_sent"])
        self.assertTrue(result["human_review_required"])

    @patch("src.ai_engine.engine.ChatOllama")
    def test_current_context_prepared_without_model(self, ollama):

        result = prepare_mock_review_context(envelope(2))

        self.assertEqual(
            result["review_status"],
            "MOCK_CONTEXT_PREPARED",
        )

        self.assertEqual(
            result["gate_decision"]["decision"],
            "READY_FOR_AI_REVIEW",
        )

        self.assertTrue(
            validate_context(result["wf04_context"])["eligible"]
        )

        self.assert_safe(result)
        ollama.assert_not_called()

    @patch("src.ai_engine.engine.ChatOllama")
    def test_historical_context_does_not_reach_engine(self, ollama):

        result = prepare_mock_review_context(envelope(1))

        self.assertEqual(
            result["review_status"],
            "HISTORICAL_SKIPPED",
        )

        self.assertEqual(
            result["gate_decision"]["decision"],
            "HISTORICAL_CONTEXT",
        )

        self.assertIsNone(result["wf04_context"])
        self.assert_safe(result)
        ollama.assert_not_called()

    def test_invalid_http_contract_is_blocked(self):

        data = envelope(2)
        data["operational_dispatch_allowed"] = True

        result = prepare_mock_review_context(data)

        self.assertEqual(result["review_status"], "BLOCKED")
        self.assertIsNone(result["wf04_context"])
        self.assert_safe(result)

    def test_event_identity_mismatch_is_blocked(self):

        data = envelope(2)
        data["context"]["event"]["source_event_id"] = (
            "UNEXPECTED-EVENT"
        )

        result = prepare_mock_review_context(data)

        self.assertEqual(result["review_status"], "BLOCKED")
        self.assertEqual(
            result["gate_decision"]["reason_code"],
            "WF04_CONTEXT_VALIDATION_FAILED",
        )

        self.assertIsNone(result["wf04_context"])
        self.assert_safe(result)

    def test_missing_evidence_is_blocked(self):

        data = envelope(2)
        data["context"]["event"]["evidence"] = []

        result = prepare_mock_review_context(data)

        self.assertEqual(result["review_status"], "BLOCKED")
        self.assertIsNone(result["wf04_context"])
        self.assert_safe(result)

    def test_original_envelope_is_not_modified(self):

        data = envelope(2)
        original = copy.deepcopy(data)

        result = prepare_mock_review_context(data)

        self.assertEqual(data, original)

        self.assertNotIn(
            "validation_status",
            data["context"],
        )

        self.assertEqual(
            result["review_status"],
            "MOCK_CONTEXT_PREPARED",
        )

    def test_current_non_pending_context_is_blocked(self):

        data = envelope(2)
        context = data["context"]

        context["queue_status"] = "COMPLETED"
        context["eligible_for_context_review"] = False
        context["context_status"] = "NOT_PENDING"

        result = prepare_mock_review_context(data)

        self.assertEqual(result["review_status"], "BLOCKED")
        self.assertEqual(
            result["gate_decision"]["reason_code"],
            "QUEUE_NOT_PENDING",
        )
        self.assertIsNone(result["wf04_context"])


if __name__ == "__main__":
    unittest.main()
