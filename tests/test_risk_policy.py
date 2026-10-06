import unittest

from src.policy.risk_policy import (
    RiskPolicyValidationError,
    evaluate_risk_policy,
)
from src.risk.ioc_risk import RiskAssessment


def build_risk(
    *,
    score=10,
    level="LOW",
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


class RiskPolicyTests(unittest.TestCase):

    def test_low_risk_is_allowed(self):
        risk = build_risk(
            score=10,
            level="LOW",
        )

        result = evaluate_risk_policy(
            risk=risk
        )

        self.assertEqual(
            result.decision,
            "ALLOW",
        )

    def test_medium_risk_requires_review(self):
        risk = build_risk(
            score=45,
            level="MEDIUM",
        )

        result = evaluate_risk_policy(
            risk=risk
        )

        self.assertEqual(
            result.decision,
            "REVIEW",
        )

    def test_high_risk_is_escalated(self):
        risk = build_risk(
            score=70,
            level="HIGH",
        )

        result = evaluate_risk_policy(
            risk=risk
        )

        self.assertEqual(
            result.decision,
            "ESCALATE",
        )

    def test_critical_risk_is_escalated(self):
        risk = build_risk(
            score=95,
            level="CRITICAL",
        )

        result = evaluate_risk_policy(
            risk=risk
        )

        self.assertEqual(
            result.decision,
            "ESCALATE",
        )

    def test_operational_action_is_always_blocked(self):
        risk = build_risk(
            score=95,
            level="CRITICAL",
        )

        result = evaluate_risk_policy(
            risk=risk
        )

        self.assertFalse(
            result.operational_action_allowed
        )

        self.assertTrue(
            result.human_review_required
        )

    def test_decision_is_explainable(self):
        risk = build_risk(
            score=45,
            level="MEDIUM",
        )

        result = evaluate_risk_policy(
            risk=risk
        )

        self.assertTrue(
            any(
                reason.startswith(
                    "policy_decision="
                )
                for reason
                in result.reasons
            )
        )

    def test_invalid_input_is_rejected(self):
        with self.assertRaises(
            RiskPolicyValidationError
        ):
            evaluate_risk_policy(
                risk="invalid"
            )


if __name__ == "__main__":
    unittest.main()
