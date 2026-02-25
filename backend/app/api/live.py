import asyncio
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ..core import (
    ADMIN_COOKIE_NAME,
    CONFIG,
    get_admin_from_token,
    stream_account_manager,
    stream_manager,
    weibo_client,
)
from ..core.stream import StreamConfig, StreamType

router = APIRouter(prefix="/api/live", tags=["live"])


class LiveRoomInfo(BaseModel):
    room_id: Optional[str] = None
    title: str
    rtmp_url: Optional[str] = None
    stream_key: Optional[str] = None
    cover_url: Optional[str] = None
    status: str = "not_created"


class StartStreamRequest(BaseModel):
    video_id: Optional[str] = None
    black_screen: bool = False
    title: str = ""
    account_id: Optional[str] = None
    stream_id: Optional[str] = None
    rtmp_url: Optional[str] = None
    stream_key: Optional[str] = None
    loop: bool = True
    bandwidth_mode: str = "normal"
    keepalive_pulse: bool = False
    pulse_on_seconds: int = 120
    pulse_off_seconds: int = 60


class StopStreamRequest(BaseModel):
    stream_id: Optional[str] = None
    account_id: Optional[str] = None


class StreamStatusItem(BaseModel):
    stream_id: str
    account_id: Optional[str] = None
    account_name: Optional[str] = None
    title: str = ""
    source: str = ""
    started_at: Optional[str] = None
    status: str
    is_running: bool
    error: Optional[str] = None
    video: Optional[str] = None
    video_path: Optional[str] = None
    stream_url: Optional[str] = None
    rtmp_url: Optional[str] = None
    stream_type: Optional[str] = None
    youtube_video_id: Optional[str] = None
    watermark_enabled: bool = False
    uptime_seconds: int = 0
    reconnect_attempts: int = 0
    last_exit_code: Optional[int] = None
    pulse_enabled: bool = False
    pulse_phase: str = "steady"
    pulse_on_seconds: int = 0
    pulse_off_seconds: int = 0


class StreamStatusListResponse(BaseModel):
    running_count: int
    items: list[StreamStatusItem]


def _resolve_stream_id(stream_id: Optional[str], account_id: Optional[str]) -> Optional[str]:
    if account_id and account_id.strip():
        return stream_manager.account_stream_id(account_id)
    if stream_id and stream_id.strip():
        return stream_id.strip()
    return None


@router.get("/streams", response_model=StreamStatusListResponse)
async def list_streams():
    items = stream_manager.list_statuses()
    return StreamStatusListResponse(
        running_count=stream_manager.running_count,
        items=[StreamStatusItem(**item) for item in items],
    )


@router.get("/status", response_model=StreamStatusItem)
async def get_stream_status(
    stream_id: Optional[str] = None,
    account_id: Optional[str] = None,
):
    """兼容旧接口：默认返回第一路状态；带参数时返回指定流状态"""
    target_stream_id = _resolve_stream_id(stream_id, account_id)
    if target_stream_id:
        return StreamStatusItem(**stream_manager.get_status(target_stream_id))

    items = stream_manager.list_statuses()
    if items:
        return StreamStatusItem(**items[0])
    return StreamStatusItem(**stream_manager.get_status("default"))


@router.post("/start")
async def start_stream(request: StartStreamRequest):
    """开始本地视频推流（支持多路）"""
    video_path: Optional[Path] = None
    stream_type = StreamType.BLACK_SCREEN if request.black_screen else StreamType.LOCAL_VIDEO
    source = "black_screen" if request.black_screen else "local_video"
    default_title = "黑屏保活"

    if stream_type == StreamType.LOCAL_VIDEO:
        if not request.video_id or not request.video_id.strip():
            raise HTTPException(status_code=400, detail="请选择视频或启用黑屏模式")

        # 查找视频文件
        for file in CONFIG.videos_dir.iterdir():
            if file.is_file() and file.stem == request.video_id:
                video_path = file
                break

        if not video_path:
            raise HTTPException(status_code=404, detail="Video not found")
        default_title = video_path.name

    rtmp_url = request.rtmp_url
    stream_key = request.stream_key
    account_id: Optional[str] = None
    account_name: Optional[str] = None

    if request.account_id:
        account = await stream_account_manager.get_account(request.account_id)
        if not account:
            raise HTTPException(status_code=404, detail="直播账号不存在")
        if not account.enabled:
            raise HTTPException(status_code=400, detail="直播账号已禁用")
        account_id = account.id
        account_name = account.name
        rtmp_url = account.rtmp_url
        stream_key = account.stream_key

    if not rtmp_url or not stream_key:
        raise HTTPException(status_code=400, detail="请提供推流账号或 RTMP 地址与推流码")

    target_stream_id = _resolve_stream_id(request.stream_id, account_id)
    if not target_stream_id:
        target_stream_id = f"manual:{uuid.uuid4().hex[:8]}"

    bandwidth_mode = request.bandwidth_mode
    if request.keepalive_pulse and bandwidth_mode == "normal":
        bandwidth_mode = "keepalive"

    config = StreamConfig(
        video_path=video_path,
        stream_type=stream_type,
        rtmp_url=rtmp_url,
        stream_key=stream_key,
        loop=request.loop,
        bandwidth_mode=bandwidth_mode,
        pulse_enabled=request.keepalive_pulse,
        pulse_on_seconds=request.pulse_on_seconds,
        pulse_off_seconds=request.pulse_off_seconds,
    )

    success, error = await stream_manager.start_stream(
        config,
        stream_id=target_stream_id,
        account_id=account_id,
        account_name=account_name,
        title=request.title.strip() or default_title,
        source=source,
    )

    if success:
        return {
            "status": "started",
            "stream_id": target_stream_id,
            "message": "Stream started successfully",
        }
    raise HTTPException(status_code=500, detail=f"Failed to start stream: {error}")


@router.post("/stop")
async def stop_stream(request: Optional[StopStreamRequest] = Body(default=None)):
    """停止推流：可按 stream_id/账号停止，也可全部停止"""
    target_stream_id = None
    if request is not None:
        target_stream_id = _resolve_stream_id(request.stream_id, request.account_id)

    if target_stream_id:
        success, error = await stream_manager.stop_stream(target_stream_id)
        if success:
            return {
                "status": "stopped",
                "stream_id": target_stream_id,
                "message": "Stream stopped successfully",
            }
        raise HTTPException(status_code=500, detail=f"Failed to stop stream: {error}")

    result = await stream_manager.stop_all()
    if result["success"]:
        return {
            "status": "stopped",
            "message": "All streams stopped successfully",
            "results": result["results"],
        }
    raise HTTPException(status_code=500, detail={"message": "部分推流停止失败", "results": result["results"]})


@router.websocket("/ws")
async def stream_status_websocket(websocket: WebSocket):
    """多路推流实时状态推送"""
    token = websocket.cookies.get(ADMIN_COOKIE_NAME)
    if not get_admin_from_token(token):
        await websocket.close(code=1008, reason="管理员未登录")
        return

    await websocket.accept()
    try:
        while True:
            await websocket.send_json(
                {
                    "running_count": stream_manager.running_count,
                    "items": stream_manager.list_statuses(),
                }
            )
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass


@router.post("/create-room")
async def create_live_room(title: str, cover: UploadFile = File(None)):
    """
    Create a new live room and get RTMP push URL.
    This will interact with Weibo's live page.
    """
    if not await weibo_client.is_logged_in():
        raise HTTPException(status_code=401, detail="Not logged in")

    cover_path = None
    if cover:
        cover_id = str(uuid.uuid4())[:8]
        cover_ext = Path(cover.filename).suffix or ".jpg"
        cover_path = CONFIG.covers_dir / f"{cover_id}{cover_ext}"
        content = await cover.read()
        cover_path.write_bytes(content)

    result = await weibo_client.get_live_stream_info(
        title=title,
        cover_path=str(cover_path) if cover_path else None,
    )

    if result is None:
        raise HTTPException(status_code=500, detail="Failed to create live room")

    if result.get("status") == "need_analysis":
        return LiveRoomInfo(
            title=title,
            status="need_analysis",
            rtmp_url=None,
            stream_key=None,
        )

    return LiveRoomInfo(
        room_id=result.get("room_id"),
        title=title,
        rtmp_url=result.get("rtmp_url"),
        stream_key=result.get("stream_key"),
        status="created",
    )


@router.get("/check-login")
async def check_weibo_login():
    """Check if logged into Weibo"""
    logged_in = await weibo_client.is_logged_in()
    user_info = None
    if logged_in:
        user_info = await weibo_client.get_user_info()

    return {
        "logged_in": logged_in,
        "user_info": user_info,
    }
