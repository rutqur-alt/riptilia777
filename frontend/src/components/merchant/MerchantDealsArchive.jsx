import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { useAuth, API } from "@/App";
import { Button } from "@/components/ui/button";
import ChatHistoryModal from "./ChatHistoryModal";
import { ChevronRight, Copy, FileText, History, Loader, MessageCircle } from "lucide-react";

export default function MerchantDealsArchive() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [deals, setDeals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [chatTradeId, setChatTradeId] = useState(null);
  const [showChat, setShowChat] = useState(false);

  useEffect(() => {
    fetchDeals();
  }, []);

  const fetchDeals = async () => {
    try {
      const res = await axios.get(`${API}/merchant/trades`, {
        params: { type: "sell" },
        headers: { Authorization: `Bearer ${token}` }
      });
      setDeals(res.data || []);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const filteredDeals = filter === "all" ? deals : deals.filter(d => {
    if (filter === "active") return ["pending", "paid"].includes(d.status);
    return d.status === filter;
  });

  const getStatusBadge = (status) => {
    if (status === "pending_completion") {
      return <span className="px-2 py-1 rounded-lg text-xs bg-[#F59E0B]/10 text-[#F59E0B] inline-flex items-center gap-1" title="Ожидайте, скоро сделка завершится">⏳ Завершается</span>;
    }
    const styles = {
      pending: "bg-[#F59E0B]/10 text-[#F59E0B]",
      paid: "bg-[#3B82F6]/10 text-[#3B82F6]",
      completed: "bg-[#10B981]/10 text-[#10B981]",
      cancelled: "bg-[#71717A]/10 text-[#71717A]",
      dispute: "bg-[#EF4444]/10 text-[#EF4444]",
      disputed: "bg-[#EF4444]/10 text-[#EF4444]"
    };
    const labels = {
      pending: "Ожидает",
      paid: "Оплачено",
      completed: "Завершено",
      cancelled: "Отменено",
      dispute: "Спор",
      disputed: "Спор"
    };
    return <span className={`px-2 py-1 rounded-lg text-xs ${styles[status] || styles.pending}`}>{labels[status] || status}</span>;
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Архив сделок</h1>

      <div className="flex gap-2 flex-wrap">
        {[
          { key: "all", label: "Все" },
          { key: "active", label: "Активные" },
          { key: "completed", label: "Завершённые" },
          { key: "cancelled", label: "Отменённые" },
          { key: "dispute", label: "Споры" }
        ].map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-4 py-2 rounded-lg text-sm transition-colors ${
              filter === f.key ? "bg-white/10 text-white" : "text-[#71717A] hover:bg-white/5"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-20"><Loader className="w-8 h-8 animate-spin text-[#71717A]" /></div>
      ) : filteredDeals.length === 0 ? (
        <div className="text-center py-20">
          <FileText className="w-16 h-16 text-[#52525B] mx-auto mb-4" />
          <h3 className="text-lg font-medium text-white mb-2">Нет сделок</h3>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredDeals.map(deal => (
            <div 
              key={deal.id} 
              onClick={() => navigate(`/merchant/deals-archive/${deal.id}`)}
              className="bg-[#121212] border border-white/5 rounded-xl p-4 cursor-pointer hover:bg-white/5 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 bg-[#3B82F6]/10 rounded-xl flex items-center justify-center">
                    <FileText className="w-6 h-6 text-[#3B82F6]" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-xs text-[#71717A] font-['JetBrains_Mono']">#{deal.id?.slice(0, 12)}</span>
                      <button onClick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(deal.id); toast.success("Номер сделки скопирован"); }} className="p-0.5 rounded hover:bg-white/10 transition-colors" title="Скопировать номер сделки">
                        <Copy className="w-3 h-3 text-[#71717A] hover:text-white" />
                      </button>
                    </div>
                    <div className="text-white font-medium">{deal.client_nickname || "Клиент"}</div>
                    <div className="text-sm text-[#71717A]">
                      {deal.amount} {deal.currency || "USDT"} • {deal.fiat_amount?.toFixed(2) || "—"} ₽
                    </div>
                    <div className="text-xs text-[#52525B]">
                      {new Date(deal.created_at).toLocaleString("ru-RU")}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); setChatTradeId(deal.id); setShowChat(true); }} className="border-[#3B82F6]/30 text-[#3B82F6] hover:bg-[#3B82F6]/10 text-xs">
                    <MessageCircle className="w-3 h-3 mr-1" /> Чат
                  </Button>
                  {getStatusBadge(deal.status)}
                  <ChevronRight className="w-5 h-5 text-[#71717A]" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Chat History Modal */}
      <ChatHistoryModal
        open={showChat}
        onClose={() => setShowChat(false)}
        tradeId={chatTradeId}
        token={token}
        canOpenDispute={false}
      />
    </div>
  );
}
