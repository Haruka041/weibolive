import secrets
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import Cookie, HTTPException, status

from .config import CONFIG

ADMIN_COOKIE_NAME = "weibolive_admin_token"


@dataclass
class AdminSession:
    username: str
    expires_at: float


class AdminAuthManager:
    """管理员认证管理器（内存会话）"""

    def __init__(self):
        self._sessions: dict[str, AdminSession] = {}

    def _cleanup_expired_sessions(self) -> None:
        now = time.time()
        expired_tokens = [
            token for token, session in self._sessions.items() if session.expires_at <= now
        ]
        for token in expired_tokens:
            self._sessions.pop(token, None)

    def authenticate(self, username: str, password: str) -> bool:
        if not username or not password:
            return False
        user_password = CONFIG.admin_users.get(username)
        return user_password == password

    def login(self, username: str, password: str) -> Optional[str]:
        if not self.authenticate(username, password):
            return None

        self._cleanup_expired_sessions()
        token = secrets.token_urlsafe(32)
        expires_at = time.time() + CONFIG.admin_session_ttl_seconds
        self._sessions[token] = AdminSession(username=username, expires_at=expires_at)
        return token

    def verify_token(self, token: Optional[str]) -> Optional[str]:
        if not token:
            return None

        self._cleanup_expired_sessions()
        session = self._sessions.get(token)
        if not session:
            return None
        return session.username

    def logout(self, token: Optional[str]) -> None:
        if token:
            self._sessions.pop(token, None)


admin_auth_manager = AdminAuthManager()


def get_admin_from_token(token: Optional[str]) -> Optional[str]:
    return admin_auth_manager.verify_token(token)


async def require_admin(
    token: Optional[str] = Cookie(default=None, alias=ADMIN_COOKIE_NAME),
) -> str:
    username = admin_auth_manager.verify_token(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理员未登录或会话已过期",
        )
    return username
