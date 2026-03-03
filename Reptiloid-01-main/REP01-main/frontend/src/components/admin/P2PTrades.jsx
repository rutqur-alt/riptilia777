import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Activity, MessageCircle } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { Badge, LoadingSpinner, EmptyState, PageHeader } from "@/components/admin/SharedComponents";

export function P2PTrades() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  useEffect(() => { fetchTrades(); }, []);

  const fetchTrades = async () => {
    try {
      const response = await axios.get(`${API}/admin/trades`, { headers: { Authorization: `Bearer ${token}` } });
      const data = response.data?.trades || response.data || [];
      setTrades(Array.isArray(data) ? data : []);
    } catch (error) {
      toast.error("Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  };

  const handleTradeClick = (trade) => {
    if (trade.status === "disputed") {
      navigate("/admin/messages", { state: { category: "p2p_dispute", tradeId: trade.id } });
    }
  };

  const filtered = trades.filter(t => {
    if (filter === "active") return ["pending", "paid"].includes(t.status);
    if (filter === "disputed") return t.status === "disputed";
    if (filter === "completed") return t.status === "completed";
    return true;
  });

  const statusColors = {
    pending: "yellow",
    paid: "blue",
    completed: "green",
    cancelled: "gray",
    disputed: "red"
  };

  const statusLabels = {
    pending: "Ожидание",
    paid: "Оплачено",
    completed: "Завершена",
    cancelled: "Отменена",
    disputed: "Спор"
  };

  return (
    <div className="space-y-4" data-testid="p2p-trades">
      <PageHeader title="Сделки P2P" subtitle={`Всего: ${trades.length}`} />

      <div className="flex gap-2">
        {[
          { key: "all", label: "Все" },
          { key: "active", label: "Активные" },
          { key: "disputed", label: "Споры" },
          { key: "completed", label: "Завершённые" },
        ].map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-3 py-1 rounded-lg text-xs ${filter === f.key ? "bg-[#10B981]/15 text-[#10B981]" : "text-[#71717A] hover:text-white"}`}
            data-testid={`filter-${f.key}`}
          >
            {f.label}
            {f.key === "disputed" && trades.filter(t => t.status === "disputed").length > 0 && (
              <span className="ml-1 bg-[#EF4444] text-white text-[9px] px-1 rounded-full">
                {trades.filter(t => t.status === "disputed").length}
              </span>
            )}
          </button>
        ))}
      </div>

      {loading ? <LoadingSpinner /> : filtered.length === 0 ? (
        <EmptyState icon={Activity} text="Нет сделок" />
      ) : (
        <div className="space-y-2">
          {filtered.slice(0, 50).map(trade => (
            <div 
              key={trade.id} 
              onClick={() => handleTradeClick(trade)}
              className={`bg-[#121212] border rounded-xl p-3 transition-all ${
                trade.status === "disputed" 
                  ? "border-[#EF4444]/30 cursor-pointer hover:bg-[#EF4444]/5 hover:border-[#EF4444]/50" 
                  : "border-white/5"
              }`}
              data-testid={`trade-${trade.id}`}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span className="text-white text-xs font-medium">#{trade.id?.slice(0, 8)}</span>
                  <Badge color={statusColors[trade.status]}>{statusLabels[trade.status] || trade.status}</Badge>
                  {trade.status === "disputed" && (
                    <span className="text-[#EF4444] text-[10px] flex items-center gap-1">
                      <MessageCircle className="w-3 h-3" /> Открыть чат
                    </span>
                  )}
                </div>
                <span className="text-[#52525B] text-[10px]">{new Date(trade.created_at).toLocaleString("ru-RU")}</span>
              </div>
              <div className="text-[#A1A1AA] text-xs">
                <span className="text-[#10B981] font-mono">{trade.amount_usdt} USDT</span> = <span className="font-mono">{trade.amount_rub} ₽</span>
                {trade.trader_login && <span className="text-[#52525B]"> • Продавец: {trade.trader_login}</span>}
                {trade.buyer_login && <span className="text-[#52525B]"> • Покупатель: {trade.buyer_login}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default P2PTrades;
