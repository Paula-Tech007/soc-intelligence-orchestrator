"""Threat Intelligence provider interface for MVP1.3."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.ioc.contract import CanonicalIOC
from src.threat_intel.contract import ThreatIntelResult


class ThreatIntelProviderError(RuntimeError):
    """Base error for Threat Intelligence providers."""


class ThreatIntelProviderUnavailable(
    ThreatIntelProviderError
):
    """Raised when a provider cannot be reached or queried."""


class ThreatIntelProviderResponseError(
    ThreatIntelProviderError
):
    """Raised when a provider returns an invalid response."""


class ThreatIntelProvider(ABC):
    """Common interface implemented by every TI provider."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable provider identifier."""
        raise NotImplementedError

    @abstractmethod
    def enrich(
        self,
        ioc: CanonicalIOC,
    ) -> ThreatIntelResult:
        """Enrich one canonical IOC."""
        raise NotImplementedError
