import unittest

from src.ioc.contract import build_canonical_ioc
from src.risk.ioc_risk import (
    IOCRiskValidationError,
    assess_ioc_risk,
)
from src.threat_intel.contract import (
    build_threat_intel_result,
)


def build_ioc(
    *,
    severity="HIGH",
    confidence=90,
):
    return build_canonical_ioc({
        "schema_version": "1.0",
        "environment": "LAB",
        "ioc_type": "domain",
        "value": "evil.example",
        "source": "TEST",
        "source_event_id": "RISK-001",
        "observed_at": "2026-10-06T16:00:00Z",
        "severity": severity,
        "confidence": confidence,
    })


def build_intel(
    ioc,
    *,
    known=True,
    reputation="MALICIOUS",
    confidence=95,
    threat_score=95,
):
    return build_threat_intel_result(
        provider="TEST",
        ioc_type=ioc.ioc_type,
        ioc_value=ioc.normalized_value,
        ioc_fingerprint=ioc.fingerprint,
        known=known,
        reputation=reputation,
        confidence=confidence,
        threat_score=threat_score,
        sources=["TEST"],
        tags=["test"],
    )


class IOCRiskTests(unittest.TestCase):

    def test_malicious_high_confidence_is_critical(
        self,
    ):
        ioc = build_ioc(
            severity="HIGH",
            confidence=90,
        )

        intel = build_intel(
            ioc,
            reputation="MALICIOUS",
            confidence=95,
            threat_score=95,
        )

        result = assess_ioc_risk(
            ioc=ioc,
            threat_intel=intel,
        )

        self.assertEqual(
            result.risk_level,
            "CRITICAL",
        )

        self.assertGreaterEqual(
            result.risk_score,
            80,
        )

    def test_benign_ioc_reduces_risk(self):
        ioc = build_ioc(
            severity="MEDIUM",
            confidence=50,
        )

        intel = build_intel(
            ioc,
            known=True,
            reputation="BENIGN",
            confidence=95,
            threat_score=5,
        )

        result = assess_ioc_risk(
            ioc=ioc,
            threat_intel=intel,
        )

        self.assertEqual(
            result.risk_level,
            "LOW",
        )

    def test_unknown_ioc_does_not_force_high_risk(
        self,
    ):
        ioc = build_ioc(
            severity="LOW",
            confidence=20,
        )

        intel = build_intel(
            ioc,
            known=False,
            reputation="UNKNOWN",
            confidence=0,
            threat_score=0,
        )

        result = assess_ioc_risk(
            ioc=ioc,
            threat_intel=intel,
        )

        self.assertEqual(
            result.risk_level,
            "LOW",
        )

    def test_risk_is_explainable(self):
        ioc = build_ioc()

        intel = build_intel(
            ioc
        )

        result = assess_ioc_risk(
            ioc=ioc,
            threat_intel=intel,
        )

        self.assertGreater(
            len(result.reasons),
            0,
        )

        self.assertTrue(
            any(
                reason.startswith(
                    "event_severity="
                )
                for reason
                in result.reasons
            )
        )

        self.assertTrue(
            any(
                reason.startswith(
                    "final_score="
                )
                for reason
                in result.reasons
            )
        )

    def test_operational_action_is_blocked(self):
        ioc = build_ioc()

        intel = build_intel(
            ioc
        )

        result = assess_ioc_risk(
            ioc=ioc,
            threat_intel=intel,
        )

        self.assertFalse(
            result.operational_action_allowed
        )

        self.assertTrue(
            result.human_review_required
        )

    def test_score_is_never_above_100(self):
        ioc = build_ioc(
            severity="CRITICAL",
            confidence=100,
        )

        intel = build_intel(
            ioc,
            reputation="MALICIOUS",
            confidence=100,
            threat_score=100,
        )

        result = assess_ioc_risk(
            ioc=ioc,
            threat_intel=intel,
        )

        self.assertEqual(
            result.risk_score,
            100,
        )

    def test_mismatched_fingerprint_is_rejected(
        self,
    ):
        ioc = build_ioc()

        intel = build_threat_intel_result(
            provider="TEST",
            ioc_type=ioc.ioc_type,
            ioc_value=ioc.normalized_value,
            ioc_fingerprint="a" * 64,
            known=True,
            reputation="MALICIOUS",
            confidence=90,
            threat_score=90,
            sources=["TEST"],
            tags=[],
        )

        with self.assertRaises(
            IOCRiskValidationError
        ):
            assess_ioc_risk(
                ioc=ioc,
                threat_intel=intel,
            )


if __name__ == "__main__":
    unittest.main()
