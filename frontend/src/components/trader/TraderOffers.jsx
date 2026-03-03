import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { toast } from "sonner";
import { useAuth, API } from "@/App";
import axios from "axios";
import { 
  Plus, ListOrdered, CreditCard, DollarSign, 
  XCircle, Play, Pause 
} from "lucide-react";
import { PAYMENT_METHODS } from "@/config/paymentMethods";

// Helper to get display name from payment_details format
const getPaymentDetailDisplayName = (detail) => {
  const method = PAYMENT_METHODS[detail.payment_type];
  const emoji = method ? method.emoji : "\uD83D\uDCB0";
  const name = method ? method.shortName : detail.payment_type;
  
  if (detail.payment_type === "card" || detail.payment_type === "sng_card") {
    const last4 = detail.card_number ? ("\u2022\u2022\u2022\u2022 " + detail.card_number.slice(-4)) : "";
    return emoji + " " + (detail.bank_name || name) + " " + last4;
  }
  if (detail.payment_type === "sbp" || detail.payment_type === "sng_sbp") {
    return emoji + " " + (detail.bank_name || "\u0421\u0411\u041F") + " " + (detail.phone_number || "");
  }
  if (detail.payment_type === "sim") {
    return emoji + " " + (detail.operator_name || "SIM") + " " + (detail.phone_number || "");
  }
  if (detail.payment_type === "qr_code") {
    return emoji + " QR-\u043A\u043E\u0434 " + (detail.bank_name || "");
  }
  if (detail.payment_type === "mono_bank") {
    return emoji + " Monobank " + (detail.phone_number || detail.card_number || "");
  }
  return emoji + " " + name;
};

export default function TraderOffers() {
  const { token } = useAuth();
  const [offers, setOffers] = useState([]);
  const [paymentDetails, setPaymentDetails] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [newOffer, setNewOffer] = useState({
    amount_usdt: "",
    min_amount: "",
    max_amount: "",
    price_rub: "",
    payment_detail_ids: [],
    conditions: ""
  });

  useEffect(() => {
    fetchOffers();
    fetchPaymentDetails();
  }, []);

  const fetchPaymentDetails = async () => {
    try {
      const response = await axios.get(`${API}/trader/payment-details`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setPaymentDetails(response.data);
    } catch (error) {
      console.error(error);
    }
  };

  const fetchOffers = async () => {
    try {
      const response = await axios.get(`${API}/offers/my`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setOffers(response.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateOffer = async () => {
    if (!newOffer.amount_usdt || !newOffer.price_rub) {
      toast.error("\u0417\u0430\u043F\u043E\u043B\u043D\u0438\u0442\u0435 \u0432\u0441\u0435 \u043F\u043E\u043B\u044F");
      return;
    }
    if (newOffer.payment_detail_ids.length === 0) {
      toast.error("\u0412\u044B\u0431\u0435\u0440\u0438\u0442\u0435 \u0445\u043E\u0442\u044F \u0431\u044B \u043E\u0434\u0438\u043D \u0440\u0435\u043A\u0432\u0438\u0437\u0438\u0442 \u0434\u043B\u044F \u043F\u0440\u0438\u0451\u043C\u0430 \u043F\u043B\u0430\u0442\u0435\u0436\u0435\u0439");
      return;
    }

    // Derive payment_methods from selected payment details
    const paymentMethods = [];
    newOffer.payment_detail_ids.forEach(detailId => {
      const detail = paymentDetails.find(d => d.id === detailId);
      if (detail) {
        paymentMethods.push(detail.payment_type);
      }
    });

    const amount = parseFloat(newOffer.amount_usdt);
    const minAmount = newOffer.min_amount ? parseFloat(newOffer.min_amount) : 1;
    const maxAmount = newOffer.max_amount ? parseFloat(newOffer.max_amount) : amount;

    try {
      await axios.post(`${API}/offers`, {
        amount_usdt: amount,
        min_amount: minAmount,
        max_amount: maxAmount,
        price_rub: parseFloat(newOffer.price_rub),
        payment_methods: [...new Set(paymentMethods)],
        payment_detail_ids: newOffer.payment_detail_ids,
        conditions: newOffer.conditions || null
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("\u041E\u0431\u044A\u044F\u0432\u043B\u0435\u043D\u0438\u0435 \u0441\u043E\u0437\u0434\u0430\u043D\u043E");
      setCreateOpen(false);
      setNewOffer({
        amount_usdt: "",
        min_amount: "",
        max_amount: "",
        price_rub: "",
        payment_detail_ids: [],
        conditions: ""
      });
      fetchOffers();
    } catch (error) {
      toast.error(error.response?.data?.detail || "\u041E\u0448\u0438\u0431\u043A\u0430 \u0441\u043E\u0437\u0434\u0430\u043D\u0438\u044F");
    }
  };

  const handleDeleteOffer = async (offerId) => {
    try {
      const response = await axios.delete(`${API}/offers/${offerId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = response.data;
      
      if (data.total_refund > 0) {
        toast.success(
          `Объявление закрыто. Возвращено на баланс: ${data.total_refund.toFixed(2)} USDT` +
          (data.commission_refund > 0 ? ` (включая ${data.commission_refund.toFixed(2)} неиспользованной комиссии)` : ''),
          { duration: 5000 }
        );
      } else {
        toast.success("Объявление закрыто");
      }
      fetchOffers();
    } catch (error) {
      toast.error("Ошибка удаления");
    }
  };

  const togglePaymentDetail = (detailId) => {
    setNewOffer(prev => ({
      ...prev,
      payment_detail_ids: prev.payment_detail_ids.includes(detailId)
        ? prev.payment_detail_ids.filter(id => id !== detailId)
        : [...prev.payment_detail_ids, detailId]
    }));
  };

  // Group payment detailsby type for display
  const groupedDetails = {};
  paymentDetails.filter(d => d.is_active !== false).forEach(detail => {
    const type = detail.payment_type || "other";
    if (!groupedDetails[type]) groupedDetails[type] = [];
    groupedDetails[type].push(detail);
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <h1 className="text-2xl font-bold text-white font-['Unbounded']">{"\u041C\u043E\u0438 \u043E\u0431\u044A\u044F\u0432\u043B\u0435\u043D\u0438\u044F"}</h1>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button className="bg-[#7C3AED] hover:bg-[#6D28D9] rounded-full px-6" data-testid="create-offer-btn" title="Создать новое объявление">
              <Plus className="w-4 h-4 mr-2" />
              {"\u0421\u043E\u0437\u0434\u0430\u0442\u044C"}
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-[#121212] border-white/10 text-white max-w-lg max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="font-['Unbounded']">{"\u0421\u043E\u0437\u0434\u0430\u0442\u044C \u043E\u0431\u044A\u044F\u0432\u043B\u0435\u043D\u0438\u0435"}</DialogTitle>
            </DialogHeader>
            <div className="space-y-5 pt-4">
              <div className="p-4 bg-[#F59E0B]/10 border border-[#F59E0B]/20 rounded-xl">
                <div className="flex items-center gap-2 text-[#F59E0B]">
                  <DollarSign className="w-5 h-5" />
                  <span className="font-medium">{"\u041A\u043E\u043C\u0438\u0441\u0441\u0438\u044F \u043F\u043B\u0430\u0442\u0444\u043E\u0440\u043C\u044B: 1.0%"}</span>
                </div>
                <p className="text-sm text-[#A1A1AA] mt-1">{"\u0028\u0431\u0443\u0434\u0435\u0442 \u0441\u043F\u0438\u0441\u0430\u043D\u0430 \u043F\u0440\u0438 \u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043D\u0438\u0438 \u0441\u0434\u0435\u043B\u043A\u0438\u0029"}</p>
              </div>

              <div className="space-y-2">
                <Label className="text-[#A1A1AA]">{"\u0421\u0443\u043C\u043C\u0430 \u043A \u043F\u0440\u043E\u0434\u0430\u0436\u0435 (USDT)"}</Label>
                <Input
                  type="number"
                  placeholder="1000"
                  value={newOffer.amount_usdt}
                  onChange={(e) => setNewOffer({ ...newOffer, amount_usdt: e.target.value })}
                  className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl"
                  data-testid="offer-amount-usdt"
                />
                <p className="text-xs text-[#71717A]">{"Эта сумма + 1% комиссии будет заморожена из вашего баланса"}</p>
                {newOffer.amount_usdt && (
                  <div className="mt-2 p-3 bg-[#F59E0B]/10 border border-[#F59E0B]/20 rounded-xl">
                    <p className="text-xs text-[#F59E0B]">
                      <strong>К заморозке:</strong> {(parseFloat(newOffer.amount_usdt) * 1.01).toFixed(2)} USDT 
                      <span className="text-[#A1A1AA] ml-1">
                        ({newOffer.amount_usdt} + {(parseFloat(newOffer.amount_usdt) * 0.01).toFixed(2)} комиссия)
                      </span>
                    </p>
                    <p className="text-[10px] text-[#A1A1AA] mt-1">1% комиссия списывается с каждой сделки</p>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-[#A1A1AA]">{"\u041C\u0438\u043D. \u0437\u0430 \u0441\u0434\u0435\u043B\u043A\u0443 (USDT)"}</Label>
                  <Input
                    type="number"
                    placeholder="10"
                    value={newOffer.min_amount}
                    onChange={(e) => setNewOffer({ ...newOffer, min_amount: e.target.value })}
                    className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl"
                    data-testid="offer-min-amount"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-[#A1A1AA]">{"\u041C\u0430\u043A\u0441. \u0437\u0430 \u0441\u0434\u0435\u043B\u043A\u0443 (USDT)"}</Label>
                  <Input
                    type="number"
                    placeholder="500"
                    value={newOffer.max_amount}
                    onChange={(e) => setNewOffer({ ...newOffer, max_amount: e.target.value })}
                    className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl"
                    data-testid="offer-max-amount"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label className="text-[#A1A1AA]">{"\u041A\u0443\u0440\u0441 (RUB \u0437\u0430 1 USDT)"}</Label>
                <Input
                  type="number"
                  placeholder="92.50"
                  value={newOffer.price_rub}
                  onChange={(e) => setNewOffer({ ...newOffer, price_rub: e.target.value })}
                  className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl"
                  data-testid="offer-price"
                />
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label className="text-[#A1A1AA]">{"\u0420\u0435\u043A\u0432\u0438\u0437\u0438\u0442\u044B \u0434\u043B\u044F \u043F\u0440\u0438\u0451\u043C\u0430 \u043F\u043B\u0430\u0442\u0435\u0436\u0435\u0439"}</Label>
                  <Link to="/trader/payment-details" className="text-xs text-[#7C3AED] hover:underline">
                    {"+\u0414\u043E\u0431\u0430\u0432\u0438\u0442\u044C \u043D\u043E\u0432\u044B\u0435"}
                  </Link>
                </div>
                
                {paymentDetails.length === 0 ? (
                  <div className="p-6 border border-dashed border-white/10 rounded-xl text-center">
                    <CreditCard className="w-10 h-10 text-[#52525B] mx-auto mb-3" />
                    <p className="text-[#71717A] mb-3">{"\u0423 \u0432\u0430\u0441 \u043D\u0435\u0442 \u0441\u043E\u0445\u0440\u0430\u043D\u0451\u043D\u043D\u044B\u0445 \u0440\u0435\u043A\u0432\u0438\u0437\u0438\u0442\u043E\u0432"}</p>
                    <Link to="/trader/payment-details">
                      <Button variant="outline" size="sm" className="border-[#7C3AED]/50 text-[#7C3AED]" title="Добавить новый платежный реквизит">
                        {"\u0414\u043E\u0431\u0430\u0432\u0438\u0442\u044C \u0440\u0435\u043A\u0432\u0438\u0437\u0438\u0442\u044B"}
                      </Button>
                    </Link>
                  </div>
                ) : (
                  <div className="space-y-2 max-h-[280px] overflow-y-auto pr-1">
                    {Object.entries(groupedDetails).map(([typeId, details]) => {
                      const method = PAYMENT_METHODS[typeId];
                      if (!method) return null;
                      
                      return (
                        <div key={typeId}>
                          <div className="text-xs text-[#52525B] mb-2">{method.emoji} {method.shortName}</div>
                          <div className="space-y-2">
                            {details.map((detail) => (
                              <div
                                key={detail.id}
                                onClick={() => togglePaymentDetail(detail.id)}
                                className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${
                                  newOffer.payment_detail_ids.includes(detail.id)
                                    ? "border-[#10B981] bg-[#10B981]/10"
                                    : "border-white/10 hover:border-white/20"
                                }`}
                              >
                                <Checkbox checked={newOffer.payment_detail_ids.includes(detail.id)} />
                                <span className="text-sm flex-1">{getPaymentDetailDisplayName(detail)}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <Label className="text-[#A1A1AA]">{"\u0423\u0441\u043B\u043E\u0432\u0438\u044F \u0438 \u043F\u0440\u0430\u0432\u0438\u043B\u0430 (\u043D\u0435\u043E\u0431\u044F\u0437\u0430\u0442\u0435\u043B\u044C\u043D\u043E)"}</Label>
                <textarea
                  placeholder={"\u041D\u0430\u043F\u0440\u0438\u043C\u0435\u0440: \u041F\u0435\u0440\u0435\u0432\u043E\u0434 \u0442\u043E\u043B\u044C\u043A\u043E \u0441 \u043A\u0430\u0440\u0442\u044B \u043D\u0430 \u0438\u043C\u044F \u0432\u043B\u0430\u0434\u0435\u043B\u044C\u0446\u0430. \u0411\u0435\u0437 \u043A\u043E\u043C\u043C\u0435\u043D\u0442\u0430\u0440\u0438\u0435\u0432 \u043A \u043F\u0435\u0440\u0435\u0432\u043E\u0434\u0443."}
                  value={newOffer.conditions}
                  onChange={(e) => setNewOffer({ ...newOffer, conditions: e.target.value })}
                  className="w-full bg-[#1A1A1A] border border-white/10 text-white rounded-xl p-3 min-h-[80px] resize-none text-sm placeholder:text-[#52525B]"
                />
              </div>

              <Button onClick={handleCreateOffer} className="w-full bg-[#7C3AED] hover:bg-[#6D28D9] h-12 rounded-xl" data-testid="submit-offer-btn" title="Создать новое торговое объявление">
                {"\u0421\u043E\u0437\u0434\u0430\u0442\u044C \u043E\u0431\u044A\u044F\u0432\u043B\u0435\u043D\u0438\u0435"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="spinner" />
        </div>
      ) : offers.length === 0 ? (
        <div className="text-center py-12">
          <ListOrdered className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
          <p className="text-[#71717A]">{"\u0423 \u0432\u0430\u0441 \u043F\u043E\u043A\u0430 \u043D\u0435\u0442 \u043E\u0431\u044A\u044F\u0432\u043B\u0435\u043D\u0438\u0439"}</p>
        </div>
      ) : (
        <div className="space-y-4">
          {offers.map((offer) => (
            <div key={offer.id} className={`bg-[#121212] border rounded-2xl p-6 ${offer.paused_by_admin ? 'border-[#F59E0B]/30' : !offer.is_active ? 'border-[#52525B]/30 opacity-60' : 'border-white/5'}`} data-testid="offer-card">
              <div className="flex items-start justify-between">
                <div className="space-y-3 flex-1">
                  <div className="flex items-center gap-4 flex-wrap">
                    <div className="text-2xl font-bold text-white font-['JetBrains_Mono']">
                      {offer.price_rub} <span className="text-[#71717A] text-lg">RUB/USDT</span>
                    </div>
                    {offer.paused_by_admin ? (
                      <span className="px-2 py-1 bg-[#F59E0B]/10 text-[#F59E0B] text-xs rounded-full font-medium flex items-center gap-1" title={"\u041F\u0440\u0438\u043E\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D\u043E \u043C\u043E\u0434\u0435\u0440\u0430\u0442\u043E\u0440\u043E\u043C"}>
                        <Pause className="w-3 h-3" />
                        {"\u041D\u0430 \u043F\u0430\u0443\u0437\u0435"}
                      </span>
                    ) : offer.is_active ? (
                      <span className="px-2 py-1 bg-[#10B981]/10 text-[#10B981] text-xs rounded-full font-medium flex items-center gap-1">
                        <Play className="w-3 h-3" />
                        {"\u0410\u043A\u0442\u0438\u0432\u043D\u043E"}
                      </span>
                    ) : (
                      <span className="px-2 py-1 bg-[#52525B]/20 text-[#71717A] text-xs rounded-full font-medium flex items-center gap-1">
                        <XCircle className="w-3 h-3" />
                        {"Закрыто"}
                      </span>
                    )}
                  </div>
                  {offer.paused_by_admin && offer.admin_pause_reason && (
                    <div className="text-xs text-[#F59E0B] bg-[#F59E0B]/5 px-3 py-2 rounded-lg">
                      {"\u26A0\uFE0F \u041F\u0440\u0438\u0447\u0438\u043D\u0430: "}{offer.admin_pause_reason}
                    </div>
                  )}
                  <div className="flex gap-4 text-sm text-[#A1A1AA] flex-wrap">
                    <span>{"Доступно: "}<span className="text-white font-medium">{(offer.available_usdt ?? offer.amount_usdt ?? 0).toFixed(2)}</span> / {(offer.amount_usdt || 0).toFixed(2)} USDT</span>
                    <span className="text-[#52525B] hidden sm:inline">{"•"}</span>
                    <span>{"Лимит: "}{(offer.min_amount || 1).toFixed(2)} - {(offer.max_amount || offer.amount_usdt || 0).toFixed(2)} USDT</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {offer.payment_details?.map((detail) => (
                      <span key={detail.id} className="px-2 py-1 bg-white/5 text-[#A1A1AA] text-xs rounded-lg">
                        {getPaymentDetailDisplayName(detail)}
                      </span>
                    ))}
                    {!offer.payment_details?.length && offer.payment_methods?.map((method) => {
                      const m = PAYMENT_METHODS[method];
                      return (
                        <span key={method} className="px-2 py-1 bg-white/5 text-[#A1A1AA] text-xs rounded-lg">
                          {m ? m.emoji : "\uD83D\uDCB0"} {m ? m.shortName : method}
                        </span>
                      );
                    })}
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleDeleteOffer(offer.id)}
                  className="text-[#EF4444] hover:text-[#EF4444] hover:bg-[#EF4444]/10 ml-2"
                  data-testid="delete-offer-btn"
                >
                  <XCircle className="w-5 h-5" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
