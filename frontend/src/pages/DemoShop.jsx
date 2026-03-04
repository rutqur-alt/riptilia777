import React, { useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { toast } from 'sonner';
import axios from 'axios';
import CryptoJS from 'crypto-js';
import { 
  Wallet, RefreshCw, Clock, CheckCircle, XCircle, AlertTriangle,
  ExternalLink, History, ArrowRight, Loader2, Store, Settings, Copy
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

// ==================== DEMO SHOP ====================
// Демонстрационный магазин с полной интеграцией через Invoice API
// Показывает как работает интеграция мерчанта

export default function DemoShop() {
  // === Config ===
  const [apiKey, setApiKey] = useState('');
  const [secretKey, setSecretKey] = useState('');
  const [merchantId, setMerchantId] = useState('');
  const [connected, setConnected] = useState(false);
  const [merchantName, setMerchantName] = useState('');
  
  // === Balance ===
  const [balanceRub, setBalanceRub] = useState(0);
  const [loadingBalance, setLoadingBalance] = useState(false);
  
  // === Top-up ===
  const [amount, setAmount] = useState('');
  const [topUpLoading, setTopUpLoading] = useState(false);
  
  // === Orders History ===
  const [orders, setOrders] = useState([]);
  const [loadingOrders, setLoadingOrders] = useState(false);
  const [showHistory, setShowHistory] = useState(true);

  // === Webhook Log (для демонстрации) ===
  const [webhookLog, setWebhookLog] = useState([]);

  // Load saved keys
  useEffect(() => {
    const savedKey = localStorage.getItem('demo_api_key');
    const savedSecret = localStorage.getItem('demo_secret_key');
    if (savedKey && savedSecret) {
      setApiKey(savedKey);
      setSecretKey(savedSecret);
    }
  }, []);

  // Generate HMAC-SHA256 signature
  const generateSignature = useCallback((params, secret) => {
    const SIGN_FIELDS = ['merchant_id', 'order_id', 'amount', 'currency', 'user_id', 'callback_url'];
    const signParams = {};
    
    for (const [k, v] of Object.entries(params)) {
      if (!SIGN_FIELDS.includes(k) || k === 'sign' || v == null) continue;
      signParams[k] = typeof v === 'number' && Number.isInteger(v) ? Math.floor(v) : v;
    }
    
    const signString = Object.keys(signParams).sort()
      .map(k => `${k}=${signParams[k]}`).join('&') + secret;
    
    return CryptoJS.HmacSHA256(signString, secret).toString();
  }, []);

  // Connect to merchant
  const connect = async () => {
    if (!apiKey || !secretKey) {
      toast.error('Введите API Key и Secret Key');
      return;
    }
    
    try {
      // Get merchant info
      const res = await axios.get(`${API}/shop/merchant-info/${apiKey}`);
      if (res.data) {
        setMerchantId(res.data.merchant_id);
        setMerchantName(res.data.company_name || 'Магазин');
        setBalanceRub(res.data.balance_rub || 0);
        setConnected(true);
        localStorage.setItem('demo_api_key', apiKey);
        localStorage.setItem('demo_secret_key', secretKey);
        toast.success('Подключено!');
        loadOrders();
      }
    } catch (e) {
      const errData = e.response?.data;
      let errMsg = e.message;
      if (errData) {
        if (typeof errData === 'string') errMsg = errData;
        else if (typeof errData.detail === 'string') errMsg = errData.detail;
        else if (errData.message) errMsg = errData.message;
      }
      toast.error('Ошибка подключения: ' + errMsg);
    }
  };

  // Load balance
  const loadBalance = async () => {
    if (!apiKey) return;
    setLoadingBalance(true);
    try {
      const res = await axios.get(`${API}/shop/merchant-info/${apiKey}`);
      setBalanceRub(res.data?.balance_rub || 0);
    } catch (e) {
      console.error(e);
    }
    setLoadingBalance(false);
  };

  // Load orders history with webhook status
  const loadOrders = async () => {
    if (!apiKey) return;
    setLoadingOrders(true);
    try {
      const res = await axios.get(`${API}/v1/invoice/transactions`, {
        params: { limit: 50 },
        headers: { 'X-Api-Key': apiKey }
      });
      const txs = res.data?.data?.transactions || [];
      setOrders(txs);
    } catch (e) {
      console.error(e);
    }
    setLoadingOrders(false);
  };

  // Create payment via Invoice API
  const createPayment = async () => {
    const amountNum = parseInt(amount);
    if (!amountNum || amountNum < 100) {
      toast.error('Минимальная сумма 100 ₽');
      return;
    }
    
    setTopUpLoading(true);
    try {
      const orderId = `ORDER_${Date.now()}`;
      const callbackUrl = window.location.origin + '/api/demo-webhook'; // Демо webhook
      
      const params = {
        merchant_id: merchantId,
        order_id: orderId,
        amount: amountNum,
        currency: 'RUB',
        callback_url: callbackUrl,
        user_id: null
      };
      
      // Generate signature
      params.sign = generateSignature(params, secretKey);
      params.description = `Пополнение на ${amountNum} ₽`;
      
      // Call Invoice API
      const res = await axios.post(`${API}/v1/invoice/create`, params, {
        headers: { 'X-Api-Key': apiKey, 'Content-Type': 'application/json' }
      });
      
      if (res.data.status === 'success') {
        toast.success('Платёж создан!');
        
        // Add to webhook log
        setWebhookLog(prev => [{
          time: new Date().toLocaleTimeString(),
          order_id: orderId,
          payment_id: res.data.payment_id,
          status: 'waiting_requisites',
          message: 'Инвойс создан, ожидает выбора оператора'
        }, ...prev]);
        
        // Redirect to payment page
        window.open(res.data.payment_url, '_blank');
        
        // Refresh orders
        setTimeout(loadOrders, 1000);
      } else {
        const msg = res.data.message || res.data.detail;
        toast.error(typeof msg === 'string' ? msg : 'Ошибка создания платежа');
      }
    } catch (e) {
      const errData = e.response?.data;
      let errMsg = 'Ошибка';
      if (errData) {
        if (typeof errData === 'string') errMsg = errData;
        else if (typeof errData.detail === 'string') errMsg = errData.detail;
        else if (typeof errData.message === 'string') errMsg = errData.message;
        else if (errData.detail?.message) errMsg = errData.detail.message;
      }
      toast.error(errMsg);
    }
    setTopUpLoading(false);
    setAmount('');
  };

  // Get status badge
  const getStatusBadge = (status) => {
    const styles = {
      waiting_requisites: { bg: 'bg-gray-500/20', text: 'text-gray-400', label: 'Ожидает выбора', icon: Clock },
      pending: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: 'Ожидает оплаты', icon: Clock },
      paid: { bg: 'bg-blue-500/20', text: 'text-blue-400', label: 'Оплачено', icon: CheckCircle },
      completed: { bg: 'bg-emerald-500/20', text: 'text-emerald-400', label: 'Завершён', icon: CheckCircle },
      cancelled: { bg: 'bg-red-500/20', text: 'text-red-400', label: 'Отменён', icon: XCircle },
      expired: { bg: 'bg-zinc-500/20', text: 'text-zinc-400', label: 'Истёк', icon: XCircle },
      disputed: { bg: 'bg-orange-500/20', text: 'text-orange-400', label: 'Спор', icon: AlertTriangle }
    };
    const s = styles[status] || styles.pending;
    const Icon = s.icon;
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs ${s.bg} ${s.text}`}>
        <Icon className="w-3 h-3" />
        {s.label}
      </span>
    );
  };

  // Get webhook status description
  const getWebhookStatus = (status) => {
    const descriptions = {
      waiting_requisites: 'Webhook: ожидание (клиент не выбрал оператора)',
      pending: 'Webhook: pending (клиент выбрал оператора)',
      paid: 'Webhook: paid (клиент нажал "Я оплатил")',
      completed: 'Webhook: completed ✓ (оператор подтвердил)',
      cancelled: 'Webhook: cancelled (отмена/таймаут)',
      expired: 'Webhook: expired (истёк срок)',
      disputed: 'Webhook: disputed (открыт спор)'
    };
    return descriptions[status] || `Webhook: ${status}`;
  };

  // Disconnect
  const disconnect = () => {
    setConnected(false);
    setMerchantId('');
    setMerchantName('');
    setBalanceRub(0);
    setOrders([]);
    localStorage.removeItem('demo_api_key');
    localStorage.removeItem('demo_secret_key');
  };

  // Quick amounts
  const quickAmounts = [500, 1000, 2000, 5000, 10000];

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white p-4 md:p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-500 to-blue-600 flex items-center justify-center">
              <Store className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold">Демо Магазин</h1>
              <p className="text-sm text-zinc-500">Интеграция через Invoice API</p>
            </div>
          </div>
          {connected && (
            <Button variant="ghost" size="sm" onClick={disconnect} className="text-zinc-500">
              Отключить
            </Button>
          )}
        </div>

        {/* Connection Form */}
        {!connected ? (
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Settings className="w-5 h-5 text-emerald-400" />
                Подключение к API
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm text-zinc-400 mb-2 block">API Key</label>
                <Input
                  placeholder="pk_live_..."
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  className="bg-zinc-950 border-zinc-800"
                />
              </div>
              <div>
                <label className="text-sm text-zinc-400 mb-2 block">Secret Key</label>
                <Input
                  type="password"
                  placeholder="sk_live_..."
                  value={secretKey}
                  onChange={(e) => setSecretKey(e.target.value)}
                  className="bg-zinc-950 border-zinc-800"
                />
              </div>
              <Button onClick={connect} className="w-full bg-emerald-600 hover:bg-emerald-700">
                Подключить
              </Button>
              <p className="text-xs text-zinc-500 text-center">
                Получите ключи в разделе "API Интеграция" дашборда мерчанта
              </p>
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Connected Header */}
            <div className="flex items-center gap-2 text-emerald-400 text-sm">
              <CheckCircle className="w-4 h-4" />
              Подключено: {merchantName}
            </div>

            {/* Balance Card */}
            <Card className="bg-gradient-to-br from-emerald-500/10 to-blue-500/10 border-emerald-500/20">
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-zinc-400 text-sm">Баланс магазина</span>
                  <Button variant="ghost" size="sm" onClick={loadBalance} disabled={loadingBalance}>
                    <RefreshCw className={`w-4 h-4 ${loadingBalance ? 'animate-spin' : ''}`} />
                  </Button>
                </div>
                <div className="text-4xl font-bold text-white font-mono">
                  {balanceRub.toLocaleString()} ₽
                </div>
                <p className="text-xs text-zinc-500 mt-2">
                  Баланс увеличивается при завершённых платежах (webhook: completed)
                </p>
              </CardContent>
            </Card>

            {/* Top-up Form */}
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Wallet className="w-5 h-5 text-emerald-400" />
                  Пополнить баланс
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <label className="text-sm text-zinc-400 mb-2 block">Сумма в рублях</label>
                  <Input
                    type="number"
                    placeholder="Введите сумму"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    className="bg-zinc-950 border-zinc-800"
                  />
                </div>
                
                <div className="flex gap-2 flex-wrap">
                  {quickAmounts.map(a => (
                    <Button 
                      key={a} 
                      variant="outline" 
                      size="sm"
                      className="border-zinc-700"
                      onClick={() => setAmount(String(a))}
                    >
                      {a >= 1000 ? `${a/1000}к` : a}
                    </Button>
                  ))}
                </div>

                <Button 
                  onClick={createPayment} 
                  disabled={topUpLoading || !amount}
                  className="w-full bg-emerald-600 hover:bg-emerald-700"
                >
                  {topUpLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <ArrowRight className="w-4 h-4 mr-2" />
                  )}
                  Создать платёж
                </Button>

                <p className="text-xs text-zinc-500">
                  После создания откроется страница выбора оператора для оплаты
                </p>
              </CardContent>
            </Card>

            {/* Orders History with Webhook Status */}
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg flex items-center gap-2">
                    <History className="w-5 h-5 text-blue-400" />
                    История ордеров
                  </CardTitle>
                  <Button variant="ghost" size="sm" onClick={loadOrders} disabled={loadingOrders}>
                    <RefreshCw className={`w-4 h-4 ${loadingOrders ? 'animate-spin' : ''}`} />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {orders.length === 0 ? (
                  <div className="text-center py-8 text-zinc-500">
                    <History className="w-12 h-12 mx-auto mb-3 opacity-20" />
                    <p>Нет ордеров</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {orders.map((order, i) => (
                      <div 
                        key={order.id || i}
                        className="p-4 bg-zinc-950 rounded-xl border border-zinc-800 hover:border-zinc-700 transition-colors"
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-sm text-white">
                                #{order.id?.slice(0, 20) || order.order_id}
                              </span>
                              <button 
                                onClick={() => {
                                  navigator.clipboard.writeText(order.id);
                                  toast.success('ID скопирован');
                                }}
                                className="text-zinc-500 hover:text-white"
                              >
                                <Copy className="w-3 h-3" />
                              </button>
                            </div>
                            <div className="text-xs text-zinc-500 mt-1">
                              {order.created_at ? new Date(order.created_at).toLocaleString('ru') : '—'}
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-lg font-bold text-white">
                              {(order.original_amount_rub || order.amount_rub || order.fiat_amount || 0).toLocaleString()} ₽
                            </div>
                            <div className="text-xs text-zinc-500">
                              ≈ {(order.amount_usdt || 0).toFixed(2)} USDT
                            </div>
                          </div>
                        </div>
                        
                        {/* Status Badge */}
                        <div className="flex items-center justify-between mt-3 pt-3 border-t border-zinc-800">
                          <div className="flex items-center gap-2">
                            {getStatusBadge(order.status)}
                          </div>
                          {order.status !== 'completed' && order.status !== 'cancelled' && order.status !== 'expired' && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-zinc-400 hover:text-white text-xs"
                              onClick={() => window.open(`/select-operator/${order.id}`, '_blank')}
                            >
                              <ExternalLink className="w-3 h-3 mr-1" />
                              Продолжить
                            </Button>
                          )}
                        </div>
                        
                        {/* Webhook Status */}
                        <div className="mt-2 text-xs text-zinc-500 bg-zinc-900/50 rounded px-2 py-1">
                          {getWebhookStatus(order.status)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Webhook Log (Demo) */}
            {webhookLog.length > 0 && (
              <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <AlertTriangle className="w-5 h-5 text-yellow-400" />
                    Webhook события (демо)
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {webhookLog.map((log, i) => (
                      <div key={i} className="text-xs font-mono p-2 bg-zinc-950 rounded">
                        <span className="text-zinc-500">[{log.time}]</span>{' '}
                        <span className="text-emerald-400">{log.status}</span>{' '}
                        <span className="text-zinc-400">→ {log.message}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* API Info */}
            <Card className="bg-zinc-900/50 border-zinc-800">
              <CardContent className="p-4">
                <h3 className="text-sm font-medium text-zinc-300 mb-2">Как это работает:</h3>
                <ol className="text-xs text-zinc-500 space-y-1 list-decimal list-inside">
                  <li><code className="text-emerald-400">POST /api/v1/invoice/create</code> → создаёт платёж, получаем payment_url</li>
                  <li>Клиент переходит на payment_url → выбирает оператора → оплачивает</li>
                  <li>Webhook отправляется на callback_url при каждом изменении статуса</li>
                  <li>При <code className="text-emerald-400">completed</code> → баланс увеличивается</li>
                </ol>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
