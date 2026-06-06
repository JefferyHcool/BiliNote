from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.services.auth import (
    AUTH_COOKIE_NAME,
    check_password,
    create_access_token,
    get_token_max_age_seconds,
    is_auth_enabled,
    is_request_authenticated,
)
from app.utils.response import ResponseWrapper as R

router = APIRouter()


class LoginRequest(BaseModel):
    password: str


@router.get("/auth/status")
def auth_status(request: Request):
    enabled = is_auth_enabled()
    return R.success(data={
        "enabled": enabled,
        "authenticated": True if not enabled else is_request_authenticated(request),
    })


@router.post("/auth/login")
def login(data: LoginRequest):
    if not is_auth_enabled():
        return R.success(data={"token": "", "enabled": False})

    if not check_password(data.password):
        return R.error(msg="访问密码不正确", code=401)

    token = create_access_token()
    max_age = get_token_max_age_seconds()
    res = R.success(data={"token": token, "enabled": True, "expires_in": max_age})
    res.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
    )
    return res


@router.post("/auth/logout")
def logout():
    res = R.success()
    res.delete_cookie(AUTH_COOKIE_NAME)
    return res
