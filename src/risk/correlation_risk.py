"""Correlation-aware risk aggregation for MVP1.18.

Adds a bounded contextual score based on IOC correlation matches.

No network.
No database.
No LLM.
No operational action.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from src.risk.ioc_risk import RiskAssessment


class CorrelationRiskValidationError(ValueError):
    """Raised when correlation risk inputs are invalid."""


@dataclass(frozen=True)
class CorrelationRiskAssessment:
    schema_version: str
    environment: str
    ioc_fingerprint: str

    base_risk_score: int
    correlation_bonus: int
    aggregated_risk_score: int

    base_risk_level: str
    aggregated_risk_level: str

    correlated_investigations: int

    reasons: tuple[str, ...]

    operational_action_allowed: bool
    human_review_required: bool

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["reasons"] = list(self.reasons)
        return data


def _risk_level(score: int) -> str:
    if score >= 80:
        return "CRITICAL"

    if score >= 60:
        return "HIGH"

    if score >= 30:
        return "MEDIUM"

    return "LOW"


def _correlation_bonus(
    correlated_investigations: int,
) -> int:

    if correlated_investigations <= 0:
        return 0

    if correlated_investigations == 1:
        return 5

    if correlated_investigations == 2:
        return 10

    return 15


def assess_correlation_risk(
    *,
    risk: RiskAssessment,
    correlation_matches: list[dict[str, Any]],
) -> CorrelationRiskAssessment:

    if not isinstance(risk, RiskAssessment):
        raise CorrelationRiskValidationError(
            "risk deve ser RiskAssessment."
        )

    if not isinstance(correlation_matches, list):
        raise CorrelationRiskValidationError(
            "correlation_matches deve ser lista."
        )

    if risk.operational_action_allowed:
        raise CorrelationRiskValidationError(
            "acao operacional deve permanecer bloqueada."
        )

    if not risk.human_review_required:
        raise CorrelationRiskValidationError(
            "revisao humana deve permanecer obrigatoria."
        )

    correlated = 0

    for match in correlation_matches:

        if not isinstance(match, dict):
            raise CorrelationRiskValidationError(
                "correlacao invalida."
            )

        common_iocs = match.get(
            "common_iocs",
            [],
        )

        if not isinstance(common_iocs, list):
            raise CorrelationRiskValidationError(
                "common_iocs deve ser lista."
            )

        if common_iocs:
            correlated += 1

    bonus = _correlation_bonus(
        correlated
    )

    aggregated_score = min(
        100,
        risk.risk_score + bonus,
    )

    aggregated_level = _risk_level(
        aggregated_score
    )

    reasons = (
        f"base_risk_score={risk.risk_score}",
        f"base_risk_level={risk.risk_level}",
        (
            "correlated_investigations="
            f"{correlated}"
        ),
        f"correlation_bonus=+{bonus}",
        (
            "aggregated_risk_score="
            f"{aggregated_score}"
        ),
        (
            "aggregated_risk_level="
            f"{aggregated_level}"
        ),
    )

    return CorrelationRiskAssessment(
        schema_version="1.0",
        environment="LAB",
        ioc_fingerprint=
            risk.ioc_fingerprint,

        base_risk_score=
            risk.risk_score,
        correlation_bonus=bonus,
        aggregated_risk_score=
            aggregated_score,

        base_risk_level=
            risk.risk_level,
        aggregated_risk_level=
            aggregated_level,

        correlated_investigations=
            correlated,

        reasons=reasons,

        operational_action_allowed=False,
        human_review_required=True,
    )
