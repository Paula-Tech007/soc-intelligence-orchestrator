"""
Stage 16 - Testes offline de rastreabilidade em memoria.

Reaproveita os resultados MOCK integrados da Etapa 15.

Nenhuma operacao de persistencia, notificacao ou
chamada real ao Ollama e executada.
"""

import copy
import unittest

import test_integrated_mock_report as lab_fixture

from src.observability.persistence_traceability import (
    MemoryTraceabilityError,
    build_memory_traceability,
)


class TestMemoryTraceability(unittest.TestCase):

    def setUp(self):
        self.lab = lab_fixture.TestIntegratedMockReport(
            methodName="test_valid_contract_passes_official_validator"
        )

        self.lab.setUp()
        self.addCleanup(self.lab.doCleanups)

        historical, current = self.lab.observed_pair()

        self.contract = self.lab.assemble(
            historical,
            current,
        )

        self.record = copy.deepcopy(
            current["result"]["integrity_record"]
        )

    def trace(self, contract=None, record=None):
        return build_memory_traceability(
            self.contract if contract is None else contract,
            self.record if record is None else record,
        )

    def test_01_valid_memory_traceability(self):
        result = self.trace()

        self.assertEqual(
            result["integrity_status"],
            "VERIFIED_IN_MEMORY",
        )

        self.assertEqual(
            result["persistence_status"],
            "NOT_ATTEMPTED",
        )

        self.assertEqual(
            result["verification_method"],
            "SHA256_IN_MEMORY",
        )

        self.assertIs(
            result["verified_against_database"],
            False,
        )

        self.assertIsNone(result["database_record_id"])

        self.assertIs(
            result["operational_dispatch_allowed"],
            False,
        )

        self.assertIs(result["notification_sent"], False)
        self.assertIs(result["human_review_required"], True)

        self.lab.ollama.assert_not_called()

    def test_02_original_signatures_preserved(self):
        result = self.trace()

        for field in (
            "content_signature",
            "analysis_signature",
            "result_key",
        ):
            self.assertEqual(
                result[field],
                self.record[field],
            )

        self.assertEqual(
            result["identity"],
            self.record["identity"],
        )

    def test_03_historical_version_stays_skipped(self):
        result = self.trace()

        self.assertEqual(
            result["historical_control"],
            {
                "queue_id": 12,
                "investigation_version": 1,
                "status": "SKIPPED",
                "ai_executed": False,
            },
        )

    def test_04_repeat_is_deterministic(self):
        first = self.trace()
        second = self.trace()

        self.assertEqual(first, second)

        self.assertEqual(
            first["result_key"],
            second["result_key"],
        )

        self.assertIsNone(first["database_record_id"])

    def test_05_does_not_mutate_inputs(self):
        original_contract = copy.deepcopy(self.contract)
        original_record = copy.deepcopy(self.record)

        self.trace()

        self.assertEqual(
            self.contract,
            original_contract,
        )

        self.assertEqual(
            self.record,
            original_record,
        )

    def test_06_output_uses_metadata_allowlist(self):
        result = self.trace()

        self.assertEqual(
            set(result),
            {
                "schema_version",
                "environment",
                "processor",
                "integration_mode",
                "identity",
                "historical_control",
                "content_signature",
                "analysis_signature",
                "result_key",
                "integrity_status",
                "persistence_status",
                "database_record_id",
                "verification_method",
                "verified_against_database",
                "human_review_required",
                "operational_dispatch_allowed",
                "notification_sent",
            },
        )

        self.assertNotIn("analysis", result)
        self.assertNotIn("html", result)
        self.assertNotIn("token", result)
        self.assertNotIn("credentials", result)

        self.assertNotIn(
            "analysis",
            result["identity"],
        )

    def test_07_modified_analysis_is_rejected(self):
        changed = copy.deepcopy(self.contract)

        changed["results"][1]["analysis"]["summary"] = (
            "ALTERACAO_NAO_ASSINADA"
        )

        with self.assertRaises(MemoryTraceabilityError):
            self.trace(contract=changed)

    def test_08_forged_analysis_signature_is_rejected(self):
        changed = copy.deepcopy(self.record)

        changed["analysis_signature"] = "0" * 64

        with self.assertRaises(MemoryTraceabilityError):
            self.trace(record=changed)

    def test_09_divergent_identity_is_rejected(self):
        changed = copy.deepcopy(self.record)

        changed["identity"]["queue_id"] = 999

        with self.assertRaises(MemoryTraceabilityError):
            self.trace(record=changed)

    def test_10_modified_provenance_is_rejected(self):
        changed = copy.deepcopy(self.contract)

        changed["results"][1]["provenance"][
            "content_signature"
        ] = "a" * 64

        with self.assertRaises(MemoryTraceabilityError):
            self.trace(contract=changed)

    def test_11_historical_promotion_is_rejected(self):
        changed = copy.deepcopy(self.contract)

        changed["results"][0]["ai_executed"] = True

        with self.assertRaises(MemoryTraceabilityError):
            self.trace(contract=changed)

    def test_12_operational_dispatch_is_rejected(self):
        changed = copy.deepcopy(self.contract)

        changed["ready_for_operational_dispatch"] = True

        with self.assertRaises(MemoryTraceabilityError):
            self.trace(contract=changed)

    def test_13_missing_record_is_rejected(self):
        with self.assertRaises(MemoryTraceabilityError):
            self.trace(record={})

    def test_14_invalid_contract_is_rejected(self):
        with self.assertRaises(MemoryTraceabilityError):
            self.trace(contract={})


if __name__ == "__main__":
    unittest.main()
