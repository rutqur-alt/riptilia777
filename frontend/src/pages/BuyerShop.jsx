import React, { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { toast } from 'sonner';
import { API } from '@/App';
import axios from 'axios';
import {
  CheckCircle, Copy, AlertTriangle, Shield, Timer,
  RefreshCw, Loader2, Check, Clock, X, History,
  CreditCard, Smartphone, Phone, QrCode
} from 'lucide-react';
import { PAYMENT_METHODS, getPaymentMethod } from '@/config/paymentMethods';

// Import modular components
import {
  ShopHeader,
  ApiConnectionForm,
  BalanceCard,
  TopUpForm,
  OperatorSelector,
  PaymentCard,
  ChatPanel,
  SettingsDialog
} from './shop';

// Helper functions
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

const getStatusBadge = (status) => {
  const styles = {
    completed: "bg-green-500/10 text-green-400",
    pending: "bg-yellow-500/10 text-yellow-400",
    paid: "bg-blue-500/10 text-blue-400",
    disputed: "bg-orange-500/10 text-orange-400",
    cancelled: "bg-zinc-500/10 text-zinc-400"
  };
  const labels = {
    completed: "Завершено",
    pending: "Ожидание",
    paid: "Оплачено",
    disputed: "Спор",
    cancelled: "Отменено"
  };
  return (
    <span className={`px-2 py-1 rounded-full text-xs ${styles[status] || styles.pending}`}>
      {labels[status] || status}
    </span>
  );
};

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

  // === Operator selection ===
  const [step, setStep] = useState('idle');
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

  // ========== Effects ==========
  useEffect(() => {
    if (apiKey && !connected) connectApi(true);
  }, []);

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
    if (trade?.paid_at) {
      const updateDispute = () => {
        const paidAt = new Date(trade.paid_at);
        const diff = Math.floor((new Date() - paidAt) / 1000);
        if (diff >= 600) {
          setCanDispute(true);
          setDisputeCountdown(0);
        } else {
          setCanDispute(false);
          setDisputeCountdown(600 - diff);
        }
      };
      updateDispute();
      const i = setInterval(updateDispute, 1000);
      return () => clearInterval(i);
    }
  }, [trade?.paid_at]);

  useEffect(() => {
    if (trade && ["payment", "waiting", "disputed"].includes(step)) {
      fetchMessages();
      const i = setInterval(fetchMessages, 5000);
      return () => clearInterval(i);
    }
  }, [trade, step]);

  useEffect(() => {
    if (trade && step === "waiting") {
      const poll = setInterval(async () => {
        try {
          const res = await axios.get(`${API}/trades/${trade.id}/public`);
          setTrade(res.data);
          if (res.data.status === "completed") {
            setStep("completed");
            toast.success("Оплата зачислена!");
            loadBalance();
            clearInterval(poll);
          } else if (res.data.status === "disputed") {
            setStep("disputed");
          } else if (res.data.status === "cancelled") {
            resetFlow();
            toast.info("Сделка отменена");
          }
        } catch (e) { }
      }, 3000);
      return () => clearInterval(poll);
    }
  }, [trade, step]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (!operators.length) return;
    if (selectedFilter === "all") {
      setFilteredOperators(operators);
    } else {
      const filtered = operators.filter(op =>
        op.requisites?.some(r => r.type === selectedFilter)
      );
      setFilteredOperators(filtered);
    }
  }, [selectedFilter, operators]);

  // ========== API Functions ==========
  const connectApi = async (silent = false) => {
    if (!apiKey || !apiSecret || !merchantId) {
      if (!silent) toast.error('Заполните все поля');
      return;
    }
    setConnecting(true);
    try {
      const res = await axios.post(`${API}/merchant/v1/auth`, {
        api_key: apiKey,
        api_secret: apiSecret,
        merchant_id: merchantId
      });
      
      if (res.data.success) {
        setMerchantName(res.data.merchant_name || 'Магазин');
        setBalance({
          balance_usdt: res.data.balance_usdt || 0,
          total_client_rub: res.data.total_client_rub || 0,
          total_received_rub: res.data.total_received_rub || 0,
          transactions_count: res.data.transactions_count || 0
        });
        setConnected(true);
        localStorage.setItem('shop_api_key', apiKey);
        localStorage.setItem('shop_api_secret', apiSecret);
        localStorage.setItem('shop_merchant_id', merchantId);
        localStorage.setItem('shop_merchant_name', res.data.merchant_name);
        if (!silent) toast.success('Подключено!');
        loadTransactions();
      }
    } catch (e) {
      const errMsg = e.response?.data?.detail?.message || 'Ошибка авторизации';
      if (!silent) toast.error(errMsg);
      setConnected(false);
    } finally {
      setConnecting(false);
    }
  };

  const loadBalance = async () => {
    if (!apiKey || !apiSecret || !merchantId) return;
    setLoadingBalance(true);
    try {
      const res = await axios.post(`${API}/merchant/v1/balance`, {
        api_key: apiKey,
        api_secret: apiSecret,
        merchant_id: merchantId
      });
      if (res.data.success) {
        setBalance({
          balance_usdt: res.data.balance_usdt || 0,
          total_client_rub: res.data.total_client_rub || 0,
          total_received_rub: res.data.total_received_rub || 0,
          transactions_count: res.data.transactions_count || 0
        });
      }
    } catch (e) { }
    finally { setLoadingBalance(false); }
  };

  const loadTransactions = async () => {
    if (!apiKey || !apiSecret || !merchantId) return;
    setLoadingHistory(true);
    try {
      const res = await axios.post(`${API}/merchant/v1/transactions`, {
        api_key: apiKey,
        api_secret: apiSecret,
        merchant_id: merchantId,
        limit: 20
      });
      if (res.data.success) {
        setTransactions(res.data.transactions || []);
      }
    } catch (e) { }
    finally { setLoadingHistory(false); }
  };

  const startTopUp = async () => {
    const numAmount = parseInt(amount);
    if (!numAmount || numAmount < 100) {
      toast.error('Минимальная сумма 100 рублей');
      return;
    }

    setTopUpLoading(true);
    try {
      const res = await axios.post(`${API}/merchant/v1/invoice/create`, {
        api_key: apiKey,
        api_secret: apiSecret,
        merchant_id: merchantId,
        amount_rub: numAmount,
        description: `Пополнение на ${numAmount.toLocaleString()} руб.`
      });

      if (res.data.success) {
        setActiveInvoice({
          ...res.data,
          client_amount_rub: numAmount,
          merchant_receives_rub: res.data.merchant_receives_rub
        });
        setDepositAmount(numAmount);
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
    if (operator.requisites?.length > 0) {
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

      const clientAmountRub = activeInvoice.client_amount_rub || depositAmount;
      const clientPaysRub = Math.round(inv.amount_usdt * selectedOperator.price_rub * 100) / 100;

      const res = await axios.post(`${API}/trades`, {
        amount_usdt: inv.amount_usdt,
        price_rub: selectedOperator.price_rub,
        trader_id: selectedOperator.trader_id,
        payment_link_id: activeInvoice.invoice_id,
        offer_id: selectedOperator.offer_id,
        requisite_ids: [requisiteToUse.id],
        buyer_type: "client",
        merchant_id: merchantId || null,
        client_amount_rub: clientAmountRub,
        client_pays_rub: clientPaysRub,
        merchant_receives_rub: activeInvoice.merchant_receives_rub,
        merchant_receives_usdt: activeInvoice.merchant_receives_rub ? activeInvoice.merchant_receives_rub / selectedOperator.price_rub : null
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
    setActiveInvoice(null);
    setSelectedOperator(null);
    setSelectedRequisite(null);
    setMessages([]);
    setAmount('');
    setCanDispute(false);
    setDisputeCountdown(null);
  };

  const getDisplayRequisite = () => {
    return trade?.requisites?.[0] || savedRequisite;
  };

  const disconnectApi = () => {
    setConnected(false);
    setBalance(null);
    localStorage.removeItem('shop_api_key');
    localStorage.removeItem('shop_api_secret');
    localStorage.removeItem('shop_merchant_id');
    localStorage.removeItem('shop_merchant_name');
    setApiKey('');
    setApiSecret('');
    setMerchantId('');
    setMerchantName('');
    toast.success('Отключено');
  };

  // ========== Render ==========
  return (
    <div className="min-h-screen bg-[#0A0A0A]">
      <ShopHeader
        connected={connected}
        merchantName={merchantName}
        showHistory={showHistory}
        setShowHistory={setShowHistory}
        showSettings={showSettings}
        setShowSettings={setShowSettings}
        loadTransactions={loadTransactions}
      />

      <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {/* Not Connected */}
        {!connected && (
          <ApiConnectionForm
            merchantId={merchantId}
            setMerchantId={setMerchantId}
            apiKey={apiKey}
            setApiKey={setApiKey}
            apiSecret={apiSecret}
            setApiSecret={setApiSecret}
            showSecret={showSecret}
            setShowSecret={setShowSecret}
            connecting={connecting}
            connectApi={connectApi}
          />
        )}

        {/* Connected - Idle State */}
        {connected && step === 'idle' && (
          <>
            <BalanceCard
              balance={balance?.total_client_rub}
              loadingBalance={loadingBalance}
              fetchBalance={loadBalance}
            />

            <TopUpForm
              amount={amount}
              setAmount={setAmount}
              topUpLoading={topUpLoading}
              startTopUp={startTopUp}
            />

            {/* Transaction History */}
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
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${tx.status === 'completed' ? 'bg-green-500/10' : 'bg-zinc-500/10'}`}>
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
                              {Math.round(tx.client_amount_rub || tx.amount_rub || 0).toLocaleString()} RUB
                            </div>
                            <div className="text-[#52525B] text-xs">
                              {tx.created_at ? new Date(tx.created_at).toLocaleDateString('ru', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''}
                            </div>
                          </div>
                        </div>
                        <div className="text-right">
                          {getStatusBadge(tx.status)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {/* Operator Selection */}
        {step === 'select_operator' && (
          <OperatorSelector
            depositAmount={depositAmount}
            operators={operators}
            filteredOperators={filteredOperators}
            selectedFilter={selectedFilter}
            setSelectedFilter={setSelectedFilter}
            availableMethods={availableMethods}
            showMethodsDropdown={showMethodsDropdown}
            setShowMethodsDropdown={setShowMethodsDropdown}
            openOperatorDialog={openOperatorDialog}
            resetFlow={resetFlow}
          />
        )}

        {/* Payment Step */}
        {step === 'payment' && trade && (
          <div className="grid md:grid-cols-2 gap-4">
            <PaymentCard
              trade={trade}
              depositAmount={depositAmount}
              timeLeft={timeLeft}
              requisite={getDisplayRequisite()}
              cancelTrade={cancelTrade}
              markPaid={markPaid}
              copy={copy}
            />
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

        {/* Waiting Step */}
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
                    <span className="text-white font-medium">{Math.round(trade.amount_rub || depositAmount || 0).toLocaleString()} RUB</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-[#71717A]">Оператор</span>
                    <span className="text-white">{trade.trader_login}</span>
                  </div>
                </div>

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

        {/* Completed Step */}
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
                  <span className="text-white">{Math.round(trade.amount_rub || depositAmount || 0).toLocaleString()} RUB</span>
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

        {/* Disputed Step */}
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
                  <span className="text-white">{Math.round(trade.amount_rub || depositAmount || 0).toLocaleString()} RUB</span>
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

      {/* Settings Dialog */}
      <SettingsDialog
        open={showSettings}
        onOpenChange={setShowSettings}
        connected={connected}
        merchantId={merchantId}
        setMerchantId={setMerchantId}
        apiKey={apiKey}
        setApiKey={setApiKey}
        apiSecret={apiSecret}
        setApiSecret={setApiSecret}
        showSecret={showSecret}
        setShowSecret={setShowSecret}
        merchantName={merchantName}
        disconnectApi={disconnectApi}
        connectApi={connectApi}
      />

      {/* Operator Selection Dialog */}
      <Dialog open={showOperatorDialog} onOpenChange={setShowOperatorDialog}>
        <DialogContent className="bg-[#121212] border-white/10 text-white max-w-md">
          <DialogHeader>
            <DialogTitle>Выбор оператора</DialogTitle>
          </DialogHeader>

          {selectedOperator && (
            <div className="space-y-4 mt-4">
              <div className="bg-[#0A0A0A] rounded-xl p-4">
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-[#71717A]">Оператор</span>
                  <span className="text-white">{selectedOperator.nickname || selectedOperator.trader_login}</span>
                </div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-[#71717A]">Сумма к оплате</span>
                  <span className="text-white font-bold">{Math.round(selectedOperator.toPayRub || 0).toLocaleString()} RUB</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-[#71717A]">Курс</span>
                  <span className="text-white">{selectedOperator.price_rub} RUB/USDT</span>
                </div>
              </div>

              {selectedOperator.requisites?.length > 1 && (
                <div>
                  <label className="text-sm text-[#71717A] mb-2 block">Способ оплаты</label>
                  <div className="space-y-2">
                    {selectedOperator.requisites.map((req, idx) => {
                      const Icon = getRequisiteIcon(req.type);
                      return (
                        <button
                          key={idx}
                          onClick={() => setSelectedRequisite(req)}
                          className={`w-full flex items-center gap-3 p-3 rounded-xl border transition-all ${
                            selectedRequisite?.id === req.id
                              ? 'border-[#7C3AED] bg-[#7C3AED]/10'
                              : 'border-white/10 hover:border-white/20'
                          }`}
                        >
                          <Icon className="w-5 h-5 text-[#7C3AED]" />
                          <span className="text-white">{getRequisiteLabel(req.type)}</span>
                          {selectedRequisite?.id === req.id && (
                            <Check className="w-4 h-4 text-[#7C3AED] ml-auto" />
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              <div className="flex items-start gap-2">
                <input
                  type="checkbox"
                  checked={rulesAccepted}
                  onChange={(e) => setRulesAccepted(e.target.checked)}
                  className="mt-1"
                />
                <span className="text-[#71717A] text-sm">
                  Я подтверждаю, что переведу <span className="text-white font-bold">{Math.round(selectedOperator.toPayRub || 0).toLocaleString()} RUB</span> в течение 15 минут
                </span>
              </div>

              <Button
                onClick={startTrade}
                disabled={!rulesAccepted || creating}
                className="w-full h-12 bg-[#7C3AED] hover:bg-[#6D28D9]"
              >
                {creating ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                Подтвердить
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
