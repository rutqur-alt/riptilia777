"""
Database connection and utilities
"""
from motor.motor_asyncio import AsyncIOMotorClient
from pathlib import Path
from dotenv import load_dotenv
import os

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'reptiloid')]


# Admin role levels
ADMIN_ROLES = {
    "owner": 100,
    "admin": 80,
    "mod_p2p": 50,
    "mod_market": 50,
    "support": 30
}

# Granular permissions for each role
ROLE_PERMISSIONS = {
    "owner": ["*"],
    "admin": ["*"],
    "mod_p2p": [
        "view_users", "view_user_stats", "block_users", "block_user_balance",
        "view_p2p_trades", "view_p2p_offers", "resolve_p2p_disputes",
        "view_merchants", "approve_merchants",
        "view_messages", "send_messages"
    ],
    "mod_market": [
        "view_shops", "block_shops", "approve_shops", "block_shop_balance",
        "view_products", "moderate_products",
        "act_as_guarantor", "resolve_market_disputes",
        "view_messages", "send_messages"
    ],
    "support": [
        "view_all_messages", "send_messages", "answer_tickets",
        "escalate_to_mod_p2p", "escalate_to_mod_market", "escalate_to_admin",
        "invite_to_chat"
    ]
}

def has_permission(user: dict, permission: str) -> bool:
    admin_role = user.get("admin_role", user.get("role", ""))
    perms = ROLE_PERMISSIONS.get(admin_role, [])
    return "*" in perms or permission in perms
