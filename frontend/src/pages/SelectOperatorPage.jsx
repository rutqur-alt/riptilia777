import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import { API } from "@/App";
import axios from "axios";
import { 
  Clock, CheckCircle, Copy, AlertTriangle, 
  Shield, MessageCircle, Timer,
  RefreshCw, Send, XCircle, 
  Wallet, ArrowRight, Loader2, Check,
  Star, Circle, User, CreditCard, Smartphone, QrCode,
  ExternalLink, ChevronDown
} from "lucide-react";
import { PAYMENT_METHODS, getPaymentMethod, PAYMENT_METHOD_OPTIONS } from "@/config/paymentMethods";

// Иконки для типов реквизитов
const getRequisiteIcon = (type) => {
  switch (type) {
    case "card": return CreditCard;
    case "sbp": return Smartphone;
    case "sim": return Smartphone;
    case "qr_code": return QrCode;
    default: return CreditCard;
  }
};

const getRequisiteLabel = (type) => {
  switch (type) {
    case "card": return "Банковская карта";
    case "sbp": return "СБП";
    case "sim": return "Мобильный";
    case "qr_code": return "QR-код";
    default: return type;
  }
};

export default function SelectOperatorPage() {
  const { invoiceId } = useParams();
  const navigate = useNavigate();
  
  const [step, setStep] = useState("loading");
  const [invoice, setInvoice] = useState(null);
  const [operators, setOperators] = useState([]);
  const [filteredOperators, setFilteredOperators] = useState([]);
  const [selectedFilter, setSelectedFilter] = useState("all");
  const [availableMethods, setAvailableMethods] = useState([]);
  const [selectedOperator, setSelectedOperator] = useState(null);
  const [selectedRequisite, setSelectedRequisite] = useState(null);
  const [trade, setTrade] = useState(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [timeLeft, setTimeLeft] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState("");
  const [canDispute, setCanDispute] = useState(false);
  const [disputeCountdown, setDisputeCountdown] = useState(null); // Обратный отсчёт до спора
  const [depositAmount, setDepositAmount] = useState(0);
  const [showOperatorDialog, setShowOperatorDialog] = useState(false);
  const [rulesAccepted, setRulesAccepted] = useState(false);
  const [disputeLink, setDisputeLink] = useState(null);
  const [chatLink, setChatLink] = useState(null); // Ссылка на чат для покупателя
  // Сохраняем выбранный реквизит локально для отображения
  const [savedRequisite, setSavedRequisite] = useState(null);
  const [showMethodsDropdown, setShowMethodsDropdown] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => { loadData(); }, [invoiceId]);
  
  useEffect(() => {
    if (trade?.status === "pending" && trade?.expires_at) {
      const timer = setInterval(() => {
        const diff = Math.max(0, Math.floor((new Date(trade.expires_at) - new Date()) / 1000));
        setTimeLeft(diff);
        if (diff === 0) clearInterval(timer);
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [trade]);

  useEffect(() => {
    if (trade?.status === "paid" && trade?.paid_at) {
      const updateDispute = () => {
        const paidTime = new Date(trade.paid_at);
        const now = new Date();
        const minutesPassed = (now - paidTime) / 60000;
        
        if (minutesPassed >= 10) {
          setCanDispute(true);
          setDisputeCountdown(null);
        } else {
          setCanDispute(false);
          // Обратный отсчёт в секундах
          const secondsLeft = Math.max(0, Math.ceil((10 - minutesPassed) * 60));
          setDisputeCountdown(secondsLeft);
        }
      };
      
      updateDispute();
      const i = setInterval(updateDispute, 1000);
      return () => clearInterval(i);
    }
  }, [trade]);

  // Fetch messages for chat
  useEffect(() => {
    if (trade && !["completed", "cancelled"].includes(trade.status)) {
      fetchMessages();
      const i = setInterval(fetchMessages, 3000);
      return () => clearInterval(i);
    }
  }, [trade]);

  // Poll trade status
  useEffect(() => {
    if (trade && !["completed", "cancelled"].includes(trade.status)) {
      const poll = setInterval(async () => {
        try {
          const res = await axios.get(`${API}/trades/${trade.id}/public`);
          if (res.data.status !== trade.status) {
            setTrade(res.data);
            if (res.data.status === "completed") { 
              setStep("completed"); 
              toast.success("Платёж зачислен!"); 
            }
            else if (res.data.status === "disputed") setStep("disputed");
          }
        } catch (e) {}
      }, 5000);
      return () => clearInterval(poll);
    }
  }, [trade]);

  useEffect(() => { 
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); 
  }, [messages]);

  // Фильтрация операторов
  useEffect(() => {
    if (selectedFilter === "all") {
      setFilteredOperators(operators);
    } else {
      setFilteredOperators(operators.filter(op => 
        op.requisites?.some(r => r.type === selectedFilter)
      ));
    }
  }, [selectedFilter, operators]);

  const loadData = async () => {
    setLoading(true);
    try {
      const invRes = await axios.get(`${API}/shop/pay/${invoiceId}`);
      const inv = invRes.data.order;
      setInvoice(inv);
      
      // Сумма пополнения - всегда используем original_amount_rub (исходная сумма заказа)
      const deposit = inv.original_amount_rub || inv.amount_rub || Math.round((inv.amount_usdt || 0) * 97);
      setDepositAmount(deposit);
      
      // Если уже есть trade_id - загружаем trade
      if (inv.trade_id) {
        const trRes = await axios.get(`${API}/trades/${inv.trade_id}/public`);
        setTrade(trRes.data);
        
        // Сохраняем реквизит из trade
        if (trRes.data.requisites?.[0]) {
          setSavedRequisite(trRes.data.requisites[0]);
        }
        
        const st = trRes.data.status;
        setStep(st === "pending" ? "payment" : 
                st === "paid" ? "waiting" : 
                st === "completed" ? "completed" : 
                st === "disputed" ? "disputed" : "select_operator");
        return;
      }
      
      if (["completed", "paid"].includes(inv.status)) { setStep("completed"); return; }
      if (["cancelled", "expired"].includes(inv.status)) { setStep("error"); return; }
      
      // Загружаем операторов
      const params = new URLSearchParams();
      // Используем original_amount_rub (исходная сумма заказа мерчанта)
      const requestAmount = inv.original_amount_rub || inv.amount_rub;
      if (requestAmount) params.set("amount_rub", requestAmount);
      else if (inv.amount_usdt) params.set("amount_usdt", inv.amount_usdt);
      
      const opRes = await axios.get(`${API}/public/operators?${params}`);
      const ops = opRes.data.operators || [];
      
      // Показываем все методы оплаты из конфига
      const allMethods = Object.keys(PAYMENT_METHODS);
      setAvailableMethods(allMethods);
      
      // Рассчитываем сумму к оплате для каждого оператора
      // Формула: (сумма_руб / базовый_курс) * курс_трейдера
      // Базовый курс из Rapira API, курс трейдера выше → клиент платит больше
      const exchangeRate = opRes.data.exchange_rate || 78;
      const operatorsWithPrice = ops.map(op => {
        // Сумма к оплате: из бэкенда или пересчёт
        let toPayRub = op.amount_to_pay_rub || Math.round((deposit / exchangeRate) * op.price_rub);
        // Клиент никогда не платит меньше суммы пополнения
        if (deposit > 0) toPayRub = Math.max(toPayRub, deposit);
        const commissionPercent = ((op.price_rub - exchangeRate) / exchangeRate * 100).toFixed(1);
        
        return {
          ...op,
          toPayRub,
          commissionPercent: Math.max(0, parseFloat(commissionPercent))
        };
      });
      
      operatorsWithPrice.sort((a, b) => a.toPayRub - b.toPayRub);
      
      setOperators(operatorsWithPrice);
      setFilteredOperators(operatorsWithPrice);
      setStep("select_operator");
    } catch (e) {
      toast.error("Ошибка загрузки");
      setStep("error");
    } finally { setLoading(false); }
  };

  const fetchMessages = async () => {
    if (!trade) return;
    try {
      const res = await axios.get(`${API}/trades/${trade.id}/messages-public`);
      setMessages(res.data || []);
    } catch (e) {}
  };

  // Открыть диалог выбора оператора
  const openOperatorDialog = (operator) => {
    setSelectedOperator(operator);
    if (operator.requisites?.length === 1) {
      setSelectedRequisite(operator.requisites[0]);
    } else {
      setSelectedRequisite(null);
    }
    setRulesAccepted(false);
    setShowOperatorDialog(true);
  };

  // Начать сделку
  const startTrade = async () => {
    if (!selectedOperator || !invoice) return;
    if (selectedOperator.requisites?.length > 1 && !selectedRequisite) {
      toast.error("Выберите способ оплаты");
      return;
    }
    
    const requisiteToUse = selectedRequisite || selectedOperator.requisites?.[0];
    if (!requisiteToUse) {
      toast.error("Нет доступных реквизитов");
      return;
    }
    
    setCreating(true);
    
    try {
      let res;
      if (selectedOperator.is_qr_aggregator) {
        // QR aggregator trade - use dedicated endpoint
        res = await axios.post(`${API}/qr-aggregator/buy-public`, {
          amount_usdt: invoice.amount_usdt,
          method: selectedOperator.qr_method || "qr",
          payment_link_id: invoiceId
        });
        
        // QR trade created - link to invoice and redirect to payment URL
        const tradeId = res.data.id || res.data.trade_id;
        await axios.patch(`${API}/v1/invoice/${invoiceId}/link-trade`, { trade_id: tradeId }).catch(() => {});
        
        if (res.data.payment_url) {
          // TrustGain payment - redirect to their payment page
          window.location.href = res.data.payment_url;
          return;
        }
        
        // Fallback: load trade and show payment step
        const tradeRes = await axios.get(`${API}/trades/${tradeId}/public`);
        setTrade(tradeRes.data);
        setShowOperatorDialog(false);
        setStep("payment");
        setCreating(false);
        return;
      } else {
        // Regular trader trade
        res = await axios.post(`${API}/trades`, {
          amount_usdt: invoice.amount_usdt,
          price_rub: selectedOperator.price_rub,
          trader_id: selectedOperator.trader_id,
          payment_link_id: invoiceId,
          offer_id: selectedOperator.offer_id,
          requisite_ids: [requisiteToUse.id],
          buyer_type: "client"
        });
      }
      
      // Сохраняем выбранный реквизит локально
      setSavedRequisite(requisiteToUse);
      
      // Загружаем полные данные trade
      const tradeRes = await axios.get(`${API}/trades/${res.data.id}/public`);
      setTrade(tradeRes.data);
      
      // Если в trade нет реквизитов - используем сохранённый
      if (!tradeRes.data.requisites?.length) {
        setTrade({ ...tradeRes.data, requisites: [requisiteToUse] });
      }
      
      await axios.patch(`${API}/v1/invoice/${invoiceId}/link-trade`, { trade_id: res.data.id }).catch(() => {});
      setShowOperatorDialog(false);
      setStep("payment");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Ошибка создания сделки");
    } finally { setCreating(false); }
  };

  const markPaid = async () => {
    try {
      await axios.post(`${API}/trades/${trade.id}/mark-paid`);
      setTrade({ ...trade, status: "paid", paid_at: new Date().toISOString() });
      
      // Генерируем ссылку на чат для покупателя
      const link = `${window.location.origin}/dispute/${trade.id}?buyer=true`;
      setChatLink(link);
      
      setStep("waiting");
      toast.success("Ожидайте подтверждения оператора");
    } catch (e) { toast.error("Ошибка"); }
  };

  const openDispute = async () => {
    if (!canDispute) { 
      toast.error("Спор доступен через 10 минут после нажатия 'Я оплатил'"); 
      return; 
    }
    try {
      await axios.post(`${API}/trades/${trade.id}/dispute-public`, null, { 
        params: { reason: "Оплата не подтверждена оператором" } 
      });
      
      // Постоянная ссылка на спор - работает пока не решится
      const link = `${window.location.origin}/dispute/${trade.id}?buyer=true`;
      setDisputeLink(link);
      navigator.clipboard.writeText(link).catch(() => {});
      toast.success("Спор открыт! Ссылка скопирована в буфер обмена.");
      setStep("disputed");
    } catch (e) { 
      toast.error(e.response?.data?.detail || "Ошибка открытия спора"); 
    }
  };

  const cancelTrade = async () => {
    if (!confirm("Отменить платёж?")) return;
    try {
      await axios.post(`${API}/trades/${trade.id}/cancel-client`);
      toast.success("Сделка отменена");
      setStep("select_operator");
      setTrade(null);
      setSavedRequisite(null);
      loadData();
    } catch (e) { toast.error(e.response?.data?.detail || "Ошибка"); }
  };

  const sendMsg = async () => {
    if (!newMessage.trim() || !trade) return;
    try {
      await axios.post(`${API}/trades/${trade.id}/messages-public`, { content: newMessage });
      setNewMessage("");
      fetchMessages();
    } catch (e) { toast.error("Ошибка отправки"); }
  };

  const copy = (t) => { 
    navigator.clipboard.writeText(t); 
    toast.success("Скопировано"); 
  };
  
  const fmtTime = (s) => `${Math.floor(s/60)}:${(s%60).toString().padStart(2,"0")}`;

  // Получаем реквизит для отображения
  const getDisplayRequisite = () => {
    return trade?.requisites?.[0] || savedRequisite || null;
  };

  // ========== LOADING ==========
  if (loading || step === "loading") return (
    <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
      <div className="text-center">
        <Loader2 className="w-10 h-10 text-[#7C3AED] animate-spin mx-auto mb-3" />
        <p className="text-[#71717A] text-sm">Загрузка...</p>
      </div>
    </div>
  );

  // ========== ERROR ==========
  if (step === "error") return (
    <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center p-4">
      <div className="text-center max-w-sm">
        <div className="w-16 h-16 rounded-2xl bg-[#F59E0B]/10 flex items-center justify-center mx-auto mb-4">
          <AlertTriangle className="w-8 h-8 text-[#F59E0B]" />
        </div>
        <h1 className="text-xl font-bold text-white mb-2">Платёж недоступен</h1>
        <p className="text-[#71717A] text-sm">Ссылка истекла или платёж уже обработан</p>
      </div>
    </div>
  );

  // ========== SELECT OPERATOR (КАК В СТАКАНЕ) ==========
  if (step === "select_operator") {
    const bestPrice = filteredOperators[0]?.toPayRub || depositAmount;
    
    return (
      <div className="min-h-screen bg-[#0A0A0A]">
        {/* Header */}
        <div className="sticky top-0 z-10 bg-[#0A0A0A]/95 backdrop-blur-xl border-b border-white/5">
          <div className="px-4 py-4 max-w-4xl mx-auto">
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="text-[#71717A] text-xs mb-1">Пополнение счёта</div>
                <div className="text-2xl font-bold text-white font-['JetBrains_Mono']">
                  {Math.round(depositAmount).toLocaleString()} ₽
                </div>
              </div>
              <div className="w-12 h-12 rounded-2xl bg-[#7C3AED]/10 flex items-center justify-center">
                <Wallet className="w-6 h-6 text-[#7C3AED]" />
              </div>
            </div>
            
            {/* Фильтр по способу оплаты - раскрывающийся */}
            <div className="relative">
              <button
                onClick={() => setShowMethodsDropdown(!showMethodsDropdown)}
                className="flex items-center justify-between gap-3 px-4 py-3 bg-[#121212] border border-white/10 rounded-xl hover:border-white/20 transition-colors min-w-[200px]"
              >
                <span className="text-white">
                  {selectedFilter === "all" ? "Все методы" : getPaymentMethod(selectedFilter).name}
                </span>
                <ChevronDown className={`w-4 h-4 text-[#71717A] transition-transform ${showMethodsDropdown ? 'rotate-180' : ''}`} />
              </button>
              
              {/* Dropdown с методами */}
              {showMethodsDropdown && (
                <div className="absolute top-full left-0 mt-2 bg-[#1A1A1A] border border-white/10 rounded-xl overflow-hidden z-20 shadow-xl min-w-[200px]">
                  <button
                    onClick={() => { setSelectedFilter("all"); setShowMethodsDropdown(false); }}
                    className={`w-full flex items-center justify-between gap-3 px-4 py-3 hover:bg-white/5 transition-colors ${
                      selectedFilter === "all" ? "text-white" : "text-[#A1A1AA]"
                    }`}
                  >
                    <span>Все методы</span>
                    {selectedFilter === "all" && <Check className="w-4 h-4 text-white" />}
                  </button>
                  {availableMethods.map(methodType => {
                    const info = getPaymentMethod(methodType);
                    const isSelected = selectedFilter === methodType;
                    return (
                      <button
                        key={methodType}
                        onClick={() => { setSelectedFilter(methodType); setShowMethodsDropdown(false); }}
                        className={`w-full flex items-center gap-3 px-4 py-3 transition-colors ${
                          isSelected 
                            ? "bg-[#7C3AED] text-white" 
                            : "text-[#A1A1AA] hover:bg-white/5"
                        }`}
                      >
                        <span className="text-lg">{info.emoji}</span>
                        <span className="flex-1 text-left">{info.name}</span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="px-4 py-4 max-w-4xl mx-auto">
          {/* Количество операторов */}
          <div className="flex items-center justify-between mb-4">
            <span className="text-[#71717A] text-sm">
              {filteredOperators.length} {filteredOperators.length === 1 ? 'оператор' : 'операторов'}
            </span>
            <span className="text-xs text-[#52525B]">Сортировка: лучшая цена</span>
          </div>
          
          {/* Заголовок таблицы */}
          <div className="hidden md:grid grid-cols-12 gap-4 px-4 py-2 text-xs text-[#52525B] uppercase tracking-wider mb-2">
            <div className="col-span-3">Оператор</div>
            <div className="col-span-2">Комиссия</div>
            <div className="col-span-3">Способы оплаты</div>
            <div className="col-span-2">Сделок</div>
            <div className="col-span-2 text-right">К оплате</div>
          </div>

          {filteredOperators.length === 0 ? (
            <div className="bg-[#121212] rounded-2xl p-8 text-center border border-white/5">
              <AlertTriangle className="w-12 h-12 text-[#F59E0B] mx-auto mb-3" />
              <h2 className="text-lg font-semibold text-white mb-2">Нет доступных операторов</h2>
              <p className="text-[#71717A] text-sm mb-4">
                {selectedFilter !== "all" ? "Попробуйте другой способ оплаты" : "Попробуйте позже"}
              </p>
              {selectedFilter !== "all" && (
                <Button onClick={() => setSelectedFilter("all")} variant="outline" size="sm" className="border-white/10 text-white">
                  Показать все
                </Button>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              {filteredOperators.map((op, index) => {
                const isBest = op.toPayRub === bestPrice;
                const diff = op.toPayRub - bestPrice;
                const uniqueTypes = [...new Set(op.requisites?.map(r => r.type) || [])];
                
                return (
                  <div 
                    key={op.offer_id} 
                    onClick={() => openOperatorDialog(op)}
                    className={`bg-[#121212] border hover:bg-[#1A1A1A] rounded-xl p-4 cursor-pointer transition-all ${
                      isBest ? "border-[#10B981]/30" : "border-white/5 hover:border-[#7C3AED]/30"
                    }`}
                  >
                    <div className="grid md:grid-cols-12 gap-4 items-center">
                      {/* Оператор */}
                      <div className="md:col-span-3 flex items-center gap-3">
                        <div className="relative">
                          <div className="w-10 h-10 rounded-full bg-[#1A1A1A] flex items-center justify-center">
                            <User className="w-5 h-5 text-[#52525B]" />
                          </div>
                          <div className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-[#121212] ${
                            op.is_online ? 'bg-[#10B981]' : 'bg-[#52525B]'
                          }`} />
                        </div>
                        <div>
                          <div className="text-white font-medium text-sm flex items-center gap-2">
                            {op.nickname || op.trader_login}
                            {isBest && (
                              <span className="px-2 py-0.5 bg-[#10B981]/10 text-[#10B981] text-xs rounded-full font-medium">
                                Лучшая цена
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-1 text-xs text-[#52525B]">
                            <CheckCircle className="w-3 h-3 text-[#10B981]" />
                            {op.success_rate || 100}%
                          </div>
                        </div>
                      </div>

                      {/* Комиссия */}
                      <div className="md:col-span-2">
                        <div className={`text-sm font-medium ${
                          op.commissionPercent <= 0 ? 'text-[#10B981]' : 
                          op.commissionPercent < 1 ? 'text-[#F59E0B]' : 'text-[#71717A]'
                        }`}>
                          {op.commissionPercent > 0 ? `+${op.commissionPercent}%` : `${op.commissionPercent}%`}
                        </div>
                        <div className="text-xs text-[#52525B]">комиссия</div>
                      </div>

                      {/* Способы оплаты */}
                      <div className="md:col-span-3">
                        <div className="flex flex-wrap gap-1">
                          {uniqueTypes.map((type, idx) => {
                            const Icon = getRequisiteIcon(type);
                            return (
                              <span 
                                key={idx} 
                                className="inline-flex items-center gap-1 px-2 py-1 bg-[#1A1A1A] text-[#A1A1AA] text-xs rounded"
                              >
                                <Icon className="w-3 h-3" />
                                {getRequisiteLabel(type)}
                              </span>
                            );
                          })}
                        </div>
                      </div>

                      {/* Сделок */}
                      <div className="md:col-span-2">
                        <div className="text-white text-sm">{op.trades_count || 0}</div>
                        <div className="text-xs text-[#52525B]">сделок</div>
                      </div>

                      {/* К оплате */}
                      <div className="md:col-span-2 text-right">
                        <div className="text-xl font-bold text-white font-['JetBrains_Mono']">
                          {Math.round(op.toPayRub).toLocaleString()} ₽
                        </div>
                        {diff > 0 && (
                          <div className="text-xs text-[#52525B]">
                            +{Math.round(diff).toLocaleString()} ₽
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          
          <p className="text-center text-[#52525B] text-xs mt-6 flex items-center justify-center gap-2">
            <Shield className="w-4 h-4" /> Безопасная оплата
          </p>
        </div>

        {/* Диалог выбора оператора */}
        <Dialog open={showOperatorDialog} onOpenChange={setShowOperatorDialog}>
          <DialogContent className="bg-[#121212] border-white/10 text-white max-w-md">
            <DialogHeader>
              <DialogTitle className="text-white">Оплата через {selectedOperator?.nickname || 'оператора'}</DialogTitle>
            </DialogHeader>
            
            <div className="space-y-4">
              {/* Сумма */}
              <div className="bg-[#0A0A0A] rounded-xl p-4">
                <div className="flex justify-between items-center">
                  <span className="text-[#71717A]">Сумма пополнения</span>
                  <span className="text-white font-medium">{Math.round(depositAmount).toLocaleString()} ₽</span>
                </div>
                <div className="flex justify-between items-center mt-2">
                  <span className="text-[#71717A]">К оплате</span>
                  <span className="text-xl font-bold text-white">{Math.round(selectedOperator?.toPayRub || 0).toLocaleString()} ₽</span>
                </div>
                {selectedOperator?.commissionPercent !== 0 && (
                  <div className="flex justify-between items-center mt-1">
                    <span className="text-[#52525B] text-sm">Комиссия оператора</span>
                    <span className={`text-sm ${selectedOperator?.commissionPercent > 0 ? 'text-[#F59E0B]' : 'text-[#10B981]'}`}>
                      {selectedOperator?.commissionPercent > 0 ? '+' : ''}{selectedOperator?.commissionPercent}%
                    </span>
                  </div>
                )}
              </div>
              
              {/* Выбор реквизита (если несколько) */}
              {selectedOperator?.requisites?.length > 1 && (
                <div>
                  <div className="text-sm text-[#71717A] mb-2">Выберите способ оплаты:</div>
                  <div className="space-y-2">
                    {selectedOperator.requisites.map((req) => {
                      const Icon = getRequisiteIcon(req.type);
                      const isSelected = selectedRequisite?.id === req.id;
                      return (
                        <button
                          key={req.id}
                          onClick={() => setSelectedRequisite(req)}
                          className={`w-full flex items-center gap-3 p-3 rounded-xl border transition-colors ${
                            isSelected 
                              ? 'bg-[#7C3AED]/10 border-[#7C3AED]' 
                              : 'bg-[#0A0A0A] border-white/5 hover:border-white/20'
                          }`}
                        >
                          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                            isSelected ? 'bg-[#7C3AED]/20' : 'bg-white/5'
                          }`}>
                            <Icon className={`w-5 h-5 ${isSelected ? 'text-[#7C3AED]' : 'text-[#71717A]'}`} />
                          </div>
                          <div className="text-left">
                            <div className="text-white font-medium">{req.data?.bank_name || getRequisiteLabel(req.type)}</div>
                            <div className="text-xs text-[#52525B]">{getRequisiteLabel(req.type)}</div>
                          </div>
                          {isSelected && (
                            <Check className="w-5 h-5 text-[#7C3AED] ml-auto" />
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
              
              {/* Условия оператора */}
              {selectedOperator?.conditions && (
                <div className="bg-[#F59E0B]/10 border border-[#F59E0B]/20 rounded-xl p-3">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 text-[#F59E0B] mt-0.5 flex-shrink-0" />
                    <div>
                      <div className="text-[#F59E0B] text-sm font-medium mb-1">Условия оператора</div>
                      <div className="text-[#A1A1AA] text-sm">{selectedOperator.conditions}</div>
                    </div>
                  </div>
                </div>
              )}
              
              {/* Правила */}
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={rulesAccepted}
                  onChange={(e) => setRulesAccepted(e.target.checked)}
                  className="mt-1 w-4 h-4 rounded border-white/20 bg-transparent checked:bg-[#7C3AED] checked:border-[#7C3AED]"
                />
                <span className="text-sm text-[#71717A]">
                  Я принимаю правила сервиса и обязуюсь совершить перевод точной суммы без комментария
                </span>
              </label>
              
              {/* Кнопка */}
              <Button
                onClick={startTrade}
                disabled={creating || !rulesAccepted || (selectedOperator?.requisites?.length > 1 && !selectedRequisite)}
                className="w-full h-12 bg-[#10B981] hover:bg-[#059669] text-white rounded-xl"
               title="Перейти к оплате заказа">
                {creating ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <>Перейти к оплате</>
                )}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    );
  }

  // ========== PAYMENT (с чатом) ==========
  if (step === "payment" && trade) {
    const requisite = getDisplayRequisite();
    const ReqIcon = requisite ? getRequisiteIcon(requisite.type) : CreditCard;
    
    // Если реквизиты ещё не загрузились — показываем только спиннер и кнопку назад
    if (!requisite) {
      return (
        <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center p-4">
          <div className="text-center">
            <Loader2 className="w-12 h-12 text-[#7C3AED] animate-spin mx-auto mb-4" />
            <p className="text-[#A1A1AA] text-lg mb-6">Реквизиты загружаются...</p>
            <Button 
              variant="outline" 
              onClick={() => { setStep("select_operator"); setTrade(null); setSavedRequisite(null); loadData(); }}
              className="border-white/10 text-[#A1A1AA] hover:bg-white/5"
              title="Вернуться к выбору оператора"
            >
              Назад
            </Button>
          </div>
        </div>
      );
    }
    
    return (
      <div className="min-h-screen bg-[#0A0A0A]">
        <div className="max-w-4xl mx-auto p-4">
          <div className="grid md:grid-cols-2 gap-4">
            {/* Левая колонка - реквизиты */}
            <div className="space-y-4">
              {/* Таймер */}
              <div className="bg-[#121212] rounded-2xl p-4 border border-white/5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-[#F59E0B]/10 flex items-center justify-center">
                      <Clock className="w-5 h-5 text-[#F59E0B]" />
                    </div>
                    <div>
                      <div className="text-[#71717A] text-xs">Осталось времени</div>
                      <div className="text-white font-bold font-['JetBrains_Mono'] text-xl">{fmtTime(timeLeft || 0)}</div>
                    </div>
                  </div>
                  <Button variant="ghost" onClick={cancelTrade} className="text-[#EF4444] hover:text-[#EF4444] hover:bg-[#EF4444]/10" title="Отменить сделку">
                    Отменить
                  </Button>
                </div>
              </div>

              {/* Реквизиты */}
              <div className="bg-[#121212] rounded-2xl p-6 border border-white/5">
                <h2 className="text-lg font-semibold text-white mb-4">Переведите на реквизиты</h2>
                
                {/* Сумма к оплате */}
                <div className="bg-[#0A0A0A] rounded-xl p-4 mb-4">
                  <div className="text-[#71717A] text-xs mb-1">Сумма к оплате</div>
                  <div className="flex items-center justify-between">
                    <div className="text-2xl font-bold text-white font-['JetBrains_Mono']">
                      {Math.round(trade.amount_rub || 0).toLocaleString()} ₽
                    </div>
                    <Button variant="ghost" size="sm" onClick={() => copy(Math.round(trade.amount_rub || 0).toString())} className="text-[#7C3AED]">
                      <Copy className="w-4 h-4" />
                    </Button>
                  </div>
                  <div className="text-[#F59E0B] text-xs mt-1 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    Переведите точную сумму без комментария!
                  </div>
                </div>
                
                {/* Реквизиты */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-[#A1A1AA] text-sm">
                    <ReqIcon className="w-4 h-4" />
                    <span className="font-medium">{requisite.data?.bank_name || getRequisiteLabel(requisite.type)}</span>
                  </div>
                  
                  {requisite.data?.card_number && (
                    <div className="bg-[#0A0A0A] rounded-xl p-4">
                      <div className="text-[#71717A] text-xs mb-1">Номер карты</div>
                      <div className="flex items-center justify-between">
                        <div className="text-white font-mono text-lg tracking-wider">{requisite.data.card_number}</div>
                        <Button variant="ghost" size="sm" onClick={() => copy(requisite.data.card_number.replace(/\s/g, ''))} className="text-[#7C3AED]">
                          <Copy className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  )}
                  
                  {requisite.data?.phone && (
                    <div className="bg-[#0A0A0A] rounded-xl p-4">
                      <div className="text-[#71717A] text-xs mb-1">Номер телефона (СБП)</div>
                      <div className="flex items-center justify-between">
                        <div className="text-white font-mono text-lg">{requisite.data.phone}</div>
                        <Button variant="ghost" size="sm" onClick={() => copy(requisite.data.phone.replace(/\D/g, ''))} className="text-[#7C3AED]">
                          <Copy className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  )}
                  
                  {requisite.data?.card_holder && (
                    <div className="bg-[#0A0A0A] rounded-xl p-4">
                      <div className="text-[#71717A] text-xs mb-1">Получатель</div>
                      <div className="text-white">{requisite.data.card_holder}</div>
                    </div>
                  )}
                </div>

                {/* Кнопка оплаты */}
                <Button onClick={markPaid} className="w-full h-14 bg-[#10B981] hover:bg-[#059669] text-white text-lg rounded-xl mt-4" title="Подтвердить что оплата отправлена">
                  <Check className="w-6 h-6 mr-2" /> Я оплатил
                </Button>
              </div>
            </div>

            {/* Правая колонка - чат */}
            <div className="bg-[#121212] rounded-2xl border border-white/5 flex flex-col h-[500px]">
              <div className="p-4 border-b border-white/5">
                <h3 className="text-white font-semibold flex items-center gap-2">
                  <MessageCircle className="w-4 h-4" />
                  Чат с оператором
                </h3>
                <p className="text-[#52525B] text-xs mt-1">Оператор: {trade.trader_login || 'Загрузка...'}</p>
              </div>
              
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {messages.length === 0 ? (
                  <div className="text-center text-[#52525B] text-sm py-8">
                    <MessageCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    Начните диалог с оператором
                  </div>
                ) : (
                  messages.map((msg, i) => (
                    <div key={i} className={`flex ${msg.sender_type === 'client' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[80%] px-4 py-2 rounded-2xl ${
                        msg.sender_type === 'client' 
                          ? 'bg-[#7C3AED] text-white rounded-br-sm' 
                          : 'bg-white/5 text-[#E4E4E7] rounded-bl-sm'
                      }`}>
                        <p className="text-sm">{msg.content}</p>
                        <p className="text-[10px] opacity-50 mt-1">
                          {new Date(msg.created_at).toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit' })}
                        </p>
                      </div>
                    </div>
                  ))
                )}
                <div ref={messagesEndRef} />
              </div>
              
              <div className="p-4 border-t border-white/5">
                <div className="flex gap-2">
                  <Input
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && sendMsg()}
                    placeholder="Написать сообщение..."
                    className="bg-[#0A0A0A] border-white/10 text-white placeholder:text-[#52525B]"
                  />
                  <Button onClick={sendMsg} className="bg-[#7C3AED] hover:bg-[#6D28D9]">
                    <Send className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ========== WAITING (с чатом и спором) ==========
  if (step === "waiting" && trade) {
    // Ссылка на чат/спор для покупателя
    const buyerLink = chatLink || `${window.location.origin}/dispute/${trade.id}?buyer=true`;
    
    return (
      <div className="min-h-screen bg-[#0A0A0A]">
        <div className="max-w-4xl mx-auto p-4">
          <div className="grid md:grid-cols-2 gap-4">
            {/* Левая колонка - статус */}
            <div className="space-y-4">
              <div className="bg-[#121212] rounded-2xl p-6 border border-white/5">
                <div className="flex items-center justify-center mb-4">
                  <div className="w-16 h-16 rounded-2xl bg-[#3B82F6]/10 flex items-center justify-center">
                    <Loader2 className="w-8 h-8 text-[#3B82F6] animate-spin" />
                  </div>
                </div>
                <h2 className="text-xl font-bold text-white text-center mb-2">Ожидаем подтверждения</h2>
                <p className="text-[#71717A] text-center mb-4">Оператор проверяет ваш платёж</p>
                
                {/* Детали сделки */}
                <div className="bg-[#0A0A0A] rounded-xl p-4 mb-4">
                  <div className="flex justify-between text-sm mb-2">
                    <span className="text-[#71717A]">ID сделки</span>
                    <span className="text-white font-mono text-xs">{trade.id}</span>
                  </div>
                  <div className="flex justify-between text-sm mb-2">
                    <span className="text-[#71717A]">Сумма</span>
                    <span className="text-white font-medium">{Math.round(trade.amount_rub || 0).toLocaleString()} ₽</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-[#71717A]">Оператор</span>
                    <span className="text-white">{trade.trader_login}</span>
                  </div>
                </div>
                
                {/* Кнопка спора */}
                {canDispute ? (
                  <Button onClick={openDispute} variant="outline" className="w-full border-[#EF4444] text-[#EF4444] hover:bg-[#EF4444]/10" title="Открыть спор по сделке">
                    <AlertTriangle className="w-4 h-4 mr-2" />
                    Открыть спор
                  </Button>
                ) : (
                  <div className="bg-[#0A0A0A] rounded-xl p-3 text-center">
                    <div className="text-[#52525B] text-sm mb-1">Спор доступен через</div>
                    <div className="text-white font-bold font-['JetBrains_Mono'] text-lg">
                      {disputeCountdown !== null ? fmtTime(disputeCountdown) : '10:00'}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Правая колонка - чат */}
            <div className="bg-[#121212] rounded-2xl border border-white/5 flex flex-col h-[500px]">
              <div className="p-4 border-b border-white/5">
                <h3 className="text-white font-semibold flex items-center gap-2">
                  <MessageCircle className="w-4 h-4" />
                  Чат с оператором
                </h3>
              </div>
              
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {messages.length === 0 ? (
                  <div className="text-center text-[#52525B] text-sm py-8">
                    <MessageCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    Напишите оператору если есть вопросы
                  </div>
                ) : (
                  messages.map((msg, i) => (
                    <div key={i} className={`flex ${msg.sender_type === 'client' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[80%] px-4 py-2 rounded-2xl ${
                        msg.sender_type === 'client' 
                          ? 'bg-[#7C3AED] text-white rounded-br-sm' 
                          : 'bg-white/5 text-[#E4E4E7] rounded-bl-sm'
                      }`}>
                        <p className="text-sm">{msg.content}</p>
                        <p className="text-[10px] opacity-50 mt-1">
                          {new Date(msg.created_at).toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit' })}
                        </p>
                      </div>
                    </div>
                  ))
                )}
                <div ref={messagesEndRef} />
              </div>
              
              <div className="p-4 border-t border-white/5">
                <div className="flex gap-2">
                  <Input
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && sendMsg()}
                    placeholder="Написать сообщение..."
                    className="bg-[#0A0A0A] border-white/10 text-white placeholder:text-[#52525B]"
                  />
                  <Button onClick={sendMsg} className="bg-[#7C3AED] hover:bg-[#6D28D9]">
                    <Send className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ========== COMPLETED ==========
  if (step === "completed") return (
    <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center p-4">
      <div className="text-center max-w-sm">
        <div className="w-20 h-20 rounded-full bg-[#10B981]/10 flex items-center justify-center mx-auto mb-6">
          <CheckCircle className="w-10 h-10 text-[#10B981]" />
        </div>
        <h1 className="text-2xl font-bold text-white mb-2">Платёж успешен!</h1>
        <p className="text-[#71717A]">Средства зачислены на ваш счёт</p>
        
        {trade && (
          <div className="bg-[#121212] rounded-xl p-4 mt-6 text-left">
            <div className="flex justify-between text-sm mb-2">
              <span className="text-[#71717A]">Сумма</span>
              <span className="text-white font-medium">{Math.round(trade.amount_rub || 0).toLocaleString()} ₽</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-[#71717A]">ID сделки</span>
              <span className="text-white font-mono text-xs">{trade.id}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );

  // ========== DISPUTED ==========
  if (step === "disputed") {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center p-4">
        <div className="text-center max-w-md w-full">
          <div className="w-20 h-20 rounded-full bg-[#F59E0B]/10 flex items-center justify-center mx-auto mb-6">
            <AlertTriangle className="w-10 h-10 text-[#F59E0B]" />
          </div>
          <h1 className="text-2xl font-bold text-white mb-2">Спор открыт</h1>
          <p className="text-[#71717A]">Модератор рассмотрит вашу ситуацию</p>
        </div>
      </div>
    );
  }

  return null;
}
