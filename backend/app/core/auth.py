from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import AppSettings, get_settings

security = HTTPBearer(auto_error=False)


def get_current_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    settings: AppSettings = Depends(get_settings),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    if credentials.credentials != settings.bearer_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")
    return credentials.credentials
