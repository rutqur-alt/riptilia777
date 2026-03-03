import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { ArrowDownRight, MessageCircle, XCircle, Search } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { LoadingSpinner, EmptyState, PageHeader } from "@/components/admin/SharedComponents";

export function CryptoPayouts() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [payouts, setPayouts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => { fetchPayouts(); }, [filter]);

  const fetchPayouts = async () => {
    try {
      setLoading(true);
      const params = filter !== "all" ? `?status=${filter}` : "";
      const response = await axios.get(`${API}/admin/crypto-payouts${params}`, { 
        headers: { Authorization: `Bearer ${token}` } 
      });
      setPayouts(response.data || []);
    } catch (error) {
      toast.error("Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  };

  const updateStatus = async (orderId, newStatus) => {
    try {
      await axios.post(`${API}/admin/crypto-payouts/${orderId}/update-status`, 
        { status: newStatus },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success("Статус обновлён");
      fetchPayouts();
    } catch (error) {
      toast.error("Ошибка");
    }
  };

  const openChat = (payout) => {
    if (payout.conversation_id) {
      navigate("/admin/messages", { state: { conversationId: payout.conversation_id, category: "crypto_payout" } });
    }
  };

  const statusColors = {
    pending: "bg-[#F59E0B]/20 text-[#F59E0B]",
    paid: "bg-[#3B82F6]/20 text-[#3B82F6]",
    completed: "bg-[#10B981]/20 text-[#10B981]",
    cancelled: "bg-[#EF4444]/20 text-[#EF4444]",
    dispute: "bg-[#EF4444]/20 text-[#EF4444]"
  };

  const statusLabels = {
    pending: "Ожидает",
    paid: "Оплачен",
    completed: "Завершён",
    cancelled: "Отменён",
    dispute: "Спор"
  };

  const filters = [
    { key: "all", label: "Все" },
    { key: "active", label: "Активные" },
    { key: "dispute", label: "Споры" },
    { key: "completed", label: "Завершённые" },
    { key: "cancelled", label: "Отменённые" }
  ];

  // Filter payouts by search
  const filtered = payouts.filter(p => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      p.id?.toLowerCase().includes(query) ||
      p.buyer_nickname?.toLowerCase().includes(query) ||
      p.merchant_nickname?.toLowerCase().includes(query) ||
      p.wallet_address?.toLowerCase().includes(query)
    );
  });

  return (
    <div className="space-y-4" data-testid="crypto-payouts">
      <PageHeader title="Выплаты" subtitle="Заказы на покупку криптовалюты" />

      {/* Search + Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#52525B]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Поиск по ID, покупателю, кошельку..."
            className="w-full bg-[#121212] border border-white/10 rounded-xl pl-10 pr-10 py-2 text-sm text-white placeholder-[#52525B] focus:outline-none focus:border-[#7C3AED]"
            data-testid="search-payouts"
          />
          {searchQuery && (
            <button onClick={() => setSearchQuery("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#52525B] hover:text-white">
              <XCircle className="w-4 h-4" />
            </button>
          )}
        </div>
        <div className="flex gap-2 overflow-x-auto pb-2">
          {filters.map(f => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`px-4 py-2 rounded-full text-sm whitespace-nowrap transition-all ${
                filter === f.key
                  ? "bg-[#10B981] text-white"
                  : "bg-[#121212] text-[#A1A1AA] hover:bg-white/10"
              }`}
              data-testid={`filter-${f.key}`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {searchQuery && (
        <div className="text-xs text-[#71717A]">
          Найдено: {filtered.length} из {payouts.length}
        </div>
      )}

      {loading ? <LoadingSpinner /> : filtered.length === 0 ? (
        <EmptyState icon={ArrowDownRight} text={searchQuery ? "Ничего не найдено" : "Нет заказов"} />
      ) : (
        <div className="space-y-2">
          {filtered.map(p => (
            <div 
              key={p.id} 
              className="bg-[#121212] border border-white/5 rounded-xl p-4 hover:border-[#10B981]/30 transition-colors cursor-pointer"
              onClick={() => openChat(p)}
              data-testid={`payout-${p.id}`}
            >
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-[#10B981]/20 flex items-center justify-center">
                      <ArrowDownRight className="w-5 h-5 text-[#10B981]" />
                    </div>
                    <div>
                      <div className="text-white font-medium">{p.amount_usdt} USDT</div>
                      <div className="text-[#71717A] text-xs">
                        Покупатель: @{p.buyer_nickname} • Мерчант: @{p.merchant_nickname || "неизвестен"}
                      </div>
                    </div>
                  </div>
                </div>
                
                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <div className="text-[#10B981] font-mono text-sm">{(p.amount_rub || 0).toFixed(2)} ₽</div>
                    <div className="text-[#52525B] text-xs">Курс: {p.rate} ₽</div>
                  </div>
                  
                  <span className={`px-2 py-1 rounded text-xs font-medium ${statusColors[p.status] || statusColors.pending}`}>
                    {statusLabels[p.status] || p.status}
                  </span>
                  
                  {p.status === "pending" && (
                    <div className="flex gap-1" onClick={e => e.stopPropagation()}>
                      <Button 
                        size="sm" 
                        onClick={() => updateStatus(p.id, "paid")}
                        className="h-7 bg-[#3B82F6] hover:bg-[#2563EB] text-xs"
                      >
                        Оплачен
                      </Button>
                      <Button 
                        size="sm" 
                        variant="ghost"
                        onClick={() => updateStatus(p.id, "cancelled")}
                        className="h-7 text-[#EF4444] hover:bg-[#EF4444]/10"
                      >
                        <XCircle className="w-4 h-4" />
                      </Button>
                    </div>
                  )}
                  
                  {p.status === "paid" && (
                    <div className="flex gap-1" onClick={e => e.stopPropagation()}>
                      <Button 
                        size="sm" 
                        onClick={() => updateStatus(p.id, "completed")}
                        className="h-7 bg-[#10B981] hover:bg-[#059669] text-xs"
                      >
                        Завершить
                      </Button>
                      <Button 
                        size="sm" 
                        variant="ghost"
                        onClick={() => updateStatus(p.id, "dispute")}
                        className="h-7 text-[#EF4444] hover:bg-[#EF4444]/10"
                      >
                        Спор
                      </Button>
                    </div>
                  )}
                  
                  {p.status === "dispute" && (
                    <div className="flex gap-1" onClick={e => e.stopPropagation()}>
                      <Button 
                        size="sm" 
                        onClick={() => updateStatus(p.id, "completed")}
                        className="h-7 bg-[#10B981] hover:bg-[#059669] text-xs"
                      >
                        Решить
                      </Button>
                    </div>
                  )}
                  
                  <MessageCircle className="w-4 h-4 text-[#71717A]" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default CryptoPayouts;
