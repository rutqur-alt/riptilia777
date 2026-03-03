import { useState, useEffect, useRef } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { API } from "@/App";
import axios from "axios";
import { 
  Clock, CheckCircle, Copy, AlertTriangle, 
  Shield, MessageCircle, Timer, CreditCard, User,
  ChevronRight, RefreshCw, Send, XCircle, Building2, Wallet
} from "lucide-react";

/**
 * DepositPage - "White-label" платёжный интерфейс
 * Клиент видит "платёжных операторов", а не трейдеров и криптовалюту
 * Логика та же самая, меняется только отображение
 */

const bankLogos = {
  sberbank: "🟢",
  tinkoff: "🟡", 
  alfa: "🔴",
  vtb: "🔵",
  raiffeisen: "🟠",
  qiwi: "🟣",
  yoomoney: "🟣",
  sbp: "⚡",
  sbp_qr: "📱",
  sim: "📞",
};

const bankNames = {
  sberbank: "Сбербанк",
  tinkoff: "Тинькофф",
  alfa: "Альфа-Банк",
  vtb: "ВТБ",
  raiffeisen: "Райффайзен",
  qiwi: "QIWI",
  yoomoney: "ЮMoney",
  sbp: "СБП",
  sbp_qr: "СБП QR",
  sim: "Мобильный",
};

export default function DepositPage() {
  const { linkId } = useParams();
  const [searchParams] = useSearchParams();
  
  const [step, setStep] = useState("loading"); // loading, select_operator, payment, waiting, completed, disputed
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
  const [clientSessionId, setClientSessionId] = useState(null);
  const messagesEndRef = useRef(null);

  // Generate or get client session ID
  useEffect(() => {
    const storageKey = `deposit_client_${linkId}`;
    let sessionId = localStorage.getItem(storageKey);
    if (!sessionId) {
      sessionId = `client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      localStorage.setItem(storageKey, sessionId);
    }
    setClientSessionId(sessionId);
  }, [linkId]);

  useEffect(() => {
    if (clientSessionId) {
      fetchData();
    }
  }, [linkId, clientSessionId]);

  // Timer for trade
  useEffect(() => {
    if (trade && trade.status === "pending") {
      const interval = setInterval(() => {
        const expires = new Date(trade.expires_at);
        const now = new Date();
        const diff = Math.max(0, Math.floor((expires - now) / 1000));
        setTimeLeft(diff);
        if (diff === 0) clearInterval(interval);
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [trade]);

  // Check dispute availability
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

  // Fetch messages
  useEffect(() => {
    if (trade && trade.id && (step === "payment" || step === "waiting" || step === "disputed")) {
      fetchMessages(trade.id);
      const interval = setInterval(() => fetchMessages(trade.id), 3000);
      return () => clearInterval(interval);
    }
  }, [trade, step]);

  // Scroll messages
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
              toast.success("Оплата успешна! Средства зачислены.");
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

  const fetchData = async () => {
    try {
      // 1. Get payment link info
      const linkRes = await axios.get(`${API}/payment-links/${linkId}`);
      setLink(linkRes.data);
      
      // 2. Get merchant info
      const merchantRes = await axios.get(`${API}/merchants/${linkRes.data.merchant_id}/public`);
      setMerchant(merchantRes.data);
      
      // 3. Check for existing active trade for this client
      try {
        const activeTradeRes = await axios.get(`${API}/payment-links/${linkId}/active-trade`, {
          params: { client_id: clientSessionId }
        });
        
        if (activeTradeRes.data && activeTradeRes.data.id) {
          // Found active trade - restore it
          setTrade(activeTradeRes.data);
          
          // Set step based on trade status
          if (activeTradeRes.data.status === "pending") {
            setStep("payment");
          } else if (activeTradeRes.data.status === "paid") {
            setStep("waiting");
          } else if (activeTradeRes.data.status === "disputed") {
            setStep("disputed");
          } else if (activeTradeRes.data.status === "completed") {
            setStep("completed");
          } else if (activeTradeRes.data.status === "cancelled") {
            setStep("cancelled");
          }
          
          // Fetch messages
          fetchMessages(activeTradeRes.data.id);
          setLoading(false);
          return; // Don't need to fetch offers
        }
      } catch (e) {
        // No active trade, continue to offer selection
      }
      
      // 4. If no active trade - check if link is already completed
      if (linkRes.data.status === "completed") {
        setStep("completed");
        setLoading(false);
        return;
      }
      
      // 5. Fetch available offers filtered by merchant type and amount
      // Backend already filters by:
      // - is_active: true
      // - accepted_merchant_types includes merchant_type  
      // - available_usdt > 0
      const offersRes = await axios.get(`${API}/offers`, {
        params: {
          merchant_type: merchantRes.data.merchant_type,
          min_amount: linkRes.data.amount_usdt  // Only show offers that can cover this amount
        }
      });
      
      // Additional frontend filter to ensure enough balance
      const validOffers = offersRes.data.filter(o => 
        o.min_amount <= linkRes.data.amount_usdt && 
        o.available_usdt >= linkRes.data.amount_usdt  // Must have enough available balance
      );
      setOffers(validOffers);
      setStep("select_operator");
    } catch (error) {
      console.error(error);
      toast.error("Ошибка загрузки данных");
    } finally {
      setLoading(false);
    }
  };
  
  const fetchMessages = async (tradeId) => {
    try {
      const response = await axios.get(`${API}/trades/${tradeId}/messages-public`);
      setMessages(response.data);
    } catch (error) {
      console.error(error);
    }
  };

  const handleSelectOffer = (offer) => {
    setSelectedOffer(offer);
    setSelectedRequisite(null);
  };

  const handleCreateTrade = async () => {
    if (!selectedOffer) return;
    
    setCreating(true);
    try {
      const requisiteIds = selectedRequisite 
        ? [selectedRequisite.id] 
        : (selectedOffer.requisite_ids || []);
      
      const response = await axios.post(`${API}/trades`, {
        amount_usdt: link.amount_usdt,
        price_rub: selectedOffer.price_rub,
        trader_id: selectedOffer.trader_id,
        payment_link_id: linkId,
        offer_id: selectedOffer.id,
        requisite_ids: requisiteIds,
        client_session_id: clientSessionId  // Save client session for returning
      });
      
      // Save trade ID to localStorage as backup
      localStorage.setItem(`deposit_trade_${linkId}`, response.data.id);
      
      setTrade(response.data);
      setStep("payment");
      toast.success("Заявка создана! Оплатите в течение 30 минут.");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка создания заявки");
    } finally {
      setCreating(false);
    }
  };

  const handleMarkPaid = async () => {
    try {
      await axios.post(`${API}/trades/${trade.id}/mark-paid`);
      setTrade({ ...trade, status: "paid" });
      setStep("waiting");
      toast.success("Ожидайте подтверждения оплаты");
    } catch (error) {
      toast.error("Ошибка");
    }
  };

  const handleOpenDispute = async () => {
    if (!trade || !canDispute) return;
    
    const reason = prompt("Опишите проблему:");
    if (!reason) return;
    
    try {
      await axios.post(`${API}/trades/${trade.id}/dispute-public`, null, { params: { reason } });
      setTrade({ ...trade, status: "disputed" });
      setStep("disputed");
      toast.success("Обращение отправлено. Оператор подключится к чату.");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка");
    }
  };

  const handleCancelTrade = async () => {
    if (!trade) return;
    if (!confirm("Отменить платёж?")) return;
    
    try {
      await axios.post(`${API}/trades/${trade.id}/cancel-client`);
      setTrade({ ...trade, status: "cancelled" });
      setStep("cancelled");
      toast.success("Платёж отменён");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка отмены");
    }
  };

  const handleSendMessage = async () => {
    if (!newMessage.trim() || !trade) return;
    
    try {
      await axios.post(`${API}/trades/${trade.id}/messages-public`, { content: newMessage });
      setNewMessage("");
      fetchMessages();
    } catch (error) {
      toast.error("Ошибка отправки");
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

  // Calculate operator fee percentage (difference from base merchant rate)
  const calculateOperatorFee = (offer) => {
    if (!link) return 0;
    const baseRate = link.price_rub; // Merchant's base rate
    const operatorRate = offer.price_rub;
    const feePercent = ((operatorRate - baseRate) / baseRate * 100).toFixed(1);
    return parseFloat(feePercent);
  };

  // Get total amount to pay (in RUB)
  const getTotalAmount = (offer) => {
    if (!link) return 0;
    return Math.round(link.amount_usdt * offer.price_rub);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 flex items-center justify-center">
        <div className="w-8 h-8 border-3 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!link) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 flex items-center justify-center px-4">
        <div className="text-center max-w-md bg-white rounded-2xl shadow-lg p-8">
          <AlertTriangle className="w-16 h-16 text-amber-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-slate-800 mb-2">Ссылка недействительна</h1>
          <p className="text-slate-500">Платёжная ссылка не найдена или истекла</p>
        </div>
      </div>
    );
  }

  if (link.status !== "active" && !trade) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 flex items-center justify-center px-4">
        <div className="text-center max-w-md bg-white rounded-2xl shadow-lg p-8">
          <CheckCircle className="w-16 h-16 text-emerald-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-slate-800 mb-2">Платёж завершён</h1>
          <p className="text-slate-500">Эта ссылка уже была использована</p>
        </div>
      </div>
    );
  }

  // =============== STEP: SELECT OPERATOR ===============
  if (step === "select_operator") {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 px-4 py-8">
        <div className="max-w-xl mx-auto">
          {/* Header */}
          <div className="text-center mb-8">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center mx-auto mb-4 shadow-lg">
              <Wallet className="w-8 h-8 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-slate-800 mb-2">Пополнение счёта</h1>
            <p className="text-slate-500">{merchant?.merchant_name || "Сервис"}</p>
          </div>

          {/* Amount Card */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
            <div className="text-center">
              <div className="text-slate-500 text-sm mb-1">Сумма к зачислению</div>
              <div className="text-4xl font-bold text-slate-800">
                {link.amount_rub.toLocaleString()} ₽
              </div>
            </div>
          </div>

          {/* Operators List */}
          <div className="mb-4">
            <h2 className="text-lg font-semibold text-slate-800 mb-3">Выберите платёжного оператора</h2>
          </div>

          {offers.length === 0 ? (
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 text-center">
              <AlertTriangle className="w-12 h-12 text-amber-500 mx-auto mb-4" />
              <h2 className="text-xl font-bold text-slate-800 mb-2">Операторы недоступны</h2>
              <p className="text-slate-500 mb-6">В данный момент нет доступных операторов. Попробуйте позже.</p>
              <Button onClick={() => window.location.reload()} className="bg-blue-600 hover:bg-blue-700">
                <RefreshCw className="w-4 h-4 mr-2" />
                Обновить
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {offers.map((offer, index) => {
                const totalAmount = getTotalAmount(offer);
                const feePercent = calculateOperatorFee(offer);
                const isSelected = selectedOffer?.id === offer.id;
                const requisites = offer.requisites || [];
                
                // Get primary payment method
                const primaryMethod = offer.payment_methods?.[0] || "card";
                
                return (
                  <div
                    key={offer.id}
                    className={`bg-white rounded-xl border-2 transition-all overflow-hidden ${
                      isSelected
                        ? "border-blue-500 shadow-md"
                        : "border-slate-200 hover:border-slate-300"
                    }`}
                  >
                    {/* Operator Info */}
                    <div 
                      className="p-4 cursor-pointer"
                      onClick={() => handleSelectOffer(offer)}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          {/* Operator Icon */}
                          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-slate-100 to-slate-200 flex items-center justify-center text-2xl">
                            {bankLogos[primaryMethod] || <Building2 className="w-6 h-6 text-slate-400" />}
                          </div>
                          <div>
                            <div className="font-semibold text-slate-800">
                              Оператор #{index + 1}
                            </div>
                            <div className="text-sm text-slate-500">
                              {(() => {
                                // Get unique payment types from requisites - show ALL
                                const types = [...new Set(offer.requisites?.map(r => r.type) || [])];
                                const typeNames = {
                                  card: "Банковская карта",
                                  sbp: "СБП",
                                  qr: "QR-код", 
                                  sim: "Сотовая связь",
                                  cis: "Перевод СНГ"
                                };
                                return types.map(t => typeNames[t] || t).join(", ");
                              })()}
                            </div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-xl font-bold text-slate-800">
                            {totalAmount.toLocaleString()} ₽
                          </div>
                          {feePercent > 0 && (
                            <div className="text-sm text-amber-600">
                              +{feePercent}% комиссия
                            </div>
                          )}
                          {feePercent <= 0 && (
                            <div className="text-sm text-emerald-600">
                              Без комиссии
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Rating */}
                      <div className="mt-3 flex items-center gap-4 text-sm">
                        <div className="flex items-center gap-1">
                          <CheckCircle className="w-4 h-4 text-emerald-500" />
                          <span className="text-slate-600">{offer.success_rate || 100}% успешных</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <Clock className="w-4 h-4 text-blue-500" />
                          <span className="text-slate-600">~5 мин</span>
                        </div>
                      </div>
                    </div>

                    {/* Expanded - Select Payment Method */}
                    {isSelected && requisites.length > 0 && (
                      <div className="border-t border-slate-100 p-4 bg-slate-50">
                        <div className="text-sm font-medium text-slate-700 mb-3">Способ оплаты</div>
                        <div className="flex flex-wrap gap-2 mb-4">
                          {requisites.map((req) => (
                            <button
                              key={req.id}
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedRequisite(req);
                              }}
                              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                                selectedRequisite?.id === req.id
                                  ? "bg-blue-600 text-white shadow-sm"
                                  : "bg-white text-slate-700 border border-slate-200 hover:border-blue-300"
                              }`}
                            >
                              <span className="text-lg">
                                {req.type === "card" && "💳"}
                                {req.type === "sbp" && "⚡"}
                                {req.type === "qr" && "📱"}
                                {req.type === "sim" && "📞"}
                                {req.type === "cis" && "🌍"}
                              </span>
                              <span>
                                {req.type === "card" && "Банковская карта"}
                                {req.type === "sbp" && "СБП"}
                                {req.type === "qr" && "QR-код"}
                                {req.type === "sim" && "Сотовая связь"}
                                {req.type === "cis" && "Перевод СНГ"}
                              </span>
                            </button>
                          ))}
                        </div>
                        
                        <Button 
                          onClick={(e) => {
                            e.stopPropagation();
                            handleCreateTrade();
                          }}
                          disabled={creating || !selectedRequisite}
                          className={`w-full h-12 rounded-xl font-semibold ${
                            selectedRequisite 
                              ? "bg-blue-600 hover:bg-blue-700" 
                              : "bg-slate-300 cursor-not-allowed"
                          }`}
                        >
                          {creating ? (
                            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                          ) : (
                            <>
                              Оплатить {totalAmount.toLocaleString()} ₽
                              <ChevronRight className="w-5 h-5 ml-2" />
                            </>
                          )}
                        </Button>
                      </div>
                    )}

                    {/* No requisites */}
                    {isSelected && requisites.length === 0 && (
                      <div className="border-t border-slate-100 p-4 bg-slate-50">
                        <Button 
                          onClick={(e) => {
                            e.stopPropagation();
                            handleCreateTrade();
                          }}
                          disabled={creating}
                          className="w-full h-12 rounded-xl font-semibold bg-blue-600 hover:bg-blue-700"
                        >
                          {creating ? (
                            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                          ) : (
                            <>
                              Оплатить {totalAmount.toLocaleString()} ₽
                              <ChevronRight className="w-5 h-5 ml-2" />
                            </>
                          )}
                        </Button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Security Badge */}
          <div className="mt-6 flex items-center justify-center gap-2 text-sm text-slate-500">
            <Shield className="w-4 h-4" />
            <span>Безопасная оплата</span>
          </div>

          {/* Earn with us CTA */}
          <div className="mt-8 text-center">
            <a 
              href="/auth" 
              className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white font-semibold rounded-xl shadow-lg shadow-emerald-500/30 transition-all hover:shadow-emerald-500/50"
            >
              <Wallet className="w-5 h-5" />
              Зарабатывай с нами
            </a>
            <p className="mt-2 text-sm text-slate-500">Стань платёжным оператором и получай доход</p>
          </div>
        </div>
      </div>
    );
  }

  // =============== STEP: PAYMENT ===============
  if (step === "payment" && trade) {
    const requisite = (trade.requisites || [])[0];
    const totalAmount = trade.amount_rub;
    
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 px-4 py-8">
        <div className="max-w-lg mx-auto">
          {/* Timer Header */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-4 mb-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-amber-100 flex items-center justify-center">
                  <Timer className="w-6 h-6 text-amber-600" />
                </div>
                <div>
                  <div className="text-sm text-slate-500">Оплатите в течение</div>
                  <div className="text-2xl font-bold text-amber-600 font-mono">
                    {timeLeft !== null ? formatTime(timeLeft) : "30:00"}
                  </div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm text-slate-500">Заявка</div>
                <div className="text-slate-800 font-mono">#{trade.id.slice(0, 8)}</div>
              </div>
            </div>
          </div>

          {/* Amount Card */}
          <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-2xl p-6 mb-4 text-white shadow-lg">
            <div className="text-blue-100 text-sm mb-1">Сумма к оплате</div>
            <div className="text-4xl font-bold font-mono mb-2">
              {totalAmount?.toLocaleString()} ₽
            </div>
            <div className="text-blue-200 text-sm">
              Зачисление: {link.amount_rub.toLocaleString()} ₽
            </div>
          </div>

          {/* Payment Details */}
          {requisite ? (
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-5 mb-4">
              <div className="text-sm text-slate-500 mb-4">Реквизиты для оплаты</div>
              
              {requisite.type === "card" && (
                <div className="space-y-4">
                  <div className="flex items-center gap-2 text-slate-700">
                    <span className="text-2xl">💳</span>
                    <span className="font-medium">{requisite.data?.bank_name || "Банковская карта"}</span>
                  </div>
                  <div className="flex items-center justify-between bg-slate-50 rounded-xl p-4">
                    <div className="text-2xl font-bold text-slate-800 font-mono tracking-wider">
                      {requisite.data?.card_number || "—"}
                    </div>
                    <button 
                      onClick={() => copyToClipboard(requisite.data?.card_number?.replace(/\s/g, "") || "")}
                      className="p-2 rounded-lg bg-blue-100 hover:bg-blue-200 transition-colors"
                    >
                      <Copy className="w-5 h-5 text-blue-600" />
                    </button>
                  </div>
                  {requisite.data?.card_holder && (
                    <div className="flex items-center gap-2 text-slate-600 text-sm">
                      <User className="w-4 h-4" />
                      <span>{requisite.data.card_holder}</span>
                    </div>
                  )}
                </div>
              )}
              
              {requisite.type === "sbp" && (
                <div className="space-y-4">
                  <div className="flex items-center gap-2 text-slate-700">
                    <span className="text-2xl">⚡</span>
                    <span className="font-medium">СБП {requisite.data?.bank_name || ""}</span>
                  </div>
                  <div className="flex items-center justify-between bg-slate-50 rounded-xl p-4">
                    <div className="text-2xl font-bold text-slate-800 font-mono">
                      {requisite.data?.phone || "—"}
                    </div>
                    <button 
                      onClick={() => copyToClipboard(requisite.data?.phone?.replace(/\s/g, "") || "")}
                      className="p-2 rounded-lg bg-blue-100 hover:bg-blue-200 transition-colors"
                    >
                      <Copy className="w-5 h-5 text-blue-600" />
                    </button>
                  </div>
                  {requisite.data?.recipient_name && (
                    <div className="text-slate-600 text-sm">{requisite.data.recipient_name}</div>
                  )}
                </div>
              )}
              
              {requisite.type === "sim" && (
                <div className="space-y-4">
                  <div className="flex items-center gap-2 text-slate-700">
                    <span className="text-2xl">📞</span>
                    <span className="font-medium">{requisite.data?.operator || "Мобильный перевод"}</span>
                  </div>
                  <div className="flex items-center justify-between bg-slate-50 rounded-xl p-4">
                    <div className="text-2xl font-bold text-slate-800 font-mono">
                      {requisite.data?.phone || "—"}
                    </div>
                    <button 
                      onClick={() => copyToClipboard(requisite.data?.phone?.replace(/\s/g, "") || "")}
                      className="p-2 rounded-lg bg-blue-100 hover:bg-blue-200 transition-colors"
                    >
                      <Copy className="w-5 h-5 text-blue-600" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-4">
              <div className="flex items-center gap-2 text-amber-700">
                <AlertTriangle className="w-5 h-5" />
                <span>Реквизиты появятся в чате</span>
              </div>
            </div>
          )}

          {/* Chat */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 mb-4 overflow-hidden">
            <div className="p-3 border-b border-slate-100 flex items-center gap-2 bg-slate-50">
              <MessageCircle className="w-4 h-4 text-blue-600" />
              <span className="text-slate-700 text-sm font-medium">Чат с оператором</span>
            </div>
            <div className="h-32 overflow-y-auto p-3 space-y-2">
              {messages.length === 0 ? (
                <div className="text-center py-4 text-slate-400 text-sm">
                  Напишите, если есть вопросы
                </div>
              ) : (
                messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${msg.sender_type === "client" ? "justify-end" : "justify-start"}`}
                  >
                    <div className={`max-w-[80%] rounded-xl px-3 py-2 text-sm ${
                      msg.sender_type === "client"
                        ? "bg-blue-600 text-white"
                        : "bg-slate-100 text-slate-700"
                    }`}>
                      {msg.content}
                    </div>
                  </div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>
            <div className="p-2 border-t border-slate-100 flex gap-2">
              <Input
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
                placeholder="Сообщение..."
                className="bg-slate-50 border-slate-200 rounded-lg h-9 text-sm text-slate-800"
              />
              <Button onClick={handleSendMessage} size="sm" className="bg-blue-600 hover:bg-blue-700 rounded-lg px-3">
                <Send className="w-4 h-4" />
              </Button>
            </div>
          </div>

          {/* Actions */}
          <div className="space-y-2">
            <Button 
              onClick={handleMarkPaid}
              className="w-full bg-emerald-500 hover:bg-emerald-600 h-12 rounded-xl font-semibold"
            >
              <CheckCircle className="w-5 h-5 mr-2" />
              Я оплатил
            </Button>
            <Button 
              onClick={handleCancelTrade}
              variant="outline" 
              className="w-full border-slate-200 h-10 rounded-xl text-slate-600 hover:bg-slate-50"
            >
              <XCircle className="w-4 h-4 mr-2" />
              Отменить
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // =============== STEP: WAITING ===============
  if (step === "waiting" && trade) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 px-4 py-8">
        <div className="max-w-lg mx-auto">
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
            <div className="flex items-center gap-4 mb-6">
              <div className="w-14 h-14 rounded-2xl bg-blue-100 flex items-center justify-center">
                <Clock className="w-7 h-7 text-blue-600 animate-pulse" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-slate-800">Проверка оплаты</h1>
                <p className="text-slate-500 text-sm">Оператор проверяет поступление средств</p>
              </div>
            </div>

            <div className="bg-slate-50 rounded-xl p-4 space-y-3 mb-4">
              <div className="flex justify-between">
                <span className="text-slate-500">Сумма</span>
                <span className="font-bold text-slate-800">{trade.amount_rub?.toLocaleString()} ₽</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Зачисление</span>
                <span className="font-bold text-emerald-600">{link.amount_rub.toLocaleString()} ₽</span>
              </div>
            </div>

            {!canDispute && (
              <div className="bg-amber-50 rounded-xl p-3 text-sm text-amber-700">
                ⏳ Обратиться в поддержку можно через 10 минут
              </div>
            )}
          </div>

          {/* Chat */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 mb-6 overflow-hidden">
            <div className="p-4 border-b border-slate-100 flex items-center gap-2">
              <MessageCircle className="w-5 h-5 text-blue-600" />
              <h3 className="font-semibold text-slate-800">Чат с оператором</h3>
            </div>
            <div className="h-64 overflow-y-auto p-4 space-y-2">
              {messages.length === 0 ? (
                <div className="text-center py-8 text-slate-400 text-sm">
                  Напишите, если возникли вопросы
                </div>
              ) : (
                messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${msg.sender_type === "client" ? "justify-end" : "justify-start"}`}
                  >
                    <div className={`max-w-[80%] rounded-xl px-3 py-2 ${
                      msg.sender_type === "admin"
                        ? "bg-red-100 text-red-800"
                        : msg.sender_type === "client"
                          ? "bg-blue-600 text-white"
                          : "bg-slate-100 text-slate-700"
                    }`}>
                      {msg.sender_type === "admin" && (
                        <div className="text-xs font-medium mb-1">Поддержка</div>
                      )}
                      <p className="text-sm">{msg.content}</p>
                    </div>
                  </div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>
            <div className="p-3 border-t border-slate-100 flex gap-2">
              <Input
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
                placeholder="Сообщение..."
                className="bg-slate-50 border-slate-200 rounded-xl text-slate-800"
              />
              <Button onClick={handleSendMessage} className="bg-blue-600 hover:bg-blue-700 rounded-xl px-4">
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
              className={`w-full h-12 rounded-xl ${canDispute ? "border-amber-300 text-amber-600 hover:bg-amber-50" : "border-slate-200 text-slate-400"}`}
            >
              <AlertTriangle className="w-4 h-4 mr-2" />
              {canDispute ? "Обратиться в поддержку" : "Поддержка через 10 мин"}
            </Button>
            <Button 
              onClick={handleCancelTrade}
              variant="outline" 
              className="w-full border-slate-200 h-12 rounded-xl text-red-500 hover:bg-red-50"
            >
              <XCircle className="w-4 h-4 mr-2" />
              Отменить платёж
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // =============== STEP: DISPUTED ===============
  if (step === "disputed" && trade) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 px-4 py-8">
        <div className="max-w-lg mx-auto">
          <div className="bg-amber-50 border border-amber-200 rounded-2xl p-6 mb-6">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-14 h-14 rounded-2xl bg-amber-100 flex items-center justify-center">
                <AlertTriangle className="w-7 h-7 text-amber-600" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-slate-800">Обращение в поддержку</h1>
                <p className="text-amber-700 text-sm">Оператор подключится к чату</p>
              </div>
            </div>

            <div className="bg-white rounded-xl p-4 space-y-3">
              <div className="flex justify-between">
                <span className="text-slate-500">Сумма</span>
                <span className="font-bold text-slate-800">{trade.amount_rub?.toLocaleString()} ₽</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Статус</span>
                <span className="text-amber-600 font-medium">На рассмотрении</span>
              </div>
            </div>
          </div>

          {/* Chat */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="p-4 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <MessageCircle className="w-5 h-5 text-amber-600" />
                <h3 className="font-semibold text-slate-800">Чат поддержки</h3>
              </div>
              <span className="text-xs bg-amber-100 text-amber-700 px-2 py-1 rounded">Оператор подключён</span>
            </div>
            <div className="h-72 overflow-y-auto p-4 space-y-2">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.sender_type === "client" ? "justify-end" : "justify-start"}`}
                >
                  <div className={`max-w-[80%] rounded-xl px-3 py-2 ${
                    msg.sender_type === "admin"
                      ? "bg-amber-100 text-amber-800"
                      : msg.sender_type === "client"
                        ? "bg-blue-600 text-white"
                        : "bg-slate-100 text-slate-700"
                  }`}>
                    {msg.sender_type === "admin" && (
                      <div className="text-xs font-medium mb-1">👨‍💼 Поддержка</div>
                    )}
                    <p className="text-sm">{msg.content}</p>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
            <div className="p-3 border-t border-slate-100 flex gap-2">
              <Input
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
                placeholder="Опишите проблему..."
                className="bg-slate-50 border-slate-200 rounded-xl text-slate-800"
              />
              <Button onClick={handleSendMessage} className="bg-blue-600 hover:bg-blue-700 rounded-xl px-4">
                <Send className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // =============== STEP: CANCELLED ===============
  if (step === "cancelled" || trade?.status === "cancelled") {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 px-4 py-8">
        <div className="max-w-lg mx-auto">
          <div className="bg-white rounded-2xl shadow-lg border border-slate-200 p-8 text-center">
            <div className="w-20 h-20 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-6">
              <XCircle className="w-10 h-10 text-slate-400" />
            </div>
            <h1 className="text-2xl font-bold text-slate-800 mb-2">Платёж отменён</h1>
            <p className="text-slate-500 mb-6">Вы отменили этот платёж</p>
            <div className="bg-slate-50 rounded-xl p-6 text-slate-500 font-medium">
              {link?.amount_rub?.toLocaleString()} ₽
            </div>
            <p className="text-slate-400 text-sm mt-4">
              Вы можете создать новый платёж в личном кабинете
            </p>
          </div>
        </div>
      </div>
    );
  }

  // =============== STEP: COMPLETED ===============
  if (step === "completed" || trade?.status === "completed") {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 px-4 py-8">
        <div className="max-w-lg mx-auto">
          <div className="bg-white rounded-2xl shadow-lg border border-slate-200 p-8 text-center">
            <div className="w-20 h-20 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-6">
              <CheckCircle className="w-10 h-10 text-emerald-500" />
            </div>
            <h1 className="text-2xl font-bold text-slate-800 mb-2">Оплата успешна!</h1>
            <p className="text-slate-500 mb-6">Средства зачислены на ваш счёт</p>
            <div className="bg-emerald-50 rounded-xl p-6 text-emerald-700 font-bold text-3xl">
              +{link?.amount_rub?.toLocaleString()} ₽
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Default
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 flex items-center justify-center">
      <div className="w-8 h-8 border-3 border-blue-600 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}
