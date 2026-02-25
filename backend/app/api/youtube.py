"""
YouTube 转播 API

注意：本项目为官方授权的学习项目，仅供学习 Web 自动化和流媒体技术使用。
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Body
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import logging
import shutil
import uuid

from ..core.youtube import youtube_parser
from ..core.stream import StreamConfig, StreamType
from ..core.overlay import WatermarkConfig, WatermarkPosition
from ..core import stream_account_manager, stream_manager
from ..core.config import CONFIG

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/youtube", tags=["youtube"])


# 水印文件存储目录
WATERMARK_DIR = CONFIG.data_dir / "watermarks"
WATERMARK_DIR.mkdir(parents=True, exist_ok=True)


def _resolve_watermark_path(filename: str) -> Path:
    """解析并校验水印文件路径，防止路径穿越"""
    safe_name = Path(filename).name
    if not safe_name or safe_name != filename:
        raise HTTPException(status_code=400, detail="非法文件名")

    path = (WATERMARK_DIR / safe_name).resolve()
    watermark_root = WATERMARK_DIR.resolve()

    if path.parent != watermark_root:
        raise HTTPException(status_code=400, detail="非法文件路径")

    return path


# ============ 请求/响应模型 ============

class ParseRequest(BaseModel):
    """解析请求"""
    url: str


class WatermarkSettings(BaseModel):
    """水印设置"""
    enabled: bool = False
    type: str = "text"  # "text" 或 "image"
    # 通用
    position: str = "bottom_right"
    opacity: float = 0.7
    margin: int = 10
    # 文字水印
    text: Optional[str] = None
    font_size: int = 24
    font_color: str = "white"
    # 图片水印
    image_filename: Optional[str] = None
    scale: float = 1.0


class StartRelayRequest(BaseModel):
    """开始转播请求"""
    youtube_url: str
    account_id: Optional[str] = None
    stream_id: Optional[str] = None
    rtmp_url: Optional[str] = None
    stream_key: Optional[str] = None
    quality: str = "best"
    bandwidth_mode: str = "normal"
    keepalive_pulse: bool = False
    pulse_on_seconds: int = 120
    pulse_off_seconds: int = 60
    watermark: Optional[WatermarkSettings] = None


class StopRelayRequest(BaseModel):
    stream_id: Optional[str] = None
    account_id: Optional[str] = None


class StreamInfoResponse(BaseModel):
    """流信息响应"""
    video_id: str
    title: str
    author: str
    is_live: bool
    thumbnail: str
    description: Optional[str] = None
    view_count: Optional[int] = None


# ============ API 端点 ============

@router.post("/parse")
async def parse_youtube_url(request: ParseRequest):
    """
    解析 YouTube URL，获取视频/直播信息
    """
    try:
        info = await youtube_parser.parse_url(request.url)
        
        return {
            "success": True,
            "data": {
                "video_id": info.video_id,
                "title": info.title,
                "author": info.author,
                "is_live": info.is_live,
                "thumbnail": info.thumbnail,
                "description": info.description,
                "view_count": info.view_count,
                "duration": info.duration,
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("解析 YouTube URL 失败")
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


@router.get("/status")
async def get_relay_status():
    """
    获取转播状态
    """
    status = stream_manager.list_statuses_by_type(StreamType.URL_STREAM.value)
    return {
        "success": True,
        "data": status,
        "running_count": len([item for item in status if item.get("is_running")]),
    }


@router.post("/start")
async def start_youtube_relay(request: StartRelayRequest):
    """
    开始 YouTube 转播
    """
    try:
        # 解析 YouTube URL
        info = await youtube_parser.parse_url(request.youtube_url)
        
        # 获取流 URL
        stream_url = await youtube_parser.get_stream_url(
            info.video_id, 
            request.quality
        )
        
        if not stream_url:
            raise HTTPException(status_code=400, detail="无法获取流地址")

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

        if account_id:
            target_stream_id = stream_manager.account_stream_id(account_id)
        elif request.stream_id and request.stream_id.strip():
            target_stream_id = request.stream_id.strip()
        else:
            target_stream_id = f"manual:{uuid.uuid4().hex[:8]}"
        
        # 构建水印配置
        watermark = None
        if request.watermark and request.watermark.enabled:
            position_map = {
                "top_left": WatermarkPosition.TOP_LEFT,
                "top_right": WatermarkPosition.TOP_RIGHT,
                "bottom_left": WatermarkPosition.BOTTOM_LEFT,
                "bottom_right": WatermarkPosition.BOTTOM_RIGHT,
                "center": WatermarkPosition.CENTER,
            }
            
            watermark = WatermarkConfig(
                enabled=True,
                position=position_map.get(
                    request.watermark.position, 
                    WatermarkPosition.BOTTOM_RIGHT
                ),
                opacity=request.watermark.opacity,
                margin=request.watermark.margin,
            )
            
            if request.watermark.type == "text" and request.watermark.text:
                watermark.text = request.watermark.text
                watermark.font_size = request.watermark.font_size
                watermark.font_color = request.watermark.font_color
            elif request.watermark.type == "image":
                if not request.watermark.image_filename:
                    raise HTTPException(status_code=400, detail="请选择水印图片")

                image_path = _resolve_watermark_path(request.watermark.image_filename)
                if not image_path.exists():
                    raise HTTPException(status_code=400, detail="指定水印图片不存在")

                watermark.image_path = str(image_path)
                watermark.scale = request.watermark.scale
        
        bandwidth_mode = request.bandwidth_mode
        if request.keepalive_pulse and bandwidth_mode == "normal":
            bandwidth_mode = "keepalive"

        # 构建推流配置
        config = StreamConfig(
            rtmp_url=rtmp_url,
            stream_key=stream_key,
            stream_url=stream_url,
            stream_type=StreamType.URL_STREAM,
            youtube_video_id=info.video_id,
            quality=request.quality,
            bandwidth_mode=bandwidth_mode,
            pulse_enabled=request.keepalive_pulse,
            pulse_on_seconds=request.pulse_on_seconds,
            pulse_off_seconds=request.pulse_off_seconds,
            watermark=watermark,
        )
        
        # 开始推流
        success, error = await stream_manager.start_stream(
            config,
            stream_id=target_stream_id,
            account_id=account_id,
            account_name=account_name,
            title=info.title,
            source="youtube",
        )
        
        if success:
            return {
                "success": True,
                "message": f"开始转播: {info.title}",
                "data": {
                    "video_id": info.video_id,
                    "title": info.title,
                    "stream_url": stream_url,
                    "stream_id": target_stream_id,
                }
            }
        else:
            raise HTTPException(status_code=500, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("开始转播失败")
        raise HTTPException(status_code=500, detail=f"转播失败: {str(e)}")


@router.post("/stop")
async def stop_youtube_relay(request: Optional[StopRelayRequest] = Body(default=None)):
    """
    停止转播
    """
    target_stream_id = None
    if request:
        if request.account_id and request.account_id.strip():
            target_stream_id = stream_manager.account_stream_id(request.account_id)
        elif request.stream_id and request.stream_id.strip():
            target_stream_id = request.stream_id.strip()

    if target_stream_id:
        success, error = await stream_manager.stop_stream(target_stream_id)
        if success:
            return {"success": True, "message": "转播已停止", "stream_id": target_stream_id}
        raise HTTPException(status_code=500, detail=error)

    youtube_streams = stream_manager.list_statuses_by_type(StreamType.URL_STREAM.value)
    results: list[dict] = []
    for item in youtube_streams:
        stream_id = item.get("stream_id")
        if not stream_id:
            continue
        success, error = await stream_manager.stop_stream(stream_id)
        results.append(
            {
                "stream_id": stream_id,
                "success": success,
                "error": None if success else error,
            }
        )

    all_success = all(entry["success"] for entry in results) if results else True
    if all_success:
        return {"success": True, "message": "转播已停止", "results": results}
    raise HTTPException(status_code=500, detail={"message": "部分转播停止失败", "results": results})


@router.post("/watermark/upload")
async def upload_watermark(file: UploadFile = File(...)):
    """
    上传水印图片
    """
    # 验证文件类型
    allowed_types = ["image/png", "image/jpeg", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400, 
            detail=f"不支持的文件类型: {file.content_type}"
        )
    
    # 生成文件名
    ext = Path(file.filename or "watermark.png").suffix.lstrip(".") or "png"
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = WATERMARK_DIR / filename
    
    # 保存文件
    try:
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return {
            "success": True,
            "data": {
                "filename": filename,
                "url": f"/api/youtube/watermark/{filename}",
                "size": filepath.stat().st_size,
            }
        }
    except Exception as e:
        logger.exception("保存水印图片失败")
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


@router.get("/watermark/list")
async def list_watermarks():
    """
    获取水印图片列表
    """
    watermarks = []
    for file in WATERMARK_DIR.iterdir():
        if file.is_file() and file.suffix.lower() in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
            watermarks.append({
                "filename": file.name,
                "url": f"/api/youtube/watermark/{file.name}",
                "size": file.stat().st_size,
            })
    
    return {
        "success": True,
        "data": watermarks
    }


@router.delete("/watermark/{filename}")
async def delete_watermark(filename: str):
    """
    删除水印图片
    """
    filepath = _resolve_watermark_path(filename)
    
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    
    try:
        filepath.unlink()
        return {"success": True, "message": "删除成功"}
    except Exception as e:
        logger.exception("删除水印图片失败")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.get("/check_live/{video_id}")
async def check_live_status(video_id: str):
    """
    检查直播状态
    """
    try:
        is_live = await youtube_parser.check_live_status(video_id)
        return {
            "success": True,
            "data": {
                "video_id": video_id,
                "is_live": is_live,
            }
        }
    except Exception as e:
        logger.exception("检查直播状态失败")
        raise HTTPException(status_code=500, detail=f"检查失败: {str(e)}")
