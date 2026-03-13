from datetime import datetime, timezone
import uuid
import logging

from core.database import db

logger = logging.getLogger(__name__)

async def _audit_log_dispute(action: str, trade_id: str, user_id: str, user_role: str, details: dict = None):
    """Write audit log entry for dispute action"""
    await db.dispute_audit_log.insert_one({
        "id": str(uuid.uuid4()),
        "action": action,
        "trade_id": trade_id,
        "user_id": user_id,
        "user_role": user_role,
        "details": details or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


def _build_dispute_system_message(trade: dict, opener: str, reason: str, now: str) -> str:
    """Build detailed first system message with full trade info per spec section 10"""
    provider_id = trade.get("provider_id", "N/A")
    merchant_id = trade.get("merchant_id", "N/A")
    buyer_id = trade.get("buyer_id") or trade.get("client_id") or "N/A"
    trader_id = trade.get("trader_id", "N/A")

    lines = [
        "--- СПОР QR-АГРЕГАТОРА ---",
        f"ID сделки: {trade.get('id')}",
        f"Тип сделки: QR-агрегатор",
        f"Признак QR-агрегатора: Да",
        f"Покупатель: {buyer_id}",
        f"Продавец (провайдер): {provider_id}",
        f"Мерчант: {merchant_id}",
        f"Трейдер: {trader_id}",
        f"Дата создания сделки: {trade.get('created_at', 'N/A')}",
        f"Дата открытия спора: {now}",
        f"Сумма оплаты: {trade.get('amount_rub', 0)} RUB",
        f"Сумма в USDT: {trade.get('amount_usdt', 0)} USDT",
        f"Сумма зачисления мерчанту: {trade.get('merchant_receives_usdt', 'N/A')} USDT",
        f"Валюта: RUB / USDT",
        f"Платёжный метод: {trade.get('qr_method', 'qr')}",
        f"Статус платежа: {trade.get('status', 'N/A')}",
        f"ID транзакции: {trade.get('trustgain_operation_id') or trade.get('qr_operation_id', 'N/A')}",
        f"ID мерчанта: {merchant_id}",
        f"ID провайдера: {provider_id}",
        f"Комиссия платформы: {trade.get('platform_commission_usdt', 0)} USDT",
        f"Комиссия мерчанта: {trade.get('merchant_commission_usdt', 0)} USDT",
        f"Заморожено у провайдера: {trade.get('total_freeze_usdt', 0)} USDT",
        f"",
        f"Спор открыт: {opener}",
        f"Причина: {reason}",
    ]
    return "\n".join(lines)


def _check_dispute_eligibility(trade: dict) -> tuple:
    """Check if trade is eligible for dispute per spec sections 2 and 5.
    Returns (eligible: bool, error_message: str)"""
    # Must be QR aggregator trade
    if not trade.get("qr_aggregator_trade") and not trade.get("is_qr_aggregator"):
        return False, "Спор доступен только для сделок QR-агрегатора"

    status = trade.get("status", "")

    # Already disputed
    if status == "disputed":
        return False, "Спор уже открыт по этой сделке"

    # Already completed — no dispute needed
    if status == "completed":
        return False, "Сделка уже завершена"

    # Condition 1: cancelled status — eligible
    if status == "cancelled":
        return True, ""

    # Condition 2: active (pending/paid) and >60 minutes old
    if status in ("pending", "paid", "active"):
        created_at = trade.get("created_at")
        if created_at:
            try:
                created_time = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                minutes_passed = (now - created_time).total_seconds() / 60
                if minutes_passed < 60:
                    remaining = int(60 - minutes_passed)
                    return False, f"Спор можно открыть через {remaining} мин. (активная сделка должна быть старше 60 минут)"
                return True, ""
            except Exception:
                pass
        return True, ""

    return False, f"Спор невозможен для сделки со статусом '{status}'"


async def _create_qr_dispute_conversation(trade: dict, reason: str, opener: str, opener_id: str) -> dict:
    """Create a P2P dispute conversation for QR trade"""
    now = datetime.now(timezone.utc).isoformat()
    trade_id = trade["id"]
    
    # Participants: merchant/buyer, provider, admins
    participants = []
    
    # 1. Buyer (Merchant or Trader)
    if trade.get("merchant_id"):
        participants.append({
            "user_id": trade["merchant_id"],
            "role": "merchant",
            "joined_at": now
        })
    elif trade.get("buyer_id"):
        participants.append({
            "user_id": trade["buyer_id"],
            "role": "trader",
            "joined_at": now
        })
        
    # 2. Provider
    if trade.get("provider_id"):
        participants.append({
            "user_id": trade["provider_id"],
            "role": "qr_provider",
            "joined_at": now
        })
        
    # 3. Admins/Mods (will join dynamically, but we create the conv)
    
    conv_id = str(uuid.uuid4())
    conversation = {
        "id": conv_id,
        "type": "p2p_dispute",
        "related_id": trade_id,
        "title": f"Спор по сделке {trade_id}",
        "status": "active",
        "participants": participants,
        "created_at": now,
        "updated_at": now,
        "metadata": {
            "is_qr_aggregator": True,
            "dispute_reason": reason,
            "opened_by": opener,
            "opened_by_id": opener_id
        }
    }
    
    await db.unified_conversations.insert_one(conversation)
    return conversation
