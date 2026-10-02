import os
import unittest

from unittest.mock import Mock, patch

import httpx

from src.context.local_http_client import (
    ContextClientError,
    fetch_local_context,
)


TEST_TOKEN = "SOC_LAB_TEST_TOKEN_" + ("x" * 40)


def valid_payload(queue_id=13, historical=False):
    current = 2
    requested = 1 if historical else 2

    return {
        "integration_mode": "LOCAL_POSTGRES_READ_ONLY",
        "real_database_query": True,
        "operational_dispatch_allowed": False,
        "human_review_required": True,
        "context": {
            "environment": "LAB",
            "processor": "WF-03",
            "queue_id": queue_id,
            "source_event_id": "LAB-0001",
            "requested_version": requested,
            "current_version": current,
            "is_historical_version": historical,
            "eligible_for_context_review": not historical,
            "dispatch_status": "MOCK_ONLY",
            "ai_executed": False,
            "notification_sent": False,
        },
    }


class TestLocalHTTPClient(unittest.TestCase):

    def setUp(self):
        env = patch.dict(
            os.environ,
            {"SOC_BRIDGE_HTTP_TOKEN": TEST_TOKEN},
        )
        env.start()
        self.addCleanup(env.stop)

    @patch("src.context.local_http_client.httpx.get")
    def test_current_context(self, get):
        get.return_value = Mock(
            status_code=200,
            json=lambda: valid_payload(),
        )

        result = fetch_local_context(13)

        self.assertEqual(result["context"]["requested_version"], 2)

        args, kwargs = get.call_args

        self.assertEqual(
            args[0],
            "http://127.0.0.1:8765/lab/context/13",
        )
        self.assertEqual(
            kwargs["headers"]["Authorization"],
            f"Bearer {TEST_TOKEN}",
        )
        self.assertFalse(kwargs["follow_redirects"])
        self.assertFalse(kwargs["trust_env"])

    @patch("src.context.local_http_client.httpx.get")
    def test_historical_context_is_identified(self, get):
        get.return_value = Mock(
            status_code=200,
            json=lambda: valid_payload(12, historical=True),
        )

        result = fetch_local_context(12)
        context = result["context"]

        self.assertTrue(context["is_historical_version"])
        self.assertFalse(context["eligible_for_context_review"])

    @patch("src.context.local_http_client.httpx.get")
    def test_invalid_queue_id_never_calls_http(self, get):
        for value in (0, -1, True, "13", 2147483648):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    fetch_local_context(value)

        get.assert_not_called()

    @patch("src.context.local_http_client.httpx.get")
    def test_missing_token_never_calls_http(self, get):
        with patch.dict(
            os.environ,
            {"SOC_BRIDGE_HTTP_TOKEN": ""},
        ):
            with self.assertRaises(ContextClientError):
                fetch_local_context(13)

        get.assert_not_called()

    @patch("src.context.local_http_client.httpx.get")
    def test_authentication_error_is_controlled(self, get):
        get.return_value = Mock(status_code=401)

        with self.assertRaisesRegex(
            ContextClientError,
            "HTTP 401",
        ):
            fetch_local_context(13)

    @patch("src.context.local_http_client.httpx.get")
    def test_network_failure_is_controlled(self, get):
        get.side_effect = httpx.ConnectError(
            "Sensitive diagnostic placeholder"
        )

        with self.assertRaises(ContextClientError) as result:
            fetch_local_context(13)

        self.assertNotIn(
            "Sensitive diagnostic placeholder",
            str(result.exception),
        )

    @patch("src.context.local_http_client.httpx.get")
    def test_operational_dispatch_is_rejected(self, get):
        payload = valid_payload()
        payload["operational_dispatch_allowed"] = True

        get.return_value = Mock(
            status_code=200,
            json=lambda: payload,
        )

        with self.assertRaises(ContextClientError):
            fetch_local_context(13)

    @patch("src.context.local_http_client.httpx.get")
    def test_historical_review_is_rejected(self, get):
        payload = valid_payload(12, historical=True)
        payload["context"]["eligible_for_context_review"] = True

        get.return_value = Mock(
            status_code=200,
            json=lambda: payload,
        )

        with self.assertRaises(ContextClientError):
            fetch_local_context(12)

    @patch("src.context.local_http_client.httpx.get")
    def test_queue_mismatch_is_rejected(self, get):
        get.return_value = Mock(
            status_code=200,
            json=lambda: valid_payload(queue_id=99),
        )

        with self.assertRaises(ContextClientError):
            fetch_local_context(13)


if __name__ == "__main__":
    unittest.main()