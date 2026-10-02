"""
Stage 18.6A - Generic in-memory traceability regression.

Synthetic envelopes and offline MOCK only.
No PostgreSQL, real Ollama or dispatch.
"""

import copy
import unittest

import test_generic_integrated_mock_report as fixture

from src.ai_engine.integrity import build_integrity_record

from src.observability.persistence_traceability import (
    MemoryTraceabilityError,
    build_memory_traceability,
)


class GenericMemoryTraceabilityTests(unittest.TestCase):

    def setUp(self):
        self.lab = fixture.GenericIntegratedMockTests(
            methodName="test_01_generic_pair_produces_valid_contract"
        )

        self.lab.setUp()
        self.addCleanup(self.lab.doCleanups)

        historical, current = self.lab.observed_pair()

        self.contract = self.lab.assemble(historical, current)

        self.record = copy.deepcopy(
            current["result"]["integrity_record"]
        )

        # The expected references come from the independent
        # validated synthetic current context, not WF-04 output.
        self.expected = tuple(
            item["evidence_id"]
            for item in self.lab.envelopes[32][
                "context"
            ]["event"]["evidence"]
        )

    def trace(self, contract=None, record=None, expected=None):
        return build_memory_traceability(
            self.contract if contract is None else contract,
            self.record if record is None else record,
            expected_evidence_ids=(
                self.expected if expected is None else expected
            ),
        )

    def test_01_generic_traceability_is_valid(self):
        result = self.trace()

        self.assertEqual(result["identity"]["queue_id"], 32)
        self.assertEqual(
            result["identity"]["investigation_version"], 5,
        )
        self.assertEqual(
            result["identity"]["source_event_id"],
            fixture.EVENT_ID,
        )
        self.assertEqual(
            result["historical_control"]["queue_id"], 31,
        )
        self.assertEqual(
            result["historical_control"]["investigation_version"], 4,
        )

        self.lab.ollama.assert_not_called()

    def test_02_generic_requires_explicit_opt_in(self):
        with self.assertRaises(MemoryTraceabilityError):
            build_memory_traceability(
                self.contract,
                self.record,
            )

    def test_03_signatures_are_preserved(self):
        trace = self.trace()

        for field in (
            "content_signature",
            "analysis_signature",
            "result_key",
        ):
            self.assertEqual(trace[field], self.record[field])

    def test_04_forged_evidence_rejected_even_if_resigned(self):
        changed = copy.deepcopy(self.contract)

        current = changed["results"][1]

        current["analysis"]["evidence_ids"] = [
            self.expected[0],
            "LAB-FORGED-EV",
        ]

        # Reconstruct the WF-04 integrity input without
        # asserting that any database row was verified.
        signed_input = copy.deepcopy(current)

        signed_input.update({
            "fixture_type": "MOCK_AI_RESPONSE",
            "real_ollama_call": False,
            "ready_for_operational_dispatch": False,
        })

        resigned_record = build_integrity_record(signed_input)

        with self.assertRaises(MemoryTraceabilityError):
            self.trace(
                contract=changed,
                record=resigned_record,
            )

    def test_05_modified_signature_is_rejected(self):
        changed = copy.deepcopy(self.record)
        changed["analysis_signature"] = "0" * 64

        with self.assertRaises(MemoryTraceabilityError):
            self.trace(record=changed)

    def test_06_historical_promotion_is_rejected(self):
        changed = copy.deepcopy(self.contract)
        changed["results"][0]["ai_executed"] = True

        with self.assertRaises(MemoryTraceabilityError):
            self.trace(contract=changed)

    def test_07_invalid_trusted_evidence_is_rejected(self):
        with self.assertRaises(MemoryTraceabilityError):
            self.trace(expected=["LAB-NOT-REGISTERED"])

    def test_08_trace_has_no_operational_claim(self):
        result = self.trace()

        self.assertEqual(
            result["persistence_status"], "NOT_ATTEMPTED",
        )
        self.assertEqual(
            result["verification_method"], "SHA256_IN_MEMORY",
        )
        self.assertIs(
            result["verified_against_database"], False,
        )
        self.assertIsNone(result["database_record_id"])
        self.assertIs(
            result["operational_dispatch_allowed"], False,
        )
        self.assertIs(result["notification_sent"], False)
        self.assertIs(result["human_review_required"], True)


if __name__ == "__main__":
    unittest.main()
