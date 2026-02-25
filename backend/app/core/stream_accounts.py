import asyncio
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import CONFIG


@dataclass
class StreamAccount:
    id: str
    name: str
    rtmp_url: str
    stream_key: str
    enabled: bool
    created_at: str
    updated_at: str

    def to_dict(self) -> dict:
        return asdict(self)


class StreamAccountManager:
    """直播推流账号管理器"""

    def __init__(self, storage_file: Path):
        self.storage_file = storage_file
        self._lock = asyncio.Lock()
        self._accounts: dict[str, StreamAccount] = {}
        self._load_from_disk()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _load_from_disk(self) -> None:
        if not self.storage_file.exists():
            self._accounts = {}
            return

        try:
            data = json.loads(self.storage_file.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                self._accounts = {}
                return

            loaded: dict[str, StreamAccount] = {}
            for item in data:
                if not isinstance(item, dict):
                    continue
                try:
                    account = StreamAccount(
                        id=str(item["id"]),
                        name=str(item["name"]),
                        rtmp_url=str(item["rtmp_url"]),
                        stream_key=str(item["stream_key"]),
                        enabled=bool(item.get("enabled", True)),
                        created_at=str(item.get("created_at", self._now_iso())),
                        updated_at=str(item.get("updated_at", self._now_iso())),
                    )
                    if account.id and account.name:
                        loaded[account.id] = account
                except KeyError:
                    continue

            self._accounts = loaded
        except Exception:
            self._accounts = {}

    def _save_to_disk(self) -> None:
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        data = [account.to_dict() for account in self._accounts.values()]
        data.sort(key=lambda item: item.get("created_at", ""))
        self.storage_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    async def list_accounts(self) -> list[StreamAccount]:
        async with self._lock:
            accounts = list(self._accounts.values())
            accounts.sort(key=lambda item: item.created_at)
            return accounts

    async def get_account(self, account_id: str) -> Optional[StreamAccount]:
        async with self._lock:
            return self._accounts.get(account_id)

    async def create_account(
        self,
        name: str,
        rtmp_url: str,
        stream_key: str,
        enabled: bool = True,
    ) -> StreamAccount:
        async with self._lock:
            normalized_name = name.strip()
            normalized_rtmp = rtmp_url.strip().rstrip("/")
            normalized_key = stream_key.strip()

            if not normalized_name:
                raise ValueError("账号名称不能为空")
            if not normalized_rtmp:
                raise ValueError("RTMP 地址不能为空")
            if not normalized_key:
                raise ValueError("推流码不能为空")

            for existing in self._accounts.values():
                if existing.name.strip().lower() == normalized_name.lower():
                    raise ValueError("账号名称已存在")

            now = self._now_iso()
            account = StreamAccount(
                id=str(uuid.uuid4())[:8],
                name=normalized_name,
                rtmp_url=normalized_rtmp,
                stream_key=normalized_key,
                enabled=enabled,
                created_at=now,
                updated_at=now,
            )
            self._accounts[account.id] = account
            self._save_to_disk()
            return account

    async def update_account(
        self,
        account_id: str,
        *,
        name: Optional[str] = None,
        rtmp_url: Optional[str] = None,
        stream_key: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> Optional[StreamAccount]:
        async with self._lock:
            account = self._accounts.get(account_id)
            if not account:
                return None

            if name is not None:
                normalized_name = name.strip()
                if not normalized_name:
                    raise ValueError("账号名称不能为空")
                for existing in self._accounts.values():
                    if existing.id != account_id and existing.name.strip().lower() == normalized_name.lower():
                        raise ValueError("账号名称已存在")
                account.name = normalized_name

            if rtmp_url is not None:
                normalized_rtmp = rtmp_url.strip().rstrip("/")
                if not normalized_rtmp:
                    raise ValueError("RTMP 地址不能为空")
                account.rtmp_url = normalized_rtmp

            if stream_key is not None:
                normalized_key = stream_key.strip()
                if not normalized_key:
                    raise ValueError("推流码不能为空")
                account.stream_key = normalized_key

            if enabled is not None:
                account.enabled = enabled

            account.updated_at = self._now_iso()
            self._save_to_disk()
            return account

    async def delete_account(self, account_id: str) -> bool:
        async with self._lock:
            if account_id not in self._accounts:
                return False
            self._accounts.pop(account_id, None)
            self._save_to_disk()
            return True


stream_account_manager = StreamAccountManager(CONFIG.stream_accounts_file)
