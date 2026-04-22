from __future__ import annotations

import secrets

from fastapi import HTTPException, Request, status

from maf_backend.settings import Settings


class BearerTokenAuthenticator:
    def __init__(self, settings: Settings) -> None:
        self._token = settings.api_bearer_token

    async def authenticate(self, request: Request) -> str:
        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

        token = authorization.removeprefix("Bearer ").strip()
        if not token or not secrets.compare_digest(token, self._token):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")

        return "local-user"
