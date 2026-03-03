import React, { useState, useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import {
  MessageCircle, Scale, ArrowDownRight, Briefcase, Shield, Store,
  HelpCircle, Send, Users, XCircle, Search, Archive, Check, X,
  AlertTriangle, Clock, CheckCircle, Percent, FileText, ChevronRight,
  ChevronLeft, Settings, Plus, Trash2, Edit, Copy, User, RefreshCw,
  UserPlus, DollarSign, Lock, History, PlusCircle, UserCog, LogOut, Loader
} from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { Badge, LoadingSpinner, PageHeader } from "@/components/admin/SharedComponents";

function UnifiedMessagesHub() {
  const { token, user } = useAuth();
  const location = useLocation();
  const adminRole = user?.admin_role || "admin";
  
  // Handle navigation state (e.g., from P2P Trades clicking on a dispute)
  const initialCategory = location.state?.category || "all";
  const targetTradeId = location.state?.tradeId || null;
  
  const [activeCategory, setActiveCategory] = useState(initialCategory);
  const [conversations, setConversations] = useState([]);
  const [conversationsKey, setConversationsKey] = useState(0);
  const [selectedConv, setSelectedConv] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [showArchive, setShowArchive] = useState(false);
  const [archivedConvs, setArchivedConvs] = useState([]);
  const [staffList, setStaffList] = useState([]);
  const [showStaffModal, setShowStaffModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  // User chat state
  const [showCreateUserChat, setShowCreateUserChat] = useState(false);
  const [userChatTarget, setUserChatTarget] = useState(null);
  const [userChatSubject, setUserChatSubject] = useState("");
  const [userChats, setUserChats] = useState([]);
  const [userSearchQuery, setUserSearchQuery] = useState("");
  const [userSearchResults, setUserSearchResults] = useState([]);
  const messagesEndRef = useRef(null);
  // Commission modal state
  const [showCommissionModal, setShowCommissionModal] = useState(false);
  const [commissionValue, setCommissionValue] = useState("");
  const [commissionType, setCommissionType] = useState(null); // "merchant" or "shop"
  const [commissionSettings, setCommissionSettings] = useState(null);
  const [commissionTargetData, setCommissionTargetData] = useState(null); // Store conv data when opening modal
  
  // Message templates (auto-messages) state
  const [showTemplatesModal, setShowTemplatesModal] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [newTemplateTitle, setNewTemplateTitle] = useState("");
  const [newTemplateContent, setNewTemplateContent] = useState("");
  const [templateCategory, setTemplateCategory] = useState("general");

  // Shop categories mapping (English -> Russian)
  const SHOP_CATEGORIES = {
    accounts: "Аккаунты",
    software: "Софт",
    databases: "Базы данных",
    tools: "Инструменты",
    guides: "Гайды и схемы",
    keys: "Ключи",
    financial: "Финансовое",
    templates: "Шаблоны",
    other: "Другое"
  };
  const getCategoryLabel = (cat) => SHOP_CATEGORIES[cat] || cat;

  // Role colors per spec
  const ROLE_CONFIG = {
    user: { color: 'bg-white text-black border border-gray-300', name: 'Пользователь', marker: 'bg-white border border-gray-400' },
    buyer: { color: 'bg-white text-black border border-gray-300', name: 'Покупатель', marker: 'bg-white border border-gray-400' },
    p2p_seller: { color: 'bg-white text-black border border-gray-300', name: 'Продавец 💱', marker: 'bg-white border border-gray-400' },
    shop_owner: { color: 'bg-white text-black border border-gray-300', name: '🏪 Магазин', marker: 'bg-[#8B5CF6]' },
    merchant: { color: 'bg-white text-black border border-gray-300', name: '🟠 Мерчант', marker: 'bg-[#F97316]' },
    mod_p2p: { color: 'bg-[#F59E0B] text-white', name: 'Модератор P2P', marker: 'bg-[#F59E0B]' },
    mod_market: { color: 'bg-[#F59E0B] text-white', name: '⚖️ Гарант', marker: 'bg-[#F59E0B]' },
    support: { color: 'bg-[#3B82F6] text-white', name: 'Поддержка', marker: 'bg-[#3B82F6]' },
    admin: { color: 'bg-[#EF4444] text-white', name: 'Администратор', marker: 'bg-[#EF4444]' },
    owner: { color: 'bg-[#EF4444] text-white', name: '👑 Владелец', marker: 'bg-[#EF4444]' },
    system: { color: 'bg-[#6B7280] text-white', name: 'Система', marker: 'bg-[#6B7280]' }
  };
  const getRoleInfo = (role) => ROLE_CONFIG[role] || ROLE_CONFIG.user;

  // Categories based on role
  const getCategories = () => {
    const baseCategories = [
      { key: "all", label: "Все", icon: MessageCircle, color: "text-white" }
    ];
    
    // P2P Moderator: disputes, crypto payouts, merchant apps
    if (adminRole === "mod_p2p" || adminRole === "owner" || adminRole === "admin") {
      baseCategories.push({ key: "p2p_dispute", label: "P2P Споры", icon: Scale, color: "text-[#EF4444]" });
      baseCategories.push({ key: "crypto_payout", label: "Выплаты", icon: ArrowDownRight, color: "text-[#10B981]" });
      baseCategories.push({ key: "merchant_app", label: "Заявки мерчантов", icon: Briefcase, color: "text-[#F97316]" });
    }
    
    // Marketplace Moderator (Guarantor): marketplace disputes, shop apps, guarantor orders
    if (adminRole === "mod_market" || adminRole === "owner" || adminRole === "admin") {
      baseCategories.push({ key: "guarantor", label: "Гарант-сделки", icon: Shield, color: "text-[#F59E0B]" });
      baseCategories.push({ key: "shop_app", label: "Заявки магазинов", icon: Store, color: "text-[#8B5CF6]" });
    }
    
    // Support: support tickets
    if (adminRole === "support" || adminRole === "owner" || adminRole === "admin") {
      baseCategories.push({ key: "support", label: "Поддержка", icon: HelpCircle, color: "text-[#3B82F6]" });
    }
    
    // Admin/Owner/Mods: write to users
    if (adminRole === "owner" || adminRole === "admin" || adminRole === "mod_p2p" || adminRole === "mod_market") {
      baseCategories.push({ key: "admin_to_user", label: "Пользователям", icon: Users, color: "text-[#71717A]" });
    }
    
    // All staff: show chats they were invited to
    baseCategories.push({ key: "invited", label: "Приглашённые", icon: UserPlus, color: "text-[#F59E0B]" });
    
    return baseCategories;
  };

  useEffect(() => {
    fetchConversations();
    const interval = setInterval(fetchConversations, 10000);
    return () => clearInterval(interval);
  }, [activeCategory]);

  // Auto-select conversation if coming from trades page with specific trade ID
  useEffect(() => {
    if (targetTradeId && conversations.length > 0 && !selectedConv) {
      const targetConv = conversations.find(c => 
        c.related_id === targetTradeId || c.id === targetTradeId || c.context_id === targetTradeId
      );
      if (targetConv) {
        setSelectedConv(targetConv);
      }
    }
  }, [targetTradeId, conversations, selectedConv]);

  useEffect(() => {
    if (selectedConv) {
      fetchMessages(selectedConv.id);
      const interval = setInterval(() => fetchMessages(selectedConv.id), 5000);
      return () => clearInterval(interval);
    }
  }, [selectedConv?.id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const fetchConversations = async () => {
    setLoading(true);
    try {
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
            category: "p2p_dispute",
            title: c.trade ? `Спор: ${c.trade.amount} USDT` : (c.title || "P2P Спор"),
            subtitle: c.trade ? `@${c.trade.buyer_nickname || "покупатель"} vs @${c.trade.seller_nickname || "продавец"}` : (c.subtitle || ""),
            type: "p2p_dispute"
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
      
      // Fetch merchant applications - first try unified conversations, then legacy
      if ((adminRole === "mod_p2p" || adminRole === "owner" || adminRole === "admin") &&
          (activeCategory === "all" || activeCategory === "merchant_app")) {
        try {
          // Try unified conversations first
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
            // Fallback to legacy
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
          // Fallback to legacy on error
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
      
      // Fetch shop applications - first try unified conversations, then legacy
      if ((adminRole === "mod_market" || adminRole === "owner" || adminRole === "admin") &&
          (activeCategory === "all" || activeCategory === "shop_app")) {
        try {
          // Try unified conversations first
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
            // Fallback to legacy - only get pending applications
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
          // Fallback to legacy on error - only get pending applications
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
      
      // Fetch guarantor orders (Marketplace with Guarantor)
      if ((adminRole === "mod_market" || adminRole === "owner" || adminRole === "admin") &&
          (activeCategory === "all" || activeCategory === "guarantor")) {
        try {
          const res = await axios.get(`${API}/msg/admin/guarantor-orders`, {
            headers: { Authorization: `Bearer ${token}` }
          });
          allConvs = [...allConvs, ...(res.data || []).map(c => ({
            ...c,
            category: "guarantor",
            title: c.title || "Гарант-сделка",
            subtitle: c.subtitle || "",
            type: "marketplace_guarantor"
          }))];
        } catch (e) { console.error(e); }
      }
      
      // Fetch support tickets (open and in_progress)
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

      // Fetch admin-to-user chats (for writing to users)
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
          setUserChats(res.data || []);
        } catch (e) { console.error(e); }
      }
      
      // Fetch invited chats (where current user was invited)
      if (activeCategory === "all" || activeCategory === "invited") {
        try {
          const res = await axios.get(`${API}/admin/invited-chats`, {
            headers: { Authorization: `Bearer ${token}` }
          });
          // Filter out chats already in admin_to_user to avoid duplicates
          const invitedChats = (res.data || []).filter(c => 
            !allConvs.some(existing => existing.id === c.id)
          );
          allConvs = [...allConvs, ...invitedChats.map(c => ({
            ...c,
            category: "invited"
          }))];
        } catch (e) { console.error(e); }
      }
      
      setConversations([...allConvs]);
      setConversationsKey(prev => prev + 1);
    } catch (error) {
      console.error("Error fetching conversations:", error);
    } finally {
      setLoading(false);
    }
  };

  const fetchMessages = async (convId) => {
    if (!selectedConv) return;
    
    try {
      let msgs = [];
      
      if (selectedConv.type === "p2p_dispute" || selectedConv.type === "p2p_trade") {
        // Use the conversation ID, not related_id
        const res = await axios.get(`${API}/msg/conversations/${selectedConv.id}`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        msgs = res.data?.messages || [];
      } else if (selectedConv.type === "merchant_application") {
        // First try unified conversations
        if (selectedConv.id && !selectedConv.id.startsWith("merchant_")) {
          const res = await axios.get(`${API}/msg/conversations/${selectedConv.id}`, {
            headers: { Authorization: `Bearer ${token}` }
          });
          msgs = res.data?.messages || [];
        } else {
          // Fallback to legacy API
          const res = await axios.get(`${API}/admin/merchant-chat/${selectedConv.data?.id}`, {
            headers: { Authorization: `Bearer ${token}` }
          });
          msgs = (res.data || []).map(m => ({
            ...m, content: m.message, sender_name: m.sender_login, sender_role: m.sender_type === "admin" ? m.sender_role : "merchant"
          }));
        }
      } else if (selectedConv.type === "shop_application") {
        // First try unified conversations  
        if (selectedConv.id && !selectedConv.id.startsWith("shop_")) {
          const res = await axios.get(`${API}/msg/conversations/${selectedConv.id}`, {
            headers: { Authorization: `Bearer ${token}` }
          });
          msgs = res.data?.messages || [];
        } else {
          // Fallback to legacy API
          const res = await axios.get(`${API}/admin/shop-application-chat/${selectedConv.data?.user_id}`, {
            headers: { Authorization: `Bearer ${token}` }
          });
          msgs = (res.data || []).map(m => ({
            ...m, content: m.message, sender_name: m.sender_login, sender_role: m.sender_type === "admin" ? m.sender_role : "shop_owner"
          }));
        }
      } else if (selectedConv.type === "marketplace_guarantor") {
        // Guarantor orders use unified conversations
        const res = await axios.get(`${API}/msg/conversations/${selectedConv.id}`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        msgs = res.data?.messages || [];
      } else if (selectedConv.type === "crypto_order") {
        // Crypto payout orders use unified conversations
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
      } else if (selectedConv.type === "staff_chat" || selectedConv.type === "admin_user_chat") {
        // Staff chats and user chats use unified messages
        const res = await axios.get(`${API}/msg/conversations/${selectedConv.id}`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        msgs = res.data?.messages || [];
      }
      
      setMessages(msgs);
    } catch (error) {
      console.error("Error fetching messages:", error);
    }
  };

  // Fetch archived conversations
  const fetchArchivedConvs = async () => {
    try {
      const res = await axios.get(`${API}/msg/admin/archived`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setArchivedConvs(res.data || []);
    } catch (error) {
      console.error("Error fetching archived:", error);
    }
  };

  // Fetch staff list for adding to conversation
  const fetchStaffList = async () => {
    try {
      const res = await axios.get(`${API}/msg/admin/staff-list`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setStaffList(res.data || []);
    } catch (error) {
      console.error("Error fetching staff:", error);
    }
  };

  // Search conversations
  const handleSearch = async (query) => {
    setSearchQuery(query);
    if (query.length < 2) {
      setSearchResults([]);
      setIsSearching(false);
      return;
    }
    setIsSearching(true);
    try {
      const res = await axios.get(`${API}/msg/admin/search`, {
        params: { q: query },
        headers: { Authorization: `Bearer ${token}` }
      });
      setSearchResults(res.data || []);
    } catch (error) {
      console.error("Search error:", error);
      setSearchResults([]);
    }
  };

  // ========== COMMISSION FUNCTIONS ==========
  const fetchCommissionSettings = async () => {
    try {
      const res = await axios.get(`${API}/super-admin/commissions/all`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setCommissionSettings(res.data);
    } catch (error) {
      console.error("Error fetching commission settings:", error);
    }
  };

  const openCommissionModal = async (type) => {
    await fetchCommissionSettings();
    setCommissionType(type);
    
    // IMPORTANT: Save the current selectedConv data for use when submitting
    setCommissionTargetData({
      user_id: selectedConv?.user_id || selectedConv?.data?.user_id,
      related_id: selectedConv?.related_id || selectedConv?.data?.id,
      data: selectedConv?.data
    });
    console.log("Opening commission modal with data:", {
      user_id: selectedConv?.user_id || selectedConv?.data?.user_id,
      related_id: selectedConv?.related_id || selectedConv?.data?.id
    });
    
    // Set default commission based on type
    if (type === "merchant") {
      const merchantType = selectedConv?.data?.merchant_type || "other";
      const key = `${merchantType}_commission`;
      setCommissionValue(commissionSettings?.[key] || 0.5);
    } else if (type === "shop") {
      setCommissionValue(commissionSettings?.shop_commission || 5);
    }
    setShowCommissionModal(true);
  };

  const handleApproveWithCommission = async () => {
    if (!commissionValue || isNaN(parseFloat(commissionValue))) {
      toast.error("Введите корректную комиссию");
      return;
    }

    const commission = parseFloat(commissionValue);
    
    try {
      if (commissionType === "merchant") {
        const merchantId = selectedConv.related_id || selectedConv.data?.id || selectedConv.data?.user_id;
        if (!merchantId) {
          toast.error("ID мерчанта не найден");
          return;
        }
        await axios.post(`${API}/admin/merchants/${merchantId}/approve`,
          { approved: true, custom_commission: commission },
          { headers: { Authorization: `Bearer ${token}` } }
        );
        toast.success(`Мерчант одобрен с комиссией ${commission}%`);
      } else if (commissionType === "shop") {
        // Use saved data from when modal was opened
        const userId = commissionTargetData?.user_id || commissionTargetData?.data?.user_id;
        const shopAppId = commissionTargetData?.related_id || commissionTargetData?.data?.id;
        
        console.log("=== SHOP APPROVAL DEBUG ===");
        console.log("commissionTargetData:", commissionTargetData);
        console.log("userId:", userId);
        console.log("shopAppId:", shopAppId);
        console.log("commission:", commission);
        
        if (!userId) {
          toast.error("ID пользователя не найден. Данные: " + JSON.stringify(commissionTargetData));
          return;
        }
        if (!shopAppId) {
          toast.error("ID заявки не найден");
          return;
        }
        
        // First set pending commission
        const commissionNum = parseFloat(commission) || 5;
        
        const commissionRes = await axios.post(`${API}/admin/shop-applications/commission/${userId}`,
          { commission: commissionNum },
          { headers: { Authorization: `Bearer ${token}` } }
        );
        console.log("Commission response:", commissionRes.data);
        
        // Then approve
        const approveRes = await axios.post(`${API}/admin/shop-applications/${shopAppId}/review?decision=approve`,
          { comment: `Комиссия: ${commissionNum}%` },
          { headers: { Authorization: `Bearer ${token}` } }
        );
        console.log("Approve response:", approveRes.data);
        
        toast.success(`Магазин одобрен с комиссией ${commissionNum}%`);
      }
      
      setShowCommissionModal(false);
      setCommissionValue("");
      setCommissionType(null);
      setCommissionTargetData(null);
      fetchConversations();
      setSelectedConv(null);
    } catch (error) {
      toast.error("Ошибка: " + (error.response?.data?.detail || error.message));
    }
  };

  // ========== USER CHAT FUNCTIONS ==========
  const fetchUserChats = async () => {
    try {
      const res = await axios.get(`${API}/admin/user-chats`, { headers: { Authorization: `Bearer ${token}` } });
      setUserChats(res.data || []);
    } catch (error) { console.error("Error fetching user chats:", error); }
  };

  const searchUsers = async (q) => {
    setUserSearchQuery(q);
    if (q.length < 2) { setUserSearchResults([]); return; }
    try {
      const [traders, merchants] = await Promise.all([
        axios.get(`${API}/admin/traders`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/admin/merchants`, { headers: { Authorization: `Bearer ${token}` } })
      ]);
      const results = [];
      const searchLower = q.toLowerCase();
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
      setUserSearchResults(results.slice(0, 10));
    } catch (error) { console.error("Search error:", error); }
  };

  const createUserChat = async () => {
    if (!userChatTarget) {
      toast.error("Выберите пользователя");
      return;
    }
    try {
      await axios.post(`${API}/admin/user-chats`, {
        user_id: userChatTarget.id,
        user_type: userChatTarget.type,
        subject: userChatSubject
      }, { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Чат создан");
      setShowCreateUserChat(false);
      setUserChatTarget(null);
      setUserChatSubject("");
      setUserSearchQuery("");
      fetchUserChats();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка создания чата");
    }
  };

  // ========== MESSAGE TEMPLATES (AUTO-MESSAGES) ==========
  const fetchTemplates = async (category = null) => {
    setTemplatesLoading(true);
    try {
      const url = category ? `${API}/staff/templates?category=${category}` : `${API}/staff/templates`;
      const res = await axios.get(url, { headers: { Authorization: `Bearer ${token}` } });
      setTemplates(res.data || []);
    } catch (error) { 
      console.error("Error fetching templates:", error); 
      setTemplates([]);
    } finally {
      setTemplatesLoading(false);
    }
  };

  const openTemplatesModal = (category = "general") => {
    setTemplateCategory(category);
    fetchTemplates(category);
    setShowTemplatesModal(true);
    setEditingTemplate(null);
    setNewTemplateTitle("");
    setNewTemplateContent("");
  };

  const createTemplate = async () => {
    if (!newTemplateTitle.trim() || !newTemplateContent.trim()) {
      toast.error("Заполните название и текст шаблона");
      return;
    }
    try {
      await axios.post(`${API}/staff/templates`, {
        title: newTemplateTitle,
        content: newTemplateContent,
        category: templateCategory
      }, { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Шаблон создан");
      setNewTemplateTitle("");
      setNewTemplateContent("");
      fetchTemplates(templateCategory);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка создания шаблона");
    }
  };

  const updateTemplate = async () => {
    if (!editingTemplate) return;
    if (!newTemplateTitle.trim() || !newTemplateContent.trim()) {
      toast.error("Заполните название и текст шаблона");
      return;
    }
    try {
      await axios.put(`${API}/staff/templates/${editingTemplate.id}`, {
        title: newTemplateTitle,
        content: newTemplateContent,
        category: templateCategory
      }, { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Шаблон обновлён");
      setEditingTemplate(null);
      setNewTemplateTitle("");
      setNewTemplateContent("");
      fetchTemplates(templateCategory);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка обновления");
    }
  };

  const deleteTemplate = async (templateId) => {
    if (!window.confirm("Удалить шаблон?")) return;
    try {
      await axios.delete(`${API}/staff/templates/${templateId}`, { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Шаблон удалён");
      fetchTemplates(templateCategory);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка удаления");
    }
  };

  const selectTemplate = (template) => {
    setNewMessage(template.content);
    setShowTemplatesModal(false);
    toast.success("Шаблон выбран");
  };

  const startEditTemplate = (template) => {
    setEditingTemplate(template);
    setNewTemplateTitle(template.title);
    setNewTemplateContent(template.content);
  };

  const cancelEditTemplate = () => {
    setEditingTemplate(null);
    setNewTemplateTitle("");
    setNewTemplateContent("");
  };

  // Leave conversation (exit from chat - it disappears from staff's list)
  const handleLeaveConversation = async () => {
    if (!selectedConv) return;
    if (!window.confirm("Вы уверены, что хотите выйти из чата? Чат исчезнет из вашего списка.")) return;
    
    try {
      // For support tickets - use separate endpoint
      if (selectedConv.type === "support_ticket") {
        const ticketId = selectedConv.related_id || selectedConv.data?.id;
        await axios.post(`${API}/admin/support/tickets/${ticketId}/leave`, {}, {
          headers: { Authorization: `Bearer ${token}` }
        });
      } else {
        // For unified conversations
        let convId = selectedConv.id;
        // For prefixed IDs like merchant_xxx, use related_id
        if (convId.includes("_") && selectedConv.related_id) {
          convId = selectedConv.related_id;
        }
        await axios.post(`${API}/msg/conversations/${convId}/leave`, {}, {
          headers: { Authorization: `Bearer ${token}` }
        });
      }
      
      toast.success("Вы вышли из чата");
      setSelectedConv(null);
      fetchConversations();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка выхода из чата");
    }
  };


  // Delete conversation (only for resolved/archived)
  const handleDeleteConversation = async (convId) => {
    if (!window.confirm("ВНИМАНИЕ! Удалить чат и все сообщения навсегда?\n\nЭто действие НЕОБРАТИМО!")) return;
    
    try {
      await axios.delete(`${API}/msg/conversations/${convId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Чат удалён");
      setSelectedConv(null);
      fetchArchivedConvs();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка удаления");
    }
  };

  // Add staff to conversation
  const handleAddStaff = async (staffId) => {
    if (!selectedConv) return;
    
    try {
      await axios.post(`${API}/msg/conversations/${selectedConv.id}/add-staff`, 
        { staff_id: staffId },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success("Сотрудник добавлен в чат");
      setShowStaffModal(false);
      fetchMessages(selectedConv.id);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка добавления");
    }
  };

  const sendMessage = async () => {
    if (!newMessage.trim() || !selectedConv) return;
    // Can't send to closed conversations
    if (selectedConv.status === "closed") {
      toast.error("Невозможно отправить сообщение в закрытый чат");
      return;
    }
    setSending(true);
    
    try {
      if (selectedConv.type === "p2p_dispute" || selectedConv.type === "p2p_trade") {
        await axios.post(`${API}/msg/conversations/${selectedConv.id}/send`,
          { content: newMessage },
          { headers: { Authorization: `Bearer ${token}` } }
        );
      } else if (selectedConv.type === "merchant_application") {
        // Try unified first
        if (selectedConv.id && !selectedConv.id.startsWith("merchant_")) {
          await axios.post(`${API}/msg/conversations/${selectedConv.id}/send`,
            { content: newMessage },
            { headers: { Authorization: `Bearer ${token}` } }
          );
        } else {
          await axios.post(`${API}/admin/merchant-chat/${selectedConv.data?.id}`,
            { message: newMessage },
            { headers: { Authorization: `Bearer ${token}` } }
          );
        }
      } else if (selectedConv.type === "shop_application") {
        if (selectedConv.id && !selectedConv.id.startsWith("shop_")) {
          await axios.post(`${API}/msg/conversations/${selectedConv.id}/send`,
            { content: newMessage },
            { headers: { Authorization: `Bearer ${token}` } }
          );
        } else {
          await axios.post(`${API}/admin/shop-application-chat/${selectedConv.data?.user_id}`,
            { message: newMessage },
            { headers: { Authorization: `Bearer ${token}` } }
          );
        }
      } else if (selectedConv.type === "marketplace_guarantor") {
        await axios.post(`${API}/msg/conversations/${selectedConv.id}/send`,
          { content: newMessage },
          { headers: { Authorization: `Bearer ${token}` } }
        );
      } else if (selectedConv.type === "crypto_order") {
        // Crypto payout orders
        await axios.post(`${API}/msg/conversations/${selectedConv.id}/send`,
          { content: newMessage },
          { headers: { Authorization: `Bearer ${token}` } }
        );
      } else if (selectedConv.type === "support_ticket") {
        await axios.post(`${API}/admin/support/tickets/${selectedConv.data?.id}/message`,
          { content: newMessage },
          { headers: { Authorization: `Bearer ${token}` } }
        );
      } else if (selectedConv.type === "staff_chat" || selectedConv.type === "admin_user_chat") {
        // Staff chats and user chats
        await axios.post(`${API}/msg/conversations/${selectedConv.id}/send`,
          { content: newMessage },
          { headers: { Authorization: `Bearer ${token}` } }
        );
      }
      
      setNewMessage("");
      fetchMessages(selectedConv.id);
    } catch (error) {
      toast.error("Ошибка отправки");
    } finally {
      setSending(false);
    }
  };

  // Decision actions
  const handleDecision = async (type, params) => {
    try {
      if (selectedConv.type === "p2p_dispute") {
        await axios.post(`${API}/msg/trade/${selectedConv.related_id}/resolve`,
          { decision: type, ...params },
          { headers: { Authorization: `Bearer ${token}` } }
        );
        toast.success("Решение принято");
      } else if (selectedConv.type === "merchant_application") {
        // Use related_id first, then data.id, then data.user_id
        const merchantId = selectedConv.related_id || selectedConv.data?.id || selectedConv.data?.user_id;
        if (!merchantId) {
          toast.error("ID мерчанта не найден");
          return;
        }
        if (type === "approve") {
          await axios.post(`${API}/admin/merchants/${merchantId}/approve`,
            { approved: true, commission: params.commission || 0.5 },
            { headers: { Authorization: `Bearer ${token}` } }
          );
        } else {
          await axios.post(`${API}/admin/merchants/${merchantId}/approve`,
            { approved: false, reason: params.reason },
            { headers: { Authorization: `Bearer ${token}` } }
          );
        }
        toast.success(type === "approve" ? "Мерчант одобрен" : "Заявка отклонена");
      } else if (selectedConv.type === "shop_application") {
        const shopAppId = selectedConv.related_id || selectedConv.data?.id;
        if (!shopAppId) {
          toast.error("ID заявки не найден");
          return;
        }
        // Use /review endpoint with decision parameter
        await axios.post(`${API}/admin/shop-applications/${shopAppId}/review?decision=${type}`,
          { comment: params.reason || "" },
          { headers: { Authorization: `Bearer ${token}` } }
        );
        toast.success(type === "approve" ? "Магазин одобрен" : "Заявка отклонена");
      } else if (selectedConv.type === "marketplace_guarantor") {
        // Guarantor decisions
        const orderId = selectedConv.related_id || selectedConv.data?.id;
        if (!orderId) {
          toast.error("ID заказа не найден");
          return;
        }
        await axios.post(`${API}/msg/guarantor/order/${orderId}/decision`,
          { decision_type: type, ...params },
          { headers: { Authorization: `Bearer ${token}` } }
        );
        toast.success("Решение гаранта принято");
      } else if (selectedConv.type === "support_ticket") {
        await axios.post(`${API}/admin/support/tickets/${selectedConv.data?.id}/status?status=${type}`,
          {}, { headers: { Authorization: `Bearer ${token}` } }
        );
        toast.success("Статус обновлён");
      }
      
      // Force refresh after decision - wait a bit for backend to update
      setSelectedConv(null);
      await new Promise(resolve => setTimeout(resolve, 300));
      await fetchConversations();
    } catch (error) {
      toast.error("Ошибка: " + (error.response?.data?.detail || error.message));
    }
  };

  const getCategoryIcon = (category) => {
    switch (category) {
      case "p2p_dispute": return Scale;
      case "merchant_app": return Briefcase;
      case "shop_app": return Store;
      case "support": return HelpCircle;
      case "guarantor": return Shield;
      default: return MessageCircle;
    }
  };

  const getCategoryColor = (category) => {
    switch (category) {
      case "p2p_dispute": return "text-[#EF4444]";
      case "merchant_app": return "text-[#F97316]";
      case "shop_app": return "text-[#8B5CF6]";
      case "support": return "text-[#3B82F6]";
      case "marketplace": return "text-[#8B5CF6]";
      default: return "text-[#71717A]";
    }
  };

  const categories = getCategories();
  const filteredConvs = activeCategory === "all" ? conversations : conversations.filter(c => c.category === activeCategory);

  return (
    <div className="space-y-4" data-testid="unified-messages-hub">
      <PageHeader 
        title="Центр сообщений" 
        subtitle={`${getRoleInfo(adminRole).name} • ${conversations.length} активных чатов`} 
      />
      
      {/* Category Tabs + Archive Button */}
      <div className="flex items-center justify-between gap-2 bg-[#121212] p-2 rounded-xl">
        <div className="flex items-center gap-1 overflow-x-auto">
          {categories.map(cat => {
            const count = cat.key === "all" ? conversations.length : conversations.filter(c => c.category === cat.key).length;
            return (
              <button
                key={cat.key}
                onClick={() => { setActiveCategory(cat.key); setSelectedConv(null); setShowArchive(false); }}
                className={`flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs whitespace-nowrap transition-all ${
                  activeCategory === cat.key && !showArchive
                    ? "bg-[#7C3AED] text-white" 
                    : "text-[#71717A] hover:bg-white/5"
                }`}
                data-testid={`category-${cat.key}`}
              >
                {cat.label}
                {count > 0 && (
                  <span className={`text-[10px] px-1 py-0.5 rounded-full ${
                    activeCategory === cat.key && !showArchive ? "bg-white/20" : "bg-white/10"
                  }`}>
                    {count}
                  </span>
                )}
              </button>
            );
          })}
        </div>
        
        {/* Action Buttons */}
        <div className="flex items-center gap-1 shrink-0">
          {/* Create User Chat Button */}
          {activeCategory === "admin_to_user" && (adminRole === "owner" || adminRole === "admin" || adminRole === "mod_p2p" || adminRole === "mod_market") && (
            <button
              onClick={() => setShowCreateUserChat(true)}
              className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs bg-[#7C3AED]/10 text-[#7C3AED] hover:bg-[#7C3AED]/20"
            >
              <PlusCircle className="w-3 h-3" />
              Новый
            </button>
          )}
          {/* Archive Toggle */}
          <button
            onClick={() => { 
              setShowArchive(!showArchive); 
              setSelectedConv(null);
              if (!showArchive) fetchArchivedConvs();
            }}
            className={`flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs transition-all ${
              showArchive ? "bg-[#52525B] text-white" : "text-[#71717A] hover:bg-white/5"
            }`}
            data-testid="archive-toggle"
          >
            <History className="w-3 h-3" />
            Архив
            {archivedConvs.length > 0 && showArchive && (
              <span className="text-[10px] px-1 py-0.5 rounded-full bg-white/20">{archivedConvs.length}</span>
            )}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 h-[calc(100vh-280px)]">
        {/* Conversations List */}
        <div className="bg-[#121212] border border-white/5 rounded-xl overflow-hidden flex flex-col">
          <div className="p-3 border-b border-white/5">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-white font-semibold text-sm">
                {isSearching && searchQuery ? `Поиск (${searchResults.length})` : showArchive ? `Архив (${archivedConvs.length})` : `Чаты (${filteredConvs.length})`}
              </h3>
              <Button variant="ghost" size="sm" onClick={showArchive ? fetchArchivedConvs : fetchConversations} className="h-7 w-7 p-0">
                <RefreshCw className="w-4 h-4 text-[#71717A]" />
              </Button>
            </div>
            {/* Search Input */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-[#52525B]" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => handleSearch(e.target.value)}
                placeholder="Поиск по никнейму, магазину..."
                className="w-full bg-white/5 border border-white/10 rounded-lg pl-9 pr-3 py-1.5 text-sm text-white placeholder-[#52525B] focus:outline-none focus:border-[#7C3AED]"
                data-testid="chat-search-input"
              />
              {searchQuery && (
                <button onClick={() => { setSearchQuery(""); setSearchResults([]); setIsSearching(false); }} className="absolute right-2 top-1/2 transform -translate-y-1/2 text-[#52525B] hover:text-white">
                  <XCircle className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
          <div className="flex-1 overflow-y-auto">
            {loading ? <LoadingSpinner /> : (isSearching && searchQuery ? searchResults : showArchive ? archivedConvs : filteredConvs).length === 0 ? (
              <div className="p-6 text-center">
                {isSearching && searchQuery ? (
                  <>
                    <Search className="w-10 h-10 text-[#52525B] mx-auto mb-3" />
                    <p className="text-[#71717A] text-sm">Ничего не найдено</p>
                  </>
                ) : showArchive ? (
                  <>
                    <History className="w-10 h-10 text-[#52525B] mx-auto mb-3" />
                    <p className="text-[#71717A] text-sm">Архив пуст</p>
                  </>
                ) : (
                  <>
                    <MessageCircle className="w-10 h-10 text-[#52525B] mx-auto mb-3" />
                    <p className="text-[#71717A] text-sm">Нет чатов</p>
                  </>
                )}
              </div>
            ) : (
              (isSearching && searchQuery ? searchResults : showArchive ? archivedConvs : filteredConvs).map(conv => {
                const Icon = getCategoryIcon(conv.category || conv.type);
                const iconColor = getCategoryColor(conv.category || conv.type);
                const isSelected = selectedConv?.id === conv.id;
                const isResolved = conv.resolved || conv.archived;
                const isLeftByMe = conv.is_left_by_me;
                const isCryptoDispute = conv.type === "crypto_order" && conv.status === "dispute";
                
                return (
                  <div
                    key={conv.id}
                    onClick={() => setSelectedConv(conv)}
                    className={`p-3 border-b border-white/5 cursor-pointer transition-colors ${
                      isSelected ? "bg-[#7C3AED]/10 border-l-2 border-l-[#7C3AED]" : 
                      isCryptoDispute ? "bg-[#EF4444]/10 border-l-2 border-l-[#EF4444] hover:bg-[#EF4444]/20" :
                      "hover:bg-white/5"
                    } ${isResolved || isLeftByMe ? "opacity-70" : ""}`}
                    data-testid={`conv-${conv.id}`}
                  >
                    <div className="flex items-start gap-2">
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                        isCryptoDispute ? "bg-[#EF4444]/20" : `${iconColor.replace("text-", "bg-")}/20`
                      }`}>
                        <Icon className={`w-4 h-4 ${isCryptoDispute ? "text-[#EF4444]" : iconColor}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className={`text-sm font-medium truncate ${isCryptoDispute ? "text-[#EF4444]" : "text-white"}`}>{conv.title}</span>
                          {(conv.status === "disputed" || conv.status === "dispute") && (
                            <span className="bg-[#EF4444] text-white text-[9px] px-1.5 py-0.5 rounded animate-pulse">🔴 СПОР</span>
                          )}
                          {isResolved && (
                            <span className="bg-[#10B981] text-white text-[9px] px-1.5 py-0.5 rounded">РЕШЁН</span>
                          )}
                          {isLeftByMe && !isResolved && (
                            <span className="bg-[#52525B] text-white text-[9px] px-1.5 py-0.5 rounded">ВЫШЛИ</span>
                          )}
                        </div>
                        <p className={`text-xs truncate ${isCryptoDispute ? "text-[#EF4444]/70" : "text-[#71717A]"}`}>{conv.subtitle}</p>
                        {/* Show category label in archive */}
                        {showArchive && conv.category_label && (
                          <p className="text-[#F59E0B]/70 text-[10px] mt-0.5">{conv.category_label}</p>
                        )}
                        {conv.resolved_at && (
                          <p className="text-[#10B981]/70 text-[10px] mt-0.5">
                            Решён: {new Date(conv.resolved_at).toLocaleDateString("ru-RU")}
                          </p>
                        )}
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        {conv.unread_count > 0 && (
                          <span className="bg-[#EF4444] text-white text-[10px] px-1.5 py-0.5 rounded-full">
                            {conv.unread_count}
                          </span>
                        )}
                        {/* Delete button for archived/resolved chats */}
                        {showArchive && (isResolved || isLeftByMe) && (
                          <button
                            onClick={(e) => { e.stopPropagation(); handleDeleteConversation(conv.id); }}
                            className="text-[#EF4444]/60 hover:text-[#EF4444] p-1"
                            title="Удалить чат"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Chat & Actions */}
        <div className="lg:col-span-2 bg-[#121212] border border-white/5 rounded-xl overflow-hidden flex flex-col">
          {selectedConv ? (
            <>
              {/* Header */}
              <div className={`p-3 border-b border-white/5 ${selectedConv.status === "disputed" ? "bg-[#EF4444]/5" : selectedConv.status === "closed" ? "bg-[#52525B]/5" : ""}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${getCategoryColor(selectedConv.category || selectedConv.type).replace("text-", "bg-")}/20`}>
                      {React.createElement(getCategoryIcon(selectedConv.category || selectedConv.type), { className: `w-5 h-5 ${getCategoryColor(selectedConv.category || selectedConv.type)}` })}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-white font-semibold text-sm">{selectedConv.title}</h3>
                        {selectedConv.status === "closed" && (
                          <span className="bg-[#52525B] text-white text-[9px] px-1.5 py-0.5 rounded">ЗАКРЫТ</span>
                        )}
                        {selectedConv.status === "dispute" && selectedConv.type === "crypto_order" && (
                          <span className="bg-[#EF4444] text-white text-[9px] px-1.5 py-0.5 rounded animate-pulse">🔴 СПОР</span>
                        )}
                      </div>
                      <p className="text-[#71717A] text-xs">{selectedConv.subtitle}</p>
                      {/* Show merchant and buyer for crypto orders */}
                      {selectedConv.type === "crypto_order" && (
                        <div className="flex items-center gap-3 mt-1 text-[10px]">
                          <span className="text-[#F97316]">💼 Мерчант: @{selectedConv.order?.merchant_nickname || "неизвестен"}</span>
                          <span className="text-[#10B981]">🛒 Покупатель: @{selectedConv.order?.buyer_nickname || "неизвестен"}</span>
                        </div>
                      )}
                      {/* Show categories for shop applications */}
                      {selectedConv.type === "shop_application" && selectedConv.data?.categories && selectedConv.data.categories.length > 0 && (
                        <p className="text-[#8B5CF6] text-xs mt-0.5">
                          📁 {selectedConv.data.categories.map(c => getCategoryLabel(c)).join(", ")}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    {/* Add Staff Button */}
                    {selectedConv.status !== "closed" && (
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        onClick={() => { fetchStaffList(); setShowStaffModal(true); }}
                        className="h-7 px-2 text-[#8B5CF6] hover:bg-[#8B5CF6]/10"
                        title="Добавить персонал"
                      >
                        <UserCog className="w-4 h-4 mr-1" />
                        <span className="text-xs">+</span>
                      </Button>
                    )}
                    {/* Leave Chat Button */}
                    {!selectedConv.resolved && (
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        onClick={handleLeaveConversation}
                        className="h-7 px-2 text-[#52525B] hover:bg-[#52525B]/10 hover:text-white"
                        title="Выйти из чата"
                      >
                        <LogOut className="w-4 h-4" />
                      </Button>
                    )}
                    {/* Delete Button for resolved/archived chats */}
                    {(selectedConv.resolved || selectedConv.archived) && (
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        onClick={() => handleDeleteConversation(selectedConv.id)}
                        className="h-7 px-2 text-[#EF4444] hover:bg-[#EF4444]/10"
                        title="Удалить чат"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    )}
                    <Button variant="ghost" size="sm" onClick={() => setSelectedConv(null)} className="h-7 w-7 p-0">
                      <XCircle className="w-4 h-4 text-[#71717A]" />
                    </Button>
                  </div>
                </div>
              </div>

              {/* Resolved chat indicator */}
              {selectedConv.resolved && (
                <div className="p-2 border-b border-white/5 bg-[#10B981]/10">
                  <div className="flex items-center gap-2 text-xs text-[#10B981]">
                    <CheckCircle className="w-4 h-4" />
                    <span>Вопрос решён</span>
                    {selectedConv.resolved_at && (
                      <span>• {new Date(selectedConv.resolved_at).toLocaleDateString("ru-RU")}</span>
                    )}
                  </div>
                </div>
              )}

              {/* Decision Buttons */}
              {/* Assigned moderator indicator */}
              {selectedConv.assigned_to && (
                <div className="p-2 border-b border-white/5 bg-[#8B5CF6]/5">
                  <div className="flex items-center gap-2 text-xs text-[#8B5CF6]">
                    <UserCog className="w-4 h-4" />
                    <span>Взято в работу: {selectedConv.assigned_to_name || "Модератор"}</span>
                    {selectedConv.assigned_at && (
                      <span className="text-[#71717A]">• {new Date(selectedConv.assigned_at).toLocaleString("ru-RU", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" })}</span>
                    )}
                  </div>
                </div>
              )}

              {(selectedConv.status === "pending" || selectedConv.status === "pending_confirmation" || selectedConv.status === "pending_payment" || selectedConv.status === "disputed" || selectedConv.status === "dispute" || selectedConv.status === "open" || selectedConv.status === "active" || selectedConv.status === "paid" || selectedConv.status === "pending_delivery") && (
                <div className="p-3 border-b border-white/5 bg-[#0A0A0A]">
                  <div className="text-[10px] text-[#52525B] mb-2">ДЕЙСТВИЯ:</div>
                  <div className="flex flex-wrap gap-2">
                    {selectedConv.type === "p2p_dispute" && (
                      <>
                        <button onClick={() => openTemplatesModal("dispute")} className="px-3 py-1.5 bg-[#8B5CF6]/10 text-[#8B5CF6] rounded-lg text-xs hover:bg-[#8B5CF6]/20" data-testid="auto-message-dispute-btn">
                          ⚡ Авто-сообщение
                        </button>
                        <button onClick={() => handleDecision("refund_buyer", {})} className="px-3 py-1.5 bg-[#10B981]/10 text-[#10B981] rounded-lg text-xs hover:bg-[#10B981]/20" data-testid="refund-buyer-btn">
                          💰 В пользу покупателя
                        </button>
                        <button onClick={() => handleDecision("cancel_dispute", {})} className="px-3 py-1.5 bg-[#EF4444]/10 text-[#EF4444] rounded-lg text-xs hover:bg-[#EF4444]/20" data-testid="cancel-dispute-btn">
                          💰 Отменить
                        </button>
                      </>
                    )}
                    {selectedConv.type === "merchant_application" && (
                      <>
                        <button onClick={() => openTemplatesModal("merchant_app")} className="px-3 py-1.5 bg-[#8B5CF6]/10 text-[#8B5CF6] rounded-lg text-xs hover:bg-[#8B5CF6]/20" data-testid="auto-message-btn">
                          ⚡ Авто-сообщение
                        </button>
                        {/* Only admin/owner can approve */}
                        {(adminRole === "owner" || adminRole === "admin") && (
                          <button onClick={() => openCommissionModal("merchant")} className="px-3 py-1.5 bg-[#10B981]/10 text-[#10B981] rounded-lg text-xs hover:bg-[#10B981]/20" data-testid="approve-merchant-btn">
                            ✅ Одобрить
                          </button>
                        )}
                        {/* All staff can reject */}
                        <button onClick={() => handleDecision("reject", { reason: prompt("Причина отказа:") })} className="px-3 py-1.5 bg-[#EF4444]/10 text-[#EF4444] rounded-lg text-xs hover:bg-[#EF4444]/20" data-testid="reject-merchant-btn">
                          ❌ Отклонить
                        </button>
                      </>
                    )}
                    {selectedConv.type === "shop_application" && (
                      <>
                        <button onClick={() => openTemplatesModal("shop_app")} className="px-3 py-1.5 bg-[#8B5CF6]/10 text-[#8B5CF6] rounded-lg text-xs hover:bg-[#8B5CF6]/20" data-testid="auto-message-shop-btn">
                          ⚡ Авто-сообщение
                        </button>
                        {/* Only admin/owner can approve */}
                        {(adminRole === "owner" || adminRole === "admin") && (
                          <button onClick={() => openCommissionModal("shop")} className="px-3 py-1.5 bg-[#10B981]/10 text-[#10B981] rounded-lg text-xs hover:bg-[#10B981]/20" data-testid="approve-shop-btn">
                            ✅ Одобрить
                          </button>
                        )}
                        {/* All staff can reject */}
                        <button onClick={() => handleDecision("reject", { reason: prompt("Причина отказа:") })} className="px-3 py-1.5 bg-[#EF4444]/10 text-[#EF4444] rounded-lg text-xs hover:bg-[#EF4444]/20" data-testid="reject-shop-btn">
                          ❌ Отклонить
                        </button>
                      </>
                    )}
                    {selectedConv.type === "marketplace_guarantor" && (
                      <>
                        <button onClick={() => openTemplatesModal("guarantor")} className="px-3 py-1.5 bg-[#8B5CF6]/10 text-[#8B5CF6] rounded-lg text-xs hover:bg-[#8B5CF6]/20" data-testid="auto-message-guarantor-btn">
                          ⚡ Авто-сообщение
                        </button>
                        <button onClick={() => {
                          const hours = prompt("Срок (часов):", "24");
                          if (hours) axios.post(`${API}/msg/guarantor/order/${selectedConv.related_id}/set-deadline`, 
                            { deadline_type: "response", deadline_hours: parseInt(hours) }, 
                            { headers: { Authorization: `Bearer ${token}` } }
                          ).then(() => { toast.success("Дедлайн установлен"); fetchMessages(selectedConv.id); });
                        }} className="px-3 py-1.5 bg-[#8B5CF6]/10 text-[#8B5CF6] rounded-lg text-xs hover:bg-[#8B5CF6]/20">
                          ⏱️ Установить дедлайн
                        </button>
                        <button onClick={() => handleDecision("refund_full", { reason: prompt("Причина:") || "Возврат по решению гаранта" })} className="px-3 py-1.5 bg-[#10B981]/10 text-[#10B981] rounded-lg text-xs hover:bg-[#10B981]/20">
                          💰 Полный возврат
                        </button>
                        <button onClick={() => {
                          const amount = prompt("Сумма частичного возврата (USDT):");
                          if (amount) handleDecision("refund_partial", { amount: parseFloat(amount), reason: prompt("Причина:") || "" });
                        }} className="px-3 py-1.5 bg-[#F59E0B]/10 text-[#F59E0B] rounded-lg text-xs hover:bg-[#F59E0B]/20">
                          💸 Частичный возврат
                        </button>
                        <button onClick={() => handleDecision("release_seller", { reason: prompt("Примечание:") || "" })} className="px-3 py-1.5 bg-[#F97316]/10 text-[#F97316] rounded-lg text-xs hover:bg-[#F97316]/20">
                          ✅ Выплатить продавцу
                        </button>
                        <button onClick={() => {
                          const days = prompt("Срок замены (дней):", "3");
                          if (days) handleDecision("demand_replace", { deadline_days: parseInt(days), reason: prompt("Причина:") || "Товар не соответствует описанию" });
                        }} className="px-3 py-1.5 bg-[#EF4444]/10 text-[#EF4444] rounded-lg text-xs hover:bg-[#EF4444]/20">
                          🔄 Требовать замену
                        </button>
                      </>
                    )}
                    {selectedConv.type === "crypto_order" && selectedConv.status !== "dispute" && selectedConv.status !== "completed" && selectedConv.status !== "cancelled" && (
                      <>
                        <button 
                          onClick={async () => {
                            try {
                              await axios.post(`${API}/admin/crypto-payouts/${selectedConv.related_id}/update-status`,
                                { status: "completed" },
                                { headers: { Authorization: `Bearer ${token}` } }
                              );
                              toast.success("Сделка завершена! Монеты переведены покупателю.");
                              fetchMessages(selectedConv.id);
                              fetchConversations();
                            } catch (e) {
                              toast.error("Ошибка");
                            }
                          }} 
                          className="px-3 py-1.5 bg-[#10B981]/20 text-[#10B981] rounded-lg text-xs hover:bg-[#10B981]/30 font-medium"
                          data-testid="complete-payout-btn"
                        >
                          💰 Завершить сделку
                        </button>
                        <button 
                          onClick={async () => {
                            const reason = prompt("Причина отмены:");
                            if (!reason) return;
                            try {
                              await axios.post(`${API}/admin/crypto-payouts/${selectedConv.related_id}/update-status`,
                                { status: "cancelled" },
                                { headers: { Authorization: `Bearer ${token}` } }
                              );
                              toast.success("Сделка отменена");
                              fetchMessages(selectedConv.id);
                              fetchConversations();
                            } catch (e) {
                              toast.error("Ошибка");
                            }
                          }}
                          className="px-3 py-1.5 bg-[#EF4444]/10 text-[#EF4444] rounded-lg text-xs hover:bg-[#EF4444]/20"
                          data-testid="cancel-payout-btn"
                        >
                          ❌ Отменить
                        </button>
                      </>
                    )}
                    {selectedConv.type === "crypto_order" && selectedConv.status === "dispute" && (
                      <>
                        <button 
                          onClick={async () => {
                            if (!confirm("Выплатить USDT мерчанту с баланса платформы?")) return;
                            try {
                              await axios.post(`${API}/admin/crypto-payouts/${selectedConv.related_id}/resolve-dispute`,
                                { winner: "merchant" },
                                { headers: { Authorization: `Bearer ${token}` } }
                              );
                              toast.success("Спор решён в пользу мерчанта. USDT выплачены.");
                              fetchMessages(selectedConv.id);
                              fetchConversations();
                            } catch (e) {
                              toast.error("Ошибка");
                            }
                          }} 
                          className="px-3 py-1.5 bg-[#F97316]/20 text-[#F97316] rounded-lg text-xs hover:bg-[#F97316]/30 font-medium"
                        >
                          💼 Мерчант выиграл
                        </button>
                        <button 
                          onClick={async () => {
                            if (!confirm("USDT останутся на платформе?")) return;
                            try {
                              await axios.post(`${API}/admin/crypto-payouts/${selectedConv.related_id}/resolve-dispute`,
                                { winner: "platform" },
                                { headers: { Authorization: `Bearer ${token}` } }
                              );
                              toast.success("Спор решён в пользу платформы");
                              fetchMessages(selectedConv.id);
                              fetchConversations();
                            } catch (e) {
                              toast.error("Ошибка");
                            }
                          }}
                          className="px-3 py-1.5 bg-[#3B82F6]/10 text-[#3B82F6] rounded-lg text-xs hover:bg-[#3B82F6]/20"
                        >
                          🏢 Платформа выиграла
                        </button>
                      </>
                    )}
                    {selectedConv.type === "support_ticket" && (
                      <>
                        <button onClick={() => openTemplatesModal("support")} className="px-3 py-1.5 bg-[#8B5CF6]/10 text-[#8B5CF6] rounded-lg text-xs hover:bg-[#8B5CF6]/20" data-testid="auto-message-support-btn">
                          ⚡ Авто-сообщение
                        </button>
                        <button onClick={() => { setNewMessage("📋 Предоставьте дополнительную информацию"); }} className="px-3 py-1.5 bg-[#3B82F6]/10 text-[#3B82F6] rounded-lg text-xs hover:bg-[#3B82F6]/20">
                          📋 Запросить информацию
                        </button>
                        <button onClick={() => handleDecision("resolved", {})} className="px-3 py-1.5 bg-[#10B981]/10 text-[#10B981] rounded-lg text-xs hover:bg-[#10B981]/20">
                          ✅ Решить
                        </button>
                        <button onClick={() => handleDecision("closed", {})} className="px-3 py-1.5 bg-[#52525B]/10 text-[#71717A] rounded-lg text-xs hover:bg-[#52525B]/20">
                          🔒 Закрыть
                        </button>
                      </>
                    )}
                  </div>
                </div>
              )}

              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-3 space-y-3">
                {messages.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full">
                    <MessageCircle className="w-10 h-10 text-[#52525B] mb-3" />
                    <p className="text-[#71717A] text-sm">Нет сообщений</p>
                  </div>
                ) : (
                  messages.map((msg, idx) => {
                    const isAdmin = msg.sender_type === "admin" || ["admin", "owner", "mod_p2p", "mod_market", "support"].includes(msg.sender_role);
                    const isSystem = msg.is_system || msg.sender_role === "system";
                    const roleInfo = getRoleInfo(msg.sender_role);
                    
                    if (isSystem) {
                      return (
                        <div key={idx} className="flex justify-center">
                          <div className="bg-[#6B7280]/20 text-[#A1A1AA] text-xs px-3 py-1 rounded-full max-w-[80%] text-center">
                            {msg.content}
                          </div>
                        </div>
                      );
                    }

                    return (
                      <div key={idx} className={`flex ${isAdmin ? "justify-end" : "justify-start"}`}>
                        <div className="max-w-[75%]">
                          {!isAdmin && (
                            <div className="flex items-center gap-1.5 text-[10px] text-[#71717A] mb-0.5 ml-2">
                              <div className={`w-2 h-2 rounded-full ${roleInfo.marker}`}></div>
                              <span>{roleInfo.name}</span>
                            </div>
                          )}
                          <div className={`p-2.5 rounded-xl ${isAdmin ? roleInfo.color : "bg-white text-black border border-gray-300"}`}>
                            <p className="text-xs whitespace-pre-wrap">{msg.content}</p>
                            <div className={`text-[10px] mt-1 ${isAdmin ? "text-white/60" : "text-gray-500"}`}>
                              {new Date(msg.created_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Input */}
              <div className="p-3 border-t border-white/5">
                <div className="flex gap-2">
                  <Input
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    onKeyPress={(e) => e.key === "Enter" && sendMessage()}
                    placeholder="Написать сообщение..."
                    className="flex-1 bg-[#0A0A0A] border-white/10 text-white h-9 rounded-lg"
                    data-testid="message-input"
                  />
                  <Button onClick={sendMessage} disabled={sending || !newMessage.trim()} className="bg-[#7C3AED] hover:bg-[#6D28D9] h-9 px-4" data-testid="send-btn">
                    {sending ? <Loader className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                  </Button>
                </div>
              </div>

              {/* Role legend */}
              <div className="px-3 py-2 border-t border-white/5 bg-[#0A0A0A]">
                <div className="flex flex-wrap gap-3 text-[10px] text-[#52525B]">
                  <span className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-white border border-gray-400" /> Пользователь</span>
                  <span className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-[#F97316]" /> Мерчант</span>
                  <span className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-[#8B5CF6]" /> Магазин</span>
                  <span className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-[#F59E0B]" /> Модератор</span>
                  <span className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-[#3B82F6]" /> Поддержка</span>
                  <span className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-[#EF4444]" /> Админ</span>
                </div>
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <MessageCircle className="w-12 h-12 text-[#52525B] mx-auto mb-3" />
                <p className="text-[#71717A]">Выберите чат</p>
                <p className="text-[#52525B] text-xs mt-1">для просмотра и решения</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Staff Selection Modal */}
      {/* Commission Modal */}
      {showCommissionModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4" data-testid="commission-modal">
          <div className="bg-[#121212] border border-white/10 rounded-2xl w-full max-w-sm">
            <div className="p-4 border-b border-white/5 flex items-center justify-between">
              <h3 className="text-white font-semibold">
                {commissionType === "merchant" ? "💼 Комиссия мерчанта" : "🏪 Комиссия магазина"}
              </h3>
              <button onClick={() => { setShowCommissionModal(false); setCommissionValue(""); setCommissionType(null); }} className="text-[#71717A] hover:text-white">
                <XCircle className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="text-[#71717A] text-xs mb-2 block">
                  Установите комиссию для {commissionType === "merchant" ? "мерчанта" : "магазина"} (%)
                </label>
                <div className="flex items-center gap-2">
                  <Input
                    type="number"
                    step="0.1"
                    min="0"
                    max="100"
                    value={commissionValue}
                    onChange={(e) => setCommissionValue(e.target.value)}
                    placeholder="Введите комиссию"
                    className="flex-1 bg-white/5 border-white/10 text-white text-center text-lg"
                    data-testid="commission-input"
                  />
                  <span className="text-white text-lg font-bold">%</span>
                </div>
                {commissionSettings && (
                  <div className="mt-3 p-3 bg-white/5 rounded-lg">
                    <p className="text-[#71717A] text-xs mb-2">Глобальные комиссии:</p>
                    {commissionType === "merchant" ? (
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <span className="text-[#71717A]">Казино:</span><span className="text-white">{commissionSettings.casino_commission}%</span>
                        <span className="text-[#71717A]">Магазин:</span><span className="text-white">{commissionSettings.shop_commission}%</span>
                        <span className="text-[#71717A]">Стрим:</span><span className="text-white">{commissionSettings.stream_commission}%</span>
                        <span className="text-[#71717A]">Другое:</span><span className="text-white">{commissionSettings.other_commission}%</span>
                      </div>
                    ) : (
                      <div className="text-xs">
                        <span className="text-[#71717A]">Стандартная комиссия: </span>
                        <span className="text-white">{commissionSettings.shop_commission || 5}%</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
              <div className="flex gap-2">
                <Button 
                  variant="ghost" 
                  onClick={() => { setShowCommissionModal(false); setCommissionValue(""); setCommissionType(null); }}
                  className="flex-1 text-[#71717A]"
                >
                  Отмена
                </Button>
                <Button 
                  onClick={handleApproveWithCommission}
                  className="flex-1 bg-[#10B981] hover:bg-[#059669] text-white"
                  data-testid="confirm-commission-btn"
                >
                  ✅ Одобрить
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showStaffModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-[#121212] border border-white/10 rounded-2xl w-full max-w-md">
            <div className="p-4 border-b border-white/5 flex items-center justify-between">
              <h3 className="text-white font-semibold">Добавить персонал в чат</h3>
              <button onClick={() => setShowStaffModal(false)} className="text-[#71717A] hover:text-white">
                <XCircle className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 max-h-[60vh] overflow-y-auto">
              {staffList.length === 0 ? (
                <p className="text-[#71717A] text-sm text-center py-4">Нет доступных сотрудников</p>
              ) : (
                <div className="space-y-2">
                  {staffList.map(staff => (
                    <button
                      key={staff.id}
                      onClick={() => handleAddStaff(staff.id)}
                      className="w-full flex items-center gap-3 p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors"
                    >
                      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                        staff.admin_role === "owner" || staff.admin_role === "admin" ? "bg-[#EF4444]/20" :
                        staff.admin_role === "mod_p2p" || staff.admin_role === "mod_market" ? "bg-[#F59E0B]/20" :
                        "bg-[#3B82F6]/20"
                      }`}>
                        <UserCog className={`w-5 h-5 ${
                          staff.admin_role === "owner" || staff.admin_role === "admin" ? "text-[#EF4444]" :
                          staff.admin_role === "mod_p2p" || staff.admin_role === "mod_market" ? "text-[#F59E0B]" :
                          "text-[#3B82F6]"
                        }`} />
                      </div>
                      <div className="flex-1 text-left">
                        <div className="text-white text-sm font-medium">{staff.nickname || staff.login}</div>
                        <div className="text-[#71717A] text-xs">{staff.role_label || staff.admin_role}</div>
                      </div>
                      <PlusCircle className="w-5 h-5 text-[#10B981]" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Create User Chat Modal */}
      {showCreateUserChat && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-[#121212] border border-white/10 rounded-2xl w-full max-w-md">
            <div className="p-4 border-b border-white/5 flex items-center justify-between">
              <h3 className="text-white font-semibold">👤 Новый чат с пользователем</h3>
              <button onClick={() => { setShowCreateUserChat(false); setUserChatTarget(null); setUserSearchQuery(""); }} className="text-[#71717A] hover:text-white"><XCircle className="w-5 h-5" /></button>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="text-[#71717A] text-xs mb-1 block">Поиск пользователя *</label>
                <Input value={userSearchQuery} onChange={e => searchUsers(e.target.value)} placeholder="Введите никнейм..." className="bg-white/5 border-white/10" />
                {userSearchResults.length > 0 && (
                  <div className="mt-2 bg-white/5 rounded-lg max-h-40 overflow-y-auto">
                    {userSearchResults.map(u => (
                      <button key={u.id} onClick={() => { setUserChatTarget(u); setUserSearchQuery(u.name); setUserSearchResults([]); }}
                        className={`w-full p-2 text-left hover:bg-white/10 flex items-center gap-2 ${userChatTarget?.id === u.id ? "bg-[#7C3AED]/20" : ""}`}>
                        <span className={`w-2 h-2 rounded-full ${u.type === "merchant" ? "bg-[#F97316]" : "bg-white"}`}></span>
                        <span className="text-white text-sm">@{u.name}</span>
                        <span className="text-[#52525B] text-xs">{u.type === "merchant" ? "мерчант" : "пользователь"}</span>
                      </button>
                    ))}
                  </div>
                )}
                {userChatTarget && (
                  <div className="mt-2 p-2 bg-[#7C3AED]/10 rounded-lg flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-[#7C3AED]" />
                    <span className="text-white text-sm">@{userChatTarget.name}</span>
                    <span className="text-[#71717A] text-xs">({userChatTarget.type})</span>
                  </div>
                )}
              </div>
              <div>
                <label className="text-[#71717A] text-xs mb-1 block">Тема (опционально)</label>
                <Input value={userChatSubject} onChange={e => setUserChatSubject(e.target.value)} placeholder="Тема сообщения..." className="bg-white/5 border-white/10" />
              </div>
              <Button onClick={createUserChat} disabled={!userChatTarget} className="w-full bg-[#7C3AED] hover:bg-[#6D28D9] disabled:opacity-50">
                <MessageCircle className="w-4 h-4 mr-2" /> Создать чат
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Message Templates Modal */}
      {showTemplatesModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50" onClick={() => setShowTemplatesModal(false)}>
          <div className="bg-[#18181B] rounded-xl p-6 w-[600px] max-h-[80vh] overflow-y-auto border border-white/10" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-white">⚡ Авто-сообщения</h3>
              <button onClick={() => setShowTemplatesModal(false)} className="text-[#71717A] hover:text-white">
                <XCircle className="w-5 h-5" />
              </button>
            </div>
            
            {/* Template form */}
            <div className="bg-white/5 rounded-lg p-4 mb-4">
              <h4 className="text-sm font-medium text-white mb-3">
                {editingTemplate ? "✏️ Редактировать шаблон" : "➕ Новый шаблон"}
              </h4>
              <div className="space-y-3">
                <Input 
                  value={newTemplateTitle} 
                  onChange={e => setNewTemplateTitle(e.target.value)} 
                  placeholder="Название шаблона" 
                  className="bg-white/5 border-white/10 text-white"
                />
                <Textarea 
                  value={newTemplateContent} 
                  onChange={e => setNewTemplateContent(e.target.value)} 
                  placeholder="Текст сообщения..." 
                  className="bg-white/5 border-white/10 text-white min-h-[100px]"
                />
                <div className="flex gap-2">
                  {editingTemplate ? (
                    <>
                      <Button onClick={updateTemplate} className="bg-[#7C3AED] hover:bg-[#6D28D9] text-white">
                        <CheckCircle className="w-4 h-4 mr-2" /> Сохранить
                      </Button>
                      <Button onClick={cancelEditTemplate} variant="outline" className="border-white/20 text-white hover:bg-white/10">
                        Отмена
                      </Button>
                    </>
                  ) : (
                    <Button onClick={createTemplate} className="bg-[#10B981] hover:bg-[#059669] text-white">
                      <PlusCircle className="w-4 h-4 mr-2" /> Добавить
                    </Button>
                  )}
                </div>
              </div>
            </div>

            {/* Templates list */}
            <div className="space-y-2">
              <h4 className="text-sm font-medium text-[#71717A]">Ваши шаблоны</h4>
              {templatesLoading ? (
                <div className="text-center py-4 text-[#71717A]">
                  <Loader className="w-5 h-5 animate-spin mx-auto" />
                </div>
              ) : templates.length === 0 ? (
                <div className="text-center py-4 text-[#71717A] text-sm">
                  Нет сохранённых шаблонов
                </div>
              ) : (
                templates.map(t => (
                  <div key={t.id} className="bg-white/5 rounded-lg p-3 hover:bg-white/10 transition-colors group">
                    <div className="flex items-start justify-between">
                      <div className="flex-1 cursor-pointer" onClick={() => selectTemplate(t)}>
                        <div className="font-medium text-white text-sm">{t.title}</div>
                        <div className="text-[#71717A] text-xs mt-1 line-clamp-2">{t.content}</div>
                      </div>
                      <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity ml-2">
                        <button 
                          onClick={() => startEditTemplate(t)} 
                          className="p-1.5 text-[#3B82F6] hover:bg-[#3B82F6]/20 rounded"
                          title="Редактировать"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button 
                          onClick={() => deleteTemplate(t.id)} 
                          className="p-1.5 text-[#EF4444] hover:bg-[#EF4444]/20 rounded"
                          title="Удалить"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
            
            <div className="mt-4 text-xs text-[#71717A] text-center">
              Нажмите на шаблон, чтобы вставить текст в поле сообщения
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default UnifiedMessagesHub;
