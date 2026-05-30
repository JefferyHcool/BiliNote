from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.services.auth import is_auth_enabled, is_request_authenticated


PUBLIC_PATHS = {
    "/api/auth/status",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/sys_health",
    "/api/sys_check",
}


class AuthMiddleware(BaseHTTPMiddleware):
    """Optional single-user auth gate for self-hosted deployments.

    The middleware is intentionally disabled by default. When enabled it protects
    both API routes and backend-served assets such as /static/screenshots so a
    public deployment is not left writable/readable without a password.
    """

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS" or not is_auth_enabled():
            return await call_next(request)

        path = request.url.path
        if path in PUBLIC_PATHS:
            return await call_next(request)

        if is_request_authenticated(request):
            return await call_next(request)

        return JSONResponse(
            status_code=401,
            content={"code": 401, "msg": "未登录或登录已过期", "data": None},
        )

