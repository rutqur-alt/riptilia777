import React, { useState, useEffect, useRef } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import { 
  MessageCircle, Copy, Clock, User, Bot, Shield, 
  CreditCard, AlertTriangle, Loader2, X
} from "lucide-react";
import axios from "axios";
import { API, useAuth } from "@/App";

const ROLE_CONFIG = {
  user: { color: 'bg-white text-black border border-gray-300', name: 'Пользователь' },
  buyer: { color: 'bg-white text-black border border-gray-300', name: 'Покупатель' },
  p2p_seller: { color: 'bg-white text-black border border-gray-300', name: 'Продавец' },
  merchant: { color: 'bg-[#F97316] text-white', name: 'Мерчант' },
  mod_p2p: { color: 'bg-[#F59E0B] text-white', name: 'Модератор P2P' },
  admin: { color: 'bg-[#EF4444] text-white', name: 'Администратор' },
  owner: { color: 'bg-[#EF4444] text-white', name: 'Владелец' },
  system: { color: 'bg-[#6B7280] text-white', name: 'Система' }
};

const getRoleInfo = (role) => ROLE_CONFIG[role] || ROLE_CONFIG.user;

export function TradeChatModal({ isOpen, onClose, tradeId }) {
  const { token, user: currentUser } = useAuth();
  const [loading, setLoading] = useState(true);
  const [trade, setTrade] = useState(null);
  const [messages, setMessages] = useState([]);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (isOpen && tradeId) {
      fetchChatHistory();
    }
  }, [isOpen, tradeId]);

  useEffect(() => {
    if (messages.length > 0) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  const fetchChatHistory = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/trades/${tradeId}/chat-history`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTrade(res.data.trade);
      setMessages(res.data.messages || []);
    } catch (err) {
      toast.error("Ошибка загрузки истории чата");
    } finally {
      setLoading(false);
    }
  };

  const copy = (text) => {
    navigator.clipboard.writeText(text);
    toast.success("Скопировано");
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleString("ru-RU", { 
      day: "2-digit", month: "2-digit", year: "numeric",
      hour: "2-digit", minute: "2-digit" 
    });
  };

  const formatTime = (dateStr) => {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  };

  const getStatusConfig = (status) => {
    const config = {
      pending: { color: "text-[#F59E0B]", bg: "bg-[#F59E0B]/10", label: "Ожидание" },
      paid: { color: "text-[#3B82F6]", bg: "bg-[#3B82F6]/10", label: "Оплачено" },
      completed: { color: "text-[#10B981]", bg: "bg-[#10B981]/10", label: "Завершена" },
      cancelled: { color: "text-[#EF4444]", bg: "bg-[#EF4444]/10", label: "Отменена" },
      disputed: { color: "text-[#EF4444]", bg: "bg-[#EF4444]/10", label: "Спор" }
    };
    return config[status] || config.pending;
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="bg-[#121212] border-white/10 text-white max-w-2xl max-h-[85vh] overflow-hidden flex flex-col p-0">
        {/* Header */}
        <div className="p-4 border-b border-white/5">
          <DialogTitle className="flex items-center gap-2 text-white">
            <MessageCircle className="w-5 h-5 text-[#7C3AED]" />
            Чат сделки
            {trade && (
              <span className="text-sm text-[#71717A] font-mono">#{trade.id?.slice(0, 12)}</span>
            )}
          </DialogTitle>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-[#7C3AED]" />
          </div>
        ) : trade ? (
          <div className="flex-1 overflow-hidden flex flex-col">
            {/* Trade Info Card */}
            <div className="px-4 pt-3 pb-2">
              <div className="bg-[#0A0A0A] rounded-xl p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-[#10B981] font-bold font-mono">{trade.amount_usdt} USDT</span>
                    <span className="text-[#52525B]">=</span>
                    <span className="text-white font-mono">{trade.amount_rub?.toLocaleString()} ₽</span>
                  </div>
                  <span className={`px-2 py-0.5 rounded-full text-xs ${getStatusConfig(trade.status).bg} ${getStatusConfig(trade.status).color}`}>
                    {getStatusConfig(trade.status).label}
                  </span>
                </div>
                
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-[#52525B]">Продавец: </span>
                    <span className="text-[#10B981]">{trade.seller_nickname || "—"}</span>
                  </div>
                  <div>
                    <span className="text-[#52525B]">Покупатель: </span>
                    <span className="text-[#7C3AED]">{trade.buyer_nickname || "Клиент"}</span>
                  </div>
                  <div>
                    <span className="text-[#52525B]">Создана: </span>
                    <span className="text-[#A1A1AA]">{formatDate(trade.created_at)}</span>
                  </div>
                  {trade.completed_at && (
                    <div>
                      <span className="text-[#52525B]">Завершена: </span>
                      <span className="text-[#A1A1AA]">{formatDate(trade.completed_at)}</span>
                    </div>
                  )}
                </div>

                {/* Dispute info */}
                {trade.status === "disputed" && trade.disputed_by_role && (
                  <div className="bg-[#EF4444]/10 rounded-lg p-2 mt-2">
                    <div className="flex items-center gap-2 text-[#EF4444] text-xs font-semibold">
                      <AlertTriangle className="w-3 h-3" />
                      Спор открыт {trade.disputed_by_role}
                    </div>
                    {trade.dispute_reason && (
                      <div className="text-[#A1A1AA] text-xs mt-1">Причина: {trade.dispute_reason}</div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 pb-4 space-y-2">
              <div className="text-[#52525B] text-xs mb-2">
                Сообщений: {messages.length}
              </div>
              
              {messages.length === 0 ? (
                <div className="text-center py-8 text-[#52525B]">
                  <MessageCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p>Нет сообщений</p>
                </div>
              ) : (
                messages.map((msg, idx) => {
                  const isOwn = msg.sender_id === currentUser?.id;
                  const isSystem = msg.is_system || msg.sender_role === "system" || msg.sender_type === "system";
                  const roleInfo = getRoleInfo(msg.sender_role || msg.sender_type);
                  
                  if (isSystem) {
                    return (
                      <div key={msg.id || idx} className="flex justify-center">
                        <div className="bg-[#6B7280]/20 text-[#A1A1AA] text-xs px-3 py-1.5 rounded-full max-w-[90%] text-center">
                          {msg.content}
                        </div>
                      </div>
                    );
                  }

                  return (
                    <div key={msg.id || idx} className={`flex ${isOwn ? "justify-end" : "justify-start"}`}>
                      <div className="max-w-[80%]">
                        {!isOwn && (
                          <div className="text-[10px] text-[#71717A] mb-0.5 ml-2">
                            {msg.sender_name || msg.sender_nickname} • {roleInfo.name}
                          </div>
                        )}
                        <div className={`rounded-2xl px-4 py-2 ${
                          isOwn 
                            ? "bg-[#7C3AED] text-white" 
                            : roleInfo.color
                        }`}>
                          <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                          <div className={`text-[10px] mt-1 ${isOwn ? "text-white/60" : "opacity-60"}`}>
                            {formatTime(msg.created_at)}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>
        ) : (
          <div className="text-center py-8 text-[#71717A]">
            Сделка не найдена
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default TradeChatModal;
