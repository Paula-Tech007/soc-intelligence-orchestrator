import unittest

from unittest.mock import patch

from src.context.decision_gate import (
    BLOCKED,
    HISTORICAL,
    READY,
)

from src.context.local_http_client import ContextClientError

from src.context.local_decision_pipeline import (
    review_local_context,
)


def fixture(queue_id=13, historical=False, pending=True):

    status = "PENDING" if pending else "COMPLETED"
    eligible = pending and not historical

    return {
        "integration_mode": "LOCAL_POSTGRES_READ_ONLY",
        "real_database_query": True,
        "operational_dispatch_allowed": False,
        "human_review_required": True,
        "context": {
            "schema_version": "1.0",
            "environment": "LAB",
            "processor": "WF-03",
            "queue_id": queue_id,
            "source_event_id": "LAB-0001",
            "queue_status": status,
            "requested_version": 1 if historical else 2,
            "current_version": 2,
            "is_historical_version": historical,
            "eligible_for_context_review": eligible,
            "context_status": (
                "HISTORICAL_VERSION"
                if historical
                else "READY_FOR_REVIEW"
                if eligible
                else "NOT_PENDING"
            ),
            "dispatch_status": "MOCK_ONLY",
            "ai_executed": False,
            "notification_sent": False,
        },
    }


class TestLocalDecisionPipeline(unittest.TestCase):

    def assert_safe(self, decision):

        self.assertFalse(decision["ai_execution_allowed"])
        self.assertFalse(decision["operational_dispatch_allowed"])
        self.assertFalse(decision["notification_sent"])
        self.assertTrue(decision["human_review_required"])

    @patch(
        "src.context.local_decision_pipeline.fetch_local_context"
    )
    def test_current_context(self, fetch):

        fetch.return_value = fixture()

        result = review_local_context(13)

        fetch.assert_called_once_with(13)
        self.assertEqual(result["decision"], READY)
        self.assertTrue(result["eligible_for_ai_review"])
        self.assert_safe(result)

    @patch(
        "src.context.local_decision_pipeline.fetch_local_context"
    )
    def test_historical_context(self, fetch):

        fetch.return_value = fixture(12, historical=True)

        result = review_local_context(12)

        self.assertEqual(result["decision"], HISTORICAL)
        self.assertFalse(result["eligible_for_ai_review"])
        self.assert_safe(result)

    @patch(
        "src.context.local_decision_pipeline.fetch_local_context"
    )
    def test_non_pending_context(self, fetch):

        fetch.return_value = fixture(pending=False)

        result = review_local_context(13)

        self.assertEqual(result["decision"], BLOCKED)
        self.assertEqual(result["reason_code"], "QUEUE_NOT_PENDING")
        self.assert_safe(result)

    @patch(
        "src.context.local_decision_pipeline.fetch_local_context"
    )
    def test_http_failure_is_blocked(self, fetch):

        fetch.side_effect = ContextClientError(
            "Sensitive internal diagnostic"
        )

        result = review_local_context(13)

        self.assertEqual(result["decision"], BLOCKED)
        self.assertEqual(
            result["reason_code"],
            "CONTEXT_FETCH_FAILED",
        )
        self.assertNotIn("Sensitive", str(result))
        self.assert_safe(result)

    @patch(
        "src.context.local_decision_pipeline.fetch_local_context"
    )
    def test_queue_mismatch_is_blocked(self, fetch):

        fetch.return_value = fixture(queue_id=99)

        result = review_local_context(13)

        self.assertEqual(result["decision"], BLOCKED)
        self.assertEqual(
            result["reason_code"],
            "QUEUE_ID_MISMATCH",
        )
        self.assert_safe(result)

    @patch(
        "src.context.local_decision_pipeline.fetch_local_context"
    )
    def test_invalid_id_never_calls_http(self, fetch):

        for value in (0, -1, True, "13", 2147483648):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    review_local_context(value)

        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()