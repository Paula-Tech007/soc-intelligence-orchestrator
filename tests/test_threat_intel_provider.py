import unittest

from src.ioc.contract import build_canonical_ioc
from src.threat_intel.contract import (
    build_threat_intel_result,
)
from src.threat_intel.provider import (
    ThreatIntelProvider,
)
from src.threat_intel.service import (
    ThreatIntelService,
)


def canonical_ioc():
    return build_canonical_ioc({
        "schema_version": "1.0",
        "environment": "LAB",
        "ioc_type": "ip",
        "value": "8.8.8.8",
        "source": "TEST",
        "source_event_id": "PROVIDER-001",
        "observed_at": "2026-10-06T15:00:00Z",
        "severity": "HIGH",
        "confidence": 90,
    })


class DummyProvider(
    ThreatIntelProvider
):

    @property
    def name(self):
        return "DUMMY"

    def enrich(self, ioc):
        return build_threat_intel_result(
            provider=self.name,
            ioc_type=ioc.ioc_type,
            ioc_value=ioc.normalized_value,
            ioc_fingerprint=ioc.fingerprint,
            known=True,
            reputation="BENIGN",
            confidence=90,
            threat_score=5,
            sources=["DUMMY"],
            tags=["test"],
        )


class ThreatIntelProviderTests(
    unittest.TestCase
):

    def test_service_accepts_provider(self):
        service = ThreatIntelService(
            DummyProvider()
        )

        self.assertEqual(
            service.provider_name,
            "DUMMY",
        )

    def test_service_enriches_ioc(self):
        ioc = canonical_ioc()

        service = ThreatIntelService(
            DummyProvider()
        )

        result = service.enrich(ioc)

        self.assertEqual(
            result.ioc_fingerprint,
            ioc.fingerprint,
        )

        self.assertFalse(
            result.operational_action_allowed
        )

        self.assertTrue(
            result.human_review_required
        )

    def test_service_rejects_invalid_provider(self):
        with self.assertRaises(TypeError):
            ThreatIntelService(
                object()
            )

    def test_service_rejects_invalid_ioc(self):
        service = ThreatIntelService(
            DummyProvider()
        )

        with self.assertRaises(TypeError):
            service.enrich(
                {"ioc": "invalid"}
            )


if __name__ == "__main__":
    unittest.main()
