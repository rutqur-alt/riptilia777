"""
TON Finance Service Integration
Provides interface between FastAPI backend and TON Node.js microservice
Uses MongoDB for all financial data (fallback mode)
"""

import httpx
import os
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# TON Service configuration
TON_SERVICE_URL = os.environ.get('TON_SERVICE_URL', 'http://localhost:8002')
TON_SERVICE_API_KEY = os.environ.get('TON_SERVICE_API_KEY', 'ton_service_api_secret_key_2026')

# MongoDB database
from core.database import db


async def _ton_request(method: str, endpoint: str, data: dict = None, timeout: float = 30.0) -> dict:
    """Make request to TON service with error handling"""
    url = f"{TON_SERVICE_URL}{endpoint}"
    headers = {'X-API-Key': TON_SERVICE_API_KEY, 'Content-Type': 'application/json'}
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            if method == 'GET':
                response = await client.get(url, headers=headers)
            elif method == 'POST':
                response = await client.post(url, headers=headers, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            if response.status_code != 200:
                error_detail = response.text[:200] if response.text else "Unknown error"
                raise Exception(f"TON service error: {error_detail}")
            
            return response.json()
        except httpx.TimeoutException:
            raise Exception("TON service timeout")
        except httpx.ConnectError:
            raise Exception("TON service unavailable")


async def get_ton_service_health() -> dict:
    """Check TON service health"""
    try:
        return await _ton_request('GET', '/health')
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def send_usdt_withdrawal(to_address: str, amount: float, comment: str = "") -> dict:
    """
    Send USDT from hot wallet to user's address.
    Returns tx_hash on success.
    """
    try:
        result = await _ton_request('POST', '/send-usdt', {
            'to': to_address,
            'amount': amount,
            'comment': comment
        }, timeout=60.0)  # Longer timeout for blockchain tx
        
        logger.info(f"USDT withdrawal sent: {amount} USDT to {to_address}, hash: {result.get('tx_hash')}")
        return result
    except Exception as e:
        logger.error(f"Failed to send USDT: {e}")
        raise


async def get_deposit_address(user_id: str) -> dict:
    """Get deposit address for user"""
    return await _ton_request('GET', f'/deposit-address/{user_id}')


async def get_hot_wallet_balance() -> dict:
    """Get hot wallet balance from tonapi.io with caching"""
    import httpx
    
    # Simple in-memory cache
    cache_key = "hot_wallet_balance"
    cache_ttl = 30  # 30 seconds
    
    # Check cache
    if hasattr(get_hot_wallet_balance, '_cache'):
        cached = get_hot_wallet_balance._cache.get(cache_key)
        if cached and (datetime.now(timezone.utc).timestamp() - cached['time']) < cache_ttl:
            return cached['data']
    
    try:
        # Get hot wallet address from health endpoint (fast, local)
        health = await get_ton_service_health()
        address = health.get('hotWallet', '')
        
        if not address:
            return {"balance": 0, "ton_balance": 0, "usdt_balance": 0, "currency": "USDT"}
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Get TON balance from tonapi.io
            ton_balance = 0
            try:
                acc_response = await client.get(f"https://tonapi.io/v2/accounts/{address}")
                if acc_response.status_code == 200:
                    acc_data = acc_response.json()
                    raw_balance = int(acc_data.get('balance', 0))
                    ton_balance = raw_balance / 1e9
                    
                    # For uninit wallets, calculate from incoming transactions
                    if acc_data.get('status') == 'uninit' and ton_balance < 0.01:
                        events_response = await client.get(f"https://tonapi.io/v2/accounts/{address}/events?limit=20")
                        if events_response.status_code == 200:
                            events_data = events_response.json()
                            total_ton = 0
                            # Convert our address to raw format for comparison
                            # EQCxIoq1inAuvVt3U77cPyopvQXeSQjTfyJzhAVtdfCbqapC -> 0:b1228ab58a702ebd5b7753bedc3f2a29bd05de4908d37f227384056d75f09ba9
                            our_addr_hex = "b1228ab58a702ebd5b7753bedc3f2a29bd05de4908d37f227384056d75f09ba9"
                            for event in events_data.get('events', []):
                                for action in event.get('actions', []):
                                    if action.get('type') == 'TonTransfer':
                                        transfer = action.get('TonTransfer', {})
                                        recipient = transfer.get('recipient', {}).get('address', '')
                                        # Check if we're the recipient (incoming)
                                        if recipient and our_addr_hex in recipient.lower():
                                            total_ton += int(transfer.get('amount', 0)) / 1e9
                            if total_ton > ton_balance:
                                ton_balance = total_ton
            except:
                pass
            
            # Get USDT balance (jettons)
            usdt_balance = 0
            try:
                jettons_response = await client.get(f"https://tonapi.io/v2/accounts/{address}/jettons")
                if jettons_response.status_code == 200:
                    jettons_data = jettons_response.json()
                    for jetton in jettons_data.get('balances', []):
                        jetton_info = jetton.get('jetton', {})
                        symbol = jetton_info.get('symbol', '')
                        if symbol.upper() in ['USDT', 'USD₮']:
                            balance_str = jetton.get('balance', '0')
                            decimals = jetton_info.get('decimals', 6)
                            usdt_balance = int(balance_str) / (10 ** decimals)
                            break
            except:
                pass
            
            result = {
                "success": True,
                "address": address,
                "balance": usdt_balance,
                "ton_balance": round(ton_balance, 4),
                "usdt_balance": usdt_balance,
                "currency": "USDT"
            }
            
            # Save to cache
            if not hasattr(get_hot_wallet_balance, '_cache'):
                get_hot_wallet_balance._cache = {}
            get_hot_wallet_balance._cache[cache_key] = {
                'time': datetime.now(timezone.utc).timestamp(),
                'data': result
            }
            
            return result
            
    except Exception as e:
        return {"balance": 0, "ton_balance": 0, "usdt_balance": 0, "currency": "USDT", "error": str(e)}


async def create_user_finance_record(user_id: str) -> dict:
    """Create or ensure user finance record exists in MongoDB"""
    # Check if user exists in traders or merchants
    trader = await db.traders.find_one({"id": user_id}, {"_id": 0})
    merchant = await db.merchants.find_one({"id": user_id}, {"_id": 0})
    
    if not trader and not merchant:
        raise Exception(f"User not found: {user_id}")
    
    # Balance is already stored in traders/merchants collection as balance_usdt
    return {"success": True, "user_id": user_id}


async def get_user_ton_balance(user_id: str) -> dict:
    """Get user's balance from MongoDB (traders/merchants collection)"""
    # Check traders first
    trader = await db.traders.find_one({"id": user_id}, {"_id": 0, "balance_usdt": 1, "frozen_usdt": 1})
    if trader:
        balance = trader.get("balance_usdt", 0) or 0
        frozen = trader.get("frozen_usdt", 0) or 0
        available = balance - frozen
        return {
            "balance_ton": balance,
            "balance_usd": balance,
            "balance_usdt": balance,
            "frozen_ton": frozen,
            "frozen_usd": frozen,
            "frozen_usdt": frozen,
            "available_ton": available,
            "available_usd": available,
            "available_usdt": available
        }
    
    # Check merchants
    merchant = await db.merchants.find_one({"id": user_id}, {"_id": 0, "balance_usdt": 1, "frozen_usdt": 1})
    if merchant:
        balance = merchant.get("balance_usdt", 0) or 0
        frozen = merchant.get("frozen_usdt", 0) or 0
        available = balance - frozen
        return {
            "balance_ton": balance,
            "balance_usd": balance,
            "balance_usdt": balance,
            "frozen_ton": frozen,
            "frozen_usd": frozen,
            "frozen_usdt": frozen,
            "available_ton": available,
            "available_usd": available,
            "available_usdt": available
        }
    
    # Check admins
    admin = await db.admins.find_one({"id": user_id}, {"_id": 0})
    if admin:
        return {
            "balance_ton": 0,
            "balance_usd": 0,
            "balance_usdt": 0,
            "frozen_ton": 0,
            "frozen_usd": 0,
            "frozen_usdt": 0,
            "available_ton": 0,
            "available_usd": 0,
            "available_usdt": 0
        }
    
    raise Exception(f"User not found: {user_id}")


async def get_user_transactions(user_id: str, limit: int = 50, offset: int = 0) -> dict:
    """Get user's transaction history from MongoDB transactions collection"""
    # Get transactions from dedicated collection
    transactions = await db.transactions.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    
    # Also get recent trades to show in history
    trades = await db.trades.find(
        {"$or": [{"trader_id": user_id}, {"merchant_id": user_id}]},
        {"_id": 0, "id": 1, "type": 1, "amount_usdt": 1, "merchant_receives_usdt": 1, "merchant_id": 1, "trader_id": 1, "status": 1, "created_at": 1}
    ).sort("created_at", -1).limit(20).to_list(20)
    
    # Format trades as transactions (if not already in transactions)
    existing_ids = {t.get("id") for t in transactions}
    for trade in trades:
        trade_id = trade.get("id")
        if trade_id and trade_id not in existing_ids:
            # For merchants, show actual received amount (minus platform fee)
            # For traders, show full amount
            is_merchant_trade = trade.get("merchant_id") == user_id
            if is_merchant_trade:
                # Merchant receives amount after commission deduction
                amount = trade.get("merchant_receives_usdt") or trade.get("amount_usdt", 0)
                description = f"Сделка P2P: {amount:.2f} USDT (после комиссии)"
            else:
                amount = trade.get("amount_usdt", 0)
                description = f"Сделка P2P: {amount:.2f} USDT"
            
            transactions.append({
                "id": trade_id,
                "type": "trade",
                "amount": amount,
                "currency": "USDT",
                "status": trade.get("status"),
                "created_at": trade.get("created_at"),
                "description": description
            })
    
    # Sort combined results by date
    transactions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    total_count = await db.transactions.count_documents({"user_id": user_id})
    
    return {"transactions": transactions[:limit], "count": total_count}


async def request_withdrawal(
    user_id: str,
    amount: float,
    to_address: str,
    comment: str = ''
) -> dict:
    """Request withdrawal - creates pending request in MongoDB"""
    import uuid
    
    withdrawal_request = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "amount": amount,
        "to_address": to_address,
        "comment": comment,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.withdrawal_requests.insert_one(withdrawal_request)
    
    return {"success": True, "request_id": withdrawal_request["id"], "status": "pending"}


async def get_finance_analytics() -> dict:
    """Get financial analytics for admin dashboard (using MongoDB)"""
    try:
        # Get total trader balances
        trader_pipeline = [{"$group": {"_id": None, "total": {"$sum": "$balance_usdt"}}}]
        trader_result = await db.traders.aggregate(trader_pipeline).to_list(1)
        trader_balance = trader_result[0]["total"] if trader_result else 0
        
        # Get total merchant balances
        merchant_pipeline = [{"$group": {"_id": None, "total": {"$sum": "$balance_usdt"}}}]
        merchant_result = await db.merchants.aggregate(merchant_pipeline).to_list(1)
        merchant_balance = merchant_result[0]["total"] if merchant_result else 0
        
        total_user_balance = (trader_balance or 0) + (merchant_balance or 0)
        
        # Hot wallet balance from TON service
        hot_wallet_balance = 0
        try:
            hw_data = await _ton_request('GET', '/hot-wallet/balance')
            hot_wallet_balance = hw_data.get('balance', 0)
        except:
            pass
        
        # Pending withdrawals
        pending = await db.withdrawal_requests.count_documents({"status": "pending"})
        review = await db.withdrawal_requests.count_documents({"status": "review"})
        
        # Calculate reserve ratio
        reserve_ratio = (hot_wallet_balance / total_user_balance * 100) if total_user_balance > 0 else 100
        
        return {
            # Format expected by frontend
            "liabilities": {
                "total_ton": total_user_balance,
                "total_usd": total_user_balance,
                "frozen_ton": 0,
                "frozen_usd": 0
            },
            "assets": {
                "hot_wallet_ton": hot_wallet_balance,
                "hot_wallet_usd": hot_wallet_balance
            },
            "reserve_ratio": round(reserve_ratio, 2),
            "reserve_healthy": reserve_ratio >= 100 or total_user_balance == 0,
            "stats_24h": {
                "deposits": 0,
                "withdrawals": 0,
                "fees_collected": 0,
                "deposit_count": 0,
                "withdrawal_count": 0,
                "net_flow": 0
            },
            "pending_transactions": pending,
            "review_transactions": review,
            # Legacy format
            "hot_wallet_balance": hot_wallet_balance,
            "total_user_balances": total_user_balance,
            "reserve_buffer": 2.0,
            "available_for_platform": hot_wallet_balance - total_user_balance - 2.0,
            "pending_withdrawals": pending,
            "deposits_24h": 0,
            "withdrawals_24h": 0,
            "fee_income_24h": 0
        }
    except Exception as e:
        logger.error(f"Error getting finance analytics: {e}")
        return {
            "hot_wallet_balance": 0,
            "total_user_balances": 0,
            "reserve_buffer": 2.0,
            "available_for_platform": 0,
            "pending_withdrawals": 0,
            "deposits_24h": 0,
            "withdrawals_24h": 0,
            "fee_income_24h": 0
        }


async def get_audit_logs(limit: int = 100, admin_id: str = None) -> list:
    """Get audit logs from MongoDB"""
    query = {}
    if admin_id:
        query["admin_id"] = admin_id
    
    logs = await db.audit_logs.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return logs


async def create_audit_log(
    admin_user_id: str,
    action: str,
    target_user_id: str = None,
    target_tx_id: str = None,
    old_value: dict = None,
    new_value: dict = None,
    details: str = None,
    ip_address: str = None
) -> None:
    """Create audit log entry in MongoDB"""
    import uuid
    
    log_entry = {
        "id": str(uuid.uuid4()),
        "admin_id": admin_user_id,
        "action": action,
        "target_user_id": target_user_id,
        "target_tx_id": target_tx_id,
        "old_value": old_value,
        "new_value": new_value,
        "details": details,
        "ip_address": ip_address,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.audit_logs.insert_one(log_entry)
