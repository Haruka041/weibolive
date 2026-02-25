from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..core import (
    ADMIN_COOKIE_NAME,
    CONFIG,
    admin_auth_manager,
    get_admin_from_token,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdminLoginRequest(BaseModel):
    username: str
    password: str


@router.get("/status")
async def admin_status(
    token: Optional[str] = Cookie(default=None, alias=ADMIN_COOKIE_NAME),
):
    username = get_admin_from_token(token)
    return {
        "logged_in": bool(username),
        "username": username,
    }


@router.post("/login")
async def admin_login(request: AdminLoginRequest):
    token = admin_auth_manager.login(request.username.strip(), request.password)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理员账号或密码错误",
        )

    response = JSONResponse(
        {
            "success": True,
            "username": request.username.strip(),
        }
    )
    response.set_cookie(
        key=ADMIN_COOKIE_NAME,
        value=token,
        max_age=CONFIG.admin_session_ttl_seconds,
        httponly=True,
        secure=CONFIG.admin_cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/logout")
async def admin_logout(
    token: Optional[str] = Cookie(default=None, alias=ADMIN_COOKIE_NAME),
):
    admin_auth_manager.logout(token)
    response = JSONResponse({"success": True})
    response.delete_cookie(key=ADMIN_COOKIE_NAME, path="/")
    return response
