"""
Stage 18.6B - Generic in-memory registry tests.

Only synthetic LAB/MOCK contracts are accepted.
No PostgreSQL, real Ollama or dispatch.
"""

import copy
import unittest

import test_generic_memory_traceability as fixture

from src.observability.memory_trace_registry import (
    MemoryTraceRegistry,
)


class GenericMemoryTraceRegistryTests(unittest.TestCase):

    def setUp(self):
        self.lab = fixture.GenericMemoryTraceabilityTests(
            methodName="test_01_generic_traceability_is_valid"
        )

        self.lab.setUp()
        self.addCleanup(self.lab.doCleanups)

        self.trace = self.lab.trace()
        self.registry = MemoryTraceRegistry()

        self.trust = {
            "trusted_contract": self.lab.contract,
            "integrity_record": self.lab.record,
            "expected_evidence_ids": self.lab.expected,
        }

    def register(self, trace=None, **changes):
        options = dict(self.trust)
        options.update(changes)

        return self.registry.register(
            self.trace if trace is None else trace,
            **options,
        )

    def test_01_generic_first_registration(self):
        receipt = self.register()

        self.assertEqual(receipt["status"], "MEMORY_NEW_RESULT")
        self.assertEqual(self.registry.count(), 1)
        self.assertEqual(
            receipt["result_key"], self.trace["result_key"],
        )

        self.lab.lab.ollama.assert_not_called()

    def test_02_identical_repeat_is_idempotent(self):
        first = self.register()
        second = self.register(copy.deepcopy(self.trace))

        self.assertEqual(first["status"], "MEMORY_NEW_RESULT")
        self.assertEqual(
            second["status"], "MEMORY_ALREADY_REGISTERED",
        )
        self.assertEqual(self.registry.count(), 1)

    def test_03_generic_trace_rejected_in_legacy_mode(self):
        with self.assertRaises(ValueError):
            self.registry.register(self.trace)

        self.assertEqual(self.registry.count(), 0)

    def test_04_incomplete_trust_inputs_rejected(self):
        with self.assertRaises(ValueError):
            self.registry.register(
                self.trace,
                trusted_contract=self.lab.contract,
            )

        self.assertEqual(self.registry.count(), 0)

    def test_05_modified_trace_signature_rejected(self):
        changed = copy.deepcopy(self.trace)
        changed["analysis_signature"] = "0" * 64

        with self.assertRaises(ValueError):
            self.register(changed)

        self.assertEqual(self.registry.count(), 0)

    def test_06_changed_trusted_evidence_rejected(self):
        with self.assertRaises(ValueError):
            self.register(
                expected_evidence_ids=["LAB-UNKNOWN-EVIDENCE"],
            )

        self.assertEqual(self.registry.count(), 0)

    def test_07_modified_historical_control_rejected(self):
        changed = copy.deepcopy(self.trace)
        changed["historical_control"]["queue_id"] = 99

        with self.assertRaises(ValueError):
            self.register(changed)

        self.assertEqual(self.registry.count(), 0)

    def test_08_operational_flags_rejected(self):
        for field in (
            "operational_dispatch_allowed",
            "notification_sent",
            "verified_against_database",
        ):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.trace)
                changed[field] = True

                with self.assertRaises(ValueError):
                    self.register(changed)

        self.assertEqual(self.registry.count(), 0)

    def test_09_forged_original_record_rejected(self):
        changed = copy.deepcopy(self.lab.record)
        changed["analysis_signature"] = "a" * 64

        with self.assertRaises(ValueError):
            self.register(integrity_record=changed)

        self.assertEqual(self.registry.count(), 0)

    def test_10_receipt_has_no_persistence_claim(self):
        receipt = self.register()

        self.assertEqual(
            receipt["persistence_status"], "NOT_ATTEMPTED",
        )
        self.assertIsNone(receipt["database_record_id"])
        self.assertIs(
            receipt["verified_against_database"], False,
        )
        self.assertIs(
            receipt["operational_dispatch_allowed"], False,
        )


if __name__ == "__main__":
    unittest.main()
