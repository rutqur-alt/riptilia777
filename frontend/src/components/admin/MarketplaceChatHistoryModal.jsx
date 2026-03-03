import React, { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { 
  MessageCircle, Copy, Clock, User, Bot, Shield, 
  Package, CheckCircle, XCircle, AlertTriangle,
  Loader2, ShoppingBag
} from "lucide-react";
import axios from "axios";
import { API, useAuth } from "@/App";

/**
 * Компонент для просмотра полной истории чата заказа маркетплейса.
 */
export function MarketplaceChatHistoryModal({ isOpen, onClose, orderId }) {
  const { token } = useAuth();
  const [loading, setLoading] = useState(true);
  const [order, setOrder] = useState(null);
  const [messages, setMessages] = useState([]);

  useEffect(() => {
    if (isOpen && orderId) {
      fetchHistory();
    }
  }, [isOpen, orderId]);

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/admin/marketplace-history/${orderId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setOrder(res.data);
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
      case "mod_market": 
      case "mod_p2p": return <Shield className="w-4 h-4 text-[#3B82F6]" />;
      case "seller": return <User className="w-4 h-4 text-[#10B981]" />;
      case "buyer": return <User className="w-4 h-4 text-[#F59E0B]" />;
      case "guarantor": return <Shield className="w-4 h-4 text-[#8B5CF6]" />;
      default: return <User className="w-4 h-4 text-[#71717A]" />;
    }
  };

  const getSenderColor = (role) => {
    switch (role) {
      case "system": return "text-[#7C3AED]";
      case "admin": 
      case "mod_market":
      case "mod_p2p": return "text-[#3B82F6]";
      case "seller": return "text-[#10B981]";
      case "buyer": return "text-[#F59E0B]";
      case "guarantor": return "text-[#8B5CF6]";
      default: return "text-[#71717A]";
    }
  };

  const getStatusBadge = (status) => {
    const config = {
      pending_confirmation: { color: "bg-[#F59E0B]/10 text-[#F59E0B]", label: "Ожидание" },
      confirmed: { color: "bg-[#3B82F6]/10 text-[#3B82F6]", label: "Подтверждён" },
      completed: { color: "bg-[#10B981]/10 text-[#10B981]", label: "Завершён" },
      delivered: { color: "bg-[#10B981]/10 text-[#10B981]", label: "Доставлен" },
      cancelled: { color: "bg-[#71717A]/10 text-[#71717A]", label: "Отменён" },
      disputed: { color: "bg-[#EF4444]/10 text-[#EF4444]", label: "Спор" },
      refunded: { color: "bg-[#F59E0B]/10 text-[#F59E0B]", label: "Возврат" }
    };
    const cfg = config[status] || config.pending_confirmation;
    return <span className={`px-2 py-0.5 rounded-full text-xs ${cfg.color}`}>{cfg.label}</span>;
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="bg-[#121212] border-white/10 text-white max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-white">
            <ShoppingBag className="w-5 h-5" />
            История чата заказа
          </DialogTitle>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-[#7C3AED]" />
          </div>
        ) : order ? (
          <div className="flex-1 overflow-hidden flex flex-col">
            {/* Order Info */}
            <div className="bg-[#0A0A0A] rounded-xl p-4 mb-4 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Package className="w-4 h-4 text-[#7C3AED]" />
                  <span className="text-white font-mono text-sm">ID: {order.id}</span>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={() => copy(order.id)}
                    className="h-6 w-6 p-0 text-[#7C3AED]"
                  >
                    <Copy className="w-3 h-3" />
                  </Button>
                </div>
                {getStatusBadge(order.status)}
              </div>
              
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-[#71717A]">Товар:</span>
                  <span className="text-white ml-2">{order.product_name || 'N/A'}</span>
                </div>
                <div>
                  <span className="text-[#71717A]">Кол-во:</span>
                  <span className="text-white ml-2">{order.quantity || 1} шт.</span>
                </div>
                <div>
                  <span className="text-[#71717A]">Сумма:</span>
                  <span className="text-[#10B981] ml-2">{order.total_price} USDT</span>
                </div>
                <div>
                  <span className="text-[#71717A]">Тип:</span>
                  <span className="text-white ml-2">{order.purchase_type === 'guarantor' ? 'Через гаранта' : 'Моментальная'}</span>
                </div>
                <div>
                  <span className="text-[#71717A]">Покупатель:</span>
                  <span className="text-[#F59E0B] ml-2">{order.buyer_nickname || order.buyer_info?.nickname || 'N/A'}</span>
                </div>
                <div>
                  <span className="text-[#71717A]">Продавец:</span>
                  <span className="text-[#10B981] ml-2">{order.seller_nickname || order.seller_info?.nickname || 'N/A'}</span>
                </div>
                <div>
                  <span className="text-[#71717A]">Создан:</span>
                  <span className="text-white ml-2">{new Date(order.created_at).toLocaleString("ru-RU")}</span>
                </div>
                {order.completed_at && (
                  <div>
                    <span className="text-[#71717A]">Завершён:</span>
                    <span className="text-white ml-2">{new Date(order.completed_at).toLocaleString("ru-RU")}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto space-y-2 pr-2">
              <div className="text-[#71717A] text-xs mb-2">
                Сообщений: {messages.length}
              </div>
              
              {messages.length === 0 ? (
                <div className="text-center py-8 text-[#52525B]">
                  <MessageCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p>Нет сообщений в чате</p>
                  <p className="text-xs mt-1">Чат создаётся при покупке через гаранта</p>
                </div>
              ) : (
                messages.map((msg, idx) => (
                  <div 
                    key={msg.id || idx}
                    className={`p-3 rounded-lg ${
                      msg.sender_role === "system" || msg.is_system
                        ? "bg-[#7C3AED]/10 border border-[#7C3AED]/20"
                        : msg.sender_role === "admin" || msg.sender_role === "mod_market" || msg.sender_role === "guarantor"
                          ? "bg-[#3B82F6]/10 border border-[#3B82F6]/20"
                          : "bg-white/5"
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      {getSenderIcon(msg.sender_role)}
                      <span className={`text-sm font-medium ${getSenderColor(msg.sender_role)}`}>
                        {msg.sender_name || msg.sender_role || 'Система'}
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
            Заказ не найден
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default MarketplaceChatHistoryModal;
