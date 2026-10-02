"""
Regressao automatizada do pipeline integrado SOC-LAB.

Somente httpx.get e simulado.
Os componentes de Gate, WF-04 MOCK, cache e integridade
sao executados normalmente.

Nao necessita FastAPI, PostgreSQL, Ollama ou token real.
"""

import copy
import json
import os
import unittest

from pathlib import Path
from unittest.mock import patch

import httpx

from src.ai_engine.cache import AnalysisCache

from src.ai_engine.integrity import verify_integrity_record

from src.context.local_http_client import ContextClientError

from src.context.integrated_mock_pipeline import (
    run_integrated_mock_review,
)


FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "wf03_context_snapshot.json"
)


def make_envelope(version):
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


class TestIntegratedMockRegression(unittest.TestCase):

    def setUp(self):
        token_patch = patch.dict(
            os.environ,
            {"SOC_BRIDGE_HTTP_TOKEN": "X" * 48},
        )

        token_patch.start()
        self.addCleanup(token_patch.stop)

        get_patch = patch(
            "src.context.local_http_client.httpx.get"
        )

        self.mock_get = get_patch.start()
        self.addCleanup(get_patch.stop)

    def serve(self, data, queue_id):
        url = (
            "http://127.0.0.1:8765"
            f"/lab/context/{queue_id}"
        )

        self.mock_get.return_value = httpx.Response(
            200,
            json=data,
            request=httpx.Request("GET", url),
        )

    def assert_safe(self, result):
        self.assertIs(result["real_ollama_call"], False)
        self.assertIs(
            result["operational_dispatch_allowed"],
            False,
        )
        self.assertIs(
            result["ready_for_operational_dispatch"],
            False,
        )
        self.assertIs(result["notification_sent"], False)
        self.assertIs(result["human_review_required"], True)
        self.assertIs(
            result["verified_against_database"],
            False,
        )

    @patch("src.ai_engine.engine.ChatOllama")
    def test_historical_never_invokes_ai(self, ollama):
        self.serve(make_envelope(1), 12)

        result = run_integrated_mock_review(12)

        self.assertEqual(
            result["gate_decision"]["decision"],
            "HISTORICAL_CONTEXT",
        )
        self.assertEqual(
            result["review_status"],
            "HISTORICAL_SKIPPED",
        )
        self.assertIsNone(result["integrity_record"])
        self.assertFalse(result["model_invoked_this_call"])

        self.assert_safe(result)
        ollama.assert_not_called()

    @patch("src.ai_engine.engine.ChatOllama")
    def test_current_generates_verified_mock(self, ollama):
        self.serve(make_envelope(2), 13)

        result = run_integrated_mock_review(13)

        self.assertEqual(
            result["gate_decision"]["decision"],
            "READY_FOR_AI_REVIEW",
        )
        self.assertEqual(
            result["review_status"],
            "MOCK_ANALYSIS_COMPLETED",
        )
        self.assertEqual(
            result["integrity_status"],
            "VERIFIED_IN_MEMORY",
        )

        self.assertTrue(
            verify_integrity_record(
                result["integrity_record"]
            )
        )

        self.assert_safe(result)
        ollama.assert_not_called()

    @patch("src.ai_engine.engine.ChatOllama")
    def test_second_execution_uses_cache(self, ollama):
        self.serve(make_envelope(2), 13)

        cache = AnalysisCache()

        first = run_integrated_mock_review(
            13,
            cache=cache,
        )

        second = run_integrated_mock_review(
            13,
            cache=cache,
        )

        self.assertTrue(first["model_invoked_this_call"])
        self.assertFalse(second["model_invoked_this_call"])

        self.assertTrue(
            second["wf04_result"]["cache_hit"]
        )

        self.assertEqual(
            first["integrity_record"]["analysis_signature"],
            second["integrity_record"]["analysis_signature"],
        )

        self.assert_safe(first)
        self.assert_safe(second)
        ollama.assert_not_called()

    def test_invalid_http_contract_is_rejected(self):
        data = make_envelope(2)
        data["operational_dispatch_allowed"] = True

        self.serve(data, 13)

        with self.assertRaises(ContextClientError):
            run_integrated_mock_review(13)

    def test_invalid_evidence_never_produces_analysis(self):
        data = make_envelope(2)
        data["context"]["event"]["evidence"] = []

        self.serve(data, 13)

        result = run_integrated_mock_review(13)

        self.assertEqual(
            result["review_status"],
            "BLOCKED",
        )
        self.assertIsNone(result["wf04_result"])
        self.assertIsNone(result["integrity_record"])
        self.assertFalse(result["model_invoked_this_call"])
        self.assert_safe(result)

    def test_http_queue_mismatch_is_rejected(self):
        self.serve(make_envelope(2), 12)

        with self.assertRaises(ContextClientError):
            run_integrated_mock_review(12)

    def test_invalid_json_is_rejected(self):
        self.mock_get.return_value = httpx.Response(
            200,
            content=b"not-json",
            request=httpx.Request(
                "GET",
                "http://127.0.0.1:8765/lab/context/13",
            ),
        )

        with self.assertRaises(ContextClientError):
            run_integrated_mock_review(13)

    def test_invalid_id_never_calls_http(self):
        for value in (0, -1, True, "13", 2147483648):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    run_integrated_mock_review(value)

        self.mock_get.assert_not_called()

    def test_tampering_with_integrity_is_detected(self):
        self.serve(make_envelope(2), 13)

        result = run_integrated_mock_review(13)

        tampered = copy.deepcopy(
            result["integrity_record"]
        )

        tampered["analysis"]["summary"] = (
            "Conteudo adulterado."
        )

        with self.assertRaises(ValueError):
            verify_integrity_record(tampered)


if __name__ == "__main__":
    unittest.main()
