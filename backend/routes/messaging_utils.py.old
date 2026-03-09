"""
Unified Messaging System API Routes
Complete implementation based on messaging specification
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
import uuid

# ==================== CONSTANTS ====================

CONVERSATION_TYPES = {
    "p2p_trade": "P2P Сделка",
    "p2p_merchant": "Сделка через мерчанта", 
    "marketplace": "Заказ Marketplace",
    "support_ticket": "Тикет поддержки",
    "forum_topic": "Тема форума",
    "internal_mods_p2p": "Чат модераторов P2P",
    "internal_mods_market": "Чат модераторов Marketplace",
    "internal_support": "Чат поддержки",
    "internal_admin": "Чат администрации",
    "internal_discussion": "Внутреннее обсуждение",
    "merchant_application": "Заявка мерчанта",
    "shop_application": "Заявка на магазин"
}

# Role Colors (hex)
ROLE_COLORS = {
    "user": "#FFFFFF",           # White - regular user
    "buyer": "#FFFFFF",          # White - buyer
    "p2p_seller": "#FFFFFF",     # White - P2P seller (with icon 💱)
    "shop_owner": "#8B5CF6",     # Purple - shop owner
    "merchant": "#F97316",       # Orange - merchant
    "mod_p2p": "#F59E0B",        # Yellow - P2P moderator
    "mod_market": "#F59E0B",     # Yellow - Marketplace moderator/guarantor (with icon ⚖️)
    "support": "#3B82F6",        # Blue - support
    "admin": "#EF4444",          # Red - admin
    "owner": "#EF4444",          # Red - owner
    "system": "#6B7280"          # Gray - system messages
}

# Role Icons
ROLE_ICONS = {
    "p2p_seller": "💱",
    "mod_market": "⚖️",
    "shop_owner": "🏪",
    "merchant": "🏢"
}

# Role Display Names
ROLE_DISPLAY_NAMES = {
    "user": "Пользователь",
    "buyer": "Покупатель",
    "p2p_seller": "Продавец",
    "shop_owner": "Магазин",
    "merchant": "Мерчант",
    "mod_p2p": "Модератор P2P",
    "mod_market": "Гарант",
    "support": "Поддержка",
    "admin": "Администратор",
    "owner": "Владелец",
    "system": "Система"
}


# Staff Role Display Names (English)
STAFF_ROLE_DISPLAY_EN = {
    "owner": "Owner",
    "admin": "Admin",
    "mod_p2p": "P2P Moderator",
    "mod_market": "Market Moderator",
    "support": "Support",
}


def get_staff_display_name(user: dict) -> str:
    """Get display name for a staff user based on admin_role"""
    admin_role = user.get("admin_role", "")
    role_label = STAFF_ROLE_DISPLAY_EN.get(admin_role, admin_role)
    nickname = user.get("nickname") or user.get("login") or "Staff"
    return f"{nickname} [{role_label}]"


# ==================== DELETE PERMISSION LOGIC ====================

def check_delete_permission(
    conv_type: str,
    conv_status: str,
    user_role: str,
    is_sender: bool,
    message_age_seconds: int
) -> tuple:
    """
    Check if user can delete a message.
    Returns (can_delete: bool, reason: str)
    
    Rules from spec:
    - P2P chat (no dispute): NO deletion for buyer/seller
    - P2P chat (dispute): NO deletion for buyer/seller
    - Marketplace: NO deletion from start
    - Forum/Support: 5 min for own messages
    - Internal: 5 min for own messages
    - Moderators: own (5 min) + can delete others
    - Admin: can delete everything
    """
    
    FIVE_MINUTES = 5 * 60  # seconds
    
    # Admin/Owner can delete everything
    if user_role in ["admin", "owner"]:
        return True, "admin_privilege"
    
    # Moderators can delete own (5 min) + others
    if user_role in ["mod_p2p", "mod_market"]:
        if not is_sender:
            return True, "moderator_delete_other"
        if message_age_seconds <= FIVE_MINUTES:
            return True, "moderator_own_within_time"
        return False, "time_expired"
    
    # Support can delete in support context
    if user_role == "support":
        if conv_type == "support_ticket":
            if not is_sender:
                return True, "support_delete_other"
            if message_age_seconds <= FIVE_MINUTES:
                return True, "support_own_within_time"
        return False, "no_permission"
    
    # Regular users (buyer, seller, shop_owner, merchant)
    
    # P2P trades - NO deletion allowed (per spec table)
    if conv_type in ["p2p_trade", "p2p_merchant"]:
        return False, "p2p_no_delete"
    
    # Marketplace - NO deletion from start
    if conv_type == "marketplace":
        return False, "marketplace_no_delete"
    
    # In dispute status - block deletion
    if conv_status == "dispute":
        return False, "dispute_locked"
    
    # Forum and support - 5 min for own
    if conv_type in ["forum_topic", "support_ticket"]:
        if is_sender and message_age_seconds <= FIVE_MINUTES:
            return True, "self_delete_within_time"
        if is_sender:
            return False, "time_expired"
        return False, "not_sender"
    
    return False, "no_permission"


# ==================== HELPER FUNCTIONS ====================

def create_system_message(conversation_id: str, content: str, msg_type: str = "info") -> dict:
    """Create a system message"""
    return {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "sender_id": "system",
        "sender_role": "system",
        "sender_name": "Система",
        "content": content,
        "message_type": msg_type,  # info, warning, success, error
        "is_system": True,
        "can_delete": False,
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }


def create_message(
    conversation_id: str,
    sender_id: str,
    sender_role: str,
    sender_name: str,
    content: str,
    attachments: list = None
) -> dict:
    """Create a user message"""
    return {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "sender_id": sender_id,
        "sender_role": sender_role,
        "sender_name": sender_name,
        "content": content,
        "attachments": attachments or [],
        "is_system": False,
        "can_delete": True,  # Will be checked by rules
        "is_deleted": False,
        "deleted_by": None,
        "deleted_at": None,
        "delete_reason": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }


def create_conversation(
    conv_type: str,
    related_id: str,
    title: str,
    initial_participants: list
) -> dict:
    """
    Create a new conversation.
    
    initial_participants format:
    [
        {"user_id": "...", "role": "buyer", "name": "Иван"},
        {"user_id": "...", "role": "p2p_seller", "name": "Алексей"}
    ]
    """
    # Marketplace orders start with delete_locked = True
    delete_locked = conv_type == "marketplace"
    
    return {
        "id": str(uuid.uuid4()),
        "type": conv_type,
        "status": "active",
        "related_id": related_id,
        "title": title,
        "delete_locked": delete_locked,
        "participants": initial_participants,
        "unread_counts": {p["user_id"]: 0 for p in initial_participants},
        "last_message_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }


def add_participant_to_conversation(conversation: dict, user_id: str, role: str, name: str) -> dict:
    """Add a participant to existing conversation"""
    new_participant = {
        "user_id": user_id,
        "role": role,
        "name": name,
        "joined_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Check if already participant
    for p in conversation.get("participants", []):
        if p["user_id"] == user_id:
            return conversation  # Already in
    
    conversation["participants"].append(new_participant)
    conversation["unread_counts"][user_id] = 0
    conversation["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    return conversation


def get_role_display_info(role: str, name: str) -> dict:
    """Get display information for a role"""
    return {
        "name": name,
        "role": role,
        "role_display": ROLE_DISPLAY_NAMES.get(role, role),
        "color": ROLE_COLORS.get(role, "#FFFFFF"),
        "icon": ROLE_ICONS.get(role, ""),
        "bg_class": get_tailwind_bg_class(role)
    }


def get_tailwind_bg_class(role: str) -> str:
    """Get Tailwind CSS background class for role"""
    mapping = {
        "user": "bg-white text-black",
        "buyer": "bg-white text-black",
        "p2p_seller": "bg-white text-black",
        "shop_owner": "bg-[#8B5CF6] text-white",
        "merchant": "bg-[#F97316] text-white",
        "mod_p2p": "bg-[#F59E0B] text-white",
        "mod_market": "bg-[#F59E0B] text-white",
        "support": "bg-[#3B82F6] text-white",
        "admin": "bg-[#EF4444] text-white",
        "owner": "bg-[#EF4444] text-white",
        "system": "bg-[#6B7280] text-white"
    }
    return mapping.get(role, "bg-white text-black")


# ==================== PYDANTIC MODELS ====================

class SendMessageRequest(BaseModel):
    content: str
    attachments: Optional[List[str]] = None

class OpenDisputeRequest(BaseModel):
    reason: str

class ResolveDisputeRequest(BaseModel):
    decision: str  # "refund_buyer", "release_seller", "split"
    amount: Optional[float] = None
    reason: str

class CreateSupportTicketRequest(BaseModel):
    category: str
    subject: str
    message: str
    related_id: Optional[str] = None  # Optional trade/order ID

class CreateInternalChatRequest(BaseModel):
    title: str
    participant_ids: List[str]
    related_dispute_id: Optional[str] = None


# ==================== EXPORT ====================

__all__ = [
    'CONVERSATION_TYPES',
    'ROLE_COLORS',
    'ROLE_ICONS',
    'ROLE_DISPLAY_NAMES',
    'check_delete_permission',
    'create_system_message',
    'create_message',
    'create_conversation',
    'add_participant_to_conversation',
    'get_role_display_info',
    'get_tailwind_bg_class',
    'SendMessageRequest',
    'OpenDisputeRequest',
    'ResolveDisputeRequest',
    'CreateSupportTicketRequest',
    'CreateInternalChatRequest'
]
