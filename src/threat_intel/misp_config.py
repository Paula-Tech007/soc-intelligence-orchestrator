"""MISP environment configuration loader for MVP1.6.

Reads configuration from environment variables only.
Never logs or exposes the API key.
"""

from __future__ import annotations

import os

from src.threat_intel.misp_client import (
    MISPClientConfig,
    MISPClientConfigurationError,
)


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def _parse_bool(
    value: str | None,
    *,
    field: str,
    default: bool,
) -> bool:

    if value is None:
        return default

    normalized = value.strip().lower()

    if normalized in TRUE_VALUES:
        return True

    if normalized in FALSE_VALUES:
        return False

    raise MISPClientConfigurationError(
        f"{field} possui valor booleano invalido."
    )


def _parse_timeout(
    value: str | None,
) -> float:

    if value is None or not value.strip():
        return 10.0

    try:
        timeout = float(value)
    except ValueError as exc:
        raise MISPClientConfigurationError(
            "MISP_TIMEOUT_SECONDS invalido."
        ) from exc

    if timeout <= 0:
        raise MISPClientConfigurationError(
            "MISP_TIMEOUT_SECONDS deve ser maior que zero."
        )

    return timeout


def load_misp_config(
    env: dict[str, str] | None = None,
) -> MISPClientConfig:

    source = os.environ if env is None else env

    base_url = source.get(
        "MISP_URL",
        "",
    ).strip()

    api_key = source.get(
        "MISP_API_KEY",
        "",
    ).strip()

    enabled = _parse_bool(
        source.get(
            "ENABLE_REAL_INTEGRATIONS"
        ),
        field="ENABLE_REAL_INTEGRATIONS",
        default=False,
    )

    verify_tls = _parse_bool(
        source.get(
            "MISP_VERIFY_TLS"
        ),
        field="MISP_VERIFY_TLS",
        default=True,
    )

    timeout = _parse_timeout(
        source.get(
            "MISP_TIMEOUT_SECONDS"
        )
    )

    return MISPClientConfig(
        base_url=base_url,
        api_key=api_key,
        timeout_seconds=timeout,
        verify_tls=verify_tls,
        real_integrations_enabled=enabled,
    )
