"""Deterministic IOC Risk Engine for MVP1.8.

No network, no database, no LLM and no operational action.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from src.ioc.contract import CanonicalIOC
from src.threat_intel.contract import ThreatIntelResult


SEVERITY_WEIGHTS = {
    "LOW": 10,
    "MEDIUM": 25,
    "HIGH": 40,
    "CRITICAL": 55,
}

REPUTATION_WEIGHTS = {
    "UNKNOWN": 0,
    "BENIGN": -20,
    "SUSPICIOUS": 20,
    "MALICIOUS": 40,
}


class IOCRiskValidationError(ValueError):
    """Raised when risk inputs are invalid."""


@dataclass(frozen=True)
class RiskAssessment:
    schema_version: str
    environment: str
    ioc_fingerprint: str
    risk_score: int
    risk_level: str
    reasons: tuple[str, ...]
    operational_action_allowed: bool
    human_review_required: bool

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["reasons"] = list(self.reasons)
        return data


def _clamp_score(value: int) -> int:
    return max(0, min(100, value))


def _risk_level(score: int) -> str:
    if score >= 80:
        return "CRITICAL"

    if score >= 60:
        return "HIGH"

    if score >= 30:
        return "MEDIUM"

    return "LOW"


def assess_ioc_risk(
    *,
    ioc: CanonicalIOC,
    threat_intel: ThreatIntelResult,
) -> RiskAssessment:

    if not isinstance(ioc, CanonicalIOC):
        raise IOCRiskValidationError(
            "ioc deve ser CanonicalIOC."
        )

    if not isinstance(
        threat_intel,
        ThreatIntelResult,
    ):
        raise IOCRiskValidationError(
            "threat_intel deve ser ThreatIntelResult."
        )

    if (
        ioc.fingerprint
        != threat_intel.ioc_fingerprint
    ):
        raise IOCRiskValidationError(
            "fingerprint divergente entre IOC e Threat Intel."
        )

    score = 0
    reasons: list[str] = []

    severity_weight = SEVERITY_WEIGHTS[
        ioc.severity
    ]

    score += severity_weight
    reasons.append(
        f"event_severity={ioc.severity}"
        f" (+{severity_weight})"
    )

    confidence_weight = round(
        ioc.confidence * 0.15
    )

    score += confidence_weight
    reasons.append(
        f"ioc_confidence={ioc.confidence}"
        f" (+{confidence_weight})"
    )

    reputation_weight = REPUTATION_WEIGHTS[
        threat_intel.reputation
    ]

    score += reputation_weight

    sign = (
        "+"
        if reputation_weight >= 0
        else ""
    )

    reasons.append(
        f"reputation={threat_intel.reputation}"
        f" ({sign}{reputation_weight})"
    )

    threat_weight = round(
        threat_intel.threat_score * 0.25
    )

    score += threat_weight
    reasons.append(
        f"threat_score={threat_intel.threat_score}"
        f" (+{threat_weight})"
    )

    if threat_intel.known:
        score += 5
        reasons.append(
            "known_ioc=True (+5)"
        )
    else:
        reasons.append(
            "known_ioc=False (+0)"
        )

    if (
        threat_intel.reputation
        == "MALICIOUS"
        and threat_intel.confidence >= 80
    ):
        score += 10
        reasons.append(
            "high_confidence_malicious=True (+10)"
        )

    final_score = _clamp_score(
        score
    )

    final_level = _risk_level(
        final_score
    )

    reasons.append(
        f"final_score={final_score}"
    )

    reasons.append(
        f"risk_level={final_level}"
    )

    return RiskAssessment(
        schema_version="1.0",
        environment="LAB",
        ioc_fingerprint=ioc.fingerprint,
        risk_score=final_score,
        risk_level=final_level,
        reasons=tuple(reasons),
        operational_action_allowed=False,
        human_review_required=True,
    )
