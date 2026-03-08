import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { AlertTriangle, ChevronRight, Copy, DollarSign, History, Loader, MessageCircle, Percent, Target } from "lucide-react";
import { toast } from "sonner";
import { useAuth, API } from "@/App";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import ChatHistoryModal from "./ChatHistoryModal";

export default function MerchantPayments() {
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("active");
  const [chatTradeId, setChatTradeId] = useState(null);
  const [showChat, setShowChat] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    fetchPayments();
  }, [filter]);

  const fetchPayments = async () => {
    try {
      const response = await axios.get(`${API}/merchant/trades`, {
        params: { type: "sell", status: filter },
        headers: { Authorization: `Bearer ${token}` }
      });
      setPayments(response.data || []);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const disputeCount = payments.filter(p => p.status === "dispute" || p.status === "disputed").length;

  const filteredPayments = payments.filter(p => {
    // First filter by status tab
    if (filter === "active") {
      if (!["pending", "active", "paid", "waiting", "processing"].includes(p.status)) return false;
    } else if (filter === "completed") {
      if (p.status !== "completed") return false;
    } else if (filter === "cancelled") {
      if (!["cancelled", "rejected", "expired"].includes(p.status)) return false;
    } else if (filter === "dispute") {
      if (p.status !== "dispute" && p.status !== "disputed") return false;
    }
    
    // Then filter by search query
    if (!searchQuery.trim()) return true;
    const q = searchQuery.trim().toLowerCase();
    return (p.id && p.id.toLowerCase().includes(q)) ||
           (p.client_nickname && p.client_nickname.toLowerCase().includes(q)) ||
           (p.amount && String(p.amount).includes(q)) ||
           (p.fiat_amount && String(p.fiat_amount).includes(q));
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Платежи (Пополнения)</h1>
      </div>

      {/* Commission Info Banner */}
      <div className="bg-gradient-to-r from-[#3B82F6]/10 to-transparent border border-[#3B82F6]/20 rounded-xl p-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-[#3B82F6]/20 rounded-xl flex items-center justify-center">
            <Percent className="w-5 h-5 text-[#3B82F6]" />
          </div>
          <div>
            <p className="text-white font-medium">Комиссия на платежи: <span className="text-[#3B82F6]">{user?.commission_rate || 0}%</span></p>
            <p className="text-[#71717A] text-sm">Списывается с каждого успешного пополнения от клиента</p>
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <Input
          placeholder="Поиск по номеру сделки, клиенту или сумме..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="bg-[#121212] border-white/10 text-white pl-10"
        />
        <Target className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#71717A]" />
      </div>

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        {[
          { key: "active", label: "Активные" },
          { key: "completed", label: "Завершённые" },
          { key: "cancelled", label: "Отменённые" },
          { key: "dispute", label: `Споры${disputeCount > 0 ? ` (${disputeCount})` : ""}`, danger: true }
        ].map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-4 py-2 rounded-lg text-sm transition-colors ${
              filter === f.key
                ? f.danger ? "bg-[#EF4444]/20 text-[#EF4444]" : "bg-white/10 text-white"
                : f.danger && disputeCount > 0 ? "text-[#EF4444] hover:bg-[#EF4444]/10" : "text-[#71717A] hover:bg-white/5"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-20"><Loader className="w-8 h-8 animate-spin text-[#71717A]" /></div>
      ) : filteredPayments.length === 0 ? (
        <div className="text-center py-20">
          <DollarSign className="w-16 h-16 text-[#52525B] mx-auto mb-4" />
          <h3 className="text-lg font-medium text-white mb-2">Нет платежей</h3>
          <p className="text-[#71717A]">{filter === "dispute" ? "Нет открытых споров" : "Платежи появятся здесь"}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredPayments.map(payment => (
            <div 
              key={payment.id}
              onClick={() => { setChatTradeId(payment.id); setShowChat(true); }}
              className={`bg-[#121212] border rounded-xl p-4 cursor-pointer transition-all ${
                (payment.status === "dispute" || payment.status === "disputed") 
                  ? "border-[#EF4444]/30 bg-[#EF4444]/5 hover:bg-[#EF4444]/10" 
                  : "border-white/5 hover:bg-white/5"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                    (payment.status === "dispute" || payment.status === "disputed") ? "bg-[#EF4444]/20" : "bg-[#3B82F6]/10"
                  }`}>
                    {(payment.status === "dispute" || payment.status === "disputed") ? (
                      <AlertTriangle className="w-6 h-6 text-[#EF4444]" />
                    ) : (
                      <DollarSign className="w-6 h-6 text-[#3B82F6]" />
                    )}
                  </div>
                  <div>
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-xs text-[#71717A] font-['JetBrains_Mono']">#{payment.id}</span>
                      <button onClick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(payment.id); toast.success("Номер сделки скопирован"); }} className="p-0.5 rounded hover:bg-white/10 transition-colors" title="Скопировать номер сделки">
                        <Copy className="w-3 h-3 text-[#71717A] hover:text-white" />
                      </button>
                    </div>
                    <div className={`font-medium ${(payment.status === "dispute" || payment.status === "disputed") ? "text-[#EF4444]" : "text-white"}`}>
                      {payment.client_nickname || "Клиент"}
                    </div>
                    <div className="text-sm text-[#71717A]">
                      {(payment.original_amount_rub || payment.fiat_amount || payment.amount_rub || 0).toLocaleString("ru-RU", {maximumFractionDigits: 0})} ₽
                    </div>
                    <div className="text-xs text-[#52525B]">
                      {new Date(payment.created_at).toLocaleString("ru-RU")}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); setChatTradeId(payment.id); setShowChat(true); }} className="border-[#3B82F6]/30 text-[#3B82F6] hover:bg-[#3B82F6]/10 text-xs">
                    <MessageCircle className="w-3 h-3 mr-1" /> Чат
                  </Button>
                  {(payment.status === "dispute" || payment.status === "disputed") && (
                    <span className="px-2 py-1 bg-[#EF4444]/10 text-[#EF4444] rounded-lg text-xs flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" /> Спор
                    </span>
                  )}
                  {["pending", "active", "paid", "waiting"].includes(payment.status) && (
                    <span className={`px-2 py-1 rounded-lg text-xs ${
                      payment.status === "paid" ? "bg-[#3B82F6]/10 text-[#3B82F6]" :
                      payment.status === "waiting" ? "bg-[#F59E0B]/10 text-[#F59E0B]" :
                      "bg-[#10B981]/10 text-[#10B981]"
                    }`}>
                      {payment.status === "paid" ? "Оплачено" :
                       payment.status === "waiting" ? "Ожидание" :
                       payment.status === "pending" ? "Ожидает" : "Активна"}
                    </span>
                  )}
                  {payment.status === "completed" && (
                    <span className="px-2 py-1 bg-[#10B981]/10 text-[#10B981] rounded-lg text-xs">Завершено</span>
                  )}
                  {payment.status === "cancelled" && (payment.qr_aggregator_trade || payment.is_qr_aggregator) && !payment.has_dispute && (
                    <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); setChatTradeId(payment.id); setShowChat(true); }} className="border-[#EF4444]/30 text-[#EF4444] hover:bg-[#EF4444]/10 text-xs">
                      <AlertTriangle className="w-3 h-3 mr-1" /> Открыть спор
                    </Button>
                  )}
                  {payment.status === "cancelled" && (
                    <span className="px-2 py-1 bg-[#71717A]/10 text-[#71717A] rounded-lg text-xs">Отменено</span>
                  )}
                  <ChevronRight className={`w-5 h-5 ${(payment.status === "dispute" || payment.status === "disputed") ? "text-[#EF4444]" : "text-[#71717A]"}`} />
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
        canOpenDispute={true}
        onDisputeOpened={() => { setFilter("dispute"); fetchPayments(); }}
      />
    </div>
  );
}
