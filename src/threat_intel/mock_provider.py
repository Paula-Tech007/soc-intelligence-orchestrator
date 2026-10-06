"""Local mock Threat Intelligence provider for MVP1.2."""

from __future__ import annotations

from src.ioc.contract import CanonicalIOC
from src.threat_intel.contract import (
    ThreatIntelResult,
    build_threat_intel_result,
)


MOCK_DATABASE = {
    ("ip", "8.8.8.8"): {
        "known": True,
        "reputation": "BENIGN",
        "confidence": 95,
        "threat_score": 5,
        "sources": ["MOCK-TI"],
        "tags": ["public-dns", "known-service"],
        "first_seen": "2020-01-01T00:00:00Z",
        "last_seen": "2026-10-06T00:00:00Z",
    },
    ("domain", "malicious-example.test"): {
        "known": True,
        "reputation": "MALICIOUS",
        "confidence": 92,
        "threat_score": 95,
        "sources": ["MOCK-TI", "MISP-MOCK"],
        "tags": ["malware", "command-and-control"],
        "first_seen": "2026-09-01T10:00:00Z",
        "last_seen": "2026-10-05T20:00:00Z",
    },
}


def enrich_ioc(
    ioc: CanonicalIOC,
) -> ThreatIntelResult:

    if not isinstance(ioc, CanonicalIOC):
        raise TypeError(
            "ioc deve ser CanonicalIOC."
        )

    key = (
        ioc.ioc_type,
        ioc.normalized_value,
    )

    intel = MOCK_DATABASE.get(key)

    if intel is None:
        return build_threat_intel_result(
            provider="MOCK_PROVIDER",
            ioc_type=ioc.ioc_type,
            ioc_value=ioc.normalized_value,
            ioc_fingerprint=ioc.fingerprint,
            known=False,
            reputation="UNKNOWN",
            confidence=0,
            threat_score=0,
            sources=[],
            tags=[],
        )

    return build_threat_intel_result(
        provider="MOCK_PROVIDER",
        ioc_type=ioc.ioc_type,
        ioc_value=ioc.normalized_value,
        ioc_fingerprint=ioc.fingerprint,
        known=intel["known"],
        reputation=intel["reputation"],
        confidence=intel["confidence"],
        threat_score=intel["threat_score"],
        sources=intel["sources"],
        tags=intel["tags"],
        first_seen=intel["first_seen"],
        last_seen=intel["last_seen"],
    )
