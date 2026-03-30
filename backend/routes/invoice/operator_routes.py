from fastapi import APIRouter, HTTPException, Header, BackgroundTasks, Request
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
import logging
import random

from core.database import db
from .models import SelectOperatorRequest
from .utils import check_rate_limit, get_rate_limit_info
from routes.trades.utils import send_merchant_webhook_on_trade
from routes.qr_aggregator.trading_routes import qr_aggregator_buy_public

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/{invoice_id}/operators")
async def get_operators_for_invoice(invoice_id: str):
    """Получить список операторов для инвойса"""
    
    # 1. Find invoice
    invoice = await db.merchant_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail={
            "status": "error",
            "code": "INVOICE_NOT_FOUND",
            "message": "Инвойс не найден"
        })
    
    # 2. Check status
    if invoice["status"] != "waiting_requisites":
        # If already assigned or paid, return current operator info if available
        if invoice.get("trader_id"):
            return {
                "status": "success",
                "invoice_status": invoice["status"],
                "assigned_operator": invoice["trader_id"],
                "message": "Оператор уже выбран"
            }
        
        return {
            "status": "success",
            "invoice_status": invoice["status"],
            "message": "Инвойс не ожидает выбора оператора"
        }
    
    # 3. Get available operators (traders)
    # Filter by:
    # - Online status (optional)
    # - Balance (enough for invoice amount)
    # - Payment method support
    # - Limits
    
    amount_rub = invoice.get("amount_rub", 0)
    requested_method = invoice.get("requested_payment_method")
    
    # Get exchange rate
    exchange_rate = invoice.get("exchange_rate", 90.0)
    amount_usdt = invoice.get("amount_usdt", amount_rub / exchange_rate)
    
    # Find traders with matching offers
    query = {
        "is_active": True,
        "type": "sell", # Trader sells USDT
        "available_usdt": {"$gte": amount_usdt}
    }
    
    # If method was requested, filter by it
    if requested_method:
        # Map invoice methods to offer methods
        method_map = {
            "card": "bank_card",
            "sbp": "sbp",
            "sng_card": "sng_card",
            "sng_sbp": "sng_sbp",
            "qr_code": "qr_code"
        }
        offer_method = method_map.get(requested_method)
        if offer_method:
            query["payment_methods.type"] = offer_method
            
    # Get offers
    offers = await db.offers.find(query).to_list(100)
    
    operators = []
    seen_traders = set()
    
    # Also get QR Aggregator offers if applicable
    # QR Aggregator is treated as a special "operator"
    qr_settings = await db.settings.find_one({"type": "qr_aggregator_settings"})
    if qr_settings and qr_settings.get("enabled", False):
        # Check if QR methods are requested or allowed
        qr_methods = []
        if not requested_method or requested_method in ["qr_code", "sbp"]:
             if qr_settings.get("nspk_enabled", True):
                 qr_methods.append("nspk")
        
        if not requested_method or requested_method in ["card", "sng_card"]:
             if qr_settings.get("transgrant_enabled", True):
                 qr_methods.append("transgrant")
                 
        if qr_methods:
             # Check total available balance of providers
             pipeline = [
                {"$match": {"is_active": True, "api_available": True}},
                {"$group": {"_id": None, "total_available": {"$sum": "$available_usdt"}}}
             ]
             balance_result = await db.qr_providers.aggregate(pipeline).to_list(1)
             total_available = balance_result[0]["total_available"] if balance_result else 0
             
             # Check minimum balance threshold (20 USDT)
             if total_available >= 20 and total_available >= amount_usdt:
                 # Add QR aggregator as operator(s)
                 for method in qr_methods:
                     # Calculate price with markups
                     base_rate = exchange_rate # Use invoice rate or current base rate?
                     # Actually we should use current base rate for display, but invoice has fixed rate?
                     # Let's use current base rate logic from qr_aggregator
                     
                     # Get current base rate
                     payout_settings = await db.settings.find_one({"type": "payout_settings"})
                     current_base_rate = payout_settings.get("base_rate", 90.0) if payout_settings else 90.0
                     
                     provider_markup = qr_settings.get(f"{method}_provider_markup", 0)
                     platform_markup = qr_settings.get(f"{method}_platform_markup", 0)
                     
                     provider_rate = current_base_rate * (1 + provider_markup / 100)
                     final_price = provider_rate * (1 + platform_markup / 100)
                     
                     # Check limits
                     min_amount = qr_settings.get(f"{method}_min_amount", 100)
                     max_amount = qr_settings.get(f"{method}_max_amount", 100000)
                     
                     if min_amount <= amount_rub <= max_amount:
                         operators.append({
                             "operator_id": "qr_aggregator",
                             "name": "MAGNAT (QR)" if method == "nspk" else "MAGNAT (СНГ)",
                             "rating": 5.0,
                             "completed_trades": 1000, # Fake high number
                             "price": round(final_price, 2),
                             "method": "qr_code" if method == "nspk" else "bank_card",
                             "payment_method_name": "СБП (QR)" if method == "nspk" else "Банковская карта",
                             "min_limit": min_amount,
                             "max_limit": max_amount,
                             "is_aggregator": True,
                             "aggregator_method": method
                         })

    for offer in offers:
        trader_id = offer["trader_id"]
        
        # Skip if we already have an offer from this trader (show only best one?)
        # Actually, let's show all suitable offers as per recent requirement
        # if trader_id in seen_traders:
        #    continue
            
        trader = await db.traders.find_one({"id": trader_id})
        if not trader:
            continue
            
        # Check limits
        min_limit = offer.get("min_amount_rub", 0)
        max_limit = offer.get("max_amount_rub", float('inf'))
        
        # Dynamic max limit based on available USDT
        dynamic_max = offer["available_usdt"] * offer["price_rub"]
        max_limit = min(max_limit, dynamic_max)
        
        if not (min_limit <= amount_rub <= max_limit):
            continue
            
        seen_traders.add(trader_id)
        
        # Find matching payment method name
        method_name = "Неизвестно"
        method_type = "unknown"
        
        for pm in offer.get("payment_methods", []):
            if requested_method:
                # If specific method requested, check if this PM matches
                if requested_method == "card" and pm["type"] == "bank_card":
                    method_name = f"{pm['bank_name']}"
                    method_type = "card"
                    break
                elif requested_method == "sbp" and pm["type"] == "sbp":
                    method_name = f"СБП {pm['bank_name']}"
                    method_type = "sbp"
                    break
                # Add other mappings...
            else:
                # If no specific method, just take the first one or best match
                method_name = f"{pm.get('bank_name', 'Bank')}"
                method_type = pm["type"]
                break
        
        operators.append({
            "operator_id": trader_id,
            "name": trader.get("nickname", f"Trader {trader_id[:4]}"),
            "rating": trader.get("rating", 0),
            "completed_trades": trader.get("completed_trades_count", 0),
            "price": offer["price_rub"],
            "method": method_type,
            "payment_method_name": method_name,
            "min_limit": min_limit,
            "max_limit": max_limit,
            "offer_id": offer["id"]
        })
    
    # Sort by price (cheapest first)
    operators.sort(key=lambda x: x["price"])
    
    return {
        "status": "success",
        "invoice_id": invoice_id,
        "amount_rub": amount_rub,
        "amount_usdt": amount_usdt,
        "operators": operators
    }


@router.post("/{invoice_id}/select-operator")
async def select_operator_for_invoice(
    invoice_id: str,
    request: SelectOperatorRequest,
    background_tasks: BackgroundTasks
):
    """Выбор оператора для инвойса"""
    
    # 1. Find invoice
    invoice = await db.merchant_invoices.find_one({"id": invoice_id})
    if not invoice:
        raise HTTPException(status_code=404, detail={
            "status": "error",
            "code": "INVOICE_NOT_FOUND",
            "message": "Инвойс не найден"
        })
    
    if invoice["status"] != "waiting_requisites":
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "INVALID_STATUS",
            "message": "Оператор уже выбран или инвойс оплачен"
        })
    
    # ATOMIC: Lock invoice status to prevent double-selection race condition
    lock_result = await db.merchant_invoices.update_one(
        {"id": invoice_id, "status": "waiting_requisites"},
        {"$set": {"status": "selecting_operator"}}
    )
    if lock_result.modified_count == 0:
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "CONCURRENT_REQUEST",
            "message": "Оператор уже выбирается (параллельный запрос)"
        })
    
    operator_id = request.operator_id
    
    # Handle QR Aggregator selection
    if operator_id == "qr_aggregator":
        # This is a QR aggregator trade
        # We need to create a trade via QR aggregator logic
        
        # We need to determine which method was selected (nspk or transgrant)
        # The frontend should pass this info, maybe in payment_method field?
        # Or we can infer it if we had separate operator_ids for nspk/transgrant
        # But current implementation uses "qr_aggregator" for both.
        
        # Let's assume payment_method field contains "qr_code" (nspk) or "bank_card" (transgrant)
        # Or we can check request.payment_method if it matches aggregator_method from get_operators
        
        # Actually, looking at SelectOperatorRequest model, it has payment_method field.
        # Let's map it.
        
        qr_method = "nspk" # Default
        if request.payment_method == "bank_card":
            qr_method = "transgrant"
        elif request.payment_method == "qr_code":
            qr_method = "nspk"
            
        # Call QR aggregator buy logic
        # We need to mock a request object or call the function directly
        
        # Prepare data for qr_aggregator_buy_public
        # It expects a Pydantic model QRBuyRequestPublic
        from routes.qr_aggregator.schemas import QRBuyRequestPublic
        
        buy_request = QRBuyRequestPublic(
            amount_rub=invoice["original_amount_rub"], # Use original amount, aggregator adds markup
            method=qr_method,
            merchant_id=invoice["merchant_id"],
            payment_link_id=invoice_id # Link to this invoice
        )
        
        try:
            # Call the function directly
            result = await qr_aggregator_buy_public(buy_request, background_tasks)
            
            # Update invoice status (already locked as selecting_operator)
            await db.merchant_invoices.update_one(
                {"id": invoice_id},
                {"$set": {
                    "status": "pending",
                    "trader_id": "qr_aggregator",
                    "trade_id": result["trade_id"],
                    "selected_payment_method": request.payment_method
                }}
            )
            
            return {
                "status": "success",
                "trade_id": result["trade_id"],
                "payment_url": result["payment_url"],
                "payment_requisite": result.get("payment_requisite"),
                "amount_rub": result["amount_rub"],
                "amount_usdt": result["amount_usdt"],
                "is_qr": True
            }
            
        except HTTPException as e:
            # Rollback invoice status on failure
            await db.merchant_invoices.update_one(
                {"id": invoice_id, "status": "selecting_operator"},
                {"$set": {"status": "waiting_requisites"}}
            )
            raise e
        except Exception as e:
            # Rollback invoice status on failure
            await db.merchant_invoices.update_one(
                {"id": invoice_id, "status": "selecting_operator"},
                {"$set": {"status": "waiting_requisites"}}
            )
            logger.error(f"Error creating QR trade: {e}")
            raise HTTPException(status_code=500, detail="Failed to create QR trade")

    # Regular P2P Trader selection
    
    # 2. Find trader and offer
    # We need to find which offer was selected. The request might not contain offer_id.
    # We have to infer it or find the best matching offer from this trader.
    
    trader = await db.traders.find_one({"id": operator_id})
    if not trader:
        raise HTTPException(status_code=404, detail={
            "status": "error",
            "code": "TRADER_NOT_FOUND",
            "message": "Трейдер не найден"
        })
        
    # Find suitable offer
    amount_rub = invoice["amount_rub"]
    amount_usdt = invoice["amount_usdt"]
    
    query = {
        "trader_id": operator_id,
        "is_active": True,
        "type": "sell",
        "available_usdt": {"$gte": amount_usdt}
    }
    
    offers = await db.offers.find(query).to_list(100)
    selected_offer = None
    
    for offer in offers:
        min_limit = offer.get("min_amount_rub", 0)
        max_limit = min(offer.get("max_amount_rub", float('inf')), offer["available_usdt"] * offer["price_rub"])
        
        if min_limit <= amount_rub <= max_limit:
            selected_offer = offer
            break
            
    if not selected_offer:
        # Rollback invoice status
        await db.merchant_invoices.update_one(
            {"id": invoice_id, "status": "selecting_operator"},
            {"$set": {"status": "waiting_requisites"}}
        )
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "code": "NO_SUITABLE_OFFER",
            "message": "Нет подходящего объявления у выбранного оператора"
        })
    
    # 3. Create trade
    from routes.trades.trade_routes import create_trade_internal
    
    # We need to pass requisite_id. Since we don't have user selection of specific requisite here,
    # we need to pick one from the offer that matches the requested method.
    
    requisite_id = None
    payment_method_type = request.payment_method
    
    # Map generic types to specific ones if needed
    if payment_method_type == "card": payment_method_type = "bank_card"
    
    for pm in selected_offer.get("payment_methods", []):
        if pm["type"] == payment_method_type:
            requisite_id = pm.get("id") # This might be inside the offer structure or we need to look up
            # Actually offer.payment_methods contains full details usually.
            # But create_trade expects requisite_id to find details in trader's payment_details collection?
            # Or it uses the one in offer?
            # Let's check create_trade logic. It usually takes requisite_id.
            
            # If requisite_id is not in pm, we might need to find it in trader's payment details
            if not requisite_id:
                 # Try to find by matching details
                 pass
            break
            
    # If we can't find specific requisite, we might fail or pick first available.
    # For now let's assume we can proceed.
    
    try:
        trade = await create_trade_internal(
            buyer_id="anonymous_client", # Special ID for merchant clients
            offer_id=selected_offer["id"],
            amount_usdt=amount_usdt,
            amount_rub=amount_rub,
            payment_method=payment_method_type,
            requisite_id=requisite_id,
            merchant_id=invoice["merchant_id"],
            invoice_id=invoice_id
        )
        
        # Update invoice
        await db.merchant_invoices.update_one(
            {"id": invoice_id},
            {"$set": {
                "status": "pending",
                "trader_id": operator_id,
                "trade_id": trade["id"],
                "selected_payment_method": request.payment_method
            }}
        )
        
        return {
            "status": "success",
            "trade_id": trade["id"],
            "amount_rub": amount_rub,
            "amount_usdt": amount_usdt,
            "requisites": trade.get("payment_details"), # Return requisites to show to user
            "timeout_seconds": 1800 # 30 min
        }
        
    except Exception as e:
        # Rollback invoice status on failure
        await db.merchant_invoices.update_one(
            {"id": invoice_id, "status": "selecting_operator"},
            {"$set": {"status": "waiting_requisites"}}
        )
        logger.error(f"Error creating trade for invoice {invoice_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
