"""
Stage 18.5B - Generic integrated SOC-LAB regression.

All data is synthetic. HTTP and Ollama are mocked.
No PostgreSQL connection, notification or dispatch.
"""

import copy
import os
import unittest

from unittest.mock import patch

import httpx

from test_integrated_mock_report import make_envelope

from src.ai_engine.cache import AnalysisCache
from src.ai_engine.integrity import (
    build_integrity_record,
    sha256_json,
)

from src.observability.pipeline import run_observed_mock_review

from src.reports.integrated_mock_adapter import (
    assemble_integrated_mock_contract,
    build_integrated_mock_report,
)

from src.reports.report_builder import validate_contract


EVENT_ID = "LAB-ALT-002"
INVESTIGATION_ID = "INV-LAB-ALT-002"

EVIDENCE = (
    "LAB-ALT-EV-01",
    "LAB-ALT-EV-02",
)


def synthetic_envelope(original_version, queue_id, new_version):
    envelope = make_envelope(original_version)
    context = envelope["context"]

    context["queue_id"] = queue_id
    context["investigation_id"] = INVESTIGATION_ID
    context["source_event_id"] = EVENT_ID
    context["requested_version"] = new_version
    context["current_version"] = 5

    context["provenance"]["version"] = new_version

    # Synthetic digest for MOCK provenance only.
    # This does not claim a real database reread.
    context["provenance"]["content_signature"] = sha256_json({
        "scenario": EVENT_ID,
        "version": new_version,
    })

    context["event"]["source_event_id"] = EVENT_ID

    mapping = {
        "LAB-EV-001": EVIDENCE[0],
        "LAB-EV-002": EVIDENCE[1],
    }

    for item in context["event"]["evidence"]:
        item["evidence_id"] = mapping[item["evidence_id"]]

    return envelope


class GenericIntegratedMockTests(unittest.TestCase):

    def setUp(self):
        self.envelopes = {
            31: synthetic_envelope(1, 31, 4),
            32: synthetic_envelope(2, 32, 5),
        }

        token = patch.dict(
            os.environ,
            {"SOC_BRIDGE_HTTP_TOKEN": "X" * 48},
        )
        token.start()
        self.addCleanup(token.stop)

        http = patch(
            "src.context.local_http_client.httpx.get",
            side_effect=self.serve,
        )
        self.http_mock = http.start()
        self.addCleanup(http.stop)

        model = patch("src.ai_engine.engine.ChatOllama")
        self.ollama = model.start()
        self.addCleanup(model.stop)

    def serve(self, url, **kwargs):
        queue_id = int(url.rsplit("/", 1)[-1])

        if queue_id not in self.envelopes:
            raise AssertionError("Unexpected synthetic queue.")

        return httpx.Response(
            200,
            json=copy.deepcopy(self.envelopes[queue_id]),
            request=httpx.Request("GET", url),
        )

    def observed_pair(self, cache=None):
        if cache is None:
            cache = AnalysisCache()

        historical = run_observed_mock_review(31, cache=cache)
        current = run_observed_mock_review(32, cache=cache)

        return historical, current

    def assemble(self, historical, current, **overrides):
        options = {
            "historical_envelope": self.envelopes[31],
            "current_envelope": self.envelopes[32],
        }
        options.update(overrides)

        return assemble_integrated_mock_contract(
            historical,
            current,
            **options,
        )

    def report(self, historical, current):
        return build_integrated_mock_report(
            historical,
            current,
            historical_envelope=self.envelopes[31],
            current_envelope=self.envelopes[32],
        )

    def test_01_generic_pair_produces_valid_contract(self):
        historical, current = self.observed_pair()

        original_h = copy.deepcopy(self.envelopes[31])
        original_c = copy.deepcopy(self.envelopes[32])

        contract = self.assemble(historical, current)

        old, new = validate_contract(
            contract,
            expected_evidence_ids=EVIDENCE,
        )

        self.assertEqual(old["queue_id"], 31)
        self.assertEqual(new["queue_id"], 32)
        self.assertEqual(old["investigation_version"], 4)
        self.assertEqual(new["investigation_version"], 5)

        self.assertEqual(
            new["analysis"]["evidence_ids"],
            list(EVIDENCE),
        )

        self.assertEqual(self.envelopes[31], original_h)
        self.assertEqual(self.envelopes[32], original_c)

        self.ollama.assert_not_called()

    def test_02_integrated_html_uses_second_identity(self):
        historical, current = self.observed_pair()

        report = self.report(historical, current)
        html = report["html"]

        for value in (
            EVENT_ID,
            INVESTIGATION_ID,
            *EVIDENCE,
            "queue 31",
        ):
            self.assertIn(value, html)

        self.assertIs(report["verified_against_database"], False)
        self.assertIs(report["operational_dispatch_allowed"], False)
        self.assertIs(report["notification_sent"], False)
        self.assertIs(report["human_review_required"], True)

        self.ollama.assert_not_called()

    def test_03_generic_pair_requires_current_envelope(self):
        historical, current = self.observed_pair()

        with self.assertRaises(ValueError):
            assemble_integrated_mock_contract(
                historical,
                current,
                historical_envelope=self.envelopes[31],
            )

    def test_04_forged_evidence_rejected_even_when_resigned(self):
        historical, current = self.observed_pair()

        changed = copy.deepcopy(current)

        wf04 = changed["result"]["wf04_result"]

        wf04["analysis"]["evidence_ids"] = [
            EVIDENCE[0],
            "LAB-FORGED-EV",
        ]

        # Recompute the hash to ensure that rejection is
        # caused by trusted context evidence validation,
        # not merely by an outdated SHA-256 signature.
        changed["result"]["integrity_record"] = (
            build_integrity_record(wf04)
        )

        with self.assertRaises(ValueError):
            self.assemble(historical, changed)

        self.ollama.assert_not_called()

    def test_05_current_identity_mismatch_rejected(self):
        historical, current = self.observed_pair()

        changed = copy.deepcopy(self.envelopes[32])

        changed["context"]["investigation_id"] = "OTHER-INV"

        with self.assertRaises(ValueError):
            self.assemble(
                historical,
                current,
                current_envelope=changed,
            )

    def test_06_current_provenance_mismatch_rejected(self):
        historical, current = self.observed_pair()

        changed = copy.deepcopy(self.envelopes[32])

        changed["context"]["provenance"][
            "content_signature"
        ] = "a" * 64

        with self.assertRaises(ValueError):
            self.assemble(
                historical,
                current,
                current_envelope=changed,
            )

    def test_07_non_consecutive_versions_rejected(self):
        historical, current = self.observed_pair()

        changed = copy.deepcopy(self.envelopes[31])

        changed["context"]["requested_version"] = 2
        changed["context"]["provenance"]["version"] = 2

        with self.assertRaises(ValueError):
            self.assemble(
                historical,
                current,
                historical_envelope=changed,
            )

    def test_08_historical_promotion_rejected(self):
        historical, current = self.observed_pair()

        changed = copy.deepcopy(historical)

        changed["result"]["review_status"] = (
            "MOCK_ANALYSIS_COMPLETED"
        )

        with self.assertRaises(ValueError):
            self.assemble(changed, current)

    def test_09_telemetry_mismatch_rejected(self):
        historical, current = self.observed_pair()

        changed = copy.deepcopy(current)

        changed["telemetry"]["integrity_status"] = (
            "NOT_APPLICABLE"
        )

        with self.assertRaises(ValueError):
            self.assemble(historical, changed)

    def test_10_duplicate_trusted_evidence_rejected(self):
        historical, current = self.observed_pair()

        changed = copy.deepcopy(self.envelopes[32])

        evidence = changed["context"]["event"]["evidence"]

        evidence[1]["evidence_id"] = evidence[0]["evidence_id"]

        with self.assertRaises(ValueError):
            self.assemble(
                historical,
                current,
                current_envelope=changed,
            )

    def test_11_operational_dispatch_rejected(self):
        historical, current = self.observed_pair()

        changed = copy.deepcopy(current)

        changed["result"]["operational_dispatch_allowed"] = True

        with self.assertRaises(ValueError):
            self.assemble(historical, changed)

        self.ollama.assert_not_called()

    def test_12_cache_repetition_preserves_signed_result(self):
        cache = AnalysisCache()

        historical, current = self.observed_pair(cache)

        repeated = run_observed_mock_review(
            32,
            cache=cache,
        )

        self.assertIs(current["telemetry"]["cache_hit"], False)
        self.assertIs(repeated["telemetry"]["cache_hit"], True)

        first = self.assemble(historical, current)
        second = self.assemble(historical, repeated)

        self.assertEqual(
            first["results"][1]["analysis"],
            second["results"][1]["analysis"],
        )

        self.assertEqual(
            current["result"]["integrity_record"],
            repeated["result"]["integrity_record"],
        )

        self.ollama.assert_not_called()


if __name__ == "__main__":
    unittest.main()
