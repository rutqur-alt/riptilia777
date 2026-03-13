import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { API } from "@/App";
import axios from "axios";
import { 
  CheckCircle, XCircle, Clock, MessageCircle, Copy, Download, Shield, AlertTriangle 
} from "lucide-react";

export default function PurchaseCard({ purchase, expandedId, toggleExpand, copyToClipboard, onRefresh, token }) {
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [disputing, setDisputing] = useState(false);
  const [disputeReason, setDisputeReason] = useState("");
  const [showDisputeForm, setShowDisputeForm] = useState(false);

  const handleConfirm = async () => {
    setConfirming(true);
    try {
      const response = await axios.post(
        `${API}/marketplace/purchases/${purchase.id}/confirm`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      // Format delivered content for display
      const formatContent = (content) => {
        if (!content) return null;
        const items = Array.isArray(content) ? content : [content];
        return items.map(item => {
          if (typeof item === 'string') return item;
          if (typeof item === 'object' && item !== null) return item.text || '';
          return String(item);
        }).filter(Boolean).join('\n---\n');
      };
      
      toast.success(
        <div>
          <div className="font-semibold">Покупка подтверждена!</div>
          {response.data.delivered_content && (
            <div className="text-sm mt-2 font-mono bg-black/20 p-2 rounded break-all whitespace-pre-wrap max-h-32 overflow-y-auto">
              {formatContent(response.data.delivered_content)}
            </div>
          )}
        </div>,
        { duration: 15000 }
      );
      onRefresh();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка подтверждения");
    } finally {
      setConfirming(false);
    }
  };

  const handleCancel = async () => {
    setCancelling(true);
    try {
      await axios.post(
        `${API}/marketplace/purchases/${purchase.id}/cancel`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success("Заказ отменён, средства возвращены");
      onRefresh();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка отмены");
    } finally {
      setCancelling(false);
    }
  };

  const handleDispute = async () => {
    if (!disputeReason.trim()) {
      toast.error("Укажите причину спора");
      return;
    }
    setDisputing(true);
    try {
      await axios.post(
        `${API}/marketplace/purchases/${purchase.id}/dispute`,
        {},
        { 
          headers: { Authorization: `Bearer ${token}` },
          params: { reason: disputeReason }
        }
      );
      toast.success("Спор открыт. Администратор рассмотрит вашу заявку.");
      setShowDisputeForm(false);
      onRefresh();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка открытия спора");
    } finally {
      setDisputing(false);
    }
  };

  // Status badge
  const getStatusBadge = () => {
    switch (purchase.status) {
      case "completed":
        return <span className="px-2 py-1 text-xs rounded-full bg-[#10B981]/10 text-[#10B981]">Завершено</span>;
      case "pending_confirmation":
        return <span className="px-2 py-1 text-xs rounded-full bg-[#F59E0B]/10 text-[#F59E0B] flex items-center gap-1"><Clock className="w-3 h-3" />Ожидает подтверждения</span>;
      case "disputed":
        return <span className="px-2 py-1 text-xs rounded-full bg-[#EF4444]/10 text-[#EF4444]">Спор</span>;
      case "cancelled":
        return <span className="px-2 py-1 text-xs rounded-full bg-[#71717A]/10 text-[#71717A]">Отменено</span>;
      case "refunded":
        return <span className="px-2 py-1 text-xs rounded-full bg-[#3B82F6]/10 text-[#3B82F6]">Возврат</span>;
      default:
        return <span className="px-2 py-1 text-xs rounded-full bg-[#71717A]/10 text-[#71717A]">{purchase.status}</span>;
    }
  };

  const isGuarantor = purchase.purchase_type === "guarantor";
  const isPending = purchase.status === "pending_confirmation";
  const hasContent = purchase.delivered_content && (Array.isArray(purchase.delivered_content) ? purchase.delivered_content.length > 0 : purchase.delivered_content);

  return (
    <div className={`bg-[#121212] border rounded-xl p-5 ${isPending ? "border-[#F59E0B]/30" : "border-white/5"}`}>
      {/* Order Number */}
      <div className="flex items-center justify-between text-xs text-[#52525B] mb-2">
        <div className="flex items-center gap-2">
          <span>Заказ #{purchase.id?.slice(0, 8).toUpperCase()}</span>
          {purchase.unread_messages > 0 && (
            <span className="px-1.5 py-0.5 text-[10px] rounded-full bg-[#EF4444] text-white font-bold animate-pulse">
              {purchase.unread_messages} новых
            </span>
          )}
        </div>
        <span>{new Date(purchase.created_at).toLocaleString("ru-RU")}</span>
      </div>
      
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-white font-semibold">{purchase.product_name}</span>
            {isGuarantor && (
              <span className="px-1.5 py-0.5 text-[10px] rounded bg-[#7C3AED]/20 text-[#A78BFA] flex items-center gap-1">
                <Shield className="w-3 h-3" />Гарант
              </span>
            )}
          </div>
          <div className="text-sm text-[#71717A]">@{purchase.seller_nickname}</div>
        </div>
        {getStatusBadge()}
      </div>
      
      <div className="flex items-center justify-between text-sm mb-2">
        <span className="text-[#71717A]">Количество: {purchase.quantity}</span>
        <div className="text-right">
          <span className="text-[#10B981] font-mono">{purchase.total_price?.toFixed(2)} USDT</span>
          {isGuarantor && purchase.guarantor_fee > 0 && (
            <div className="text-xs text-[#7C3AED]">+{purchase.guarantor_fee?.toFixed(2)} гарант</div>
          )}
        </div>
      </div>

      {/* Auto-complete countdown for pending */}
      {isPending && purchase.auto_complete_at && (
        <div className="mb-3 p-2 bg-[#F59E0B]/5 border border-[#F59E0B]/20 rounded-lg text-xs text-[#F59E0B] flex items-center gap-2">
          <Clock className="w-4 h-4" />
          <span>Автозавершение: {new Date(purchase.auto_complete_at).toLocaleDateString("ru-RU")}</span>
        </div>
      )}

      {/* Action buttons for pending guarantor orders */}
      {isPending && (
        <div className="space-y-2 mt-3">
          <div className="flex gap-2">
            <Button
              onClick={handleConfirm}
              disabled={confirming}
              className="flex-1 bg-[#10B981] hover:bg-[#059669] text-white"
             title="Подтвердить получение оплаты">
              {confirming ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <CheckCircle className="w-4 h-4 mr-2" />
                  Подтвердить получение
                </>
              )}
            </Button>
            <Button
              onClick={handleCancel}
              disabled={cancelling}
              variant="outline"
              className="border-[#EF4444]/30 text-[#EF4444] hover:bg-[#EF4444]/10"
            >
              {cancelling ? (
                <div className="w-4 h-4 border-2 border-[#EF4444] border-t-transparent rounded-full animate-spin" />
              ) : (
                <XCircle className="w-4 h-4" />
              )}
            </Button>
          </div>
          
          {/* Chat button - different for guarantor vs regular purchases */}
          {isGuarantor ? (
            <Button
              onClick={() => navigate(`/trader/guarantor-chat/${purchase.id}`)}
              variant="outline"
              size="sm"
              className="w-full text-[#7C3AED] border-[#7C3AED]/30 hover:bg-[#7C3AED]/10 text-xs"
            >
              <Shield className="w-3 h-3 mr-1" />
              Чат гаранта
            </Button>
          ) : (
            <Button
              onClick={() => {
                const orderId = purchase.id?.slice(0, 8).toUpperCase();
                navigate(`/trader/shop-chats?shop=${purchase.seller_id}&subject=${encodeURIComponent(`Вопрос по заказу #${orderId}`)}`);
              }}
              variant="outline"
              size="sm"
              className="w-full text-[#7C3AED] border-[#7C3AED]/30 hover:bg-[#7C3AED]/10 text-xs"
            >
              <MessageCircle className="w-3 h-3 mr-1" />
              Вопрос по заказу
            </Button>
          )}
          
          {!showDisputeForm ? (
            <Button
              onClick={() => setShowDisputeForm(true)}
              variant="ghost"
              size="sm"
              className="w-full text-[#71717A] hover:text-[#EF4444] text-xs"
             title="Открыть спор по сделке">
              <AlertTriangle className="w-3 h-3 mr-1" />
              Открыть спор
            </Button>
          ) : (
            <div className="p-3 bg-[#0A0A0A] border border-[#EF4444]/20 rounded-lg space-y-2">
              <textarea
                value={disputeReason}
                onChange={(e) => setDisputeReason(e.target.value)}
                placeholder="Опишите проблему..."
                className="w-full bg-[#121212] border border-white/10 rounded-lg p-2 text-white text-sm resize-none h-20"
              />
              <div className="flex gap-2">
                <Button
                  onClick={handleDispute}
                  disabled={disputing}
                  size="sm"
                  className="flex-1 bg-[#EF4444] hover:bg-[#DC2626] text-white text-xs"
                >
                  {disputing ? "Отправка..." : "Отправить спор"}
                </Button>
                <Button
                  onClick={() => setShowDisputeForm(false)}
                  variant="outline"
                  size="sm"
                  className="text-xs"
                 title="Отменить действие">
                  Отмена
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
      
      {/* Show/Hide Product Button for completed orders */}
      {hasContent && (
        <div className="mt-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => toggleExpand(purchase.id)}
            className="w-full border-[#7C3AED]/30 text-[#A78BFA] hover:bg-[#7C3AED]/10"
          >
            {expandedId === purchase.id ? (
              <>
                <XCircle className="w-4 h-4 mr-2" />
                Скрыть товар
              </>
            ) : (
              <>
                <CheckCircle className="w-4 h-4 mr-2" />
                Показать товар
              </>
            )}
          </Button>
          
          {expandedId === purchase.id && (
            <div className="mt-3 p-4 bg-[#0A0A0A] border border-[#7C3AED]/20 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <div className="text-xs text-[#A78BFA]">Полученный товар ({Array.isArray(purchase.delivered_content) ? purchase.delivered_content.length : 1} шт.):</div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    const content = Array.isArray(purchase.delivered_content) 
                      ? purchase.delivered_content.map(item => typeof item === 'object' ? item.text : item).join('\n')
                      : (typeof purchase.delivered_content === 'object' ? purchase.delivered_content.text : purchase.delivered_content);
                    copyToClipboard(content);
                  }}
                  className="text-[#71717A] hover:text-white p-1 h-auto"
                >
                  <Copy className="w-4 h-4" />
                </Button>
              </div>
              <div className="space-y-2">
                {(Array.isArray(purchase.delivered_content) ? purchase.delivered_content : [purchase.delivered_content]).map((item, idx) => {
                  const itemText = typeof item === 'object' ? item.text : item;
                  const itemPhoto = typeof item === 'object' ? item.photo_url : null;
                  const itemFile = typeof item === 'object' ? item.file_url : null;
                  
                  return (
                    <div key={idx} className="bg-[#121212] p-3 rounded border border-white/5 space-y-2">
                      {/* Text content */}
                      {itemText && (
                        <div className="flex items-center justify-between">
                          <span className="text-sm text-white font-mono break-all">{itemText}</span>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => copyToClipboard(itemText)}
                            className="text-[#52525B] hover:text-white p-1 h-auto ml-2 flex-shrink-0"
                          >
                            <Copy className="w-3 h-3" />
                          </Button>
                        </div>
                      )}
                      
                      {/* Photo */}
                      {itemPhoto && !itemPhoto.includes("[") && (
                        <div className="mt-2">
                          <img src={itemPhoto} alt="" className="max-w-full max-h-48 rounded-lg" />
                        </div>
                      )}
                      {itemPhoto && itemPhoto.includes("[") && (
                        <div className="text-xs text-[#71717A] italic">{itemPhoto}</div>
                      )}
                      
                      {/* File */}
                      {itemFile && !itemFile.includes("[") && (
                        <div className="mt-2">
                          <a 
                            href={itemFile} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="text-xs text-[#7C3AED] hover:text-[#A78BFA] flex items-center gap-1"
                          >
                            <Download className="w-3 h-3" />
                            Скачать файл
                          </a>
                        </div>
                      )}
                      {itemFile && itemFile.includes("[") && (
                        <div className="text-xs text-[#71717A] italic">{itemFile}</div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
      
      {/* Question about order button - for all orders */}
      {!isPending && (
        <div className="mt-3">
          <Button
            onClick={() => {
              const orderId = purchase.id?.slice(0, 8).toUpperCase();
              navigate(`/trader/shop-chats?shop=${purchase.seller_id}&subject=${encodeURIComponent(`Вопрос по заказу #${orderId}`)}`);
            }}
            variant="outline"
            size="sm"
            className="w-full text-[#7C3AED] border-[#7C3AED]/30 hover:bg-[#7C3AED]/10 text-xs"
          >
            <MessageCircle className="w-3 h-3 mr-1" />
            Вопрос по заказу #{purchase.id?.slice(0, 8).toUpperCase()}
          </Button>
        </div>
      )}
      
      <div className="text-xs text-[#52525B] mt-3">
        {new Date(purchase.created_at).toLocaleString("ru-RU")}
      </div>
    </div>
  );
}
