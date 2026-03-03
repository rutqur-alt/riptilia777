import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useAuth, API } from "@/App";
import axios from "axios";
import { 
  TrendingUp, MessageCircle, ExternalLink, CheckCircle, 
  XCircle, AlertTriangle, Clock, Copy 
} from "lucide-react";
import { getStatusBadge } from "./utils";

const StatusBadge = ({ status, role = "seller" }) => {
  const badge = getStatusBadge(status, role);
  return <span className={badge.className}>{badge.label}</span>;
};

export default function TraderSales() {
  const { token } = useAuth();
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTrades();
  }, []);

  const fetchTrades = async () => {
    try {
      const response = await axios.get(`${API}/trades/sales/active`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTrades(response.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async (tradeId) => {
    try {
      await axios.post(`${API}/trades/${tradeId}/confirm`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Сделка подтверждена");
      fetchTrades();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка");
    }
  };

  const handleCancel = async (tradeId) => {
    try {
      await axios.post(`${API}/trades/${tradeId}/cancel`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Сделка отменена");
      fetchTrades();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка");
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white font-['Unbounded']">Мои продажи</h1>
      <p className="text-[#71717A]">Сделки, где вы продаёте USDT</p>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="spinner" />
        </div>
      ) : trades.length === 0 ? (
        <div className="text-center py-12">
          <TrendingUp className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
          <p className="text-[#71717A]">Продаж пока нет</p>
        </div>
      ) : (
        <div className="space-y-4">
          {trades.map((trade) => (
            <div key={trade.id} className="bg-[#121212] border border-white/5 rounded-2xl p-6" data-testid="trade-card">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <Link to={`/trader/sales/${trade.id}`} className="text-sm text-[#71717A] font-['JetBrains_Mono'] hover:text-[#7C3AED]">
                      #{trade.id}
                    </Link>
                    <button onClick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(trade.id); toast.success("Номер сделки скопирован"); }} className="p-1 rounded hover:bg-white/10 transition-colors" title="Скопировать номер сделки">
                      <Copy className="w-3.5 h-3.5 text-[#71717A] hover:text-white" />
                    </button>
                  </div>
                  <div className="text-xl font-bold text-white mt-1">
                    -{trade.amount_usdt} USDT
                  </div>
                  <div className="text-sm text-[#71717A] mt-1">
                    Покупатель: {trade.buyer_type === "trader" ? `@${trade.buyer_login || "Трейдер"}` : "Клиент"}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge status={trade.status} />
                  {(trade.status === "pending" || trade.status === "paid" || trade.status === "disputed") && (
                    <Link to={`/trader/sales/${trade.id}`}>
                      <Button size="sm" variant="ghost" className="text-[#7C3AED] hover:bg-[#7C3AED]/10">
                        <ExternalLink className="w-4 h-4" />
                      </Button>
                    </Link>
                  )}
                </div>
              </div>
              
              {trade.status === "paid" && (
                <div className="bg-[#3B82F6]/10 border border-[#3B82F6]/20 rounded-xl p-3 mb-4">
                  <div className="flex items-center gap-2 text-[#3B82F6]">
                    <MessageCircle className="w-4 h-4" />
                    <span className="font-medium text-sm">Покупатель отметил оплату! Проверьте поступление.</span>
                  </div>
                </div>
              )}
              
              {trade.status === "disputed" && (
                <div className="bg-[#EF4444]/10 border border-[#EF4444]/20 rounded-xl p-3 mb-4">
                  <div className="flex items-center gap-2 text-[#EF4444]">
                    <AlertTriangle className="w-4 h-4" />
                    <span className="font-medium text-sm">Спор открыт! Администратор рассмотрит.</span>
                  </div>
                </div>
              )}
              
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm mb-4">
                <div>
                  <div className="text-[#71717A]">Курс</div>
                  <div className="text-white font-medium">{trade.price_rub} RUB</div>
                </div>
                <div>
                  <div className="text-[#71717A]">Получите</div>
                  <div className="text-white font-medium">{trade.amount_rub?.toLocaleString()} ₽</div>
                </div>
                <div>
                  <div className="text-[#71717A]">Комиссия</div>
                  <div className="text-[#F59E0B] font-medium">{trade.trader_commission} USDT</div>
                </div>
                <div>
                  <div className="text-[#71717A]">Дата</div>
                  <div className="text-white text-xs">{new Date(trade.created_at).toLocaleDateString()}</div>
                </div>
              </div>

              {(trade.status === "pending" || trade.status === "paid" || trade.status === "disputed") && (
                <div className="flex flex-wrap gap-3">
                  <Link to={`/trader/sales/${trade.id}`} className="flex-1 min-w-[150px]">
                    <Button className="w-full bg-[#7C3AED] hover:bg-[#6D28D9] h-10 rounded-xl">
                      <MessageCircle className="w-4 h-4 mr-2" />
                      Открыть
                    </Button>
                  </Link>
                  {(trade.status === "paid" || trade.status === "disputed") && (
                    <Button onClick={() => handleConfirm(trade.id)} className="bg-[#10B981] hover:bg-[#059669] h-10 rounded-xl px-6">
                      <CheckCircle className="w-4 h-4 mr-2" />
                      Подтвердить
                    </Button>
                  )}
                  {trade.status === "pending" && (
                    <Button onClick={() => handleCancel(trade.id)} variant="outline" className="border-[#EF4444]/50 text-[#EF4444] hover:bg-[#EF4444]/10 h-10 rounded-xl">
                      <XCircle className="w-4 h-4" />
                    </Button>
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
