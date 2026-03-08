"""
Offers routes - P2P trading offers management
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import List, Optional
import uuid

from core.database import db
from core.auth import require_role
from models.schemas import OfferCreate, OfferResponse

router = APIRouter(tags=["offers"])


def _payment_detail_to_requisite(detail: dict) -> dict:
    """Convert payment_details document to legacy requisites shape {id, type, data: {...}} used by frontend."""
    pt = detail.get("payment_type") or detail.get("type")
    req_type = pt
    data = {}

    if pt in ("card", "sng_card"):
        req_type = "card"
        holder = detail.get("holder_name")
        data = {
            "bank_name": detail.get("bank_name"),
            "card_number": detail.get("card_number"),
            "holder_name": holder,
            "card_holder": holder,
        }
    elif pt in ("sbp", "sng_sbp"):
        req_type = "sbp"
        data = {
            "bank_name": detail.get("bank_name"),
            "phone": detail.get("phone_number"),
        }
    elif pt == "sim":
        req_type = "sim"
        data = {
            "operator": detail.get("operator_name") or detail.get("bank_name"),
            "phone": detail.get("phone_number"),
        }
    elif pt == "qr_code":
        req_type = "qr"
        data = {
            "bank_name": detail.get("bank_name"),
            "qr_data": detail.get("qr_link") or detail.get("qr_data"),
            "description": detail.get("comment"),
        }
    else:
        req_type = pt or "other"
        data = {
            "bank_name": detail.get("bank_name"),
        }

    clean_data = {k: v for k, v in data.items() if v not in (None, "")}
    return {
        "id": detail.get("id"),
        "trader_id": detail.get("trader_id"),
        "type": req_type,
        "data": clean_data,
    }


def _is_legacy_requisite(item: dict) -> bool:
    """Check if item is already in legacy requisite format {id, type, data: {...}}"""
    return "data" in item and "type" in item and isinstance(item.get("data"), dict)


@router.post("/offers", response_model=OfferResponse)
async def create_offer(data: OfferCreate, user: dict = Depends(require_role(["trader"]))):
    """Create a new P2P offer"""
    trader = await db.traders.find_one({"id": user["id"]}, {"_id": 0})
    
    # Check if balance is locked
    if trader.get("is_balance_locked"):
        raise HTTPException(status_code=403, detail="Ваш баланс заблокирован. Создание объявлений недоступно.")
    
    # Get commission settings
    settings = await db.commission_settings.find_one({}, {"_id": 0})
    commission_rate = settings.get("trader_commission", 1.0) if settings else 1.0
    
    # Calculate reserved commission (1% of offer amount)
    reserved_commission = data.amount_usdt * (commission_rate / 100)
    total_to_reserve = data.amount_usdt + reserved_commission
    
    # Check balance (amount + commission)
    if trader["balance_usdt"] < total_to_reserve:
        raise HTTPException(status_code=400, detail=f"Недостаточно средств. Нужно: {total_to_reserve:.2f} USDT (включая {commission_rate}% комиссии). Баланс: {trader['balance_usdt']:.2f} USDT")
    
    # Validate payment details - load from db.payment_details
    payment_details = []
    payment_detail_ids = data.payment_detail_ids or data.requisite_ids or []
    payment_types_seen = set()
    
    if payment_detail_ids:
        for detail_id in payment_detail_ids:
            detail = await db.payment_details.find_one({"id": detail_id, "trader_id": user["id"]}, {"_id": 0})
            if detail:
                pt = detail.get("payment_type", "")
                if pt in payment_types_seen:
                    raise HTTPException(status_code=400, detail=f"Можно выбрать только один реквизит типа '{pt}'")
                payment_types_seen.add(pt)
                payment_details.append(detail)
    
    # Get trader's trade stats
    trades_count = await db.trades.count_documents({"trader_id": user["id"], "status": "completed"})
    total_trades = await db.trades.count_documents({"trader_id": user["id"]})
    success_rate = (trades_count / total_trades * 100) if total_trades > 0 else 100.0
    
    # Validate min/max amounts
    min_amount = data.min_amount if data.min_amount else 1.0
    max_amount = data.max_amount if data.max_amount else data.amount_usdt
    
    if min_amount < 1.0:
        raise HTTPException(status_code=400, detail="Минимальная сумма не может быть меньше 1 USDT")
    if max_amount > data.amount_usdt:
        raise HTTPException(status_code=400, detail="Максимальная сумма не может превышать сумму к продаже")
    if min_amount > max_amount:
        raise HTTPException(status_code=400, detail="Минимальная сумма не может превышать максимальную")
    
    # Convert payment_details to legacy requisite format for frontend compatibility
    requisites_legacy = [_payment_detail_to_requisite(d) for d in payment_details]
    
    offer_doc = {
        "id": str(uuid.uuid4()),
        "trader_id": user["id"],
        "trader_login": trader["login"],
        "type": "sell",  # Трейдер продаёт USDT за рубли
        "amount_usdt": data.amount_usdt,
        "available_usdt": data.amount_usdt,
        "min_amount": min_amount,
        "max_amount": max_amount,
        "price_rub": data.price_rub,
        "payment_methods": data.payment_methods,
        "payment_detail_ids": payment_detail_ids,
        "requisite_ids": payment_detail_ids,
        "payment_details": payment_details,
        "requisites": requisites_legacy,
        "conditions": data.conditions,
        "is_active": True,
        "trades_count": trades_count,
        "success_rate": round(success_rate, 1),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "commission_rate": commission_rate,
        "reserved_commission": round(reserved_commission, 4),
        "sold_usdt": 0.0,
        "actual_commission": 0.0
    }
    
    # Reserve funds from trader balance
    await db.traders.update_one(
        {"id": user["id"]},
        {"$inc": {"balance_usdt": -total_to_reserve}}
    )
    
    await db.offers.insert_one(offer_doc)
    return offer_doc


def _normalize_offer(offer: dict) -> dict:
    """Ensure offer has all required fields with sensible defaults"""
    # Handle amount fields
    if "amount_usdt" not in offer:
        offer["amount_usdt"] = offer.get("max_amount", 0)
    if "available_usdt" not in offer:
        offer["available_usdt"] = offer.get("max_amount", 0)
    if "min_amount" not in offer:
        offer["min_amount"] = 1.0
    if "max_amount" not in offer:
        offer["max_amount"] = offer.get("amount_usdt", 0)
    if "price_rub" not in offer:
        offer["price_rub"] = 0.0
    
    # Handle trader_login - try to load from trader collection if missing
    if not offer.get("trader_login"):
        offer["trader_login"] = ""  # Will be populated by caller if needed
    
    # Handle payment_methods - ensure it's always a list
    if not offer.get("payment_methods"):
        offer["payment_methods"] = []
    elif not isinstance(offer["payment_methods"], list):
        offer["payment_methods"] = [offer["payment_methods"]]
    
    # Synchronize is_active and status fields
    # Use is_active as the source of truth if present, otherwise derive from status
    if "is_active" not in offer:
        status = offer.get("status", "")
        offer["is_active"] = status == "active"
    
    # Ensure created_at exists
    if not offer.get("created_at"):
        offer["created_at"] = datetime.now(timezone.utc).isoformat()
    
    # Clean _id from embedded payment_details/requisites
    if offer.get("payment_details"):
        offer["payment_details"] = [{k: v for k, v in d.items() if k != "_id"} for d in offer["payment_details"]]
    if offer.get("requisites"):
        offer["requisites"] = [{k: v for k, v in req.items() if k != "_id"} for req in offer["requisites"]]
    
    return offer


async def _load_payment_details_for_offer(offer: dict) -> dict:
    """Load payment details from db.payment_details for an offer and ensure legacy requisites format."""
    detail_ids = offer.get("payment_detail_ids") or offer.get("requisite_ids") or []
    if detail_ids:
        details = []
        for did in detail_ids:
            d = await db.payment_details.find_one({"id": did}, {"_id": 0})
            if d:
                details.append(d)
        if details:
            offer["payment_details"] = details
            # Always rebuild requisites in legacy format from fresh payment_details
            offer["requisites"] = [_payment_detail_to_requisite(d) for d in details]
            offer["requisite_ids"] = detail_ids
    else:
        # Check if existing requisites are in legacy format already
        existing_reqs = offer.get("requisites") or []
        if existing_reqs and not _is_legacy_requisite(existing_reqs[0]):
            # They look like raw payment_details, convert them
            offer["requisites"] = [_payment_detail_to_requisite(d) for d in existing_reqs]
    return offer


@router.get("/offers", response_model=List[OfferResponse])
async def get_offers(
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    payment_method: Optional[str] = None,
    sort_by: Optional[str] = "price"
):
    """Get active offers with filters"""
    query = {"is_active": True, "available_usdt": {"$gt": 0}}
    
    if payment_method:
        query["payment_methods"] = payment_method
    
    if min_amount:
        query["available_usdt"] = {"$gte": min_amount}
    if max_amount:
        if "available_usdt" in query:
            query["available_usdt"]["$lte"] = max_amount
        else:
            query["available_usdt"] = {"$lte": max_amount}
    
    sort_field = "price_rub"
    sort_order = 1
    if sort_by == "amount":
        sort_field = "available_usdt"
        sort_order = -1
    elif sort_by == "rating":
        sort_field = "success_rate"
        sort_order = -1
    
    offers = await db.offers.find(query, {"_id": 0}).sort(sort_field, sort_order).to_list(100)
    
    for offer in offers:
        # Load payment details from db.payment_details
        offer = await _load_payment_details_for_offer(offer)
        offer = _normalize_offer(offer)
        
        # Add online status
        trader = await db.traders.find_one({"id": offer.get("trader_id")}, {"_id": 0, "last_seen": 1})
        if trader and trader.get("last_seen"):
            try:
                last_seen = datetime.fromisoformat(trader["last_seen"].replace("Z", "+00:00"))
                diff_minutes = (datetime.now(timezone.utc) - last_seen).total_seconds() / 60
                offer["is_online"] = diff_minutes < 5
            except:
                offer["is_online"] = False
        else:
            offer["is_online"] = False
    
    return offers


@router.get("/offers/my", response_model=List[OfferResponse])
async def get_my_offers(user: dict = Depends(require_role(["trader"]))):
    """Get current trader's offers"""
    offers = await db.offers.find({"trader_id": user["id"]}, {"_id": 0}).to_list(100)
    
    # Get trader's login for fallback
    trader = await db.traders.find_one({"id": user["id"]}, {"_id": 0, "login": 1})
    trader_login = trader.get("login", "") if trader else ""
    
    result = []
    for offer in offers:
        offer = await _load_payment_details_for_offer(offer)
        offer = _normalize_offer(offer)
        
        # Ensure trader_login is set
        if not offer.get("trader_login"):
            offer["trader_login"] = trader_login
        
        result.append(offer)
    return result


@router.get("/public/offers")
async def get_public_offers(
    payment_method: Optional[str] = None,
    currency: Optional[str] = "RUB",
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    sort_by: Optional[str] = "price"
):
    """Public order book endpoint - no auth required"""
    query = {
        "is_active": True, 
        "available_usdt": {"$gt": 0},
        "paused_by_trader": {"$ne": True},  # Hide paused by trader
        "paused_by_admin": {"$ne": True}    # Hide paused by admin
    }
    
    if payment_method and payment_method != "all":
        query["payment_methods"] = payment_method
    
    if min_amount:
        query["available_usdt"] = {"$gte": min_amount}
    if max_amount:
        if "available_usdt" in query:
            query["available_usdt"]["$lte"] = max_amount
        else:
            query["available_usdt"] = {"$lte": max_amount}
    
    sort_field = "price_rub"
    sort_order = 1
    if sort_by == "amount":
        sort_field = "available_usdt"
        sort_order = -1
    elif sort_by == "rating":
        sort_field = "success_rate"
        sort_order = -1
    
    offers = await db.offers.find(query, {"_id": 0}).sort(sort_field, sort_order).to_list(100)
    
    for offer in offers:
        # Load payment details from db.payment_details and convert to legacy format
        offer = await _load_payment_details_for_offer(offer)
        offer = _normalize_offer(offer)
        
        # Add trader info
        trader = await db.traders.find_one({"id": offer.get("trader_id")}, {"_id": 0, "last_seen": 1, "display_name": 1, "login": 1})
        if trader:
            offer["trader_display_name"] = trader.get("display_name") or offer.get("trader_login", "")
            if trader.get("last_seen"):
                try:
                    last_seen = datetime.fromisoformat(trader["last_seen"].replace("Z", "+00:00"))
                    diff_minutes = (datetime.now(timezone.utc) - last_seen).total_seconds() / 60
                    offer["is_online"] = diff_minutes < 5
                except:
                    offer["is_online"] = False
            else:
                offer["is_online"] = False
        else:
            offer["trader_display_name"] = offer.get("trader_login", "")
            offer["is_online"] = False
    
    # === Add QR aggregator providers to order book ===
    try:
        qr_settings = await db.qr_aggregator_settings.find_one({"type": "main"}, {"_id": 0})
        if qr_settings and qr_settings.get("is_enabled", True):
            # Fetch exchange rate for QR pricing
            _payout_settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
            exchange_rate = _payout_settings.get("base_rate", 78.0) if _payout_settings else 78.0
            if not exchange_rate or exchange_rate <= 0:
                _comm = await db.commission_settings.find_one({}, {"_id": 0})
                exchange_rate = _comm.get("default_price_rub", 78.0) if _comm else 78.0
            
            qr_providers = await db.qr_providers.find({"is_active": True, "balance_usdt": {"$gt": 0}}, {"_id": 0}).to_list(50)
            
            # Auto-hide: skip QR offers if total available balance < 20 USDT
            _total_available = sum(p.get("balance_usdt", 0) - p.get("frozen_usdt", 0) for p in qr_providers)
            if _total_available < 20.0:
                qr_providers = []  # Hide all QR offers
            
            for qrp in qr_providers:
                available_balance = qrp.get("balance_usdt", 0) - qrp.get("frozen_usdt", 0)
                if available_balance <= 0:
                    continue
                
                # Check online status
                is_online = False
                if qrp.get("last_seen"):
                    try:
                        last_seen = datetime.fromisoformat(str(qrp["last_seen"]).replace("Z", "+00:00"))
                        diff_minutes = (datetime.now(timezone.utc) - last_seen).total_seconds() / 60
                        is_online = diff_minutes < 5
                    except:
                        pass
                
                display_name = qrp.get("display_name") or qrp.get("login", "QR Provider")
                
                for method_key in ["qr", "sng"]:
                    tg_method = "nspk" if method_key == "qr" else "transgrant"
                    if not qrp.get(f"{tg_method}_enabled", False):
                        continue
                    
                    provider_markup = qrp.get(f"{tg_method}_commission_percent", 5.0)
                    platform_markup = qr_settings.get(f"{tg_method}_commission_percent", 5.0)
                    provider_price_rub = round(exchange_rate * (1 + provider_markup / 100) * (1 + platform_markup / 100), 2)
                    
                    if method_key == "qr":
                        method_label = "QR"
                        method_name = "СБП (QR-код)"
                        req_type = "qr_code"
                        pm_type = "qr_code"
                    else:
                        method_label = "СНГ"
                        method_name = "Банковская карта"
                        req_type = "card"
                        pm_type = "card"
                    
                    min_amt = qr_settings.get(f"{tg_method}_min_amount", 100)
                    max_amt = qr_settings.get(f"{tg_method}_max_amount", 100000)
                    min_usdt = round(min_amt / provider_price_rub, 2) if provider_price_rub > 0 else 1
                    max_usdt = min(round(max_amt / provider_price_rub, 2), available_balance)
                    
                    if payment_method and payment_method != "all":
                        if payment_method != pm_type:
                            continue
                    
                    qr_offer = {
                        "id": f"qr_provider_{qrp['id']}_{method_key}",
                        "offer_id": f"qr_provider_{qrp['id']}_{method_key}",
                        "trader_id": qrp["id"],
                        "trader_login": qrp.get("login", ""),
                        "trader_display_name": f"{display_name} ({method_label})",
                        "type": "sell",
                        "price_rub": provider_price_rub,
                        "available_usdt": round(available_balance, 2),
                        "min_amount": min_usdt,
                        "max_amount": max_usdt,
                        "payment_methods": [pm_type],
                        "requisites": [{"id": f"qr_{qrp['id']}_{method_key}", "type": req_type, "data": {"bank_name": method_name, "phone": "Автоматический" if method_key == "qr" else "", "card_number": "" if method_key == "sng" else ""}}],
                        "is_active": True,
                        "is_online": is_online,
                        "success_rate": qrp.get("success_rate", 100),
                        "trades_count": qrp.get("total_operations", 0),
                        "is_qr_aggregator": True,
                        "qr_provider_id": qrp["id"],
                        "qr_method": method_key,
                        "conditions": f"Автоматическая оплата через {method_name}",
                    }
                    offers.append(qr_offer)
    except Exception as e:
        import traceback
        traceback.print_exc()
    
    # Re-sort after adding QR providers
    if sort_by == "price" or sort_field == "price_rub":
        offers.sort(key=lambda x: x.get("price_rub", 0))
    elif sort_by == "amount":
        offers.sort(key=lambda x: x.get("available_usdt", 0), reverse=True)
    elif sort_by == "rating":
        offers.sort(key=lambda x: x.get("success_rate", 0), reverse=True)
    
    return offers



@router.get("/public/operators")
async def get_operators_for_payment(
    payment_method: Optional[str] = None,
    amount_rub: Optional[float] = None,
    amount_usdt: Optional[float] = None,
    currency: str = "RUB"
):
    """
    Получить список операторов (трейдеров) для оплаты.
    Покупатель видит список доступных трейдеров с офферами и выбирает одного.
    
    Parameters:
    - payment_method: фильтр по методу оплаты (необязательно)
    - amount_rub: сумма в рублях
    - amount_usdt: или сумма в USDT
    """
    # Получаем текущий курс из Rapira API (хранится в payout_settings)
    payout_settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    exchange_rate = payout_settings.get("base_rate", 78.0) if payout_settings else 78.0
    # Фоллбэк на commission_settings если payout_settings пуст
    if not exchange_rate or exchange_rate <= 0:
        comm_settings = await db.commission_settings.find_one({}, {"_id": 0})
        exchange_rate = comm_settings.get("default_price_rub", 78.0) if comm_settings else 78.0
    
    # Определяем сумму в USDT для фильтрации по лимитам оффера
    if amount_usdt:
        filter_amount_usdt = amount_usdt
        filter_amount_rub = amount_usdt * exchange_rate
    elif amount_rub:
        filter_amount_rub = amount_rub
        filter_amount_usdt = amount_rub / exchange_rate
    else:
        filter_amount_rub = 0
        filter_amount_usdt = 0
    
    # Базовый запрос - СТРОГАЯ проверка активных офферов
    query = {
        "type": "sell",                           # Только продажа
        "is_active": True,                        # Объявление активно
        "paused_by_trader": {"$ne": True},        # НЕ на паузе
        "available_usdt": {"$gt": 0}              # Есть доступный баланс
    }
    
    # Фильтр по методу оплаты
    if payment_method and payment_method != "all":
        query["payment_methods"] = payment_method
    
    # Фильтр по лимитам (если указана сумма)
    if filter_amount_usdt > 0:
        query["min_amount"] = {"$lte": filter_amount_usdt}
        query["$or"] = [
            {"max_amount": {"$gte": filter_amount_usdt}},
            {"available_usdt": {"$gte": filter_amount_usdt}}
        ]
    
    offers = await db.offers.find(query, {"_id": 0}).sort("price_rub", 1).to_list(100)
    
    operators = []
    
    for offer in offers:
        trader_id = offer.get("trader_id")
        
        # Получаем информацию о трейдере
        trader = await db.traders.find_one(
            {"id": trader_id},
            {"_id": 0, "password_hash": 0, "password": 0}
        )
        
        if not trader:
            continue
        
        # Пропускаем заблокированных/неактивных трейдеров
        trader_status = trader.get("status", "active")
        if trader_status not in [None, "active"]:
            continue
        
        # Пропускаем если трейдер заблокирован
        if trader.get("is_blocked") or trader.get("blocked"):
            continue
        
        # Проверяем что у оффера достаточно USDT для запрошенной суммы
        available = offer.get("available_usdt", 0)
        if filter_amount_usdt > 0 and available < filter_amount_usdt * 0.99:  # 1% погрешность
            continue
        
        # Проверяем лимиты оффера
        min_amt = offer.get("min_amount", 0)
        max_amt = offer.get("max_amount", float('inf'))
        if filter_amount_usdt > 0:
            if filter_amount_usdt < min_amt:
                continue
            if max_amt and filter_amount_usdt > max_amt and filter_amount_usdt > available:
                continue
        
        # (no per-trader dedup — show all matching offers)
        
        # Проверяем онлайн статус
        is_online = False
        if trader.get("last_seen"):
            try:
                last_seen = datetime.fromisoformat(trader["last_seen"].replace("Z", "+00:00"))
                diff_minutes = (datetime.now(timezone.utc) - last_seen).total_seconds() / 60
                is_online = diff_minutes < 5
            except:
                pass
        
        # Получаем реквизиты в legacy формате
        requisites = offer.get("requisites", [])
        # Check if requisites are already in legacy format
        if requisites and not _is_legacy_requisite(requisites[0]):
            requisites = [_payment_detail_to_requisite(r) for r in requisites]
        
        # Если реквизитов нет в оффере, подгружаем из БД
        if not requisites:
            detail_ids = offer.get("payment_detail_ids") or offer.get("requisite_ids") or []
            details = []
            for did in detail_ids:
                d = await db.payment_details.find_one({"id": did}, {"_id": 0})
                if d:
                    details.append(d)
            if details:
                requisites = [_payment_detail_to_requisite(d) for d in details]
        
        # Убираем _id из реквизитов
        requisites = [{k: v for k, v in req.items() if k != "_id"} for req in requisites]
        
        # Статистика трейдера
        trades_count = offer.get("trades_count", 0)
        success_rate = offer.get("success_rate", 100.0)
        
        # Рассчитываем сумму к оплате трейдеру
        # Логика: клиент хочет пополнить X руб -> amount_usdt = X / базовый_курс
        # Трейдер продаёт по своему курсу -> к_оплате = amount_usdt * курс_трейдера
        # Пример: 7800₽ / 78(база) = 100 USDT * 100(трейдер) = 10,000₽ к оплате
        offer_price_rub = offer.get("price_rub", exchange_rate)
        if filter_amount_rub > 0:
            filter_amount_usdt = filter_amount_rub / exchange_rate
            amount_to_pay_rub = round(filter_amount_usdt * offer_price_rub, 2)
        else:
            amount_to_pay_rub = 0
        
        operators.append({
            "trader_id": trader_id,
            "offer_id": offer["id"],
            "trader_login": trader.get("login", ""),
            "nickname": trader.get("nickname") or trader.get("display_name") or trader.get("login", "Оператор"),
            "is_online": is_online,
            "trades_count": trades_count,
            "success_rate": success_rate,
            "price_rub": offer_price_rub,
            "min_amount": offer.get("min_amount", 1),
            "max_amount": min(offer.get("max_amount", 100000), offer.get("available_usdt", 100000)),
            "available_usdt": offer.get("available_usdt", 0),
            "payment_methods": offer.get("payment_methods", []),
            "requisites": requisites,
            "payment_details": requisites,
            "requisite_ids": offer.get("payment_detail_ids") or offer.get("requisite_ids", []),
            "payment_detail_ids": offer.get("payment_detail_ids") or offer.get("requisite_ids", []),
            "conditions": offer.get("conditions", ""),
            "amount_to_pay_rub": amount_to_pay_rub
        })
    
    # ===== Добавляем QR-агрегатор провайдеров (каждый метод = отдельное объявление) =====
    try:
        # Загружаем настройки платформы для комиссий
        qr_settings = await db.qr_aggregator_settings.find_one({"type": "main"}, {"_id": 0}) or {}
        platform_nspk_percent = qr_settings.get("nspk_commission_percent", 5.5)
        platform_transgrant_percent = qr_settings.get("transgrant_commission_percent", 5.0)
        
        qr_query = {"is_active": True}
        qr_providers = await db.qr_providers.find(qr_query, {"_id": 0, "password_hash": 0, "password": 0}).to_list(20)
        
        # Auto-hide: skip QR offers if total available balance < 20 USDT
        _total_available_ops = sum(p.get("balance_usdt", 0) - p.get("frozen_usdt", 0) for p in qr_providers)
        if _total_available_ops < 20.0:
            qr_providers = []  # Hide all QR offers from payment page
        
        for qrp in qr_providers:
            if not qrp.get("is_active"):
                continue
            balance = qrp.get("balance_usdt", 0) or 0
            if balance <= 0:
                continue
            
            methods = qrp.get("methods", {})
            if not methods:
                continue
            
            # Онлайн статус (общий для всех методов провайдера)
            is_online = False
            if qrp.get("last_seen"):
                try:
                    last_seen = datetime.fromisoformat(str(qrp["last_seen"]).replace("Z", "+00:00"))
                    diff_minutes = (datetime.now(timezone.utc) - last_seen).total_seconds() / 60
                    is_online = diff_minutes < 15
                except:
                    pass
            if qrp.get("api_available") or qrp.get("nspk_api_available") or qrp.get("transgrant_api_available"):
                is_online = True
            
            # Каждый включённый метод = отдельное объявление в стакане
            for method_key, method_cfg in methods.items():
                if not method_cfg.get("enabled"):
                    continue
                
                min_amt = method_cfg.get("min_amount", 0)
                max_amt = method_cfg.get("max_amount", 1000000)
                
                # Проверяем лимиты суммы
                if filter_amount_rub > 0:
                    if filter_amount_rub < min_amt or filter_amount_rub > max_amt:
                        continue
                
                # Проверяем баланс USDT
                if filter_amount_usdt > 0 and balance < filter_amount_usdt * 0.99:
                    continue
                
                # Рассчитываем РЕАЛЬНУЮ цену с наценками провайдера И платформы
                # QR/NSPK: курс × (1 + провайдер%) × (1 + платформа%)
                # СНГ/TransGrant: курс × (1 + провайдер%) × (1 + платформа%)
                if method_key == "qr":
                    provider_markup = qrp.get("nspk_commission_percent", 12.5) / 100
                    platform_markup = platform_nspk_percent / 100
                elif method_key == "sng":
                    provider_markup = qrp.get("transgrant_commission_percent", 10.0) / 100
                    platform_markup = platform_transgrant_percent / 100
                else:
                    provider_markup = method_cfg.get("markup_percent", 0) / 100
                    platform_markup = 0
                
                # Курс для клиента = базовый × (1 + провайдер) × (1 + платформа)
                provider_price_rub = round(exchange_rate * (1 + provider_markup) * (1 + platform_markup), 2)
                if filter_amount_rub > 0:
                    amount_to_pay = round(filter_amount_rub * (1 + provider_markup) * (1 + platform_markup), 2)
                else:
                    amount_to_pay = 0
                
                # Определяем название и тип для метода
                if method_key == "qr":
                    method_name = "СБП (QR-код)"
                    method_label = "QR"
                    req_type = "qr_code"
                elif method_key == "sng":
                    method_name = "Банковская карта"
                    method_label = "СНГ"
                    req_type = "card"
                else:
                    method_name = method_key
                    method_label = method_key.upper()
                    req_type = "sbp"
                
                requisite = {
                    "id": f"qr_{qrp['id']}_{method_key}",
                    "type": req_type,
                    "data": {"bank_name": method_name, "phone": "Автоматический"},
                    "is_qr_aggregator": True,
                    "qr_method": method_key
                }
                
                display_name = qrp.get("display_name") or qrp.get("login", "QR Оператор")
                
                operators.append({
                    "trader_id": qrp["id"],
                    "offer_id": f"qr_provider_{qrp['id']}_{method_key}",
                    "trader_login": qrp.get("login", ""),
                    "nickname": f"{display_name} ({method_label})",
                    "is_online": is_online,
                    "trades_count": qrp.get("total_operations", 0),
                    "success_rate": qrp.get("success_rate", 100),
                    "price_rub": round(provider_price_rub, 2),
                    "min_amount": min_amt,
                    "max_amount": min(max_amt, balance * exchange_rate),
                    "available_usdt": balance,
                    "payment_methods": [req_type],
                    "requisites": [requisite],
                    "payment_details": [requisite],
                    "requisite_ids": [requisite["id"]],
                    "payment_detail_ids": [requisite["id"]],
                    "conditions": f"Автоматическая оплата через {method_name}",
                    "amount_to_pay_rub": amount_to_pay,
                    "is_qr_aggregator": True,
                    "qr_provider_id": qrp["id"],
                    "qr_method": method_key
                })
    except Exception as e:
        import traceback
        traceback.print_exc()
    
    # Сортируем: онлайн вверху, потом по рейтингу
    operators.sort(key=lambda x: (-int(x["is_online"]), -x["success_rate"], x["price_rub"]))
    
    return {
        "operators": operators,
        "exchange_rate": exchange_rate,
        "amount_rub": filter_amount_rub,
        "amount_usdt": round(filter_amount_usdt, 4),
        "payment_method": payment_method,
        "total_operators": len(operators)
    }



@router.delete("/offers/{offer_id}")
async def delete_offer(offer_id: str, user: dict = Depends(require_role(["trader"]))):
    """Delete an offer permanently and refund unused funds"""
    offer = await db.offers.find_one({"id": offer_id}, {"_id": 0})
    if not offer:
        raise HTTPException(status_code=404, detail="Объявление не найдено")
    if offer["trader_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Это не ваше объявление")
    
    # Check for active trades - any status except completed and cancelled
    active_trades = await db.trades.count_documents({
        "offer_id": offer_id,
        "status": {"$nin": ["completed", "cancelled"]}
    })
    
    if active_trades > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Невозможно удалить объявление: есть {active_trades} незавершённых сделок. Дождитесь завершения или отмены всех сделок."
        )
    
    # Calculate refund
    available_usdt = offer.get("available_usdt", 0)
    reserved_commission = offer.get("reserved_commission", 0)
    sold_usdt = offer.get("sold_usdt", 0)
    commission_rate = offer.get("commission_rate", 1.0)
    
    correct_commission = sold_usdt * (commission_rate / 100)
    commission_refund = reserved_commission - correct_commission
    total_refund = available_usdt + max(0, commission_refund)
    
    if total_refund > 0:
        await db.traders.update_one(
            {"id": user["id"]},
            {"$inc": {"balance_usdt": total_refund}}
        )
    
    # ПОЛНОСТЬЮ УДАЛЯЕМ объявление из базы данных
    await db.offers.delete_one({"id": offer_id})
    
    return {
        "status": "deleted",
        "returned_usdt": round(available_usdt, 4),
        "commission_refund": round(max(0, commission_refund), 4),
        "total_refund": round(total_refund, 4),
        "sold_usdt": round(sold_usdt, 4),
        "actual_commission_paid": round(correct_commission, 4)
    }


@router.patch("/offers/{offer_id}/pause")
async def pause_offer(offer_id: str, user: dict = Depends(require_role(["trader"]))):
    """Pause an offer - hide from public order book"""
    offer = await db.offers.find_one({"id": offer_id}, {"_id": 0})
    if not offer:
        raise HTTPException(status_code=404, detail="Объявление не найдено")
    if offer["trader_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Это не ваше объявление")
    
    if offer.get("paused_by_trader"):
        raise HTTPException(status_code=400, detail="Объявление уже на паузе")
    
    await db.offers.update_one(
        {"id": offer_id},
        {"$set": {"paused_by_trader": True, "paused_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"status": "paused", "message": "Объявление поставлено на паузу"}


@router.patch("/offers/{offer_id}/resume")
async def resume_offer(offer_id: str, user: dict = Depends(require_role(["trader"]))):
    """Resume a paused offer - show in public order book"""
    offer = await db.offers.find_one({"id": offer_id}, {"_id": 0})
    if not offer:
        raise HTTPException(status_code=404, detail="Объявление не найдено")
    if offer["trader_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Это не ваше объявление")
    
    if offer.get("paused_by_admin"):
        raise HTTPException(status_code=400, detail="Объявление приостановлено модератором. Обратитесь в поддержку.")
    
    if not offer.get("paused_by_trader"):
        raise HTTPException(status_code=400, detail="Объявление не на паузе")
    
    await db.offers.update_one(
        {"id": offer_id},
        {"$set": {"paused_by_trader": False}, "$unset": {"paused_at": ""}}
    )
    
    return {"status": "resumed", "message": "Объявление возобновлено"}


@router.get("/offers/{offer_id}/trades")
async def get_offer_trades(offer_id: str, user: dict = Depends(require_role(["trader"]))):
    """Get all trades for a specific offer"""
    offer = await db.offers.find_one({"id": offer_id}, {"_id": 0})
    if not offer:
        raise HTTPException(status_code=404, detail="Объявление не найдено")
    if offer["trader_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Это не ваше объявление")
    
    trades = await db.trades.find(
        {"offer_id": offer_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    # Get summary
    total = len(trades)
    completed = len([t for t in trades if t.get("status") == "completed"])
    cancelled = len([t for t in trades if t.get("status") == "cancelled"])
    active = total - completed - cancelled
    
    return {
        "offer_id": offer_id,
        "summary": {
            "total": total,
            "completed": completed,
            "cancelled": cancelled,
            "active": active
        },
        "trades": trades
    }

