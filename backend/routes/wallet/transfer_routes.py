from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
import os

from routes.ton_finance import (
    send_usdt_withdrawal,
    create_audit_log
)
from .dependencies import require_roles

router = APIRouter()

class SendRequest(BaseModel):
    to_address: str
    amount: float


@router.post("/admin/wallet/send-usdt")
async def admin_send_usdt(
    data: SendRequest,
    request: Request,
    user: dict = Depends(require_roles(["admin"]))
):
    """Send USDT from hot wallet to any address (admin only)"""
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Сумма должна быть больше 0")
    
    try:
        # Send USDT via ton-service
        result = await send_usdt_withdrawal(
            to_address=data.to_address,
            amount=data.amount,
            comment="Admin withdrawal"
        )
        
        await create_audit_log(
            admin_user_id=user['id'],
            action='admin_send_usdt',
            new_value={
                "to": data.to_address,
                "amount": data.amount,
                "tx_hash": result.get('tx_hash')
            },
            ip_address=request.client.host
        )
        
        return {
            "success": True,
            "amount": data.amount,
            "currency": "USDT",
            "to_address": data.to_address,
            "tx_hash": result.get('tx_hash'),
            "message": f"Отправлено {data.amount} USDT"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/wallet/send-ton")
async def admin_send_ton(
    data: SendRequest,
    request: Request,
    user: dict = Depends(require_roles(["admin"]))
):
    """Send TON from hot wallet to any address (admin only)"""
    import httpx
    
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Сумма должна быть больше 0")
    
    try:
        # Send TON via ton-service
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{os.environ.get('TON_SERVICE_URL', 'http://localhost:8002')}/send",
                headers={"X-API-Key": os.environ.get('TON_SERVICE_API_KEY', 'ton_service_api_secret_key_2026')},
                json={
                    "to": data.to_address,
                    "amount": data.amount,
                    "comment": "Admin withdrawal"
                }
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail="Ошибка отправки TON")
            
            result = response.json()
        
        await create_audit_log(
            admin_user_id=user['id'],
            action='admin_send_ton',
            new_value={
                "to": data.to_address,
                "amount": data.amount,
                "seqno": result.get('seqno')
            },
            ip_address=request.client.host
        )
        
        return {
            "success": True,
            "amount": data.amount,
            "currency": "TON",
            "to_address": data.to_address,
            "seqno": result.get('seqno'),
            "message": f"Отправлено {data.amount} TON"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
