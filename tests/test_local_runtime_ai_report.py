"""Offline Phase 09 Runtime AI report integration tests."""

import unittest
from unittest.mock import patch

from src.ai_engine.integrity import sha256_json
from src.context.local_runtime_ai_report import (
    run_local_runtime_ai_report,
)
from test_runtime_ai_artifacts import make_runtime


class LocalRuntimeAIReportTests(unittest.TestCase):

    def setUp(self):
        self.runtime = make_runtime()
        self.runtime["report_status"] = "NOT_GENERATED"

        patcher = patch(
            "src.context.local_runtime_ai_report.run_local_runtime_ai",
            return_value=self.runtime,
        )

        self.run_ai = patcher.start()
        self.addCleanup(patcher.stop)

    def execute(self):
        return run_local_runtime_ai_report(
            12,
            13,
            allow_model_execution=True,
            model=object(),
        )

    def test_01_disabled_by_default(self):
        with self.assertRaises(PermissionError):
            run_local_runtime_ai_report(12, 13)

        self.run_ai.assert_not_called()

    def test_02_integrity_and_html(self):
        delivery = self.execute()

        self.assertEqual(delivery["pipeline_status"], "COMPLETED")
        self.assertEqual(
            delivery["integrity_status"],
            "VERIFIED_IN_MEMORY",
        )
        self.assertEqual(
            delivery["report_status"],
            "AWAITING_HUMAN_REVIEW",
        )
        self.assertIn("<!DOCTYPE html>", delivery["html"])
        self.assertIs(delivery["human_review_required"], True)
        self.assertIs(delivery["human_review_completed"], False)
        self.assertIs(delivery["operational_dispatch_allowed"], False)
        self.assertIs(delivery["notification_sent"], False)
        self.run_ai.assert_called_once()

    def test_03_real_mode_label(self):
        self.runtime = make_runtime("LOCAL_OLLAMA")
        self.runtime["report_status"] = "NOT_GENERATED"
        self.run_ai.return_value = self.runtime

        delivery = self.execute()

        self.assertEqual(delivery["execution_mode"], "LOCAL_OLLAMA")
        self.assertIn(
            "OLLAMA LOCAL - ANALISE REAL",
            delivery["html"],
        )

    def test_04_signature_tampering_rejected(self):
        self.runtime["wf04_result"]["analysis"]["assessment"] = "Changed"

        with self.assertRaises(ValueError):
            self.execute()

    def test_05_report_failure_does_not_return_success(self):
        with patch(
            "src.context.local_runtime_ai_report.build_runtime_ai_report",
            side_effect=ValueError("HTML validation failed"),
        ):
            with self.assertRaises(ValueError):
                self.execute()

    def test_06_untrusted_html_is_escaped(self):
        self.runtime["wf04_result"]["analysis"]["summary"] = (
            "<script>alert(1)</script>"
        )

        self.runtime["analysis_signature"] = sha256_json(
            self.runtime["wf04_result"]["analysis"]
        )

        delivery = self.execute()

        self.assertIn("&lt;script&gt;", delivery["html"])
        self.assertNotIn("<script>", delivery["html"])


if __name__ == "__main__":
    unittest.main()