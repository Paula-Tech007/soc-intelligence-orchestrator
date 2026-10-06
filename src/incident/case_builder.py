"""Deterministic Incident / Case Builder for MVP1.10.

Consumes IOC, Threat Intelligence, RiskAssessment and PolicyDecision
and produces a controlled IncidentCase.

No network.
No database.
No LLM.
No operational action.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any

from src.ioc.contract import CanonicalIOC
from src.policy.risk_policy import PolicyDecision
from src.risk.ioc_risk import RiskAssessment
from src.threat_intel.contract import ThreatIntelResult


class IncidentCaseValidationError(ValueError):
    """Raised when IncidentCase inputs are inconsistent or invalid."""


@dataclass(frozen=True)
class IncidentCase:
    schema_version: str
    environment: str
    incident_id: str

    ioc_type: str
    ioc_value: str
    ioc_fingerprint: str

    source_event_id: str

    threat_provider: str
    threat_known: bool
    threat_reputation: str
    threat_score: int

    risk_score: int
    risk_level: str

    policy_decision: str
    status: str

    summary: str
    reasons: tuple[str, ...]

    operational_action_allowed: bool
    human_review_required: bool
    human_review_completed: bool

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["reasons"] = list(self.reasons)
        return data


def _build_incident_id(
    *,
    ioc: CanonicalIOC,
) -> str:
    seed = (
        f"{ioc.fingerprint}|"
        f"{ioc.source_event_id}|"
        f"{ioc.observed_at}"
    )

    digest = hashlib.sha256(
        seed.encode("utf-8")
    ).hexdigest()[:24]

    return f"INC-{digest.upper()}"


def _status_for_policy(
    decision: str,
) -> str:
    mapping = {
        "ALLOW": "OBSERVED",
        "REVIEW": "PENDING_REVIEW",
        "ESCALATE": "ESCALATED",
    }

    try:
        return mapping[decision]
    except KeyError as exc:
        raise IncidentCaseValidationError(
            f"policy_decision inválida: {decision}"
        ) from exc


def build_incident_case(
    *,
    ioc: CanonicalIOC,
    threat_intel: ThreatIntelResult,
    risk: RiskAssessment,
    policy: PolicyDecision,
) -> IncidentCase:

    if not isinstance(ioc, CanonicalIOC):
        raise IncidentCaseValidationError(
            "ioc deve ser CanonicalIOC."
        )

    if not isinstance(
        threat_intel,
        ThreatIntelResult,
    ):
        raise IncidentCaseValidationError(
            "threat_intel deve ser ThreatIntelResult."
        )

    if not isinstance(
        risk,
        RiskAssessment,
    ):
        raise IncidentCaseValidationError(
            "risk deve ser RiskAssessment."
        )

    if not isinstance(
        policy,
        PolicyDecision,
    ):
        raise IncidentCaseValidationError(
            "policy deve ser PolicyDecision."
        )

    fingerprints = {
        ioc.fingerprint,
        threat_intel.ioc_fingerprint,
        risk.ioc_fingerprint,
        policy.ioc_fingerprint,
    }

    if len(fingerprints) != 1:
        raise IncidentCaseValidationError(
            "fingerprints divergentes entre os componentes."
        )

    if risk.risk_score != policy.risk_score:
        raise IncidentCaseValidationError(
            "risk_score divergente entre Risk e Policy."
        )

    if risk.risk_level != policy.risk_level:
        raise IncidentCaseValidationError(
            "risk_level divergente entre Risk e Policy."
        )

    if (
        risk.operational_action_allowed
        or policy.operational_action_allowed
    ):
        raise IncidentCaseValidationError(
            "ação operacional não pode estar habilitada."
        )

    if (
        not risk.human_review_required
        or not policy.human_review_required
    ):
        raise IncidentCaseValidationError(
            "revisão humana deve permanecer obrigatória."
        )

    status = _status_for_policy(
        policy.decision
    )

    incident_id = _build_incident_id(
        ioc=ioc
    )

    summary = (
        f"IOC {ioc.ioc_type} "
        f"{ioc.normalized_value} | "
        f"reputation={threat_intel.reputation} | "
        f"risk={risk.risk_level}/{risk.risk_score} | "
        f"decision={policy.decision}"
    )

    reasons = (
        f"threat_provider={threat_intel.provider}",
        f"threat_known={threat_intel.known}",
        f"threat_reputation={threat_intel.reputation}",
        f"threat_score={threat_intel.threat_score}",
        f"risk_score={risk.risk_score}",
        f"risk_level={risk.risk_level}",
        f"policy_decision={policy.decision}",
        f"incident_status={status}",
    )

    return IncidentCase(
        schema_version="1.0",
        environment="LAB",
        incident_id=incident_id,

        ioc_type=ioc.ioc_type,
        ioc_value=ioc.normalized_value,
        ioc_fingerprint=ioc.fingerprint,

        source_event_id=ioc.source_event_id,

        threat_provider=threat_intel.provider,
        threat_known=threat_intel.known,
        threat_reputation=threat_intel.reputation,
        threat_score=threat_intel.threat_score,

        risk_score=risk.risk_score,
        risk_level=risk.risk_level,

        policy_decision=policy.decision,
        status=status,

        summary=summary,
        reasons=reasons,

        operational_action_allowed=False,
        human_review_required=True,
        human_review_completed=False,
    )
