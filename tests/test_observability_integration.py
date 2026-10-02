"""
Etapa 14 - Regressao integrada da observabilidade SOC-LAB.

Somente o transporte HTTP e simulado.
Gate, WF-04 MOCK, cache, integridade e observabilidade
executam normalmente.

Nao requer PostgreSQL, FastAPI, Ollama ou token real.
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

from src.observability.pipeline import (
    run_observed_mock_review,
)


FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "wf03_context_snapshot.json"
)


TELEMETRY_KEYS = {
    "schema_version",
    "environment",
    "pipeline_status",
    "gate_decision",
    "review_status",
    "integrity_status",
    "cache_hit",
    "duration_ms",
    "error_category",
}


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


class TestObservabilityIntegration(unittest.TestCase):

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

    def serve(self, envelope, queue_id):
        url = (
            "http://127.0.0.1:8765"
            f"/lab/context/{queue_id}"
        )

        self.mock_get.return_value = httpx.Response(
            200,
            json=envelope,
            request=httpx.Request("GET", url),
        )

    def assert_safe(self, output):
        result = output["result"]
        telemetry = output["telemetry"]

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

        self.assertEqual(set(telemetry), TELEMETRY_KEYS)
        self.assertEqual(telemetry["environment"], "LAB")
        self.assertEqual(
            telemetry["pipeline_status"],
            "COMPLETED",
        )
        self.assertIs(type(telemetry["duration_ms"]), int)
        self.assertGreaterEqual(
            telemetry["duration_ms"],
            0,
        )
        self.assertIsNone(telemetry["error_category"])

    @patch("src.ai_engine.engine.ChatOllama")
    def test_historical_queue_12(self, ollama):
        self.serve(make_envelope(1), 12)

        output = run_observed_mock_review(12)
        result = output["result"]
        telemetry = output["telemetry"]

        self.assertEqual(
            telemetry["gate_decision"],
            "HISTORICAL_CONTEXT",
        )
        self.assertEqual(
            telemetry["review_status"],
            "HISTORICAL_SKIPPED",
        )
        self.assertEqual(
            telemetry["integrity_status"],
            "NOT_APPLICABLE",
        )
        self.assertIsNone(telemetry["cache_hit"])
        self.assertIsNone(result["integrity_record"])

        self.assert_safe(output)
        ollama.assert_not_called()

    @patch("src.ai_engine.engine.ChatOllama")
    def test_current_queue_13_cache_miss(self, ollama):
        self.serve(make_envelope(2), 13)

        output = run_observed_mock_review(
            13,
            cache=AnalysisCache(),
        )

        result = output["result"]
        telemetry = output["telemetry"]

        self.assertEqual(
            telemetry["gate_decision"],
            "READY_FOR_AI_REVIEW",
        )
        self.assertEqual(
            telemetry["review_status"],
            "MOCK_ANALYSIS_COMPLETED",
        )
        self.assertEqual(
            telemetry["integrity_status"],
            "VERIFIED_IN_MEMORY",
        )
        self.assertIs(telemetry["cache_hit"], False)
        self.assertTrue(result["model_invoked_this_call"])

        self.assertTrue(
            verify_integrity_record(
                result["integrity_record"]
            )
        )

        self.assert_safe(output)
        ollama.assert_not_called()

    @patch("src.ai_engine.engine.ChatOllama")
    def test_second_queue_13_uses_cache(self, ollama):
        self.serve(make_envelope(2), 13)

        cache = AnalysisCache()

        first = run_observed_mock_review(
            13,
            cache=cache,
        )

        second = run_observed_mock_review(
            13,
            cache=cache,
        )

        self.assertIs(
            first["telemetry"]["cache_hit"],
            False,
        )
        self.assertIs(
            second["telemetry"]["cache_hit"],
            True,
        )

        self.assertTrue(
            first["result"]["model_invoked_this_call"]
        )
        self.assertFalse(
            second["result"]["model_invoked_this_call"]
        )

        self.assertEqual(
            first["result"]["integrity_record"][
                "analysis_signature"
            ],
            second["result"]["integrity_record"][
                "analysis_signature"
            ],
        )

        self.assert_safe(first)
        self.assert_safe(second)
        ollama.assert_not_called()

    @patch("src.ai_engine.engine.ChatOllama")
    def test_invalid_evidence_is_blocked(self, ollama):
        envelope = make_envelope(2)
        envelope["context"]["event"]["evidence"] = []

        self.serve(envelope, 13)

        output = run_observed_mock_review(13)

        self.assertEqual(
            output["telemetry"]["gate_decision"],
            "BLOCKED_BY_POLICY",
        )
        self.assertEqual(
            output["telemetry"]["review_status"],
            "BLOCKED",
        )
        self.assertIsNone(
            output["telemetry"]["cache_hit"]
        )
        self.assertIsNone(
            output["result"]["wf04_result"]
        )

        self.assert_safe(output)
        ollama.assert_not_called()

    @patch("src.ai_engine.engine.ChatOllama")
    def test_telemetry_does_not_export_internal_data(
        self,
        ollama,
    ):
        self.serve(make_envelope(2), 13)

        output = run_observed_mock_review(13)

        result = output["result"]
        telemetry = output["telemetry"]

        self.assertEqual(set(telemetry), TELEMETRY_KEYS)

        self.assertNotIn(
            "integrity_record",
            telemetry,
        )
        self.assertNotIn(
            "wf04_result",
            telemetry,
        )
        self.assertNotIn(
            "context",
            telemetry,
        )
        self.assertNotIn(
            "evidence",
            telemetry,
        )

        signature = result["integrity_record"][
            "analysis_signature"
        ]

        self.assertNotIn(signature, repr(telemetry))

        self.assert_safe(output)
        ollama.assert_not_called()

    def test_invalid_http_contract_has_no_telemetry(self):
        envelope = make_envelope(2)
        envelope["operational_dispatch_allowed"] = True

        self.serve(envelope, 13)

        with patch(
            "src.observability.pipeline.collect_review_telemetry"
        ) as collector:

            with self.assertRaises(ContextClientError):
                run_observed_mock_review(13)

            collector.assert_not_called()


if __name__ == "__main__":
    unittest.main()
