import unittest

import httpx

from src.ioc.contract import build_canonical_ioc
from src.threat_intel.misp_client import (
    MISPClientConfig,
    MISPClientConfigurationError,
    MISPReadOnlyClient,
)
from src.threat_intel.provider import (
    ThreatIntelProviderResponseError,
    ThreatIntelProviderUnavailable,
)


def canonical_ioc():
    return build_canonical_ioc({
        "schema_version": "1.0",
        "environment": "LAB",
        "ioc_type": "domain",
        "value": "evil.example",
        "source": "TEST",
        "source_event_id": "MISP-CLIENT-001",
        "observed_at": "2026-10-06T15:00:00Z",
        "severity": "HIGH",
        "confidence": 90,
    })


def config(enabled=True):
    return MISPClientConfig(
        base_url="https://misp.test.local",
        api_key="test-key-not-real",
        timeout_seconds=5,
        verify_tls=True,
        real_integrations_enabled=enabled,
    )


class MISPClientTests(unittest.TestCase):

    def test_real_integration_disabled_blocks_request(
        self,
    ):
        client = MISPReadOnlyClient(
            config(enabled=False)
        )

        try:
            with self.assertRaises(
                MISPClientConfigurationError
            ):
                client.lookup_ioc(
                    canonical_ioc()
                )
        finally:
            client.close()

    def test_https_is_required(self):
        with self.assertRaises(
            MISPClientConfigurationError
        ):
            MISPClientConfig(
                base_url="http://misp.local",
                api_key="test-key",
                verify_tls=True,
                real_integrations_enabled=True,
            )

    def test_tls_cannot_be_disabled(self):
        with self.assertRaises(
            MISPClientConfigurationError
        ):
            MISPClientConfig(
                base_url="https://misp.local",
                api_key="test-key",
                verify_tls=False,
                real_integrations_enabled=True,
            )

    def test_placeholder_key_is_rejected(self):
        with self.assertRaises(
            MISPClientConfigurationError
        ):
            MISPClientConfig(
                base_url="https://misp.local",
                api_key="CHANGE_ME",
                verify_tls=True,
                real_integrations_enabled=True,
            )

    def test_successful_lookup(self):

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
                            }
                        ]
                    }
                },
            )

        transport = httpx.MockTransport(
            handler
        )

        with MISPReadOnlyClient(
            config(),
            transport=transport,
        ) as client:

            result = client.lookup_ioc(
                canonical_ioc()
            )

        self.assertEqual(
            len(result["attributes"]),
            1,
        )

        self.assertEqual(
            result["attributes"][0]["value"],
            "evil.example",
        )

    def test_empty_response_is_supported(self):

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

        with MISPReadOnlyClient(
            config(),
            transport=transport,
        ) as client:

            result = client.lookup_ioc(
                canonical_ioc()
            )

        self.assertEqual(
            result,
            {"attributes": []},
        )

    def test_non_200_is_provider_unavailable(self):

        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                503,
                json={"error": "unavailable"},
            )
        )

        with MISPReadOnlyClient(
            config(),
            transport=transport,
        ) as client:

            with self.assertRaises(
                ThreatIntelProviderUnavailable
            ):
                client.lookup_ioc(
                    canonical_ioc()
                )

    def test_invalid_json_is_rejected(self):

        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                content=b"not-json",
                headers={
                    "Content-Type":
                        "application/json"
                },
            )
        )

        with MISPReadOnlyClient(
            config(),
            transport=transport,
        ) as client:

            with self.assertRaises(
                ThreatIntelProviderResponseError
            ):
                client.lookup_ioc(
                    canonical_ioc()
                )


if __name__ == "__main__":
    unittest.main()
