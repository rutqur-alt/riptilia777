import React, { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { toast } from 'sonner';
import { API } from '@/App';
import axios from 'axios';
import {
  Wallet, Settings, Store, CreditCard, Smartphone, QrCode, Phone,
  CheckCircle, Copy, AlertTriangle, Shield, MessageCircle, Timer,
  RefreshCw, Send, Loader2, Check, User, ChevronDown, Clock,
  ArrowRight, Eye, EyeOff, Save, Plug, History, X, ExternalLink
} from 'lucide-react';
import { PAYMENT_METHODS, getPaymentMethod, PAYMENT_METHOD_OPTIONS } from '@/config/paymentMethods';

const getRequisiteIcon = (type) => {
  switch (type) {
    case "card": return CreditCard;
    case "sbp": return Smartphone;
    case "sim": return Phone;
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

const fmtTime = (s) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`;

export default function BuyerShop() {
  // === API Connection ===
  const [apiKey, setApiKey] = useState(() => localStorage.getItem('shop_api_key') || '');
  const [apiSecret, setApiSecret] = useState(() => localStorage.getItem('shop_api_secret') || '');
  const [merchantId, setMerchantId] = useState(() => localStorage.getItem('shop_merchant_id') || '');
  const [merchantName, setMerchantName] = useState(() => localStorage.getItem('shop_merchant_name') || '');
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showSecret, setShowSecret] = useState(false);

  // === Balance ===
  const [balance, setBalance] = useState(null);
  const [loadingBalance, setLoadingBalance] = useState(false);

  // === Top-up flow ===
  const [amount, setAmount] = useState('');
  const [topUpLoading, setTopUpLoading] = useState(false);
  const [activeInvoice, setActiveInvoice] = useState(null);

  // === Operator selection (stak) ===
  const [step, setStep] = useState('idle'); // idle, select_operator, payment, waiting, completed, disputed
  const [operators, setOperators] = useState([]);
  const [filteredOperators, setFilteredOperators] = useState([]);
  const [selectedFilter, setSelectedFilter] = useState('all');
  const [availableMethods, setAvailableMethods] = useState([]);
  const [showMethodsDropdown, setShowMethodsDropdown] = useState(false);
  const [selectedOperator, setSelectedOperator] = useState(null);
  const [selectedRequisite, setSelectedRequisite] = useState(null);
  const [showOperatorDialog, setShowOperatorDialog] = useState(false);
  const [rulesAccepted, setRulesAccepted] = useState(false);
  const [creating, setCreating] = useState(false);
  const [depositAmount, setDepositAmount] = useState(0);

  // === Trade ===
  const [trade, setTrade] = useState(null);
  const [savedRequisite, setSavedRequisite] = useState(null);
  const [timeLeft, setTimeLeft] = useState(null);
  const [canDispute, setCanDispute] = useState(false);
  const [disputeCountdown, setDisputeCountdown] = useState(null);

  // === Chat ===
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const messagesEndRef = useRef(null);

  // === History ===
  const [transactions, setTransactions] = useState([]);
  const [showHistory, setShowHistory] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  
  // === Active Payments ===
  const [activePayments, setActivePayments] = useState([]);
  const [loadingActive, setLoadingActive] = useState(false);

  // ========== Auto-connect on mount ==========
  useEffect(() => {
    if (apiKey && !connected) {
      connectApi(true);
    }
  }, []);

  // ========== Timer for pending trade ==========
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

  // ========== Dispute countdown ==========
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
          setDisputeCountdown(Math.max(0, Math.ceil((10 - minutesPassed) * 60)));
        }
      };
      updateDispute();
      const i = setInterval(updateDispute, 1000);
      return () => clearInterval(i);
    }
  }, [trade]);

  // ========== Fetch messages ==========
  useEffect(() => {
    if (trade && !["completed", "cancelled"].includes(trade.status)) {
      fetchMessages();
      const i = setInterval(fetchMessages, 3000);
      return () => clearInterval(i);
    }
  }, [trade]);

  // ========== Poll trade status ==========
  useEffect(() => {
    if (trade && !["completed", "cancelled"].includes(trade.status)) {
      const poll = setInterval(async () => {
        try {
          const res = await axios.get(`${API}/trades/${trade.id}/public`);
          if (res.data.status !== trade.status) {
            setTrade(res.data);
            if (res.data.status === "completed") {
              setStep("completed");
              toast.success("Оплата зачислена!");
              loadBalance();
            } else if (res.data.status === "disputed") {
              setStep("disputed");
            }
          }
        } catch (e) { }
      }, 5000);
      return () => clearInterval(poll);
    }
  }, [trade]);

  // ========== Scroll messages ==========
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ========== Filter operators ==========
  useEffect(() => {
    if (selectedFilter === "all") {
      setFilteredOperators(operators);
    } else {
      setFilteredOperators(operators.filter(op =>
        op.requisites?.some(r => r.type === selectedFilter)
      ));
    }
  }, [selectedFilter, operators]);

  // ========== API FUNCTIONS ==========

  const connectApi = async (silent = false) => {
    if (!apiKey) {
      if (!silent) toast.error('Введите API ключ');
      return;
    }
    setConnecting(true);
    try {
      const res = await axios.get(`${API}/shop/merchant-info/${apiKey}`);
      if (res.data) {
        const mid = res.data.merchant_id || res.data.id || '';
        const mname = res.data.company_name || res.data.name || res.data.shop_name || 'Магазин';
        setMerchantId(mid);
        setMerchantName(mname);
        setBalance({ balance_usdt: res.data.balance_usdt || 0, total_received: res.data.total_received || 0, total_transactions: res.data.total_transactions || 0 });
        setConnected(true);
        localStorage.setItem('shop_api_key', apiKey);
        localStorage.setItem('shop_api_secret', apiSecret);
        localStorage.setItem('shop_merchant_id', mid);
        localStorage.setItem('shop_merchant_name', mname);
        if (!silent) toast.success('Подключено!');
        loadBalance();
        loadActivePayments(apiKey);  // Передаём apiKey напрямую
      }
    } catch (e) {
      if (!silent) toast.error('Неверный API ключ');
      setConnected(false);
    } finally {
      setConnecting(false);
    }
  };

  const loadBalance = async () => {
    if (!apiKey) return;
    setLoadingBalance(true);
    try {
      const res = await axios.get(`${API}/shop/merchant-info/${apiKey}`);
      if (res.data) {
        setBalance({
          balance_usdt: res.data.balance_usdt || 0,
          total_received: res.data.total_received || 0,
          total_received_rub: res.data.total_received_rub || 0,
          total_transactions: res.data.total_transactions || 0
        });
      }
    } catch (e) { }
    finally { setLoadingBalance(false); }
  };

  const loadTransactions = async () => {
    if (!apiKey || !merchantId) return;
    setLoadingHistory(true);
    try {
      const res = await axios.get(`${API}/v1/invoice/transactions`, {
        params: { merchant_id: merchantId, limit: 20 },
        headers: { 'X-Api-Key': apiKey }
      });
      // API returns { status, data: { transactions: [...] } }
      const txs = res.data?.data?.transactions || res.data?.transactions || [];
      setTransactions(Array.isArray(txs) ? txs : []);
    } catch (e) { 
      console.error('Load transactions error:', e);
      setTransactions([]);
    }
    finally { setLoadingHistory(false); }
  };

  // Загрузка активных заявок (pending, waiting_requisites)
  const loadActivePayments = async (key = null) => {
    const useKey = key || apiKey;
    if (!useKey) return;
    setLoadingActive(true);
    try {
      const res = await axios.get(`${API}/v1/invoice/transactions`, {
        params: { status: 'active', limit: 10 },
        headers: { 'X-Api-Key': useKey }
      });
      const txs = res.data?.data?.transactions || [];
      setActivePayments(Array.isArray(txs) ? txs : []);
    } catch (e) {
      console.error('Load active payments error:', e);
      setActivePayments([]);
    }
    finally { setLoadingActive(false); }
  };

  const createTopUp = async () => {
    const numAmount = parseInt(amount);
    if (!numAmount || numAmount < 100) {
      toast.error('Минимальная сумма 100 рублей');
      return;
    }

    setTopUpLoading(true);
    try {
      // Use the quick-payment endpoint for simplicity
      const res = await axios.post(`${API}/shop/quick-payment`, {
        amount_rub: numAmount,
        description: `Пополнение на ${numAmount.toLocaleString()} руб.`
      });

      if (res.data.invoice_id) {
        setActiveInvoice(res.data);
        setDepositAmount(numAmount);
        // Load operators for this invoice
        await loadOperators(res.data.invoice_id, numAmount);
      }
    } catch (e) {
      toast.error('Ошибка создания платежа');
    } finally {
      setTopUpLoading(false);
    }
  };

  const loadOperators = async (invoiceId, amountRub) => {
    try {
      const invRes = await axios.get(`${API}/shop/pay/${invoiceId}`);
      const inv = invRes.data.order;

      const params = new URLSearchParams();
      if (amountRub) params.set("amount_rub", amountRub);

      const opRes = await axios.get(`${API}/public/operators?${params}`);
      const ops = opRes.data.operators || [];

      const allMethods = Object.keys(PAYMENT_METHODS);
      setAvailableMethods(allMethods);

      const exchangeRate = opRes.data.exchange_rate || 78;
      const operatorsWithPrice = ops.map(op => {
        let toPayRub = op.amount_to_pay_rub || Math.round((amountRub / exchangeRate) * op.price_rub);
        if (amountRub > 0) toPayRub = Math.max(toPayRub, amountRub);
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
      setStep('select_operator');
    } catch (e) {
      toast.error('Ошибка загрузки операторов');
    }
  };

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

  const startTrade = async () => {
    if (!selectedOperator || !activeInvoice) return;
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
      const invRes = await axios.get(`${API}/shop/pay/${activeInvoice.invoice_id}`);
      const inv = invRes.data.order;

      const res = await axios.post(`${API}/trades`, {
        amount_usdt: inv.amount_usdt,
        price_rub: selectedOperator.price_rub,
        trader_id: selectedOperator.trader_id,
        payment_link_id: activeInvoice.invoice_id,
        offer_id: selectedOperator.offer_id,
        requisite_ids: [requisiteToUse.id],
        buyer_type: "client"
      });

      setSavedRequisite(requisiteToUse);

      const tradeRes = await axios.get(`${API}/trades/${res.data.id}/public`);
      setTrade(tradeRes.data);
      if (!tradeRes.data.requisites?.length) {
        setTrade({ ...tradeRes.data, requisites: [requisiteToUse] });
      }

      await axios.patch(`${API}/v1/invoice/${activeInvoice.invoice_id}/link-trade`, { trade_id: res.data.id }).catch(() => { });
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
      toast.success("Спор открыт!");
      setStep("disputed");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Ошибка открытия спора");
    }
  };

  const cancelTrade = async () => {
    if (!confirm("Отменить платеж?")) return;
    try {
      await axios.post(`${API}/trades/${trade.id}/cancel-client`);
      toast.success("Сделка отменена");
      resetFlow();
    } catch (e) { toast.error(e.response?.data?.detail || "Ошибка"); }
  };

  const fetchMessages = async () => {
    if (!trade) return;
    try {
      const res = await axios.get(`${API}/trades/${trade.id}/messages-public`);
      setMessages(res.data || []);
    } catch (e) { }
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

  const resetFlow = () => {
    setStep('idle');
    setTrade(null);
    setSavedRequisite(null);
    setActiveInvoice(null);
    setOperators([]);
    setFilteredOperators([]);
    setMessages([]);
    setAmount('');
    loadBalance();
  };

  const getDisplayRequisite = () => {
    return trade?.requisites?.[0] || savedRequisite || null;
  };

  const disconnectApi = () => {
    localStorage.removeItem('shop_api_key');
    localStorage.removeItem('shop_api_secret');
    localStorage.removeItem('shop_merchant_id');
    localStorage.removeItem('shop_merchant_name');
    setApiKey('');
    setApiSecret('');
    setMerchantId('');
    setMerchantName('');
    setConnected(false);
    setBalance(null);
    setTransactions([]);
    resetFlow();
    toast.success('Отключено');
  };

  const quickAmounts = [500, 1000, 2000, 5000, 10000];

  const getStatusBadge = (status) => {
    const configs = {
      pending: { bg: 'bg-yellow-500/10', text: 'text-yellow-400', label: 'Ожидание' },
      active: { bg: 'bg-blue-500/10', text: 'text-blue-400', label: 'Активный' },
      paid: { bg: 'bg-blue-500/10', text: 'text-blue-400', label: 'Оплачен' },
      completed: { bg: 'bg-green-500/10', text: 'text-green-400', label: 'Завершён' },
      cancelled: { bg: 'bg-red-500/10', text: 'text-red-400', label: 'Отменён' },
      expired: { bg: 'bg-zinc-500/10', text: 'text-zinc-400', label: 'Истёк' },
      disputed: { bg: 'bg-orange-500/10', text: 'text-orange-400', label: 'Спор' },
      dispute: { bg: 'bg-orange-500/10', text: 'text-orange-400', label: 'Спор' },
      waiting_requisites: { bg: 'bg-yellow-500/10', text: 'text-yellow-400', label: 'Ожидание' }
    };
    const c = configs[status] || configs.pending;
    return <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${c.bg} ${c.text}`}>{c.label}</span>;
  };

  // ========================================
  // ============= RENDER =================
  // ========================================

  return (
    <div className="min-h-screen bg-[#0A0A0A]">
      {/* ========== HEADER ========== */}
      <header className="sticky top-0 z-50 bg-[#0A0A0A]/95 backdrop-blur-xl border-b border-white/5">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#7C3AED] to-[#10B981] flex items-center justify-center">
              <Store className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-white font-bold text-lg">{connected ? merchantName : 'Магазин'}</h1>
              <div className="flex items-center gap-1.5">
                <div className={`w-2 h-2 rounded-full ${connected ? 'bg-[#10B981]' : 'bg-[#EF4444]'}`} />
                <span className="text-xs text-[#71717A]">{connected ? 'Подключено' : 'Не подключено'}</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {connected && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  const newValue = !showHistory;
                  setShowHistory(newValue);
                  if (newValue && apiKey && merchantId) {
                    loadTransactions();
                  }
                }}
                className="text-[#71717A] hover:text-white"
              >
                <History className="w-4 h-4" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowSettings(!showSettings)}
              className="text-[#71717A] hover:text-white"
            >
              <Settings className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">

        {/* ========== NOT CONNECTED STATE ========== */}
        {!connected && (
          <div className="bg-[#121212] border border-white/10 rounded-2xl p-6 max-w-md mx-auto">
            <div className="text-center mb-6">
              <div className="w-16 h-16 mx-auto bg-gradient-to-br from-[#7C3AED] to-[#10B981] rounded-2xl flex items-center justify-center mb-4">
                <Plug className="w-8 h-8 text-white" />
              </div>
              <h2 className="text-xl font-bold text-white mb-1">Подключение к магазину</h2>
              <p className="text-[#71717A] text-sm">Введите API ключ для начала работы</p>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-sm text-[#71717A] mb-1.5 block">API Key</label>
                <Input
                  type="text"
                  placeholder="Введите API ключ"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  className="bg-[#0A0A0A] border-white/10 text-white placeholder:text-[#52525B]"
                />
              </div>
              <div>
                <label className="text-sm text-[#71717A] mb-1.5 block">Secret Key</label>
                <div className="relative">
                  <Input
                    type={showSecret ? 'text' : 'password'}
                    placeholder="Введите Secret ключ"
                    value={apiSecret}
                    onChange={(e) => setApiSecret(e.target.value)}
                    className="bg-[#0A0A0A] border-white/10 text-white placeholder:text-[#52525B] pr-10"
                  />
                  <button
                    onClick={() => setShowSecret(!showSecret)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[#52525B] hover:text-white"
                  >
                    {showSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <Button
                onClick={() => connectApi(false)}
                disabled={connecting || !apiKey}
                className="w-full h-12 bg-[#7C3AED] hover:bg-[#6D28D9] text-white rounded-xl"
              >
                {connecting ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <>
                    <Plug className="w-4 h-4 mr-2" />
                    Подключить
                  </>
                )}
              </Button>
            </div>
          </div>
        )}

        {/* ========== CONNECTED: BALANCE + TOPUP ========== */}
        {connected && step === 'idle' && (
          <>
            {/* Balance Card */}
            <div className="bg-gradient-to-br from-[#7C3AED]/20 to-[#10B981]/20 border border-[#7C3AED]/20 rounded-2xl p-6">
              <div className="flex items-center justify-between mb-4">
                <span className="text-[#A1A1AA] text-sm">Баланс</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={loadBalance}
                  disabled={loadingBalance}
                  className="text-[#71717A] hover:text-white p-1"
                >
                  <RefreshCw className={`w-4 h-4 ${loadingBalance ? 'animate-spin' : ''}`} />
                </Button>
              </div>
              <div className="text-4xl font-bold text-white mb-1 font-['JetBrains_Mono']">
                {balance ? `${(balance.balance_usdt || 0).toFixed(2)} USDT` : '---'}
              </div>
              {balance?.total_received_rub != null && balance.total_received_rub > 0 && (
                <div className="text-sm text-[#71717A]">
                  Всего пополнено: {(balance.total_received_rub || 0).toLocaleString()} ₽
                </div>
              )}
            </div>

            {/* Top-up Section */}
            <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
              <h2 className="text-white font-semibold text-lg mb-4 flex items-center gap-2">
                <Wallet className="w-5 h-5 text-[#10B981]" />
                Пополнить баланс
              </h2>

              <div className="space-y-4">
                <div>
                  <label className="text-sm text-[#71717A] mb-2 block">Сумма в рублях</label>
                  <div className="relative">
                    <Input
                      type="number"
                      placeholder="Введите сумму"
                      value={amount}
                      onChange={(e) => setAmount(e.target.value)}
                      className="bg-[#0A0A0A] border-white/10 h-14 text-2xl text-center pr-12 text-white placeholder:text-[#52525B] font-['JetBrains_Mono']"
                      min="100"
                    />
                    <span className="absolute right-4 top-1/2 -translate-y-1/2 text-[#52525B] text-lg">RUB</span>
                  </div>
                </div>

                {/* Quick amounts */}
                <div className="grid grid-cols-5 gap-2">
                  {quickAmounts.map((val) => (
                    <Button
                      key={val}
                      variant="outline"
                      onClick={() => setAmount(String(val))}
                      className={`border-white/10 text-white hover:bg-white/5 h-11 px-2 text-sm font-medium ${amount === String(val) ? 'bg-[#10B981]/20 border-[#10B981]' : ''
                        }`}
                    >
                      {val >= 1000 ? `${val / 1000}k` : val}
                    </Button>
                  ))}
                </div>

                <Button
                  onClick={createTopUp}
                  disabled={!amount || topUpLoading || parseInt(amount) < 100}
                  className="w-full h-14 bg-[#10B981] hover:bg-[#059669] text-white text-lg rounded-xl"
                >
                  {topUpLoading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <>
                      <Wallet className="w-5 h-5 mr-2" />
                      Пополнить
                    </>
                  )}
                </Button>
              </div>
            </div>

            {/* === ACTIVE PAYMENTS === */}
            {activePayments.length > 0 && (
              <div className="bg-gradient-to-r from-yellow-500/10 to-orange-500/10 border border-yellow-500/20 rounded-2xl p-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-white font-semibold text-lg flex items-center gap-2">
                    <Clock className="w-5 h-5 text-yellow-400" />
                    Активные заявки ({activePayments.length})
                  </h2>
                  <Button variant="ghost" size="sm" onClick={loadActivePayments} disabled={loadingActive} className="text-[#71717A]">
                    <RefreshCw className={`w-4 h-4 ${loadingActive ? 'animate-spin' : ''}`} />
                  </Button>
                </div>
                <div className="space-y-2">
                  {activePayments.map((payment, i) => (
                    <div 
                      key={payment.id || i} 
                      className="flex items-center justify-between py-3 px-4 bg-[#0A0A0A] rounded-xl cursor-pointer hover:bg-[#1A1A1A] transition-colors"
                      onClick={() => {
                        // Перейти к продолжению оплаты
                        if (payment.id) {
                          window.open(`/select-operator/${payment.id}`, '_blank');
                        }
                      }}
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-yellow-500/10 flex items-center justify-center">
                          <Clock className="w-5 h-5 text-yellow-400" />
                        </div>
                        <div>
                          <div className="text-white text-sm font-medium">
                            {(payment.original_amount_rub || payment.amount_rub || 0).toLocaleString()} ₽
                          </div>
                          <div className="text-[#52525B] text-xs">
                            {payment.created_at ? new Date(payment.created_at).toLocaleDateString('ru', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="px-2 py-1 text-xs rounded-full bg-yellow-500/10 text-yellow-400">
                          {payment.status === 'waiting_requisites' ? 'Ожидает выбора' : payment.status === 'pending' ? 'Ожидает оплаты' : 'В процессе'}
                        </span>
                        <ExternalLink className="w-4 h-4 text-[#52525B]" />
                      </div>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-[#52525B] mt-3">Нажмите на заявку чтобы продолжить оплату</p>
              </div>
            )}

            {/* Transaction History (inline) */}
            {showHistory && (
              <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-white font-semibold text-lg flex items-center gap-2">
                    <History className="w-5 h-5 text-[#7C3AED]" />
                    История операций
                  </h2>
                  <Button variant="ghost" size="sm" onClick={loadTransactions} disabled={loadingHistory} className="text-[#71717A]">
                    <RefreshCw className={`w-4 h-4 ${loadingHistory ? 'animate-spin' : ''}`} />
                  </Button>
                </div>
                {transactions.length === 0 ? (
                  <div className="text-center py-8 text-[#52525B]">
                    <History className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>Нет операций</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {transactions.map((tx, i) => (
                      <div key={tx.id || i} className="flex items-center justify-between py-3 px-4 bg-[#0A0A0A] rounded-xl">
                        <div className="flex items-center gap-3">
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${tx.status === 'completed' ? 'bg-green-500/10' : 'bg-zinc-500/10'
                            }`}>
                            {tx.status === 'completed' ? (
                              <CheckCircle className="w-4 h-4 text-green-400" />
                            ) : tx.status === 'disputed' || tx.status === 'dispute' ? (
                              <AlertTriangle className="w-4 h-4 text-orange-400" />
                            ) : (
                              <Clock className="w-4 h-4 text-zinc-400" />
                            )}
                          </div>
                          <div>
                            <div className="text-white text-sm font-medium">
                              {(tx.amount_rub || tx.original_amount_rub || 0).toLocaleString()} RUB
                            </div>
                            <div className="text-[#52525B] text-xs">
                              {tx.created_at ? new Date(tx.created_at).toLocaleDateString('ru', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''}
                            </div>
                          </div>
                        </div>
                        <div className="text-right">
                          {getStatusBadge(tx.status)}
                          {tx.amount_usdt && (
                            <div className="text-xs text-[#71717A] mt-1">{tx.amount_usdt} USDT</div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {/* ========== SELECT OPERATOR (STAK) ========== */}
        {step === 'select_operator' && (
          <div>
            {/* Back button + amount header */}
            <div className="flex items-center justify-between mb-4">
              <Button
                variant="ghost"
                onClick={resetFlow}
                className="text-[#71717A] hover:text-white"
              >
                <X className="w-4 h-4 mr-1" /> Отмена
              </Button>
              <div className="text-right">
                <div className="text-[#71717A] text-xs">Пополнение</div>
                <div className="text-xl font-bold text-white font-['JetBrains_Mono']">
                  {depositAmount.toLocaleString()} RUB
                </div>
              </div>
            </div>

            {/* Payment method filter */}
            <div className="relative mb-4">
              <button
                onClick={() => setShowMethodsDropdown(!showMethodsDropdown)}
                className="flex items-center justify-between gap-3 px-4 py-3 bg-[#121212] border border-white/10 rounded-xl hover:border-white/20 transition-colors min-w-[200px]"
              >
                <span className="text-white">
                  {selectedFilter === "all" ? "Все методы оплаты" : getPaymentMethod(selectedFilter).name}
                </span>
                <ChevronDown className={`w-4 h-4 text-[#71717A] transition-transform ${showMethodsDropdown ? 'rotate-180' : ''}`} />
              </button>
              {showMethodsDropdown && (
                <div className="absolute top-full left-0 mt-2 bg-[#1A1A1A] border border-white/10 rounded-xl overflow-hidden z-20 shadow-xl min-w-[200px]">
                  <button
                    onClick={() => { setSelectedFilter("all"); setShowMethodsDropdown(false); }}
                    className={`w-full flex items-center justify-between gap-3 px-4 py-3 hover:bg-white/5 transition-colors ${selectedFilter === "all" ? "text-white" : "text-[#A1A1AA]"}`}
                  >
                    <span>Все методы</span>
                    {selectedFilter === "all" && <Check className="w-4 h-4 text-white" />}
                  </button>
                  {availableMethods.map(methodType => {
                    const info = getPaymentMethod(methodType);
                    return (
                      <button
                        key={methodType}
                        onClick={() => { setSelectedFilter(methodType); setShowMethodsDropdown(false); }}
                        className={`w-full flex items-center gap-3 px-4 py-3 transition-colors ${selectedFilter === methodType ? "bg-[#7C3AED] text-white" : "text-[#A1A1AA] hover:bg-white/5"}`}
                      >
                        <span className="text-lg">{info.emoji}</span>
                        <span className="flex-1 text-left">{info.name}</span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Operators count */}
            <div className="flex items-center justify-between mb-3">
              <span className="text-[#71717A] text-sm">
                {filteredOperators.length} {filteredOperators.length === 1 ? 'оператор' : 'операторов'}
              </span>
              <span className="text-xs text-[#52525B]">Лучшая цена сверху</span>
            </div>

            {/* Operators list */}
            {filteredOperators.length === 0 ? (
              <div className="bg-[#121212] rounded-2xl p-8 text-center border border-white/5">
                <AlertTriangle className="w-12 h-12 text-[#F59E0B] mx-auto mb-3" />
                <h2 className="text-lg font-semibold text-white mb-2">Нет доступных операторов</h2>
                <p className="text-[#71717A] text-sm">
                  {selectedFilter !== "all" ? "Попробуйте другой способ оплаты" : "Попробуйте позже"}
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {filteredOperators.map((op, index) => {
                  const bestPrice = filteredOperators[0]?.toPayRub || depositAmount;
                  const isBest = op.toPayRub === bestPrice;
                  const diff = op.toPayRub - bestPrice;
                  const uniqueTypes = [...new Set(op.requisites?.map(r => r.type) || [])];

                  return (
                    <div
                      key={op.offer_id}
                      onClick={() => openOperatorDialog(op)}
                      className={`bg-[#121212] border hover:bg-[#1A1A1A] rounded-xl p-4 cursor-pointer transition-all ${isBest ? "border-[#10B981]/30" : "border-white/5 hover:border-[#7C3AED]/30"}`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="relative">
                            <div className="w-10 h-10 rounded-full bg-[#1A1A1A] flex items-center justify-center">
                              <User className="w-5 h-5 text-[#52525B]" />
                            </div>
                            <div className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-[#121212] ${op.is_online ? 'bg-[#10B981]' : 'bg-[#52525B]'}`} />
                          </div>
                          <div>
                            <div className="text-white font-medium text-sm flex items-center gap-2">
                              {op.nickname || op.trader_login}
                              {isBest && (
                                <span className="px-2 py-0.5 bg-[#10B981]/10 text-[#10B981] text-xs rounded-full">
                                  Лучшая цена
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-2 text-xs text-[#52525B]">
                              <span className="flex items-center gap-1"><CheckCircle className="w-3 h-3 text-[#10B981]" />{op.success_rate || 100}%</span>
                              <span>{op.trades_count || 0} сделок</span>
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-4">
                          <div className="hidden sm:flex flex-wrap gap-1">
                            {uniqueTypes.map((type, idx) => {
                              const Icon = getRequisiteIcon(type);
                              return (
                                <span key={idx} className="inline-flex items-center gap-1 px-2 py-1 bg-[#1A1A1A] text-[#A1A1AA] text-xs rounded">
                                  <Icon className="w-3 h-3" />
                                  {getRequisiteLabel(type)}
                                </span>
                              );
                            })}
                          </div>
                          <div className="text-right">
                            <div className="text-lg font-bold text-white font-['JetBrains_Mono']">
                              {op.toPayRub.toLocaleString()} RUB
                            </div>
                            {op.commissionPercent > 0 && (
                              <div className="text-xs text-[#F59E0B]">+{op.commissionPercent}%</div>
                            )}
                          </div>
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
        )}

        {/* ========== PAYMENT STEP ========== */}
        {step === 'payment' && trade && (
          <div>
            <Button variant="ghost" onClick={cancelTrade} className="text-[#71717A] hover:text-white mb-4">
              <X className="w-4 h-4 mr-1" /> Отменить сделку
            </Button>

            <div className="grid md:grid-cols-2 gap-4">
              {/* Left: Payment details */}
              <div className="bg-[#121212] rounded-2xl p-6 border border-white/5">
                <div className="text-center mb-4">
                  <div className="w-14 h-14 rounded-2xl bg-[#F59E0B]/10 flex items-center justify-center mx-auto mb-3">
                    <Timer className="w-7 h-7 text-[#F59E0B]" />
                  </div>
                  <h2 className="text-lg font-bold text-white">Переведите точную сумму</h2>
                  {timeLeft != null && (
                    <div className="text-sm text-[#F59E0B] mt-1">
                      Осталось: {fmtTime(timeLeft)}
                    </div>
                  )}
                </div>

                {(() => {
                  const requisite = getDisplayRequisite();
                  if (!requisite) return (
                    <div className="text-center py-4 text-[#71717A]">
                      <AlertTriangle className="w-8 h-8 mx-auto mb-2 text-[#F59E0B]" />
                      <p>Реквизиты загружаются...</p>
                    </div>
                  );
                  const ReqIcon = getRequisiteIcon(requisite.type);
                  return (
                    <div className="space-y-3">
                      {/* Amount */}
                      <div className="bg-[#0A0A0A] rounded-xl p-4 text-center">
                        <div className="text-[#71717A] text-xs mb-1">Сумма к оплате</div>
                        <div className="text-3xl font-bold text-white font-['JetBrains_Mono']">
                          {(trade.amount_rub || depositAmount).toLocaleString()} RUB
                        </div>
                      </div>

                      {/* Requisite details */}
                      <div className="bg-[#0A0A0A] rounded-xl p-4">
                        <div className="flex items-center gap-2 mb-3">
                          <ReqIcon className="w-4 h-4 text-[#7C3AED]" />
                          <span className="text-[#71717A] text-sm">{getRequisiteLabel(requisite.type)}</span>
                        </div>

                        {requisite.data?.card_number && (
                          <div className="flex items-center justify-between py-2">
                            <span className="text-white font-mono text-lg tracking-wider">{requisite.data.card_number}</span>
                            <button onClick={() => copy(requisite.data.card_number)} className="text-[#7C3AED] hover:text-white p-1">
                              <Copy className="w-4 h-4" />
                            </button>
                          </div>
                        )}
                        {requisite.data?.phone && (
                          <div className="flex items-center justify-between py-2">
                            <span className="text-white font-mono text-lg">{requisite.data.phone}</span>
                            <button onClick={() => copy(requisite.data.phone)} className="text-[#7C3AED] hover:text-white p-1">
                              <Copy className="w-4 h-4" />
                            </button>
                          </div>
                        )}
                        {requisite.data?.bank_name && (
                          <div className="text-[#52525B] text-sm">{requisite.data.bank_name}</div>
                        )}
                        {requisite.data?.card_holder && (
                          <div className="text-[#71717A] text-sm mt-1">{requisite.data.card_holder}</div>
                        )}
                      </div>
                    </div>
                  );
                })()}

                <Button onClick={markPaid} className="w-full h-14 bg-[#10B981] hover:bg-[#059669] text-white text-lg rounded-xl mt-4">
                  <Check className="w-6 h-6 mr-2" /> Я оплатил
                </Button>
              </div>

              {/* Right: Chat */}
              <ChatPanel
                trade={trade}
                messages={messages}
                newMessage={newMessage}
                setNewMessage={setNewMessage}
                sendMsg={sendMsg}
                messagesEndRef={messagesEndRef}
              />
            </div>
          </div>
        )}

        {/* ========== WAITING STEP ========== */}
        {step === 'waiting' && trade && (
          <div className="grid md:grid-cols-2 gap-4">
            <div className="space-y-4">
              <div className="bg-[#121212] rounded-2xl p-6 border border-white/5">
                <div className="flex items-center justify-center mb-4">
                  <div className="w-16 h-16 rounded-2xl bg-[#3B82F6]/10 flex items-center justify-center">
                    <Loader2 className="w-8 h-8 text-[#3B82F6] animate-spin" />
                  </div>
                </div>
                <h2 className="text-xl font-bold text-white text-center mb-2">Ожидаем подтверждения</h2>
                <p className="text-[#71717A] text-center mb-4">Оператор проверяет ваш платёж</p>

                <div className="bg-[#0A0A0A] rounded-xl p-4 mb-4">
                  <div className="flex justify-between text-sm mb-2">
                    <span className="text-[#71717A]">Сумма</span>
                    <span className="text-white font-medium">{(trade.amount_rub || depositAmount).toLocaleString()} RUB</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-[#71717A]">Оператор</span>
                    <span className="text-white">{trade.trader_login}</span>
                  </div>
                </div>

                {/* Dispute */}
                {canDispute ? (
                  <Button onClick={openDispute} variant="outline" className="w-full border-[#EF4444] text-[#EF4444] hover:bg-[#EF4444]/10">
                    <AlertTriangle className="w-4 h-4 mr-2" />
                    Открыть спор
                  </Button>
                ) : (
                  <div className="bg-[#0A0A0A] rounded-xl p-3 text-center">
                    <div className="text-[#52525B] text-sm mb-1">Спор доступен через</div>
                    <div className="text-white font-bold font-['JetBrains_Mono'] text-lg">
                      {disputeCountdown != null ? fmtTime(disputeCountdown) : '10:00'}
                    </div>
                  </div>
                )}
              </div>
            </div>

            <ChatPanel
              trade={trade}
              messages={messages}
              newMessage={newMessage}
              setNewMessage={setNewMessage}
              sendMsg={sendMsg}
              messagesEndRef={messagesEndRef}
            />
          </div>
        )}

        {/* ========== COMPLETED ========== */}
        {step === 'completed' && (
          <div className="bg-[#121212] rounded-2xl p-8 border border-white/5 text-center max-w-md mx-auto">
            <div className="w-20 h-20 rounded-full bg-[#10B981]/10 flex items-center justify-center mx-auto mb-6">
              <CheckCircle className="w-10 h-10 text-[#10B981]" />
            </div>
            <h2 className="text-2xl font-bold text-white mb-2">Оплата зачислена!</h2>
            <p className="text-[#71717A] mb-6">Средства зачислены на ваш счёт</p>
            {trade && (
              <div className="bg-[#0A0A0A] rounded-xl p-4 text-left mb-6">
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-[#71717A]">Сумма</span>
                  <span className="text-white">{(trade.amount_rub || depositAmount).toLocaleString()} RUB</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-[#71717A]">Оператор</span>
                  <span className="text-white">{trade.trader_login}</span>
                </div>
              </div>
            )}
            <Button onClick={resetFlow} className="w-full h-12 bg-[#7C3AED] hover:bg-[#6D28D9] text-white rounded-xl">
              Вернуться в магазин
            </Button>
          </div>
        )}

        {/* ========== DISPUTED ========== */}
        {step === 'disputed' && trade && (
          <div className="grid md:grid-cols-2 gap-4">
            <div className="bg-[#121212] rounded-2xl p-6 border border-white/5">
              <div className="flex items-center justify-center mb-4">
                <div className="w-16 h-16 rounded-2xl bg-[#F59E0B]/10 flex items-center justify-center">
                  <AlertTriangle className="w-8 h-8 text-[#F59E0B]" />
                </div>
              </div>
              <h2 className="text-xl font-bold text-white text-center mb-2">Спор открыт</h2>
              <p className="text-[#71717A] text-center mb-4">Модератор рассмотрит вашу ситуацию</p>

              <div className="bg-[#0A0A0A] rounded-xl p-4 mb-4">
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-[#71717A]">Сумма</span>
                  <span className="text-white">{(trade.amount_rub || depositAmount).toLocaleString()} RUB</span>
                </div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-[#71717A]">Оператор</span>
                  <span className="text-white">{trade.trader_login}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-[#71717A]">Статус</span>
                  <span className="text-[#F59E0B]">На рассмотрении</span>
                </div>
              </div>

              <Button onClick={resetFlow} variant="outline" className="w-full border-white/10 text-white hover:bg-white/5">
                Вернуться в магазин
              </Button>
            </div>

            <ChatPanel
              trade={trade}
              messages={messages}
              newMessage={newMessage}
              setNewMessage={setNewMessage}
              sendMsg={sendMsg}
              messagesEndRef={messagesEndRef}
            />
          </div>
        )}
      </div>

      {/* ========== SETTINGS MODAL ========== */}
      <Dialog open={showSettings} onOpenChange={setShowSettings}>
        <DialogContent className="bg-[#121212] border-white/10 text-white max-w-md">
          <DialogHeader>
            <DialogTitle className="text-white">Настройки</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm text-[#71717A] mb-1.5 block">API Key</label>
              <Input
                type="text"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="bg-[#0A0A0A] border-white/10 text-white font-mono text-sm"
              />
            </div>
            <div>
              <label className="text-sm text-[#71717A] mb-1.5 block">Secret Key</label>
              <Input
                type={showSecret ? 'text' : 'password'}
                value={apiSecret}
                onChange={(e) => setApiSecret(e.target.value)}
                className="bg-[#0A0A0A] border-white/10 text-white font-mono text-sm"
              />
            </div>
            {connected && (
              <div className="bg-[#0A0A0A] rounded-xl p-3">
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-[#71717A]">Merchant ID</span>
                  <span className="text-white font-mono text-xs">{merchantId}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-[#71717A]">Магазин</span>
                  <span className="text-white">{merchantName}</span>
                </div>
              </div>
            )}
            <div className="flex gap-2">
              <Button
                onClick={() => { connectApi(false); setShowSettings(false); }}
                className="flex-1 bg-[#7C3AED] hover:bg-[#6D28D9] text-white"
              >
                <Save className="w-4 h-4 mr-2" /> Сохранить
              </Button>
              {connected && (
                <Button
                  onClick={() => { disconnectApi(); setShowSettings(false); }}
                  variant="outline"
                  className="border-[#EF4444] text-[#EF4444] hover:bg-[#EF4444]/10"
                >
                  Отключить
                </Button>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* ========== OPERATOR DIALOG ========== */}
      <Dialog open={showOperatorDialog} onOpenChange={setShowOperatorDialog}>
        <DialogContent className="bg-[#121212] border-white/10 text-white max-w-md">
          <DialogHeader>
            <DialogTitle className="text-white">Оплата через {selectedOperator?.nickname || 'оператора'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="bg-[#0A0A0A] rounded-xl p-4">
              <div className="flex justify-between items-center">
                <span className="text-[#71717A]">Сумма пополнения</span>
                <span className="text-white font-medium">{depositAmount.toLocaleString()} RUB</span>
              </div>
              <div className="flex justify-between items-center mt-2">
                <span className="text-[#71717A]">К оплате</span>
                <span className="text-xl font-bold text-white">{selectedOperator?.toPayRub?.toLocaleString()} RUB</span>
              </div>
              {selectedOperator?.commissionPercent > 0 && (
                <div className="flex justify-between items-center mt-1">
                  <span className="text-[#52525B] text-sm">Комиссия оператора</span>
                  <span className="text-sm text-[#F59E0B]">+{selectedOperator?.commissionPercent}%</span>
                </div>
              )}
            </div>

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
                        className={`w-full flex items-center gap-3 p-3 rounded-xl border transition-colors ${isSelected ? 'bg-[#7C3AED]/10 border-[#7C3AED]' : 'bg-[#0A0A0A] border-white/5 hover:border-white/20'}`}
                      >
                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${isSelected ? 'bg-[#7C3AED]/20' : 'bg-white/5'}`}>
                          <Icon className={`w-5 h-5 ${isSelected ? 'text-[#7C3AED]' : 'text-[#71717A]'}`} />
                        </div>
                        <div className="text-left">
                          <div className="text-white font-medium">{req.data?.bank_name || getRequisiteLabel(req.type)}</div>
                          <div className="text-xs text-[#52525B]">{getRequisiteLabel(req.type)}</div>
                        </div>
                        {isSelected && <Check className="w-5 h-5 text-[#7C3AED] ml-auto" />}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={rulesAccepted}
                onChange={(e) => setRulesAccepted(e.target.checked)}
                className="mt-1 w-4 h-4 rounded border-white/20 bg-transparent checked:bg-[#7C3AED]"
              />
              <span className="text-sm text-[#71717A]">
                Я принимаю правила сервиса и обязуюсь совершить перевод точной суммы без комментария
              </span>
            </label>

            <Button
              onClick={startTrade}
              disabled={creating || !rulesAccepted || (selectedOperator?.requisites?.length > 1 && !selectedRequisite)}
              className="w-full h-12 bg-[#10B981] hover:bg-[#059669] text-white rounded-xl"
            >
              {creating ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Перейти к оплате'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ========== CHAT PANEL COMPONENT ==========
function ChatPanel({ trade, messages, newMessage, setNewMessage, sendMsg, messagesEndRef }) {
  return (
    <div className="bg-[#121212] rounded-2xl border border-white/5 flex flex-col h-[500px]">
      <div className="p-4 border-b border-white/5">
        <h3 className="text-white font-semibold flex items-center gap-2">
          <MessageCircle className="w-4 h-4" />
          Сообщения
        </h3>
        <p className="text-[#52525B] text-xs mt-1">Оператор: {trade?.trader_login || 'Загрузка...'}</p>
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
              <div className={`max-w-[80%] px-4 py-2 rounded-2xl ${msg.sender_type === 'client'
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
  );
}
