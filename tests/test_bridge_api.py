"""
Testes da ponte PostgreSQL - LAB.

Nao realiza conexoes reais ao banco.
Testa os contratos HTTP e a injecao da conexao restrita.
"""

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.bridge.app import app
from src.bridge.db import connect_bridge_db


def make_context(queue_id=13, historical=False):

    version = 1 if historical else 2

    return {
        "schema_version": "1.0",
        "environment": "LAB",
        "processor": "WF-03",
        "queue_id": queue_id,
        "source_event_id": "LAB-0001",
        "requested_version": version,
        "current_version": 2,
        "is_historical_version": historical,
        "eligible_for_context_review": not historical,
        "context_status": (
            "HISTORICAL_VERSION"
            if historical
            else "READY_FOR_REVIEW"
        ),
        "dispatch_status": "MOCK_ONLY",
        "ai_executed": False,
        "notification_sent": False,
        "evidence_count": 1 if historical else 2,
    }


class TestBridgeAPI(unittest.TestCase):

    def setUp(self):
        self.token = 'LAB_TEST_TOKEN_' + ('x' * 40)
        self.env_patch = patch.dict(
            os.environ,
            {'SOC_BRIDGE_HTTP_TOKEN': self.token},
        )
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.client = TestClient(
            app,
            headers={'Authorization': f'Bearer {self.token}'},
        )

    def tearDown(self):
        self.client.close()

    def test_health(self):

        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(data["environment"], "LAB")
        self.assertEqual(data["status"], "UP")
        self.assertFalse(data["database_checked"])
        self.assertFalse(data["operational_dispatch_allowed"])

    @patch("src.bridge.app.build_context")
    def test_current_version(self, mocked_builder):

        mocked_builder.return_value = make_context()

        response = self.client.get("/lab/context/13")

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertTrue(data["real_database_query"])
        self.assertFalse(data["operational_dispatch_allowed"])
        self.assertTrue(data["human_review_required"])

        self.assertEqual(data["context"]["queue_id"], 13)
        self.assertEqual(
            data["context"]["requested_version"], 2
        )

        self.assertTrue(
            data["context"]["eligible_for_context_review"]
        )

        # Garante que a API injeta a conexao restrita.
        mocked_builder.assert_called_once_with(
            13,
            connection_factory=connect_bridge_db,
        )

    @patch("src.bridge.app.build_context")
    def test_historical_version(self, mocked_builder):

        mocked_builder.return_value = make_context(
            queue_id=12,
            historical=True,
        )

        response = self.client.get("/lab/context/12")

        self.assertEqual(response.status_code, 200)

        context = response.json()["context"]

        self.assertTrue(context["is_historical_version"])
        self.assertFalse(
            context["eligible_for_context_review"]
        )

    @patch("src.bridge.app.build_context")
    def test_missing_context(self, mocked_builder):

        mocked_builder.return_value = None

        response = self.client.get("/lab/context/999999")

        self.assertEqual(response.status_code, 404)

    @patch("src.bridge.app.build_context")
    def test_database_failure(self, mocked_builder):

        mocked_builder.side_effect = RuntimeError(
            "Internal database diagnostic"
        )

        response = self.client.get("/lab/context/13")

        self.assertEqual(response.status_code, 503)

        self.assertNotIn(
            "Internal database diagnostic",
            response.text,
        )

    @patch("src.bridge.app.build_context")
    def test_invalid_contract(self, mocked_builder):

        context = make_context()

        # Resposta nao autorizada.
        context["environment"] = "PRODUCTION"

        mocked_builder.return_value = context

        response = self.client.get("/lab/context/13")

        self.assertEqual(response.status_code, 409)

    def test_invalid_queue_id(self):

        response = self.client.get("/lab/context/0")

        self.assertEqual(response.status_code, 422)



    def test_missing_bearer_token(self):

        response = self.client.get(
            "/lab/context/13",
            headers={"Authorization": ""},
        )

        self.assertEqual(response.status_code, 401)

    def test_invalid_bearer_token(self):

        response = self.client.get(
            "/lab/context/13",
            headers={"Authorization": "Bearer INVALID_TOKEN"},
        )

        self.assertEqual(response.status_code, 401)

    def test_authentication_not_configured(self):

        with patch.dict(
            os.environ,
            {"SOC_BRIDGE_HTTP_TOKEN": ""},
        ):
            response = self.client.get("/lab/context/13")

        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()