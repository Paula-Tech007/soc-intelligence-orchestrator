"""
Testes offline da integridade do AI Review Orchestrator.
"""

import copy
import json
import unittest

from pathlib import Path
from unittest.mock import patch

from src.ai_engine.cache import AnalysisCache

from src.ai_engine.integrity import (
    sha256_json,
    verify_integrity_record,
)

from src.ai_engine.review_integrity import (
    run_verified_mock_review,
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


class TestAIReviewIntegrity(unittest.TestCase):

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
    def test_current_generates_verified_record(self, ollama):
        result = run_verified_mock_review(envelope(2))

        self.assertEqual(
            result["review_status"],
            "MOCK_ANALYSIS_COMPLETED",
        )

        self.assertEqual(
            result["integrity_status"],
            "VERIFIED_IN_MEMORY",
        )

        record = result["integrity_record"]

        self.assertTrue(verify_integrity_record(record))
        self.assertEqual(len(record["analysis_signature"]), 64)
        self.assertEqual(len(record["content_signature"]), 64)
        self.assertEqual(len(record["result_key"]), 64)

        self.assertEqual(
            record["analysis_signature"],
            sha256_json(result["wf04_result"]["analysis"]),
        )

        self.assert_safe(result)
        ollama.assert_not_called()

    @patch(
        "src.ai_engine.review_integrity.build_integrity_record"
    )
    def test_historical_never_generates_record(self, builder):
        result = run_verified_mock_review(envelope(1))

        self.assertEqual(
            result["review_status"],
            "HISTORICAL_SKIPPED",
        )

        self.assertEqual(
            result["integrity_status"],
            "NOT_APPLICABLE",
        )

        self.assertIsNone(result["integrity_record"])
        self.assert_safe(result)
        builder.assert_not_called()

    @patch(
        "src.ai_engine.review_integrity.build_integrity_record"
    )
    def test_blocked_never_generates_record(self, builder):
        data = envelope(2)
        data["operational_dispatch_allowed"] = True

        result = run_verified_mock_review(data)

        self.assertEqual(result["review_status"], "BLOCKED")
        self.assertIsNone(result["integrity_record"])

        self.assert_safe(result)
        builder.assert_not_called()

    def test_modified_analysis_is_detected(self):
        result = run_verified_mock_review(envelope(2))

        tampered = copy.deepcopy(result["integrity_record"])

        tampered["analysis"]["summary"] = (
            "Conteudo alterado apos assinatura."
        )

        with self.assertRaises(ValueError):
            verify_integrity_record(tampered)

    def test_modified_identity_is_detected(self):
        result = run_verified_mock_review(envelope(2))

        tampered = copy.deepcopy(result["integrity_record"])
        tampered["identity"]["source_event_id"] = "ALTERED"

        with self.assertRaises(ValueError):
            verify_integrity_record(tampered)

    @patch(
        "src.ai_engine.review_integrity.verify_integrity_record"
    )
    def test_verification_failure_interrupts_processing(
        self,
        verifier,
    ):
        verifier.side_effect = ValueError(
            "Assinatura inconsistente."
        )

        with self.assertRaises(ValueError):
            run_verified_mock_review(envelope(2))

    def test_cache_keeps_analysis_signature(self):
        cache = AnalysisCache()
        data = envelope(2)

        first = run_verified_mock_review(data, cache=cache)
        second = run_verified_mock_review(data, cache=cache)

        self.assertTrue(first["model_invoked_this_call"])
        self.assertFalse(second["model_invoked_this_call"])

        self.assertEqual(
            first["integrity_record"]["analysis_signature"],
            second["integrity_record"]["analysis_signature"],
        )

        self.assertEqual(
            first["integrity_record"]["result_key"],
            second["integrity_record"]["result_key"],
        )

        self.assert_safe(first)
        self.assert_safe(second)

    def test_original_envelope_is_preserved(self):
        data = envelope(2)
        original = copy.deepcopy(data)

        run_verified_mock_review(data)

        self.assertEqual(data, original)


if __name__ == "__main__":
    unittest.main()
