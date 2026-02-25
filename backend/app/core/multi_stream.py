"""
多路推流管理器
在单个进程中同时管理多个独立 FFmpeg 推流任务。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .stream import StreamConfig, StreamManager, StreamStatus


@dataclass
class StreamSessionMeta:
    stream_id: str
    account_id: Optional[str] = None
    account_name: Optional[str] = None
    title: str = ""
    source: str = ""  # local_video / youtube / custom
    started_at: Optional[str] = None


class MultiStreamManager:
    """管理多个 StreamManager 实例"""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._streams: dict[str, StreamManager] = {}
        self._meta: dict[str, StreamSessionMeta] = {}

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def account_stream_id(account_id: str) -> str:
        return f"account:{account_id.strip()}"

    @property
    def is_running(self) -> bool:
        """兼容旧接口：是否存在任意运行中的推流"""
        return self.running_count > 0

    @property
    def running_count(self) -> int:
        return sum(1 for manager in self._streams.values() if manager.is_running)

    async def start_stream(
        self,
        config: StreamConfig,
        *,
        stream_id: str = "default",
        account_id: Optional[str] = None,
        account_name: Optional[str] = None,
        title: str = "",
        source: str = "",
    ) -> tuple[bool, str]:
        normalized_id = (stream_id or "").strip()
        if not normalized_id:
            return False, "stream_id 不能为空"

        async with self._lock:
            manager = self._streams.get(normalized_id)
            if manager is None:
                manager = StreamManager()
                self._streams[normalized_id] = manager

            self._meta[normalized_id] = StreamSessionMeta(
                stream_id=normalized_id,
                account_id=account_id,
                account_name=account_name,
                title=title or "",
                source=source or "",
                started_at=None,
            )

        success, error = await manager.start_stream(config)
        if not success:
            return False, error

        meta = self._meta.get(normalized_id)
        if meta:
            meta.started_at = self._now_iso()
        return True, ""

    async def stop_stream(self, stream_id: str = "default") -> tuple[bool, str]:
        normalized_id = (stream_id or "").strip()
        if not normalized_id:
            return False, "stream_id 不能为空"

        async with self._lock:
            manager = self._streams.get(normalized_id)

        if manager is None:
            return False, "未找到对应推流任务"

        success, error = await manager.stop_stream()
        if success:
            async with self._lock:
                self._streams.pop(normalized_id, None)
                self._meta.pop(normalized_id, None)
        return success, error

    async def stop_all(self) -> dict:
        async with self._lock:
            stream_ids = list(self._streams.keys())

        results: list[dict] = []
        for stream_id in stream_ids:
            success, error = await self.stop_stream(stream_id)
            results.append(
                {
                    "stream_id": stream_id,
                    "success": success,
                    "error": None if success else error,
                }
            )

        all_success = all(item["success"] for item in results)
        return {
            "success": all_success,
            "results": results,
        }

    def get_status(self, stream_id: str = "default") -> dict:
        normalized_id = (stream_id or "").strip() or "default"
        manager = self._streams.get(normalized_id)
        base = {
            "stream_id": normalized_id,
            "account_id": None,
            "account_name": None,
            "title": "",
            "source": "",
            "started_at": None,
            "status": StreamStatus.IDLE.value,
            "is_running": False,
            "stream_type": None,
            "error": None,
            "video": None,
            "video_path": None,
            "stream_url": None,
            "rtmp_url": None,
            "youtube_video_id": None,
            "watermark_enabled": False,
            "uptime_seconds": 0,
            "reconnect_attempts": 0,
            "last_exit_code": None,
            "pulse_enabled": False,
            "pulse_phase": "steady",
            "pulse_on_seconds": 0,
            "pulse_off_seconds": 0,
        }
        meta = self._meta.get(normalized_id)
        if meta:
            base.update(
                {
                    "account_id": meta.account_id,
                    "account_name": meta.account_name,
                    "title": meta.title,
                    "source": meta.source,
                    "started_at": meta.started_at,
                }
            )
        if manager:
            base.update(manager.get_status())
        return base

    def list_statuses(self) -> list[dict]:
        items: list[dict] = []
        for stream_id in list(self._streams.keys()):
            items.append(self.get_status(stream_id))

        items.sort(
            key=lambda item: (
                0 if item.get("is_running") else 1,
                item.get("started_at") or "",
                item.get("stream_id") or "",
            )
        )
        return items

    def list_statuses_by_type(self, stream_type: str) -> list[dict]:
        return [item for item in self.list_statuses() if item.get("stream_type") == stream_type]


multi_stream_manager = MultiStreamManager()
