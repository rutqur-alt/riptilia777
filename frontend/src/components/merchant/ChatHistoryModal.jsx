import { useState, useEffect, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { MERCHANT_ROLE_DISPLAY, getMerchantRoleDisplay } from "./merchantRoleDisplay";
import { AlertTriangle, Loader, MessageCircle, Send } from "lucide-react";

export default function ChatHistoryModal({ open, onClose, tradeId, token, canOpenDispute, onDisputeOpened, isCryptoOrder = false }) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [trade, setTrade] = useState(null);
  const [openingDispute, setOpeningDispute] = useState(false);
  const [newMessage, setNewMessage] = useState('');
  const [sendingMessage, setSendingMessage] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (open && tradeId) {
      fetchChat();
      // Poll for new messages in disputes
      const interval = setInterval(() => {
        if (trade && ['dispute', 'disputed'].includes(trade.status)) {
          fetchChat(true);
        }
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [open, tradeId, trade?.status]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const fetchChat = async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      // Use different API for crypto orders (payouts)
      const endpoint = isCryptoOrder 
        ? `${API}/merchant/crypto-orders/${tradeId}/chat`
        : `${API}/merchant/trades/${tradeId}/chat`;
      const res = await axios.get(endpoint, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setMessages(res.data.messages || []);
      setTrade(res.data.trade || null);
    } catch (error) {
      console.error(error);
      if (!silent) toast.error("Не удалось загрузить чат");
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const sendMessage = async () => {
    if (!newMessage.trim() || !tradeId) return;
    setSendingMessage(true);
    try {
      await axios.post(`${API}/merchant/disputes/${tradeId}/messages`, 
        { content: newMessage.trim() },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setNewMessage('');
      await fetchChat(true);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка отправки сообщения');
    } finally {
      setSendingMessage(false);
    }
  };

  const isQrTrade = trade?.qr_aggregator_trade || trade?.is_qr_aggregator;

  const handleOpenDispute = async () => {
    if (!window.confirm("Вы уверены что хотите открыть спор по этой сделке?")) return;
    setOpeningDispute(true);
    try {
      const url = isQrTrade
        ? `${API}/qr-aggregator/trades/${tradeId}/dispute`
        : `${API}/merchant/disputes/${tradeId}/open`;
      await axios.post(url, { reason: "Спор открыт мерчантом" }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Спор открыт");
      if (onDisputeOpened) onDisputeOpened();
      onClose();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка открытия спора");
    } finally {
      setOpeningDispute(false);
    }
  };

  const getStatusLabel = (status) => {
    const labels = {
      pending: "Ожидает", active: "Активна", paid: "Оплачено", waiting: "Ожидание",
      completed: "Завершено", cancelled: "Отменено", dispute: "Спор", disputed: "Спор",
      pending_completion: "⏳ Завершается"
    };
    return labels[status] || status;
  };

  const getStatusColor = (status) => {
    if (["completed"].includes(status)) return "text-[#10B981]";
    if (["cancelled"].includes(status)) return "text-[#71717A]";
    if (["dispute", "disputed"].includes(status)) return "text-[#EF4444]";
    if (status === "pending_completion") return "text-[#F59E0B]";
    return "text-[#F59E0B]";
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="bg-[#121212] border-white/10 text-white max-w-lg max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <MessageCircle className="w-5 h-5 text-[#3B82F6]" />
            История чата
            {trade && (
              <span className={`text-sm font-normal ml-2 ${getStatusColor(trade.status)}`}>
                ({getStatusLabel(trade.status)})
              </span>
            )}
          </DialogTitle>
        </DialogHeader>

        {/* Trade info */}
        {trade && (
          <div className="bg-[#1A1A1A] rounded-xl p-3 flex items-center justify-between">
            <div>
              <div className="text-sm text-white font-medium">
                {trade.buyer_nickname || trade.client_nickname || "Клиент"}
              </div>
              <div className="text-xs text-[#71717A]">
                {(trade.client_amount_rub || trade.amount_rub || 0).toLocaleString("ru-RU", {maximumFractionDigits: 0})} ₽
              </div>
            </div>
            <div className="text-xs text-[#52525B]">
              #{tradeId?.slice(-6)}
            </div>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto space-y-2 min-h-[200px] max-h-[400px] pr-1" style={{scrollbarWidth: "thin", scrollbarColor: "#333 transparent"}}>
          {loading ? (
            <div className="flex justify-center py-10">
              <Loader className="w-6 h-6 animate-spin text-[#71717A]" />
            </div>
          ) : messages.length === 0 ? (
            <div className="text-center py-10">
              <MessageCircle className="w-12 h-12 text-[#52525B] mx-auto mb-3" />
              <p className="text-[#71717A] text-sm">Сообщений нет</p>
            </div>
          ) : (
            messages.map((msg, i) => {
              const ri = getMerchantRoleDisplay(msg.sender_role);
              return (
              <div key={i} className={`flex ${msg.sender_role === "merchant" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[80%] rounded-xl px-3 py-2 ${ri.bg}`}>
                  <div className="text-xs font-medium mb-1" style={{color: ri.color}}>
                    <span className="opacity-60">[{ri.label}]</span>{" "}
                    {msg.sender_name || msg.sender_nickname || ri.label}
                  </div>
                  <div className="text-sm whitespace-pre-wrap break-words">{msg.text || msg.content || msg.message}</div>
                  <div className="text-[10px] text-[#52525B] mt-1 text-right">
                    {msg.created_at ? new Date(msg.created_at).toLocaleString("ru-RU") : ""}
                  </div>
                </div>
              </div>
            );})          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Message Input for Disputes */}
        {trade && ['dispute', 'disputed'].includes(trade.status) && (
          <div className="pt-3 border-t border-white/5">
            <div className="flex gap-2">
              <input
                type="text"
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                placeholder="Написать сообщение в спор..."
                className="flex-1 px-4 py-2.5 bg-[#0A0A0A] border border-white/10 rounded-xl text-white text-sm placeholder-[#52525B] focus:outline-none focus:border-[#3B82F6]/50"
              />
              <button
                onClick={sendMessage}
                disabled={!newMessage.trim() || sendingMessage}
                className="px-4 py-2.5 bg-[#3B82F6] hover:bg-[#2563EB] disabled:opacity-50 text-white rounded-xl transition-colors"
              >
                {sendingMessage ? (
                  <Loader className="w-5 h-5 animate-spin" />
                ) : (
                  <Send className="w-5 h-5" />
                )}
              </button>
            </div>
          </div>
        )}

        {/* Open Dispute button — for regular trades: not cancelled/completed; for QR trades: also cancelled */}
        {canOpenDispute && trade && !['dispute', 'disputed', 'completed'].includes(trade.status) && (
          (isQrTrade ? !['dispute', 'disputed', 'completed'].includes(trade.status) : !['cancelled'].includes(trade.status)) && (
            <div className="pt-2 border-t border-white/5">
              <Button
                onClick={handleOpenDispute}
                disabled={openingDispute}
                className="w-full bg-[#EF4444] hover:bg-[#DC2626] text-white h-10 rounded-xl"
              >
                {openingDispute ? (
                  <Loader className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <AlertTriangle className="w-4 h-4 mr-2" />
                )}
                Открыть спор
              </Button>
            </div>
          )
        )}
      </DialogContent>
    </Dialog>
  );
}
