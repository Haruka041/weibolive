import os
import json
from pathlib import Path

class Config:
    # Server
    host: str = os.getenv("WEIBOLIVE_HOST", "0.0.0.0")
    port: int = int(os.getenv("WEIBOLIVE_PORT", "8887"))
    
    # Paths
    base_dir: Path = Path(__file__).parent.parent.parent  # backend directory
    project_dir: Path = base_dir.parent  # weibolive directory
    data_dir: Path = base_dir / "data"
    cookies_dir: Path = data_dir / "cookies"
    videos_dir: Path = data_dir / "videos"
    covers_dir: Path = data_dir / "covers"
    stream_accounts_file: Path = data_dir / "stream_accounts.json"
    
    # Playwright
    headless: bool = os.getenv("WEIBOLIVE_HEADLESS", "1") == "1"
    
    # Weibo
    weibo_live_url: str = "https://me.weibo.com/content/live"
    weibo_login_url: str = "https://weibo.com"

    # Admin auth
    admin_users_raw: str = os.getenv("WEIBOLIVE_ADMIN_USERS", "").strip()
    admin_username: str = os.getenv("WEIBOLIVE_ADMIN_USERNAME", "admin")
    admin_password: str = os.getenv("WEIBOLIVE_ADMIN_PASSWORD", "admin123")
    admin_session_ttl_seconds: int = int(os.getenv("WEIBOLIVE_ADMIN_SESSION_TTL_SECONDS", "86400"))
    admin_cookie_secure: bool = os.getenv("WEIBOLIVE_ADMIN_COOKIE_SECURE", "0") == "1"
    
    def __init__(self):
        # Ensure directories exist
        self.cookies_dir.mkdir(parents=True, exist_ok=True)
        self.videos_dir.mkdir(parents=True, exist_ok=True)
        self.covers_dir.mkdir(parents=True, exist_ok=True)

    @property
    def admin_users(self) -> dict[str, str]:
        """
        返回管理员账号字典：{username: password}

        优先读取 WEIBOLIVE_ADMIN_USERS(JSON)，格式示例：
        {"admin":"admin123","ops":"ops123"}
        """
        if self.admin_users_raw:
            try:
                parsed = json.loads(self.admin_users_raw)
                if isinstance(parsed, dict):
                    users = {
                        str(k).strip(): str(v)
                        for k, v in parsed.items()
                        if str(k).strip() and str(v)
                    }
                    if users:
                        return users
            except json.JSONDecodeError:
                pass

        return {self.admin_username: self.admin_password}

CONFIG = Config()
