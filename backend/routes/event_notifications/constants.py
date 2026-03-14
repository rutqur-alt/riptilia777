
# ==================== NOTIFICATION TYPES ====================
NOTIFICATION_TYPES = {
    # Trading section
    "trade_created": {"icon": "TrendingUp", "section": "trading"},
    "trade_payment_sent": {"icon": "DollarSign", "section": "trading"},
    "trade_payment_received": {"icon": "CheckCircle", "section": "trading"},
    "trade_completed": {"icon": "CheckCircle", "section": "trading"},
    "trade_cancelled": {"icon": "XCircle", "section": "trading"},
    "trade_disputed": {"icon": "AlertTriangle", "section": "trading"},
    "trade_message": {"icon": "MessageCircle", "section": "trading"},
    
    # Buy USDT (Crypto payouts)
    "payout_order_created": {"icon": "DollarSign", "section": "buy_usdt"},
    "payout_order_assigned": {"icon": "User", "section": "buy_usdt"},
    "payout_order_paid": {"icon": "CheckCircle", "section": "buy_usdt"},
    "payout_order_completed": {"icon": "CheckCircle", "section": "buy_usdt"},
    "payout_order_cancelled": {"icon": "XCircle", "section": "buy_usdt"},
    
    # Marketplace
    "marketplace_purchase": {"icon": "ShoppingBag", "section": "market"},
    "marketplace_delivered": {"icon": "Package", "section": "market"},
    "marketplace_confirmed": {"icon": "CheckCircle", "section": "market"},
    "marketplace_disputed": {"icon": "AlertTriangle", "section": "market"},
    "shop_new_order": {"icon": "ShoppingBag", "section": "market"},
    "shop_message": {"icon": "MessageCircle", "section": "market"},
    
    # Finance
    "deposit_received": {"icon": "ArrowDownRight", "section": "finances"},
    "withdrawal_completed": {"icon": "ArrowUpRight", "section": "finances"},
    "withdrawal_processing": {"icon": "Clock", "section": "finances"},
    "balance_updated": {"icon": "Wallet", "section": "finances"},
    
    # Messages
    "new_message": {"icon": "MessageCircle", "section": "messages"},
    "support_reply": {"icon": "MessageCircle", "section": "messages"},
    "broadcast": {"icon": "Bell", "section": "messages"},
    
    # Referrals
    "new_referral": {"icon": "Users", "section": "referrals"},
    "referral_bonus": {"icon": "DollarSign", "section": "referrals"},
    
    # Merchant specific
    "merchant_payment_received": {"icon": "DollarSign", "section": "trading"},
    "merchant_withdrawal_request": {"icon": "ArrowUpRight", "section": "trading"},
    "merchant_withdrawal_completed": {"icon": "CheckCircle", "section": "finances"},
}
