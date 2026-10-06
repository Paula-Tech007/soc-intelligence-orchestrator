import unittest

from src.ioc.contract import build_canonical_ioc
from src.threat_intel.contract import (
    ThreatIntelValidationError,
    build_threat_intel_result,
)
from src.threat_intel.mock_provider import enrich_ioc


def build_ioc(
    ioc_type="ip",
    value="8.8.8.8",
):
    return build_canonical_ioc({
        "schema_version": "1.0",
        "environment": "LAB",
        "ioc_type": ioc_type,
        "value": value,
        "source": "TEST",
        "source_event_id": "TEST-001",
        "observed_at": "2026-10-06T15:00:00Z",
        "severity": "HIGH",
        "confidence": 90,
    })


class ThreatIntelEnrichmentTests(
    unittest.TestCase
):

    def test_known_benign_ioc(self):
        result = enrich_ioc(
            build_ioc()
        )

        self.assertTrue(
            result.known
        )
        self.assertEqual(
            result.reputation,
            "BENIGN",
        )
        self.assertEqual(
            result.threat_score,
            5,
        )
        self.assertEqual(
            result.enrichment_status,
            "ENRICHED",
        )

    def test_known_malicious_domain(self):
        result = enrich_ioc(
            build_ioc(
                "domain",
                "malicious-example.test",
            )
        )

        self.assertTrue(
            result.known
        )
        self.assertEqual(
            result.reputation,
            "MALICIOUS",
        )
        self.assertEqual(
            result.threat_score,
            95,
        )
        self.assertIn(
            "malware",
            result.tags,
        )

    def test_unknown_ioc(self):
        result = enrich_ioc(
            build_ioc(
                "ip",
                "1.1.1.1",
            )
        )

        self.assertFalse(
            result.known
        )
        self.assertEqual(
            result.reputation,
            "UNKNOWN",
        )
        self.assertEqual(
            result.threat_score,
            0,
        )
        self.assertEqual(
            result.enrichment_status,
            "NO_INTELLIGENCE_FOUND",
        )

    def test_operational_action_is_blocked(self):
        result = enrich_ioc(
            build_ioc()
        )

        self.assertFalse(
            result.operational_action_allowed
        )
        self.assertTrue(
            result.human_review_required
        )

    def test_sources_are_normalized(self):
        result = build_threat_intel_result(
            provider="TEST",
            ioc_type="ip",
            ioc_value="8.8.8.8",
            ioc_fingerprint="a" * 64,
            known=True,
            reputation="BENIGN",
            confidence=90,
            threat_score=10,
            sources=[
                "SOURCE-B",
                "SOURCE-A",
                "SOURCE-A",
            ],
            tags=[
                "tag-b",
                "tag-a",
                "tag-a",
            ],
        )

        self.assertEqual(
            result.sources,
            (
                "SOURCE-A",
                "SOURCE-B",
            ),
        )

        self.assertEqual(
            result.tags,
            (
                "tag-a",
                "tag-b",
            ),
        )

    def test_unknown_ioc_cannot_be_malicious(self):
        with self.assertRaises(
            ThreatIntelValidationError
        ):
            build_threat_intel_result(
                provider="TEST",
                ioc_type="ip",
                ioc_value="1.1.1.1",
                ioc_fingerprint="a" * 64,
                known=False,
                reputation="MALICIOUS",
                confidence=10,
                threat_score=0,
                sources=[],
                tags=[],
            )

    def test_unknown_ioc_cannot_have_score(self):
        with self.assertRaises(
            ThreatIntelValidationError
        ):
            build_threat_intel_result(
                provider="TEST",
                ioc_type="ip",
                ioc_value="1.1.1.1",
                ioc_fingerprint="a" * 64,
                known=False,
                reputation="UNKNOWN",
                confidence=0,
                threat_score=50,
                sources=[],
                tags=[],
            )

    def test_invalid_score_is_rejected(self):
        with self.assertRaises(
            ThreatIntelValidationError
        ):
            build_threat_intel_result(
                provider="TEST",
                ioc_type="ip",
                ioc_value="8.8.8.8",
                ioc_fingerprint="a" * 64,
                known=True,
                reputation="BENIGN",
                confidence=101,
                threat_score=10,
                sources=["TEST"],
                tags=[],
            )


if __name__ == "__main__":
    unittest.main()
