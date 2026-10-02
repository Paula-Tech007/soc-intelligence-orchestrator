"""
Etapa 15 - Testes integrados do adaptador MOCK para WF-05.

Simula apenas httpx.get. Gate, WF-04 MOCK, cache,
observabilidade, integridade e report_builder sao reais.

Nenhum servico externo e necessario.
"""

import copy
import json
import os
import unittest

from pathlib import Path
from unittest.mock import patch

import httpx

from src.ai_engine.cache import AnalysisCache
from src.observability.pipeline import run_observed_mock_review

from src.reports.integrated_mock_adapter import (
    assemble_integrated_mock_contract,
    build_integrated_mock_report,
)

from src.reports.report_builder import validate_contract


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


class TestIntegratedMockReport(unittest.TestCase):

    def setUp(self):
        self.envelopes = {
            12: make_envelope(1),
            13: make_envelope(2),
        }

        token_patch = patch.dict(
            os.environ,
            {"SOC_BRIDGE_HTTP_TOKEN": "X" * 48},
        )
        token_patch.start()
        self.addCleanup(token_patch.stop)

        http_patch = patch(
            "src.context.local_http_client.httpx.get",
            side_effect=self.serve,
        )
        self.mock_get = http_patch.start()
        self.addCleanup(http_patch.stop)

        ollama_patch = patch(
            "src.ai_engine.engine.ChatOllama"
        )
        self.ollama = ollama_patch.start()
        self.addCleanup(ollama_patch.stop)

    def serve(self, url, **kwargs):
        queue_id = int(url.rsplit("/", 1)[-1])

        if queue_id not in self.envelopes:
            raise AssertionError("Queue fora do LAB.")

        return httpx.Response(
            200,
            json=self.envelopes[queue_id],
            request=httpx.Request("GET", url),
        )

    def observed_pair(self, cache=None):
        if cache is None:
            cache = AnalysisCache()

        historical = run_observed_mock_review(
            12,
            cache=cache,
        )

        current = run_observed_mock_review(
            13,
            cache=cache,
        )

        return historical, current

    def assemble(self, historical, current, envelope=None):
        return assemble_integrated_mock_contract(
            historical,
            current,
            historical_envelope=(
                self.envelopes[12]
                if envelope is None
                else envelope
            ),
        )

    def report(self, historical, current):
        return build_integrated_mock_report(
            historical,
            current,
            historical_envelope=self.envelopes[12],
        )

    def test_valid_contract_passes_official_validator(self):
        historical, current = self.observed_pair()

        contract = self.assemble(historical, current)

        skipped, analyzed = validate_contract(contract)

        self.assertEqual(len(contract["results"]), 2)
        self.assertEqual(skipped["queue_id"], 12)
        self.assertEqual(skipped["status"], "SKIPPED")
        self.assertIsNone(skipped["analysis"])
        self.assertIs(skipped["ai_executed"], False)

        self.assertEqual(analyzed["queue_id"], 13)
        self.assertEqual(
            analyzed["status"],
            "ANALYSIS_COMPLETED",
        )

        self.ollama.assert_not_called()

    def test_html_is_generated_by_official_wf05(self):
        historical, current = self.observed_pair()

        report = self.report(historical, current)

        self.assertEqual(
            report["report_type"],
            "WF05_INTEGRATED_MOCK",
        )
        self.assertEqual(
            report["integrity_status"],
            "VERIFIED_IN_MEMORY",
        )
        self.assertIs(
            report["verified_against_database"],
            False,
        )
        self.assertIs(
            report["operational_dispatch_allowed"],
            False,
        )
        self.assertIs(report["notification_sent"], False)
        self.assertIs(report["human_review_required"], True)

        html = report["html"]

        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("LABORATORIO - ANALISE SIMULADA", html)
        self.assertIn("LAB-EV-001", html)
        self.assertIn("LAB-EV-002", html)
        self.assertIn("Revisão humana obrigatória.", html)

        self.ollama.assert_not_called()

    def test_cache_hit_preserves_valid_report(self):
        cache = AnalysisCache()

        historical, first = self.observed_pair(cache)

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

        first_report = self.report(historical, first)
        second_report = self.report(historical, second)

        self.assertIn("<!DOCTYPE html>", first_report["html"])
        self.assertIn("<!DOCTYPE html>", second_report["html"])

        self.assertEqual(
            first["result"]["integrity_record"][
                "analysis_signature"
            ],
            second["result"]["integrity_record"][
                "analysis_signature"
            ],
        )

        self.ollama.assert_not_called()

    def test_historical_promotion_is_rejected(self):
        historical, current = self.observed_pair()

        changed = copy.deepcopy(historical)

        changed["result"]["review_status"] = (
            "MOCK_ANALYSIS_COMPLETED"
        )

        with self.assertRaises(ValueError):
            self.assemble(changed, current)

    def test_tampered_analysis_is_rejected(self):
        historical, current = self.observed_pair()

        changed = copy.deepcopy(current)

        changed["result"]["wf04_result"]["analysis"][
            "summary"
        ] = "ALTERACAO_NAO_VERIFICADA"

        with self.assertRaises(ValueError):
            self.assemble(historical, changed)

    def test_missing_integrity_is_rejected(self):
        historical, current = self.observed_pair()

        changed = copy.deepcopy(current)
        changed["result"]["integrity_record"] = None

        with self.assertRaises(ValueError):
            self.assemble(historical, changed)

    def test_telemetry_mismatch_is_rejected(self):
        historical, current = self.observed_pair()

        changed = copy.deepcopy(current)

        changed["telemetry"]["review_status"] = "BLOCKED"

        with self.assertRaises(ValueError):
            self.assemble(historical, changed)

    def test_historical_identity_mismatch_is_rejected(self):
        historical, current = self.observed_pair()

        changed_envelope = copy.deepcopy(self.envelopes[12])

        changed_envelope["context"]["source_event_id"] = (
            "LAB-OUTRO-EVENTO"
        )

        with self.assertRaises(ValueError):
            self.assemble(
                historical,
                current,
                envelope=changed_envelope,
            )

    def test_blocked_current_cannot_generate_report(self):
        self.envelopes[13]["context"]["event"][
            "evidence"
        ] = []

        historical, current = self.observed_pair()

        self.assertEqual(
            current["result"]["review_status"],
            "BLOCKED",
        )

        with self.assertRaises(ValueError):
            self.report(historical, current)

        self.ollama.assert_not_called()


if __name__ == "__main__":
    unittest.main()
