"""MISP Threat Intelligence adapter for MVP1.3.

This module does not perform network access by itself.
A lookup callable is injected by the caller.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.ioc.contract import CanonicalIOC
from src.threat_intel.contract import (
    ThreatIntelResult,
    build_threat_intel_result,
)
from src.threat_intel.provider import (
    ThreatIntelProvider,
    ThreatIntelProviderResponseError,
    ThreatIntelProviderUnavailable,
)


LookupCallable = Callable[
    [CanonicalIOC],
    dict[str, Any],
]


class MISPProvider(ThreatIntelProvider):
    """Adapter between canonical IOCs and MISP responses."""

    def __init__(
        self,
        lookup: LookupCallable,
    ) -> None:

        if not callable(lookup):
            raise TypeError(
                "lookup deve ser callable."
            )

        self._lookup = lookup

    @property
    def name(self) -> str:
        return "MISP"

    def enrich(
        self,
        ioc: CanonicalIOC,
    ) -> ThreatIntelResult:

        if not isinstance(
            ioc,
            CanonicalIOC,
        ):
            raise TypeError(
                "ioc deve ser CanonicalIOC."
            )

        try:
            response = self._lookup(ioc)
        except Exception as exc:
            raise ThreatIntelProviderUnavailable(
                "falha ao consultar MISP."
            ) from exc

        if not isinstance(response, dict):
            raise ThreatIntelProviderResponseError(
                "resposta MISP deve ser objeto."
            )

        attributes = response.get(
            "attributes",
            [],
        )

        if not isinstance(attributes, list):
            raise ThreatIntelProviderResponseError(
                "attributes MISP deve ser lista."
            )

        if not attributes:
            return build_threat_intel_result(
                provider=self.name,
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

        valid_attributes = []

        for attribute in attributes:
            if not isinstance(attribute, dict):
                raise ThreatIntelProviderResponseError(
                    "atributo MISP invalido."
                )

            value = attribute.get("value")

            if (
                isinstance(value, str)
                and value.strip()
                == ioc.normalized_value
            ):
                valid_attributes.append(
                    attribute
                )

        if not valid_attributes:
            return build_threat_intel_result(
                provider=self.name,
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

        confidence_values = []
        scores = []
        tags = set()
        sources = {"MISP"}
        first_seen_values = []
        last_seen_values = []

        for attribute in valid_attributes:

            confidence = attribute.get(
                "confidence",
                50,
            )

            if (
                type(confidence) is int
                and 0 <= confidence <= 100
            ):
                confidence_values.append(
                    confidence
                )

            threat_score = attribute.get(
                "threat_score",
                70,
            )

            if (
                type(threat_score) is int
                and 0 <= threat_score <= 100
            ):
                scores.append(
                    threat_score
                )

            raw_tags = attribute.get(
                "tags",
                [],
            )

            if isinstance(raw_tags, list):
                tags.update(
                    item.strip()
                    for item in raw_tags
                    if isinstance(item, str)
                    and item.strip()
                )

            source = attribute.get(
                "source",
            )

            if (
                isinstance(source, str)
                and source.strip()
            ):
                sources.add(
                    source.strip()
                )

            first_seen = attribute.get(
                "first_seen",
            )

            if (
                isinstance(first_seen, str)
                and first_seen.strip()
            ):
                first_seen_values.append(
                    first_seen.strip()
                )

            last_seen = attribute.get(
                "last_seen",
            )

            if (
                isinstance(last_seen, str)
                and last_seen.strip()
            ):
                last_seen_values.append(
                    last_seen.strip()
                )

        confidence = max(
            confidence_values,
            default=50,
        )

        threat_score = max(
            scores,
            default=70,
        )

        if threat_score >= 80:
            reputation = "MALICIOUS"
        elif threat_score >= 40:
            reputation = "SUSPICIOUS"
        else:
            reputation = "BENIGN"

        return build_threat_intel_result(
            provider=self.name,
            ioc_type=ioc.ioc_type,
            ioc_value=ioc.normalized_value,
            ioc_fingerprint=ioc.fingerprint,
            known=True,
            reputation=reputation,
            confidence=confidence,
            threat_score=threat_score,
            sources=sorted(sources),
            tags=sorted(tags),
            first_seen=(
                min(first_seen_values)
                if first_seen_values
                else None
            ),
            last_seen=(
                max(last_seen_values)
                if last_seen_values
                else None
            ),
        )
