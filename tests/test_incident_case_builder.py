import unittest

from src.incident.case_builder import (
    IncidentCaseValidationError,
    build_incident_case,
)
from src.ioc.contract import build_canonical_ioc
from src.policy.risk_policy import (
    evaluate_risk_policy,
)
from src.risk.ioc_risk import (
    RiskAssessment,
    assess_ioc_risk,
)
from src.threat_intel.contract import (
    build_threat_intel_result,
)


def build_ioc():
    return build_canonical_ioc({
        "schema_version": "1.0",
        "environment": "LAB",
        "ioc_type": "domain",
        "value": "malicious-example.test",
        "source": "TEST",
        "source_event_id": "INCIDENT-TEST-001",
        "observed_at": "2026-10-06T16:00:00Z",
        "severity": "HIGH",
        "confidence": 95,
    })


def build_intel(ioc):
    return build_threat_intel_result(
        provider="TEST",
        ioc_type=ioc.ioc_type,
        ioc_value=ioc.normalized_value,
        ioc_fingerprint=ioc.fingerprint,
        known=True,
        reputation="MALICIOUS",
        confidence=95,
        threat_score=95,
        sources=["TEST"],
        tags=["malicious"],
    )


def build_pipeline():
    ioc = build_ioc()
    intel = build_intel(ioc)

    risk = assess_ioc_risk(
        ioc=ioc,
        threat_intel=intel,
    )

    policy = evaluate_risk_policy(
        risk=risk,
    )

    return ioc, intel, risk, policy


class IncidentCaseBuilderTests(unittest.TestCase):

    def test_builds_incident_case(self):
        ioc, intel, risk, policy = build_pipeline()

        result = build_incident_case(
            ioc=ioc,
            threat_intel=intel,
            risk=risk,
            policy=policy,
        )

        self.assertTrue(
            result.incident_id.startswith(
                "INC-"
            )
        )

        self.assertEqual(
            result.ioc_fingerprint,
            ioc.fingerprint,
        )

    def test_escalated_policy_creates_escalated_status(
        self,
    ):
        ioc, intel, risk, policy = build_pipeline()

        result = build_incident_case(
            ioc=ioc,
            threat_intel=intel,
            risk=risk,
            policy=policy,
        )

        self.assertEqual(
            result.policy_decision,
            "ESCALATE",
        )

        self.assertEqual(
            result.status,
            "ESCALATED",
        )

    def test_incident_id_is_deterministic(self):
        ioc, intel, risk, policy = build_pipeline()

        first = build_incident_case(
            ioc=ioc,
            threat_intel=intel,
            risk=risk,
            policy=policy,
        )

        second = build_incident_case(
            ioc=ioc,
            threat_intel=intel,
            risk=risk,
            policy=policy,
        )

        self.assertEqual(
            first.incident_id,
            second.incident_id,
        )

    def test_summary_is_explainable(self):
        ioc, intel, risk, policy = build_pipeline()

        result = build_incident_case(
            ioc=ioc,
            threat_intel=intel,
            risk=risk,
            policy=policy,
        )

        self.assertIn(
            "MALICIOUS",
            result.summary,
        )

        self.assertIn(
            risk.risk_level,
            result.summary,
        )

    def test_operational_action_remains_blocked(self):
        ioc, intel, risk, policy = build_pipeline()

        result = build_incident_case(
            ioc=ioc,
            threat_intel=intel,
            risk=risk,
            policy=policy,
        )

        self.assertFalse(
            result.operational_action_allowed
        )

        self.assertTrue(
            result.human_review_required
        )

        self.assertFalse(
            result.human_review_completed
        )

    def test_mismatched_fingerprint_is_rejected(self):
        ioc, intel, risk, policy = build_pipeline()

        bad_risk = RiskAssessment(
            schema_version=risk.schema_version,
            environment=risk.environment,
            ioc_fingerprint="b" * 64,
            risk_score=risk.risk_score,
            risk_level=risk.risk_level,
            reasons=risk.reasons,
            operational_action_allowed=False,
            human_review_required=True,
        )

        with self.assertRaises(
            IncidentCaseValidationError
        ):
            build_incident_case(
                ioc=ioc,
                threat_intel=intel,
                risk=bad_risk,
                policy=policy,
            )

    def test_risk_policy_score_mismatch_is_rejected(
        self,
    ):
        ioc, intel, risk, policy = build_pipeline()

        bad_policy = type(policy)(
            schema_version=policy.schema_version,
            environment=policy.environment,
            ioc_fingerprint=policy.ioc_fingerprint,
            risk_score=policy.risk_score - 1,
            risk_level=policy.risk_level,
            decision=policy.decision,
            reasons=policy.reasons,
            operational_action_allowed=False,
            human_review_required=True,
        )

        with self.assertRaises(
            IncidentCaseValidationError
        ):
            build_incident_case(
                ioc=ioc,
                threat_intel=intel,
                risk=risk,
                policy=bad_policy,
            )

    def test_invalid_input_is_rejected(self):
        ioc, intel, risk, policy = build_pipeline()

        with self.assertRaises(
            IncidentCaseValidationError
        ):
            build_incident_case(
                ioc="invalid",
                threat_intel=intel,
                risk=risk,
                policy=policy,
            )


if __name__ == "__main__":
    unittest.main()
