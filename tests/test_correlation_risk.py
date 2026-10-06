import unittest

from src.risk.correlation_risk import (
    CorrelationRiskValidationError,
    assess_correlation_risk,
)
from src.risk.ioc_risk import RiskAssessment


def build_risk(
    *,
    score=50,
    level="MEDIUM",
):
    return RiskAssessment(
        schema_version="1.0",
        environment="LAB",
        ioc_fingerprint="a" * 64,
        risk_score=score,
        risk_level=level,
        reasons=("test",),
        operational_action_allowed=False,
        human_review_required=True,
    )


def match():
    return {
        "source_event_id": "INC-OTHER",
        "common_ips": [],
        "common_hostnames": [],
        "common_iocs": [
            {
                "type": "domain",
                "value": "evil.example",
                "fingerprint": "a" * 64,
            }
        ],
        "relation_type":
            "SHARED_INDICATORS",
    }


class CorrelationRiskTests(
    unittest.TestCase
):

    def test_no_correlation_adds_no_bonus(self):
        result = assess_correlation_risk(
            risk=build_risk(),
            correlation_matches=[],
        )

        self.assertEqual(
            result.correlation_bonus,
            0,
        )

        self.assertEqual(
            result.aggregated_risk_score,
            50,
        )

    def test_one_correlation_adds_five(self):
        result = assess_correlation_risk(
            risk=build_risk(),
            correlation_matches=[
                match(),
            ],
        )

        self.assertEqual(
            result.correlation_bonus,
            5,
        )

        self.assertEqual(
            result.aggregated_risk_score,
            55,
        )

    def test_two_correlations_add_ten(self):
        result = assess_correlation_risk(
            risk=build_risk(),
            correlation_matches=[
                match(),
                match(),
            ],
        )

        self.assertEqual(
            result.correlation_bonus,
            10,
        )

    def test_three_or_more_caps_bonus_at_fifteen(
        self,
    ):
        result = assess_correlation_risk(
            risk=build_risk(),
            correlation_matches=[
                match(),
                match(),
                match(),
                match(),
            ],
        )

        self.assertEqual(
            result.correlation_bonus,
            15,
        )

    def test_score_is_capped_at_100(self):
        result = assess_correlation_risk(
            risk=build_risk(
                score=95,
                level="CRITICAL",
            ),
            correlation_matches=[
                match(),
                match(),
            ],
        )

        self.assertEqual(
            result.aggregated_risk_score,
            100,
        )

    def test_risk_level_can_increase(self):
        result = assess_correlation_risk(
            risk=build_risk(
                score=58,
                level="MEDIUM",
            ),
            correlation_matches=[
                match(),
            ],
        )

        self.assertEqual(
            result.aggregated_risk_level,
            "HIGH",
        )

    def test_match_without_common_iocs_is_ignored(
        self,
    ):
        result = assess_correlation_risk(
            risk=build_risk(),
            correlation_matches=[
                {
                    "source_event_id":
                        "INC-IP-ONLY",
                    "common_ips": [
                        "192.0.2.1",
                    ],
                    "common_hostnames": [],
                    "common_iocs": [],
                    "relation_type":
                        "SHARED_INDICATORS",
                }
            ],
        )

        self.assertEqual(
            result.correlated_investigations,
            0,
        )

    def test_operational_action_remains_blocked(
        self,
    ):
        result = assess_correlation_risk(
            risk=build_risk(),
            correlation_matches=[
                match(),
            ],
        )

        self.assertFalse(
            result.operational_action_allowed
        )

        self.assertTrue(
            result.human_review_required
        )

    def test_invalid_matches_are_rejected(self):
        with self.assertRaises(
            CorrelationRiskValidationError
        ):
            assess_correlation_risk(
                risk=build_risk(),
                correlation_matches="invalid",
            )


if __name__ == "__main__":
    unittest.main()
