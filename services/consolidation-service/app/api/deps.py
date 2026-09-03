import secrets

from fastapi import Header, HTTPException, status

from app.config import settings


def require_api_key(x_api_key: str = Header(default="")) -> None:
    # Compared as bytes, not str: Starlette decodes headers as latin-1, so a non-ASCII byte in
    # the header would make compare_digest raise TypeError (surfacing as a 500 with a stack
    # trace) instead of simply failing the comparison.
    if not secrets.compare_digest(x_api_key.encode("utf-8"), settings.api_key.encode("utf-8")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")
