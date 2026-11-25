from collections.abc import Callable

import jwt
from fastapi import Depends, Request

from shared.errors import ApiError
from shared.security import decode_token


def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise ApiError("unauthorized", "Autenticação necessária.", 401)
    try:
        return decode_token(auth.removeprefix("Bearer ").strip())
    except jwt.PyJWTError:
        raise ApiError("unauthorized", "Autenticação necessária.", 401) from None


def require_role(*roles: str) -> Callable:
    def dependency(claims: dict = Depends(get_current_user)) -> dict:
        if claims.get("role") not in roles:
            raise ApiError("forbidden", "Acesso negado para o seu perfil.", 403)
        return claims

    return dependency
