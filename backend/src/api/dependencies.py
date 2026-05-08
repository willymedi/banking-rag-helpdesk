from fastapi import Depends, Header, HTTPException, status

from src.api.container import Container, get_container, get_settings


def require_api_key(x_api_key: str | None = Header(None)) -> None:
    settings = get_settings()
    if not settings.api_key:
        return
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid api key")


VALID_ROLES = {"dev", "architect", "security", "sre", "auditor", "compliance"}


def get_user_role(x_user_role: str | None = Header(None)) -> str:
    role = (x_user_role or "auditor").lower()
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"unknown role: {role}")
    return role


def container_dep() -> Container:
    return get_container()


def authed(api_key_check: None = Depends(require_api_key)) -> None:
    return None
