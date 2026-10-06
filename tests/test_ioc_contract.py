import unittest

from src.ioc.contract import (
    IOCValidationError,
    build_canonical_ioc,
)


def valid_payload():
    return {
        "schema_version": "1.0",
        "environment": "LAB",
        "ioc_type": "ip",
        "value": "8.8.8.8",
        "source": "MISP",
        "source_event_id": "MISP-IOC-001",
        "observed_at": "2026-10-06T15:00:00Z",
        "severity": "HIGH",
        "confidence": 90,
    }


class IOCContractTests(unittest.TestCase):

    def test_valid_ip_builds_canonical_contract(self):
        result = build_canonical_ioc(
            valid_payload()
        )

        self.assertEqual(
            result.ioc_type,
            "ip",
        )
        self.assertEqual(
            result.normalized_value,
            "8.8.8.8",
        )
        self.assertEqual(
            result.severity,
            "HIGH",
        )
        self.assertEqual(
            result.confidence,
            90,
        )
        self.assertFalse(
            result.operational_action_allowed
        )
        self.assertTrue(
            result.human_review_required
        )
        self.assertEqual(
            len(result.fingerprint),
            64,
        )

    def test_domain_is_normalized(self):
        payload = valid_payload()
        payload["ioc_type"] = "domain"
        payload["value"] = "Example.COM."

        result = build_canonical_ioc(
            payload
        )

        self.assertEqual(
            result.normalized_value,
            "example.com",
        )

    def test_sha256_is_normalized_to_lowercase(self):
        payload = valid_payload()
        payload["ioc_type"] = "sha256"
        payload["value"] = "A" * 64

        result = build_canonical_ioc(
            payload
        )

        self.assertEqual(
            result.normalized_value,
            "a" * 64,
        )

    def test_same_ioc_produces_same_fingerprint(self):
        first = build_canonical_ioc(
            valid_payload()
        )
        second = build_canonical_ioc(
            valid_payload()
        )

        self.assertEqual(
            first.fingerprint,
            second.fingerprint,
        )

    def test_invalid_ip_is_rejected(self):
        payload = valid_payload()
        payload["value"] = "999.999.999.999"

        with self.assertRaises(
            IOCValidationError
        ):
            build_canonical_ioc(
                payload
            )

    def test_invalid_ioc_type_is_rejected(self):
        payload = valid_payload()
        payload["ioc_type"] = "email"

        with self.assertRaises(
            IOCValidationError
        ):
            build_canonical_ioc(
                payload
            )

    def test_invalid_confidence_is_rejected(self):
        payload = valid_payload()
        payload["confidence"] = 101

        with self.assertRaises(
            IOCValidationError
        ):
            build_canonical_ioc(
                payload
            )

    def test_environment_outside_lab_is_rejected(self):
        payload = valid_payload()
        payload["environment"] = "PROD"

        with self.assertRaises(
            IOCValidationError
        ):
            build_canonical_ioc(
                payload
            )

    def test_timestamp_without_timezone_is_rejected(self):
        payload = valid_payload()
        payload["observed_at"] = (
            "2026-10-06T15:00:00"
        )

        with self.assertRaises(
            IOCValidationError
        ):
            build_canonical_ioc(
                payload
            )


if __name__ == "__main__":
    unittest.main()
