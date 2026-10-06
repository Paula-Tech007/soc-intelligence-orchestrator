import unittest

from src.ioc.contract import build_canonical_ioc
from src.threat_intel.misp_provider import (
    MISPProvider,
)
from src.threat_intel.provider import (
    ThreatIntelProviderResponseError,
    ThreatIntelProviderUnavailable,
)
from src.threat_intel.service import (
    ThreatIntelService,
)


def canonical_ioc():
    return build_canonical_ioc({
        "schema_version": "1.0",
        "environment": "LAB",
        "ioc_type": "domain",
        "value": "evil.example",
        "source": "TEST",
        "source_event_id": "MISP-001",
        "observed_at": "2026-10-06T15:00:00Z",
        "severity": "HIGH",
        "confidence": 90,
    })


class MISPProviderContractTests(
    unittest.TestCase
):

    def test_malicious_hit(self):

        def lookup(ioc):
            return {
                "attributes": [
                    {
                        "value":
                            ioc.normalized_value,
                        "confidence": 94,
                        "threat_score": 96,
                        "source": "MISP-LAB",
                        "tags": [
                            "malware",
                            "c2",
                        ],
                        "first_seen":
                            "2026-09-01T00:00:00Z",
                        "last_seen":
                            "2026-10-05T00:00:00Z",
                    }
                ]
            }

        service = ThreatIntelService(
            MISPProvider(lookup)
        )

        result = service.enrich(
            canonical_ioc()
        )

        self.assertTrue(result.known)
        self.assertEqual(
            result.reputation,
            "MALICIOUS",
        )
        self.assertEqual(
            result.threat_score,
            96,
        )
        self.assertEqual(
            result.confidence,
            94,
        )
        self.assertIn(
            "MISP",
            result.sources,
        )

    def test_unknown_ioc(self):

        provider = MISPProvider(
            lambda ioc: {
                "attributes": []
            }
        )

        result = provider.enrich(
            canonical_ioc()
        )

        self.assertFalse(result.known)
        self.assertEqual(
            result.reputation,
            "UNKNOWN",
        )
        self.assertEqual(
            result.threat_score,
            0,
        )

    def test_unrelated_attribute_is_ignored(self):

        provider = MISPProvider(
            lambda ioc: {
                "attributes": [
                    {
                        "value":
                            "another.example",
                        "threat_score": 99,
                    }
                ]
            }
        )

        result = provider.enrich(
            canonical_ioc()
        )

        self.assertFalse(result.known)

    def test_invalid_response_is_rejected(self):

        provider = MISPProvider(
            lambda ioc: {
                "attributes": "invalid"
            }
        )

        with self.assertRaises(
            ThreatIntelProviderResponseError
        ):
            provider.enrich(
                canonical_ioc()
            )

    def test_provider_failure_is_distinct(
        self,
    ):

        def lookup(ioc):
            raise TimeoutError(
                "MISP unavailable"
            )

        provider = MISPProvider(
            lookup
        )

        with self.assertRaises(
            ThreatIntelProviderUnavailable
        ):
            provider.enrich(
                canonical_ioc()
            )

    def test_operational_action_remains_blocked(
        self,
    ):

        provider = MISPProvider(
            lambda ioc: {
                "attributes": []
            }
        )

        result = provider.enrich(
            canonical_ioc()
        )

        self.assertFalse(
            result.operational_action_allowed
        )
        self.assertTrue(
            result.human_review_required
        )


if __name__ == "__main__":
    unittest.main()
