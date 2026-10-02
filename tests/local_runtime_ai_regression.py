"""Optional local Phase 09 regression. Excluded from offline CI."""

import unittest

from src.ai_engine.engine import MODEL_NAME
from src.context.local_runtime_ai import run_local_runtime_ai


class LocalRuntimeAIRegression(unittest.TestCase):

    def test_authenticated_context_with_real_ollama(self):
        result = run_local_runtime_ai(
            12,
            13,
            allow_model_execution=True,
        )

        self.assertEqual(result["pipeline_status"], "COMPLETED")
        self.assertEqual(result["execution_mode"], "LOCAL_OLLAMA")
        self.assertEqual(result["context_transport"], "AUTHENTICATED_LOCAL_HTTP")
        self.assertIs(result["runtime_database_query"], True)
        self.assertEqual(result["historical_status"], "SKIPPED")
        self.assertEqual(result["current_status"], "ANALYSIS_COMPLETED")
        self.assertEqual(result["wf04_result"]["model"], MODEL_NAME)
        self.assertIs(result["real_ollama_call"], True)
        self.assertEqual(len(result["analysis_signature"]), 64)
        self.assertEqual(
            result["integrity_status"],
            "ANALYSIS_SHA256_CALCULATED",
        )
        self.assertIs(result["verified_against_database"], False)
        self.assertEqual(result["persistence_status"], "NOT_ATTEMPTED")
        self.assertEqual(result["report_status"], "NOT_GENERATED")
        self.assertIs(result["human_review_required"], True)
        self.assertIs(result["human_review_completed"], False)
        self.assertIs(result["operational_dispatch_allowed"], False)
        self.assertIs(result["notification_sent"], False)

        print("[OK] PostgreSQL/FastAPI consultados.")
        print("[OK] Versao historica ignorada.")
        print("[OK] Ollama real executou WF-04.")
        print("[OK] Analise assinada em memoria.")
        print("[OK] Sem despacho ou notificacoes.")


if __name__ == "__main__":
    unittest.main(verbosity=2)