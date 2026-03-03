"""
Unified Messaging System for Reptiloid Platform
Based on the messaging specification document.

Key Principles:
1. All messages stored forever in database
2. No one can completely delete a message - only hide for certain users
3. In disputes, users cannot delete their messages
4. Guarantor is arbiter with decision-making authority
5. Color coding system for quick role identification

Role Colors:
- User/Buyer: white
- P2P Seller: white + 💱
- Shop Owner: purple (#8B5CF6)
- Merchant: orange (#F97316)
- P2P Moderator: yellow (#F59E0B)
- Marketplace Moderator/Guarantor: yellow + ⚖️
- Support: blue (#3B82F6)
- Administrator: red (#EF4444)
- System: gray (#6B7280)
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
import uuid

router = APIRouter(prefix="/messaging", tags=["Messaging"])

# ==================== MODELS ====================

class ConversationType:
    P2P_TRADE = "p2p_trade"           # P2P trade between users
    P2P_MERCHANT = "p2p_merchant"     # P2P trade through merchant
    MARKETPLACE = "marketplace"        # Marketplace order with guarantor
    SUPPORT_TICKET = "support_ticket"  # Support ticket
    FORUM_TOPIC = "forum_topic"        # Forum discussion
    INTERNAL_STAFF = "internal_staff"  # Internal staff chat
    MERCHANT_APPLICATION = "merchant_app"  # Merchant registration application
    SHOP_APPLICATION = "shop_app"      # Shop opening application

class ConversationStatus:
    ACTIVE = "active"
    DISPUTE = "dispute"
    COMPLETED = "completed"
    ARCHIVED = "archived"

class SenderRole:
    USER = "user"                    # Regular user/buyer - white
    P2P_SELLER = "p2p_seller"        # P2P seller - white + 💱
    SHOP_OWNER = "shop_owner"        # Shop owner - purple
    MERCHANT = "merchant"            # Merchant - orange
    MOD_P2P = "mod_p2p"              # P2P moderator - yellow
    MOD_MARKET = "mod_market"        # Marketplace mod/guarantor - yellow + ⚖️
    SUPPORT = "support"              # Support - blue
    ADMIN = "admin"                  # Administrator - red
    SYSTEM = "system"                # System messages - gray

# Role color mapping
ROLE_COLORS = {
    "user": "#FFFFFF",
    "p2p_seller": "#FFFFFF",
    "shop_owner": "#8B5CF6",
    "merchant": "#F97316",
    "mod_p2p": "#F59E0B",
    "mod_market": "#F59E0B",
    "support": "#3B82F6",
    "admin": "#EF4444",
    "owner": "#EF4444",
    "system": "#6B7280"
}

# Role icons
ROLE_ICONS = {
    "p2p_seller": "💱",
    "mod_market": "⚖️",
    "shop_owner": "🏪",
    "merchant": "🏢"
}

# Role display names
ROLE_NAMES = {
    "user": "Пользователь",
    "p2p_seller": "Продавец P2P",
    "shop_owner": "Владелец магазина",
    "merchant": "Мерчант",
    "mod_p2p": "Модератор P2P",
    "mod_market": "Гарант",
    "support": "Поддержка",
    "admin": "Администратор",
    "owner": "Владелец",
    "system": "Система"
}

# ==================== MESSAGE DELETION RULES ====================
# Based on the specification table

def can_delete_message(
    context: str,           # p2p, p2p_dispute, marketplace, forum, support, internal
    user_role: str,         # role of user trying to delete
    is_own_message: bool,   # is this their own message
    message_age_minutes: int,
    is_dispute: bool = False
) -> tuple[bool, str]:
    """
    Check if user can delete a message based on complex rules.
    Returns (can_delete, reason)
    """
    
    # Admin can delete everything
    if user_role in ["admin", "owner"]:
        return True, "admin_privilege"
    
    # Moderators can delete their own (5 min) + others' messages
    if user_role in ["mod_p2p", "mod_market"]:
        if is_own_message and message_age_minutes <= 5:
            return True, "moderator_own_within_time"
        if not is_own_message:
            return True, "moderator_delete_other"
        return False, "time_expired"
    
    # Support can delete their own (5 min) + others' in support context
    if user_role == "support":
        if context == "support_ticket":
            if is_own_message and message_age_minutes <= 5:
                return True, "support_own_within_time"
            if not is_own_message:
                return True, "support_delete_other"
        return False, "no_permission"
    
    # Regular users and sellers
    if user_role in ["user", "p2p_seller", "shop_owner", "merchant"]:
        # In disputes - NO deletion allowed
        if is_dispute or context in ["p2p_dispute", "marketplace"]:
            return False, "delete_locked_in_dispute"
        
        # P2P trade without dispute - NO deletion (per spec table)
        if context == "p2p":
            return False, "p2p_no_delete"
        
        # Forum, support - 5 minutes for own messages
        if context in ["forum", "support_ticket"]:
            if is_own_message and message_age_minutes <= 5:
                return True, "self_delete_within_time"
            return False, "time_expired" if is_own_message else "not_own_message"
        
        # Internal chats - 5 minutes for own
        if context == "internal":
            if is_own_message and message_age_minutes <= 5:
                return True, "self_delete_within_time"
            return False, "time_expired"
    
    return False, "no_permission"


# ==================== HELPER FUNCTIONS ====================

def get_sender_display(role: str, name: str) -> dict:
    """Get display info for message sender"""
    return {
        "name": name,
        "role": role,
        "role_name": ROLE_NAMES.get(role, role),
        "color": ROLE_COLORS.get(role, "#FFFFFF"),
        "icon": ROLE_ICONS.get(role, "")
    }

def create_system_message(conversation_id: str, content: str) -> dict:
    """Create a system message"""
    return {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "sender_id": "system",
        "sender_role": "system",
        "sender_name": "Система",
        "content": content,
        "is_system_message": True,
        "can_be_deleted": False,
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

def create_conversation(
    conv_type: str,
    related_id: str,
    title: str,
    participants: list
) -> dict:
    """Create a new conversation"""
    return {
        "id": str(uuid.uuid4()),
        "type": conv_type,
        "status": ConversationStatus.ACTIVE,
        "related_id": related_id,
        "title": title,
        "delete_locked": conv_type == ConversationType.MARKETPLACE,  # Marketplace locked from start
        "participants": participants,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }


# ==================== API ENDPOINTS ====================

# These will be imported and used in server.py
# The actual implementation will be in server.py using the db connection

"""
Endpoints to implement:

# Conversations
GET /api/messaging/conversations - Get user's conversations
GET /api/messaging/conversations/{id} - Get conversation details
POST /api/messaging/conversations - Create conversation (internal use)

# Messages
GET /api/messaging/conversations/{id}/messages - Get messages
POST /api/messaging/conversations/{id}/messages - Send message
DELETE /api/messaging/messages/{id} - Delete message (with rules)

# P2P Trade specific
POST /api/messaging/trade/{trade_id}/open-dispute - Open dispute, add moderator
POST /api/messaging/trade/{trade_id}/resolve - Resolve dispute

# Marketplace specific
POST /api/messaging/order/{order_id}/create - Create order chat with guarantor

# Support
POST /api/messaging/support/create - Create support ticket
GET /api/messaging/support/tickets - Get user's tickets

# Internal Staff
GET /api/messaging/staff/chats - Get staff chats
POST /api/messaging/staff/chats - Create internal discussion
"""

# Export for use in server.py
__all__ = [
    'ConversationType',
    'ConversationStatus', 
    'SenderRole',
    'ROLE_COLORS',
    'ROLE_ICONS',
    'ROLE_NAMES',
    'can_delete_message',
    'get_sender_display',
    'create_system_message',
    'create_conversation'
]
