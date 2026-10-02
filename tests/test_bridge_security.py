"""
SOC Intelligence Orchestrator
Etapa 06.8 - API Security Regression

Testes isolados: nenhuma conexao real ao PostgreSQL.
"""

import os
import unittest

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.bridge.app import app


LAB_TOKEN = "LAB_SECURITY_TEST_" + ("x" * 40)


class TestBridgeSecurity(unittest.TestCase):

    def setUp(self):

        self.environment = patch.dict(
            os.environ,
            {"SOC_BRIDGE_HTTP_TOKEN": LAB_TOKEN},
        )

        self.environment.start()
        self.addCleanup(self.environment.stop)

        self.client = TestClient(app)
        self.addCleanup(self.client.close)

        self.url = "/lab/context/13"

    @patch("src.bridge.app.build_context")
    def test_missing_token_never_queries_database(self, builder):

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 401)
        builder.assert_not_called()

    @patch("src.bridge.app.build_context")
    def test_invalid_token_never_queries_database(self, builder):

        response = self.client.get(
            self.url,
            headers={"Authorization": "Bearer INVALID_TOKEN"},
        )

        self.assertEqual(response.status_code, 401)
        builder.assert_not_called()

    @patch("src.bridge.app.build_context")
    def test_missing_server_secret_fails_closed(self, builder):

        with patch.dict(
            os.environ,
            {"SOC_BRIDGE_HTTP_TOKEN": ""},
        ):
            response = self.client.get(
                self.url,
                headers={
                    "Authorization": f"Bearer {LAB_TOKEN}"
                },
            )

        self.assertEqual(response.status_code, 503)
        builder.assert_not_called()

    @patch("src.bridge.app.build_context")
    def test_invalid_queue_id_never_queries_database(self, builder):

        response = self.client.get(
            "/lab/context/invalid",
            headers={
                "Authorization": f"Bearer {LAB_TOKEN}"
            },
        )

        self.assertEqual(response.status_code, 422)
        builder.assert_not_called()

    @patch("src.bridge.app.build_context")
    def test_queue_id_above_limit_is_rejected(self, builder):

        response = self.client.get(
            "/lab/context/2147483648",
            headers={
                "Authorization": f"Bearer {LAB_TOKEN}"
            },
        )

        self.assertEqual(response.status_code, 422)
        builder.assert_not_called()

    @patch("src.bridge.app.build_context")
    def test_internal_database_error_is_sanitized(self, builder):

        builder.side_effect = RuntimeError(
            "SENSITIVE_INTERNAL_DATABASE_DIAGNOSTIC"
        )

        response = self.client.get(
            self.url,
            headers={
                "Authorization": f"Bearer {LAB_TOKEN}"
            },
        )

        self.assertEqual(response.status_code, 503)

        self.assertNotIn(
            "SENSITIVE_INTERNAL_DATABASE_DIAGNOSTIC",
            response.text,
        )

        self.assertNotIn(
            "Traceback",
            response.text,
        )

    @patch("src.bridge.app.build_context")
    def test_health_does_not_query_database(self, builder):

        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(data["environment"], "LAB")
        self.assertFalse(data["database_checked"])
        self.assertFalse(data["operational_dispatch_allowed"])

        self.assertNotIn("password", response.text.lower())
        self.assertNotIn("token", response.text.lower())

        builder.assert_not_called()


if __name__ == "__main__":
    unittest.main()