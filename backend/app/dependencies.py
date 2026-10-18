import secrets

from fastapi import Header, HTTPException, Request

from .config import settings


def get_db(request: Request):
    return request.app.state.db


async def require_api_key(x_api_key: str | None = Header(default=None)) -> str:
    if x_api_key:
        candidate = x_api_key.encode()
        for key in settings.api_key_list:
            if secrets.compare_digest(candidate, key.encode()):
                return key
    raise HTTPException(status_code=401, detail="Invalid or missing API key")
