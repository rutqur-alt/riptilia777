import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAuth, API } from "@/App";
import axios from "axios";
import { 
  History, MessageCircle, ExternalLink, CheckCircle, 
  AlertTriangle, Clock, Copy 
} from "lucide-react";
import { toast } from "sonner";
import { getStatusBadge } from "./utils";

const StatusBadge = ({ status }) => {
  const badge = getStatusBadge(status, "buyer");
  return <span className={badge.className}>{badge.label}</span>;
};

export default function TraderPurchases() {
  const { token } = useAuth();
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTrades();
  }, []);

  const fetchTrades = async () => {
    try {
      const response = await axios.get(`${API}/trades/purchases/active`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTrades(response.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white font-['Unbounded']">Мои покупки</h1>
          <p className="text-[#71717A]">Сделки, где вы покупаете USDT</p>
        </div>
        <Link to="/">
          <Button className="bg-[#10B981] hover:bg-[#059669] rounded-full px-6" title="Купить USDT">
            Купить ещё
          </Button>
        </Link>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="spinner" />
        </div>
      ) : trades.length === 0 ? (
        <div className="text-center py-12">
          <History className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
          <p className="text-[#71717A]">Покупок пока нет</p>
          <Link to="/">
            <Button className="mt-4 bg-[#7C3AED] hover:bg-[#6D28D9] rounded-full px-6">
              Перейти на главную
            </Button>
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {trades.map((trade) => (
            <div key={trade.id} className="bg-[#121212] border border-white/5 rounded-2xl p-6" data-testid="purchase-card">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <Link to={`/trader/purchases/${trade.id}`} className="text-sm text-[#71717A] font-['JetBrains_Mono'] hover:text-[#7C3AED]">
                      #{trade.id}
                    </Link>
                    <button onClick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(trade.id); toast.success("Номер сделки скопирован"); }} className="p-1 rounded hover:bg-white/10 transition-colors" title="Скопировать номер сделки">
                      <Copy className="w-3.5 h-3.5 text-[#71717A] hover:text-white" />
                    </button>
                  </div>
                  <div className="text-xl font-bold text-[#10B981] mt-1">
                    +{trade.amount_usdt.toFixed(2)} USDT
                  </div>
                  <div className="text-sm text-[#71717A] mt-1">
                    Продавец: @{trade.seller_login || trade.trader_login || "Трейдер"}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge status={trade.status} />
                  {(trade.status === "pending" || trade.status === "paid" || trade.status === "disputed") && (
                    <Link to={`/trader/purchases/${trade.id}`}>
                      <Button size="sm" variant="ghost" className="text-[#7C3AED] hover:bg-[#7C3AED]/10">
                        <ExternalLink className="w-4 h-4" />
                      </Button>
                    </Link>
                  )}
                </div>
              </div>
              
              {trade.status === "pending" && (
                <div className="bg-[#F59E0B]/10 border border-[#F59E0B]/20 rounded-xl p-3 mb-4">
                  <div className="flex items-center gap-2 text-[#F59E0B]">
                    <AlertTriangle className="w-4 h-4" />
                    <span className="font-medium text-sm">Ожидает вашей оплаты! Переведите деньги продавцу.</span>
                  </div>
                </div>
              )}
              
              {trade.status === "paid" && (
                <div className="bg-[#3B82F6]/10 border border-[#3B82F6]/20 rounded-xl p-3 mb-4">
                  <div className="flex items-center gap-2 text-[#3B82F6]">
                    <Clock className="w-4 h-4" />
                    <span className="font-medium text-sm">Оплата отправлена. Ожидайте подтверждения.</span>
                  </div>
                </div>
              )}
              
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                <div>
                  <div className="text-[#71717A]">Курс</div>
                  <div className="text-white font-medium">{trade.price_rub} RUB</div>
                </div>
                <div>
                  <div className="text-[#71717A]">Оплатить</div>
                  <div className="text-white font-medium">{trade.amount_rub?.toLocaleString()} ₽</div>
                </div>
                <div>
                  <div className="text-[#71717A]">Комиссия</div>
                  <div className="text-[#10B981] font-medium">0%</div>
                </div>
                <div>
                  <div className="text-[#71717A]">Дата</div>
                  <div className="text-white text-xs">{new Date(trade.created_at).toLocaleDateString()}</div>
                </div>
              </div>

              {(trade.status === "pending" || trade.status === "paid" || trade.status === "disputed") && (
                <div className="flex gap-3 mt-4">
                  <Link to={`/trader/purchases/${trade.id}`} className="flex-1">
                    <Button className="w-full bg-[#7C3AED] hover:bg-[#6D28D9] h-10 rounded-xl">
                      <MessageCircle className="w-4 h-4 mr-2" />
                      Открыть сделку
                    </Button>
                  </Link>
                </div>
              )}

              {trade.status === "completed" && (
                <div className="mt-4 p-3 bg-[#10B981]/10 border border-[#10B981]/20 rounded-xl">
                  <div className="flex items-center gap-2 text-[#10B981] text-sm">
                    <CheckCircle className="w-4 h-4" />
                    <span>USDT зачислены на ваш баланс</span>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
