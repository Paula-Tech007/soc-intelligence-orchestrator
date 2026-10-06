import unittest

import httpx

from src.ioc.contract import build_canonical_ioc
from src.threat_intel.misp_client import (
    MISPClientConfig,
    MISPReadOnlyClient,
)
from src.threat_intel.misp_provider import (
    MISPProvider,
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
        "source_event_id": "MISP-E2E-001",
        "observed_at": "2026-10-06T15:00:00Z",
        "severity": "HIGH",
        "confidence": 90,
    })


class MISPEndToEndTests(unittest.TestCase):

    def test_full_pipeline_malicious_ioc(self):

        def handler(request):
            self.assertEqual(
                request.method,
                "POST",
            )

            self.assertEqual(
                request.url.path,
                "/attributes/restSearch",
            )

            return httpx.Response(
                200,
                json={
                    "response": {
                        "Attribute": [
                            {
                                "value":
                                    "evil.example",
                                "type":
                                    "domain",
                                "confidence":
                                    96,
                                "threat_score":
                                    98,
                                "source":
                                    "MISP-LAB",
                                "tags": [
                                    "malware",
                                    "c2",
                                ],
                                "first_seen":
                                    "2026-09-01T00:00:00Z",
                                "last_seen":
                                    "2026-10-06T12:00:00Z",
                            }
                        ]
                    }
                },
            )

        transport = httpx.MockTransport(
            handler
        )

        config = MISPClientConfig(
            base_url="https://misp.test.local",
            api_key="test-key-not-real",
            timeout_seconds=5,
            verify_tls=True,
            real_integrations_enabled=True,
        )

        with MISPReadOnlyClient(
            config,
            transport=transport,
        ) as client:

            provider = MISPProvider(
                client.lookup_ioc
            )

            service = ThreatIntelService(
                provider
            )

            result = service.enrich(
                canonical_ioc()
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
            98,
        )

        self.assertEqual(
            result.confidence,
            96,
        )

        self.assertIn(
            "MISP",
            result.sources,
        )

        self.assertIn(
            "MISP-LAB",
            result.sources,
        )

        self.assertIn(
            "malware",
            result.tags,
        )

        self.assertFalse(
            result.operational_action_allowed
        )

        self.assertTrue(
            result.human_review_required
        )

    def test_full_pipeline_unknown_ioc(self):

        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "response": {
                        "Attribute": []
                    }
                },
            )
        )

        config = MISPClientConfig(
            base_url="https://misp.test.local",
            api_key="test-key-not-real",
            timeout_seconds=5,
            verify_tls=True,
            real_integrations_enabled=True,
        )

        with MISPReadOnlyClient(
            config,
            transport=transport,
        ) as client:

            service = ThreatIntelService(
                MISPProvider(
                    client.lookup_ioc
                )
            )

            result = service.enrich(
                canonical_ioc()
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

    def test_provider_http_failure_propagates(
        self,
    ):

        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                503,
                json={
                    "error":
                        "MISP unavailable"
                },
            )
        )

        config = MISPClientConfig(
            base_url="https://misp.test.local",
            api_key="test-key-not-real",
            timeout_seconds=5,
            verify_tls=True,
            real_integrations_enabled=True,
        )

        with MISPReadOnlyClient(
            config,
            transport=transport,
        ) as client:

            service = ThreatIntelService(
                MISPProvider(
                    client.lookup_ioc
                )
            )

            with self.assertRaises(
                Exception
            ):
                service.enrich(
                    canonical_ioc()
                )


if __name__ == "__main__":
    unittest.main()
