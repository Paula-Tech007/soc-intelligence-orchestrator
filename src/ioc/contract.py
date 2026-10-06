"""IOC canonical contract for MVP1.

Pure local validation layer.
No network, no database, no LLM, no operational action.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlparse
import hashlib
import re


ALLOWED_IOC_TYPES = {
    "ip",
    "domain",
    "url",
    "sha256",
}

ALLOWED_SEVERITIES = {
    "LOW",
    "MEDIUM",
    "HIGH",
    "CRITICAL",
}

DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[A-Za-z]{2,63}$"
)

SHA256_RE = re.compile(r"^[a-fA-F0-9]{64}$")


class IOCValidationError(ValueError):
    """Raised when the IOC contract is invalid."""


@dataclass(frozen=True)
class CanonicalIOC:
    schema_version: str
    environment: str
    ioc_type: str
    value: str
    source: str
    source_event_id: str
    observed_at: str
    severity: str
    confidence: int
    normalized_value: str
    fingerprint: str
    operational_action_allowed: bool
    human_review_required: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _require_non_empty_string(
    payload: dict[str, Any],
    field: str,
) -> str:
    value = payload.get(field)

    if not isinstance(value, str) or not value.strip():
        raise IOCValidationError(
            f"{field} deve ser uma string nao vazia."
        )

    return value.strip()


def _validate_confidence(value: Any) -> int:
    if type(value) is not int:
        raise IOCValidationError(
            "confidence deve ser inteiro."
        )

    if not 0 <= value <= 100:
        raise IOCValidationError(
            "confidence deve estar entre 0 e 100."
        )

    return value


def _normalize_ip(value: str) -> str:
    try:
        return str(ip_address(value))
    except ValueError as exc:
        raise IOCValidationError(
            "IOC do tipo ip invalido."
        ) from exc


def _normalize_domain(value: str) -> str:
    normalized = value.strip().lower().rstrip(".")

    if not DOMAIN_RE.fullmatch(normalized):
        raise IOCValidationError(
            "IOC do tipo domain invalido."
        )

    return normalized


def _normalize_url(value: str) -> str:
    normalized = value.strip()

    parsed = urlparse(normalized)

    if parsed.scheme not in {"http", "https"}:
        raise IOCValidationError(
            "IOC do tipo url deve usar http ou https."
        )

    if not parsed.netloc:
        raise IOCValidationError(
            "IOC do tipo url invalido."
        )

    return normalized


def _normalize_sha256(value: str) -> str:
    normalized = value.strip().lower()

    if not SHA256_RE.fullmatch(normalized):
        raise IOCValidationError(
            "IOC do tipo sha256 invalido."
        )

    return normalized


def normalize_ioc_value(
    ioc_type: str,
    value: str,
) -> str:
    normalizers = {
        "ip": _normalize_ip,
        "domain": _normalize_domain,
        "url": _normalize_url,
        "sha256": _normalize_sha256,
    }

    try:
        normalizer = normalizers[ioc_type]
    except KeyError as exc:
        raise IOCValidationError(
            f"ioc_type nao suportado: {ioc_type}"
        ) from exc

    return normalizer(value)


def _canonical_fingerprint(
    *,
    ioc_type: str,
    normalized_value: str,
) -> str:
    canonical = f"{ioc_type}:{normalized_value}"

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


def _validate_observed_at(value: str) -> str:
    candidate = value.strip()

    try:
        parsed = datetime.fromisoformat(
            candidate.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise IOCValidationError(
            "observed_at deve estar em ISO 8601."
        ) from exc

    if parsed.tzinfo is None:
        raise IOCValidationError(
            "observed_at deve conter timezone."
        )

    return parsed.astimezone(
        timezone.utc
    ).isoformat().replace("+00:00", "Z")


def build_canonical_ioc(
    payload: dict[str, Any],
) -> CanonicalIOC:
    if not isinstance(payload, dict):
        raise IOCValidationError(
            "payload deve ser objeto JSON."
        )

    schema_version = payload.get(
        "schema_version",
        "1.0",
    )

    if schema_version != "1.0":
        raise IOCValidationError(
            "schema_version nao suportada."
        )

    environment = payload.get(
        "environment",
        "LAB",
    )

    if environment != "LAB":
        raise IOCValidationError(
            "environment deve ser LAB no MVP1."
        )

    ioc_type = _require_non_empty_string(
        payload,
        "ioc_type",
    ).lower()

    if ioc_type not in ALLOWED_IOC_TYPES:
        raise IOCValidationError(
            f"ioc_type nao suportado: {ioc_type}"
        )

    raw_value = _require_non_empty_string(
        payload,
        "value",
    )

    source = _require_non_empty_string(
        payload,
        "source",
    )

    source_event_id = _require_non_empty_string(
        payload,
        "source_event_id",
    )

    observed_at_raw = _require_non_empty_string(
        payload,
        "observed_at",
    )

    severity = _require_non_empty_string(
        payload,
        "severity",
    ).upper()

    if severity not in ALLOWED_SEVERITIES:
        raise IOCValidationError(
            f"severity invalida: {severity}"
        )

    confidence = _validate_confidence(
        payload.get("confidence")
    )

    normalized_value = normalize_ioc_value(
        ioc_type,
        raw_value,
    )

    observed_at = _validate_observed_at(
        observed_at_raw
    )

    fingerprint = _canonical_fingerprint(
        ioc_type=ioc_type,
        normalized_value=normalized_value,
    )

    return CanonicalIOC(
        schema_version="1.0",
        environment="LAB",
        ioc_type=ioc_type,
        value=raw_value,
        source=source,
        source_event_id=source_event_id,
        observed_at=observed_at,
        severity=severity,
        confidence=confidence,
        normalized_value=normalized_value,
        fingerprint=fingerprint,
        operational_action_allowed=False,
        human_review_required=True,
    )
