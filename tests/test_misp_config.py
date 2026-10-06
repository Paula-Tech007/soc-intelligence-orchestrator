import unittest

from src.threat_intel.misp_client import (
    MISPClientConfigurationError,
)
from src.threat_intel.misp_config import (
    load_misp_config,
)


class MISPConfigTests(unittest.TestCase):

    def test_valid_config_is_loaded(self):
        config = load_misp_config({
            "MISP_URL":
                "https://misp.test.local",
            "MISP_API_KEY":
                "test-key-not-real",
            "MISP_TIMEOUT_SECONDS":
                "7.5",
            "MISP_VERIFY_TLS":
                "true",
            "ENABLE_REAL_INTEGRATIONS":
                "true",
        })

        self.assertEqual(
            config.base_url,
            "https://misp.test.local",
        )

        self.assertEqual(
            config.timeout_seconds,
            7.5,
        )

        self.assertTrue(
            config.verify_tls
        )

        self.assertTrue(
            config.real_integrations_enabled
        )

    def test_real_integrations_default_to_false(self):
        config = load_misp_config({
            "MISP_URL":
                "https://misp.test.local",
            "MISP_API_KEY":
                "test-key-not-real",
        })

        self.assertFalse(
            config.real_integrations_enabled
        )

    def test_tls_defaults_to_true(self):
        config = load_misp_config({
            "MISP_URL":
                "https://misp.test.local",
            "MISP_API_KEY":
                "test-key-not-real",
        })

        self.assertTrue(
            config.verify_tls
        )

    def test_timeout_defaults_to_ten_seconds(self):
        config = load_misp_config({
            "MISP_URL":
                "https://misp.test.local",
            "MISP_API_KEY":
                "test-key-not-real",
        })

        self.assertEqual(
            config.timeout_seconds,
            10.0,
        )

    def test_invalid_boolean_is_rejected(self):
        with self.assertRaises(
            MISPClientConfigurationError
        ):
            load_misp_config({
                "MISP_URL":
                    "https://misp.test.local",
                "MISP_API_KEY":
                    "test-key-not-real",
                "MISP_VERIFY_TLS":
                    "maybe",
            })

    def test_invalid_timeout_is_rejected(self):
        with self.assertRaises(
            MISPClientConfigurationError
        ):
            load_misp_config({
                "MISP_URL":
                    "https://misp.test.local",
                "MISP_API_KEY":
                    "test-key-not-real",
                "MISP_TIMEOUT_SECONDS":
                    "abc",
            })

    def test_http_url_is_rejected(self):
        with self.assertRaises(
            MISPClientConfigurationError
        ):
            load_misp_config({
                "MISP_URL":
                    "http://misp.test.local",
                "MISP_API_KEY":
                    "test-key-not-real",
            })

    def test_missing_api_key_is_rejected(self):
        with self.assertRaises(
            MISPClientConfigurationError
        ):
            load_misp_config({
                "MISP_URL":
                    "https://misp.test.local",
                "MISP_API_KEY":
                    "",
            })

    def test_placeholder_key_is_rejected(self):
        with self.assertRaises(
            MISPClientConfigurationError
        ):
            load_misp_config({
                "MISP_URL":
                    "https://misp.test.local",
                "MISP_API_KEY":
                    "CHANGE_ME",
            })


if __name__ == "__main__":
    unittest.main()
