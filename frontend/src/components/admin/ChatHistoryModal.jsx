import React, { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { 
  MessageCircle, Copy, Clock, User, Bot, Shield, 
  CreditCard, CheckCircle, XCircle, AlertTriangle,
  Loader2
} from "lucide-react";
import axios from "axios";
import { API, useAuth } from "@/App";

/**
 * Компонент для просмотра полной истории чата сделки.
 * Используется админами, модераторами и мерчантами.
 * Показывает ВСЕ сообщения и реквизиты, независимо от статуса сделки.
 */
export function ChatHistoryModal({ isOpen, onClose, tradeId }) {
  const { token } = useAuth();
  const [loading, setLoading] = useState(true);
  const [trade, setTrade] = useState(null);
  const [messages, setMessages] = useState([]);

  useEffect(() => {
    if (isOpen && tradeId) {
      fetchHistory();
    }
  }, [isOpen, tradeId]);

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/admin/trades-history/${tradeId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTrade(res.data);
      setMessages(res.data.messages || []);
    } catch (err) {
      toast.error("Ошибка загрузки истории");
    } finally {
      setLoading(false);
    }
  };

  const copy = (text) => {
    navigator.clipboard.writeText(text);
    toast.success("Скопировано");
  };

  const getSenderIcon = (role) => {
    switch (role) {
      case "system": return <Bot className="w-4 h-4 text-[#7C3AED]" />;
      case "admin": 
      case "mod_p2p": return <Shield className="w-4 h-4 text-[#3B82F6]" />;
      case "trader": return <User className="w-4 h-4 text-[#10B981]" />;
      case "client": return <User className="w-4 h-4 text-[#F59E0B]" />;
      default: return <User className="w-4 h-4 text-[#71717A]" />;
    }
  };

  const getSenderColor = (role) => {
    switch (role) {
      case "system": return "text-[#7C3AED]";
      case "admin": 
      case "mod_p2p": return "text-[#3B82F6]";
      case "trader": return "text-[#10B981]";
      case "client": return "text-[#F59E0B]";
      default: return "text-[#71717A]";
    }
  };

  const getStatusBadge = (status) => {
    const config = {
      pending: { color: "bg-[#F59E0B]/10 text-[#F59E0B]", label: "Ожидание" },
      paid: { color: "bg-[#3B82F6]/10 text-[#3B82F6]", label: "Оплачено" },
      completed: { color: "bg-[#10B981]/10 text-[#10B981]", label: "Завершена" },
      cancelled: { color: "bg-[#71717A]/10 text-[#71717A]", label: "Отменена" },
      disputed: { color: "bg-[#EF4444]/10 text-[#EF4444]", label: "Спор" }
    };
    const cfg = config[status] || config.pending;
    return <span className={`px-2 py-0.5 rounded-full text-xs ${cfg.color}`}>{cfg.label}</span>;
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="bg-[#121212] border-white/10 text-white max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-white">
            <MessageCircle className="w-5 h-5" />
            История чата сделки
          </DialogTitle>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-[#7C3AED]" />
          </div>
        ) : trade ? (
          <div className="flex-1 overflow-hidden flex flex-col">
            {/* Trade Info */}
            <div className="bg-[#0A0A0A] rounded-xl p-4 mb-4 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-white font-mono text-sm">ID: {trade.id}</span>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={() => copy(trade.id)}
                    className="h-6 w-6 p-0 text-[#7C3AED]"
                  >
                    <Copy className="w-3 h-3" />
                  </Button>
                </div>
                {getStatusBadge(trade.status)}
              </div>
              
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-[#71717A]">Сумма:</span>
                  <span className="text-white ml-2">{trade.amount_usdt} USDT = {trade.amount_rub} ₽</span>
                </div>
                <div>
                  <span className="text-[#71717A]">Курс:</span>
                  <span className="text-white ml-2">{trade.price_rub} ₽/USDT</span>
                </div>
                <div>
                  <span className="text-[#71717A]">Продавец:</span>
                  <span className="text-[#10B981] ml-2">{trade.seller_nickname || trade.trader_login || 'N/A'}</span>
                </div>
                <div>
                  <span className="text-[#71717A]">Покупатель:</span>
                  <span className="text-[#F59E0B] ml-2">{trade.buyer_nickname || trade.buyer_login || 'Клиент'}</span>
                </div>
                <div>
                  <span className="text-[#71717A]">Создана:</span>
                  <span className="text-white ml-2">{new Date(trade.created_at).toLocaleString("ru-RU")}</span>
                </div>
                {trade.completed_at && (
                  <div>
                    <span className="text-[#71717A]">Завершена:</span>
                    <span className="text-white ml-2">{new Date(trade.completed_at).toLocaleString("ru-RU")}</span>
                  </div>
                )}
              </div>

              {/* Dispute info */}
              {trade.status === "disputed" && trade.disputed_by_role && (
                <div className="bg-[#EF4444]/10 border border-[#EF4444]/20 rounded-lg p-3 mt-2">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-[#EF4444]" />
                    <span className="text-[#EF4444] text-sm font-bold">Спор открыт {trade.disputed_by_role}</span>
                  </div>
                  {trade.dispute_reason && (
                    <div className="text-[#A1A1AA] text-xs mt-1">Причина: {trade.dispute_reason}</div>
                  )}
                </div>
              )}

              {/* Requisites */}
              {trade.requisites_history?.length > 0 && (
                <div className="mt-3 pt-3 border-t border-white/5">
                  <div className="text-[#71717A] text-xs mb-2">Выданные реквизиты:</div>
                  {trade.requisites_history.map((req, idx) => (
                    <div key={idx} className="bg-white/5 rounded-lg p-2 text-sm">
                      <div className="flex items-center gap-2 text-white">
                        <CreditCard className="w-4 h-4 text-[#7C3AED]" />
                        {req.data?.bank_name || req.type}
                      </div>
                      {req.data?.card_number && (
                        <div className="text-[#A1A1AA] text-xs mt-1">
                          Карта: {req.data.card_number}
                        </div>
                      )}
                      {req.data?.phone && (
                        <div className="text-[#A1A1AA] text-xs mt-1">
                          Телефон: {req.data.phone}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto space-y-2 pr-2">
              <div className="text-[#71717A] text-xs mb-2">
                Сообщений: {messages.length}
              </div>
              
              {messages.length === 0 ? (
                <div className="text-center py-8 text-[#52525B]">
                  <MessageCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p>Нет сообщений</p>
                </div>
              ) : (
                messages.map((msg, idx) => (
                  <div 
                    key={msg.id || idx}
                    className={`p-3 rounded-lg ${
                      msg.sender_role === "system" 
                        ? "bg-[#7C3AED]/10 border border-[#7C3AED]/20"
                        : msg.sender_role === "admin" || msg.sender_role === "mod_p2p"
                          ? "bg-[#3B82F6]/10 border border-[#3B82F6]/20"
                          : "bg-white/5"
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      {getSenderIcon(msg.sender_role)}
                      <span className={`text-sm font-medium ${getSenderColor(msg.sender_role)}`}>
                        {msg.sender_nickname || msg.sender_role || 'Система'}
                      </span>
                      <span className="text-[#52525B] text-xs flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {new Date(msg.created_at).toLocaleString("ru-RU")}
                      </span>
                    </div>
                    <p className="text-white text-sm whitespace-pre-wrap">{msg.content}</p>
                  </div>
                ))
              )}
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

export default ChatHistoryModal;
