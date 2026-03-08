import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { useAuth, API } from "@/App";
import { Loader, ShoppingBag } from "lucide-react";

export default function MerchantPurchases() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [purchases, setPurchases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    fetchPurchases();
  }, []);

  const fetchPurchases = async () => {
    try {
      const response = await axios.get(`${API}/marketplace/my-purchases`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setPurchases(response.data || []);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleExpand = async (purchase) => {
    const newId = expandedId === purchase.id ? null : purchase.id;
    setExpandedId(newId);
    // Mark as viewed when expanding
    if (newId && !purchase.viewed) {
      try {
        await axios.post(`${API}/marketplace/purchases/${purchase.id}/mark-viewed`, {}, {
          headers: { Authorization: `Bearer ${token}` }
        });
        // Update local state
        setPurchases(prev => prev.map(p => p.id === purchase.id ? { ...p, viewed: true } : p));
      } catch (e) { console.error(e); }
    }
  };

  const getStatusBadge = (status) => {
    const styles = {
      completed: "bg-[#10B981]/10 text-[#10B981]",
      pending_confirmation: "bg-[#F59E0B]/10 text-[#F59E0B]",
      disputed: "bg-[#EF4444]/10 text-[#EF4444]",
      cancelled: "bg-[#71717A]/10 text-[#71717A]",
      refunded: "bg-[#3B82F6]/10 text-[#3B82F6]"
    };
    const labels = {
      completed: "Завершено",
      pending_confirmation: "Ожидает подтверждения",
      disputed: "Спор",
      cancelled: "Отменено",
      refunded: "Возврат",
      delivered: "Доставлено"
    };
    return (
      <span className={`text-xs px-2 py-1 rounded-lg ${styles[status] || "bg-[#71717A]/10 text-[#71717A]"}`}>
        {labels[status] || status}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Мои покупки</h1>
        <p className="text-[#71717A]">История заказов с маркетплейса</p>
      </div>

      {loading ? (
        <div className="flex justify-center py-20"><Loader className="w-8 h-8 animate-spin text-[#71717A]" /></div>
      ) : purchases.length === 0 ? (
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-6 text-center py-20">
          <ShoppingBag className="w-16 h-16 text-[#52525B] mx-auto mb-4" />
          <p className="text-[#71717A]">У вас пока нет покупок на маркетплейсе</p>
          <a href="/marketplace">
            <button className="mt-4 px-6 py-2 bg-[#7C3AED] hover:bg-[#6D28D9] text-white rounded-full text-sm">
              Перейти в каталог
            </button>
          </a>
        </div>
      ) : (
        <div className="space-y-3">
          {purchases.map(p => (
            <div key={p.id} 
              className={`bg-[#121212] border rounded-xl p-4 cursor-pointer transition-colors ${
                p.status === "pending_confirmation" ? "border-[#F59E0B]/30" : 
                !p.viewed ? "border-[#7C3AED]/30" : "border-white/5"
              }`}
              onClick={() => handleExpand(p)}
            >
              <div className="flex items-center justify-between text-xs text-[#52525B] mb-2">
                <div className="flex items-center gap-2">
                  <span>Заказ #{p.id?.slice(0, 8).toUpperCase()}</span>
                  {!p.viewed && (
                    <span className="px-1.5 py-0.5 text-[10px] rounded-full bg-[#7C3AED] text-white font-bold">
                      Новый
                    </span>
                  )}
                  {p.unread_messages > 0 && (
                    <span className="px-1.5 py-0.5 text-[10px] rounded-full bg-[#EF4444] text-white font-bold animate-pulse">
                      {p.unread_messages} новых
                    </span>
                  )}
                </div>
                <span>{new Date(p.created_at).toLocaleString("ru-RU")}</span>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-white font-medium">{p.product_name || "Товар"}</div>
                  <div className="text-sm text-[#71717A]">{p.quantity || 1} шт. | @{p.seller_nickname || "Продавец"}</div>
                </div>
                <div className="text-right">
                  <div className="text-white font-medium font-['JetBrains_Mono']">{p.total_price?.toFixed(2)} USDT</div>
                  {getStatusBadge(p.status)}
                </div>
              </div>
              
              {expandedId === p.id && (
                <div className="mt-3 pt-3 border-t border-white/5 space-y-2">
                  {p.delivered_content && p.delivered_content.length > 0 && (
                    <div>
                      <div className="text-xs text-[#71717A] mb-1">Содержимое:</div>
                      <div className="bg-black/30 rounded-lg p-3 text-sm text-white font-mono break-all whitespace-pre-wrap max-h-40 overflow-y-auto">
                        {Array.isArray(p.delivered_content) ? p.delivered_content.map((item, i) => (
                          <div key={i}>{typeof item === 'object' ? (item.text || JSON.stringify(item)) : item}</div>
                        )) : p.delivered_content}
                      </div>
                    </div>
                  )}
                  {p.purchase_type === "guarantor" && (
                    <button 
                      onClick={(e) => { e.stopPropagation(); navigate(`/merchant/guarantor-purchase/${p.id}`); }}
                      className="w-full py-2 bg-[#7C3AED]/20 text-[#A78BFA] rounded-lg text-sm hover:bg-[#7C3AED]/30 transition-colors"
                    >
                      Открыть чат с гарантом
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
