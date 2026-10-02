"""Offline integrity and HTML tests for Phase 09."""

import copy
import unittest

from src.ai_engine.integrity import sha256_json
from src.ai_engine.runtime_integrity import (
    build_runtime_integrity,
    verify_runtime_integrity,
)
from src.reports.runtime_ai_report import build_runtime_ai_report


def make_runtime(mode="INJECTED_TEST_MODEL"):
    analysis = {
        "summary": "Synthetic event.",
        "assessment": "Requires human review.",
        "evidence_ids": ["LAB-EV-001", "LAB-EV-002"],
        "limitations": ["Synthetic evidence."],
        "review_actions": ["Review evidence."],
    }

    return {
        "environment": "LAB",
        "processor": "LOCAL_RUNTIME_AI",
        "execution_mode": mode,
        "pipeline_status": "COMPLETED",
        "historical_status": "SKIPPED",
        "current_status": "ANALYSIS_COMPLETED",
        "historical_queue_id": 12,
        "current_queue_id": 13,
        "context_transport": "AUTHENTICATED_LOCAL_HTTP",
        "runtime_database_query": True,
        "real_ollama_call": mode == "LOCAL_OLLAMA",
        "analysis_signature": sha256_json(analysis),
        "integrity_status": "ANALYSIS_SHA256_CALCULATED",
        "verified_against_database": False,
        "persistence_status": "NOT_ATTEMPTED",
        "human_review_required": True,
        "human_review_completed": False,
        "operational_dispatch_allowed": False,
        "notification_sent": False,
        "wf04_result": {
            "environment": "LAB",
            "processor": "WF-04",
            "queue_id": 13,
            "investigation_id": "LAB-INV-001",
            "source_event_id": "LAB-0001",
            "investigation_version": 2,
            "model": "qwen3:4b-instruct",
            "status": "ANALYSIS_COMPLETED",
            "dispatch_status": "MOCK_ONLY",
            "ai_executed": True,
            "requires_human_review": True,
            "notification_sent": False,
            "real_execution_started": False,
            "provenance": {
                "version": 2,
                "content_signature": "a" * 64,
            },
            "analysis": analysis,
        },
    }


class RuntimeAIArtifactTests(unittest.TestCase):

    def test_01_build_and_verify_signature(self):
        runtime = make_runtime()
        record = build_runtime_integrity(runtime)
        self.assertTrue(verify_runtime_integrity(runtime, record))
        self.assertEqual(record["analysis_signature"], runtime["analysis_signature"])
        self.assertEqual(len(record["result_key"]), 64)

    def test_02_analysis_tampering_fails_closed(self):
        runtime = make_runtime()
        record = build_runtime_integrity(runtime)
        runtime["wf04_result"]["analysis"]["assessment"] = "Changed"
        with self.assertRaises(ValueError):
            verify_runtime_integrity(runtime, record)

    def test_03_record_tampering_is_rejected(self):
        runtime = make_runtime()
        record = build_runtime_integrity(runtime)
        record["result_key"] = "b" * 64
        with self.assertRaises(ValueError):
            verify_runtime_integrity(runtime, record)

    def test_04_mode_is_explicit_in_report(self):
        runtime = make_runtime("LOCAL_OLLAMA")
        html = build_runtime_ai_report(runtime)
        self.assertIn("OLLAMA LOCAL - ANALISE REAL", html)
        self.assertIn("REVISAO HUMANA OBRIGATORIA", html)

    def test_05_offline_mode_is_not_mislabelled(self):
        html = build_runtime_ai_report(make_runtime())
        self.assertIn("MODELO INJETADO - TESTE OFFLINE", html)
        self.assertNotIn("OLLAMA LOCAL - ANALISE REAL", html)

    def test_06_report_escapes_untrusted_text(self):
        runtime = make_runtime()
        runtime["wf04_result"]["analysis"]["summary"] = "<script>alert(1)</script>"
        runtime["analysis_signature"] = sha256_json(
            runtime["wf04_result"]["analysis"]
        )
        html = build_runtime_ai_report(runtime)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)


if __name__ == "__main__":
    unittest.main()