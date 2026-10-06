"""Threat Intelligence enrichment contract for MVP1.2.

Pure local contract.
No network, no database, no LLM, no operational action.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


ALLOWED_REPUTATIONS = {
    "UNKNOWN",
    "BENIGN",
    "SUSPICIOUS",
    "MALICIOUS",
}


class ThreatIntelValidationError(ValueError):
    """Raised when a Threat Intelligence result is invalid."""


@dataclass(frozen=True)
class ThreatIntelResult:
    schema_version: str
    environment: str
    provider: str
    ioc_type: str
    ioc_value: str
    ioc_fingerprint: str
    known: bool
    reputation: str
    confidence: int
    threat_score: int
    sources: tuple[str, ...]
    tags: tuple[str, ...]
    first_seen: str | None
    last_seen: str | None
    enrichment_status: str
    operational_action_allowed: bool
    human_review_required: bool

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["sources"] = list(self.sources)
        data["tags"] = list(self.tags)
        return data


def _validate_score(
    value: Any,
    field: str,
) -> int:
    if type(value) is not int:
        raise ThreatIntelValidationError(
            f"{field} deve ser inteiro."
        )

    if not 0 <= value <= 100:
        raise ThreatIntelValidationError(
            f"{field} deve estar entre 0 e 100."
        )

    return value


def _normalize_strings(
    value: Any,
    field: str,
) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ThreatIntelValidationError(
            f"{field} deve ser lista."
        )

    normalized = []

    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ThreatIntelValidationError(
                f"{field} contem valor invalido."
            )

        normalized.append(
            item.strip()
        )

    return tuple(sorted(set(normalized)))


def build_threat_intel_result(
    *,
    provider: str,
    ioc_type: str,
    ioc_value: str,
    ioc_fingerprint: str,
    known: bool,
    reputation: str,
    confidence: int,
    threat_score: int,
    sources: list[str] | tuple[str, ...],
    tags: list[str] | tuple[str, ...],
    first_seen: str | None = None,
    last_seen: str | None = None,
) -> ThreatIntelResult:

    if not isinstance(provider, str) or not provider.strip():
        raise ThreatIntelValidationError(
            "provider invalido."
        )

    if not isinstance(ioc_type, str) or not ioc_type.strip():
        raise ThreatIntelValidationError(
            "ioc_type invalido."
        )

    if not isinstance(ioc_value, str) or not ioc_value.strip():
        raise ThreatIntelValidationError(
            "ioc_value invalido."
        )

    if (
        not isinstance(ioc_fingerprint, str)
        or len(ioc_fingerprint) != 64
    ):
        raise ThreatIntelValidationError(
            "ioc_fingerprint invalido."
        )

    if type(known) is not bool:
        raise ThreatIntelValidationError(
            "known deve ser booleano."
        )

    normalized_reputation = reputation.strip().upper()

    if normalized_reputation not in ALLOWED_REPUTATIONS:
        raise ThreatIntelValidationError(
            f"reputation invalida: {normalized_reputation}"
        )

    confidence = _validate_score(
        confidence,
        "confidence",
    )

    threat_score = _validate_score(
        threat_score,
        "threat_score",
    )

    normalized_sources = _normalize_strings(
        sources,
        "sources",
    )

    normalized_tags = _normalize_strings(
        tags,
        "tags",
    )

    if not known:
        if normalized_reputation != "UNKNOWN":
            raise ThreatIntelValidationError(
                "IOC desconhecido deve ter reputation UNKNOWN."
            )

        if threat_score != 0:
            raise ThreatIntelValidationError(
                "IOC desconhecido deve ter threat_score 0."
            )

    enrichment_status = (
        "ENRICHED"
        if known
        else "NO_INTELLIGENCE_FOUND"
    )

    return ThreatIntelResult(
        schema_version="1.0",
        environment="LAB",
        provider=provider.strip(),
        ioc_type=ioc_type.strip().lower(),
        ioc_value=ioc_value.strip(),
        ioc_fingerprint=ioc_fingerprint,
        known=known,
        reputation=normalized_reputation,
        confidence=confidence,
        threat_score=threat_score,
        sources=normalized_sources,
        tags=normalized_tags,
        first_seen=first_seen,
        last_seen=last_seen,
        enrichment_status=enrichment_status,
        operational_action_allowed=False,
        human_review_required=True,
    )
