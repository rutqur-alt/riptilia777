"""
TON Finance Integration for Reptiloid Exchange
Handles communication between Python backend and Node.js TON service
"""

import os
import httpx
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# TON Service configuration
TON_SERVICE_URL = os.environ.get('TON_SERVICE_URL', 'http://localhost:8002')
TON_SERVICE_API_KEY = os.environ.get('TON_SERVICE_API_KEY', 'ton_service_api_secret_key_2026')

async def _ton_request(method: str, endpoint: str, data: dict = None) -> dict:
    """Make authenticated request to TON service"""
    headers = {
        'X-Api-Key': TON_SERVICE_API_KEY,
        'Content-Type': 'application/json'
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        if method == 'GET':
            response = await client.get(f"{TON_SERVICE_URL}{endpoint}", headers=headers)
        elif method == 'POST':
            response = await client.post(f"{TON_SERVICE_URL}{endpoint}", json=data, headers=headers)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        if response.status_code != 200:
            logger.error(f"TON service error: {response.status_code} - {response.text}")
            raise Exception(f"TON service error: {response.text}")
        
        return response.json()


async def get_ton_service_health() -> dict:
    """Check TON service health"""
    try:
        return await _ton_request('GET', '/health')
    except Exception as e:
        logger.error(f"TON service health check failed: {e}")
        return {'status': 'error', 'message': str(e)}


async def create_user_finance_record(user_id: str) -> dict:
    """Create finance record for new user in PostgreSQL"""
    return await _ton_request('POST', '/create-user-finance', {'userId': user_id})


async def get_deposit_address(user_id: str) -> dict:
    """Get deposit address and comment for user"""
    return await _ton_request('GET', f'/deposit-address/{user_id}')


async def get_user_ton_balance(user_id: str) -> dict:
    """Get user's TON balance from PostgreSQL"""
    return await _ton_request('GET', f'/user-balance/{user_id}')


async def get_hot_wallet_balance() -> dict:
    """Get hot wallet balance"""
    return await _ton_request('GET', '/hot-wallet/balance')


async def get_user_transactions(user_id: str, limit: int = 50, offset: int = 0) -> dict:
    """Get user's transaction history"""
    return await _ton_request('GET', f'/user-transactions/{user_id}?limit={limit}&offset={offset}')


async def request_withdrawal(
    user_id: str,
    amount: float,
    to_address: str,
    comment: str = ''
) -> dict:
    """
    Request TON withdrawal
    For amounts >= 50 TON, requires manual approval
    """
    return await _ton_request('POST', '/send-ton', {
        'to': to_address,
        'amount': amount,
        'comment': comment,
        'userId': user_id
    })


# ==================== PostgreSQL Direct Connection (for complex queries) ====================

import asyncpg
from contextlib import asynccontextmanager

_pg_pool = None

async def get_pg_pool():
    """Get PostgreSQL connection pool"""
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = await asyncpg.create_pool(
            host=os.environ.get('POSTGRES_HOST', 'localhost'),
            port=int(os.environ.get('POSTGRES_PORT', 5432)),
            database=os.environ.get('POSTGRES_DB', 'reptiloid_finance'),
            user=os.environ.get('POSTGRES_USER', 'finance_admin'),
            password=os.environ.get('POSTGRES_PASSWORD', 'finance_secure_2026'),
            min_size=2,
            max_size=10
        )
    return _pg_pool


@asynccontextmanager
async def pg_transaction():
    """Context manager for PostgreSQL transactions"""
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            yield conn


async def get_finance_analytics() -> dict:
    """Get financial analytics for admin dashboard"""
    pool = await get_pg_pool()
    
    async with pool.acquire() as conn:
        # Total user balances (liabilities)
        total_balances = await conn.fetchrow("""
            SELECT 
                COALESCE(SUM(balance_ton), 0) as total_ton,
                COALESCE(SUM(balance_usd), 0) as total_usd,
                COALESCE(SUM(frozen_ton), 0) as frozen_ton,
                COALESCE(SUM(frozen_usd), 0) as frozen_usd
            FROM users_finance
        """)
        
        # Transaction stats (24h)
        tx_stats = await conn.fetchrow("""
            SELECT 
                COALESCE(SUM(CASE WHEN type = 'deposit' THEN amount ELSE 0 END), 0) as deposits_24h,
                COALESCE(SUM(CASE WHEN type = 'withdraw' THEN amount ELSE 0 END), 0) as withdrawals_24h,
                COALESCE(SUM(fee), 0) as fees_24h,
                COUNT(CASE WHEN type = 'deposit' THEN 1 END) as deposit_count,
                COUNT(CASE WHEN type = 'withdraw' THEN 1 END) as withdrawal_count
            FROM transactions
            WHERE created_at > NOW() - INTERVAL '24 hours'
            AND status = 'success'
        """)
        
        # Pending transactions
        pending = await conn.fetchrow("""
            SELECT COUNT(*) as count FROM transactions WHERE status = 'pending'
        """)
        
        # Review transactions (need attention)
        review = await conn.fetchrow("""
            SELECT COUNT(*) as count FROM transactions WHERE status = 'review'
        """)
        
        # Get hot wallet balance
        try:
            hot_wallet = await get_hot_wallet_balance()
            hot_wallet_balance = hot_wallet.get('balance', 0)
        except:
            hot_wallet_balance = 0
        
        total_liabilities = float(total_balances['total_ton'])
        reserve_ratio = (hot_wallet_balance / total_liabilities * 100) if total_liabilities > 0 else 100
        
        return {
            'liabilities': {
                'total_ton': float(total_balances['total_ton']),
                'total_usd': float(total_balances['total_usd']),
                'frozen_ton': float(total_balances['frozen_ton']),
                'frozen_usd': float(total_balances['frozen_usd'])
            },
            'assets': {
                'hot_wallet_ton': hot_wallet_balance
            },
            'reserve_ratio': round(reserve_ratio, 2),
            'reserve_healthy': reserve_ratio >= 105,
            'stats_24h': {
                'deposits': float(tx_stats['deposits_24h']),
                'withdrawals': float(tx_stats['withdrawals_24h']),
                'fees_collected': float(tx_stats['fees_24h']),
                'deposit_count': tx_stats['deposit_count'],
                'withdrawal_count': tx_stats['withdrawal_count'],
                'net_flow': float(tx_stats['deposits_24h']) - float(tx_stats['withdrawals_24h'])
            },
            'pending_transactions': pending['count'],
            'review_transactions': review['count'],
            'timestamp': datetime.utcnow().isoformat()
        }


async def get_audit_logs(limit: int = 100, admin_id: str = None) -> list:
    """Get audit logs"""
    pool = await get_pg_pool()
    
    query = "SELECT * FROM audit_logs"
    params = []
    
    if admin_id:
        query += " WHERE admin_user_id = $1"
        params.append(admin_id)
    
    query += " ORDER BY created_at DESC LIMIT $" + str(len(params) + 1)
    params.append(limit)
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


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
    """Create audit log entry"""
    pool = await get_pg_pool()
    
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO audit_logs (admin_user_id, action, target_user_id, target_tx_id, old_value, new_value, details, ip_address)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """, admin_user_id, action, target_user_id, target_tx_id, 
        str(old_value) if old_value else None,
        str(new_value) if new_value else None,
        details, ip_address)
