import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import axios from "axios";
import { useAuth, API } from "@/App";
import { Button } from "@/components/ui/button";
import ChatHistoryModal from "./ChatHistoryModal";
import { ChevronLeft, History, Loader, MessageCircle, XCircle } from "lucide-react";

export default function MerchantDealDetails() {
  const { token } = useAuth();
  const { orderId } = useParams();
  const navigate = useNavigate();
  const [deal, setDeal] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showChat, setShowChat] = useState(false);

  useEffect(() => {
    fetchDeal();
  }, [orderId]);

  const fetchDeal = async () => {
    try {
      const res = await axios.get(`${API}/merchant/trades/${orderId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setDeal(res.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="flex justify-center py-20"><Loader className="w-8 h-8 animate-spin text-[#71717A]" /></div>;
  }

  if (!deal) {
    return (
      <div className="text-center py-20">
        <XCircle className="w-16 h-16 text-[#52525B] mx-auto mb-4" />
        <h3 className="text-lg font-medium text-white mb-2">Сделка не найдена</h3>
        <Button onClick={() => navigate("/merchant/deals-archive")} variant="outline" className="border-white/10 text-white">
          <ChevronLeft className="w-4 h-4 mr-2" /> Назад
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center gap-3">
        <Button onClick={() => navigate("/merchant/deals-archive")} variant="outline" size="sm" className="border-white/10 text-white">
          <ChevronLeft className="w-4 h-4" />
        </Button>
        <h1 className="text-2xl font-bold text-white">Сделка #{deal.id?.slice(-6)}</h1>
      </div>

      <div className="bg-[#121212] border border-white/5 rounded-2xl p-6 space-y-4">
        <div className="flex justify-between py-3 border-b border-white/5">
          <span className="text-[#71717A]">Статус</span>
          <span className={`font-medium ${
            deal.status === "completed" ? "text-[#10B981]" :
            deal.status === "cancelled" ? "text-[#71717A]" :
            deal.status === "dispute" ? "text-[#EF4444]" :
            "text-[#F59E0B]"
          }`}>
            {deal.status === "completed" ? "Завершено" :
             deal.status === "cancelled" ? "Отменено" :
             deal.status === "dispute" ? "Спор" :
             deal.status === "paid" ? "Оплачено" :
             deal.status === "pending" ? "Ожидает" : deal.status}
          </span>
        </div>
        <div className="flex justify-between py-3 border-b border-white/5">
          <span className="text-[#71717A]">Клиент</span>
          <span className="text-white">{deal.client_nickname || "—"}</span>
        </div>
        <div className="flex justify-between py-3 border-b border-white/5">
          <span className="text-[#71717A]">Сумма USDT</span>
          <span className="text-white font-['JetBrains_Mono']">{deal.amount} {deal.currency || "USDT"}</span>
        </div>
        <div className="flex justify-between py-3 border-b border-white/5">
          <span className="text-[#71717A]">Сумма RUB</span>
          <span className="text-white font-['JetBrains_Mono']">{deal.fiat_amount?.toFixed(2) || "—"} ₽</span>
        </div>
        {deal.merchant_commission > 0 && (
          <div className="flex justify-between py-3 border-b border-white/5">
            <span className="text-[#71717A]">Комиссия</span>
            <span className="text-[#EF4444] font-['JetBrains_Mono']">-{deal.merchant_commission?.toFixed(4)} USDT</span>
          </div>
        )}
        <div className="flex justify-between py-3 border-b border-white/5">
          <span className="text-[#71717A]">Трейдер</span>
          <span className="text-white">{deal.trader_login || "—"}</span>
        </div>
        <div className="flex justify-between py-3 border-b border-white/5">
          <span className="text-[#71717A]">Дата создания</span>
          <span className="text-white">{deal.created_at ? new Date(deal.created_at).toLocaleString("ru-RU") : "—"}</span>
        </div>
        {deal.completed_at && (
          <div className="flex justify-between py-3">
            <span className="text-[#71717A]">Дата завершения</span>
            <span className="text-white">{new Date(deal.completed_at).toLocaleString("ru-RU")}</span>
          </div>
        )}
      </div>

      {/* Chat History Button */}
      <Button
        onClick={() => setShowChat(true)}
        className="w-full bg-[#3B82F6] hover:bg-[#2563EB] text-white h-12 rounded-xl"
      >
        <MessageCircle className="w-5 h-5 mr-2" /> Показать историю чата
      </Button>

      {/* Chat History Modal */}
      <ChatHistoryModal
        open={showChat}
        onClose={() => setShowChat(false)}
        tradeId={orderId}
        token={token}
        canOpenDispute={deal.status && !["completed", "cancelled", "dispute", "disputed"].includes(deal.status)}
        onDisputeOpened={() => fetchDeal()}
      />
    </div>
  );
}
