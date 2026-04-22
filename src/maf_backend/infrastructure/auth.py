from __future__ import annotations

from fastapi import HTTPException, status

from maf_backend.settings import Settings


async def verify_bearer_token(
    authorization: str | None = None,
    settings: Settings | None = None,
) -> None:
    if settings is None:
        raise RuntimeError("settings are required for auth verification")
    if authorization is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if token != settings.api_bearer_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")