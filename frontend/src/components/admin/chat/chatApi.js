// API functions for UnifiedMessagesHub
import axios from "axios";
import { API } from "@/App";

// Fetch all conversations based on role and category
export const fetchAllConversations = async (token, adminRole, activeCategory, setUserChats) => {
  let allConvs = [];
  
  // Fetch P2P disputes
  if ((adminRole === "mod_p2p" || adminRole === "owner" || adminRole === "admin") && 
      (activeCategory === "all" || activeCategory === "p2p_dispute")) {
    try {
      const res = await axios.get(`${API}/msg/admin/disputes`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      allConvs = [...allConvs, ...(res.data || []).map(c => ({ 
        ...c, 
        id: c.id || c.trade?.id,
        related_id: c.trade?.id,
        context_id: c.trade?.id,
        category: "p2p_dispute",
        title: c.trade ? `Спор: ${c.trade.amount_usdt || c.trade.amount} USDT` : (c.title || "P2P Спор"),
        subtitle: c.trade ? `@${c.trade.buyer_nickname || c.trade.buyer_login || "покупатель"} vs @${c.trade.trader_login || c.trade.seller_nickname || "продавец"}` : (c.subtitle || ""),
        type: "p2p_dispute",
        status: c.trade?.status || c.status || "disputed"
      }))];
    } catch (e) { console.error(e); }
  }
  
  // Fetch crypto payout orders
  if ((adminRole === "mod_p2p" || adminRole === "owner" || adminRole === "admin") &&
      (activeCategory === "all" || activeCategory === "crypto_payout")) {
    try {
      const res = await axios.get(`${API}/msg/admin/crypto-payouts`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      allConvs = [...allConvs, ...(res.data || []).map(c => ({
        ...c,
        category: "crypto_payout",
        title: c.title || `Покупка ${c.amount_usdt || c.order?.amount_usdt || "?"} USDT`,
        subtitle: c.subtitle || `@${c.buyer_nickname || c.order?.buyer_nickname || "покупатель"}`,
        type: "crypto_order"
      }))];
    } catch (e) { console.error(e); }
  }
  
  // Fetch merchant applications
  if ((adminRole === "mod_p2p" || adminRole === "owner" || adminRole === "admin") &&
      (activeCategory === "all" || activeCategory === "merchant_app")) {
    try {
      const unifiedRes = await axios.get(`${API}/msg/admin/merchant-applications`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (unifiedRes.data && unifiedRes.data.length > 0) {
        allConvs = [...allConvs, ...(unifiedRes.data || []).map(c => ({
          ...c,
          category: "merchant_app",
          title: c.title || c.merchant_name || "Заявка мерчанта",
          subtitle: c.subtitle || `@${c.nickname || "пользователь"} • ${c.merchant_type || ""}`,
          type: "merchant_application"
        }))];
      } else {
        const res = await axios.get(`${API}/merchants/pending`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        allConvs = [...allConvs, ...(res.data || []).map(m => ({
          id: `merchant_${m.id}`,
          related_id: m.id,
          title: m.merchant_name,
          subtitle: `@${m.nickname} • ${m.merchant_type}`,
          type: "merchant_application",
          category: "merchant_app",
          status: "pending",
          data: m
        }))];
      }
    } catch (e) { 
      try {
        const res = await axios.get(`${API}/merchants/pending`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        allConvs = [...allConvs, ...(res.data || []).map(m => ({
          id: `merchant_${m.id}`,
          related_id: m.id,
          title: m.merchant_name,
          subtitle: `@${m.nickname} • ${m.merchant_type}`,
          type: "merchant_application",
          category: "merchant_app",
          status: "pending",
          data: m
        }))];
      } catch (e2) { console.error(e2); }
    }
  }
  
  // Fetch shop applications
  if ((adminRole === "mod_market" || adminRole === "owner" || adminRole === "admin") &&
      (activeCategory === "all" || activeCategory === "shop_app")) {
    try {
      const unifiedRes = await axios.get(`${API}/msg/admin/shop-applications`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (unifiedRes.data && unifiedRes.data.length > 0) {
        allConvs = [...allConvs, ...(unifiedRes.data || []).map(c => ({
          ...c,
          category: "shop_app",
          title: c.title || c.shop_name || "Заявка на магазин",
          subtitle: c.subtitle || `@${c.user_nickname || "пользователь"}`,
          type: "shop_application"
        }))];
      } else {
        const res = await axios.get(`${API}/admin/shop-applications?status=pending`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        allConvs = [...allConvs, ...(res.data || []).map(s => ({
          id: `shop_${s.id}`,
          related_id: s.id,
          title: s.shop_name,
          subtitle: `@${s.user_nickname}`,
          type: "shop_application",
          category: "shop_app",
          status: "pending",
          data: s
        }))];
      }
    } catch (e) { 
      try {
        const res = await axios.get(`${API}/admin/shop-applications?status=pending`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        allConvs = [...allConvs, ...(res.data || []).map(s => ({
          id: `shop_${s.id}`,
          related_id: s.id,
          title: s.shop_name,
          subtitle: `@${s.user_nickname}`,
          type: "shop_application",
          category: "shop_app",
          status: "pending",
          data: s
        }))];
      } catch (e2) { console.error(e2); }
    }
  }
  
  // Fetch guarantor orders
  if ((adminRole === "mod_market" || adminRole === "owner" || adminRole === "admin") &&
      (activeCategory === "all" || activeCategory === "guarantor")) {
    try {
      const res = await axios.get(`${API}/msg/admin/guarantor-orders`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      allConvs = [...allConvs, ...(res.data || []).map(c => ({
        ...c,
        id: c.conversation_id || c.id,
        purchase_id: c.id,
        category: "guarantor",
        title: c.title || "Гарант-сделка",
        subtitle: c.subtitle || "",
        type: "marketplace_guarantor"
      }))];
    } catch (e) { console.error(e); }
  }
  
  // Fetch support tickets
  if ((adminRole === "support" || adminRole === "owner" || adminRole === "admin") &&
      (activeCategory === "all" || activeCategory === "support")) {
    try {
      const res = await axios.get(`${API}/admin/support/tickets?status=active`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      allConvs = [...allConvs, ...(res.data || []).map(t => ({
        id: `ticket_${t.id}`,
        related_id: t.id,
        title: t.subject,
        subtitle: `@${t.user_nickname} • ${t.category_name || t.category}`,
        type: "support_ticket",
        category: "support",
        status: t.status,
        unread_count: t.unread_count,
        data: t
      }))];
    } catch (e) { console.error(e); }
  }
    // Unified support tickets (from unified_conversations)
    try {
      const res2 = await axios.get(`${API}/admin/unified-support-tickets`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const existingIds = new Set(allConvs.map(c => c.id));
      allConvs = [...allConvs, ...(res2.data || []).filter(t => !existingIds.has(t.id) && !existingIds.has(`ticket_${t.id}`)).map(t => ({
        id: t.id,
        related_id: t.id,
        title: t.subject || "Обращение в поддержку",
        subtitle: `@${t.user_nickname || "пользователь"} \u2022 ${t.category_name || t.category || "другое"}`,
        type: "unified_support_ticket",
        category: "support",
        status: t.status || "active",
        unread_count: t.unread_count || 0,
        data: t
      }))];
    } catch (e) { console.error(e); }


  // Fetch admin-to-user chats
  if ((adminRole === "owner" || adminRole === "admin" || adminRole === "mod_p2p" || adminRole === "mod_market") &&
      (activeCategory === "all" || activeCategory === "admin_to_user")) {
    try {
      const res = await axios.get(`${API}/admin/user-chats`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      allConvs = [...allConvs, ...(res.data || []).map(c => ({
        ...c,
        category: "admin_to_user",
        title: c.title || `Чат с @${c.target_user_name}`,
        subtitle: c.subject || "Сообщение администрации",
        type: "admin_user_chat"
      }))];
      if (setUserChats) setUserChats(res.data || []);
    } catch (e) { console.error(e); }
  }
  
  // Fetch invited chats
  if (activeCategory === "all" || activeCategory === "invited") {
    try {
      const res = await axios.get(`${API}/admin/invited-chats`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const invitedChats = (res.data || []).filter(c => 
        !allConvs.some(existing => existing.id === c.id)
      );
      allConvs = [...allConvs, ...invitedChats.map(c => ({
        ...c,
        category: "invited"
      }))];
    } catch (e) { console.error(e); }
  }
  
  // Filter out archived conversations (they should only appear in Archive section)
  return allConvs.filter(c => !c.archived);
};

// Fetch messages for a conversation
export const fetchConversationMessages = async (token, selectedConv) => {
  if (!selectedConv) return [];
  
  let msgs = [];
  
  if (selectedConv.type === "p2p_dispute" || selectedConv.type === "p2p_trade") {
    const tradeId = selectedConv.related_id || selectedConv.trade?.id || selectedConv.id;
    const res = await axios.get(`${API}/admin/disputes/${tradeId}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    msgs = (res.data?.messages || []).map(m => ({
      ...m,
      sender_role: m.sender_role || m.sender_type
    }));
  } else if (selectedConv.type === "merchant_application") {
    if (selectedConv.id && !selectedConv.id.startsWith("merchant_")) {
      const res = await axios.get(`${API}/msg/conversations/${selectedConv.id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      msgs = res.data?.messages || [];
    } else {
      const res = await axios.get(`${API}/admin/merchant-chat/${selectedConv.data?.id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      msgs = (res.data || []).map(m => ({
        ...m, content: m.message, sender_name: m.sender_login, sender_role: m.sender_type === "admin" ? m.sender_role : "merchant"
      }));
    }
  } else if (selectedConv.type === "shop_application") {
    if (selectedConv.id && !selectedConv.id.startsWith("shop_")) {
      const res = await axios.get(`${API}/msg/conversations/${selectedConv.id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      msgs = res.data?.messages || [];
    } else {
      const res = await axios.get(`${API}/admin/shop-application-chat/${selectedConv.data?.user_id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      msgs = (res.data || []).map(m => ({
        ...m, content: m.message, sender_name: m.sender_login, sender_role: m.sender_type === "admin" ? m.sender_role : "shop_owner"
      }));
    }
  } else if (selectedConv.type === "marketplace_guarantor") {
    const res = await axios.get(`${API}/msg/conversations/${selectedConv.id}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    msgs = res.data?.messages || [];
  } else if (selectedConv.type === "crypto_order") {
    const res = await axios.get(`${API}/admin/conversations/${selectedConv.id}/messages`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    msgs = res.data || [];
  } else if (selectedConv.type === "support_ticket") {
    const res = await axios.get(`${API}/admin/support/tickets/${selectedConv.data?.id}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    msgs = (res.data?.messages || []).map(m => ({
      ...m, sender_role: m.sender_type === "admin" ? (m.sender_role || "support") : "user"
    }));
  } else if (selectedConv.type === "unified_support_ticket") {
    const res = await axios.get(`${API}/msg/conversations/${selectedConv.id}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    msgs = res.data?.messages || [];
  } else if (selectedConv.type === "staff_chat" || selectedConv.type === "admin_user_chat") {
    const res = await axios.get(`${API}/msg/conversations/${selectedConv.id}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    msgs = res.data?.messages || [];
  }
  
  return msgs;
};

// Send message
export const sendConversationMessage = async (token, selectedConv, content) => {
  if (selectedConv.type === "p2p_dispute" || selectedConv.type === "p2p_trade") {
    const tradeId = selectedConv.related_id || selectedConv.trade?.id || selectedConv.id;
    await axios.post(`${API}/admin/disputes/${tradeId}/message`,
      { content },
      { headers: { Authorization: `Bearer ${token}` } }
    );
  } else if (selectedConv.type === "merchant_application") {
    if (selectedConv.id && !selectedConv.id.startsWith("merchant_")) {
      await axios.post(`${API}/msg/conversations/${selectedConv.id}/send`,
        { content },
        { headers: { Authorization: `Bearer ${token}` } }
      );
    } else {
      await axios.post(`${API}/admin/merchant-chat/${selectedConv.data?.id}`,
        { message: content },
        { headers: { Authorization: `Bearer ${token}` } }
      );
    }
  } else if (selectedConv.type === "shop_application") {
    if (selectedConv.id && !selectedConv.id.startsWith("shop_")) {
      await axios.post(`${API}/msg/conversations/${selectedConv.id}/send`,
        { content },
        { headers: { Authorization: `Bearer ${token}` } }
      );
    } else {
      await axios.post(`${API}/admin/shop-application-chat/${selectedConv.data?.user_id}`,
        { message: content },
        { headers: { Authorization: `Bearer ${token}` } }
      );
    }
  } else if (selectedConv.type === "marketplace_guarantor" || selectedConv.type === "crypto_order") {
    await axios.post(`${API}/msg/conversations/${selectedConv.id}/send`,
      { content },
      { headers: { Authorization: `Bearer ${token}` } }
    );
  } else if (selectedConv.type === "support_ticket") {
    await axios.post(`${API}/admin/support/tickets/${selectedConv.data?.id}/message`,
      { content },
      { headers: { Authorization: `Bearer ${token}` } }
    );
  } else if (selectedConv.type === "unified_support_ticket") {
    await axios.post(`${API}/msg/conversations/${selectedConv.id}/send`,
      { content },
      { headers: { Authorization: `Bearer ${token}` } }
    );
  } else if (selectedConv.type === "staff_chat" || selectedConv.type === "admin_user_chat") {
    await axios.post(`${API}/msg/conversations/${selectedConv.id}/send`,
      { content },
      { headers: { Authorization: `Bearer ${token}` } }
    );
  }
};

// Fetch archived conversations
export const fetchArchivedConversations = async (token) => {
  const res = await axios.get(`${API}/msg/admin/archived`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return res.data || [];
};

// Fetch staff list
export const fetchStaff = async (token) => {
  const res = await axios.get(`${API}/msg/admin/staff-list`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return res.data || [];
};

// Search conversations
export const searchConversations = async (token, query) => {
  const res = await axios.get(`${API}/msg/admin/search`, {
    params: { q: query },
    headers: { Authorization: `Bearer ${token}` }
  });
  return res.data || [];
};

// Add staff to conversation
export const addStaffToConversation = async (token, convId, staffId) => {
  await axios.post(`${API}/msg/conversations/${convId}/add-staff`, 
    { staff_id: staffId },
    { headers: { Authorization: `Bearer ${token}` } }
  );
};

// Leave conversation
export const leaveConversation = async (token, selectedConv) => {
  if (selectedConv.type === "support_ticket" && selectedConv.id.startsWith("ticket_")) {
    const ticketId = selectedConv.related_id || selectedConv.data?.id;
    await axios.post(`${API}/admin/support/tickets/${ticketId}/leave`, {}, {
      headers: { Authorization: `Bearer ${token}` }
    });
  } else {
    let convId = selectedConv.id;
    if (convId.includes("_") && selectedConv.related_id) {
      convId = selectedConv.related_id;
    }
    await axios.post(`${API}/msg/conversations/${convId}/leave`, {}, {
      headers: { Authorization: `Bearer ${token}` }
    });
  }
};

// Delete conversation
export const deleteConversation = async (token, convId) => {
  await axios.delete(`${API}/msg/conversations/${convId}`, {
    headers: { Authorization: `Bearer ${token}` }
  });
};

// Fetch commission settings
export const fetchCommissions = async (token) => {
  const res = await axios.get(`${API}/super-admin/commissions/all`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return res.data;
};

// Templates API
export const fetchTemplates = async (token, category = null) => {
  const url = category ? `${API}/staff/templates?category=${category}` : `${API}/staff/templates`;
  const res = await axios.get(url, { headers: { Authorization: `Bearer ${token}` } });
  return res.data || [];
};

export const createTemplate = async (token, data) => {
  await axios.post(`${API}/staff/templates`, data, { headers: { Authorization: `Bearer ${token}` } });
};

export const updateTemplate = async (token, templateId, data) => {
  await axios.put(`${API}/staff/templates/${templateId}`, data, { headers: { Authorization: `Bearer ${token}` } });
};

export const deleteTemplate = async (token, templateId) => {
  await axios.delete(`${API}/staff/templates/${templateId}`, { headers: { Authorization: `Bearer ${token}` } });
};

// User chats API
export const fetchUserChats = async (token) => {
  const res = await axios.get(`${API}/admin/user-chats`, { headers: { Authorization: `Bearer ${token}` } });
  return res.data || [];
};

export const createUserChat = async (token, data) => {
  await axios.post(`${API}/admin/user-chats`, data, { headers: { Authorization: `Bearer ${token}` } });
};

export const searchUsers = async (token, query) => {
  const [traders, merchants] = await Promise.all([
    axios.get(`${API}/admin/traders`, { headers: { Authorization: `Bearer ${token}` } }),
    axios.get(`${API}/admin/merchants`, { headers: { Authorization: `Bearer ${token}` } })
  ]);
  const results = [];
  const searchLower = query.toLowerCase();
  (traders.data || []).forEach(t => {
    const searchStr = `${t.nickname || ""} ${t.login || ""}`.toLowerCase();
    if (searchStr.includes(searchLower)) {
      results.push({ id: t.id, name: t.nickname || t.login, login: t.login, type: "trader" });
    }
  });
  (merchants.data || []).forEach(m => {
    const searchStr = `${m.merchant_name || ""} ${m.nickname || ""} ${m.login || ""}`.toLowerCase();
    if (searchStr.includes(searchLower)) {
      results.push({ id: m.id, name: m.merchant_name || m.nickname || m.login, login: m.login, type: "merchant" });
    }
  });
  return results.slice(0, 10);
};
