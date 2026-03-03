#!/usr/bin/env python3
"""
Migration script to normalize the 'offers' collection.
Fixes:
1. Missing trader_login - loads from traders collection
2. Missing payment_methods - sets to empty list
3. Inconsistent is_active/status fields - synchronizes them
4. Missing required fields - adds defaults

Run: python3 migrations/normalize_offers.py
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import os
import sys

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))


async def normalize_offers():
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    db_name = os.environ.get('DB_NAME', 'test_database')
    
    print(f"Connecting to {mongo_url}, database: {db_name}")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    # Get all offers
    offers = await db.offers.find({}).to_list(1000)
    print(f"\nFound {len(offers)} offers to check")
    
    fixed_count = 0
    
    for offer in offers:
        offer_id = offer.get("id", str(offer.get("_id")))
        updates = {}
        issues = []
        
        # 1. Fix missing trader_login
        if not offer.get("trader_login"):
            trader = await db.traders.find_one({"id": offer.get("trader_id")}, {"_id": 0, "login": 1})
            if trader:
                updates["trader_login"] = trader.get("login", "")
                issues.append(f"trader_login was missing, set to '{updates['trader_login']}'")
            else:
                updates["trader_login"] = ""
                issues.append("trader_login was missing, trader not found")
        
        # 2. Fix missing payment_methods
        if not offer.get("payment_methods"):
            # Try to derive from payment_details
            payment_methods = []
            if offer.get("payment_details"):
                for pd in offer["payment_details"]:
                    pt = pd.get("payment_type", "")
                    if pt and pt not in payment_methods:
                        payment_methods.append(pt)
            updates["payment_methods"] = payment_methods if payment_methods else []
            issues.append(f"payment_methods was missing, set to {updates['payment_methods']}")
        
        # 3. Synchronize is_active and status
        has_is_active = "is_active" in offer
        has_status = "status" in offer
        
        if has_status and not has_is_active:
            # Has status but no is_active - derive is_active from status
            updates["is_active"] = offer["status"] == "active"
            issues.append(f"is_active missing, derived from status='{offer['status']}' -> is_active={updates['is_active']}")
        
        if has_is_active and has_status:
            # Both exist - check for inconsistency
            is_active_val = offer.get("is_active")
            status_val = offer.get("status")
            
            # is_active takes precedence
            expected_status = "active" if is_active_val else "inactive"
            if status_val != expected_status and is_active_val != (status_val == "active"):
                updates["status"] = expected_status
                issues.append(f"status inconsistent with is_active={is_active_val}, status was '{status_val}', set to '{expected_status}'")
        
        if not has_is_active and not has_status:
            # Neither exists - default to inactive
            updates["is_active"] = False
            updates["status"] = "inactive"
            issues.append("both is_active and status missing, defaulted to inactive")
        
        # 4. Fix missing amount fields
        if "amount_usdt" not in offer:
            updates["amount_usdt"] = offer.get("max_amount", 0)
            issues.append(f"amount_usdt missing, set to {updates['amount_usdt']}")
        
        if "available_usdt" not in offer:
            updates["available_usdt"] = offer.get("amount_usdt", offer.get("max_amount", 0))
            issues.append(f"available_usdt missing, set to {updates['available_usdt']}")
        
        if "min_amount" not in offer:
            updates["min_amount"] = 1.0
            issues.append("min_amount missing, set to 1.0")
        
        if "max_amount" not in offer:
            updates["max_amount"] = offer.get("amount_usdt", 0)
            issues.append(f"max_amount missing, set to {updates['max_amount']}")
        
        if "price_rub" not in offer:
            updates["price_rub"] = 0.0
            issues.append("price_rub missing, set to 0.0")
        
        if "created_at" not in offer:
            updates["created_at"] = datetime.now(timezone.utc).isoformat()
            issues.append("created_at missing, set to now")
        
        # Apply updates if any
        if updates:
            print(f"\n  Offer {offer_id[:12]}...")
            for issue in issues:
                print(f"    - {issue}")
            
            await db.offers.update_one(
                {"id": offer_id},
                {"$set": updates}
            )
            fixed_count += 1
    
    print(f"\n✅ Migration complete. Fixed {fixed_count} offers out of {len(offers)} total.")
    client.close()


if __name__ == "__main__":
    asyncio.run(normalize_offers())
