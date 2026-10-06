"""Deterministic Policy Engine for MVP1.9.

Consumes RiskAssessment and produces a controlled policy decision.
No network, no LLM and no operational action.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from src.risk.ioc_risk import RiskAssessment


class RiskPolicyValidationError(ValueError):
    """Raised when policy inputs are invalid."""


@dataclass(frozen=True)
class PolicyDecision:
    schema_version: str
    environment: str
    ioc_fingerprint: str
    risk_score: int
    risk_level: str
    decision: str
    reasons: tuple[str, ...]
    operational_action_allowed: bool
    human_review_required: bool

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["reasons"] = list(self.reasons)
        return data


def _decision_for_level(risk_level: str) -> str:
    mapping = {
        "LOW": "ALLOW",
        "MEDIUM": "REVIEW",
        "HIGH": "ESCALATE",
        "CRITICAL": "ESCALATE",
    }

    try:
        return mapping[risk_level]
    except KeyError as exc:
        raise RiskPolicyValidationError(
            f"risk_level inválido: {risk_level}"
        ) from exc


def evaluate_risk_policy(
    *,
    risk: RiskAssessment,
) -> PolicyDecision:

    if not isinstance(risk, RiskAssessment):
        raise RiskPolicyValidationError(
            "risk deve ser RiskAssessment."
        )

    decision = _decision_for_level(
        risk.risk_level
    )

    reasons: list[str] = [
        f"risk_score={risk.risk_score}",
        f"risk_level={risk.risk_level}",
        f"policy_decision={decision}",
    ]

    if decision == "ALLOW":
        reasons.append(
            "low_risk_policy=allow"
        )

    elif decision == "REVIEW":
        reasons.append(
            "medium_risk_policy=human_review"
        )

    else:
        reasons.append(
            "high_risk_policy=escalation_required"
        )

    return PolicyDecision(
        schema_version="1.0",
        environment="LAB",
        ioc_fingerprint=risk.ioc_fingerprint,
        risk_score=risk.risk_score,
        risk_level=risk.risk_level,
        decision=decision,
        reasons=tuple(reasons),
        operational_action_allowed=False,
        human_review_required=True,
    )
