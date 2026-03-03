// UnifiedMessagesHub - Refactored main component
import React, { useState, useEffect, useCallback, useRef } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useLocation } from "react-router-dom";
import { toast } from "sonner";
import axios from "axios";
import { History, PlusCircle } from "lucide-react";
import { useAuth, API } from "@/App";
import { PageHeader } from "@/components/admin/SharedComponents";

// Import modular components
import { ChatSidebar } from "./chat/ChatSidebar";
import { ChatWindow } from "./chat/ChatWindow";
import { CommissionModal, StaffModal, CreateUserChatModal, TemplatesModal } from "./chat/ChatModals";
import { 
  getCategories, 
  getRoleInfo,
  fetchAllConversations,
  fetchConversationMessages,
  sendConversationMessage,
  fetchArchivedConversations,
  fetchStaff,
  searchConversations,
  addStaffToConversation,
  leaveConversation,
  deleteConversation,
  fetchCommissions,
  fetchTemplates as fetchTemplatesApi,
  createTemplate as createTemplateApi,
  updateTemplate as updateTemplateApi,
  deleteTemplate as deleteTemplateApi,
  searchUsers as searchUsersApi,
  createUserChat as createUserChatApi
} from "./chat";

function UnifiedMessagesHub() {
  const { token, user } = useAuth();
  const location = useLocation();
  const adminRole = user?.admin_role || "admin";
  
  // Handle navigation state
  const initialCategory = location.state?.category || "all";
  const targetTradeId = location.state?.tradeId || null;
  
  // Main state
  const [activeCategory, setActiveCategory] = useState(initialCategory);
  const [conversations, setConversations] = useState([]);
  const [selectedConv, setSelectedConv] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  
  // Archive state
  const [showArchive, setShowArchive] = useState(false);
  const [archivedConvs, setArchivedConvs] = useState([]);
  
  // Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  
  // Staff modal state
  const [staffList, setStaffList] = useState([]);
  const [showStaffModal, setShowStaffModal] = useState(false);
  
  // User chat state
  const [showCreateUserChat, setShowCreateUserChat] = useState(false);
  const [userChatTarget, setUserChatTarget] = useState(null);
  const [userChatSubject, setUserChatSubject] = useState("");
  const [userChats, setUserChats] = useState([]);
  const [userSearchQuery, setUserSearchQuery] = useState("");
  const [userSearchResults, setUserSearchResults] = useState([]);
  
  // Commission modal state
  const [showCommissionModal, setShowCommissionModal] = useState(false);
  const [commissionValue, setCommissionValue] = useState("");
  const [withdrawalCommissionValue, setWithdrawalCommissionValue] = useState("");
  const [commissionType, setCommissionType] = useState(null);
  const [commissionSettings, setCommissionSettings] = useState(null);
  const [commissionTargetData, setCommissionTargetData] = useState(null);
  
  // Templates modal state
  const [showTemplatesModal, setShowTemplatesModal] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [newTemplateTitle, setNewTemplateTitle] = useState("");
  const [newTemplateContent, setNewTemplateContent] = useState("");
  const [templateCategory, setTemplateCategory] = useState("general");

  // Track if initial load is done to prevent flickering on refresh
  const initialLoadDone = useRef(false);

  // Fetch conversations - always fetch ALL categories so tab counters are stable
  const fetchConversations = useCallback(async () => {
    if (!initialLoadDone.current) setLoading(true);
    try {
      const allConvs = await fetchAllConversations(token, adminRole, "all", setUserChats);
      // Filter out archived/resolved conversations from active list
      const activeConvs = allConvs.filter(c => !c.archived && c.status !== "archived");
      setConversations(activeConvs);
    } catch (error) {
      console.error("Error fetching conversations:", error);
    } finally {
      setLoading(false);
      initialLoadDone.current = true;
    }
  }, [token, adminRole]);

  // Fetch messages
  const fetchMessages = useCallback(async () => {
    if (!selectedConv) return;
    try {
      const msgs = await fetchConversationMessages(token, selectedConv);
      setMessages(msgs);
    } catch (error) {
      console.error("Error fetching messages:", error);
    }
  }, [token, selectedConv]);

  // Effects
  useEffect(() => {
    fetchConversations();
    const interval = setInterval(fetchConversations, 20000);
    return () => clearInterval(interval);
  }, [fetchConversations]);

  useEffect(() => {
    if (targetTradeId && conversations.length > 0 && !selectedConv) {
      const targetConv = conversations.find(c => 
        c.related_id === targetTradeId || c.id === targetTradeId || c.context_id === targetTradeId
      );
      if (targetConv) setSelectedConv(targetConv);
    }
  }, [targetTradeId, conversations, selectedConv]);

  useEffect(() => {
    if (selectedConv) {
      fetchMessages();
      const interval = setInterval(fetchMessages, 15000);
      return () => clearInterval(interval);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedConv?.id]);

  // Handlers
  const handleSearch = async (query) => {
    setSearchQuery(query);
    if (query.length < 2) {
      setSearchResults([]);
      setIsSearching(false);
      return;
    }
    setIsSearching(true);
    try {
      const results = await searchConversations(token, query);
      setSearchResults(results);
    } catch (error) {
      console.error("Search error:", error);
      setSearchResults([]);
    }
  };

  const clearSearch = () => {
    setSearchQuery("");
    setSearchResults([]);
    setIsSearching(false);
  };

  const handleSendMessage = async () => {
    if (!newMessage.trim() || !selectedConv) return;
    if (selectedConv.status === "closed") {
      toast.error("Невозможно отправить сообщение в закрытый чат");
      return;
    }
    setSending(true);
    try {
      await sendConversationMessage(token, selectedConv, newMessage);
      setNewMessage("");
      fetchMessages();
    } catch (error) {
      toast.error("Ошибка отправки");
    } finally {
      setSending(false);
    }
  };

  const handleLeaveConversation = async () => {
    if (!selectedConv) return;
    if (!window.confirm("Вы уверены, что хотите выйти из чата?")) return;
    try {
      await leaveConversation(token, selectedConv);
      toast.success("Вы вышли из чата");
      setSelectedConv(null);
      fetchConversations();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка выхода из чата");
    }
  };

  const handleDeleteConversation = async (convId) => {
    if (!window.confirm("Удалить чат навсегда?")) return;
    try {
      await deleteConversation(token, convId);
      toast.success("Чат удалён");
      setSelectedConv(null);
      if (showArchive) {
        const archived = await fetchArchivedConversations(token);
        setArchivedConvs(archived);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка удаления");
    }
  };

  const handleAddStaff = async (staffId) => {
    if (!selectedConv) return;
    try {
      await addStaffToConversation(token, selectedConv.id, staffId);
      toast.success("Сотрудник добавлен в чат");
      setShowStaffModal(false);
      fetchMessages();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка добавления");
    }
  };

  const openStaffModal = async () => {
    try {
      const staff = await fetchStaff(token);
      setStaffList(staff);
      setShowStaffModal(true);
    } catch (error) {
      console.error("Error fetching staff:", error);
    }
  };

  const toggleArchive = async () => {
    setShowArchive(!showArchive);
    setSelectedConv(null);
    if (!showArchive) {
      try {
        const archived = await fetchArchivedConversations(token);
        setArchivedConvs(archived);
      } catch (error) {
        console.error("Error fetching archived:", error);
      }
    }
  };

  // Commission handlers
  const openCommissionModal = async (type) => {
    try {
      const settings = await fetchCommissions(token);
      setCommissionSettings(settings);
    } catch (error) {
      console.error("Error fetching commission settings:", error);
    }
    setCommissionType(type);
    // Extract user_id from various possible locations in the conversation object
    const extractedUserId = selectedConv?.user_id 
      || selectedConv?.data?.user_id 
      || (selectedConv?.participants && selectedConv.participants[0]?.user_id)
      || (selectedConv?.participants && selectedConv.participants[0]?.id);
    const extractedRelatedId = selectedConv?.related_id || selectedConv?.data?.id;
    setCommissionTargetData({
      user_id: extractedUserId,
      related_id: extractedRelatedId,
      data: selectedConv?.data
    });
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
      toast.error("Введите комиссию на платежи");
      return;
    }
    const commission = parseFloat(commissionValue);
    const withdrawalComm = withdrawalCommissionValue ? parseFloat(withdrawalCommissionValue) : 3.0;
    if (commissionType === "merchant" && (!withdrawalCommissionValue || isNaN(withdrawalComm))) {
      toast.error("Введите комиссию на выплаты");
      return;
    }
    try {
      if (commissionType === "merchant") {
        const merchantId = selectedConv.related_id || selectedConv.data?.id || selectedConv.data?.user_id;
        if (!merchantId) {
          toast.error("ID мерчанта не найден");
          return;
        }
        await axios.post(`${API}/admin/merchants/${merchantId}/approve`,
          { approved: true, custom_commission: commission, withdrawal_commission: withdrawalComm },
          { headers: { Authorization: `Bearer ${token}` } }
        );
        toast.success(`Мерчант одобрен. Платежи: ${commission}%, Выплаты: ${withdrawalComm}%`);
      } else if (commissionType === "shop") {
        const userId = commissionTargetData?.user_id || commissionTargetData?.data?.user_id
          || (selectedConv?.participants && selectedConv.participants[0]?.user_id)
          || (selectedConv?.participants && selectedConv.participants[0]?.id);
        const shopAppId = commissionTargetData?.related_id || commissionTargetData?.data?.id
          || selectedConv?.related_id;
        if (!userId || !shopAppId) {
          console.error("Missing IDs:", { userId, shopAppId, commissionTargetData, selectedConv });
          toast.error("ID не найден");
          return;
        }
        await axios.post(`${API}/admin/shop-applications/commission/${userId}`,
          { commission },
          { headers: { Authorization: `Bearer ${token}` } }
        );
        await axios.post(`${API}/admin/shop-applications/${shopAppId}/review?decision=approve&comment=${encodeURIComponent(`Комиссия: ${commission}%`)}`,
          {},
          { headers: { Authorization: `Bearer ${token}` } }
        );
        toast.success(`Магазин одобрен с комиссией ${commission}%`);
        // Archive the conversation after approval
        try {
          const convId = selectedConv?.id;
          if (convId && !convId.startsWith("shop_")) {
            await axios.post(`${API}/msg/conversations/${convId}/archive`, {}, {
              headers: { Authorization: `Bearer ${token}` }
            });
          }
        } catch (archiveErr) {
          console.log("Archive not available for this conversation type");
        }
      }
      setShowCommissionModal(false);
      setCommissionValue("");
      setCommissionType(null);
      setCommissionTargetData(null);
      // Remove conversation from list immediately (move to archive visually)
      setConversations(prev => prev.filter(c => c.id !== selectedConv?.id));
      setSelectedConv(null);
      await new Promise(resolve => setTimeout(resolve, 500));
      await fetchConversations();
    } catch (error) {
      toast.error("Ошибка: " + (error.response?.data?.detail || error.message));
    }
  };

  // Templates handlers
  const openTemplatesModal = async (category = "general") => {
    setTemplateCategory(category);
    setTemplatesLoading(true);
    try {
      const tmpl = await fetchTemplatesApi(token, category);
      setTemplates(tmpl);
    } catch (error) {
      console.error("Error fetching templates:", error);
      setTemplates([]);
    } finally {
      setTemplatesLoading(false);
    }
    setShowTemplatesModal(true);
    setEditingTemplate(null);
    setNewTemplateTitle("");
    setNewTemplateContent("");
  };

  const handleCreateTemplate = async () => {
    if (!newTemplateTitle.trim() || !newTemplateContent.trim()) {
      toast.error("Заполните название и текст шаблона");
      return;
    }
    try {
      await createTemplateApi(token, { title: newTemplateTitle, content: newTemplateContent, category: templateCategory });
      toast.success("Шаблон создан");
      setNewTemplateTitle("");
      setNewTemplateContent("");
      const tmpl = await fetchTemplatesApi(token, templateCategory);
      setTemplates(tmpl);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка создания шаблона");
    }
  };

  const handleUpdateTemplate = async () => {
    if (!editingTemplate || !newTemplateTitle.trim() || !newTemplateContent.trim()) {
      toast.error("Заполните название и текст шаблона");
      return;
    }
    try {
      await updateTemplateApi(token, editingTemplate.id, { title: newTemplateTitle, content: newTemplateContent, category: templateCategory });
      toast.success("Шаблон обновлён");
      setEditingTemplate(null);
      setNewTemplateTitle("");
      setNewTemplateContent("");
      const tmpl = await fetchTemplatesApi(token, templateCategory);
      setTemplates(tmpl);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка обновления");
    }
  };

  const handleDeleteTemplate = async (templateId) => {
    if (!window.confirm("Удалить шаблон?")) return;
    try {
      await deleteTemplateApi(token, templateId);
      toast.success("Шаблон удалён");
      const tmpl = await fetchTemplatesApi(token, templateCategory);
      setTemplates(tmpl);
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

  // User chat handlers
  const handleSearchUsers = async (query) => {
    setUserSearchQuery(query);
    if (query.length < 2) {
      setUserSearchResults([]);
      return;
    }
    try {
      const results = await searchUsersApi(token, query);
      setUserSearchResults(results);
    } catch (error) {
      console.error("Search error:", error);
    }
  };

  const handleCreateUserChat = async () => {
    if (!userChatTarget) {
      toast.error("Выберите пользователя");
      return;
    }
    try {
      await createUserChatApi(token, { 
        user_id: userChatTarget.id, 
        user_type: userChatTarget.type, 
        subject: userChatSubject 
      });
      toast.success("Чат создан");
      setShowCreateUserChat(false);
      setUserChatTarget(null);
      setUserChatSubject("");
      setUserSearchQuery("");
      fetchConversations();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка создания чата");
    }
  };

  // Decision handler
  const handleDecision = async (type, params) => {
    try {
      if (selectedConv.type === "p2p_dispute") {
        const tradeId = selectedConv.related_id || selectedConv.trade?.id || selectedConv.context_id;
        await axios.post(`${API}/msg/trade/${tradeId}/resolve`,
          { decision: type, reason: params.reason || "" },
          { headers: { Authorization: `Bearer ${token}` } }
        );
        toast.success(type === "refund_buyer" ? "Спор решён в пользу покупателя" : "Спор отменён");
      } else if (selectedConv.type === "merchant_application") {
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
        const shopAppId = selectedConv.related_id || selectedConv.data?.id || selectedConv.data?.application_id;
        if (!shopAppId) {
          toast.error("ID заявки не найден");
          return;
        }
        const commentText = params.reason || params.comment || "";
        await axios.post(`${API}/admin/shop-applications/${shopAppId}/review?decision=${type}&comment=${encodeURIComponent(commentText)}`,
          {},
          { headers: { Authorization: `Bearer ${token}` } }
        );
        toast.success(type === "approve" ? "Магазин одобрен" : "Заявка отклонена");
      } else if (selectedConv.type === "marketplace_guarantor") {
        // Use purchase_id for marketplace guarantor, or related_id for P2P guarantor
        const purchaseId = selectedConv.purchase_id || selectedConv.related_id || selectedConv.data?.id;
        if (!purchaseId) {
          toast.error("ID сделки не найден");
          return;
        }
        if (selectedConv.deal_type === "p2p") {
          // P2P guarantor deal
          await axios.post(`${API}/msg/guarantor/order/${purchaseId}/decision`,
            { decision: type, reason: params.reason || "" },
            { headers: { Authorization: `Bearer ${token}` } }
          );
        } else {
          // Marketplace guarantor deal
          await axios.post(`${API}/msg/admin/marketplace-guarantor/${purchaseId}/resolve`,
            { resolution: type, reason: params.reason || "" },
            { headers: { Authorization: `Bearer ${token}` } }
          );
        }
        toast.success(type === "complete" ? "Сделка успешно завершена" : "Сделка отменена, средства возвращены покупателю");
      } else if (selectedConv.type === "support_ticket" || selectedConv.type === "unified_support_ticket") {
        await axios.post(`${API}/admin/support/tickets/${selectedConv.data?.id}/status?status=${type}`,
          {}, { headers: { Authorization: `Bearer ${token}` } }
        );
        toast.success("Статус обновлён");
      }
      // Move conversation to archive after decision
      try {
        const convId = selectedConv.id;
        if (convId && !convId.startsWith("shop_") && !convId.startsWith("merchant_") && !convId.startsWith("ticket_")) {
          await axios.post(`${API}/msg/conversations/${convId}/archive`, {}, {
            headers: { Authorization: `Bearer ${token}` }
          });
        }
      } catch (archiveErr) {
        console.log("Archive not available for this conversation type");
      }
      // Remove conversation from list immediately (move to archive visually)
      setConversations(prev => prev.filter(c => c.id !== selectedConv.id));
      setSelectedConv(null);
      await new Promise(resolve => setTimeout(resolve, 500));
      await fetchConversations();
    } catch (error) {
      toast.error("Ошибка: " + (error.response?.data?.detail || error.message));
    }
  };

  // Computed values
  const categories = getCategories(adminRole);
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
          {activeCategory === "admin_to_user" && (adminRole === "owner" || adminRole === "admin" || adminRole === "mod_p2p" || adminRole === "mod_market") && (
            <button
              onClick={() => setShowCreateUserChat(true)}
              className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs bg-[#7C3AED]/10 text-[#7C3AED] hover:bg-[#7C3AED]/20"
             title="Создать новый элемент">
              <PlusCircle className="w-3 h-3" />
              Новый
            </button>
          )}
          <button
            onClick={toggleArchive}
            className={`flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs transition-all ${
              showArchive ? "bg-[#52525B] text-white" : "text-[#71717A] hover:bg-white/5"
            }`}
            data-testid="archive-toggle"
          title="Показать архив"
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
        <ChatSidebar
          loading={loading}
          conversations={conversations}
          filteredConvs={filteredConvs}
          selectedConv={selectedConv}
          setSelectedConv={setSelectedConv}
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          searchResults={searchResults}
          isSearching={isSearching}
          handleSearch={handleSearch}
          clearSearch={clearSearch}
          showArchive={showArchive}
          archivedConvs={archivedConvs}
          onRefresh={showArchive ? () => fetchArchivedConversations(token).then(setArchivedConvs) : fetchConversations}
          onDeleteConversation={handleDeleteConversation}
        />

        {/* Chat Window */}
        <div className="lg:col-span-2 bg-[#121212] border border-white/5 rounded-xl overflow-hidden flex flex-col">
          <ChatWindow
            selectedConv={selectedConv}
            setSelectedConv={setSelectedConv}
            messages={messages}
            newMessage={newMessage}
            setNewMessage={setNewMessage}
            sending={sending}
            onSendMessage={handleSendMessage}
            onLeaveConversation={handleLeaveConversation}
            onDeleteConversation={handleDeleteConversation}
            onAddStaff={openStaffModal}
            onDecision={handleDecision}
            onOpenTemplates={openTemplatesModal}
            onOpenCommission={openCommissionModal}
            adminRole={adminRole}
            token={token}
          />
        </div>
      </div>

      {/* Modals */}
      <CommissionModal
        show={showCommissionModal}
        onClose={() => { setShowCommissionModal(false); setCommissionValue(""); setWithdrawalCommissionValue(""); setCommissionType(null); }}
        commissionType={commissionType}
        commissionValue={commissionValue}
        setCommissionValue={setCommissionValue}
        withdrawalCommissionValue={withdrawalCommissionValue}
        setWithdrawalCommissionValue={setWithdrawalCommissionValue}
        commissionSettings={commissionSettings}
        onApprove={handleApproveWithCommission}
      />

      <StaffModal
        show={showStaffModal}
        onClose={() => setShowStaffModal(false)}
        staffList={staffList}
        onAddStaff={handleAddStaff}
      />

      <CreateUserChatModal
        show={showCreateUserChat}
        onClose={() => { setShowCreateUserChat(false); setUserChatTarget(null); setUserSearchQuery(""); }}
        userSearchQuery={userSearchQuery}
        setUserSearchQuery={setUserSearchQuery}
        userSearchResults={userSearchResults}
        userChatTarget={userChatTarget}
        setUserChatTarget={setUserChatTarget}
        userChatSubject={userChatSubject}
        setUserChatSubject={setUserChatSubject}
        onSearchUsers={handleSearchUsers}
        onCreateChat={handleCreateUserChat}
      />

      <TemplatesModal
        show={showTemplatesModal}
        onClose={() => setShowTemplatesModal(false)}
        templates={templates}
        templatesLoading={templatesLoading}
        editingTemplate={editingTemplate}
        newTemplateTitle={newTemplateTitle}
        setNewTemplateTitle={setNewTemplateTitle}
        newTemplateContent={newTemplateContent}
        setNewTemplateContent={setNewTemplateContent}
        onCreateTemplate={handleCreateTemplate}
        onUpdateTemplate={handleUpdateTemplate}
        onDeleteTemplate={handleDeleteTemplate}
        onSelectTemplate={selectTemplate}
        onStartEdit={startEditTemplate}
        onCancelEdit={cancelEditTemplate}
      />
    </div>
  );
}

export default UnifiedMessagesHub;
