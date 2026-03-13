import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { AlertTriangle, ArrowUpRight, Copy, History, Loader, MessageCircle, Percent, Plus, Target } from "lucide-react";
import { toast } from "sonner";
import { useAuth, API } from "@/App";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import ChatHistoryModal from "./ChatHistoryModal";

export default function MerchantWithdrawalRequests() {
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("active");
  const [showCreate, setShowCreate] = useState(false);
  const [payoutSettings, setPayoutSettings] = useState({ base_rate: 100 });
  const [liveRate, setLiveRate] = useState(null);
  const [form, setForm] = useState({ 
    amount_rub: "", 
    payment_type: "card",
    card_number: "",
    sbp_phone: "",
    bank_name: ""
  });

  const [chatTradeId, setChatTradeId] = useState(null);
  const [showChat, setShowChat] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const commissionRate = user?.withdrawal_commission || 3;
  const merchantRate = payoutSettings.base_rate * (1 - commissionRate / 100);
  const calculatedUsdt = form.amount_rub ? (parseFloat(form.amount_rub) / merchantRate).toFixed(2) : "0.00";

  useEffect(() => {
    fetchRequests();
    fetchPayoutSettings();
  }, [filter]);

  const fetchPayoutSettings = async () => {
    try {
      const res = await axios.get(`${API}/payout-settings/public`);
      setPayoutSettings({
        base_rate: res.data.base_rate || 100
      });
    } catch (e) {
      console.error(e);
    }
  };

  const fetchRequests = async () => {
    try {
      const response = await axios.get(`${API}/crypto/my-offers`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      let data = response.data || [];
      if (filter === "active") {
        data = data.filter(r => r.status === "active" || r.status === "in_progress");
      } else if (filter === "completed") {
        // "sold" status means the offer was successfully completed
        data = data.filter(r => r.status === "completed" || r.status === "sold");
      } else if (filter === "cancelled") {
        data = data.filter(r => r.status === "cancelled");
      }
      setRequests(data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const createRequest = async () => {
    if (!form.amount_rub || parseFloat(form.amount_rub) <= 0) {
      toast.error("Укажите сумму в рублях");
      return;
    }
    if (form.payment_type === "card" && !form.card_number) {
      toast.error("Укажите номер карты");
      return;
    }
    if (form.payment_type === "sbp" && (!form.sbp_phone || !form.bank_name)) {
      toast.error("Укажите номер СБП и банк");
      return;
    }

    try {
      await axios.post(`${API}/crypto/sell-offers`, {
        amount_rub: parseFloat(form.amount_rub),
        payment_type: form.payment_type,
        card_number: form.card_number,
        sbp_phone: form.sbp_phone,
        bank_name: form.bank_name
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Заявка создана");
      setShowCreate(false);
      setForm({ amount_rub: "", payment_type: "card", card_number: "", sbp_phone: "", bank_name: "" });
      fetchRequests();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка создания");
    }
  };

  const cancelRequest = async (id) => {
    try {
      await axios.delete(`${API}/crypto/sell-offers/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Заявка отменена");
      fetchRequests();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка");
    }
  };

  const filteredRequests = requests.filter(r => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.trim().toLowerCase();
    return (r.id && r.id.toLowerCase().includes(q)) ||
           (r.amount_rub && String(r.amount_rub).includes(q)) ||
           (r.card_number && r.card_number.includes(q)) ||
           (r.sbp_phone && r.sbp_phone.includes(q));
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Заявки на выплаты</h1>
        <Button onClick={() => setShowCreate(true)} className="bg-[#10B981] hover:bg-[#059669]">
          <Plus className="w-4 h-4 mr-2" /> Создать заявку
        </Button>
      </div>

      {/* Commission Info Banner */}
      <div className="bg-gradient-to-r from-[#10B981]/10 to-transparent border border-[#10B981]/20 rounded-xl p-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-[#10B981]/20 rounded-xl flex items-center justify-center">
            <Percent className="w-5 h-5 text-[#10B981]" />
          </div>
          <div>
            <p className="text-white font-medium">Ваша комиссия на выплаты: <span className="text-[#10B981]">{commissionRate}%</span></p>
            <p className="text-[#71717A] text-sm">Базовый курс: <span className="text-[#3B82F6] font-bold">{payoutSettings.base_rate} ₽/USDT</span> (биржа) | Ваш курс: <span className="text-[#10B981] font-bold">{merchantRate.toFixed(2)} ₽/USDT</span></p>
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <Input
          placeholder="Поиск по номеру сделки или сумме..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="bg-[#121212] border-white/10 text-white pl-10"
        />
        <Target className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#71717A]" />
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        {[
          { key: "active", label: "Активные" },
          { key: "completed", label: "Завершённые" },
          { key: "cancelled", label: "Отменённые" }
        ].map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-4 py-2 rounded-lg text-sm transition-colors ${
              filter === f.key
                ? "bg-white/10 text-white"
                : "text-[#71717A] hover:bg-white/5"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Create Dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="bg-[#121212] border-white/10 text-white max-w-md">
          <DialogHeader>
            <DialogTitle>Создать заявку на выплату</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="text-[#A1A1AA]">Сумма в рублях</Label>
              <Input
                type="number"
                value={form.amount_rub}
                onChange={(e) => setForm({...form, amount_rub: e.target.value})}
                placeholder="10000"
                className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl"
              />
              {form.amount_rub && (
                <div className="text-sm text-[#71717A]">
                  Будет списано: <span className="text-[#F97316] font-medium">{calculatedUsdt} USDT</span> (курс {merchantRate.toFixed(2)} ₽)
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label className="text-[#A1A1AA]">Способ оплаты</Label>
              <div className="flex gap-2">
                <button
                  onClick={() => setForm({...form, payment_type: "card"})}
                  className={`flex-1 py-2 rounded-lg text-sm ${form.payment_type === "card" ? "bg-[#F97316] text-white" : "bg-white/5 text-[#71717A]"}`}
                >
                  Карта
                </button>
                <button
                  onClick={() => setForm({...form, payment_type: "sbp"})}
                  className={`flex-1 py-2 rounded-lg text-sm ${form.payment_type === "sbp" ? "bg-[#F97316] text-white" : "bg-white/5 text-[#71717A]"}`}
                >
                  СБП
                </button>
              </div>
            </div>

            {form.payment_type === "card" ? (
              <div className="space-y-2">
                <Label className="text-[#A1A1AA]">Номер карты</Label>
                <Input
                  value={form.card_number}
                  onChange={(e) => setForm({...form, card_number: e.target.value})}
                  placeholder="0000 0000 0000 0000"
                  className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl"
                />
              </div>
            ) : (
              <>
                <div className="space-y-2">
                  <Label className="text-[#A1A1AA]">Номер телефона (СБП)</Label>
                  <Input
                    value={form.sbp_phone}
                    onChange={(e) => setForm({...form, sbp_phone: e.target.value})}
                    placeholder="+7 999 999 99 99"
                    className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-[#A1A1AA]">Банк</Label>
                  <Input
                    value={form.bank_name}
                    onChange={(e) => setForm({...form, bank_name: e.target.value})}
                    placeholder="Сбербанк"
                    className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl"
                  />
                </div>
              </>
            )}

            <Button onClick={createRequest} className="w-full bg-[#10B981] hover:bg-[#059669] h-12 rounded-xl">
              Создать заявку
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Requests List */}
      {loading ? (
        <div className="flex justify-center py-20"><Loader className="w-8 h-8 animate-spin text-[#71717A]" /></div>
      ) : filteredRequests.length === 0 ? (
        <div className="text-center py-20">
          <ArrowUpRight className="w-16 h-16 text-[#52525B] mx-auto mb-4" />
          <h3 className="text-lg font-medium text-white mb-2">Нет заявок</h3>
          <p className="text-[#71717A]">Создайте первую заявку на выплату</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredRequests.map(req => (
            <div key={req.id} className="bg-[#121212] border rounded-xl p-4 border-white/5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                    req.status === "dispute" ? "bg-[#EF4444]/20" :
                    req.status === "active" ? "bg-[#10B981]/10" : "bg-[#71717A]/10"
                  }`}>
                    {req.status === "dispute" ? (
                      <AlertTriangle className="w-6 h-6 text-[#EF4444]" />
                    ) : (
                      <ArrowUpRight className="w-6 h-6 text-[#10B981]" />
                    )}
                  </div>
                  <div>
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-xs text-[#71717A] font-['JetBrains_Mono']">#{req.id?.slice(0, 12)}</span>
                      <button onClick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(req.id); toast.success("Номер сделки скопирован"); }} className="p-0.5 rounded hover:bg-white/10 transition-colors" title="Скопировать номер сделки">
                        <Copy className="w-3 h-3 text-[#71717A] hover:text-white" />
                      </button>
                    </div>
                    <div className="text-white font-medium">
                      {(req.amount_rub || 0).toLocaleString("ru-RU")} ₽
                    </div>
                    <div className="text-sm text-[#71717A]">
                      {(req.usdt_from_merchant || 0).toFixed(2)} USDT | {req.payment_type === "card" ? "Карта" : "СБП"}
                    </div>
                    <div className="text-xs text-[#52525B]">
                      {req.created_at ? new Date(req.created_at).toLocaleString("ru-RU") : "—"}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-1 rounded-lg ${
                    req.status === "active" ? "bg-[#10B981]/10 text-[#10B981]" :
                    req.status === "dispute" ? "bg-[#EF4444]/10 text-[#EF4444]" :
                    req.status === "in_progress" ? "bg-[#F59E0B]/10 text-[#F59E0B]" :
                    "bg-[#71717A]/10 text-[#71717A]"
                  }`}>
                    {req.status === "active" ? "Активна" :
                     req.status === "dispute" ? "Спор" :
                     req.status === "in_progress" ? "В процессе" :
                     req.status === "completed" ? "Завершена" :
                     req.status === "cancelled" ? "Отменена" : req.status}
                  </span>
                  <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); setChatTradeId(req.id); setShowChat(true); }} className="border-[#3B82F6]/30 text-[#3B82F6] hover:bg-[#3B82F6]/10 text-xs">
                    <MessageCircle className="w-3 h-3 mr-1" /> Чат
                  </Button>
                  {req.status === "active" && (
                    <Button size="sm" variant="outline" onClick={() => cancelRequest(req.id)} className="border-[#EF4444]/30 text-[#EF4444] hover:bg-[#EF4444]/10 text-xs">
                      Отменить
                    </Button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Chat History Modal for Withdrawal Requests */}
      <ChatHistoryModal
        open={showChat}
        onClose={() => setShowChat(false)}
        tradeId={chatTradeId}
        token={token}
        canOpenDispute={false}
        isCryptoOrder={true}
      />
    </div>
  );
}
