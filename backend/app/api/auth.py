from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
from ..core import weibo_client

router = APIRouter(prefix="/api/auth", tags=["auth"])

class LoginStatus(BaseModel):
    logged_in: bool
    user_info: Optional[dict] = None

@router.get("/qrcode")
async def get_login_qrcode():
    """Get Weibo login QR code image"""
    qr_bytes = await weibo_client.get_login_qrcode()
    
    if qr_bytes is None:
        # Already logged in or error
        if await weibo_client.is_logged_in():
            return {"status": "already_logged_in"}
        raise HTTPException(status_code=500, detail="Failed to get QR code")
    
    return Response(content=qr_bytes, media_type="image/png")

@router.get("/status")
async def get_login_status():
    """Check if user is logged in"""
    logged_in = await weibo_client.is_logged_in()
    user_info = None
    
    if logged_in:
        user_info = await weibo_client.get_user_info()
    
    return LoginStatus(logged_in=logged_in, user_info=user_info)

@router.post("/wait")
async def wait_for_login(timeout: int = 120):
    """Wait for user to scan QR code and login"""
    success = await weibo_client.wait_for_login(timeout)
    
    if success:
        user_info = await weibo_client.get_user_info()
        return {"status": "success", "user_info": user_info}
    else:
        return {"status": "timeout"}

@router.post("/logout")
async def logout():
    """Logout and clear cookies"""
    await weibo_client.close_browser()
    return {"status": "logged_out"}
