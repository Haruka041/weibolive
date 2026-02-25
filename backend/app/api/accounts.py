from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core import stream_account_manager

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


class StreamAccountCreateRequest(BaseModel):
    name: str
    rtmp_url: str
    stream_key: str
    enabled: bool = True


class StreamAccountUpdateRequest(BaseModel):
    name: Optional[str] = None
    rtmp_url: Optional[str] = None
    stream_key: Optional[str] = None
    enabled: Optional[bool] = None


@router.get("")
async def list_stream_accounts():
    accounts = await stream_account_manager.list_accounts()
    return [account.to_dict() for account in accounts]


@router.get("/{account_id}")
async def get_stream_account(account_id: str):
    account = await stream_account_manager.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    return account.to_dict()


@router.post("")
async def create_stream_account(request: StreamAccountCreateRequest):
    try:
        account = await stream_account_manager.create_account(
            name=request.name,
            rtmp_url=request.rtmp_url,
            stream_key=request.stream_key,
            enabled=request.enabled,
        )
        return account.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/{account_id}")
async def update_stream_account(account_id: str, request: StreamAccountUpdateRequest):
    try:
        account = await stream_account_manager.update_account(
            account_id,
            name=request.name,
            rtmp_url=request.rtmp_url,
            stream_key=request.stream_key,
            enabled=request.enabled,
        )
        if not account:
            raise HTTPException(status_code=404, detail="账号不存在")
        return account.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{account_id}")
async def delete_stream_account(account_id: str):
    success = await stream_account_manager.delete_account(account_id)
    if not success:
        raise HTTPException(status_code=404, detail="账号不存在")
    return {"success": True, "account_id": account_id}
