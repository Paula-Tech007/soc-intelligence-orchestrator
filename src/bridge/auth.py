"""
Autenticacao HTTP da ponte local SOC LAB.

O token deve ser recebido exclusivamente pela variavel
SOC_BRIDGE_HTTP_TOKEN.

A credencial nao e armazenada no codigo-fonte.
"""

import os
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)


bearer = HTTPBearer(auto_error=False)


def require_lab_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> None:

    expected = os.environ.get("SOC_BRIDGE_HTTP_TOKEN", "")

    if len(expected) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Autenticacao da ponte indisponivel.",
        )

    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not secrets.compare_digest(
            credentials.credentials,
            expected,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credencial nao autorizada.",
            headers={"WWW-Authenticate": "Bearer"},
        )