import { useState, useEffect, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { API } from "@/App";
import axios from "axios";
import { 
  Wallet, Clock, CheckCircle, Copy, ArrowLeft, AlertTriangle, 
  Star, Shield, MessageCircle, Timer, CreditCard, Phone, User,
  ChevronRight, Info, RefreshCw, Send, XCircle
} from "lucide-react";

const paymentMethodLabels = {
  sberbank: "Сбербанк",
  tinkoff: "Тинькофф",
  alfa: "Альфа-Банк",
  raiffeisen: "Райффайзен",
  vtb: "ВТБ",
  qiwi: "QIWI",
  yoomoney: "ЮMoney",
  sbp: "СБП",
  sbp_qr: "СБП QR-код",
  sim: "SIM (баланс)",
  custom: "Другой банк"
};

export default function PayPage() {
  const { linkId } = useParams();
  const [step, setStep] = useState("info"); // info, select_trader, payment, waiting, completed, disputed
  const [link, setLink] = useState(null);
  const [merchant, setMerchant] = useState(null);
  const [offers, setOffers] = useState([]);
  const [selectedOffer, setSelectedOffer] = useState(null);
  const [selectedRequisite, setSelectedRequisite] = useState(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [trade, setTrade] = useState(null);
  const [timeLeft, setTimeLeft] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState("");
  const [canDispute, setCanDispute] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    fetchData();
  }, [linkId]);

  // Timer for trade
  useEffect(() => {
    if (trade && trade.status === "pending") {
      const interval = setInterval(() => {
        const expires = new Date(trade.expires_at);
        const now = new Date();
        const diff = Math.max(0, Math.floor((expires - now) / 1000));
        setTimeLeft(diff);
        if (diff === 0) {
          clearInterval(interval);
        }
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [trade]);

  // Check if can open dispute (10 min after payment)
  useEffect(() => {
    if (trade && trade.status === "paid" && trade.paid_at) {
      const checkDispute = () => {
        const paidAt = new Date(trade.paid_at);
        const now = new Date();
        const minutesPassed = (now - paidAt) / 1000 / 60;
        setCanDispute(minutesPassed >= 10);
      };
      checkDispute();
      const interval = setInterval(checkDispute, 10000);
      return () => clearInterval(interval);
    }
  }, [trade]);

  // Fetch messages for chat
  useEffect(() => {
    if (trade && (step === "payment" || step === "waiting" || step === "disputed")) {
      fetchMessages();
      const interval = setInterval(fetchMessages, 3000);
      return () => clearInterval(interval);
    }
  }, [trade, step]);

  // Scroll to bottom of messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Poll trade status
  useEffect(() => {
    if (trade && trade.status !== "completed" && trade.status !== "cancelled") {
      const interval = setInterval(async () => {
        try {
          const res = await axios.get(`${API}/trades/${trade.id}/public`);
          if (res.data.status !== trade.status) {
            setTrade(res.data);
            if (res.data.status === "completed") {
              setStep("completed");
              toast.success("Сделка завершена! Средства зачислены.");
            } else if (res.data.status === "disputed") {
              setStep("disputed");
            }
          }
        } catch (e) {
          console.error(e);
        }
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [trade]);

  const fetchMessages = async () => {
    if (!trade) return;
    try {
      const res = await axios.get(`${API}/trades/${trade.id}/messages-public`);
      setMessages(res.data);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchData = async () => {
    try {
      const linkRes = await axios.get(`${API}/payment-links/${linkId}`);
      setLink(linkRes.data);
      
      // Fetch merchant info
      const merchantRes = await axios.get(`${API}/merchants/${linkRes.data.merchant_id}/public`);
      setMerchant(merchantRes.data);
      
      // Fetch available offers for this merchant type
      const offersRes = await axios.get(`${API}/offers?merchant_type=${merchantRes.data.merchant_type}`);
      // Filter offers that can handle this amount
      const validOffers = offersRes.data.filter(o => 
        o.min_amount <= linkRes.data.amount_usdt && 
        o.max_amount >= linkRes.data.amount_usdt
      );
      setOffers(validOffers);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectOffer = (offer) => {
    setSelectedOffer(offer);
  };

  const handleCreateTrade = async () => {
    if (!selectedOffer) return;
    
    setCreating(true);
    try {
      // If user selected a specific requisite, use only that one
      const requisiteIds = selectedRequisite 
        ? [selectedRequisite.id] 
        : (selectedOffer.requisite_ids || []);
      
      const response = await axios.post(`${API}/trades`, {
        amount_usdt: link.amount_usdt,
        price_rub: selectedOffer.price_rub,
        trader_id: selectedOffer.trader_id,
        payment_link_id: linkId,
        offer_id: selectedOffer.id,
        requisite_ids: requisiteIds
      });
      setTrade(response.data);
      setStep("payment");
      toast.success("Сделка создана! Оплатите в течение 30 минут.");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка создания сделки");
    } finally {
      setCreating(false);
    }
  };

  const handleMarkPaid = async () => {
    try {
      await axios.post(`${API}/trades/${trade.id}/mark-paid`);
      setTrade({ ...trade, status: "paid" });
      setStep("waiting");
      toast.success("Ожидайте подтверждения от продавца");
    } catch (error) {
      toast.error("Ошибка");
    }
  };

  const handleOpenDispute = async () => {
    if (!trade) return;
    
    if (!canDispute) {
      toast.error("Спор можно открыть через 10 минут после оплаты");
      return;
    }
    
    const reason = prompt("Укажите причину спора:");
    if (!reason) return;
    
    try {
      await axios.post(`${API}/trades/${trade.id}/dispute-public`, null, {
        params: { reason }
      });
      setTrade({ ...trade, status: "disputed" });
      setStep("disputed");
      toast.success("Спор открыт. Администратор подключится к чату.");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка открытия спора");
    }
  };

  const handleCancelTrade = async () => {
    if (!trade) return;
    if (!confirm("Отменить сделку? Это действие нельзя отменить.")) return;
    
    try {
      await axios.post(`${API}/trades/${trade.id}/cancel-client`);
      setTrade({ ...trade, status: "cancelled" });
      toast.success("Сделка отменена");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка отмены");
    }
  };

  const handleSendMessage = async () => {
    if (!newMessage.trim() || !trade) return;
    
    try {
      await axios.post(`${API}/trades/${trade.id}/messages-public`, {
        content: newMessage
      });
      setNewMessage("");
      fetchMessages();
    } catch (error) {
      toast.error("Ошибка отправки сообщения");
    }
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success("Скопировано");
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
        <div className="spinner" />
      </div>
    );
  }

  if (!link) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center px-4">
        <div className="text-center max-w-md">
          <AlertTriangle className="w-16 h-16 text-[#F59E0B] mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-white font-['Unbounded'] mb-2">Ссылка не найдена</h1>
          <p className="text-[#71717A]">Платежная ссылка недействительна или истекла</p>
        </div>
      </div>
    );
  }

  if (link.status !== "active" && !trade) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center px-4">
        <div className="text-center max-w-md">
          <CheckCircle className="w-16 h-16 text-[#10B981] mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-white font-['Unbounded'] mb-2">Платеж завершен</h1>
          <p className="text-[#71717A]">Эта ссылка уже была использована</p>
        </div>
      </div>
    );
  }

  // Step: Info - Show payment details
  if (step === "info") {
    return (
      <div className="min-h-screen bg-[#0A0A0A] px-4 py-8">
        <div className="max-w-lg mx-auto">
          {/* Header */}
          <div className="flex items-center gap-3 mb-8">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#7C3AED] to-[#A855F7] flex items-center justify-center">
              <Shield className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold text-white font-['Unbounded']">Безопасная оплата</span>
          </div>

          {/* Main Card */}
          <div className="bg-[#121212] border border-white/5 rounded-3xl p-8 mb-6">
            <div className="text-center mb-8">
              <div className="w-16 h-16 rounded-2xl bg-[#7C3AED]/10 flex items-center justify-center mx-auto mb-4">
                <Wallet className="w-8 h-8 text-[#7C3AED]" />
              </div>
              <div className="text-[#71717A] mb-2">Мерчант</div>
              <div className="text-xl font-bold text-white">{merchant?.merchant_name || "Мерчант"}</div>
            </div>

            <div className="bg-[#0A0A0A] rounded-2xl p-6 space-y-4 mb-6">
              <div className="flex justify-between items-center">
                <span className="text-[#71717A]">Сумма к зачислению</span>
                <span className="text-2xl font-bold text-white font-['JetBrains_Mono']">
                  {link.amount_rub.toLocaleString()} ₽
                </span>
              </div>
              <div className="border-t border-white/5 pt-4">
                <div className="flex justify-between items-center">
                  <span className="text-[#71717A]">Требуется купить</span>
                  <span className="text-xl font-bold text-[#10B981] font-['JetBrains_Mono']">
                    {link.amount_usdt.toFixed(2)} USDT
                  </span>
                </div>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-[#52525B]">Курс мерчанта</span>
                <span className="text-[#A1A1AA]">1 USDT = {link.price_rub} ₽</span>
              </div>
            </div>

            <Button 
              onClick={() => setStep("select_trader")} 
              className="w-full bg-[#7C3AED] hover:bg-[#6D28D9] h-14 rounded-xl font-semibold text-lg"
              data-testid="continue-btn"
            >
              Продолжить
              <ChevronRight className="w-5 h-5 ml-2" />
            </Button>
          </div>

          {/* Info Card */}
          <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
            <div className="flex items-start gap-3">
              <Info className="w-5 h-5 text-[#7C3AED] flex-shrink-0 mt-0.5" />
              <div className="text-sm text-[#A1A1AA]">
                <p className="mb-2">Вы покупаете фиксированное количество USDT.</p>
                <p>Сумма в рублях зависит от курса выбранного трейдера. После подтверждения оплаты средства будут зачислены на ваш счет в {merchant?.merchant_name}.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Step: Select Trader
  if (step === "select_trader") {
    return (
      <div className="min-h-screen bg-[#0A0A0A] px-4 py-8">
        <div className="max-w-2xl mx-auto">
          {/* Header */}
          <div className="flex items-center gap-4 mb-8">
            <button onClick={() => setStep("info")} className="p-2 rounded-xl bg-white/5 hover:bg-white/10 transition-colors">
              <ArrowLeft className="w-5 h-5 text-white" />
            </button>
            <div>
              <h1 className="text-2xl font-bold text-white font-['Unbounded']">Выберите продавца</h1>
              <p className="text-[#71717A] text-sm">Для {merchant?.merchant_name} • Купить: {link.amount_usdt.toFixed(2)} USDT</p>
            </div>
          </div>

          {offers.length === 0 ? (
            <div className="bg-[#121212] border border-white/5 rounded-3xl p-8 text-center">
              <AlertTriangle className="w-16 h-16 text-[#F59E0B] mx-auto mb-4" />
              <h2 className="text-xl font-bold text-white mb-2">Нет доступных продавцов</h2>
              <p className="text-[#71717A] mb-6">В данный момент нет трейдеров, готовых обработать ваш платеж.</p>
              <div className="bg-[#0A0A0A] rounded-xl p-4 text-left text-sm text-[#A1A1AA] mb-6">
                <p className="mb-2">Причины:</p>
                <ul className="list-disc list-inside space-y-1">
                  <li>Закончились USDT у трейдеров</li>
                  <li>Все трейдеры заняты</li>
                  <li>Временные технические работы</li>
                </ul>
              </div>
              <div className="flex gap-3">
                <Button onClick={() => window.location.reload()} variant="outline" className="flex-1 border-white/10 h-12 rounded-xl">
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Повторить поиск
                </Button>
                <Button onClick={() => setStep("info")} variant="outline" className="flex-1 border-white/10 h-12 rounded-xl">
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Вернуться назад
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {offers.map((offer, index) => {
                const amountToPay = (link.amount_usdt * offer.price_rub).toFixed(0);
                const medal = index === 0 ? "🥇" : index === 1 ? "🥈" : index === 2 ? "🥉" : null;
                const isSelected = selectedOffer?.id === offer.id;
                const offerRequisites = offer.requisites || [];
                
                return (
                  <div
                    key={offer.id}
                    className={`bg-[#121212] border-2 rounded-2xl overflow-hidden transition-all ${
                      isSelected
                        ? "border-[#7C3AED] bg-[#7C3AED]/5"
                        : "border-white/5 hover:border-white/20"
                    }`}
                    data-testid="offer-option"
                  >
                    {/* Основная информация о трейдере - компактно */}
                    <div 
                      className="p-4 cursor-pointer"
                      onClick={() => {
                        handleSelectOffer(offer);
                        setSelectedRequisite(null);
                      }}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          {medal && <span className="text-xl">{medal}</span>}
                          <span className="text-white font-semibold">@{offer.trader_login}</span>
                          <div className="flex items-center gap-1 text-sm">
                            <Star className="w-3 h-3 text-[#F59E0B] fill-[#F59E0B]" />
                            <span className="text-[#F59E0B]">{offer.success_rate || 100}%</span>
                            <span className="text-[#52525B]">•</span>
                            <span className="text-[#71717A]">{offer.trades_count || 0} сделок</span>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-xl font-bold text-white font-['JetBrains_Mono']">
                            {parseInt(amountToPay).toLocaleString()} ₽
                          </div>
                          <div className="text-xs text-[#52525B]">{offer.price_rub} ₽/USDT • Лимит: {offer.min_amount || 1}-{offer.max_amount || offer.amount_usdt} USDT</div>
                        </div>
                      </div>

                      {/* Условия/правила трейдера */}
                      {offer.conditions && (
                        <div className="bg-[#F59E0B]/10 rounded-lg p-2 mb-2">
                          <div className="flex items-start gap-2">
                            <Info className="w-3 h-3 text-[#F59E0B] flex-shrink-0 mt-0.5" />
                            <div className="text-xs text-[#F59E0B] line-clamp-2">{offer.conditions}</div>
                          </div>
                        </div>
                      )}

                      {/* Доступные методы оплаты - компактно */}
                      <div className="flex flex-wrap gap-1">
                        {offer.payment_methods.slice(0, 5).map((method) => (
                          <span key={method} className="px-2 py-0.5 bg-white/5 text-[#71717A] text-xs rounded">
                            {paymentMethodLabels[method] || method}
                          </span>
                        ))}
                        {offer.payment_methods.length > 5 && (
                          <span className="px-2 py-0.5 bg-white/5 text-[#52525B] text-xs rounded">
                            +{offer.payment_methods.length - 5}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Развернутая секция при выборе - компактный выбор реквизитов */}
                    {isSelected && offerRequisites.length > 0 && (
                      <div className="border-t border-white/10 px-6 py-4 bg-[#0A0A0A]/50">
                        {/* Компактный выбор реквизитов - в одну строку */}
                        <div className="flex flex-wrap gap-2 mb-3">
                          {offerRequisites.map((req) => (
                            <button
                              key={req.id}
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedRequisite(req);
                              }}
                              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all ${
                                selectedRequisite?.id === req.id
                                  ? "bg-[#7C3AED] text-white"
                                  : "bg-white/5 text-[#A1A1AA] hover:bg-white/10"
                              }`}
                            >
                              {req.type === "card" && <span>💳</span>}
                              {req.type === "sbp" && <span>⚡</span>}
                              {req.type === "qr" && <span>📱</span>}
                              {req.type === "sim" && <span>📞</span>}
                              <span>
                                {req.type === "card" && (req.data?.bank_name || "Карта")}
                                {req.type === "sbp" && (req.data?.bank_name || "СБП")}
                                {req.type === "qr" && "QR"}
                                {req.type === "sim" && (req.data?.operator || "SIM")}
                              </span>
                            </button>
                          ))}
                        </div>

                        {/* Кнопка Продолжить */}
                        <div className="flex items-center justify-between">
                          <div className="text-sm">
                            <span className="text-[#10B981]">@{offer.trader_login}</span>
                            <span className="text-[#52525B] ml-2">{parseInt(amountToPay).toLocaleString()} ₽</span>
                          </div>
                          <Button 
                            onClick={(e) => {
                              e.stopPropagation();
                              handleCreateTrade();
                            }}
                            disabled={creating || !selectedRequisite}
                            className={`h-10 rounded-xl px-6 ${
                              selectedRequisite 
                                ? "bg-[#10B981] hover:bg-[#059669]" 
                                : "bg-[#52525B] cursor-not-allowed"
                            }`}
                            data-testid="create-trade-btn"
                          >
                            {creating ? <div className="spinner" /> : "Продолжить →"}
                          </Button>
                        </div>
                      </div>
                    )}

                    {/* Если нет реквизитов - показать предупреждение */}
                    {isSelected && offerRequisites.length === 0 && (
                      <div className="border-t border-white/10 px-6 py-4 bg-[#0A0A0A]/50">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2 text-[#F59E0B]">
                            <AlertTriangle className="w-5 h-5" />
                            <span className="text-sm">Нет реквизитов</span>
                          </div>
                          <Button 
                            onClick={(e) => {
                              e.stopPropagation();
                              handleCreateTrade();
                            }}
                            disabled={creating}
                            className="bg-[#10B981] hover:bg-[#059669] h-10 rounded-xl px-6"
                            data-testid="create-trade-btn"
                          >
                            {creating ? <div className="spinner" /> : "Продолжить →"}
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Step: Payment - Show payment details
  if (step === "payment" && trade) {
    // Show only the selected requisite (first one)
    const requisite = (trade.requisites || [])[0];
    
    return (
      <div className="min-h-screen bg-[#0A0A0A] px-4 py-8">
        <div className="max-w-lg mx-auto">
          {/* Header with Timer */}
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-[#F59E0B]/10 flex items-center justify-center">
                <Timer className="w-5 h-5 text-[#F59E0B]" />
              </div>
              <div>
                <div className="text-white font-semibold">Оплатите в течение</div>
                <div className="text-2xl font-bold text-[#F59E0B] font-['JetBrains_Mono']">
                  {timeLeft !== null ? formatTime(timeLeft) : "30:00"}
                </div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-[#71717A] text-sm">Сделка</div>
              <div className="text-white font-['JetBrains_Mono']">#{trade.id.slice(0, 8)}</div>
            </div>
          </div>

          {/* Amount Card */}
          <div className="bg-gradient-to-br from-[#7C3AED] to-[#6D28D9] rounded-2xl p-5 mb-4">
            <div className="text-white/70 text-sm mb-1">Сумма к оплате</div>
            <div className="text-3xl font-bold text-white font-['JetBrains_Mono'] mb-2">
              {trade.amount_rub?.toLocaleString()} ₽
            </div>
            <div className="flex items-center gap-2 text-white/70 text-sm">
              <span>{trade.amount_usdt} USDT</span>
              <span>•</span>
              <span>{trade.price_rub} ₽/USDT</span>
            </div>
          </div>

          {/* Payment Requisite - только выбранный */}
          {requisite ? (
            <div className="bg-[#121212] border border-white/5 rounded-2xl p-5 mb-4">
              <div className="flex items-center justify-between mb-4">
                <span className="text-[#71717A] text-sm">Оплатите на реквизиты</span>
                <span className="text-[#7C3AED] text-sm">@{trade.trader_login}</span>
              </div>
              
              {requisite.type === "card" && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-[#F59E0B]">
                    <span>💳</span>
                    <span className="font-medium">{requisite.data?.bank_name || "Карта"}</span>
                  </div>
                  <div className="flex items-center justify-between bg-[#0A0A0A] rounded-xl p-3">
                    <div className="text-xl font-bold text-white font-['JetBrains_Mono']">
                      {requisite.data?.card_number || "—"}
                    </div>
                    <button 
                      onClick={() => copyToClipboard(requisite.data?.card_number?.replace(/\s/g, "") || "")}
                      className="p-2 rounded-lg bg-white/5 hover:bg-white/10"
                    >
                      <Copy className="w-4 h-4 text-[#71717A]" />
                    </button>
                  </div>
                  {requisite.data?.card_holder && (
                    <div className="flex items-center gap-2 text-[#71717A] text-sm">
                      <User className="w-4 h-4" />
                      <span>{requisite.data.card_holder}</span>
                    </div>
                  )}
                </div>
              )}
              
              {requisite.type === "sbp" && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-[#10B981]">
                    <span>⚡</span>
                    <span className="font-medium">СБП {requisite.data?.bank_name || ""}</span>
                  </div>
                  <div className="flex items-center justify-between bg-[#0A0A0A] rounded-xl p-3">
                    <div className="text-xl font-bold text-white font-['JetBrains_Mono']">
                      {requisite.data?.phone || "—"}
                    </div>
                    <button 
                      onClick={() => copyToClipboard(requisite.data?.phone?.replace(/\s/g, "") || "")}
                      className="p-2 rounded-lg bg-white/5 hover:bg-white/10"
                    >
                      <Copy className="w-4 h-4 text-[#71717A]" />
                    </button>
                  </div>
                  {requisite.data?.recipient_name && (
                    <div className="text-[#71717A] text-sm">{requisite.data.recipient_name}</div>
                  )}
                </div>
              )}
              
              {requisite.type === "sim" && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-[#F59E0B]">
                    <span>📞</span>
                    <span className="font-medium">{requisite.data?.operator || "SIM"}</span>
                  </div>
                  <div className="flex items-center justify-between bg-[#0A0A0A] rounded-xl p-3">
                    <div className="text-xl font-bold text-white font-['JetBrains_Mono']">
                      {requisite.data?.phone || "—"}
                    </div>
                    <button 
                      onClick={() => copyToClipboard(requisite.data?.phone?.replace(/\s/g, "") || "")}
                      className="p-2 rounded-lg bg-white/5 hover:bg-white/10"
                    >
                      <Copy className="w-4 h-4 text-[#71717A]" />
                    </button>
                  </div>
                </div>
              )}
              
              {requisite.type === "qr" && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-[#3B82F6]">
                    <span>📱</span>
                    <span className="font-medium">QR-код {requisite.data?.bank_name || ""}</span>
                  </div>
                  <div className="text-[#71717A] text-sm">{requisite.data?.description || "Отсканируйте QR в приложении банка"}</div>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-[#F59E0B]/10 border border-[#F59E0B]/20 rounded-xl p-4 mb-4">
              <div className="flex items-center gap-2 text-[#F59E0B]">
                <AlertTriangle className="w-5 h-5" />
                <span>Реквизиты недоступны. Свяжитесь с продавцом в чате.</span>
              </div>
            </div>
          )}

          {/* Chat */}
          <div className="bg-[#121212] border border-white/5 rounded-2xl mb-4">
            <div className="p-3 border-b border-white/5 flex items-center gap-2">
              <MessageCircle className="w-4 h-4 text-[#7C3AED]" />
              <span className="text-white text-sm font-medium">Чат с продавцом</span>
            </div>
            <div className="h-32 overflow-y-auto p-3 space-y-2">
              {messages.length === 0 ? (
                <div className="text-center py-2 text-[#52525B] text-xs">
                  Напишите если есть вопросы
                </div>
              ) : (
                messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${msg.sender_type === "client" ? "justify-end" : "justify-start"}`}
                  >
                    <div className={`max-w-[80%] rounded-lg px-2 py-1 ${
                      msg.sender_type === "system" 
                        ? "bg-[#7C3AED]/10 text-[#A855F7]"
                        : msg.sender_type === "client"
                          ? "bg-[#7C3AED] text-white"
                          : "bg-white/10 text-white"
                    }`}>
                      <p className="text-xs">{msg.content}</p>
                    </div>
                  </div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>
            <div className="p-2 border-t border-white/5 flex gap-2">
              <Input
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
                placeholder="Написать..."
                className="bg-[#0A0A0A] border-white/10 text-white rounded-lg h-9 text-sm"
              />
              <Button onClick={handleSendMessage} size="sm" className="bg-[#7C3AED] hover:bg-[#6D28D9] rounded-lg px-3">
                <Send className="w-3 h-3" />
              </Button>
            </div>
          </div>

          {/* Actions */}
          <div className="space-y-2">
            <Button 
              onClick={handleMarkPaid}
              className="w-full bg-[#10B981] hover:bg-[#059669] h-12 rounded-xl font-semibold"
              data-testid="mark-paid-btn"
            >
              <CheckCircle className="w-5 h-5 mr-2" />
              Я оплатил
            </Button>
            <Button 
              onClick={handleCancelTrade}
              variant="outline" 
              className="w-full border-white/10 h-10 rounded-xl text-[#EF4444] hover:bg-[#EF4444]/10"
            >
              <XCircle className="w-4 h-4 mr-2" />
              Отменить
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // Step: Waiting for confirmation
  if (step === "waiting" && trade) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] px-4 py-8">
        <div className="max-w-lg mx-auto">
          <div className="bg-[#121212] border border-white/5 rounded-3xl p-6 mb-6">
            <div className="flex items-center gap-4 mb-6">
              <div className="w-14 h-14 rounded-2xl bg-[#3B82F6]/10 flex items-center justify-center">
                <Clock className="w-7 h-7 text-[#3B82F6] animate-pulse" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-white">Ожидание подтверждения</h1>
                <p className="text-[#71717A] text-sm">Продавец проверяет поступление</p>
              </div>
            </div>

            <div className="bg-[#0A0A0A] rounded-xl p-4 space-y-3 mb-4">
              <div className="flex justify-between">
                <span className="text-[#71717A]">Сумма</span>
                <span className="text-white font-bold">{trade.amount_rub?.toLocaleString()} ₽</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#71717A]">USDT</span>
                <span className="text-[#10B981] font-bold">{trade.amount_usdt} USDT</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#71717A]">Продавец</span>
                <span className="text-white">@{trade.trader_login || selectedOffer?.trader_login}</span>
              </div>
            </div>

            {!canDispute && (
              <div className="bg-[#F59E0B]/10 rounded-xl p-3 text-sm text-[#F59E0B]">
                ⏳ Спор можно открыть через 10 минут после оплаты
              </div>
            )}
          </div>

          {/* Chat */}
          <div className="bg-[#121212] border border-white/5 rounded-2xl mb-6">
            <div className="p-4 border-b border-white/5 flex items-center gap-2">
              <MessageCircle className="w-5 h-5 text-[#7C3AED]" />
              <h3 className="text-white font-semibold">Чат с продавцом</h3>
            </div>
            <div className="h-64 overflow-y-auto p-4 space-y-2">
              {messages.length === 0 ? (
                <div className="text-center py-8 text-[#52525B] text-sm">
                  Напишите продавцу если возникли вопросы
                </div>
              ) : (
                messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${msg.sender_type === "client" ? "justify-end" : "justify-start"}`}
                  >
                    <div className={`max-w-[80%] rounded-xl px-3 py-2 ${
                      msg.sender_type === "system" 
                        ? "bg-[#7C3AED]/10 text-[#A855F7]"
                        : msg.sender_type === "client"
                          ? "bg-[#7C3AED] text-white"
                          : msg.sender_type === "admin"
                            ? "bg-[#EF4444]/20 text-[#EF4444]"
                            : "bg-white/10 text-white"
                    }`}>
                      {msg.sender_type === "trader" && (
                        <div className="text-xs text-[#71717A] mb-1">Продавец</div>
                      )}
                      {msg.sender_type === "admin" && (
                        <div className="text-xs text-[#EF4444] mb-1">Администратор</div>
                      )}
                      <p className="text-sm">{msg.content}</p>
                    </div>
                  </div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>
            <div className="p-3 border-t border-white/5 flex gap-2">
              <Input
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
                placeholder="Написать продавцу..."
                className="bg-[#0A0A0A] border-white/10 text-white rounded-xl"
              />
              <Button onClick={handleSendMessage} className="bg-[#7C3AED] hover:bg-[#6D28D9] rounded-xl px-4">
                <Send className="w-4 h-4" />
              </Button>
            </div>
          </div>

          {/* Actions */}
          <div className="space-y-3">
            <Button 
              onClick={handleOpenDispute}
              disabled={!canDispute}
              variant="outline" 
              className={`w-full h-12 rounded-xl ${canDispute ? "border-[#F59E0B]/50 text-[#F59E0B] hover:bg-[#F59E0B]/10" : "border-white/10 text-[#52525B]"}`}
              data-testid="open-dispute-btn"
            >
              <AlertTriangle className="w-4 h-4 mr-2" />
              {canDispute ? "Открыть спор" : "Спор доступен через 10 мин"}
            </Button>
            <Button 
              onClick={handleCancelTrade}
              variant="outline" 
              className="w-full border-white/10 h-12 rounded-xl text-[#EF4444] hover:bg-[#EF4444]/10"
            >
              <XCircle className="w-4 h-4 mr-2" />
              Отменить сделку
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // Step: Disputed
  if (step === "disputed" && trade) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] px-4 py-8">
        <div className="max-w-lg mx-auto">
          <div className="bg-[#EF4444]/10 border border-[#EF4444]/20 rounded-3xl p-6 mb-6">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-14 h-14 rounded-2xl bg-[#EF4444]/20 flex items-center justify-center">
                <AlertTriangle className="w-7 h-7 text-[#EF4444]" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-white">Спор открыт</h1>
                <p className="text-[#EF4444] text-sm">Администратор рассмотрит сделку</p>
              </div>
            </div>

            <div className="bg-[#0A0A0A] rounded-xl p-4 space-y-3">
              <div className="flex justify-between">
                <span className="text-[#71717A]">Сумма</span>
                <span className="text-white font-bold">{trade.amount_rub?.toLocaleString()} ₽</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#71717A]">Продавец</span>
                <span className="text-white">@{trade.trader_login || selectedOffer?.trader_login}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#71717A]">Статус</span>
                <span className="text-[#EF4444] font-medium">На рассмотрении</span>
              </div>
            </div>
          </div>

          {/* Chat with admin */}
          <div className="bg-[#121212] border border-white/5 rounded-2xl">
            <div className="p-4 border-b border-white/5 flex items-center gap-2">
              <MessageCircle className="w-5 h-5 text-[#EF4444]" />
              <h3 className="text-white font-semibold">Чат спора</h3>
              <span className="text-xs bg-[#EF4444]/20 text-[#EF4444] px-2 py-0.5 rounded ml-auto">Админ подключен</span>
            </div>
            <div className="h-72 overflow-y-auto p-4 space-y-2">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.sender_type === "client" ? "justify-end" : "justify-start"}`}
                >
                  <div className={`max-w-[80%] rounded-xl px-3 py-2 ${
                    msg.sender_type === "system" 
                      ? "bg-[#7C3AED]/10 text-[#A855F7]"
                      : msg.sender_type === "client"
                        ? "bg-[#7C3AED] text-white"
                        : msg.sender_type === "admin"
                          ? "bg-[#EF4444]/20 text-white"
                          : "bg-white/10 text-white"
                  }`}>
                    {msg.sender_type === "trader" && (
                      <div className="text-xs text-[#71717A] mb-1">Продавец</div>
                    )}
                    {msg.sender_type === "admin" && (
                      <div className="text-xs text-[#EF4444] mb-1">👨‍💼 Администратор</div>
                    )}
                    <p className="text-sm">{msg.content}</p>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
            <div className="p-3 border-t border-white/5 flex gap-2">
              <Input
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
                placeholder="Опишите проблему..."
                className="bg-[#0A0A0A] border-white/10 text-white rounded-xl"
              />
              <Button onClick={handleSendMessage} className="bg-[#7C3AED] hover:bg-[#6D28D9] rounded-xl px-4">
                <Send className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Step: Completed
  if (step === "completed" || trade?.status === "completed") {
    return (
      <div className="min-h-screen bg-[#0A0A0A] px-4 py-8">
        <div className="max-w-lg mx-auto">
          <div className="bg-[#121212] border border-white/5 rounded-3xl p-8 text-center">
            <div className="w-20 h-20 rounded-2xl bg-[#10B981]/10 flex items-center justify-center mx-auto mb-6">
              <CheckCircle className="w-10 h-10 text-[#10B981]" />
            </div>
            <h1 className="text-2xl font-bold text-white font-['Unbounded'] mb-2">Сделка завершена!</h1>
            <p className="text-[#71717A] mb-6">Средства зачислены на ваш счёт</p>
            <div className="bg-[#10B981]/10 rounded-xl p-4 text-[#10B981] font-bold text-2xl font-['JetBrains_Mono']">
              +{trade?.amount_usdt || link?.amount_usdt} USDT
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Default fallback
  return (
    <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
      <div className="spinner" />
    </div>
  );
}
