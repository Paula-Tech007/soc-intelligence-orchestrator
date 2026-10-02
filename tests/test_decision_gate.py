import copy
import unittest

from src.context.decision_gate import (
    READY,
    HISTORICAL,
    BLOCKED,
    evaluate_context,
)


def payload(
    queue_id=13,
    requested=2,
    current=2,
    queue_status="PENDING",
):
    historical = requested < current
    eligible = queue_status == "PENDING" and not historical

    status = (
        "HISTORICAL_VERSION"
        if historical
        else "READY_FOR_REVIEW"
        if eligible
        else "NOT_PENDING"
    )

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
            "queue_status": queue_status,
            "requested_version": requested,
            "current_version": current,
            "is_historical_version": historical,
            "eligible_for_context_review": eligible,
            "context_status": status,
            "dispatch_status": "MOCK_ONLY",
            "ai_executed": False,
            "notification_sent": False,
        },
    }


class TestDecisionGate(unittest.TestCase):

    def assert_safe(self, result):
        self.assertFalse(result["ai_execution_allowed"])
        self.assertFalse(result["operational_dispatch_allowed"])
        self.assertFalse(result["notification_sent"])
        self.assertTrue(result["human_review_required"])

    def test_current_pending_context_is_ready(self):
        result = evaluate_context(payload())

        self.assertEqual(result["decision"], READY)
        self.assertEqual(
            result["reason_code"],
            "CURRENT_PENDING_CONTEXT",
        )
        self.assertTrue(result["eligible_for_ai_review"])
        self.assert_safe(result)

    def test_historical_context_is_not_ready(self):
        result = evaluate_context(
            payload(queue_id=12, requested=1)
        )

        self.assertEqual(result["decision"], HISTORICAL)
        self.assertFalse(result["eligible_for_ai_review"])
        self.assert_safe(result)

    def test_current_queue_not_pending_is_blocked(self):
        result = evaluate_context(
            payload(queue_status="COMPLETED")
        )

        self.assertEqual(result["decision"], BLOCKED)
        self.assertEqual(
            result["reason_code"],
            "QUEUE_NOT_PENDING",
        )
        self.assert_safe(result)

    def test_missing_envelope_fails_closed(self):
        result = evaluate_context(None)

        self.assertEqual(result["decision"], BLOCKED)
        self.assert_safe(result)

    def test_operational_dispatch_is_rejected(self):
        data = payload()
        data["operational_dispatch_allowed"] = True

        result = evaluate_context(data)

        self.assertEqual(result["decision"], BLOCKED)
        self.assert_safe(result)

    def test_historical_falsely_marked_current_is_blocked(self):
        data = payload(queue_id=12, requested=1)
        data["context"]["is_historical_version"] = False

        result = evaluate_context(data)

        self.assertEqual(result["decision"], BLOCKED)
        self.assertEqual(
            result["reason_code"],
            "INCONSISTENT_VERSION",
        )

    def test_false_eligibility_is_rejected(self):
        data = payload()
        data["context"]["eligible_for_context_review"] = False

        result = evaluate_context(data)

        self.assertEqual(result["decision"], BLOCKED)
        self.assertEqual(
            result["reason_code"],
            "INCONSISTENT_ELIGIBILITY",
        )

    def test_inconsistent_context_status_is_rejected(self):
        data = payload()
        data["context"]["context_status"] = "NOT_PENDING"

        result = evaluate_context(data)

        self.assertEqual(result["decision"], BLOCKED)
        self.assertEqual(
            result["reason_code"],
            "INCONSISTENT_CONTEXT_STATUS",
        )

    def test_notification_flag_is_rejected(self):
        data = payload()
        data["context"]["notification_sent"] = True

        result = evaluate_context(data)

        self.assertEqual(result["decision"], BLOCKED)
        self.assert_safe(result)

    def test_boolean_version_is_rejected(self):
        data = payload()
        data["context"]["requested_version"] = True

        result = evaluate_context(data)

        self.assertEqual(result["decision"], BLOCKED)
        self.assert_safe(result)

    def test_rejects_non_lab_context(self):
        data = payload()
        data["context"]["environment"] = "PRODUCTION"

        result = evaluate_context(data)

        self.assertEqual(result["decision"], BLOCKED)
        self.assert_safe(result)


if __name__ == "__main__":
    unittest.main()