import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Activity, MessageCircle, History, Search, XCircle, RefreshCw, Copy } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { Badge, LoadingSpinner, EmptyState, PageHeader } from "@/components/admin/SharedComponents";
import { ChatHistoryModal } from "@/components/admin/ChatHistoryModal";

// Normalize status from DB to display values
const normalizeStatus = (status) => {
  const map = {
    "dispute": "disputed",
    "pending_payment": "pending",
    "refunded": "cancelled",
  };
  return map[status] || status;
};

export function P2PTrades({ initialFilter }) {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState(initialFilter || "all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTradeId, setSelectedTradeId] = useState(null);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => { fetchTrades(); }, []);

  const fetchTrades = async () => {
    try {
      const response = await axios.get(`${API}/admin/trades?limit=500`, { headers: { Authorization: `Bearer ${token}` } });
      const data = response.data?.trades || response.data || [];
      // Normalize statuses
      const normalized = (Array.isArray(data) ? data : []).map(t => ({
        ...t,
        status: normalizeStatus(t.status)
      }));
      setTrades(normalized);
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

  const openChatHistory = (e, tradeId) => {
    e.stopPropagation();
    setSelectedTradeId(tradeId);
    setShowHistory(true);
  };

  // Search and filter logic
  const filtered = trades.filter(t => {
    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      const matchesId = t.id?.toLowerCase().includes(query);
      const matchesBuyer = t.buyer_login?.toLowerCase().includes(query) || t.buyer_nickname?.toLowerCase().includes(query);
      const matchesSeller = t.trader_login?.toLowerCase().includes(query) || t.seller_nickname?.toLowerCase().includes(query);
      if (!matchesId && !matchesBuyer && !matchesSeller) return false;
    }
    // Status filter
    if (filter === "active") return ["pending", "paid"].includes(t.status);
    if (filter === "disputed") return t.status === "disputed";
    if (filter === "completed") return t.status === "completed";
    if (filter === "cancelled") return t.status === "cancelled";
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

  const disputeCount = trades.filter(t => t.status === "disputed").length;
  const activeCount = trades.filter(t => ["pending", "paid"].includes(t.status)).length;
  const completedCount = trades.filter(t => t.status === "completed").length;
  const cancelledCount = trades.filter(t => t.status === "cancelled").length;

  return (
    <div className="space-y-4" data-testid="p2p-trades">
      <div className="flex items-center justify-between">
        <PageHeader title="Сделки P2P" subtitle={`Всего: ${trades.length}`} />
        <button
          title="Обновить список сделок"
          onClick={() => { setLoading(true); fetchTrades(); }}
          className="p-2 rounded-lg hover:bg-white/5 text-[#71717A] hover:text-white transition-colors"
          title="Обновить"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Search + Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#52525B]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Поиск по ID, покупателю, продавцу..."
            className="w-full bg-[#121212] border border-white/10 rounded-xl pl-10 pr-10 py-2 text-sm text-white placeholder-[#52525B] focus:outline-none focus:border-[#7C3AED]"
            data-testid="search-trades"
          />
          {searchQuery && (
            <button title="Очистить поиск" onClick={() => setSearchQuery("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#52525B] hover:text-white">
              <XCircle className="w-4 h-4" />
            </button>
          )}
        </div>
        <div className="flex gap-2 flex-wrap">
          {[
            { key: "all", label: "Все", count: trades.length },
            { key: "active", label: "Активные", count: activeCount },
            { key: "disputed", label: "Споры", count: disputeCount, alert: true },
            { key: "completed", label: "Завершённые", count: completedCount },
            { key: "cancelled", label: "Отменённые", count: cancelledCount },
          ].map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-3 py-1 rounded-lg text-xs ${filter === f.key ? "bg-[#10B981]/15 text-[#10B981]" : "text-[#71717A] hover:text-white"}`}
            data-testid={`filter-${f.key}`}
          >
            {f.label}
            {f.count > 0 && (
              <span className={`ml-1 text-[9px] px-1 rounded-full ${f.alert && f.count > 0 ? 'bg-[#EF4444] text-white' : 'text-[#71717A]'}`}>
                {f.count}
              </span>
            )}
          </button>
        ))}
        </div>
      </div>

      {/* Results count */}
      {searchQuery && (
        <div className="text-xs text-[#71717A]">
          Найдено: {filtered.length} из {trades.length}
        </div>
      )}

      {loading ? <LoadingSpinner /> : filtered.length === 0 ? (
        <EmptyState icon={Activity} text={searchQuery ? "Ничего не найдено" : "Нет сделок"} />
      ) : (
        <div className="space-y-2">
          {filtered.map(trade => (
            <div 
              key={trade.id} 
              className={`bg-[#121212] border rounded-xl p-3 transition-all ${
                trade.status === "disputed" 
                  ? "border-[#EF4444]/30" 
                  : "border-white/5"
              }`}
              data-testid={`trade-${trade.id}`}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span className="text-white text-xs font-medium font-['JetBrains_Mono']">#{trade.id?.slice(0, 12)}</span>
                  <button onClick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(trade.id); toast.success("Номер сделки скопирован"); }} className="p-0.5 rounded hover:bg-white/10 transition-colors" title="Скопировать номер сделки">
                    <Copy className="w-3 h-3 text-[#71717A] hover:text-white" />
                  </button>
                  <Badge color={statusColors[trade.status]}>{statusLabels[trade.status] || trade.status}</Badge>
                </div>
                <div className="flex items-center gap-2">
                  {/* Кнопка История чата - для ВСЕХ сделок */}
                  <button
                    title="Посмотреть историю чата"
                    onClick={(e) => openChatHistory(e, trade.id)}
                    className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] bg-[#7C3AED]/10 text-[#7C3AED] hover:bg-[#7C3AED]/20 transition-colors"
                    data-testid={`history-${trade.id}`}
                  >
                    <History className="w-3 h-3" />
                    История чата
                  </button>
                  {trade.status === "disputed" && (
                    <button
                      title="Перейти к разрешению спора"
                      onClick={() => handleTradeClick(trade)}
                      className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] bg-[#EF4444]/10 text-[#EF4444] hover:bg-[#EF4444]/20 transition-colors"
                    >
                      <MessageCircle className="w-3 h-3" />
                      Спор
                    </button>
                  )}
                  <span className="text-[#52525B] text-[10px]">{new Date(trade.created_at).toLocaleString("ru-RU")}</span>
                </div>
              </div>
              <div className="text-[#A1A1AA] text-xs">
                <span className="text-[#10B981] font-mono">{trade.amount_usdt} USDT</span> = <span className="font-mono">{trade.amount_rub} ₽</span>
                {trade.trader_login && <span className="text-[#52525B]"> | Продавец: {trade.trader_login}</span>}
                {trade.buyer_login && <span className="text-[#52525B]"> | Покупатель: {trade.buyer_login}</span>}
              </div>
              {trade.status === "disputed" && trade.disputed_by_role && (
                <div className="text-[#EF4444] text-xs font-bold mt-1">
                  Спор открыт {trade.disputed_by_role}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Modal для истории чата */}
      <ChatHistoryModal
        isOpen={showHistory}
        onClose={() => setShowHistory(false)}
        tradeId={selectedTradeId}
      />
    </div>
  );
}

export default P2PTrades;
