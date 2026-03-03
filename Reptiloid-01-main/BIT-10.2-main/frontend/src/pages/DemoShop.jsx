import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import { 
  CreditCard, Smartphone, Wallet, QrCode, Globe,
  ChevronRight, CheckCircle, ArrowLeft, Settings, Trash2, Key, 
  ExternalLink, RefreshCw, Server, History, Clock, AlertCircle,
  DollarSign, TrendingUp, XCircle
} from 'lucide-react';
import CryptoJS from 'crypto-js';

// Иконки для методов оплаты
const METHOD_ICONS = {
  'card': CreditCard,
  'sbp': Smartphone,
  'sim': Smartphone,
  'mono_bank': Wallet,
  'sng_sbp': Globe,
  'sng_card': CreditCard,
  'qr_code': QrCode,
};

// Статусы с цветами и иконками
const STATUS_CONFIG = {
  'waiting_requisites': { label: 'Ожидание', color: 'text-yellow-400', bg: 'bg-yellow-500/10', icon: Clock },
  'pending': { label: 'Ожидает оплаты', color: 'text-blue-400', bg: 'bg-blue-500/10', icon: Clock },
  'waiting_buyer_confirmation': { label: 'Ожидает подтв.', color: 'text-blue-400', bg: 'bg-blue-500/10', icon: Clock },
  'waiting_trader_confirmation': { label: 'Проверка', color: 'text-orange-400', bg: 'bg-orange-500/10', icon: RefreshCw },
  'paid': { label: 'Оплачен', color: 'text-emerald-400', bg: 'bg-emerald-500/10', icon: CheckCircle },
  'completed': { label: 'Завершён', color: 'text-emerald-400', bg: 'bg-emerald-500/10', icon: CheckCircle },
  'cancelled': { label: 'Отменён', color: 'text-red-400', bg: 'bg-red-500/10', icon: XCircle },
  'expired': { label: 'Истёк', color: 'text-zinc-400', bg: 'bg-zinc-500/10', icon: XCircle },
  'dispute': { label: 'Спор', color: 'text-orange-400', bg: 'bg-orange-500/10', icon: AlertCircle },
  'disputed': { label: 'Спор', color: 'text-orange-400', bg: 'bg-orange-500/10', icon: AlertCircle },
};

// Генерация HMAC-SHA256 подписи
function generateSignature(data, secretKey) {
  const signData = Object.entries(data)
    .filter(([key, value]) => key !== 'sign' && value !== null && value !== undefined)
    .sort(([a], [b]) => a.localeCompare(b));
  
  const signString = signData.map(([k, v]) => `${k}=${v}`).join('&') + secretKey;
  const hash = CryptoJS.HmacSHA256(signString, secretKey);
  return hash.toString(CryptoJS.enc.Hex);
}

const DemoShop = () => {
  // Состояния
  const [view, setView] = useState('config'); // config, shop, history
  const [config, setConfig] = useState({
    apiUrl: '',
    merchantId: '',
    apiKey: '',
    secretKey: ''
  });
  const [isConnected, setIsConnected] = useState(false);
  const [merchantName, setMerchantName] = useState('');
  const [connecting, setConnecting] = useState(false);
  
  // Shop states
  const [step, setStep] = useState('amount');
  const [amount, setAmount] = useState('');
  const [selectedMethod, setSelectedMethod] = useState(null);
  const [paymentMethods, setPaymentMethods] = useState([]);
  const [loadingMethods, setLoadingMethods] = useState(false);
  const [loading, setLoading] = useState(false);
  const [userId] = useState('user_' + Math.random().toString(36).substring(7));
  
  // История и баланс
  const [transactions, setTransactions] = useState([]);
  const [loadingTransactions, setLoadingTransactions] = useState(false);
  const [balance, setBalance] = useState(0);
  const [stats, setStats] = useState({ total: 0, paid: 0, pending: 0 });

  // Загрузка сохранённой конфигурации
  useEffect(() => {
    const saved = localStorage.getItem('bitarbitr_merchant_config_v2');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        setConfig(parsed);
        if (parsed.apiKey && parsed.merchantId && parsed.secretKey && parsed.apiUrl) {
          verifyConnection(parsed);
        }
      } catch (e) {
        // silently ignore parse errors
      }
    }
  }, []);

  // Загрузка транзакций
  const loadTransactions = useCallback(async (cfg = config) => {
    if (!cfg.apiUrl || !cfg.apiKey) return;
    
    setLoadingTransactions(true);
    const apiUrl = cfg.apiUrl.replace(/\/$/, '');
    
    try {
      const res = await fetch(`${apiUrl}/api/v1/invoice/transactions?limit=50`, {
        headers: { 'X-Api-Key': cfg.apiKey }
      });
      
      const data = await res.json();
      
      if (res.ok && data.data?.transactions) {
        setTransactions(data.data.transactions);
        
        // Подсчёт баланса из завершённых транзакций
        const completedTx = data.data.transactions.filter(
          t => t.status === 'paid' || t.status === 'completed'
        );
        const totalBalance = completedTx.reduce((sum, t) => sum + (t.original_amount_rub || t.amount_rub || 0), 0);
        setBalance(totalBalance);
        
        // Статистика
        const pendingTx = data.data.transactions.filter(
          t => ['pending', 'waiting_buyer_confirmation', 'waiting_trader_confirmation', 'waiting_requisites'].includes(t.status)
        );
        setStats({
          total: data.data.total || data.data.transactions.length,
          paid: completedTx.length,
          pending: pendingTx.length
        });
      }
    } catch (error) {
      // silently fail
    } finally {
      setLoadingTransactions(false);
    }
  }, [config]);

  // Автообновление транзакций каждые 10 секунд когда на странице истории
  useEffect(() => {
    if (view === 'history' && isConnected) {
      loadTransactions(config);
      const interval = setInterval(() => loadTransactions(config), 10000);
      return () => clearInterval(interval);
    }
  }, [view, isConnected, config, loadTransactions]);

  // Проверка подключения к API
  const verifyConnection = async (cfg = config) => {
    if (!cfg.apiUrl) {
      toast.error('Введите URL API сервера');
      return;
    }
    if (!cfg.apiKey) {
      toast.error('Введите API ключ');
      return;
    }
    if (!cfg.secretKey) {
      toast.error('Введите Secret Key');
      return;
    }

    setConnecting(true);
    const apiUrl = cfg.apiUrl.replace(/\/$/, '');

    try {
      // Проверяем подключение через merchant-info
      const res = await fetch(`${apiUrl}/api/shop/merchant-info/${cfg.apiKey}`);
      const data = await res.json();
      
      if (res.ok && data.merchant_id) {
        const updatedConfig = {
          ...cfg,
          apiUrl: apiUrl,
          merchantId: data.merchant_id
        };
        
        setConfig(updatedConfig);
        setMerchantName(data.company_name || 'Мерчант');
        setIsConnected(true);
        
        // Сохраняем конфиг
        localStorage.setItem('bitarbitr_merchant_config_v2', JSON.stringify(updatedConfig));
        
        toast.success(`Подключено к: ${data.company_name || 'Мерчант'}`);
        
        // Загружаем способы оплаты через API
        await loadPaymentMethods(updatedConfig);
        
        // Загружаем историю транзакций
        await loadTransactions(updatedConfig);
        
        setView('shop');
      } else {
        toast.error(data.detail?.message || 'Неверный API ключ');
        setIsConnected(false);
      }
    } catch (error) {
      console.error('Connection error:', error);
      toast.error('Ошибка подключения к API. Проверьте URL.');
      setIsConnected(false);
    } finally {
      setConnecting(false);
    }
  };

  // Загрузка способов оплаты через API
  const loadPaymentMethods = async (cfg = config) => {
    setLoadingMethods(true);
    const apiUrl = cfg.apiUrl.replace(/\/$/, '');
    
    try {
      const res = await fetch(`${apiUrl}/api/v1/invoice/payment-methods`, {
        headers: {
          'X-Api-Key': cfg.apiKey
        }
      });
      
      const data = await res.json();
      
      if (res.ok && data.payment_methods) {
        setPaymentMethods(data.payment_methods);
        toast.success(`Загружено ${data.payment_methods.length} способов оплаты`);
      } else {
        toast.error('Не удалось загрузить способы оплаты');
        setPaymentMethods([]);
      }
    } catch (error) {
      console.error('Load payment methods error:', error);
      toast.error('Ошибка загрузки способов оплаты');
      setPaymentMethods([]);
    } finally {
      setLoadingMethods(false);
    }
  };

  // Создание инвойса и открытие в новой вкладке
  const createInvoice = async () => {
    if (!selectedMethod || !amount || !config.merchantId || !config.apiUrl) return;
    
    setLoading(true);
    const apiUrl = config.apiUrl.replace(/\/$/, '');
    
    try {
      const orderId = `DEMO_${Date.now()}_${Math.random().toString(36).substring(7).toUpperCase()}`;
      
      const requestData = {
        merchant_id: config.merchantId,
        order_id: orderId,
        amount: parseFloat(amount),
        currency: 'RUB',
        user_id: userId,
        callback_url: `${window.location.origin}/api/demo/callback`, // callback на "наш" сайт
        payment_method: selectedMethod.id
      };
      
      const sign = generateSignature(requestData, config.secretKey);
      
      const response = await fetch(`${apiUrl}/api/v1/invoice/create`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Api-Key': config.apiKey
        },
        body: JSON.stringify({ ...requestData, sign })
      });
      
      const data = await response.json();
      
      if (response.ok && data.status === 'success') {
        toast.success('Инвойс создан! Открываю страницу оплаты...');
        
        // ВАЖНО: Формируем полный URL с доменом платформы
        // payment_url приходит как "/pay/ordXXX", нужно добавить базовый URL
        let paymentUrl = data.payment_url;
        if (paymentUrl && paymentUrl.startsWith('/')) {
          paymentUrl = `${apiUrl}${paymentUrl}`;
        }
        window.open(paymentUrl, '_blank');
        
        // Обновляем историю транзакций
        setTimeout(() => loadTransactions(config), 2000);
        
        // Сбрасываем форму для нового заказа
        setStep('amount');
        setAmount('');
        setSelectedMethod(null);
      } else {
        toast.error(data.detail?.message || data.detail || 'Ошибка создания платежа');
      }
    } catch (error) {
      console.error('Create invoice error:', error);
      toast.error('Ошибка соединения с API');
    } finally {
      setLoading(false);
    }
  };

  // Сброс конфигурации
  const resetConfig = () => {
    localStorage.removeItem('bitarbitr_merchant_config_v2');
    setConfig({ apiUrl: '', merchantId: '', apiKey: '', secretKey: '' });
    setIsConnected(false);
    setMerchantName('');
    setPaymentMethods([]);
    setTransactions([]);
    setBalance(0);
    setStats({ total: 0, paid: 0, pending: 0 });
    setView('config');
    setStep('amount');
    setAmount('');
    setSelectedMethod(null);
  };

  // Форматирование даты
  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    const date = new Date(dateStr);
    return date.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // ========== СТРАНИЦА КОНФИГУРАЦИИ ==========
  const renderConfigPage = () => (
    <div className="space-y-6">
      <div className="text-center">
        <div className="w-16 h-16 mx-auto bg-emerald-500/20 rounded-2xl flex items-center justify-center mb-4">
          <Key className="w-8 h-8 text-emerald-400" />
        </div>
        <h1 className="text-2xl font-bold mb-2">Демо-магазин</h1>
        <p className="text-zinc-400 text-sm">Эмуляция внешнего сайта мерчанта</p>
      </div>

      <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3">
        <p className="text-xs text-blue-300">
          <strong>💡 Как это работает:</strong> Этот демо-магазин работает как <strong>полностью внешний сайт</strong>. 
          Подключитесь к любому серверу BITARBITR через API, выберите способ оплаты, и страница оплаты откроется 
          в <strong>новой вкладке</strong> на домене сервера.
        </p>
      </div>

      <div className="space-y-4">
        {/* API URL */}
        <div>
          <Label className="text-zinc-400 flex items-center gap-2">
            <Server className="w-4 h-4" />
            URL API сервера
          </Label>
          <Input
            type="url"
            placeholder="https://bitarbitr.org"
            value={config.apiUrl}
            onChange={(e) => setConfig(prev => ({ ...prev, apiUrl: e.target.value }))}
            className="bg-zinc-800 border-zinc-700 mt-1 font-mono text-sm"
            data-testid="api-url-input"
          />
          <p className="text-xs text-zinc-500 mt-1">
            Домен вашего сервера BITARBITR
          </p>
        </div>

        {/* API Key */}
        <div>
          <Label className="text-zinc-400 flex items-center gap-2">
            <Key className="w-4 h-4" />
            API Key (X-Api-Key)
          </Label>
          <Input
            type="text"
            placeholder="sk_live_..."
            value={config.apiKey}
            onChange={(e) => setConfig(prev => ({ ...prev, apiKey: e.target.value }))}
            className="bg-zinc-800 border-zinc-700 mt-1 font-mono text-sm"
            data-testid="api-key-input"
          />
        </div>

        {/* Secret Key */}
        <div>
          <Label className="text-zinc-400">Secret Key (для подписи)</Label>
          <Input
            type="password"
            placeholder="Секретный ключ мерчанта"
            value={config.secretKey}
            onChange={(e) => setConfig(prev => ({ ...prev, secretKey: e.target.value }))}
            className="bg-zinc-800 border-zinc-700 mt-1"
            data-testid="secret-key-input"
          />
        </div>

        <Button
          onClick={() => verifyConnection()}
          disabled={!config.apiUrl || !config.apiKey || !config.secretKey || connecting}
          className="w-full h-12 bg-emerald-500 hover:bg-emerald-600"
          data-testid="connect-btn"
        >
          {connecting ? (
            <span className="flex items-center gap-2">
              <RefreshCw className="w-5 h-5 animate-spin" />
              Подключение...
            </span>
          ) : (
            <>
              <CheckCircle className="w-5 h-5 mr-2" />
              Подключиться к API
            </>
          )}
        </Button>
      </div>

      <div className="pt-4 border-t border-zinc-800">
        <p className="text-xs text-zinc-500 text-center">
          Получите API ключи в личном кабинете мерчанта → раздел API
        </p>
      </div>
    </div>
  );

  // ========== СТРАНИЦА МАГАЗИНА ==========
  const renderShopPage = () => (
    <div className="space-y-6">
      {/* Хедер с информацией о подключении и балансом */}
      <div className="bg-emerald-500/10 rounded-lg px-4 py-3">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-400" />
            <span className="text-sm text-emerald-400 font-medium">{merchantName}</span>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                loadTransactions(config);
                setView('history');
              }}
              className="text-zinc-400 hover:text-white h-8 px-2"
              data-testid="history-btn"
            >
              <History className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setView('config')}
              className="text-zinc-400 hover:text-white h-8 px-2"
            >
              <Settings className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={resetConfig}
              className="text-zinc-400 hover:text-red-400 h-8 px-2"
            >
              <Trash2 className="w-4 h-4" />
            </Button>
          </div>
        </div>
        
        {/* Баланс и статистика */}
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-emerald-500/20">
          <div>
            <div className="text-xs text-zinc-500">Баланс магазина</div>
            <div className="text-lg font-bold text-white flex items-center gap-1">
              <DollarSign className="w-4 h-4 text-emerald-400" />
              {balance.toLocaleString('ru-RU')} ₽
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs text-zinc-500">Оплачено / Всего</div>
            <div className="text-sm font-medium">
              <span className="text-emerald-400">{stats.paid}</span>
              <span className="text-zinc-500"> / {stats.total}</span>
              {stats.pending > 0 && (
                <span className="ml-2 text-yellow-400 text-xs">({stats.pending} в обработке)</span>
              )}
            </div>
          </div>
        </div>
        
        <div className="text-xs text-zinc-500 font-mono truncate mt-2">
          <ExternalLink className="w-3 h-3 inline mr-1" />
          {config.apiUrl}
        </div>
      </div>

      {step === 'amount' && (
        <div className="space-y-6">
          <div className="text-center">
            <h1 className="text-2xl font-bold mb-2">Пополнение счёта</h1>
            <p className="text-zinc-400">Введите сумму пополнения</p>
          </div>

          <div className="space-y-4">
            <div className="relative">
              <Input
                type="number"
                placeholder="Сумма"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="bg-zinc-800 border-zinc-700 h-14 text-xl text-center pr-12"
                min="100"
                data-testid="amount-input"
              />
              <span className="absolute right-4 top-1/2 -translate-y-1/2 text-zinc-500 text-lg">₽</span>
            </div>

            <div className="grid grid-cols-4 gap-2">
              {[500, 1000, 2000, 5000].map((val) => (
                <Button
                  key={val}
                  variant="outline"
                  onClick={() => setAmount(String(val))}
                  className={`border-zinc-700 ${amount === String(val) ? 'bg-emerald-500/20 border-emerald-500' : ''}`}
                  data-testid={`amount-btn-${val}`}
                >
                  {val}₽
                </Button>
              ))}
            </div>
          </div>

          <Button
            onClick={() => {
              if (!amount || parseFloat(amount) < 100) {
                toast.error('Минимальная сумма 100₽');
                return;
              }
              setStep('method');
            }}
            disabled={!amount}
            className="w-full h-12 bg-emerald-500 hover:bg-emerald-600"
            data-testid="continue-btn"
          >
            Продолжить
            <ChevronRight className="w-5 h-5 ml-2" />
          </Button>
        </div>
      )}

      {step === 'method' && (
        <div className="space-y-6">
          <div className="flex items-center gap-4 mb-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setStep('amount')}
              className="text-zinc-400"
            >
              <ArrowLeft className="w-4 h-4 mr-1" />
              Назад
            </Button>
            <div>
              <h1 className="text-lg font-bold">Способ оплаты</h1>
              <p className="text-zinc-400 text-sm">Сумма: {parseFloat(amount).toLocaleString('ru-RU')} ₽</p>
            </div>
          </div>

          {/* Способы оплаты из API */}
          {loadingMethods ? (
            <div className="flex items-center justify-center py-8">
              <RefreshCw className="w-6 h-6 animate-spin text-emerald-400" />
              <span className="ml-2 text-zinc-400">Загрузка способов оплаты...</span>
            </div>
          ) : paymentMethods.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-zinc-400">Способы оплаты не загружены</p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => loadPaymentMethods(config)}
                className="mt-2"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Загрузить
              </Button>
            </div>
          ) : (
            <div className="space-y-3 max-h-[350px] overflow-y-auto">
              {paymentMethods.map((method) => {
                const IconComponent = METHOD_ICONS[method.id] || CreditCard;
                return (
                  <Card
                    key={method.id}
                    className={`bg-zinc-900 border-zinc-800 cursor-pointer transition-all hover:border-zinc-600 ${
                      selectedMethod?.id === method.id ? 'border-emerald-500 ring-1 ring-emerald-500/30' : ''
                    }`}
                    onClick={() => setSelectedMethod(method)}
                    data-testid={`method-${method.id}`}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-center gap-4">
                        <div className="w-12 h-12 rounded-xl bg-zinc-800 flex items-center justify-center">
                          <IconComponent className="w-6 h-6 text-emerald-400" />
                        </div>
                        <div className="flex-1">
                          <div className="font-medium">{method.name}</div>
                          <div className="text-sm text-zinc-500">{method.description}</div>
                        </div>
                        {selectedMethod?.id === method.id && (
                          <CheckCircle className="w-5 h-5 text-emerald-500" />
                        )}
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}

          {/* Информация про новую вкладку */}
          <div className="bg-orange-500/10 border border-orange-500/20 rounded-lg p-3">
            <p className="text-xs text-orange-300">
              <ExternalLink className="w-3 h-3 inline mr-1" />
              <strong>Страница оплаты откроется в новой вкладке</strong> на домене {config.apiUrl}
            </p>
          </div>

          <Button
            onClick={createInvoice}
            disabled={!selectedMethod || loading}
            className="w-full h-12 bg-emerald-500 hover:bg-emerald-600"
            data-testid="pay-btn"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <RefreshCw className="w-5 h-5 animate-spin" />
                Создание платежа...
              </span>
            ) : (
              <>
                <ExternalLink className="w-5 h-5 mr-2" />
                Оплатить {parseFloat(amount).toLocaleString('ru-RU')} ₽
              </>
            )}
          </Button>
        </div>
      )}
    </div>
  );

  // ========== СТРАНИЦА ИСТОРИИ ТРАНЗАКЦИЙ ==========
  const renderHistoryPage = () => (
    <div className="space-y-6">
      {/* Хедер */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setView('shop')}
            className="text-zinc-400 hover:text-white"
          >
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <h1 className="text-lg font-bold">История транзакций</h1>
            <p className="text-xs text-zinc-500">{merchantName}</p>
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => loadTransactions(config)}
          disabled={loadingTransactions}
          className="text-zinc-400"
        >
          <RefreshCw className={`w-4 h-4 ${loadingTransactions ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {/* Баланс большой */}
      <div className="bg-gradient-to-r from-emerald-500/10 to-blue-500/10 rounded-xl p-4 border border-emerald-500/20">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm text-zinc-400">Баланс магазина</div>
            <div className="text-3xl font-bold text-white mt-1">
              {balance.toLocaleString('ru-RU')} ₽
            </div>
          </div>
          <div className="w-14 h-14 bg-emerald-500/20 rounded-xl flex items-center justify-center">
            <TrendingUp className="w-7 h-7 text-emerald-400" />
          </div>
        </div>
        <div className="flex gap-4 mt-4 pt-4 border-t border-zinc-800">
          <div className="flex-1">
            <div className="text-xs text-zinc-500">Оплачено</div>
            <div className="text-lg font-bold text-emerald-400">{stats.paid}</div>
          </div>
          <div className="flex-1">
            <div className="text-xs text-zinc-500">В обработке</div>
            <div className="text-lg font-bold text-yellow-400">{stats.pending}</div>
          </div>
          <div className="flex-1">
            <div className="text-xs text-zinc-500">Всего</div>
            <div className="text-lg font-bold text-zinc-300">{stats.total}</div>
          </div>
        </div>
      </div>

      {/* Список транзакций */}
      <div className="space-y-2">
        <div className="text-sm font-medium text-zinc-400 px-1">Последние операции</div>
        
        {loadingTransactions && transactions.length === 0 ? (
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="w-6 h-6 animate-spin text-emerald-400" />
            <span className="ml-2 text-zinc-400">Загрузка...</span>
          </div>
        ) : transactions.length === 0 ? (
          <div className="text-center py-8 text-zinc-500">
            <History className="w-10 h-10 mx-auto mb-2 opacity-50" />
            <p>Нет транзакций</p>
            <p className="text-xs mt-1">Создайте первый платёж</p>
          </div>
        ) : (
          <div className="space-y-2 max-h-[400px] overflow-y-auto">
            {transactions.map((tx) => {
              const statusConfig = STATUS_CONFIG[tx.status] || STATUS_CONFIG['pending'];
              const StatusIcon = statusConfig.icon;
              const displayAmount = tx.original_amount_rub || tx.amount_rub || 0;
              
              return (
                <Card 
                  key={tx.id} 
                  className="bg-zinc-900/50 border-zinc-800 hover:border-zinc-700 transition-colors"
                  data-testid={`tx-${tx.id}`}
                >
                  <CardContent className="p-3">
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-lg ${statusConfig.bg} flex items-center justify-center shrink-0`}>
                        <StatusIcon className={`w-5 h-5 ${statusConfig.color}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <span className="font-medium text-sm truncate">
                            {tx.external_id || tx.id}
                          </span>
                          <span className={`text-sm font-bold ${
                            tx.status === 'paid' || tx.status === 'completed' 
                              ? 'text-emerald-400' 
                              : 'text-zinc-300'
                          }`}>
                            {tx.status === 'paid' || tx.status === 'completed' ? '+' : ''}
                            {displayAmount.toLocaleString('ru-RU')} ₽
                          </span>
                        </div>
                        <div className="flex items-center justify-between mt-1">
                          <span className={`text-xs px-2 py-0.5 rounded ${statusConfig.bg} ${statusConfig.color}`}>
                            {statusConfig.label}
                          </span>
                          <span className="text-xs text-zinc-500">
                            {formatDate(tx.created_at)}
                          </span>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* Кнопка вернуться */}
      <Button
        onClick={() => setView('shop')}
        className="w-full bg-emerald-500 hover:bg-emerald-600"
        data-testid="back-to-shop-btn"
      >
        <ChevronRight className="w-5 h-5 mr-2 rotate-180" />
        Вернуться в магазин
      </Button>
    </div>
  );

  return (
    <div className="min-h-screen bg-[#09090B] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <Card className="bg-zinc-900/50 border-zinc-800">
          <CardContent className="p-6">
            {view === 'config' && renderConfigPage()}
            {view === 'shop' && renderShopPage()}
            {view === 'history' && renderHistoryPage()}
          </CardContent>
        </Card>
        
        <div className="text-center mt-4 space-y-1">
          <p className="text-xs text-zinc-600">
            Демо-магазин BITARBITR • Эмуляция внешнего сайта
          </p>
          <p className="text-xs text-zinc-700">
            ID покупателя: {userId}
          </p>
        </div>
      </div>
    </div>
  );
};

export default DemoShop;
