from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import Optional

from core.database import db
from core.auth import require_role, require_admin_level
from .utils import get_date_range

router = APIRouter()

# ==================== ADMIN: DASHBOARD STATS ====================

@router.get("/admin/dashboard/stats")
async def get_admin_dashboard_stats(user: dict = Depends(require_admin_level(30))):
    """Get comprehensive dashboard statistics"""
    # Count users
    traders_count = await db.traders.count_documents({})
    merchants_count = await db.merchants.count_documents({})
    pending_merchants = await db.merchants.count_documents({"status": "pending"})
    
    # Count trades
    total_trades = await db.trades.count_documents({})
    completed_trades = await db.trades.count_documents({"status": "completed"})
    active_trades = await db.trades.count_documents({"status": {"$in": ["pending", "paid"]}})
    disputed_trades = await db.trades.count_documents({"status": "disputed"})
    
    # Count offers
    active_offers = await db.offers.count_documents({"is_active": True})
    
    # Calculate volumes
    completed_trades_list = await db.trades.find({"status": "completed"}, {"_id": 0, "amount_usdt": 1, "amount_rub": 1}).to_list(10000)
    total_volume_usdt = sum([t.get("amount_usdt", 0) for t in completed_trades_list])
    total_volume_rub = sum([t.get("amount_rub", 0) for t in completed_trades_list])
    
    # Platform earnings (commissions)
    settings = await db.commission_settings.find_one({}, {"_id": 0})
    
    # Shops and products
    shops_count = await db.shops.count_documents({})
    products_count = await db.products.count_documents({})
    
    # Today's stats
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    trades_today = await db.trades.count_documents({"created_at": {"$gte": today_start.isoformat()}})
    new_users_today = await db.traders.count_documents({"created_at": {"$gte": today_start.isoformat()}})
    
    return {
        "users": {
            "traders": traders_count,
            "merchants": merchants_count,
            "pending_merchants": pending_merchants
        },
        "trades": {
            "total": total_trades,
            "completed": completed_trades,
            "active": active_trades,
            "disputed": disputed_trades,
            "today": trades_today
        },
        "volume": {
            "usdt": total_volume_usdt,
            "rub": total_volume_rub
        },
        "offers": {
            "active": active_offers
        },
        "marketplace": {
            "shops": shops_count,
            "products": products_count
        },
        "today": {
            "trades": trades_today,
            "new_users": new_users_today
        },
        "settings": settings
    }


# ==================== ADMIN: ANALYTICS ====================

@router.get("/admin/analytics")
async def get_analytics(period: str = "week", user: dict = Depends(require_role(["admin"]))):
    """Get analytics for period (day, week, month)"""
    start_str, _ = get_date_range(period)
    
    # Get completed trades in period
    trades = await db.trades.find(
        {"created_at": {"$gte": start_str}, "status": "completed"},
        {"_id": 0}
    ).to_list(100000)
    
    total_volume = sum(t.get("amount_usdt", 0) for t in trades)
    total_trades = len(trades)
    
    # Get base rate from Rapira API settings
    rate_settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
    base_rate = rate_settings.get("base_rate", 78) if rate_settings else 78
    
    # Commission calculation: avoid double-counting
    # Regular (non-QR) trades: platform_fee_rub converted to USDT
    # QR trades: platform_receives_usdt (already in USDT, includes markup + merchant fee)
    total_platform_fee_rub = sum(
        t.get("platform_fee_rub", 0) or 0
        for t in trades if not t.get("qr_aggregator_trade")
    )
    total_commission_from_rub = total_platform_fee_rub / base_rate if base_rate > 0 else 0
    total_qr_commission_usdt = sum(
        t.get("platform_receives_usdt", 0) or 0
        for t in trades if t.get("qr_aggregator_trade")
    )
    total_commission_usdt = total_commission_from_rub + total_qr_commission_usdt
    
    total_turnover_rub = sum(t.get("client_amount_rub", 0) or t.get("amount_rub", 0) for t in trades)
    
    # Volume by day
    volume_by_day = {}
    for trade in trades:
        day = trade["created_at"][:10]
        volume_by_day[day] = volume_by_day.get(day, 0) + trade.get("amount_usdt", 0)
    
    # Top traders
    trader_volumes = {}
    for trade in trades:
        tid = trade["trader_id"]
        trader_volumes[tid] = trader_volumes.get(tid, 0) + trade.get("amount_usdt", 0)
    
    top_traders = sorted(trader_volumes.items(), key=lambda x: x[1], reverse=True)[:10]
    top_traders_data = []
    for tid, vol in top_traders:
        trader = await db.traders.find_one({"id": tid}, {"_id": 0})
        if trader:
            top_traders_data.append({"login": trader["login"], "volume": round(vol, 2)})
    
    return {
        "period": period,
        "total_volume": round(total_volume, 2),
        "total_trades": total_trades,
        "total_commission": round(total_commission_usdt, 4),
        "total_turnover_rub": round(total_turnover_rub, 2),
        "avg_trade_size": round(total_volume / total_trades, 2) if total_trades > 0 else 0,
        "volume_by_day": volume_by_day,
        "top_traders": top_traders_data
    }


# ==================== ADMIN: ACCOUNTING (Бухгалтерия) ====================

@router.get("/admin/accounting")
async def get_accounting(
    period: str = "month",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user: dict = Depends(require_role(["admin"]))
):
    """
    Бухгалтерия — comprehensive income analytics for the platform.
    
    Returns breakdown of all platform income sources:
    1. QR Aggregator (platform markup commission)
    2. Trader commissions (1% from P2P trades)
    3. Merchant commissions (variable % from merchant trades)
    4. Withdrawal fees (1 USDT per withdrawal)
    5. Marketplace commissions (shop/guarantor fees)
    """
    try:
        import logging
        logger = logging.getLogger(__name__)
        start_str, end_str = get_date_range(period, date_from, date_to)

        # Get base rate for RUB -> USDT conversion
        rate_settings = await db.settings.find_one({"type": "payout_settings"}, {"_id": 0})
        base_rate = rate_settings.get("base_rate", 78) if rate_settings else 78

        # ---- 1. Completed trades in period ----
        trade_filter = {
            "status": "completed",
            "completed_at": {"$gte": start_str, "$lte": end_str}
        }
        trades = await db.trades.find(trade_filter, {"_id": 0}).to_list(100000)

        # Fallback: if no completed_at, try created_at
        if not trades:
            trade_filter_fallback = {
                "status": "completed",
                "created_at": {"$gte": start_str, "$lte": end_str}
            }
            trades = await db.trades.find(trade_filter_fallback, {"_id": 0}).to_list(100000)

        # Categorize trades
        qr_trades = [t for t in trades if t.get("qr_aggregator_trade")]
        qr_merchant_trades = [t for t in qr_trades if t.get("merchant_id")]
        qr_exchange_trades = [t for t in qr_trades if not t.get("merchant_id")]
        regular_trades = [t for t in trades if not t.get("qr_aggregator_trade")]
        regular_merchant_trades = [t for t in regular_trades if t.get("merchant_id")]
        regular_p2p_trades = [t for t in regular_trades if not t.get("merchant_id")]

        # ---- 2. QR Aggregator income ----
        # Platform markup commission (platform_commission_usdt) on ALL QR trades
        qr_platform_markup = sum(t.get("platform_commission_usdt", 0) or 0 for t in qr_trades)
        # Merchant commission on QR merchant trades
        qr_merchant_commission = sum(t.get("merchant_commission_usdt", 0) or t.get("merchant_commission", 0) or 0 for t in qr_merchant_trades)
        qr_total_income = round(qr_platform_markup + qr_merchant_commission, 4)
        qr_volume = sum(t.get("amount_usdt", 0) or 0 for t in qr_trades)

        # QR trades details by provider
        qr_by_provider = {}
        for t in qr_trades:
            pid = t.get("provider_id", "unknown")
            if pid not in qr_by_provider:
                qr_by_provider[pid] = {"count": 0, "volume": 0, "markup": 0, "merchant_fee": 0}
            qr_by_provider[pid]["count"] += 1
            qr_by_provider[pid]["volume"] += t.get("amount_usdt", 0) or 0
            qr_by_provider[pid]["markup"] += t.get("platform_commission_usdt", 0) or 0
            qr_by_provider[pid]["merchant_fee"] += t.get("merchant_commission_usdt", 0) or t.get("merchant_commission", 0) or 0

        qr_providers_details = []
        for pid, data in qr_by_provider.items():
            provider = await db.qr_providers.find_one({"id": pid}, {"_id": 0, "name": 1, "login": 1})
            qr_providers_details.append({
                "provider_id": pid,
                "name": provider.get("name", provider.get("login", pid)) if provider else pid,
                "trades": data["count"],
                "volume_usdt": round(data["volume"], 2),
                "markup_usdt": round(data["markup"], 4),
                "merchant_fee_usdt": round(data["merchant_fee"], 4),
                "total_income": round(data["markup"] + data["merchant_fee"], 4),
            })

        # ---- 3. Trader commissions (P2P trades) ----
        trader_commission_total = sum(t.get("trader_commission", 0) or 0 for t in regular_p2p_trades)
        p2p_volume = sum(t.get("amount_usdt", 0) or 0 for t in regular_p2p_trades)

        # Top traders by commission
        trader_comm_map = {}
        for t in regular_p2p_trades:
            tid = t.get("trader_id", "unknown")
            comm = t.get("trader_commission", 0) or 0
            if tid not in trader_comm_map:
                trader_comm_map[tid] = {"count": 0, "volume": 0, "commission": 0}
            trader_comm_map[tid]["count"] += 1
            trader_comm_map[tid]["volume"] += t.get("amount_usdt", 0) or 0
            trader_comm_map[tid]["commission"] += comm

        top_traders = sorted(trader_comm_map.items(), key=lambda x: x[1]["commission"], reverse=True)[:10]
        top_traders_details = []
        for tid, data in top_traders:
            trader = await db.traders.find_one({"id": tid}, {"_id": 0, "login": 1})
            top_traders_details.append({
                "trader_id": tid,
                "login": trader.get("login", tid) if trader else tid,
                "trades": data["count"],
                "volume_usdt": round(data["volume"], 2),
                "commission_usdt": round(data["commission"], 4),
            })

        # ---- 4. Merchant commissions (regular non-QR merchant trades) ----
        merchant_commission_rub = sum(t.get("platform_fee_rub", 0) or 0 for t in regular_merchant_trades)
        merchant_commission_usdt = merchant_commission_rub / base_rate if base_rate > 0 else 0
        merchant_volume = sum(t.get("amount_usdt", 0) or 0 for t in regular_merchant_trades)

        # Merchant details
        merchant_comm_map = {}
        for t in regular_merchant_trades:
            mid = t.get("merchant_id", "unknown")
            fee_rub = t.get("platform_fee_rub", 0) or 0
            if mid not in merchant_comm_map:
                merchant_comm_map[mid] = {"count": 0, "volume": 0, "fee_rub": 0}
            merchant_comm_map[mid]["count"] += 1
            merchant_comm_map[mid]["volume"] += t.get("amount_usdt", 0) or 0
            merchant_comm_map[mid]["fee_rub"] += fee_rub

        top_merchants = sorted(merchant_comm_map.items(), key=lambda x: x[1]["fee_rub"], reverse=True)[:10]
        top_merchants_details = []
        for mid, data in top_merchants:
            merchant = await db.merchants.find_one({"id": mid}, {"_id": 0, "name": 1, "company_name": 1})
            name = "—"
            if merchant:
                name = merchant.get("company_name") or merchant.get("name") or mid
            fee_usdt = data["fee_rub"] / base_rate if base_rate > 0 else 0
            top_merchants_details.append({
                "merchant_id": mid,
                "name": name,
                "trades": data["count"],
                "volume_usdt": round(data["volume"], 2),
                "commission_rub": round(data["fee_rub"], 2),
                "commission_usdt": round(fee_usdt, 4),
            })

        # ---- 5. Withdrawal fees ----
        withdrawal_filter = {
            "type": "withdrawal_fee",
            "created_at": {"$gte": start_str, "$lte": end_str}
        }
        withdrawal_fees = await db.platform_fees.find(withdrawal_filter, {"_id": 0}).to_list(100000)
        withdrawal_fee_total = sum(f.get("amount", 0) or 0 for f in withdrawal_fees)
        withdrawal_count = len(withdrawal_fees)

        # ---- 6. Marketplace / guarantor commissions ----
        # marketplace_orders with platform commission
        marketplace_filter = {
            "status": "completed",
            "completed_at": {"$gte": start_str, "$lte": end_str}
        }
        marketplace_orders = await db.marketplace_orders.find(marketplace_filter, {"_id": 0}).to_list(100000)
        if not marketplace_orders:
            marketplace_filter_fb = {
                "status": "completed",
                "created_at": {"$gte": start_str, "$lte": end_str}
            }
            marketplace_orders = await db.marketplace_orders.find(marketplace_filter_fb, {"_id": 0}).to_list(100000)
        marketplace_commission = sum(o.get("platform_commission", 0) or o.get("commission", 0) or 0 for o in marketplace_orders)
        marketplace_volume = sum(o.get("amount", 0) or o.get("total", 0) or 0 for o in marketplace_orders)
        marketplace_count = len(marketplace_orders)

        # Guarantor deals commission
        guarantor_filter = {
            "status": {"$in": ["completed", "resolved"]},
            "created_at": {"$gte": start_str, "$lte": end_str}
        }
        guarantor_deals = await db.guarantor_deals.find(guarantor_filter, {"_id": 0}).to_list(100000)
        guarantor_commission = sum(d.get("platform_commission", 0) or d.get("guarantor_fee", 0) or 0 for d in guarantor_deals)
        guarantor_count = len(guarantor_deals)

        marketplace_total = round(marketplace_commission + guarantor_commission, 4)

        # ---- TOTALS ----
        total_income = round(
            qr_total_income +
            trader_commission_total +
            merchant_commission_usdt +
            withdrawal_fee_total +
            marketplace_total,
            4
        )

        total_volume = round(
            qr_volume + p2p_volume + merchant_volume + marketplace_volume,
            2
        )

        # ---- Daily breakdown ----
        daily = {}
        for t in trades:
            day = (t.get("completed_at") or t.get("created_at", ""))[:10]
            if not day:
                continue
            if day not in daily:
                daily[day] = {"volume": 0, "income": 0, "trades": 0}
            daily[day]["trades"] += 1
            daily[day]["volume"] += t.get("amount_usdt", 0) or 0
            # Income from this trade
            if t.get("qr_aggregator_trade"):
                daily[day]["income"] += (t.get("platform_commission_usdt", 0) or 0) + (t.get("merchant_commission_usdt", 0) or t.get("merchant_commission", 0) or 0)
            elif t.get("merchant_id"):
                fee_rub = t.get("platform_fee_rub", 0) or 0
                daily[day]["income"] += fee_rub / base_rate if base_rate > 0 else 0
            else:
                daily[day]["income"] += t.get("trader_commission", 0) or 0

        # Add withdrawal fees to daily
        for f in withdrawal_fees:
            day = (f.get("created_at") or "")[:10]
            if not day:
                continue
            if day not in daily:
                daily[day] = {"volume": 0, "income": 0, "trades": 0}
            daily[day]["income"] += f.get("amount", 0) or 0

        daily_sorted = sorted(
            [{"date": k, **{kk: round(vv, 4) for kk, vv in v.items()}} for k, v in daily.items()],
            key=lambda x: x["date"]
        )

        return {
            "period": period,
            "date_from": start_str,
            "date_to": end_str,
            "base_rate": base_rate,
            "total_income_usdt": total_income,
            "total_volume_usdt": total_volume,
            "total_trades": len(trades),

            "sources": {
                "qr_aggregator": {
                    "label": "QR Агрегатор",
                    "total_usdt": qr_total_income,
                    "volume_usdt": round(qr_volume, 2),
                    "trade_count": len(qr_trades),
                    "breakdown": {
                        "platform_markup": round(qr_platform_markup, 4),
                        "merchant_commission": round(qr_merchant_commission, 4),
                    },
                    "sub": {
                        "exchange_trades": len(qr_exchange_trades),
                        "merchant_trades": len(qr_merchant_trades),
                    },
                    "details": qr_providers_details,
                },
                "trader_commissions": {
                    "label": "Комиссия трейдеров (P2P)",
                    "total_usdt": round(trader_commission_total, 4),
                    "volume_usdt": round(p2p_volume, 2),
                    "trade_count": len(regular_p2p_trades),
                    "details": top_traders_details,
                },
                "merchant_commissions": {
                    "label": "Комиссия мерчантов",
                    "total_usdt": round(merchant_commission_usdt, 4),
                    "total_rub": round(merchant_commission_rub, 2),
                    "volume_usdt": round(merchant_volume, 2),
                    "trade_count": len(regular_merchant_trades),
                    "details": top_merchants_details,
                },
                "withdrawal_fees": {
                    "label": "Комиссия за вывод",
                    "total_usdt": round(withdrawal_fee_total, 4),
                    "count": withdrawal_count,
                },
                "marketplace": {
                    "label": "Маркетплейс и гарант",
                    "total_usdt": marketplace_total,
                    "breakdown": {
                        "shop_orders": round(marketplace_commission, 4),
                        "guarantor_deals": round(guarantor_commission, 4),
                    },
                    "order_count": marketplace_count,
                    "guarantor_count": guarantor_count,
                },
            },

            "daily": daily_sorted,
        }
    except Exception as e:
        logger.error(f"[Accounting] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки бухгалтерии: {str(e)}")
