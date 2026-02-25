from datetime import datetime, timezone
from shutil import which
from fastapi import APIRouter

from ..core import CONFIG, stream_manager

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check():
    """服务健康检查"""
    dependencies = {
        "ffmpeg": {
            "ok": which("ffmpeg") is not None,
            "path": which("ffmpeg"),
        },
        "yt_dlp": {
            "ok": which("yt-dlp") is not None,
            "path": which("yt-dlp"),
        },
    }

    directories = {
        "data_dir": CONFIG.data_dir.exists(),
        "cookies_dir": CONFIG.cookies_dir.exists(),
        "videos_dir": CONFIG.videos_dir.exists(),
        "covers_dir": CONFIG.covers_dir.exists(),
        "watermarks_dir": (CONFIG.data_dir / "watermarks").exists(),
    }

    deps_ok = all(item["ok"] for item in dependencies.values())
    dirs_ok = all(directories.values())

    return {
        "status": "ok" if deps_ok and dirs_ok else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dependencies": dependencies,
        "directories": directories,
        "streams": {
            "running_count": stream_manager.running_count,
            "items": stream_manager.list_statuses(),
        },
    }
