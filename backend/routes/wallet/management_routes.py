from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid
import os

from core.database import db as mongodb
from routes.ton_finance import (
    get_ton_service_health,
    get_hot_wallet_balance,
    create_audit_log
)
from .dependencies import require_roles

router = APIRouter()

class WalletChangeRequest(BaseModel):
    new_address: str = Field(..., min_length=48, description="New TON wallet address")
    new_mnemonic: str = Field(..., description="24-word mnemonic phrase")
    confirm: bool = Field(..., description="Confirmation flag")


@router.get("/admin/wallet/current")
async def get_current_wallet(user: dict = Depends(require_roles(["admin"]))):
    """Get current active wallet info"""
    try:
        # Get from TON service
        health = await get_ton_service_health()
        hot_wallet = await get_hot_wallet_balance()
        
        # Get wallet config from MongoDB
        wallet_config = await mongodb.wallet_config.find_one(
            {"status": "active"},
            {"_id": 0}
        )
        
        return {
            "success": True,
            "wallet": {
                "address": health.get("hotWallet", ""),
                "balance": hot_wallet.get("balance", 0),
                "network": health.get("network", "testnet"),
                "status": "active",
                "created_at": wallet_config.get("created_at") if wallet_config else None
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/wallet/history")
async def get_wallet_history(user: dict = Depends(require_roles(["admin"]))):
    """Get history of all wallets"""
    try:
        wallets = await mongodb.wallet_config.find(
            {},
            {"_id": 0}
        ).sort("created_at", -1).to_list(50)
        
        return {
            "success": True,
            "wallets": wallets
        }
    except Exception as e:
        return {"success": True, "wallets": []}


@router.post("/admin/wallet/change")
async def change_wallet(
    data: WalletChangeRequest,
    request: Request,
    user: dict = Depends(require_roles(["admin"]))
):
    """Change hot wallet (CRITICAL OPERATION)"""
    
    if not data.confirm:
        raise HTTPException(status_code=400, detail="Требуется подтверждение операции")
    
    # Validate mnemonic (24 words)
    words = data.new_mnemonic.strip().split()
    if len(words) != 24:
        raise HTTPException(status_code=400, detail="Мнемоника должна содержать 24 слова")
    
    try:
        # Archive current wallet
        await mongodb.wallet_config.update_many(
            {"status": "active"},
            {"$set": {"status": "archived", "archived_at": datetime.now().isoformat()}}
        )
        
        # Save new wallet config
        new_config = {
            "id": str(uuid.uuid4()),
            "address": data.new_address,
            "mnemonic_hash": hash(data.new_mnemonic),  # Don't store raw mnemonic in DB
            "status": "active",
            "network": "testnet",
            "created_at": datetime.now().isoformat(),
            "created_by": user['id']
        }
        await mongodb.wallet_config.insert_one(new_config)
        
        # Update TON service .env (this requires service restart)
        # For now, just log the change - actual implementation needs manual restart
        
        # Create audit log
        await create_audit_log(
            admin_user_id=user['id'],
            action='change_wallet',
            old_value={"status": "archived"},
            new_value={"address": data.new_address, "status": "active"},
            details="Hot wallet changed",
            ip_address=request.client.host
        )
        
        return {
            "success": True,
            "message": "Кошелек изменен. Требуется перезапуск TON сервиса.",
            "new_address": data.new_address,
            "note": "Обновите HOT_WALLET_MNEMONIC в /app/ton-service/.env и перезапустите сервис"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Temporary storage for pending wallet activations
_pending_wallets = {}


@router.post("/admin/wallet/generate")
async def generate_new_wallet(
    request: Request,
    user: dict = Depends(require_roles(["admin"]))
):
    """
    Generate a new TON wallet and return seed phrase ONE TIME.
    The mnemonic is NOT saved on server until activation.
    """
    import httpx
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{os.environ.get('TON_SERVICE_URL', 'http://localhost:8002')}/generate-wallet",
                headers={"X-API-Key": os.environ.get('TON_SERVICE_API_KEY', 'ton_service_api_secret_key_2026')}
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail="Ошибка генерации кошелька")
            
            wallet_data = response.json()
            
            # Store temporarily in memory for activation
            # Will be saved to .env only after user confirms they saved the seed
            _pending_wallets[wallet_data['address']] = {
                'mnemonic': wallet_data['mnemonic'],
                'address': wallet_data['address'],
                'created_at': datetime.now(timezone.utc).isoformat(),
                'created_by': user['id']
            }
            
            await create_audit_log(
                admin_user_id=user['id'],
                action='generate_wallet',
                new_value={"address": wallet_data.get("address")},
                ip_address=request.client.host
            )
            
            # Return wallet data WITH mnemonic (one-time display)
            return {
                "success": True,
                "wallet": {
                    "address": wallet_data['address'],
                    "mnemonic": wallet_data['mnemonic']  # ONE TIME ONLY!
                },
                "message": "Кошелёк сгенерирован. СОХРАНИТЕ SEED-ФРАЗУ!"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/wallet/activate")
async def activate_wallet(
    request: Request,
    user: dict = Depends(require_roles(["admin"]))
):
    """
    Activate a generated wallet - save mnemonic to .env and restart TON service.
    """
    data = await request.json()
    address = data.get('address')
    
    if not address or address not in _pending_wallets:
        raise HTTPException(status_code=400, detail="Кошелёк не найден. Сгенерируйте новый.")
    
    pending = _pending_wallets[address]
    mnemonic = pending['mnemonic']
    
    try:
        import subprocess
        
        # Update TON service .env file
        env_path = '/app/ton-service/.env'
        
        # Read current .env
        with open(env_path, 'r') as f:
            env_content = f.read()
        
        # Update mnemonic and address
        import re
        env_content = re.sub(
            r'HOT_WALLET_MNEMONIC=.*',
            f'HOT_WALLET_MNEMONIC={mnemonic}',
            env_content
        )
        env_content = re.sub(
            r'HOT_WALLET_ADDRESS=.*',
            f'HOT_WALLET_ADDRESS={address}',
            env_content
        )
        
        # Write updated .env
        with open(env_path, 'w') as f:
            f.write(env_content)
        
        # Restart TON service
        subprocess.run(['sudo', 'supervisorctl', 'restart', 'ton-service'], check=True)
        
        # Remove from pending
        del _pending_wallets[address]
        
        await create_audit_log(
            admin_user_id=user['id'],
            action='activate_wallet',
            new_value={"address": address},
            ip_address=request.client.host
        )
        
        return {
            "success": True,
            "message": "Кошелёк активирован! TON service перезапущен.",
            "address": address
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка активации: {str(e)}")
