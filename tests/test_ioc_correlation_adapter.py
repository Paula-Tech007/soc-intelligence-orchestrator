import unittest

from src.context.context_builder import (
    _shared_iocs,
    indicators,
)


class IOCCorrelationAdapterTests(
    unittest.TestCase
):

    def test_extracts_canonical_ioc(self):
        event = {
            "entity": {
                "ioc_type": "domain",
                "ioc_value": "evil.example",
                "ioc_fingerprint": "a" * 64,
            },
            "evidence": [],
        }

        result = indicators(event)

        self.assertEqual(
            result["iocs"],
            [
                {
                    "type": "domain",
                    "value": "evil.example",
                    "fingerprint": "a" * 64,
                }
            ],
        )

    def test_legacy_indicators_are_preserved(self):
        event = {
            "entity": {
                "src_ip": "192.0.2.10",
                "hostname": "host-01",
                "related_hostnames": [
                    "host-02",
                ],
            },
            "evidence": [
                {
                    "dst_ip": "198.51.100.10",
                }
            ],
        }

        result = indicators(event)

        self.assertEqual(
            result["ips"],
            [
                "192.0.2.10",
                "198.51.100.10",
            ],
        )

        self.assertEqual(
            result["hostnames"],
            [
                "host-01",
                "host-02",
            ],
        )

        self.assertEqual(
            result["iocs"],
            [],
        )

    def test_shared_ioc_by_fingerprint(self):
        current = [
            {
                "type": "domain",
                "value": "evil.example",
                "fingerprint": "b" * 64,
            }
        ]

        candidate = [
            {
                "type": "domain",
                "value": "evil.example",
                "fingerprint": "b" * 64,
            }
        ]

        result = _shared_iocs(
            current,
            candidate,
        )

        self.assertEqual(
            len(result),
            1,
        )

        self.assertEqual(
            result[0]["value"],
            "evil.example",
        )

    def test_different_iocs_do_not_correlate(self):
        current = [
            {
                "type": "domain",
                "value": "one.example",
                "fingerprint": "c" * 64,
            }
        ]

        candidate = [
            {
                "type": "domain",
                "value": "two.example",
                "fingerprint": "d" * 64,
            }
        ]

        result = _shared_iocs(
            current,
            candidate,
        )

        self.assertEqual(
            result,
            [],
        )


if __name__ == "__main__":
    unittest.main()
