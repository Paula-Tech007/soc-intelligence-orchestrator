"""
Stage 18.3 - Offline generic WF-05 contract regression.

Synthetic fixtures only. No database, Ollama or dispatch.
The evidence allowlist is independently provided by the caller.
"""

import copy
import json
import unittest
from pathlib import Path

from src.reports.report_builder import build_report, validate_contract


FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "wf04_output_mock.json"
)

EXPECTED = ("LAB-ALT-EV-01", "LAB-ALT-EV-02")


def generic_fixture():
    contract = json.loads(FIXTURE.read_text(encoding="utf-8-sig"))

    historical, current = contract["results"]

    for item, queue, version in (
        (historical, 31, 4),
        (current, 32, 5),
    ):
        item["investigation_id"] = "INV-LAB-ALT-002"
        item["source_event_id"] = "LAB-ALT-002"
        item["queue_id"] = queue
        item["investigation_version"] = version
        item["provenance"]["version"] = version

    current["analysis"]["evidence_ids"] = list(EXPECTED)
    return contract


class GenericWF05ContractTests(unittest.TestCase):

    def test_01_legacy_fixture_remains_valid(self):
        original = json.loads(FIXTURE.read_text(encoding="utf-8-sig"))
        old, new = validate_contract(original)
        self.assertEqual((old["queue_id"], new["queue_id"]), (12, 13))

    def test_02_generic_opt_in_accepts_new_identity(self):
        contract = generic_fixture()
        before = copy.deepcopy(contract)

        old, new = validate_contract(
            contract, expected_evidence_ids=EXPECTED,
        )

        self.assertEqual((old["queue_id"], new["queue_id"]), (31, 32))
        self.assertEqual((old["investigation_version"],
                          new["investigation_version"]), (4, 5))
        self.assertEqual(contract, before)

    def test_03_generic_contract_requires_explicit_opt_in(self):
        with self.assertRaises(ValueError):
            validate_contract(generic_fixture())

    def test_04_generic_html_contains_correct_identity(self):
        html = build_report(
            generic_fixture(),
            expected_evidence_ids=EXPECTED,
        )
        for value in ("LAB-ALT-002", "INV-LAB-ALT-002",
                      "LAB-ALT-EV-01", "LAB-ALT-EV-02"):
            self.assertIn(value, html)
        self.assertIn("Revis", html)

    def test_05_untrusted_evidence_is_rejected(self):
        contract = generic_fixture()
        contract["results"][1]["analysis"]["evidence_ids"] = [
            "LAB-ALT-EV-01", "LAB-FORGED-EV"
        ]
        with self.assertRaises(ValueError):
            validate_contract(
                contract, expected_evidence_ids=EXPECTED,
            )

    def test_06_duplicate_evidence_is_rejected(self):
        contract = generic_fixture()
        contract["results"][1]["analysis"]["evidence_ids"] = [
            EXPECTED[0], EXPECTED[0],
        ]
        with self.assertRaises(ValueError):
            validate_contract(
                contract, expected_evidence_ids=EXPECTED,
            )

    def test_07_invalid_allowlist_is_rejected(self):
        for allowlist in ([], [" "], [EXPECTED[0], EXPECTED[0]]):
            with self.subTest(allowlist=allowlist):
                with self.assertRaises(ValueError):
                    validate_contract(
                        generic_fixture(),
                        expected_evidence_ids=allowlist,
                    )

    def test_08_non_consecutive_versions_are_rejected(self):
        contract = generic_fixture()
        contract["results"][1]["investigation_version"] = 8
        contract["results"][1]["provenance"]["version"] = 8

        with self.assertRaises(ValueError):
            validate_contract(
                contract, expected_evidence_ids=EXPECTED,
            )

    def test_09_invalid_queue_and_identity_are_rejected(self):
        for change in ("queue", "identity"):
            with self.subTest(change=change):
                contract = generic_fixture()

                if change == "queue":
                    contract["results"][1]["queue_id"] = True
                else:
                    contract["results"][0]["source_event_id"] = "OTHER"

                with self.assertRaises(ValueError):
                    validate_contract(
                        contract, expected_evidence_ids=EXPECTED,
                    )

    def test_10_historical_promotion_is_rejected(self):
        contract = generic_fixture()
        contract["results"][0]["ai_executed"] = True

        with self.assertRaises(ValueError):
            validate_contract(
                contract, expected_evidence_ids=EXPECTED,
            )

    def test_11_operational_dispatch_is_rejected(self):
        contract = generic_fixture()
        contract["ready_for_operational_dispatch"] = True

        with self.assertRaises(ValueError):
            validate_contract(
                contract, expected_evidence_ids=EXPECTED,
            )

    def test_12_generic_html_escapes_event_content(self):
        contract = generic_fixture()
        contract["results"][1]["analysis"]["summary"] = (
            "<script>alert(1)</script>"
        )

        html = build_report(
            contract,
            expected_evidence_ids=EXPECTED,
        )

        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()
