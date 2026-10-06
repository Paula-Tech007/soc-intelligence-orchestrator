"""Threat Intelligence orchestration service for MVP1.3."""

from __future__ import annotations

from src.ioc.contract import CanonicalIOC
from src.threat_intel.contract import ThreatIntelResult
from src.threat_intel.provider import ThreatIntelProvider


class ThreatIntelService:
    """Executes enrichment through a configured provider."""

    def __init__(
        self,
        provider: ThreatIntelProvider,
    ) -> None:
        if not isinstance(
            provider,
            ThreatIntelProvider,
        ):
            raise TypeError(
                "provider deve implementar "
                "ThreatIntelProvider."
            )

        self._provider = provider

    @property
    def provider_name(self) -> str:
        return self._provider.name

    def enrich(
        self,
        ioc: CanonicalIOC,
    ) -> ThreatIntelResult:

        if not isinstance(ioc, CanonicalIOC):
            raise TypeError(
                "ioc deve ser CanonicalIOC."
            )

        result = self._provider.enrich(ioc)

        if not isinstance(
            result,
            ThreatIntelResult,
        ):
            raise TypeError(
                "provider retornou resultado invalido."
            )

        if (
            result.ioc_fingerprint
            != ioc.fingerprint
        ):
            raise ValueError(
                "provider retornou fingerprint divergente."
            )

        if (
            result.ioc_type
            != ioc.ioc_type
        ):
            raise ValueError(
                "provider retornou ioc_type divergente."
            )

        if (
            result.ioc_value
            != ioc.normalized_value
        ):
            raise ValueError(
                "provider retornou ioc_value divergente."
            )

        if (
            result.operational_action_allowed
            is not False
        ):
            raise ValueError(
                "provider tentou liberar acao operacional."
            )

        if (
            result.human_review_required
            is not True
        ):
            raise ValueError(
                "revisao humana nao pode ser removida."
            )

        return result
