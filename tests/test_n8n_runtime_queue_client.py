"""Offline security regression for the read-only n8n queue client."""

import os
import unittest
from unittest.mock import Mock, patch

from src.context.n8n_runtime_queue_client import (
    QUEUE_URL,
    QueueClientError,
    fetch_lab_runtime_request,
)


def valid_receipt():
    return {
        "schema_version": "1.0",
        "environment": "LAB",
        "processor": "N8N_RUNTIME_QUEUE_READ",
        "test_only": True,
        "operational_dispatch_allowed": False,
        "notification_sent": False,
        "human_review_required": True,
        "human_review_completed": False,
        "transport_status": "QUEUED_REQUEST_AVAILABLE",
        "request_available": True,
        "row_id": 1,
        "request_id": "SOC-LAB-0001-Q12-Q13",
        "source_event_id": "LAB-0001",
        "historical_queue_id": 12,
        "current_queue_id": 13,
        "status": "QUEUED",
        "execution_mode": "LAB_TEST_ONLY",
    }


class N8NRuntimeQueueClientTests(unittest.TestCase):

    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {"SOC_N8N_LAB_HEADER_KEY": "L" * 40},
        )
        self.env.start()
        self.addCleanup(self.env.stop)

        self.http = patch(
            "src.context.n8n_runtime_queue_client.httpx.get"
        )
        self.mock_get = self.http.start()
        self.addCleanup(self.http.stop)

        self.response = Mock()
        self.response.status_code = 200
        self.response.json.return_value = valid_receipt()
        self.mock_get.return_value = self.response

    def test_valid_receipt_returns_dry_run(self):
        result = fetch_lab_runtime_request()

        self.assertEqual(result["request_id"], "SOC-LAB-0001-Q12-Q13")
        self.assertEqual(result["historical_queue_id"], 12)
        self.assertEqual(result["current_queue_id"], 13)
        self.assertEqual(result["execution_mode"], "DRY_RUN")
        self.assertIs(result["model_execution_started"], False)
        self.assertIs(result["table_mutation_attempted"], False)
        self.assertIs(result["notification_sent"], False)
        self.assertIs(result["operational_dispatch_allowed"], False)

    def test_http_is_local_authenticated_and_read_only(self):
        fetch_lab_runtime_request()

        self.mock_get.assert_called_once_with(
            QUEUE_URL,
            headers={"X-SOC-LAB-KEY": "L" * 40},
            timeout=5.0,
            follow_redirects=False,
            trust_env=False,
        )

    def test_no_queued_request_returns_none(self):
        receipt = valid_receipt()
        receipt["transport_status"] = "NO_QUEUED_REQUEST"
        receipt["request_available"] = False
        self.response.json.return_value = receipt

        self.assertIsNone(fetch_lab_runtime_request())

    def test_missing_credential_fails_before_http(self):
        os.environ.pop("SOC_N8N_LAB_HEADER_KEY", None)

        with self.assertRaises(QueueClientError):
            fetch_lab_runtime_request()

        self.mock_get.assert_not_called()

    def test_short_credential_fails_before_http(self):
        os.environ["SOC_N8N_LAB_HEADER_KEY"] = "short"

        with self.assertRaises(QueueClientError):
            fetch_lab_runtime_request()

        self.mock_get.assert_not_called()

    def test_http_403_is_rejected(self):
        self.response.status_code = 403

        with self.assertRaises(QueueClientError):
            fetch_lab_runtime_request()

    def test_invalid_json_is_rejected(self):
        self.response.json.side_effect = ValueError("invalid")

        with self.assertRaises(QueueClientError):
            fetch_lab_runtime_request()

    def test_wrong_fixture_is_rejected(self):
        receipt = valid_receipt()
        receipt["current_queue_id"] = 14
        self.response.json.return_value = receipt

        with self.assertRaises(QueueClientError):
            fetch_lab_runtime_request()

    def test_unsafe_contract_is_rejected(self):
        receipt = valid_receipt()
        receipt["operational_dispatch_allowed"] = True
        self.response.json.return_value = receipt

        with self.assertRaises(QueueClientError):
            fetch_lab_runtime_request()

    def test_boolean_cannot_replace_row_id(self):
        receipt = valid_receipt()
        receipt["row_id"] = True
        self.response.json.return_value = receipt

        with self.assertRaises(QueueClientError):
            fetch_lab_runtime_request()

    def test_rejected_transport_cannot_be_consumed(self):
        receipt = valid_receipt()
        receipt["transport_status"] = "REJECTED_QUEUE_RESPONSE"
        receipt["request_available"] = False
        self.response.json.return_value = receipt

        with self.assertRaises(QueueClientError):
            fetch_lab_runtime_request()

    def test_unexpected_fields_are_not_forwarded(self):
        receipt = valid_receipt()
        receipt["internal_token"] = "must-not-be-forwarded"
        self.response.json.return_value = receipt

        result = fetch_lab_runtime_request()

        self.assertNotIn("internal_token", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)