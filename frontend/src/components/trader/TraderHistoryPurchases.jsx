import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { useAuth, API } from "@/App";
import axios from "axios";
import { History, ArrowLeft, MessageCircle, Copy, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { TradeChatModal } from "@/components/trader/TradeChatModal";

export default function TraderHistoryPurchases() {
  const { token } = useAuth();
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedTradeId, setSelectedTradeId] = useState(null);
  const [showChat, setShowChat] = useState(false);

  useEffect(() => {
    fetchTrades();
  }, []);

  const fetchTrades = async () => {
    try {
      const response = await axios.get(`${API}/trades/purchases/history`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTrades(response.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const openChat = (tradeId) => {
    setSelectedTradeId(tradeId);
    setShowChat(true);
  };

  const getStatusBadge = (status) => {
    const styles = {
      completed: "bg-[#10B981]/10 text-[#10B981]",
      cancelled: "bg-[#EF4444]/10 text-[#EF4444]",
      disputed: "bg-[#EF4444]/10 text-[#EF4444]"
    };
    const labels = { completed: "Завершена", cancelled: "Отменена", disputed: "Спор" };
    return (
      <span className={`px-2 py-1 text-xs rounded-full font-medium ${styles[status] || "bg-[#52525B]/10 text-[#52525B]"}`}>
        {labels[status] || status}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/trader/history" className="p-2 rounded-xl bg-white/5 hover:bg-white/10">
          <ArrowLeft className="w-5 h-5 text-white" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-white font-['Unbounded']">История покупок</h1>
          <p className="text-[#71717A]">Завершённые и отменённые покупки</p>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="spinner" />
        </div>
      ) : trades.length === 0 ? (
        <div className="text-center py-12">
          <History className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
          <p className="text-[#71717A]">История покупок пуста</p>
        </div>
      ) : (
        <div className="space-y-3">
          {trades.map((trade) => (
            <div 
              key={trade.id} 
              className="bg-[#121212] border border-white/5 rounded-xl p-4 cursor-pointer hover:border-[#7C3AED]/30 transition-colors"
              onClick={() => openChat(trade.id)}
            >
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-[#71717A] font-['JetBrains_Mono']">#{trade.id}</span>
                      <button onClick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(trade.id); toast.success("Номер сделки скопирован"); }} className="p-1 rounded hover:bg-white/10 transition-colors" title="Скопировать номер сделки">
                        <Copy className="w-3 h-3 text-[#71717A] hover:text-white" />
                      </button>
                      <MessageCircle className="w-3.5 h-3.5 text-[#7C3AED]" />
                    </div>
                    <div className="text-lg font-bold text-[#10B981]">+{trade.amount_usdt} USDT</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-white font-medium">-{trade.amount_rub?.toLocaleString()} ₽</div>
                  <div className="text-xs text-[#71717A]">{new Date(trade.created_at).toLocaleDateString()}</div>
                </div>
                <div className="flex items-center gap-2">
                  {getStatusBadge(trade.status)}
                  {trade.status === "cancelled" && (trade.qr_aggregator_trade || trade.is_qr_aggregator) && (
                    <span className="px-2 py-1 text-xs rounded-full font-medium bg-[#F59E0B]/10 text-[#F59E0B] flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" />
                      Спор
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <TradeChatModal
        isOpen={showChat}
        onClose={() => setShowChat(false)}
        tradeId={selectedTradeId}
      />
    </div>
  );
}
