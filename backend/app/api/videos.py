import uuid
import shutil
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from ..core import CONFIG

router = APIRouter(prefix="/api/videos", tags=["videos"])

class VideoInfo(BaseModel):
    id: str
    filename: str
    size: int
    path: str

def get_video_files() -> List[VideoInfo]:
    """Get list of uploaded videos"""
    videos = []
    for file in CONFIG.videos_dir.iterdir():
        if file.is_file() and file.suffix.lower() in ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv']:
            videos.append(VideoInfo(
                id=file.stem,
                filename=file.name,
                size=file.stat().st_size,
                path=str(file)
            ))
    return videos

@router.get("", response_model=List[VideoInfo])
async def list_videos():
    """List all uploaded videos"""
    return get_video_files()

@router.post("/upload", response_model=VideoInfo)
async def upload_video(file: UploadFile = File(...)):
    """Upload a video file"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    safe_filename = Path(file.filename).name

    # Check file extension
    allowed_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv']
    file_ext = Path(safe_filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Generate unique filename
    video_id = str(uuid.uuid4())[:8]
    filename = f"{video_id}_{safe_filename}"
    file_path = CONFIG.videos_dir / filename
    
    # Save file (stream copy to avoid loading huge video into memory)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    size = file_path.stat().st_size
    
    return VideoInfo(
        id=video_id,
        filename=filename,
        size=size,
        path=str(file_path)
    )

@router.delete("/{video_id}")
async def delete_video(video_id: str):
    """Delete a video file"""
    for video in get_video_files():
        if video.id == video_id:
            Path(video.path).unlink()
            return {"status": "deleted", "video_id": video_id}
    
    raise HTTPException(status_code=404, detail="Video not found")

@router.get("/{video_id}")
async def get_video(video_id: str):
    """Get video file info"""
    for video in get_video_files():
        if video.id == video_id:
            return video
    
    raise HTTPException(status_code=404, detail="Video not found")

@router.get("/{video_id}/download")
async def download_video(video_id: str):
    """Download video file"""
    for video in get_video_files():
        if video.id == video_id:
            return FileResponse(
                video.path,
                media_type='application/octet-stream',
                filename=video.filename
            )
    
    raise HTTPException(status_code=404, detail="Video not found")
