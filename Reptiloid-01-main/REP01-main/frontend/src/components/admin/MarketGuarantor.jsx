import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Shield, ChevronRight } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { Badge, LoadingSpinner, EmptyState, PageHeader } from "@/components/admin/SharedComponents";

export function MarketGuarantor() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  useEffect(() => { fetchTrades(); }, [filter]);

  const fetchTrades = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/msg/admin/guarantor-orders?include_resolved=true`, 
        { headers: { Authorization: `Bearer ${token}` } }
      );
      let data = response.data || [];
      
      if (filter === "active") {
        data = data.filter(t => t.status === "pending_confirmation" || t.status === "pending");
      } else if (filter === "completed") {
        data = data.filter(t => t.status === "completed" || t.status === "released" || t.status === "refunded" || t.status === "partially_refunded");
      }
      
      setTrades(data);
    } catch (error) {
      console.error("Error fetching guarantor trades:", error);
      setTrades([]);
    } finally {
      setLoading(false);
    }
  };

  const openChat = (trade) => {
    navigate("/admin/messages", { state: { conversationId: trade.id } });
  };

  return (
    <div className="space-y-4" data-testid="market-guarantor">
      <PageHeader title="Гарант-сделки" subtitle="Статистика сделок с гарантом" />

      <div className="flex gap-2">
        {["all", "active", "completed"].map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1 rounded-lg text-xs ${filter === f ? "bg-[#7C3AED]/15 text-[#7C3AED]" : "text-[#71717A] hover:text-white"}`}
          >
            {f === "all" ? "Все" : f === "active" ? "Активные" : "Завершены"}
          </button>
        ))}
      </div>

      {loading ? <LoadingSpinner /> : trades.length === 0 ? (
        <EmptyState icon={Shield} text="Нет гарант-сделок" />
      ) : (
        <div className="space-y-3">
          {trades.map(trade => (
            <div key={trade.id} className="bg-[#121212] border border-white/5 rounded-xl p-4 cursor-pointer hover:bg-white/5 transition-colors"
                 onClick={() => openChat(trade)}>
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-white font-semibold">{trade.title || trade.data?.product_name || "Гарант-сделка"}</span>
                    <Badge color={trade.status === "pending_confirmation" || trade.status === "pending" ? "blue" : "green"}>
                      {trade.status === "pending_confirmation" || trade.status === "pending" ? "Активна" : "Завершена"}
                    </Badge>
                  </div>
                  <div className="text-[#A1A1AA] text-xs">
                    {trade.data?.total_price || trade.data?.amount || "—"} USDT • Покупатель: @{trade.data?.buyer_nickname || "—"} • Продавец: @{trade.data?.seller_nickname || "—"}
                  </div>
                  <div className="text-[#71717A] text-xs mt-1">
                    {trade.subtitle || "Нажмите для перехода в чат"}
                  </div>
                </div>
                <ChevronRight className="w-5 h-5 text-[#71717A]" />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default MarketGuarantor;
