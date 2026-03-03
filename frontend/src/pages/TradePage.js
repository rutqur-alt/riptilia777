import { useState, useEffect } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { API, useAuth } from "@/App";
import axios from "axios";
import { Wallet, Clock, CheckCircle, XCircle, ArrowLeft, Copy, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

export default function TradePage() {
  const { tradeId } = useParams();
  const navigate = useNavigate();
  const { token, user, isAuthenticated } = useAuth();
  const [trade, setTrade] = useState(null);
  const [loading, setLoading] = useState(true);
  const [timeLeft, setTimeLeft] = useState(0);

  useEffect(() => {
    fetchTrade();
    const interval = setInterval(fetchTrade, 15000);
    return () => clearInterval(interval);
  }, [tradeId]);

  // Redirect authenticated users to proper trade page with chat
  useEffect(() => {
    if (isAuthenticated && trade && user) {
      const isBuyer = trade.buyer_id === user.id;
      const isTrader = trade.trader_id === user.id;
      
      if (isBuyer) {
        navigate(`/trader/purchases/${tradeId}`, { replace: true });
        return;
      }
      if (isTrader) {
        navigate(`/trader/sales/${tradeId}`, { replace: true });
        return;
      }
    }
  }, [isAuthenticated, trade, user, tradeId, navigate]);

  useEffect(() => {
    if (trade?.status === "pending" && trade?.expires_at) {
      const updateTimer = () => {
        const now = new Date();
        const expires = new Date(trade.expires_at);
        const diff = Math.max(0, Math.floor((expires - now) / 1000));
        setTimeLeft(diff);
      };
      updateTimer();
      const timer = setInterval(updateTimer, 1000);
      return () => clearInterval(timer);
    }
  }, [trade]);

  const fetchTrade = async () => {
    try {
      // Try authenticated endpoint first for full trade data
      if (token) {
        try {
          const response = await axios.get(`${API}/trades/${tradeId}`, {
            headers: { Authorization: `Bearer ${token}` }
          });
          setTrade(response.data);
          return;
        } catch (e) {
          // Fall through to public endpoint
        }
      }
      const response = await axios.get(`${API}/trades`);
      const foundTrade = response.data.find(t => t.id === tradeId);
      setTrade(foundTrade || null);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const getTimerClass = () => {
    if (timeLeft > 600) return "text-[#10B981]"; // > 10 min
    if (timeLeft > 300) return "text-[#F59E0B]"; // > 5 min
    return "text-[#EF4444]"; // < 5 min
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
        <div className="spinner" />
      </div>
    );
  }

  if (!trade) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
        <div className="text-center">
          <AlertTriangle className="w-16 h-16 text-[#F59E0B] mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-white font-['Unbounded'] mb-2">Сделка не найдена</h1>
          <p className="text-[#71717A]">Проверьте ID сделки</p>
          <Link to="/">
            <Button className="mt-6 bg-[#7C3AED] hover:bg-[#6D28D9] rounded-full">
              На главную
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0A0A0A] px-4 py-8">
      <div className="max-w-lg mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#7C3AED] to-[#A855F7] flex items-center justify-center">
              <Wallet className="w-5 h-5 text-white" />
            </div>
            <img src="/logo.png" alt="Reptiloid" className="h-9 w-9" />
            <span className="text-xl font-bold text-white font-['Unbounded']">Reptiloid</span>
          </div>
          <Link to="/" className="text-[#71717A] hover:text-white transition-colors">
            <ArrowLeft className="w-5 h-5" />
          </Link>
        </div>

        {/* Trade Card */}
        <div className="bg-[#121212] border border-white/5 rounded-3xl overflow-hidden">
          {/* Status Header */}
          <div className={`p-6 ${
            trade.status === "completed" ? "bg-[#10B981]/10" :
            trade.status === "cancelled" ? "bg-[#EF4444]/10" :
            "bg-[#F59E0B]/10"
          }`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {trade.status === "completed" ? (
                  <CheckCircle className="w-8 h-8 text-[#10B981]" />
                ) : trade.status === "cancelled" ? (
                  <XCircle className="w-8 h-8 text-[#EF4444]" />
                ) : (
                  <Clock className="w-8 h-8 text-[#F59E0B]" />
                )}
                <div>
                  <div className="text-white font-semibold">
                    {trade.status === "completed" ? "Сделка завершена" :
                     trade.status === "cancelled" ? "Сделка отменена" :
                     "Ожидание оплаты"}
                  </div>
                  <div className="text-sm text-[#71717A] font-['JetBrains_Mono']">
                    #{trade.id}
                  </div>
                </div>
              </div>
              
              {trade.status === "pending" && (
                <div className={`text-3xl font-bold font-['JetBrains_Mono'] ${getTimerClass()}`}>
                  {formatTime(timeLeft)}
                </div>
              )}
            </div>
          </div>

          {/* Trade Details */}
          <div className="p-6 space-y-6">
            <div className="bg-[#0A0A0A] rounded-2xl p-5 space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-[#71717A]">Сумма</span>
                <span className="text-2xl font-bold text-white font-['JetBrains_Mono']">
                  {trade.amount_usdt} USDT
                </span>
              </div>
              <div className="border-t border-white/5 pt-4">
                <div className="flex justify-between">
                  <span className="text-[#71717A]">К оплате</span>
                  <span className="text-xl font-bold text-white font-['JetBrains_Mono']">
                    {trade.amount_rub.toLocaleString()} RUB
                  </span>
                </div>
              </div>
              <div className="border-t border-white/5 pt-4">
                <div className="flex justify-between">
                  <span className="text-[#71717A]">Курс</span>
                  <span className="text-white font-['JetBrains_Mono']">
                    {trade.price_rub} RUB/USDT
                  </span>
                </div>
              </div>
            </div>

            {trade.status === "pending" && (
              <div className="bg-[#7C3AED]/10 border border-[#7C3AED]/20 rounded-xl p-4">
                <h3 className="text-white font-semibold mb-3">Инструкция</h3>
                <ol className="space-y-2 text-sm text-[#A1A1AA]">
                  <li className="flex gap-2">
                    <span className="text-[#7C3AED]">1.</span>
                    Переведите {trade.amount_rub.toLocaleString()} RUB на реквизиты трейдера
                  </li>
                  <li className="flex gap-2">
                    <span className="text-[#7C3AED]">2.</span>
                    Дождитесь подтверждения трейдера
                  </li>
                  <li className="flex gap-2">
                    <span className="text-[#7C3AED]">3.</span>
                    Средства будут зачислены автоматически
                  </li>
                </ol>
              </div>
            )}

            {trade.status === "completed" && (
              <div className="bg-[#10B981]/10 border border-[#10B981]/20 rounded-xl p-4 text-center">
                <CheckCircle className="w-12 h-12 text-[#10B981] mx-auto mb-3" />
                <p className="text-[#10B981] font-semibold">Оплата подтверждена</p>
                <p className="text-sm text-[#71717A] mt-1">
                  Средства зачислены на счет мерчанта
                </p>
              </div>
            )}

            {trade.status === "cancelled" && (
              <div className="bg-[#EF4444]/10 border border-[#EF4444]/20 rounded-xl p-4 text-center">
                <XCircle className="w-12 h-12 text-[#EF4444] mx-auto mb-3" />
                <p className="text-[#EF4444] font-semibold">Сделка отменена</p>
                <p className="text-sm text-[#71717A] mt-1">
                  Средства возвращены трейдеру
                </p>
              </div>
            )}

            {/* Copy Trade ID */}
            <button
              onClick={() => {
                navigator.clipboard.writeText(trade.id);
                toast.success("ID скопирован");
              }}
              className="w-full flex items-center justify-center gap-2 py-3 text-[#71717A] hover:text-white transition-colors"
              data-testid="copy-trade-id"
            >
              <Copy className="w-4 h-4" />
              <span className="text-sm">Скопировать ID сделки</span>
            </button>
          </div>
        </div>

        {/* Support Link */}
        <div className="text-center mt-6">
          <p className="text-sm text-[#71717A]">
            Проблемы с оплатой?{" "}
            <Link to="/" className="text-[#7C3AED] hover:text-[#A855F7]">
              Свяжитесь с поддержкой
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
