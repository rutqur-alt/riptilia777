import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { API } from "@/App";
import axios from "axios";
import { 
  Wallet, DollarSign, CreditCard, Gift, Trophy, 
  Star, Zap, Crown, Sparkles, ArrowRight, User,
  LogOut, History, Settings, Clock, CheckCircle, XCircle, AlertTriangle, Key, Save, RefreshCw
} from "lucide-react";

/**
 * TestCasino - Демо-страница казино для тестирования платёжного шлюза
 * Подключено через API-ключ как реальный внешний мерчант
 */

export default function TestCasino() {
  // Load saved state from localStorage
  const savedUser = localStorage.getItem('casino_user');
  const savedBalance = localStorage.getItem('casino_balance');
  const savedApiKey = localStorage.getItem('casino_api_key');
  
  const [apiKey, setApiKey] = useState(savedApiKey || "");
  const [showApiSettings, setShowApiSettings] = useState(!savedApiKey);
  const [apiKeyInput, setApiKeyInput] = useState(savedApiKey || "");
  const [apiConnected, setApiConnected] = useState(false);
  const [merchantInfo, setMerchantInfo] = useState(null);
  
  const [isLoggedIn, setIsLoggedIn] = useState(!!savedUser);
  const [casinoUser, setCasinoUser] = useState(savedUser ? JSON.parse(savedUser) : null);
  const [balance, setBalance] = useState(savedBalance ? parseFloat(savedBalance) : 0);
  const [merchantBalance, setMerchantBalance] = useState(0);
  const [depositAmount, setDepositAmount] = useState("");
  const [showDeposit, setShowDeposit] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [loading, setLoading] = useState(false);
  const [paymentLinks, setPaymentLinks] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // Save API key and verify connection
  const saveApiKey = async () => {
    if (!apiKeyInput.trim()) {
      toast.error("Введите API ключ");
      return;
    }
    
    try {
      // Verify API key by fetching merchant balance
      const response = await axios.get(`${API}/v1/merchant/balance`, {
        headers: { "X-API-Key": apiKeyInput }
      });
      
      setApiKey(apiKeyInput);
      localStorage.setItem('casino_api_key', apiKeyInput);
      setApiConnected(true);
      setMerchantBalance(response.data.balance_usdt || 0);
      setMerchantInfo(response.data);
      setShowApiSettings(false);
      toast.success("API ключ подключен успешно!");
    } catch (error) {
      console.error("API key verification failed:", error);
      toast.error("Неверный API ключ или мерчант не найден");
      setApiConnected(false);
    }
  };

  // Disconnect API key
  const disconnectApiKey = () => {
    setApiKey("");
    setApiKeyInput("");
    localStorage.removeItem('casino_api_key');
    setApiConnected(false);
    setMerchantInfo(null);
    setShowApiSettings(true);
    toast.info("API ключ отключен");
  };

  // Save user state to localStorage
  const saveUserState = (user, bal) => {
    if (user) {
      localStorage.setItem('casino_user', JSON.stringify(user));
      localStorage.setItem('casino_balance', bal.toString());
    } else {
      localStorage.removeItem('casino_user');
      localStorage.removeItem('casino_balance');
    }
  };

  // Fetch merchant balance via API Key
  const fetchMerchantBalance = async () => {
    if (!apiKey) return;
    try {
      const response = await axios.get(`${API}/v1/merchant/balance`, {
        headers: { "X-API-Key": apiKey }
      });
      setMerchantBalance(response.data.balance_usdt || 0);
      setMerchantInfo(response.data);
      setApiConnected(true);
    } catch (error) {
      console.error("Failed to fetch merchant balance:", error);
      setApiConnected(false);
    }
  };

  // Fetch payment history via API Key
  const fetchPaymentHistory = async () => {
    if (!apiKey) return;
    setLoadingHistory(true);
    try {
      const response = await axios.get(`${API}/v1/payments`, {
        headers: { "X-API-Key": apiKey }
      });
      setPaymentLinks(response.data || []);
    } catch (error) {
      console.error("Failed to fetch payment history:", error);
    } finally {
      setLoadingHistory(false);
    }
  };

  // Initial API key verification on mount
  useEffect(() => {
    if (savedApiKey) {
      setApiKeyInput(savedApiKey);
      fetchMerchantBalance();
    }
  }, []);

  // Refresh data on mount and periodically
  useEffect(() => {
    if (isLoggedIn && apiKey) {
      fetchMerchantBalance();
      checkCompletedDeposits();
      const interval = setInterval(() => {
        fetchMerchantBalance();
        checkCompletedDeposits();
      }, 10000);
      return () => clearInterval(interval);
    }
  }, [isLoggedIn, apiKey]);

  // Check for completed deposits and add to player balance
  const checkCompletedDeposits = async () => {
    if (!apiKey) return;
    try {
      const response = await axios.get(`${API}/v1/payments`, {
        headers: { "X-API-Key": apiKey }
      });
      const payments = response.data || [];
      
      // Get list of already credited payments
      const creditedPayments = JSON.parse(localStorage.getItem('casino_credited_payments') || '[]');
      
      // Get current balance from localStorage (more reliable than state)
      let currentBalance = parseFloat(localStorage.getItem('casino_balance') || '0');
      let balanceChanged = false;
      
      // Find new completed payments
      for (const payment of payments) {
        if (payment.trade_status === 'completed' && !creditedPayments.includes(payment.id)) {
          // Add to player balance (use amount_rub for RUB balance)
          currentBalance += (payment.amount_rub || 0);
          balanceChanged = true;
          
          // Mark as credited
          creditedPayments.push(payment.id);
          
          toast.success(`+${payment.amount_rub?.toLocaleString()} ₽ зачислено на баланс!`);
        }
      }
      
      // Save if any changes
      if (balanceChanged) {
        setBalance(currentBalance);
        localStorage.setItem('casino_balance', currentBalance.toString());
        localStorage.setItem('casino_credited_payments', JSON.stringify(creditedPayments));
      }
    } catch (error) {
      console.error("Failed to check deposits:", error);
    }
  };

  // Open history modal
  const openHistory = () => {
    setShowHistory(true);
    fetchPaymentHistory();
  };

  // Simulate casino user login
  const handleCasinoLogin = (e) => {
    e.preventDefault();
    const username = e.target.username.value;
    const user = { username, id: "user_" + Math.random().toString(36).slice(2, 8) };
    const initialBalance = 0; // Start with 0 balance
    
    // Clear credited payments for new user
    localStorage.removeItem('casino_credited_payments');
    
    setIsLoggedIn(true);
    setCasinoUser(user);
    setBalance(initialBalance);
    saveUserState(user, initialBalance);
    fetchMerchantBalance();
    toast.success(`Добро пожаловать, ${username}!`);
  };

  // Logout
  const handleLogout = () => {
    setIsLoggedIn(false);
    setCasinoUser(null);
    setBalance(0);
    saveUserState(null, 0);
    localStorage.removeItem('casino_credited_payments');
  };

  // Add balance when deposit completed (called from history check)
  const addToBalance = (amount) => {
    const newBalance = balance + amount;
    setBalance(newBalance);
    saveUserState(casinoUser, newBalance);
  };

  // Create payment via API Key and redirect to deposit page
  const handleDeposit = async () => {
    if (!depositAmount || parseFloat(depositAmount) < 100) {
      toast.error("Минимальная сумма пополнения: 100 ₽");
      return;
    }

    setLoading(true);
    try {
      // Create payment via API Key (как реальный внешний сайт)
      const response = await axios.post(
        `${API}/v1/payment/create`,
        {
          amount_rub: parseFloat(depositAmount),
          description: `Пополнение для ${casinoUser?.username}`,
          client_id: casinoUser?.id
        },
        {
          headers: { 
            "X-API-Key": apiKey,
            "Content-Type": "application/json"
          }
        }
      );
      
      const paymentUrl = response.data.payment_url;
      
      // Open deposit page in new tab
      window.open(paymentUrl, '_blank');
      setShowDeposit(false);
      setDepositAmount("");
      toast.success("Платёж открыт в новой вкладке. Проверяйте историю для статуса.");
      
    } catch (error) {
      console.error("Failed to create payment:", error);
      toast.error(error.response?.data?.detail || "Ошибка создания платежа");
    } finally {
      setLoading(false);
    }
  };

  // Get status badge
  const getStatusBadge = (link) => {
    if (link.trade_status === "cancelled") {
      return (
        <span className="flex items-center gap-1 text-slate-400 bg-slate-500/20 px-2 py-1 rounded-lg text-xs">
          <XCircle className="w-3 h-3" />
          Отменено
        </span>
      );
    }
    if (link.trade_status === "disputed") {
      return (
        <span className="flex items-center gap-1 text-red-400 bg-red-500/20 px-2 py-1 rounded-lg text-xs">
          <AlertTriangle className="w-3 h-3" />
          Спор
        </span>
      );
    }
    if (link.trade_status === "paid") {
      return (
        <span className="flex items-center gap-1 text-blue-400 bg-blue-500/20 px-2 py-1 rounded-lg text-xs">
          <Clock className="w-3 h-3" />
          Проверка
        </span>
      );
    }
    if (link.trade_status === "pending") {
      return (
        <span className="flex items-center gap-1 text-yellow-400 bg-yellow-500/20 px-2 py-1 rounded-lg text-xs">
          <Clock className="w-3 h-3" />
          Ожидает оплаты
        </span>
      );
    }
    if (link.trade_status === "completed" || link.status === "completed") {
      return (
        <span className="flex items-center gap-1 text-green-400 bg-green-500/20 px-2 py-1 rounded-lg text-xs">
          <CheckCircle className="w-3 h-3" />
          Зачислено
        </span>
      );
    }
    if (link.status === "active" && !link.trade_id) {
      return (
        <span className="flex items-center gap-1 text-slate-400 bg-slate-500/20 px-2 py-1 rounded-lg text-xs">
          <Clock className="w-3 h-3" />
          Ожидает
        </span>
      );
    }
    if (link.status === "expired") {
      return (
        <span className="flex items-center gap-1 text-slate-400 bg-slate-500/20 px-2 py-1 rounded-lg text-xs">
          <XCircle className="w-3 h-3" />
          Истекла
        </span>
      );
    }
    return (
      <span className="flex items-center gap-1 text-slate-400 bg-slate-500/20 px-2 py-1 rounded-lg text-xs">
        {link.status}
      </span>
    );
  };

  // Format date
  const formatDate = (dateStr) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  };

  // Quick deposit buttons
  const quickAmounts = [500, 1000, 2000, 5000, 10000];

  // API Settings Screen (shown first if no API key)
  if (showApiSettings || !apiKey) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-900 via-violet-900 to-indigo-900">
        {/* Casino Header */}
        <header className="border-b border-white/10 bg-black/20 backdrop-blur-sm">
          <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-yellow-400 to-orange-500 flex items-center justify-center">
                <Crown className="w-7 h-7 text-white" />
              </div>
              <div>
                <div className="text-xl font-bold text-white">Lucky Vegas</div>
                <div className="text-xs text-purple-300">Online Casino</div>
              </div>
            </div>
            <div className="flex items-center gap-2 text-xs text-red-400">
              <XCircle className="w-4 h-4" />
              <span>API не подключен</span>
            </div>
          </div>
        </header>

        {/* API Setup Form */}
        <main className="flex items-center justify-center px-4 py-20">
          <div className="w-full max-w-lg">
            <div className="bg-black/30 backdrop-blur-xl border border-white/10 rounded-3xl p-8">
              <div className="text-center mb-8">
                <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center mx-auto mb-4">
                  <Key className="w-10 h-10 text-white" />
                </div>
                <h1 className="text-2xl font-bold text-white mb-2">Настройка API</h1>
                <p className="text-purple-300">Введите API-ключ мерчанта для интеграции</p>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-purple-300 mb-2">API Ключ мерчанта</label>
                  <Input
                    value={apiKeyInput}
                    onChange={(e) => setApiKeyInput(e.target.value)}
                    placeholder="Вставьте API ключ мерчанта..."
                    className="bg-white/10 border-white/20 text-white placeholder:text-white/50 h-12 rounded-xl font-mono text-sm"
                  />
                </div>
                
                <Button 
                  onClick={saveApiKey}
                  className="w-full h-12 rounded-xl bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700 text-white font-bold"
                >
                  <Save className="w-4 h-4 mr-2" />
                  Подключить API
                </Button>
              </div>

              <div className="mt-6 p-4 bg-purple-500/10 border border-purple-500/30 rounded-xl">
                <h3 className="text-white font-semibold mb-2 flex items-center gap-2">
                  <Settings className="w-4 h-4" />
                  Как получить API ключ?
                </h3>
                <ol className="text-purple-300 text-sm space-y-2">
                  <li>1. Войдите в систему как мерчант</li>
                  <li>2. Перейдите в раздел "API Ключи"</li>
                  <li>3. Скопируйте активный API ключ</li>
                  <li>4. Вставьте его в поле выше</li>
                </ol>
              </div>
              
              <div className="mt-4 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-xl">
                <div className="text-yellow-300 text-xs">
                  <strong>Тестовый API ключ:</strong>
                  <code className="block mt-1 bg-black/30 p-2 rounded text-[10px] break-all">
                    f4a6d873-dd9a-4546-bdd4-349906e91439
                  </code>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    );
  }

  if (!isLoggedIn) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-900 via-violet-900 to-indigo-900">
        {/* Casino Header */}
        <header className="border-b border-white/10 bg-black/20 backdrop-blur-sm">
          <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-yellow-400 to-orange-500 flex items-center justify-center">
                <Crown className="w-7 h-7 text-white" />
              </div>
              <div>
                <div className="text-xl font-bold text-white">Lucky Vegas</div>
                <div className="text-xs text-purple-300">Online Casino</div>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 text-xs text-green-400">
                <CheckCircle className="w-4 h-4" />
                <span>API подключен</span>
              </div>
              <Button
                onClick={() => setShowApiSettings(true)}
                variant="ghost"
                size="sm"
                className="text-purple-300 hover:text-white"
              >
                <Settings className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </header>

        {/* Login Form */}
        <main className="flex items-center justify-center px-4 py-20">
          <div className="w-full max-w-md">
            <div className="bg-black/30 backdrop-blur-xl border border-white/10 rounded-3xl p-8">
              <div className="text-center mb-8">
                <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-yellow-400 to-orange-500 flex items-center justify-center mx-auto mb-4">
                  <Crown className="w-10 h-10 text-white" />
                </div>
                <h1 className="text-2xl font-bold text-white mb-2">Добро пожаловать!</h1>
                <p className="text-purple-300">Войдите в аккаунт казино</p>
              </div>

              <form onSubmit={handleCasinoLogin} className="space-y-4">
                <div>
                  <Input
                    name="username"
                    placeholder="Имя пользователя"
                    defaultValue="Player123"
                    className="bg-white/10 border-white/20 text-white placeholder:text-white/50 h-12 rounded-xl"
                  />
                </div>
                <div>
                  <Input
                    type="password"
                    placeholder="Пароль"
                    defaultValue="password"
                    className="bg-white/10 border-white/20 text-white placeholder:text-white/50 h-12 rounded-xl"
                  />
                </div>
                <Button 
                  type="submit"
                  className="w-full h-12 rounded-xl bg-gradient-to-r from-yellow-500 to-orange-500 hover:from-yellow-600 hover:to-orange-600 text-white font-bold"
                >
                  Войти
                </Button>
              </form>

              <div className="mt-6 text-center text-sm text-purple-300">
                Тестовый аккаунт — просто нажмите "Войти"
              </div>
              
              <div className="mt-4 p-3 bg-green-500/10 border border-green-500/30 rounded-xl">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-green-300 text-xs">
                    <CheckCircle className="w-4 h-4" />
                    <span>Мерчант: {merchantInfo?.merchant_name || 'Подключен'}</span>
                  </div>
                  <Button
                    onClick={disconnectApiKey}
                    variant="ghost"
                    size="sm"
                    className="text-red-400 hover:text-red-300 text-xs h-6"
                  >
                    Отключить
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 via-violet-900 to-indigo-900">
      {/* Casino Header */}
      <header className="border-b border-white/10 bg-black/20 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-yellow-400 to-orange-500 flex items-center justify-center">
              <Crown className="w-6 h-6 text-white" />
            </div>
            <div>
              <div className="text-lg font-bold text-white">Lucky Vegas</div>
              <div className="text-xs text-green-300 flex items-center gap-1">
                <CheckCircle className="w-3 h-3" />
                {merchantInfo?.merchant_name || 'API подключен'}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {/* API Settings button */}
            <Button
              onClick={() => setShowApiSettings(true)}
              variant="ghost"
              size="sm"
              className="text-purple-300 hover:text-white hover:bg-white/10"
              title="Настройки API"
            >
              <Key className="w-4 h-4 mr-1" />
              <span className="hidden sm:inline">API</span>
            </Button>

            {/* Merchant Balance (USDT received) */}
            <div className="hidden sm:block bg-green-500/20 border border-green-500/30 rounded-xl px-3 py-1">
              <div className="text-xs text-green-300">Получено USDT</div>
              <div className="text-lg font-bold text-green-400">{merchantBalance.toFixed(2)}</div>
            </div>

            {/* History button */}
            <Button
              onClick={openHistory}
              variant="ghost"
              size="sm"
              className="text-purple-300 hover:text-white hover:bg-white/10"
              data-testid="history-btn"
            >
              <History className="w-4 h-4 mr-1" />
              История
            </Button>

            {/* Balance */}
            <div className="bg-black/30 rounded-xl px-4 py-2 flex items-center gap-3">
              <div className="text-right">
                <div className="text-xs text-purple-300">Баланс</div>
                <div className="text-lg font-bold text-yellow-400">{balance.toLocaleString()} ₽</div>
              </div>
              <Button 
                onClick={() => setShowDeposit(true)}
                size="sm"
                className="bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 rounded-lg"
                data-testid="deposit-btn"
              >
                <Wallet className="w-4 h-4 mr-1" />
                Пополнить
              </Button>
            </div>

            {/* User */}
            <div className="flex items-center gap-2">
              <div className="w-9 h-9 rounded-full bg-purple-500 flex items-center justify-center">
                <User className="w-5 h-5 text-white" />
              </div>
              <span className="text-white font-medium hidden sm:block">{casinoUser?.username}</span>
              <button
                onClick={handleLogout}
                className="ml-2 p-2 text-white/50 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                title="Выйти"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-4 py-8">
        {/* Promo Banner */}
        <div className="bg-gradient-to-r from-yellow-500/20 to-orange-500/20 border border-yellow-500/30 rounded-2xl p-6 mb-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-yellow-400 to-orange-500 flex items-center justify-center">
                <Gift className="w-8 h-8 text-white" />
              </div>
              <div>
                <div className="text-xl font-bold text-white">Бонус на первый депозит!</div>
                <div className="text-yellow-300">+100% до 50,000 ₽</div>
              </div>
            </div>
            <Button 
              onClick={() => setShowDeposit(true)}
              className="bg-gradient-to-r from-yellow-500 to-orange-500 hover:from-yellow-600 hover:to-orange-600 rounded-xl h-12 px-6"
            >
              Получить бонус
              <ArrowRight className="w-5 h-5 ml-2" />
            </Button>
          </div>
        </div>

        {/* Games Grid */}
        <div className="mb-8">
          <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
            <Star className="w-5 h-5 text-yellow-400" />
            Популярные игры
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {[
              { name: "Sweet Bonanza", color: "from-pink-500 to-rose-500" },
              { name: "Gates of Olympus", color: "from-blue-500 to-cyan-500" },
              { name: "Book of Dead", color: "from-amber-500 to-yellow-500" },
              { name: "Big Bass", color: "from-green-500 to-emerald-500" },
              { name: "Wolf Gold", color: "from-orange-500 to-red-500" },
              { name: "Starburst", color: "from-purple-500 to-violet-500" },
            ].map((game, i) => (
              <div 
                key={i}
                className={`aspect-square rounded-2xl bg-gradient-to-br ${game.color} p-4 flex flex-col justify-end cursor-pointer hover:scale-105 transition-transform`}
              >
                <div className="text-white font-bold text-sm">{game.name}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Categories */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { icon: Zap, name: "Слоты", count: "2,500+", color: "from-purple-500 to-pink-500" },
            { icon: Trophy, name: "Live Casino", count: "150+", color: "from-emerald-500 to-teal-500" },
            { icon: Sparkles, name: "Джекпоты", count: "50+", color: "from-yellow-500 to-orange-500" },
            { icon: CreditCard, name: "Карточные", count: "100+", color: "from-blue-500 to-indigo-500" },
          ].map((cat, i) => (
            <div 
              key={i}
              className={`bg-gradient-to-br ${cat.color} rounded-2xl p-5 cursor-pointer hover:scale-[1.02] transition-transform`}
            >
              <cat.icon className="w-8 h-8 text-white mb-3" />
              <div className="text-white font-bold">{cat.name}</div>
              <div className="text-white/70 text-sm">{cat.count}</div>
            </div>
          ))}
        </div>
      </main>

      {/* Deposit Modal */}
      {showDeposit && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-gradient-to-br from-slate-900 to-slate-800 border border-white/10 rounded-3xl p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-white">Пополнить баланс</h2>
              <button 
                onClick={() => setShowDeposit(false)}
                className="text-white/50 hover:text-white"
              >
                ✕
              </button>
            </div>

            {/* Quick amounts */}
            <div className="grid grid-cols-5 gap-2 mb-4">
              {quickAmounts.map((amount) => (
                <button
                  key={amount}
                  onClick={() => setDepositAmount(amount.toString())}
                  className={`py-2 rounded-lg text-sm font-medium transition-colors ${
                    depositAmount === amount.toString()
                      ? "bg-green-500 text-white"
                      : "bg-white/10 text-white hover:bg-white/20"
                  }`}
                >
                  {amount >= 1000 ? `${amount/1000}K` : amount}
                </button>
              ))}
            </div>

            {/* Custom amount */}
            <div className="relative mb-6">
              <Input
                type="number"
                value={depositAmount}
                onChange={(e) => setDepositAmount(e.target.value)}
                placeholder="Введите сумму"
                className="bg-white/10 border-white/20 text-white h-14 rounded-xl text-lg pl-4 pr-12"
              />
              <span className="absolute right-4 top-1/2 -translate-y-1/2 text-white/50">₽</span>
            </div>

            {/* Info */}
            <div className="bg-green-500/10 border border-green-500/20 rounded-xl p-4 mb-6">
              <div className="flex items-center gap-2 text-green-400 text-sm">
                <Gift className="w-4 h-4" />
                <span>+100% бонус на депозит!</span>
              </div>
            </div>

            {/* Deposit button */}
            <Button
              onClick={handleDeposit}
              disabled={loading || !depositAmount}
              className="w-full h-14 rounded-xl bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 text-white font-bold text-lg"
              data-testid="confirm-deposit-btn"
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <CreditCard className="w-5 h-5 mr-2" />
                  Пополнить {depositAmount ? `${parseInt(depositAmount).toLocaleString()} ₽` : ""}
                </>
              )}
            </Button>

            <div className="mt-4 text-center text-xs text-white/40">
              Оплата через P2P шлюз (API-интеграция)
            </div>
          </div>
        </div>
      )}

      {/* History Modal */}
      {showHistory && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-gradient-to-br from-slate-900 to-slate-800 border border-white/10 rounded-3xl p-6 w-full max-w-2xl max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <History className="w-5 h-5" />
                История пополнений
              </h2>
              <button 
                onClick={() => setShowHistory(false)}
                className="text-white/50 hover:text-white"
              >
                ✕
              </button>
            </div>

            {/* Merchant Balance Summary */}
            <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4 mb-4">
              <div className="flex items-center justify-between">
                <div className="text-green-300 text-sm">Всего получено (USDT)</div>
                <div className="text-2xl font-bold text-green-400">{merchantBalance.toFixed(2)} USDT</div>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto">
              {loadingHistory ? (
                <div className="flex items-center justify-center py-12">
                  <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : paymentLinks.length === 0 ? (
                <div className="text-center py-12">
                  <Wallet className="w-16 h-16 text-white/20 mx-auto mb-4" />
                  <div className="text-white/50">Нет пополнений</div>
                  <Button
                    onClick={() => { setShowHistory(false); setShowDeposit(true); }}
                    className="mt-4 bg-gradient-to-r from-green-500 to-emerald-500"
                  >
                    Пополнить сейчас
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  {paymentLinks.map((link) => (
                    <div
                      key={link.id}
                      className="bg-white/5 border border-white/10 rounded-xl p-4 hover:bg-white/10 transition-colors"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-green-500 to-emerald-500 flex items-center justify-center">
                            <Wallet className="w-5 h-5 text-white" />
                          </div>
                          <div>
                            <div className="text-white font-medium">
                              Пополнение #{link.id.slice(0, 8)}
                            </div>
                            <div className="text-white/50 text-sm">
                              {formatDate(link.created_at)}
                            </div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-xl font-bold text-green-400">
                            +{link.amount_rub?.toLocaleString()} ₽
                          </div>
                          {getStatusBadge(link)}
                        </div>
                      </div>
                      
                      {/* Show button based on trade status */}
                      {(link.trade_status === "pending" || link.trade_status === "paid" || link.trade_status === "disputed") && (
                        <Button
                          onClick={() => window.open(`/deposit/${link.id}`, '_blank')}
                          size="sm"
                          variant="outline"
                          className={`w-full mt-2 ${
                            link.trade_status === "disputed" 
                              ? "border-red-500/50 text-red-400 hover:bg-red-500/10" 
                              : "border-yellow-500/50 text-yellow-400 hover:bg-yellow-500/10"
                          }`}
                        >
                          <ArrowRight className="w-4 h-4 mr-2" />
                          {link.trade_status === "disputed" ? "Вернуться к спору" : 
                           link.trade_status === "paid" ? "Проверить статус" : 
                           "Продолжить оплату"}
                        </Button>
                      )}
                      
                      {link.status === "active" && !link.trade_id && (
                        <Button
                          onClick={() => window.open(`/deposit/${link.id}`, '_blank')}
                          size="sm"
                          variant="outline"
                          className="w-full mt-2 border-yellow-500/50 text-yellow-400 hover:bg-yellow-500/10"
                        >
                          <ArrowRight className="w-4 h-4 mr-2" />
                          Начать оплату
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="mt-4 pt-4 border-t border-white/10">
              <Button
                onClick={fetchPaymentHistory}
                variant="outline"
                className="w-full border-white/20 text-white/70 hover:bg-white/10"
              >
                Обновить
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
