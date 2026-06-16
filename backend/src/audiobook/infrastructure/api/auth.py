from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from .deps import get_settings

_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str = Security(_scheme)) -> str:
    settings = get_settings()
    if not api_key or api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key (X-API-Key header)",
        )
    return api_key
