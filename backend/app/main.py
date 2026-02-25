from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import asyncio

from .api import api_router
from .core import CONFIG, weibo_client, stream_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    print(f"Starting WeiboLive server on {CONFIG.host}:{CONFIG.port}")
    print(f"Data directory: {CONFIG.data_dir}")
    print(f"Videos directory: {CONFIG.videos_dir}")
    
    yield
    
    # Shutdown
    print("Shutting down...")
    await stream_manager.stop_all()
    await weibo_client.close_browser()

# Create FastAPI app
app = FastAPI(
    title="WeiboLive",
    description="微博直播自动挂机系统",
    version="1.0.0",
    lifespan=lifespan
)

# Include API routes
app.include_router(api_router)

# Mount static files for frontend (if exists)
frontend_dist = CONFIG.project_dir / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

# Serve frontend index.html for all non-API routes
@app.get("/")
async def serve_frontend():
    """Serve frontend index.html"""
    index_file = frontend_dist / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "WeiboLive API", "docs": "/docs"}

@app.get("/{path:path}")
async def serve_frontend_routes(path: str):
    """Serve frontend for all other routes"""
    # Don't intercept API routes
    if path.startswith("api/") or path.startswith("docs") or path.startswith("openapi"):
        raise HTTPException(status_code=404, detail="Not found")
    
    index_file = frontend_dist / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"error": "Not found"}
