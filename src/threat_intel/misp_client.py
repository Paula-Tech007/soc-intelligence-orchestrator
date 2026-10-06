"""Read-only MISP HTTP client for MVP1.4.

Security properties:
- No write operations.
- TLS verification enabled by default.
- API key supplied externally.
- Explicit timeout.
- Real integrations can be disabled globally.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from src.ioc.contract import CanonicalIOC
from src.threat_intel.provider import (
    ThreatIntelProviderResponseError,
    ThreatIntelProviderUnavailable,
)


class MISPClientConfigurationError(ValueError):
    """Raised when MISP client configuration is unsafe or invalid."""


@dataclass(frozen=True)
class MISPClientConfig:
    base_url: str
    api_key: str
    timeout_seconds: float = 10.0
    verify_tls: bool = True
    real_integrations_enabled: bool = False

    def __post_init__(self) -> None:
        if (
            not isinstance(self.base_url, str)
            or not self.base_url.strip()
        ):
            raise MISPClientConfigurationError(
                "MISP base_url invalida."
            )

        if not self.base_url.lower().startswith(
            "https://"
        ):
            raise MISPClientConfigurationError(
                "MISP deve utilizar HTTPS."
            )

        if (
            not isinstance(self.api_key, str)
            or not self.api_key.strip()
        ):
            raise MISPClientConfigurationError(
                "MISP api_key ausente."
            )

        if self.api_key == "CHANGE_ME":
            raise MISPClientConfigurationError(
                "MISP api_key de exemplo nao pode ser utilizada."
            )

        if (
            not isinstance(self.timeout_seconds, (int, float))
            or isinstance(self.timeout_seconds, bool)
            or self.timeout_seconds <= 0
        ):
            raise MISPClientConfigurationError(
                "timeout_seconds invalido."
            )

        if type(self.verify_tls) is not bool:
            raise MISPClientConfigurationError(
                "verify_tls deve ser booleano."
            )

        if self.verify_tls is not True:
            raise MISPClientConfigurationError(
                "TLS nao pode ser desabilitado no MVP1.4."
            )

        if type(self.real_integrations_enabled) is not bool:
            raise MISPClientConfigurationError(
                "real_integrations_enabled deve ser booleano."
            )


class MISPReadOnlyClient:
    """Minimal read-only MISP REST client."""

    def __init__(
        self,
        config: MISPClientConfig,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:

        if not isinstance(
            config,
            MISPClientConfig,
        ):
            raise TypeError(
                "config deve ser MISPClientConfig."
            )

        self._config = config

        self._client = httpx.Client(
            base_url=config.base_url.rstrip("/"),
            timeout=config.timeout_seconds,
            verify=config.verify_tls,
            transport=transport,
            headers={
                "Authorization": config.api_key,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "MISPReadOnlyClient":
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> None:
        self.close()

    def lookup_ioc(
        self,
        ioc: CanonicalIOC,
    ) -> dict[str, Any]:

        if not isinstance(
            ioc,
            CanonicalIOC,
        ):
            raise TypeError(
                "ioc deve ser CanonicalIOC."
            )

        if (
            self._config.real_integrations_enabled
            is not True
        ):
            raise MISPClientConfigurationError(
                "Integracao real com MISP esta desabilitada."
            )

        payload = {
            "returnFormat": "json",
            "value": ioc.normalized_value,
            "limit": 100,
        }

        try:
            response = self._client.post(
                "/attributes/restSearch",
                json=payload,
            )
        except httpx.HTTPError as exc:
            raise ThreatIntelProviderUnavailable(
                "falha HTTP ao consultar MISP."
            ) from exc

        if response.status_code != 200:
            raise ThreatIntelProviderUnavailable(
                "MISP retornou HTTP "
                f"{response.status_code}."
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise ThreatIntelProviderResponseError(
                "MISP retornou JSON invalido."
            ) from exc

        attributes = self._extract_attributes(
            data
        )

        return {
            "attributes": attributes,
        }

    @staticmethod
    def _extract_attributes(
        data: Any,
    ) -> list[dict[str, Any]]:

        if not isinstance(data, dict):
            raise ThreatIntelProviderResponseError(
                "resposta raiz MISP invalida."
            )

        candidates = None

        if isinstance(
            data.get("response"),
            dict,
        ):
            candidates = data["response"].get(
                "Attribute"
            )

        if candidates is None:
            candidates = data.get(
                "Attribute"
            )

        if candidates is None:
            candidates = data.get(
                "attributes"
            )

        if candidates is None:
            return []

        if not isinstance(
            candidates,
            list,
        ):
            raise ThreatIntelProviderResponseError(
                "lista de atributos MISP invalida."
            )

        normalized = []

        for item in candidates:
            if not isinstance(item, dict):
                raise ThreatIntelProviderResponseError(
                    "atributo MISP invalido."
                )

            normalized.append(item)

        return normalized
