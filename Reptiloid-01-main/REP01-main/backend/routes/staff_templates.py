"""
Staff Templates Routes - Migrated from server.py
Handles message templates for staff auto-messages
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import uuid

from core.auth import require_role
from server import db

router = APIRouter(tags=["staff_templates"])


# ==================== MODELS ====================

class MessageTemplateCreate(BaseModel):
    title: str
    content: str
    category: str = "general"  # general, merchant_app, shop_app, dispute, support, guarantor


class MessageTemplateUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None


# ==================== MESSAGE TEMPLATES (AUTO-MESSAGES) ====================

@router.get("/staff/templates")
async def get_message_templates(
    category: Optional[str] = None,
    user: dict = Depends(require_role(["admin", "owner", "mod_p2p", "mod_market", "support"]))
):
    """Get personal message templates for current staff member"""
    user_id = user["id"]
    
    query = {"user_id": user_id}
    if category:
        query["category"] = category
    
    templates = await db.message_templates.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return templates


@router.post("/staff/templates")
async def create_message_template(
    data: MessageTemplateCreate,
    user: dict = Depends(require_role(["admin", "owner", "mod_p2p", "mod_market", "support"]))
):
    """Create a new personal message template"""
    user_id = user["id"]
    now = datetime.now(timezone.utc).isoformat()
    
    template = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "title": data.title,
        "content": data.content,
        "category": data.category,
        "created_at": now,
        "updated_at": now
    }
    
    await db.message_templates.insert_one(template)
    
    return {"status": "created", "template": {k: v for k, v in template.items() if k != "_id"}}


@router.put("/staff/templates/{template_id}")
async def update_message_template(
    template_id: str,
    data: MessageTemplateUpdate,
    user: dict = Depends(require_role(["admin", "owner", "mod_p2p", "mod_market", "support"]))
):
    """Update a personal message template"""
    user_id = user["id"]
    
    # Check template exists and belongs to user
    template = await db.message_templates.find_one({"id": template_id, "user_id": user_id})
    if not template:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if data.title is not None:
        update_data["title"] = data.title
    if data.content is not None:
        update_data["content"] = data.content
    if data.category is not None:
        update_data["category"] = data.category
    
    await db.message_templates.update_one(
        {"id": template_id},
        {"$set": update_data}
    )
    
    return {"status": "updated"}


@router.delete("/staff/templates/{template_id}")
async def delete_message_template(
    template_id: str,
    user: dict = Depends(require_role(["admin", "owner", "mod_p2p", "mod_market", "support"]))
):
    """Delete a personal message template"""
    user_id = user["id"]
    
    # Check template exists and belongs to user
    template = await db.message_templates.find_one({"id": template_id, "user_id": user_id})
    if not template:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    
    await db.message_templates.delete_one({"id": template_id})
    
    return {"status": "deleted"}


# ==================== GLOBAL TEMPLATES (for admins) ====================

@router.get("/admin/global-templates")
async def get_global_templates(
    category: Optional[str] = None,
    user: dict = Depends(require_role(["admin", "owner"]))
):
    """Get global message templates available to all staff"""
    query = {"is_global": True}
    if category:
        query["category"] = category
    
    templates = await db.message_templates.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return templates


@router.post("/admin/global-templates")
async def create_global_template(
    data: MessageTemplateCreate,
    user: dict = Depends(require_role(["admin", "owner"]))
):
    """Create a global message template available to all staff"""
    now = datetime.now(timezone.utc).isoformat()
    
    template = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "is_global": True,
        "title": data.title,
        "content": data.content,
        "category": data.category,
        "created_by": user.get("login", "Admin"),
        "created_at": now,
        "updated_at": now
    }
    
    await db.message_templates.insert_one(template)
    
    return {"status": "created", "template": {k: v for k, v in template.items() if k != "_id"}}


@router.delete("/admin/global-templates/{template_id}")
async def delete_global_template(
    template_id: str,
    user: dict = Depends(require_role(["admin", "owner"]))
):
    """Delete a global message template"""
    template = await db.message_templates.find_one({"id": template_id, "is_global": True})
    if not template:
        raise HTTPException(status_code=404, detail="Глобальный шаблон не найден")
    
    await db.message_templates.delete_one({"id": template_id})
    
    return {"status": "deleted"}
