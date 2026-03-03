import React, { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import { useAuth, API } from "@/App";
import { Shield, Send, ArrowLeft, Clock, CheckCircle, XCircle, AlertTriangle, Package, User, Store, MessageCircle, Copy, Check } from "lucide-react";

export default function MarketplaceGuarantorChat() {
  const { purchaseId } = useParams();
  const navigate = useNavigate();
  const { token } = useAuth();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [purchase, setPurchase] = useState(null);
  const [conversation, setConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [userRole, setUserRole] = useState("buyer");
  const [conversationId, setConversationId] = useState(null);
  const [copied, setCopied] = useState(false);

  const messagesEndRef = useRef(null);
  const pollRef = useRef(null);
  const headers = { Authorization: `Bearer ${token}` };

  // Load purchase info and conversation
  const loadData = useCallback(async () => {
    try {
      setError(null);
      
      // Get purchase info with conversation_id
      const res = await axios.get(`${API}/marketplace/purchases/${purchaseId}/guarantor-chat`, { headers });
      const data = res.data;
      
      setPurchase(data.purchase);
      setUserRole(data.role);
      
      if (data.conversation_id) {
        setConversationId(data.conversation_id);
        
        // Load conversation with messages
        const convRes = await axios.get(`${API}/msg/conversations/${data.conversation_id}`, { headers });
        setConversation(convRes.data.conversation);
        setMessages(convRes.data.messages || []);
      }
      
      setLoading(false);
    } catch (err) {
      console.error("Error loading guarantor chat:", err);
      setError(err.response?.data?.detail || "Ошибка загрузки чата");
      setLoading(false);
    }
  }, [purchaseId, token]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Poll for new messages
  useEffect(() => {
    if (!conversationId) return;
    
    pollRef.current = setInterval(async () => {
      try {
        const convRes = await axios.get(`${API}/msg/conversations/${conversationId}`, { headers });
        setMessages(convRes.data.messages || []);
      } catch (err) {
        console.error("Poll error:", err);
      }
    }, 5000);

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [conversationId, token]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    if (!newMessage.trim() || !conversationId || sending) return;
    
    setSending(true);
    try {
      await axios.post(
        `${API}/msg/conversations/${conversationId}/send`,
        { content: newMessage.trim() },
        { headers }
      );
      setNewMessage("");
      
      // Reload messages
      const convRes = await axios.get(`${API}/msg/conversations/${conversationId}`, { headers });
      setMessages(convRes.data.messages || []);
    } catch (err) {
      console.error("Send error:", err);
      alert(err.response?.data?.detail || "Ошибка отправки сообщения");
    }
    setSending(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const copyOrderId = () => {
    const orderId = purchase?.id?.slice(0, 8).toUpperCase();
    navigator.clipboard.writeText(orderId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getStatusInfo = (status) => {
    switch (status) {
      case "pending_confirmation":
        return { label: "Ожидает подтверждения", color: "text-[#F59E0B]", bg: "bg-[#F59E0B]/10", icon: Clock };
      case "completed":
        return { label: "Завершён", color: "text-[#10B981]", bg: "bg-[#10B981]/10", icon: CheckCircle };
      case "cancelled":
        return { label: "Отменён", color: "text-[#71717A]", bg: "bg-[#71717A]/10", icon: XCircle };
      case "disputed":
        return { label: "Спор", color: "text-[#EF4444]", bg: "bg-[#EF4444]/10", icon: AlertTriangle };
      case "refunded":
        return { label: "Возврат", color: "text-[#3B82F6]", bg: "bg-[#3B82F6]/10", icon: XCircle };
      default:
        return { label: status, color: "text-[#71717A]", bg: "bg-[#71717A]/10", icon: Clock };
    }
  };

  const getRoleColor = (role) => {
    switch (role) {
      case "system": return "text-[#F59E0B]";
      case "owner": case "admin": return "text-[#EF4444]";
      case "mod_market": case "mod_p2p": return "text-[#7C3AED]";
      case "support": return "text-[#3B82F6]";
      default: return "text-[#A1A1AA]";
    }
  };

  const getRoleBadge = (msg) => {
    if (msg.is_system || msg.sender_role === "system") {
      return <span className="px-1.5 py-0.5 text-[10px] rounded bg-[#F59E0B]/20 text-[#F59E0B]">Система</span>;
    }
    if (["owner", "admin"].includes(msg.sender_role)) {
      return <span className="px-1.5 py-0.5 text-[10px] rounded bg-[#EF4444]/20 text-[#EF4444]">Админ</span>;
    }
    if (["mod_market", "mod_p2p"].includes(msg.sender_role)) {
      return <span className="px-1.5 py-0.5 text-[10px] rounded bg-[#7C3AED]/20 text-[#A78BFA]">Модератор</span>;
    }
    if (msg.sender_id === purchase?.buyer_id) {
      return <span className="px-1.5 py-0.5 text-[10px] rounded bg-[#3B82F6]/20 text-[#3B82F6]">Покупатель</span>;
    }
    if (msg.sender_id === purchase?.seller_id) {
      return <span className="px-1.5 py-0.5 text-[10px] rounded bg-[#10B981]/20 text-[#10B981]">Продавец</span>;
    }
    return null;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="w-8 h-8 border-2 border-[#7C3AED] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto p-6">
        <button onClick={() => navigate(-1)} className="flex items-center gap-2 text-[#A1A1AA] hover:text-white mb-4">
          <ArrowLeft className="w-4 h-4" /> Назад
        </button>
        <div className="bg-[#EF4444]/10 border border-[#EF4444]/20 rounded-xl p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-[#EF4444] mx-auto mb-2" />
          <p className="text-[#EF4444]">{error}</p>
        </div>
      </div>
    );
  }

  const statusInfo = getStatusInfo(purchase?.status);
  const StatusIcon = statusInfo.icon;
  const orderId = purchase?.id?.slice(0, 8).toUpperCase();
  const isActive = ["pending_confirmation", "disputed"].includes(purchase?.status);

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <button onClick={() => navigate(-1)} className="p-2 hover:bg-white/5 rounded-lg transition-colors">
          <ArrowLeft className="w-5 h-5 text-[#A1A1AA]" />
        </button>
        <div className="flex items-center gap-2">
          <Shield className="w-5 h-5 text-[#7C3AED]" />
          <h1 className="text-xl font-bold text-white">Гарант-сделка</h1>
          <span className={`px-2 py-0.5 text-xs rounded-full ${statusInfo.bg} ${statusInfo.color} flex items-center gap-1`}>
            <StatusIcon className="w-3 h-3" />
            {statusInfo.label}
          </span>
        </div>
      </div>

      {/* Deal Info Card */}
      <div className="bg-[#121212] border border-white/5 rounded-xl p-4 mb-4">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <Package className="w-4 h-4 text-[#7C3AED]" />
              <span className="text-white font-semibold">{purchase?.product_name}</span>
              <span className="text-xs text-[#52525B]">×{purchase?.quantity}</span>
            </div>
            
            <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
              <div className="flex items-center gap-2 text-[#71717A]">
                <Store className="w-3 h-3" />
                Продавец: <span className="text-white">@{purchase?.seller_nickname}</span>
              </div>
              <div className="flex items-center gap-2 text-[#71717A]">
                <User className="w-3 h-3" />
                Покупатель: <span className="text-white">@{purchase?.buyer_nickname}</span>
              </div>
              <div className="text-[#71717A]">
                Сумма: <span className="text-[#10B981] font-mono">{purchase?.total_price?.toFixed(2)} USDT</span>
              </div>
              <div className="text-[#71717A]">
                Комиссия гаранта: <span className="text-[#7C3AED] font-mono">{purchase?.guarantor_fee?.toFixed(2)} USDT</span>
              </div>
            </div>

            {purchase?.auto_complete_at && isActive && (
              <div className="mt-2 flex items-center gap-2 text-xs text-[#F59E0B]">
                <Clock className="w-3 h-3" />
                Автозавершение: {new Date(purchase.auto_complete_at).toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" })}
              </div>
            )}
          </div>

          <div className="text-right">
            <div className="flex items-center gap-1 text-xs text-[#52525B]">
              <span>#{orderId}</span>
              <button onClick={copyOrderId} className="p-0.5 hover:text-white transition-colors">
                {copied ? <Check className="w-3 h-3 text-[#10B981]" /> : <Copy className="w-3 h-3" />}
              </button>
            </div>
          </div>
        </div>

        {/* Delivered content (after completion) */}
        {purchase?.delivered_content && purchase.delivered_content.length > 0 && (
          <div className="mt-3 p-3 bg-[#10B981]/5 border border-[#10B981]/20 rounded-lg">
            <div className="text-xs text-[#10B981] font-semibold mb-1">Доставленный товар:</div>
            {purchase.delivered_content.map((item, i) => (
              <div key={i} className="text-sm text-white bg-black/30 rounded p-2 mt-1 font-mono break-all">
                {typeof item === "string" ? item : item.text || JSON.stringify(item)}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Chat Area */}
      <div className="bg-[#121212] border border-white/5 rounded-xl overflow-hidden" style={{ height: "calc(100vh - 380px)", minHeight: "400px" }}>
        {/* Chat Header */}
        <div className="px-4 py-3 border-b border-white/5 flex items-center gap-2">
          <MessageCircle className="w-4 h-4 text-[#7C3AED]" />
          <span className="text-sm text-white font-medium">Чат гарант-сделки</span>
          <span className="text-xs text-[#52525B]">• {messages.length} сообщений</span>
          {isActive && <span className="ml-auto px-2 py-0.5 text-[10px] rounded-full bg-[#10B981]/10 text-[#10B981]">Активна</span>}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3" style={{ height: "calc(100% - 120px)" }}>
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-[#52525B]">
              <MessageCircle className="w-8 h-8 mb-2" />
              <p>Нет сообщений</p>
            </div>
          ) : (
            messages.map((msg) => (
              <div key={msg.id} className={`${msg.is_system || msg.sender_role === "system" ? "mx-auto max-w-md" : ""}`}>
                {msg.is_system || msg.sender_role === "system" ? (
                  // System message
                  <div className="bg-[#F59E0B]/5 border border-[#F59E0B]/10 rounded-lg p-3 text-xs text-[#F59E0B]/80 whitespace-pre-line">
                    {msg.content}
                  </div>
                ) : (() => {
                  // Determine if this is the current user's message
                  const isMyMessage = (userRole === "buyer" && msg.sender_id === purchase?.buyer_id) ||
                    (userRole === "seller" && msg.sender_id === purchase?.seller_id) ||
                    (["admin", "owner", "mod_market", "mod_p2p", "support"].includes(msg.sender_role) && userRole === "admin");
                  
                  return isMyMessage ? (
                    // MY message - RIGHT side
                    <div className="flex justify-end">
                      <div className="max-w-[75%]">
                        <div className="flex items-center gap-2 mb-1 justify-end">
                          <span className="text-[10px] text-[#52525B]">
                            {new Date(msg.created_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}
                          </span>
                          {getRoleBadge(msg)}
                          <span className={`text-xs font-medium ${getRoleColor(msg.sender_role)}`}>
                            {msg.sender_name || msg.sender_nickname || "Вы"}
                          </span>
                        </div>
                        <div className="bg-[#7C3AED] text-white p-3 rounded-2xl rounded-tr-sm">
                          <div className="text-sm whitespace-pre-line break-words">
                            {msg.content}
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    // OTHER's message - LEFT side  
                    <div className="flex justify-start">
                      <div className="max-w-[75%]">
                        <div className="flex items-center gap-2 mb-1">
                          <div className="w-7 h-7 rounded-full bg-[#27272A] flex items-center justify-center text-[10px] font-bold text-[#A1A1AA] flex-shrink-0">
                            {(msg.sender_name || msg.sender_nickname || "?")[0]?.toUpperCase()}
                          </div>
                          <span className={`text-xs font-medium ${getRoleColor(msg.sender_role)}`}>
                            {msg.sender_name || msg.sender_nickname || "Пользователь"}
                          </span>
                          {getRoleBadge(msg)}
                          <span className="text-[10px] text-[#52525B]">
                            {new Date(msg.created_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}
                          </span>
                        </div>
                        <div className="bg-[#1E1E1E] border border-white/10 text-[#D4D4D8] p-3 rounded-2xl rounded-tl-sm ml-9">
                          <div className="text-sm whitespace-pre-line break-words">
                            {msg.content}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })()}
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        {isActive ? (
          <div className="px-4 py-3 border-t border-white/5">
            <div className="flex gap-2">
              <textarea
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Написать сообщение..."
                className="flex-1 bg-[#1A1A1A] border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-[#52525B] resize-none focus:outline-none focus:border-[#7C3AED]/50"
                rows={1}
              />
              <button
                onClick={sendMessage}
                disabled={!newMessage.trim() || sending}
                className="px-4 py-2 bg-[#7C3AED] hover:bg-[#6D28D9] disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
              >
                {sending ? (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <Send className="w-4 h-4 text-white" />
                )}
              </button>
            </div>
          </div>
        ) : (
          <div className="px-4 py-3 border-t border-white/5 text-center text-xs text-[#52525B]">
            Сделка завершена. Отправка сообщений недоступна.
          </div>
        )}
      </div>
    </div>
  );
}
