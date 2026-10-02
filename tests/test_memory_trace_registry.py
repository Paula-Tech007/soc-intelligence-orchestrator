"""
Stage 16 - Testes offline do registro idempotente em memoria.

Utiliza rastreabilidade produzida pelo pipeline MOCK
e pelo adaptador validado da Etapa 16.

Nao utiliza PostgreSQL, Ollama real ou notificacoes.
"""

import copy
import unittest

import test_integrated_mock_report as lab_fixture

from src.ai_engine.integrity import sha256_json

from src.observability.persistence_traceability import (
    build_memory_traceability,
)

from src.observability.memory_trace_registry import (
    MemoryTraceConflictError,
    MemoryTraceRegistry,
)


class TestMemoryTraceRegistry(unittest.TestCase):

    def setUp(self):
        self.lab = lab_fixture.TestIntegratedMockReport(
            methodName="test_valid_contract_passes_official_validator"
        )

        self.lab.setUp()
        self.addCleanup(self.lab.doCleanups)

        historical, current = self.lab.observed_pair()

        contract = self.lab.assemble(
            historical,
            current,
        )

        record = current["result"]["integrity_record"]

        self.trace = build_memory_traceability(
            contract,
            record,
        )

        self.registry = MemoryTraceRegistry()

    def test_01_first_registration(self):
        receipt = self.registry.register(self.trace)

        self.assertEqual(
            receipt["status"],
            "MEMORY_NEW_RESULT",
        )
        self.assertEqual(self.registry.count(), 1)
        self.assertEqual(
            receipt["result_key"],
            self.trace["result_key"],
        )

    def test_02_identical_repetition(self):
        first = self.registry.register(self.trace)
        second = self.registry.register(
            copy.deepcopy(self.trace)
        )

        self.assertEqual(
            first["status"],
            "MEMORY_NEW_RESULT",
        )
        self.assertEqual(
            second["status"],
            "MEMORY_ALREADY_REGISTERED",
        )
        self.assertEqual(self.registry.count(), 1)

    def test_03_repeated_receipt_has_no_database_claim(self):
        self.registry.register(self.trace)
        receipt = self.registry.register(self.trace)

        self.assertEqual(
            receipt["persistence_status"],
            "NOT_ATTEMPTED",
        )
        self.assertIsNone(
            receipt["database_record_id"]
        )
        self.assertIs(
            receipt["verified_against_database"],
            False,
        )
        self.assertIs(
            receipt["operational_dispatch_allowed"],
            False,
        )

    def test_04_analysis_signature_conflict(self):
        self.registry.register(self.trace)

        changed = copy.deepcopy(self.trace)
        changed["analysis_signature"] = "b" * 64

        with self.assertRaisesRegex(
            MemoryTraceConflictError,
            "INTEGRITY_CONFLICT",
        ):
            self.registry.register(changed)

        self.assertEqual(self.registry.count(), 1)

        # O registro original permanece integralmente valido.
        repeated = self.registry.register(self.trace)

        self.assertEqual(
            repeated["status"],
            "MEMORY_ALREADY_REGISTERED",
        )

    def test_05_context_signature_conflict(self):
        self.registry.register(self.trace)

        changed = copy.deepcopy(self.trace)

        changed["identity"]["content_signature"] = (
            "c" * 64
        )

        changed["content_signature"] = "c" * 64

        changed["result_key"] = sha256_json(
            changed["identity"]
        )

        with self.assertRaisesRegex(
            MemoryTraceConflictError,
            "INTEGRITY_CONFLICT",
        ):
            self.registry.register(changed)

        self.assertEqual(self.registry.count(), 1)

    def test_06_modified_input_cannot_mutate_registry(self):
        original = copy.deepcopy(self.trace)

        self.registry.register(self.trace)

        self.trace["historical_control"]["status"] = (
            "ALTERADO"
        )

        receipt = self.registry.register(original)

        self.assertEqual(
            receipt["status"],
            "MEMORY_ALREADY_REGISTERED",
        )
        self.assertEqual(self.registry.count(), 1)

    def test_07_instances_are_isolated(self):
        other = MemoryTraceRegistry()

        first = self.registry.register(self.trace)
        second = other.register(self.trace)

        self.assertEqual(
            first["status"],
            "MEMORY_NEW_RESULT",
        )
        self.assertEqual(
            second["status"],
            "MEMORY_NEW_RESULT",
        )

        self.assertEqual(self.registry.count(), 1)
        self.assertEqual(other.count(), 1)

    def test_08_invalid_result_key_rejected(self):
        changed = copy.deepcopy(self.trace)

        changed["result_key"] = "0" * 64

        with self.assertRaises(ValueError):
            self.registry.register(changed)

        self.assertEqual(self.registry.count(), 0)

    def test_09_database_claim_rejected(self):
        changed = copy.deepcopy(self.trace)

        changed["verified_against_database"] = True

        with self.assertRaises(ValueError):
            self.registry.register(changed)

        self.assertEqual(self.registry.count(), 0)

    def test_10_operational_dispatch_rejected(self):
        changed = copy.deepcopy(self.trace)

        changed["operational_dispatch_allowed"] = True

        with self.assertRaises(ValueError):
            self.registry.register(changed)

        self.assertEqual(self.registry.count(), 0)

    def test_11_extra_sensitive_field_rejected(self):
        changed = copy.deepcopy(self.trace)

        changed["analysis"] = {
            "summary": "CONTEUDO_NAO_PERMITIDO",
        }

        with self.assertRaises(ValueError):
            self.registry.register(changed)

        self.assertEqual(self.registry.count(), 0)

    def test_12_historical_promotion_rejected(self):
        changed = copy.deepcopy(self.trace)

        changed["historical_control"]["ai_executed"] = True

        with self.assertRaises(ValueError):
            self.registry.register(changed)

        self.assertEqual(self.registry.count(), 0)

    def test_13_queue_outside_lab_rejected(self):
        changed = copy.deepcopy(self.trace)

        changed["identity"]["queue_id"] = 99

        changed["result_key"] = sha256_json(
            changed["identity"]
        )

        with self.assertRaises(ValueError):
            self.registry.register(changed)

        self.assertEqual(self.registry.count(), 0)

    def test_14_invalid_persistence_status_rejected(self):
        changed = copy.deepcopy(self.trace)

        changed["persistence_status"] = "PERSISTED_VALID"

        with self.assertRaises(ValueError):
            self.registry.register(changed)

        self.assertEqual(self.registry.count(), 0)

    def test_15_invalid_input_does_not_change_count(self):
        self.registry.register(self.trace)

        with self.assertRaises(ValueError):
            self.registry.register(None)

        self.assertEqual(self.registry.count(), 1)

        repeated = self.registry.register(self.trace)

        self.assertEqual(
            repeated["status"],
            "MEMORY_ALREADY_REGISTERED",
        )

    def test_16_no_real_ollama_calls(self):
        self.registry.register(self.trace)
        self.registry.register(self.trace)

        self.lab.ollama.assert_not_called()


if __name__ == "__main__":
    unittest.main()
