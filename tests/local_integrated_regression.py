"""
Regressao integrada OPCIONAL do SOC Intelligence Orchestrator.

Executar explicitamente, somente no LAB local:
python -m unittest discover -s tests -p "local_integrated_regression.py" -v

Este arquivo nao corresponde ao padrao test_*.py.

Requer:
- FastAPI local em 127.0.0.1:8765;
- PostgreSQL sintetico existente;
- SOC_BRIDGE_HTTP_TOKEN carregado temporariamente.

Nao executa Ollama real nem escreve no banco.
"""

import os
import unittest

from unittest.mock import patch

from src.ai_engine.cache import AnalysisCache
from src.ai_engine.integrity import verify_integrity_record

from src.context.integrated_mock_pipeline import (
    run_integrated_mock_review,
)


class TestLocalIntegratedRegression(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        token = os.environ.get("SOC_BRIDGE_HTTP_TOKEN", "")

        if len(token) < 32:
            raise RuntimeError(
                "Token LAB ausente. Utilize o runner local protegido."
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
    def test_real_local_pipeline(self, ollama):

        cache = AnalysisCache()

        # 1. Queue historica: nenhum modelo deve ser construido.

        with patch(
            "src.ai_engine.review_orchestrator._FixedMockModel"
        ) as mock_model:

            historical = run_integrated_mock_review(
                12,
                cache=cache,
            )

            mock_model.assert_not_called()

        self.assertEqual(
            historical["gate_decision"]["decision"],
            "HISTORICAL_CONTEXT",
        )

        self.assertEqual(
            historical["review_status"],
            "HISTORICAL_SKIPPED",
        )

        self.assertIsNone(historical["wf04_result"])
        self.assertIsNone(historical["integrity_record"])

        self.assertEqual(
            historical["integrity_status"],
            "NOT_APPLICABLE",
        )

        self.assertFalse(
            historical["model_invoked_this_call"]
        )

        self.assert_safe(historical)

        print("\n[OK] Queue 12: historico bloqueado.")

        # 2. Queue atual: processamento MOCK e integridade.

        current = run_integrated_mock_review(
            13,
            cache=cache,
        )

        self.assertEqual(
            current["gate_decision"]["decision"],
            "READY_FOR_AI_REVIEW",
        )

        self.assertEqual(
            current["review_status"],
            "MOCK_ANALYSIS_COMPLETED",
        )

        self.assertEqual(
            current["integrity_status"],
            "VERIFIED_IN_MEMORY",
        )

        self.assertTrue(
            current["model_invoked_this_call"]
        )

        self.assertIs(
            current["wf04_result"]["real_ollama_call"],
            False,
        )

        record = current["integrity_record"]

        self.assertTrue(verify_integrity_record(record))
        self.assert_safe(current)

        print("[OK] Queue 13: MOCK e integridade verificados.")

        # 3. Segunda execucao: reutilizacao do cache.

        cached = run_integrated_mock_review(
            13,
            cache=cache,
        )

        self.assertEqual(
            cached["review_status"],
            "MOCK_ANALYSIS_COMPLETED",
        )

        self.assertIs(
            cached["model_invoked_this_call"],
            False,
        )

        self.assertIs(
            cached["wf04_result"]["cache_hit"],
            True,
        )

        self.assertEqual(
            record["analysis_signature"],
            cached["integrity_record"]["analysis_signature"],
        )

        self.assertEqual(
            record["result_key"],
            cached["integrity_record"]["result_key"],
        )

        self.assertTrue(
            verify_integrity_record(
                cached["integrity_record"]
            )
        )

        self.assert_safe(cached)

        ollama.assert_not_called()

        print("[OK] Cache: segunda invocacao evitada.")
        print("[OK] Ollama real: nao instanciado.")
        print("[OK] Regressao integrada local aprovada.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
