import { useState, useEffect, useRef } from "react";
import { Routes, Route, Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { useAuth, API } from "@/App";
import axios from "axios";
import { 
  Wallet, LogOut, LayoutDashboard, ListOrdered, History, Settings, Plus, 
  TrendingUp, DollarSign, CheckCircle, XCircle, Clock, ArrowUpRight, CreditCard,
  MessageCircle, ExternalLink, Home, Users, Copy, Link2, Store, Send, Search, 
  ArrowLeft, Check, CheckCheck, ShoppingBag, ArrowDownRight, Shield, AlertTriangle,
  ChevronDown, ChevronRight, ChevronLeft, User, Calendar, Lock, Key, Eye, EyeOff, Trash2,
  Play, Pause, Download, Loader
} from "lucide-react";
import RequisitesPage from "./RequisitesPage";
import TraderTradePage from "./TraderTradePage";
import BuyerTradePage from "./BuyerTradePage";
import TraderShop from "./TraderShop";
import MyMessagesPage from "./MyMessagesPage";

const merchantTypeLabels = {
  casino: "Казино",
  shop: "Магазин",
  stream: "Стрим",
  other: "Другое"
};

export default function TraderDashboard() {
  const { user, token, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [balance, setBalance] = useState(null);
  const [traderInfo, setTraderInfo] = useState(null);
  const [sidebarBadges, setSidebarBadges] = useState({});
  
  // Collapsible sections state
  const [expandedSections, setExpandedSections] = useState({
    trading: true,
    market: false,
    finances: false,
    other: false,
    account: false
  });

  const toggleSection = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  // Fetch sidebar badges
  useEffect(() => {
    const fetchBadges = async () => {
      try {
        const response = await axios.get(`${API}/notifications/sidebar-badges`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setSidebarBadges(response.data);
      } catch (error) {
        console.error("Failed to fetch badges:", error);
      }
    };
    
    if (token) {
      fetchBadges();
      const interval = setInterval(fetchBadges, 30000); // Refresh every 30 sec
      return () => clearInterval(interval);
    }
  }, [token]);

  // Fetch balance and trader info on mount
  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await axios.get(`${API}/traders/me`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setBalance(response.data.balance_usdt);
        setTraderInfo(response.data);
      } catch (error) {
        console.error("Failed to fetch data:", error);
      }
    };
    
    // Heartbeat to update online status
    const heartbeat = async () => {
      try {
        await axios.post(`${API}/users/heartbeat`, {}, {
          headers: { Authorization: `Bearer ${token}` }
        });
      } catch (error) {
        console.error("Heartbeat failed:", error);
      }
    };

    fetchData();
    heartbeat();
    
    const interval = setInterval(() => {
      fetchData();
      heartbeat();
    }, 30000);
    return () => clearInterval(interval);
  }, [token]);

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  // Badge component for sidebar
  const Badge = ({ count }) => {
    if (!count || count === 0) return null;
    return (
      <span className="ml-auto bg-[#EF4444] text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center">
        {count > 99 ? "99+" : count}
      </span>
    );
  };

  // Navigation sections with collapsible items
  const sections = [
    {
      key: "trading",
      title: "Торговля",
      icon: TrendingUp,
      notifyKey: "trades",
      items: [
        { path: "/trader/offers", icon: ListOrdered, label: "Объявления" },
        { path: "/trader/sales", icon: TrendingUp, label: "Продажи", notifyKey: "trades" },
        { path: "/trader/purchases", icon: DollarSign, label: "Покупки", notifyKey: "trades" },
        { path: "/trader/requisites", icon: CreditCard, label: "Реквизиты" },
        { path: "/trader/history", icon: History, label: "История" },
        { path: "/trader/trading-stats", icon: TrendingUp, label: "Статистика" },
        { path: "/trader/trading-settings", icon: Settings, label: "Настройки" }
      ]
    },
    {
      key: "buy-crypto",
      title: "Купить USDT",
      icon: DollarSign,
      single: true,
      path: "/buy-crypto",
      external: true
    },
    {
      key: "market",
      title: "Маркет",
      icon: Store,
      notifyKey: "purchases",
      items: [
        { path: "/marketplace", icon: Store, label: "Каталог", external: true },
        { path: "/trader/my-purchases", icon: ShoppingBag, label: "Мои покупки", notifyKey: "purchases" },
        { path: "/trader/shop", icon: Store, label: "Мой магазин", notifyKey: "shop_messages" }
      ]
    },
    {
      key: "finances",
      title: "Финансы",
      icon: Wallet,
      items: [
        { path: "/trader", icon: Wallet, label: "Баланс", exact: true },
        { path: "/trader/transactions", icon: History, label: "Транзакции" },
        { path: "/trader/transfers", icon: ArrowUpRight, label: "Переводы" }
      ]
    },
    {
      key: "messages",
      title: "Сообщения",
      icon: MessageCircle,
      notifyKey: "messages",
      single: true,
      path: "/trader/messages"
    },
    {
      key: "referral",
      title: "Рефералы",
      icon: Users,
      single: true,
      path: "/trader/referral"
    },
    {
      key: "account",
      title: "Аккаунт",
      icon: User,
      items: [
        { path: "/trader/account", icon: User, label: "Профиль" },
        { path: "/trader/settings", icon: Settings, label: "Настройки" }
      ]
    }
  ];

  const isActive = (path, exact) => {
    if (exact) return location.pathname === path;
    return location.pathname === path || location.pathname.startsWith(path + "/");
  };

  // Check if any item in section is active
  const isSectionActive = (section) => {
    return section.items.some(item => isActive(item.path, item.exact));
  };

  return (
    <div className="min-h-screen bg-[#0A0A0A] flex">
      {/* Sidebar */}
      <aside className="w-64 bg-[#121212] border-r border-white/5 hidden lg:flex flex-col h-screen sticky top-0 overflow-y-auto">
        {/* Header with Logo */}
        <div className="p-5 border-b border-white/5">
          <Link to="/" className="flex items-center gap-3">
            <img src="/logo.jpg" alt="Reptiloid" className="h-10 w-10 rounded-lg" />
            <div>
              <div className="text-white font-semibold font-['Unbounded'] text-sm">Reptiloid</div>
              <div className="text-xs text-[#52525B]">Личный кабинет</div>
            </div>
          </Link>
        </div>

        {/* Balance Card - Inside sidebar, not floating */}
        <div className="p-4 border-b border-white/5">
          <div className="bg-gradient-to-br from-[#7C3AED]/20 to-[#A855F7]/10 border border-[#7C3AED]/30 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-[#A78BFA]">Баланс</span>
              {sidebarBadges.total > 0 && (
                <span className="text-xs text-[#EF4444] bg-[#EF4444]/10 px-2 py-0.5 rounded-full">
                  {sidebarBadges.total} событий
                </span>
              )}
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-white font-['JetBrains_Mono']">
                {balance !== null ? balance.toFixed(2) : "—"}
              </span>
              <span className="text-sm text-[#71717A]">USDT</span>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {/* Home Link */}
          <Link
            to="/"
            className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-[#A1A1AA] hover:bg-white/5 hover:text-white transition-colors"
          >
            <Home className="w-4 h-4" />
            <span className="text-sm font-medium">Главная</span>
          </Link>

          {/* Collapsible Sections */}
          {sections.map((section) => (
            <div key={section.key}>
              {section.single ? (
                /* Single Item (not collapsible) */
                <Link
                  to={section.path}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-colors ${
                    location.pathname.startsWith(section.path)
                      ? "bg-[#7C3AED]/10 text-[#A78BFA]" 
                      : "text-[#A1A1AA] hover:bg-white/5 hover:text-white"
                  }`}
                >
                  <section.icon className="w-4 h-4" />
                  <span className="text-sm font-medium">{section.title}</span>
                </Link>
              ) : (
                <>
                  {/* Section Header */}
                  <button
                    onClick={() => toggleSection(section.key)}
                    className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl transition-colors ${
                      isSectionActive(section) 
                        ? "bg-[#7C3AED]/10 text-[#A78BFA]" 
                        : "text-[#A1A1AA] hover:bg-white/5 hover:text-white"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <section.icon className="w-4 h-4" />
                      <span className="text-sm font-medium">{section.title}</span>
                      {section.notifyKey && <Badge count={sidebarBadges[section.notifyKey]} />}
                    </div>
                    {expandedSections[section.key] ? (
                      <ChevronDown className="w-4 h-4" />
                    ) : (
                      <ChevronRight className="w-4 h-4" />
                    )}
                  </button>

                  {/* Section Items */}
                  {expandedSections[section.key] && (
                    <div className="ml-4 mt-1 space-y-0.5 border-l border-white/10 pl-3">
                      {section.items.map((item) => (
                        <Link
                          key={item.path}
                          to={item.path}
                          className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors text-sm ${
                            isActive(item.path, item.exact)
                              ? "bg-[#7C3AED]/15 text-[#A78BFA]"
                              : "text-[#71717A] hover:bg-white/5 hover:text-white"
                          }`}
                        >
                          <item.icon className="w-3.5 h-3.5" />
                          <span>{item.label}</span>
                          {item.notifyKey && <Badge count={sidebarBadges[item.notifyKey]} />}
                          {item.external && <ExternalLink className="w-3 h-3 ml-auto opacity-50" />}
                        </Link>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          ))}
        </nav>

        {/* User Info at Bottom */}
        <div className="p-4 border-t border-white/5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#10B981] to-[#059669] flex items-center justify-center text-white font-bold">
              {(user?.nickname || user?.login || "U")[0].toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-white font-medium text-sm truncate">@{user?.nickname || user?.login}</div>
              <div className="text-[10px] text-[#52525B]">
                {traderInfo?.created_at ? `с ${new Date(traderInfo.created_at).toLocaleDateString("ru-RU")}` : ""}
              </div>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-[#EF4444]/70 hover:bg-[#EF4444]/10 hover:text-[#EF4444] transition-colors w-full text-sm"
            data-testid="logout-btn"
          >
            <LogOut className="w-4 h-4" />
            <span>Выйти</span>
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-6 lg:p-8 overflow-y-auto">
        <Routes>
          <Route index element={<TraderBalance />} />
          <Route path="requisites" element={<RequisitesPage />} />
          <Route path="offers" element={<TraderOffers />} />
          <Route path="sales" element={<TraderSales />} />
          <Route path="sales/:tradeId" element={<TraderTradePage />} />
          <Route path="purchases" element={<TraderPurchases />} />
          <Route path="purchases/:tradeId" element={<BuyerTradePage />} />
          <Route path="history" element={<TraderHistory />} />
          <Route path="history/sales" element={<TraderHistorySales />} />
          <Route path="history/purchases" element={<TraderHistoryPurchases />} />
          <Route path="transactions" element={<TraderTransactions />} />
          <Route path="trading-stats" element={<TradingStats />} />
          <Route path="trading-settings" element={<TradingSettings />} />
          <Route path="shop" element={<TraderShop />} />
          <Route path="my-purchases" element={<MyMarketPurchases />} />
          <Route path="transfers" element={<TraderTransfers />} />
          <Route path="messages" element={<MyMessagesPage />} />
          <Route path="referral" element={<TraderReferral />} />
          <Route path="settings" element={<TraderSettings />} />
          <Route path="account" element={<TraderAccount />} />
        </Routes>
      </main>
    </div>
  );
}

function TraderStats() {
  const { user, token } = useAuth();
  const [trader, setTrader] = useState(null);
  const [stats, setStats] = useState({ salesCount: 0, purchasesCount: 0, salesVolume: 0, purchasesVolume: 0 });
  const [depositAmount, setDepositAmount] = useState("");
  const [depositOpen, setDepositOpen] = useState(false);

  const fetchTrader = async () => {
    try {
      const response = await axios.get(`${API}/traders/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTrader(response.data);
    } catch (error) {
      console.error(error);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API}/traders/stats`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setStats(response.data);
    } catch (error) {
      console.error(error);
    }
  };

  useEffect(() => {
    if (token) {
      fetchTrader();
      fetchStats();
    }
  }, [token]);

  const handleDeposit = async () => {
    const amount = parseFloat(depositAmount);
    if (isNaN(amount) || amount <= 0) {
      toast.error("Введите корректную сумму");
      return;
    }
    try {
      await axios.post(`${API}/traders/deposit?amount=${amount}`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(`Пополнено ${amount} USDT`);
      setDepositOpen(false);
      setDepositAmount("");
      fetchTrader();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка пополнения");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white font-['Unbounded']">Статистика</h1>
        <Dialog open={depositOpen} onOpenChange={setDepositOpen}>
          <DialogTrigger asChild>
            <Button className="bg-[#10B981] hover:bg-[#059669] text-white rounded-full px-6" data-testid="deposit-btn">
              <Plus className="w-4 h-4 mr-2" />
              Пополнить
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-[#121212] border-white/10 text-white">
            <DialogHeader>
              <DialogTitle className="font-['Unbounded']">Пополнение баланса</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 pt-4">
              <div className="p-4 bg-[#7C3AED]/10 border border-[#7C3AED]/20 rounded-xl text-sm text-[#A1A1AA]">
                Для тестирования: введите сумму и нажмите "Пополнить".
              </div>
              <div className="space-y-2">
                <Label className="text-[#A1A1AA]">Сумма USDT</Label>
                <Input
                  type="number"
                  placeholder="100"
                  value={depositAmount}
                  onChange={(e) => setDepositAmount(e.target.value)}
                  className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl"
                />
              </div>
              <Button onClick={handleDeposit} className="w-full bg-[#10B981] hover:bg-[#059669] h-12 rounded-xl">
                Пополнить
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Balance Card */}
      <div className="bg-gradient-to-br from-[#7C3AED] to-[#A855F7] rounded-2xl p-6">
        <div className="text-white/70 text-sm mb-1">Ваш баланс</div>
        <div className="text-4xl font-bold text-white font-['JetBrains_Mono']" data-testid="trader-balance">
          {trader?.balance_usdt?.toFixed(2) || "0.00"} <span className="text-xl text-white/70">USDT</span>
        </div>
        <div className="text-sm text-white/50 mt-2">Комиссия платформы: {trader?.commission_rate || 1}%</div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Продаж</div>
          <div className="text-2xl font-bold text-white">{stats.salesCount || 0}</div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Объем продаж</div>
          <div className="text-2xl font-bold text-[#10B981] font-['JetBrains_Mono']">{(stats.salesVolume || 0).toFixed(0)} <span className="text-sm">USDT</span></div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Покупок</div>
          <div className="text-2xl font-bold text-white">{stats.purchasesCount || 0}</div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Объем покупок</div>
          <div className="text-2xl font-bold text-[#7C3AED] font-['JetBrains_Mono']">{(stats.purchasesVolume || 0).toFixed(0)} <span className="text-sm">USDT</span></div>
        </div>
      </div>

      {/* Quick Links */}
      <div className="grid sm:grid-cols-2 gap-4">
        <Link to="/trader/offers">
          <div className="bg-[#121212] border border-white/5 hover:border-[#7C3AED]/50 rounded-2xl p-5 transition-colors">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-[#7C3AED]/10 flex items-center justify-center">
                <ListOrdered className="w-5 h-5 text-[#7C3AED]" />
              </div>
              <div>
                <div className="text-white font-medium">Мои объявления</div>
                <div className="text-sm text-[#71717A]">Управление офферами</div>
              </div>
            </div>
          </div>
        </Link>
        <Link to="/">
          <div className="bg-[#121212] border border-white/5 hover:border-[#10B981]/50 rounded-2xl p-5 transition-colors">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-[#10B981]/10 flex items-center justify-center">
                <TrendingUp className="w-5 h-5 text-[#10B981]" />
              </div>
              <div>
                <div className="text-white font-medium">Купить USDT</div>
                <div className="text-sm text-[#71717A]">Перейти на главную</div>
              </div>
            </div>
          </div>
        </Link>
      </div>
    </div>
  );
}

function TraderOffers() {
  const { token } = useAuth();
  const [offers, setOffers] = useState([]);
  const [requisites, setRequisites] = useState([]);
  const [balance, setBalance] = useState(0);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [newOffer, setNewOffer] = useState({
    amount_usdt: "",
    min_amount: "",
    max_amount: "",
    price_rub: "",
    accepted_merchant_types: ["casino", "shop", "stream", "other"],
    requisite_ids: [],
    conditions: ""
  });

  useEffect(() => {
    fetchOffers();
    fetchRequisites();
    fetchBalance();
  }, []);

  const fetchBalance = async () => {
    try {
      const response = await axios.get(`${API}/traders/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setBalance(response.data.balance_usdt || 0);
    } catch (error) {
      console.error(error);
    }
  };

  const fetchRequisites = async () => {
    try {
      const response = await axios.get(`${API}/requisites`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setRequisites(response.data);
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
      toast.error("Заполните все поля");
      return;
    }
    if (newOffer.requisite_ids.length === 0) {
      toast.error("Выберите хотя бы один реквизит для приёма платежей");
      return;
    }
    
    // Check for duplicate requisite types
    const selectedRequisites = newOffer.requisite_ids.map(id => requisites.find(r => r.id === id)).filter(Boolean);
    const types = selectedRequisites.map(r => r.type);
    const uniqueTypes = new Set(types);
    if (types.length !== uniqueTypes.size) {
      toast.error("Можно выбрать только один реквизит каждого типа");
      return;
    }

    // Determine payment methods from selected requisites
    const paymentMethods = [];
    newOffer.requisite_ids.forEach(reqId => {
      const req = requisites.find(r => r.id === reqId);
      if (req) {
        if (req.type === "card") paymentMethods.push(req.data.bank_name?.toLowerCase() || "card");
        if (req.type === "sbp") paymentMethods.push("sbp");
        if (req.type === "qr") paymentMethods.push("sbp_qr");
        if (req.type === "sim") paymentMethods.push("sim");
        if (req.type === "cis") paymentMethods.push("cis_" + (req.data.country?.toLowerCase() || "cis"));
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
        accepted_merchant_types: newOffer.accepted_merchant_types,
        requisite_ids: newOffer.requisite_ids,
        conditions: newOffer.conditions || null
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Объявление создано");
      setCreateOpen(false);
      setNewOffer({
        amount_usdt: "",
        min_amount: "",
        max_amount: "",
        price_rub: "",
        accepted_merchant_types: ["casino", "shop", "stream", "other"],
        requisite_ids: [],
        conditions: ""
      });
      fetchOffers();
      fetchBalance(); // Update balance after creating offer
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка создания");
    }
  };

  const handleDeleteOffer = async (offerId) => {
    try {
      await axios.delete(`${API}/offers/${offerId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Объявление удалено");
      fetchOffers();
      fetchBalance(); // Update balance after deleting offer
    } catch (error) {
      toast.error("Ошибка удаления");
    }
  };

  const toggleRequisite = (requisiteId) => {
    setNewOffer(prev => ({
      ...prev,
      requisite_ids: prev.requisite_ids.includes(requisiteId)
        ? prev.requisite_ids.filter(id => id !== requisiteId)
        : [...prev.requisite_ids, requisiteId]
    }));
  };

  const toggleMerchantType = (typeId) => {
    setNewOffer(prev => ({
      ...prev,
      accepted_merchant_types: prev.accepted_merchant_types.includes(typeId)
        ? prev.accepted_merchant_types.filter(t => t !== typeId)
        : [...prev.accepted_merchant_types, typeId]
    }));
  };

  const requisiteTypeLabels = {
    card: { name: "Банковская карта", emoji: "💳", color: "#7C3AED" },
    sbp: { name: "СБП", emoji: "⚡", color: "#10B981" },
    qr: { name: "QR-код", emoji: "📱", color: "#3B82F6" },
    sim: { name: "SIM баланс", emoji: "📞", color: "#F59E0B" },
    cis: { name: "Перевод СНГ", emoji: "🌍", color: "#EC4899" }
  };

  const getRequisiteDisplayName = (req) => {
    const typeInfo = requisiteTypeLabels[req.type];
    if (!typeInfo) return req.type;
    if (req.type === "card") {
      return `${typeInfo.emoji} ${req.data.bank_name} •••• ${req.data.card_number?.slice(-4) || ""}`;
    }
    if (req.type === "sbp") {
      return `${typeInfo.emoji} СБП ${req.data.phone}`;
    }
    if (req.type === "qr") {
      return `${typeInfo.emoji} QR-код ${req.data.bank_name}`;
    }
    if (req.type === "sim") {
      return `${typeInfo.emoji} ${req.data.operator} ${req.data.phone}`;
    }
    if (req.type === "cis") {
      return `${typeInfo.emoji} ${req.data.country} ${req.data.bank_name}`;
    }
    return `${typeInfo.emoji} ${typeInfo.name}`;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white font-['Unbounded']">Мои объявления</h1>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button className="bg-[#7C3AED] hover:bg-[#6D28D9] rounded-full px-6" data-testid="create-offer-btn">
              <Plus className="w-4 h-4 mr-2" />
              Создать
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-[#121212] border-white/10 text-white max-w-lg max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="font-['Unbounded']">Создать объявление</DialogTitle>
            </DialogHeader>
            <div className="space-y-5 pt-4">
              {/* Platform commission notice */}
              <div className="p-4 bg-[#F59E0B]/10 border border-[#F59E0B]/20 rounded-xl">
                <div className="flex items-center gap-2 text-[#F59E0B]">
                  <DollarSign className="w-5 h-5" />
                  <span className="font-medium">Комиссия платформы: 1.0%</span>
                </div>
                <p className="text-sm text-[#A1A1AA] mt-1">(будет списана при завершении сделки)</p>
              </div>

              <div className="space-y-2">
                <Label className="text-[#A1A1AA]">Сумма к продаже (USDT)</Label>
                <Input
                  type="number"
                  placeholder="1000"
                  value={newOffer.amount_usdt}
                  onChange={(e) => setNewOffer({ ...newOffer, amount_usdt: e.target.value })}
                  className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl"
                  data-testid="offer-amount-usdt"
                />
                <p className="text-xs text-[#71717A]">Эта сумма будет зарезервирована из вашего баланса</p>
              </div>

              {/* Limits */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-[#A1A1AA]">Мин. за сделку (USDT)</Label>
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
                  <Label className="text-[#A1A1AA]">Макс. за сделку (USDT)</Label>
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
                <Label className="text-[#A1A1AA]">Курс (RUB за 1 USDT)</Label>
                <Input
                  type="number"
                  placeholder="92.50"
                  value={newOffer.price_rub}
                  onChange={(e) => setNewOffer({ ...newOffer, price_rub: e.target.value })}
                  className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl"
                  data-testid="offer-price"
                />
              </div>

              {/* Requisites selection */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label className="text-[#A1A1AA]">Реквизиты для приёма платежей</Label>
                  <Link to="/trader/requisites" className="text-xs text-[#7C3AED] hover:underline">
                    + Добавить новые
                  </Link>
                </div>
                
                {requisites.length === 0 ? (
                  <div className="p-6 border border-dashed border-white/10 rounded-xl text-center">
                    <CreditCard className="w-10 h-10 text-[#52525B] mx-auto mb-3" />
                    <p className="text-[#71717A] mb-3">У вас нет сохранённых реквизитов</p>
                    <Link to="/trader/requisites">
                      <Button variant="outline" size="sm" className="border-[#7C3AED]/50 text-[#7C3AED]">
                        Добавить реквизиты
                      </Button>
                    </Link>
                  </div>
                ) : (
                  <div className="space-y-2 max-h-[280px] overflow-y-auto pr-1">
                    {Object.entries(requisiteTypeLabels).map(([typeId, typeInfo]) => {
                      const typeRequisites = requisites.filter(r => r.type === typeId);
                      if (typeRequisites.length === 0) return null;
                      
                      return (
                        <div key={typeId}>
                          <div className="text-xs text-[#52525B] mb-2">{typeInfo.emoji} {typeInfo.name}</div>
                          <div className="space-y-2">
                            {typeRequisites.map((req) => (
                              <div
                                key={req.id}
                                onClick={() => toggleRequisite(req.id)}
                                className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${
                                  newOffer.requisite_ids.includes(req.id)
                                    ? "border-[#10B981] bg-[#10B981]/10"
                                    : "border-white/10 hover:border-white/20"
                                }`}
                              >
                                <Checkbox checked={newOffer.requisite_ids.includes(req.id)} />
                                <span className="text-sm flex-1">{getRequisiteDisplayName(req)}</span>
                                {req.is_primary && (
                                  <span className="text-xs bg-[#7C3AED]/20 text-[#A855F7] px-2 py-0.5 rounded">Основной</span>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Conditions/Rules section */}
              <div className="space-y-2">
                <Label className="text-[#A1A1AA]">Условия и правила (необязательно)</Label>
                <textarea
                  placeholder="Например: Перевод только с карты на имя владельца. Без комментариев к переводу."
                  value={newOffer.conditions}
                  onChange={(e) => setNewOffer({ ...newOffer, conditions: e.target.value })}
                  className="w-full bg-[#1A1A1A] border border-white/10 text-white rounded-xl p-3 min-h-[80px] resize-none text-sm placeholder:text-[#52525B]"
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-2 mb-2">
                  <Checkbox checked={true} disabled />
                  <Label className="text-[#A1A1AA]">Принимать платежи от мерчантов</Label>
                </div>
                <Label className="text-[#71717A] text-sm">Принимать типы мерчантов:</Label>
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(merchantTypeLabels).map(([id, name]) => {
                    const commissions = { casino: "0.5%", shop: "0.3%", stream: "0.4%", other: "0.6%" };
                    return (
                      <div
                        key={id}
                        onClick={() => toggleMerchantType(id)}
                        className={`flex items-center gap-2 p-3 rounded-xl border cursor-pointer transition-colors ${
                          newOffer.accepted_merchant_types.includes(id)
                            ? "border-[#10B981] bg-[#10B981]/10"
                            : "border-white/10 hover:border-white/20"
                        }`}
                      >
                        <Checkbox checked={newOffer.accepted_merchant_types.includes(id)} />
                        <div className="flex-1">
                          <span className="text-sm">{name}</span>
                          <span className="text-xs text-[#71717A] ml-1">(комиссия {commissions[id]})</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <Button onClick={handleCreateOffer} className="w-full bg-[#7C3AED] hover:bg-[#6D28D9] h-12 rounded-xl" data-testid="submit-offer-btn">
                Создать объявление
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
          <p className="text-[#71717A]">У вас пока нет объявлений</p>
        </div>
      ) : (
        <div className="space-y-4">
          {offers.filter(o => o.is_active || o.paused_by_admin).map((offer) => (
            <div key={offer.id} className={`bg-[#121212] border rounded-2xl p-6 ${offer.paused_by_admin ? 'border-[#F59E0B]/30' : 'border-white/5'}`} data-testid="offer-card">
              <div className="flex items-start justify-between">
                <div className="space-y-3">
                  <div className="flex items-center gap-4">
                    <div className="text-2xl font-bold text-white font-['JetBrains_Mono']">
                      {offer.price_rub} <span className="text-[#71717A] text-lg">RUB/USDT</span>
                    </div>
                    {offer.paused_by_admin ? (
                      <span className="px-2 py-1 bg-[#F59E0B]/10 text-[#F59E0B] text-xs rounded-full font-medium flex items-center gap-1" title="Приостановлено модератором">
                        <Pause className="w-3 h-3" />
                        На паузе
                      </span>
                    ) : (
                      <span className="px-2 py-1 bg-[#10B981]/10 text-[#10B981] text-xs rounded-full font-medium flex items-center gap-1">
                        <Play className="w-3 h-3" />
                        Активно
                      </span>
                    )}
                  </div>
                  {offer.paused_by_admin && offer.admin_pause_reason && (
                    <div className="text-xs text-[#F59E0B] bg-[#F59E0B]/5 px-3 py-2 rounded-lg">
                      ⚠️ Причина: {offer.admin_pause_reason}
                    </div>
                  )}
                  <div className="flex gap-4 text-sm text-[#A1A1AA]">
                    <span>Доступно: <span className="text-white font-medium">{offer.available_usdt || offer.amount_usdt}</span> / {offer.amount_usdt} USDT</span>
                    <span className="text-[#52525B]">•</span>
                    <span>Лимит: {offer.min_amount || 1} - {offer.max_amount || offer.amount_usdt} USDT</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {offer.requisites?.map((req) => (
                      <span key={req.id} className="px-2 py-1 bg-white/5 text-[#A1A1AA] text-xs rounded-lg">
                        {getRequisiteDisplayName(req)}
                      </span>
                    ))}
                    {!offer.requisites?.length && offer.payment_methods?.map((method) => (
                      <span key={method} className="px-2 py-1 bg-white/5 text-[#A1A1AA] text-xs rounded-lg">
                        {method}
                      </span>
                    ))}
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleDeleteOffer(offer.id)}
                  className="text-[#EF4444] hover:text-[#EF4444] hover:bg-[#EF4444]/10"
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

function TraderSales() {
  const { token, user } = useAuth();
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTrades();
  }, []);

  const fetchTrades = async () => {
    try {
      const response = await axios.get(`${API}/trades/sales/active`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTrades(response.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async (tradeId) => {
    try {
      await axios.post(`${API}/trades/${tradeId}/confirm`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Сделка подтверждена");
      fetchTrades();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка");
    }
  };

  const handleCancel = async (tradeId) => {
    try {
      await axios.post(`${API}/trades/${tradeId}/cancel`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Сделка отменена");
      fetchTrades();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка");
    }
  };

  const getStatusBadge = (status) => {
    const styles = {
      pending: "bg-[#F59E0B]/10 text-[#F59E0B]",
      paid: "bg-[#3B82F6]/10 text-[#3B82F6]",
      completed: "bg-[#10B981]/10 text-[#10B981]",
      cancelled: "bg-[#EF4444]/10 text-[#EF4444]",
      disputed: "bg-[#EF4444]/10 text-[#EF4444]"
    };
    const labels = {
      pending: "Ожидает оплаты",
      paid: "Покупатель оплатил!",
      completed: "Завершена",
      cancelled: "Отменена",
      disputed: "Спор"
    };
    return (
      <span className={`px-2 py-1 text-xs rounded-full font-medium ${styles[status] || styles.pending}`}>
        {labels[status] || status}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white font-['Unbounded']">Мои продажи</h1>
      <p className="text-[#71717A]">Сделки, где вы продаёте USDT</p>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="spinner" />
        </div>
      ) : trades.length === 0 ? (
        <div className="text-center py-12">
          <TrendingUp className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
          <p className="text-[#71717A]">Продаж пока нет</p>
        </div>
      ) : (
        <div className="space-y-4">
          {trades.map((trade) => (
            <div key={trade.id} className="bg-[#121212] border border-white/5 rounded-2xl p-6" data-testid="trade-card">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <Link to={`/trader/sales/${trade.id}`} className="text-sm text-[#71717A] font-['JetBrains_Mono'] hover:text-[#7C3AED]">
                    #{trade.id}
                  </Link>
                  <div className="text-xl font-bold text-white mt-1">
                    -{trade.amount_usdt} USDT
                  </div>
                  <div className="text-sm text-[#71717A] mt-1">
                    Покупатель: {trade.buyer_type === "trader" ? `@${trade.buyer_login || "Трейдер"}` : "Клиент"}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {getStatusBadge(trade.status)}
                  {(trade.status === "pending" || trade.status === "paid" || trade.status === "disputed") && (
                    <Link to={`/trader/sales/${trade.id}`}>
                      <Button size="sm" variant="ghost" className="text-[#7C3AED] hover:bg-[#7C3AED]/10">
                        <ExternalLink className="w-4 h-4" />
                      </Button>
                    </Link>
                  )}
                </div>
              </div>
              
              {trade.status === "paid" && (
                <div className="bg-[#3B82F6]/10 border border-[#3B82F6]/20 rounded-xl p-3 mb-4">
                  <div className="flex items-center gap-2 text-[#3B82F6]">
                    <MessageCircle className="w-4 h-4" />
                    <span className="font-medium text-sm">Покупатель отметил оплату! Проверьте поступление.</span>
                  </div>
                </div>
              )}
              
              {trade.status === "disputed" && (
                <div className="bg-[#EF4444]/10 border border-[#EF4444]/20 rounded-xl p-3 mb-4">
                  <div className="flex items-center gap-2 text-[#EF4444]">
                    <AlertTriangle className="w-4 h-4" />
                    <span className="font-medium text-sm">Спор открыт! Администратор рассмотрит.</span>
                  </div>
                </div>
              )}
              
              <div className="grid grid-cols-4 gap-4 text-sm mb-4">
                <div>
                  <div className="text-[#71717A]">Курс</div>
                  <div className="text-white font-medium">{trade.price_rub} RUB</div>
                </div>
                <div>
                  <div className="text-[#71717A]">Получите</div>
                  <div className="text-white font-medium">{trade.amount_rub?.toLocaleString()} ₽</div>
                </div>
                <div>
                  <div className="text-[#71717A]">Комиссия</div>
                  <div className="text-[#F59E0B] font-medium">{trade.trader_commission} USDT</div>
                </div>
                <div>
                  <div className="text-[#71717A]">Дата</div>
                  <div className="text-white text-xs">{new Date(trade.created_at).toLocaleDateString()}</div>
                </div>
              </div>

              {(trade.status === "pending" || trade.status === "paid" || trade.status === "disputed") && (
                <div className="flex gap-3">
                  <Link to={`/trader/sales/${trade.id}`} className="flex-1">
                    <Button className="w-full bg-[#7C3AED] hover:bg-[#6D28D9] h-10 rounded-xl">
                      <MessageCircle className="w-4 h-4 mr-2" />
                      Открыть
                    </Button>
                  </Link>
                  {(trade.status === "paid" || trade.status === "disputed") && (
                    <Button onClick={() => handleConfirm(trade.id)} className="bg-[#10B981] hover:bg-[#059669] h-10 rounded-xl px-6">
                      <CheckCircle className="w-4 h-4 mr-2" />
                      Подтвердить
                    </Button>
                  )}
                  {trade.status === "pending" && (
                    <Button onClick={() => handleCancel(trade.id)} variant="outline" className="border-[#EF4444]/50 text-[#EF4444] hover:bg-[#EF4444]/10 h-10 rounded-xl">
                      <XCircle className="w-4 h-4" />
                    </Button>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TraderPurchases() {
  const { token, user } = useAuth();
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTrades();
  }, []);

  const fetchTrades = async () => {
    try {
      const response = await axios.get(`${API}/trades/purchases/active`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTrades(response.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    const styles = {
      pending: "bg-[#F59E0B]/10 text-[#F59E0B]",
      paid: "bg-[#3B82F6]/10 text-[#3B82F6]",
      completed: "bg-[#10B981]/10 text-[#10B981]",
      cancelled: "bg-[#EF4444]/10 text-[#EF4444]",
      disputed: "bg-[#EF4444]/10 text-[#EF4444]"
    };
    const labels = {
      pending: "Ожидает вашей оплаты",
      paid: "Ожидает подтверждения",
      completed: "Завершена",
      cancelled: "Отменена",
      disputed: "Спор"
    };
    return (
      <span className={`px-2 py-1 text-xs rounded-full font-medium ${styles[status] || styles.pending}`}>
        {labels[status] || status}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white font-['Unbounded']">Мои покупки</h1>
          <p className="text-[#71717A]">Сделки, где вы покупаете USDT</p>
        </div>
        <Link to="/">
          <Button className="bg-[#10B981] hover:bg-[#059669] rounded-full px-6">
            Купить ещё
          </Button>
        </Link>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="spinner" />
        </div>
      ) : trades.length === 0 ? (
        <div className="text-center py-12">
          <History className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
          <p className="text-[#71717A]">Покупок пока нет</p>
          <Link to="/">
            <Button className="mt-4 bg-[#7C3AED] hover:bg-[#6D28D9] rounded-full px-6">
              Перейти на главную
            </Button>
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {trades.map((trade) => (
            <div key={trade.id} className="bg-[#121212] border border-white/5 rounded-2xl p-6" data-testid="purchase-card">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <Link to={`/trader/purchases/${trade.id}`} className="text-sm text-[#71717A] font-['JetBrains_Mono'] hover:text-[#7C3AED]">
                    #{trade.id}
                  </Link>
                  <div className="text-xl font-bold text-[#10B981] mt-1">
                    +{trade.amount_usdt.toFixed(2)} USDT
                  </div>
                  <div className="text-sm text-[#71717A] mt-1">
                    Продавец: @{trade.seller_login || trade.trader_login || "Трейдер"}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {getStatusBadge(trade.status)}
                  {(trade.status === "pending" || trade.status === "paid" || trade.status === "disputed") && (
                    <Link to={`/trader/purchases/${trade.id}`}>
                      <Button size="sm" variant="ghost" className="text-[#7C3AED] hover:bg-[#7C3AED]/10">
                        <ExternalLink className="w-4 h-4" />
                      </Button>
                    </Link>
                  )}
                </div>
              </div>
              
              {trade.status === "pending" && (
                <div className="bg-[#F59E0B]/10 border border-[#F59E0B]/20 rounded-xl p-3 mb-4">
                  <div className="flex items-center gap-2 text-[#F59E0B]">
                    <AlertTriangle className="w-4 h-4" />
                    <span className="font-medium text-sm">Ожидает вашей оплаты! Переведите деньги продавцу.</span>
                  </div>
                </div>
              )}
              
              {trade.status === "paid" && (
                <div className="bg-[#3B82F6]/10 border border-[#3B82F6]/20 rounded-xl p-3 mb-4">
                  <div className="flex items-center gap-2 text-[#3B82F6]">
                    <Clock className="w-4 h-4" />
                    <span className="font-medium text-sm">Оплата отправлена. Ожидайте подтверждения.</span>
                  </div>
                </div>
              )}
              
              <div className="grid grid-cols-4 gap-4 text-sm">
                <div>
                  <div className="text-[#71717A]">Курс</div>
                  <div className="text-white font-medium">{trade.price_rub} RUB</div>
                </div>
                <div>
                  <div className="text-[#71717A]">Оплатить</div>
                  <div className="text-white font-medium">{trade.amount_rub?.toLocaleString()} ₽</div>
                </div>
                <div>
                  <div className="text-[#71717A]">Комиссия</div>
                  <div className="text-[#10B981] font-medium">0%</div>
                </div>
                <div>
                  <div className="text-[#71717A]">Дата</div>
                  <div className="text-white text-xs">{new Date(trade.created_at).toLocaleDateString()}</div>
                </div>
              </div>

              {(trade.status === "pending" || trade.status === "paid" || trade.status === "disputed") && (
                <div className="flex gap-3 mt-4">
                  <Link to={`/trader/purchases/${trade.id}`} className="flex-1">
                    <Button className="w-full bg-[#7C3AED] hover:bg-[#6D28D9] h-10 rounded-xl">
                      <MessageCircle className="w-4 h-4 mr-2" />
                      Открыть сделку
                    </Button>
                  </Link>
                </div>
              )}

              {trade.status === "completed" && (
                <div className="mt-4 p-3 bg-[#10B981]/10 border border-[#10B981]/20 rounded-xl">
                  <div className="flex items-center gap-2 text-[#10B981] text-sm">
                    <CheckCircle className="w-4 h-4" />
                    <span>USDT зачислены на ваш баланс</span>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TraderHistory() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white font-['Unbounded']">История сделок</h1>
      <p className="text-[#71717A]">Выберите раздел для просмотра завершённых сделок</p>
      
      <div className="grid sm:grid-cols-2 gap-4">
        <Link to="/trader/history/sales">
          <div className="bg-[#121212] border border-white/5 hover:border-[#10B981]/50 rounded-2xl p-6 transition-colors">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-[#10B981]/10 flex items-center justify-center">
                <TrendingUp className="w-6 h-6 text-[#10B981]" />
              </div>
              <div>
                <div className="text-white font-semibold text-lg">История продаж</div>
                <div className="text-sm text-[#71717A]">Завершённые продажи USDT</div>
              </div>
            </div>
          </div>
        </Link>
        
        <Link to="/trader/history/purchases">
          <div className="bg-[#121212] border border-white/5 hover:border-[#7C3AED]/50 rounded-2xl p-6 transition-colors">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-[#7C3AED]/10 flex items-center justify-center">
                <DollarSign className="w-6 h-6 text-[#7C3AED]" />
              </div>
              <div>
                <div className="text-white font-semibold text-lg">История покупок</div>
                <div className="text-sm text-[#71717A]">Завершённые покупки USDT</div>
              </div>
            </div>
          </div>
        </Link>
      </div>
    </div>
  );
}

function TraderHistorySales() {
  const { token } = useAuth();
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTrades();
  }, []);

  const fetchTrades = async () => {
    try {
      const response = await axios.get(`${API}/trades/sales/history`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTrades(response.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    const styles = {
      completed: "bg-[#10B981]/10 text-[#10B981]",
      cancelled: "bg-[#EF4444]/10 text-[#EF4444]"
    };
    const labels = {
      completed: "Завершена",
      cancelled: "Отменена"
    };
    return (
      <span className={`px-2 py-1 text-xs rounded-full font-medium ${styles[status] || "bg-[#52525B]/10 text-[#52525B]"}`}>
        {labels[status] || status}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/trader/history" className="p-2 rounded-xl bg-white/5 hover:bg-white/10">
          <ArrowUpRight className="w-5 h-5 text-white rotate-[225deg]" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-white font-['Unbounded']">История продаж</h1>
          <p className="text-[#71717A]">Завершённые и отменённые продажи</p>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="spinner" />
        </div>
      ) : trades.length === 0 ? (
        <div className="text-center py-12">
          <History className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
          <p className="text-[#71717A]">История продаж пуста</p>
        </div>
      ) : (
        <div className="space-y-3">
          {trades.map((trade) => (
            <div key={trade.id} className="bg-[#121212] border border-white/5 rounded-xl p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div>
                    <div className="text-sm text-[#71717A] font-['JetBrains_Mono']">#{trade.id}</div>
                    <div className="text-lg font-bold text-white">-{trade.amount_usdt} USDT</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-white font-medium">+{trade.amount_rub?.toLocaleString()} ₽</div>
                  <div className="text-xs text-[#71717A]">{new Date(trade.created_at).toLocaleDateString()}</div>
                </div>
                {getStatusBadge(trade.status)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TraderHistoryPurchases() {
  const { token } = useAuth();
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTrades();
  }, []);

  const fetchTrades = async () => {
    try {
      const response = await axios.get(`${API}/trades/purchases/history`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTrades(response.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    const styles = {
      completed: "bg-[#10B981]/10 text-[#10B981]",
      cancelled: "bg-[#EF4444]/10 text-[#EF4444]"
    };
    const labels = {
      completed: "Завершена",
      cancelled: "Отменена"
    };
    return (
      <span className={`px-2 py-1 text-xs rounded-full font-medium ${styles[status] || "bg-[#52525B]/10 text-[#52525B]"}`}>
        {labels[status] || status}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/trader/history" className="p-2 rounded-xl bg-white/5 hover:bg-white/10">
          <ArrowUpRight className="w-5 h-5 text-white rotate-[225deg]" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-white font-['Unbounded']">История покупок</h1>
          <p className="text-[#71717A]">Завершённые и отменённые покупки</p>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="spinner" />
        </div>
      ) : trades.length === 0 ? (
        <div className="text-center py-12">
          <History className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
          <p className="text-[#71717A]">История покупок пуста</p>
        </div>
      ) : (
        <div className="space-y-3">
          {trades.map((trade) => (
            <div key={trade.id} className="bg-[#121212] border border-white/5 rounded-xl p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div>
                    <div className="text-sm text-[#71717A] font-['JetBrains_Mono']">#{trade.id}</div>
                    <div className="text-lg font-bold text-[#10B981]">+{(trade.amount_usdt - trade.trader_commission).toFixed(2)} USDT</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-white font-medium">-{trade.amount_rub?.toLocaleString()} ₽</div>
                  <div className="text-xs text-[#71717A]">{new Date(trade.created_at).toLocaleDateString()}</div>
                </div>
                {getStatusBadge(trade.status)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TraderReferral() {
  const { token } = useAuth();
  const [referralInfo, setReferralInfo] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchReferralInfo();
  }, []);

  const fetchReferralInfo = async () => {
    try {
      const response = await axios.get(`${API}/traders/referral`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setReferralInfo(response.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success("Скопировано");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-white">Реферальная программа</h1>
      <p className="text-[#71717A]">Получайте 0.5% от оборота приглашённых пользователей</p>

      {/* Promo Banner */}
      <div className="bg-gradient-to-br from-[#7C3AED]/20 via-[#A855F7]/15 to-[#EC4899]/20 border border-[#7C3AED]/30 rounded-2xl p-6">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-[#7C3AED]/30 flex items-center justify-center flex-shrink-0">
            <TrendingUp className="w-6 h-6 text-[#A78BFA]" />
          </div>
          <div>
            <h3 className="text-white font-semibold text-lg mb-2">💰 Пассивный доход без усилий</h3>
            <p className="text-[#A1A1AA] text-sm leading-relaxed">
              Приглашайте друзей и знакомых на Reptiloid и получайте <span className="text-[#10B981] font-semibold">0.5% комиссии</span> с каждой их сделки — навсегда! 
              Чем больше ваших рефералов торгует, тем выше ваш пассивный доход.
            </p>
            <div className="flex flex-wrap gap-4 mt-4 text-sm">
              <div className="flex items-center gap-2 text-[#A78BFA]">
                <CheckCircle className="w-4 h-4" />
                Без ограничений по времени
              </div>
              <div className="flex items-center gap-2 text-[#A78BFA]">
                <CheckCircle className="w-4 h-4" />
                Мгновенные выплаты
              </div>
              <div className="flex items-center gap-2 text-[#A78BFA]">
                <CheckCircle className="w-4 h-4" />
                Неограниченное число рефералов
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid sm:grid-cols-3 gap-4">
        <div className="bg-[#121212] border border-white/5 rounded-xl p-5">
          <div className="text-[#52525B] text-xs mb-1">Заработано</div>
          <div className="text-2xl font-semibold text-[#10B981] font-mono">
            {referralInfo?.referral_earnings?.toFixed(2) || "0.00"}
          </div>
          <div className="text-xs text-[#52525B]">USDT</div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-xl p-5">
          <div className="text-[#52525B] text-xs mb-1">Рефералов</div>
          <div className="text-2xl font-semibold text-white">
            {referralInfo?.referrals_count || 0}
          </div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-xl p-5">
          <div className="text-[#52525B] text-xs mb-1">Ставка</div>
          <div className="text-2xl font-semibold text-white">0.5%</div>
          <div className="text-xs text-[#52525B]">от оборота</div>
        </div>
      </div>

      {/* Referral Link */}
      <div className="bg-[#121212] border border-white/5 rounded-xl p-5">
        <h3 className="text-white font-medium mb-4">Ваша реферальная ссылка</h3>
        
        <div className="space-y-4">
          <div>
            <label className="text-xs text-[#52525B] block mb-2">Код</label>
            <div className="flex items-center gap-2">
              <div className="flex-1 bg-[#0A0A0A] border border-white/10 rounded-lg px-4 py-3 font-mono text-white">
                {referralInfo?.referral_code}
              </div>
              <Button
                onClick={() => copyToClipboard(referralInfo?.referral_code)}
                variant="ghost"
                className="h-12 px-4 text-[#7C3AED] hover:bg-[#7C3AED]/10"
              >
                <Copy className="w-4 h-4" />
              </Button>
            </div>
          </div>

          <div>
            <label className="text-xs text-[#52525B] block mb-2">Ссылка</label>
            <div className="flex items-center gap-2">
              <div className="flex-1 bg-[#0A0A0A] border border-white/10 rounded-lg px-4 py-3 text-sm text-[#A1A1AA] truncate">
                {referralInfo?.referral_link}
              </div>
              <Button
                onClick={() => copyToClipboard(referralInfo?.referral_link)}
                variant="ghost"
                className="h-12 px-4 text-[#7C3AED] hover:bg-[#7C3AED]/10"
              >
                <Copy className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Referrals List */}
      {(referralInfo?.referred_traders?.length > 0 || referralInfo?.referred_merchants?.length > 0) && (
        <div className="bg-[#121212] border border-white/5 rounded-xl p-5">
          <h3 className="text-white font-medium mb-4">Приглашённые пользователи</h3>
          <div className="space-y-2">
            {referralInfo?.referred_traders?.map((t) => (
              <div key={t.id} className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs px-2 py-0.5 bg-[#7C3AED]/10 text-[#7C3AED] rounded">Трейдер</span>
                  <span className="text-white">{t.login}</span>
                </div>
                <span className="text-xs text-[#52525B]">{new Date(t.created_at).toLocaleDateString()}</span>
              </div>
            ))}
            {referralInfo?.referred_merchants?.map((m) => (
              <div key={m.id} className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs px-2 py-0.5 bg-[#10B981]/10 text-[#10B981] rounded">Мерчант</span>
                  <span className="text-white">{m.merchant_name || m.login}</span>
                </div>
                <span className="text-xs text-[#52525B]">{new Date(m.created_at).toLocaleDateString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ==================== TRADING SETTINGS ====================
function TradingSettings() {
  const { token } = useAuth();
  const [displayName, setDisplayName] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const response = await axios.get(`${API}/traders/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setDisplayName(response.data.display_name || response.data.nickname || "");
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!displayName.trim()) {
      toast.error("Введите отображаемое имя");
      return;
    }
    setSaving(true);
    try {
      await axios.put(`${API}/traders/me`, {
        display_name: displayName.trim()
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Настройки сохранены");
    } catch (error) {
      toast.error("Ошибка сохранения");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-white font-['Unbounded']">Настройки торговли</h1>

      <div className="bg-[#121212] border border-white/5 rounded-2xl p-6 space-y-6">
        <div>
          <h3 className="text-white font-semibold mb-4">Отображаемое имя</h3>
          <p className="text-sm text-[#71717A] mb-4">
            Это имя будет отображаться в стакане объявлений вместо вашего логина
          </p>
          <Input
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Введите отображаемое имя"
            className="bg-white/5 border-white/10 text-white h-12 rounded-xl max-w-md"
            maxLength={30}
          />
          <p className="text-xs text-[#71717A] mt-2">Максимум 30 символов</p>
        </div>

        <Button onClick={handleSave} disabled={saving} className="bg-[#7C3AED] hover:bg-[#6D28D9] h-11 rounded-xl px-8" data-testid="save-trading-settings-btn">
          {saving ? <div className="spinner" /> : "Сохранить"}
        </Button>
      </div>
    </div>
  );
}

// ==================== TRADING STATS ====================
function TradingStats() {
  const { token } = useAuth();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API}/traders/me/stats`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setStats(response.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white font-['Unbounded']">Статистика торговли</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Всего сделок</div>
          <div className="text-2xl font-bold text-white">{stats?.total_trades || 0}</div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Завершённых</div>
          <div className="text-2xl font-bold text-[#10B981]">{stats?.completed_trades || 0}</div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Отменённых</div>
          <div className="text-2xl font-bold text-[#71717A]">{stats?.cancelled_trades || 0}</div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Диспутов</div>
          <div className="text-2xl font-bold text-[#EF4444]">{stats?.disputed_trades || 0}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Общая сумма сделок</div>
          <div className="text-xl font-bold text-white">{(stats?.total_volume_usdt || 0).toFixed(2)} USDT</div>
          <div className="text-sm text-[#71717A]">≈ {(stats?.total_volume_rub || 0).toLocaleString()} ₽</div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Средний курс</div>
          <div className="text-xl font-bold text-white">{(stats?.avg_rate || 0).toFixed(2)} ₽</div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Среднее время сделки</div>
          <div className="text-xl font-bold text-white">{stats?.avg_time_minutes || 0} мин</div>
        </div>
      </div>
    </div>
  );
}

function TraderSettings() {
  const { token, user } = useAuth();
  const [trader, setTrader] = useState(null);
  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [show2FAForm, setShow2FAForm] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [saving, setSaving] = useState(false);
  const [twoFAEnabled, setTwoFAEnabled] = useState(false);

  useEffect(() => {
    fetchTrader();
  }, []);

  const fetchTrader = async () => {
    try {
      const response = await axios.get(`${API}/traders/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTrader(response.data);
      setTwoFAEnabled(response.data.two_fa_enabled || false);
    } catch (error) {
      console.error(error);
    }
  };

  const handleChangePassword = async () => {
    if (newPassword !== confirmPassword) {
      toast.error("Пароли не совпадают");
      return;
    }
    if (newPassword.length < 6) {
      toast.error("Пароль должен быть не менее 6 символов");
      return;
    }
    
    setSaving(true);
    try {
      await axios.post(`${API}/traders/change-password`, {
        current_password: currentPassword,
        new_password: newPassword
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Пароль успешно изменён");
      setShowPasswordForm(false);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка смены пароля");
    } finally {
      setSaving(false);
    }
  };

  const handleToggle2FA = async () => {
    setSaving(true);
    try {
      await axios.post(`${API}/traders/toggle-2fa`, {
        enabled: !twoFAEnabled
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTwoFAEnabled(!twoFAEnabled);
      toast.success(twoFAEnabled ? "2FA отключена" : "2FA включена");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-white font-['Unbounded']">Настройки аккаунта</h1>

      {/* Смена пароля */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-[#7C3AED]/20 flex items-center justify-center">
            <Key className="w-5 h-5 text-[#7C3AED]" />
          </div>
          <div>
            <h3 className="text-white font-semibold">Смена пароля</h3>
            <p className="text-sm text-[#71717A]">Изменить пароль для входа в аккаунт</p>
          </div>
        </div>
        
        {!showPasswordForm ? (
          <Button 
            onClick={() => setShowPasswordForm(true)}
            variant="outline"
            className="border-white/10 text-white hover:bg-white/5"
          >
            Изменить пароль
          </Button>
        ) : (
          <div className="space-y-4">
            <div>
              <Label className="text-[#71717A] text-sm">Текущий пароль</Label>
              <div className="relative mt-1">
                <Input
                  type={showCurrentPassword ? "text" : "password"}
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="bg-[#0A0A0A] border-white/10 text-white pr-10"
                  placeholder="Введите текущий пароль"
                />
                <button
                  type="button"
                  onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#71717A] hover:text-white"
                >
                  {showCurrentPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            
            <div>
              <Label className="text-[#71717A] text-sm">Новый пароль</Label>
              <div className="relative mt-1">
                <Input
                  type={showNewPassword ? "text" : "password"}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="bg-[#0A0A0A] border-white/10 text-white pr-10"
                  placeholder="Введите новый пароль"
                />
                <button
                  type="button"
                  onClick={() => setShowNewPassword(!showNewPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#71717A] hover:text-white"
                >
                  {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            
            <div>
              <Label className="text-[#71717A] text-sm">Подтвердите пароль</Label>
              <Input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="bg-[#0A0A0A] border-white/10 text-white mt-1"
                placeholder="Повторите новый пароль"
              />
            </div>
            
            <div className="flex gap-3">
              <Button 
                onClick={handleChangePassword}
                disabled={saving || !currentPassword || !newPassword || !confirmPassword}
                className="bg-[#7C3AED] hover:bg-[#6D28D9]"
              >
                {saving ? <div className="spinner" /> : "Сохранить"}
              </Button>
              <Button 
                onClick={() => {
                  setShowPasswordForm(false);
                  setCurrentPassword("");
                  setNewPassword("");
                  setConfirmPassword("");
                }}
                variant="outline"
                className="border-white/10 text-white hover:bg-white/5"
              >
                Отмена
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* 2FA */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${twoFAEnabled ? "bg-[#10B981]/20" : "bg-[#F59E0B]/20"}`}>
              <Lock className={`w-5 h-5 ${twoFAEnabled ? "text-[#10B981]" : "text-[#F59E0B]"}`} />
            </div>
            <div>
              <h3 className="text-white font-semibold">Двухфакторная аутентификация</h3>
              <p className="text-sm text-[#71717A]">
                {twoFAEnabled ? "2FA включена — аккаунт защищён" : "Рекомендуем включить для безопасности"}
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <span className={`px-3 py-1 rounded-full text-xs font-medium ${
              twoFAEnabled 
                ? "bg-[#10B981]/20 text-[#10B981]" 
                : "bg-[#F59E0B]/20 text-[#F59E0B]"
            }`}>
              {twoFAEnabled ? "Включено" : "Отключено"}
            </span>
            <Button 
              onClick={handleToggle2FA}
              disabled={saving}
              variant={twoFAEnabled ? "outline" : "default"}
              className={twoFAEnabled 
                ? "border-[#EF4444]/50 text-[#EF4444] hover:bg-[#EF4444]/10" 
                : "bg-[#10B981] hover:bg-[#059669]"
              }
            >
              {saving ? <div className="spinner" /> : (twoFAEnabled ? "Отключить" : "Включить")}
            </Button>
          </div>
        </div>
        
        {!twoFAEnabled && (
          <div className="mt-4 p-4 bg-[#F59E0B]/10 border border-[#F59E0B]/20 rounded-xl">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-[#F59E0B] flex-shrink-0 mt-0.5" />
              <div className="text-sm text-[#F59E0B]">
                <p className="font-medium">Защитите свой аккаунт</p>
                <p className="opacity-80 mt-1">При входе будет запрашиваться дополнительный код подтверждения.</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Информация */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
        <h3 className="text-white font-semibold mb-4">Информация об аккаунте</h3>
        <div className="space-y-3 text-sm">
          <div className="flex justify-between">
            <span className="text-[#71717A]">Логин</span>
            <span className="text-white">{user?.login}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#71717A]">Комиссия</span>
            <span className="text-white">{trader?.commission_rate}%</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#71717A]">Баланс</span>
            <span className="text-white font-['JetBrains_Mono']">{trader?.balance_usdt?.toFixed(2)} USDT</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#71717A]">Дата регистрации</span>
            <span className="text-white">{trader?.created_at ? new Date(trader.created_at).toLocaleDateString("ru-RU") : "—"}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ==================== MY MARKET PURCHASES ====================
function MyMarketPurchases() {
  const { token } = useAuth();
  const [purchases, setPurchases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    fetchPurchases();
  }, []);

  const fetchPurchases = async () => {
    try {
      const response = await axios.get(`${API}/marketplace/my-purchases`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setPurchases(response.data || []);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const toggleExpand = (id) => {
    setExpandedId(expandedId === id ? null : id);
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success("Скопировано!");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-[#7C3AED] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white font-['Unbounded']">Мои покупки</h1>
        <p className="text-[#71717A]">История заказов с маркетплейса</p>
      </div>

      {purchases.length === 0 ? (
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-12 text-center">
          <ShoppingBag className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
          <p className="text-[#71717A]">Вы ещё ничего не покупали</p>
          <Link to="/marketplace">
            <Button className="mt-4 bg-[#7C3AED] hover:bg-[#6D28D9] rounded-full px-6">
              Перейти в каталог
            </Button>
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {purchases.map((purchase) => (
            <PurchaseCard 
              key={purchase.id} 
              purchase={purchase} 
              expandedId={expandedId}
              toggleExpand={toggleExpand}
              copyToClipboard={copyToClipboard}
              onRefresh={fetchPurchases}
              token={token}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// Purchase card with guarantor support
function PurchaseCard({ purchase, expandedId, toggleExpand, copyToClipboard, onRefresh, token }) {
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [disputing, setDisputing] = useState(false);
  const [disputeReason, setDisputeReason] = useState("");
  const [showDisputeForm, setShowDisputeForm] = useState(false);

  const handleConfirm = async () => {
    setConfirming(true);
    try {
      const response = await axios.post(
        `${API}/marketplace/purchases/${purchase.id}/confirm`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      // Format delivered content for display
      const formatContent = (content) => {
        if (!content) return null;
        const items = Array.isArray(content) ? content : [content];
        return items.map(item => {
          if (typeof item === 'string') return item;
          if (typeof item === 'object' && item !== null) return item.text || '';
          return String(item);
        }).filter(Boolean).join('\n---\n');
      };
      
      toast.success(
        <div>
          <div className="font-semibold">Покупка подтверждена!</div>
          {response.data.delivered_content && (
            <div className="text-sm mt-2 font-mono bg-black/20 p-2 rounded break-all whitespace-pre-wrap max-h-32 overflow-y-auto">
              {formatContent(response.data.delivered_content)}
            </div>
          )}
        </div>,
        { duration: 15000 }
      );
      onRefresh();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка подтверждения");
    } finally {
      setConfirming(false);
    }
  };

  const handleCancel = async () => {
    setCancelling(true);
    try {
      await axios.post(
        `${API}/marketplace/purchases/${purchase.id}/cancel`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success("Заказ отменён, средства возвращены");
      onRefresh();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка отмены");
    } finally {
      setCancelling(false);
    }
  };

  const handleDispute = async () => {
    if (!disputeReason.trim()) {
      toast.error("Укажите причину спора");
      return;
    }
    setDisputing(true);
    try {
      await axios.post(
        `${API}/marketplace/purchases/${purchase.id}/dispute`,
        {},
        { 
          headers: { Authorization: `Bearer ${token}` },
          params: { reason: disputeReason }
        }
      );
      toast.success("Спор открыт. Администратор рассмотрит вашу заявку.");
      setShowDisputeForm(false);
      onRefresh();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка открытия спора");
    } finally {
      setDisputing(false);
    }
  };

  // Status badge
  const getStatusBadge = () => {
    switch (purchase.status) {
      case "completed":
        return <span className="px-2 py-1 text-xs rounded-full bg-[#10B981]/10 text-[#10B981]">Завершено</span>;
      case "pending_confirmation":
        return <span className="px-2 py-1 text-xs rounded-full bg-[#F59E0B]/10 text-[#F59E0B] flex items-center gap-1"><Clock className="w-3 h-3" />Ожидает подтверждения</span>;
      case "disputed":
        return <span className="px-2 py-1 text-xs rounded-full bg-[#EF4444]/10 text-[#EF4444]">Спор</span>;
      case "cancelled":
        return <span className="px-2 py-1 text-xs rounded-full bg-[#71717A]/10 text-[#71717A]">Отменено</span>;
      case "refunded":
        return <span className="px-2 py-1 text-xs rounded-full bg-[#3B82F6]/10 text-[#3B82F6]">Возврат</span>;
      default:
        return <span className="px-2 py-1 text-xs rounded-full bg-[#71717A]/10 text-[#71717A]">{purchase.status}</span>;
    }
  };

  const isGuarantor = purchase.purchase_type === "guarantor";
  const isPending = purchase.status === "pending_confirmation";
  const hasContent = purchase.delivered_content && (Array.isArray(purchase.delivered_content) ? purchase.delivered_content.length > 0 : purchase.delivered_content);

  return (
    <div className={`bg-[#121212] border rounded-xl p-5 ${isPending ? "border-[#F59E0B]/30" : "border-white/5"}`}>
      {/* Order Number */}
      <div className="flex items-center justify-between text-xs text-[#52525B] mb-2">
        <span>Заказ #{purchase.id?.slice(0, 8).toUpperCase()}</span>
        <span>{new Date(purchase.created_at).toLocaleString("ru-RU")}</span>
      </div>
      
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-white font-semibold">{purchase.product_name}</span>
            {isGuarantor && (
              <span className="px-1.5 py-0.5 text-[10px] rounded bg-[#7C3AED]/20 text-[#A78BFA] flex items-center gap-1">
                <Shield className="w-3 h-3" />Гарант
              </span>
            )}
          </div>
          <div className="text-sm text-[#71717A]">@{purchase.seller_nickname}</div>
        </div>
        {getStatusBadge()}
      </div>
      
      <div className="flex items-center justify-between text-sm mb-2">
        <span className="text-[#71717A]">Количество: {purchase.quantity}</span>
        <div className="text-right">
          <span className="text-[#10B981] font-mono">{purchase.total_price?.toFixed(2)} USDT</span>
          {isGuarantor && purchase.guarantor_fee > 0 && (
            <div className="text-xs text-[#7C3AED]">+{purchase.guarantor_fee?.toFixed(2)} гарант</div>
          )}
        </div>
      </div>

      {/* Auto-complete countdown for pending */}
      {isPending && purchase.auto_complete_at && (
        <div className="mb-3 p-2 bg-[#F59E0B]/5 border border-[#F59E0B]/20 rounded-lg text-xs text-[#F59E0B] flex items-center gap-2">
          <Clock className="w-4 h-4" />
          <span>Автозавершение: {new Date(purchase.auto_complete_at).toLocaleDateString("ru-RU")}</span>
        </div>
      )}

      {/* Action buttons for pending guarantor orders */}
      {isPending && (
        <div className="space-y-2 mt-3">
          <div className="flex gap-2">
            <Button
              onClick={handleConfirm}
              disabled={confirming}
              className="flex-1 bg-[#10B981] hover:bg-[#059669] text-white"
            >
              {confirming ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <CheckCircle className="w-4 h-4 mr-2" />
                  Подтвердить получение
                </>
              )}
            </Button>
            <Button
              onClick={handleCancel}
              disabled={cancelling}
              variant="outline"
              className="border-[#EF4444]/30 text-[#EF4444] hover:bg-[#EF4444]/10"
            >
              {cancelling ? (
                <div className="w-4 h-4 border-2 border-[#EF4444] border-t-transparent rounded-full animate-spin" />
              ) : (
                <XCircle className="w-4 h-4" />
              )}
            </Button>
          </div>
          
          {/* Question about order button */}
          <Button
            onClick={() => {
              const orderId = purchase.id?.slice(0, 8).toUpperCase();
              navigate(`/trader/shop-chats?shop=${purchase.seller_id}&subject=${encodeURIComponent(`Вопрос по заказу #${orderId}`)}`);
            }}
            variant="outline"
            size="sm"
            className="w-full text-[#7C3AED] border-[#7C3AED]/30 hover:bg-[#7C3AED]/10 text-xs"
          >
            <MessageCircle className="w-3 h-3 mr-1" />
            Вопрос по заказу
          </Button>
          
          {!showDisputeForm ? (
            <Button
              onClick={() => setShowDisputeForm(true)}
              variant="ghost"
              size="sm"
              className="w-full text-[#71717A] hover:text-[#EF4444] text-xs"
            >
              <AlertTriangle className="w-3 h-3 mr-1" />
              Открыть спор
            </Button>
          ) : (
            <div className="p-3 bg-[#0A0A0A] border border-[#EF4444]/20 rounded-lg space-y-2">
              <textarea
                value={disputeReason}
                onChange={(e) => setDisputeReason(e.target.value)}
                placeholder="Опишите проблему..."
                className="w-full bg-[#121212] border border-white/10 rounded-lg p-2 text-white text-sm resize-none h-20"
              />
              <div className="flex gap-2">
                <Button
                  onClick={handleDispute}
                  disabled={disputing}
                  size="sm"
                  className="flex-1 bg-[#EF4444] hover:bg-[#DC2626] text-white text-xs"
                >
                  {disputing ? "Отправка..." : "Отправить спор"}
                </Button>
                <Button
                  onClick={() => setShowDisputeForm(false)}
                  variant="outline"
                  size="sm"
                  className="text-xs"
                >
                  Отмена
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
      
      {/* Show/Hide Product Button for completed orders */}
      {hasContent && (
        <div className="mt-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => toggleExpand(purchase.id)}
            className="w-full border-[#7C3AED]/30 text-[#A78BFA] hover:bg-[#7C3AED]/10"
          >
            {expandedId === purchase.id ? (
              <>
                <XCircle className="w-4 h-4 mr-2" />
                Скрыть товар
              </>
            ) : (
              <>
                <CheckCircle className="w-4 h-4 mr-2" />
                Показать товар
              </>
            )}
          </Button>
          
          {expandedId === purchase.id && (
            <div className="mt-3 p-4 bg-[#0A0A0A] border border-[#7C3AED]/20 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <div className="text-xs text-[#A78BFA]">Полученный товар ({Array.isArray(purchase.delivered_content) ? purchase.delivered_content.length : 1} шт.):</div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    const content = Array.isArray(purchase.delivered_content) 
                      ? purchase.delivered_content.map(item => typeof item === 'object' ? item.text : item).join('\n')
                      : (typeof purchase.delivered_content === 'object' ? purchase.delivered_content.text : purchase.delivered_content);
                    copyToClipboard(content);
                  }}
                  className="text-[#71717A] hover:text-white p-1 h-auto"
                >
                  <Copy className="w-4 h-4" />
                </Button>
              </div>
              <div className="space-y-2">
                {(Array.isArray(purchase.delivered_content) ? purchase.delivered_content : [purchase.delivered_content]).map((item, idx) => {
                  const itemText = typeof item === 'object' ? item.text : item;
                  const itemPhoto = typeof item === 'object' ? item.photo_url : null;
                  const itemFile = typeof item === 'object' ? item.file_url : null;
                  
                  return (
                    <div key={idx} className="bg-[#121212] p-3 rounded border border-white/5 space-y-2">
                      {/* Text content */}
                      {itemText && (
                        <div className="flex items-center justify-between">
                          <span className="text-sm text-white font-mono break-all">{itemText}</span>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => copyToClipboard(itemText)}
                            className="text-[#52525B] hover:text-white p-1 h-auto ml-2 flex-shrink-0"
                          >
                            <Copy className="w-3 h-3" />
                          </Button>
                        </div>
                      )}
                      
                      {/* Photo */}
                      {itemPhoto && !itemPhoto.includes("[") && (
                        <div className="mt-2">
                          <img src={itemPhoto} alt="" className="max-w-full max-h-48 rounded-lg" />
                        </div>
                      )}
                      {itemPhoto && itemPhoto.includes("[") && (
                        <div className="text-xs text-[#71717A] italic">{itemPhoto}</div>
                      )}
                      
                      {/* File */}
                      {itemFile && !itemFile.includes("[") && (
                        <div className="mt-2">
                          <a 
                            href={itemFile} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="text-xs text-[#7C3AED] hover:text-[#A78BFA] flex items-center gap-1"
                          >
                            <Download className="w-3 h-3" />
                            Скачать файл
                          </a>
                        </div>
                      )}
                      {itemFile && itemFile.includes("[") && (
                        <div className="text-xs text-[#71717A] italic">{itemFile}</div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
      
      {/* Question about order button - for all orders */}
      {!isPending && (
        <div className="mt-3">
          <Button
            onClick={() => {
              const orderId = purchase.id?.slice(0, 8).toUpperCase();
              navigate(`/trader/shop-chats?shop=${purchase.seller_id}&subject=${encodeURIComponent(`Вопрос по заказу #${orderId}`)}`);
            }}
            variant="outline"
            size="sm"
            className="w-full text-[#7C3AED] border-[#7C3AED]/30 hover:bg-[#7C3AED]/10 text-xs"
          >
            <MessageCircle className="w-3 h-3 mr-1" />
            Вопрос по заказу #{purchase.id?.slice(0, 8).toUpperCase()}
          </Button>
        </div>
      )}
      
      <div className="text-xs text-[#52525B] mt-3">
        {new Date(purchase.created_at).toLocaleString("ru-RU")}
      </div>
    </div>
  );
}

// ==================== TRADER BALANCE ====================
function TraderBalance() {
  const { token } = useAuth();
  const [trader, setTrader] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [traderRes, statsRes] = await Promise.all([
        axios.get(`${API}/traders/me`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/traders/stats`, { headers: { Authorization: `Bearer ${token}` } })
      ]);
      setTrader({ ...traderRes.data, ...statsRes.data });
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-[#7C3AED] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white font-['Unbounded']">Баланс</h1>
        <p className="text-[#71717A]">Управление финансами</p>
      </div>

      {/* Balance Cards */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div className="bg-gradient-to-br from-[#10B981] to-[#059669] rounded-2xl p-6">
          <div className="text-white/80 text-sm mb-1">Основной баланс</div>
          <div className="text-3xl font-bold text-white font-['JetBrains_Mono']">
            {trader?.balance_usdt?.toFixed(2) || 0} <span className="text-lg">USDT</span>
          </div>
        </div>

        {trader?.shop_balance > 0 && (
          <div className="bg-gradient-to-br from-[#F59E0B] to-[#D97706] rounded-2xl p-6">
            <div className="text-white/80 text-sm mb-1">Баланс магазина</div>
            <div className="text-3xl font-bold text-white font-['JetBrains_Mono']">
              {trader?.shop_balance?.toFixed(2) || 0} <span className="text-lg">USDT</span>
            </div>
          </div>
        )}

        <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
          <div className="text-[#71717A] text-sm mb-1">Заработано всего</div>
          <div className="text-2xl font-bold text-white font-['JetBrains_Mono']">
            {((trader?.salesVolume || 0) + (trader?.shop_balance || 0)).toFixed(2)} <span className="text-sm">USDT</span>
          </div>
        </div>
      </div>

      {/* Statistics */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Статистика</h3>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-4 bg-white/5 rounded-xl">
            <div className="text-[#71717A] text-sm">Продаж P2P</div>
            <div className="text-xl font-bold text-white">{trader?.salesCount || 0}</div>
          </div>
          <div className="p-4 bg-white/5 rounded-xl">
            <div className="text-[#71717A] text-sm">Объём продаж</div>
            <div className="text-xl font-bold text-[#10B981] font-['JetBrains_Mono']">{(trader?.salesVolume || 0).toFixed(0)} USDT</div>
          </div>
          <div className="p-4 bg-white/5 rounded-xl">
            <div className="text-[#71717A] text-sm">Покупок P2P</div>
            <div className="text-xl font-bold text-white">{trader?.purchasesCount || 0}</div>
          </div>
          <div className="p-4 bg-white/5 rounded-xl">
            <div className="text-[#71717A] text-sm">Объём покупок</div>
            <div className="text-xl font-bold text-[#7C3AED] font-['JetBrains_Mono']">{(trader?.purchasesVolume || 0).toFixed(0)} USDT</div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid sm:grid-cols-2 gap-4">
        <Link to="/trader/transfers">
          <div className="bg-[#121212] border border-white/5 hover:border-[#7C3AED]/50 rounded-2xl p-5 transition-colors">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-[#7C3AED]/10 flex items-center justify-center">
                <ArrowUpRight className="w-5 h-5 text-[#7C3AED]" />
              </div>
              <div>
                <div className="text-white font-medium">Переводы</div>
                <div className="text-sm text-[#71717A]">Перевести другому пользователю</div>
              </div>
            </div>
          </div>
        </Link>
        <Link to="/trader/requisites">
          <div className="bg-[#121212] border border-white/5 hover:border-[#10B981]/50 rounded-2xl p-5 transition-colors">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-[#10B981]/10 flex items-center justify-center">
                <CreditCard className="w-5 h-5 text-[#10B981]" />
              </div>
              <div>
                <div className="text-white font-medium">Реквизиты</div>
                <div className="text-sm text-[#71717A]">Управление способами оплаты</div>
              </div>
            </div>
          </div>
        </Link>
      </div>
    </div>
  );
}

// ==================== TRADER TRANSACTIONS ====================
function TraderTransactions() {
  const { token, user } = useAuth();
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [balance, setBalance] = useState(0);

  useEffect(() => {
    fetchTransactions();
    fetchBalance();
  }, []);

  const fetchTransactions = async () => {
    try {
      const response = await axios.get(`${API}/traders/transactions`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTransactions(response.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const fetchBalance = async () => {
    try {
      const response = await axios.get(`${API}/traders/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setBalance(response.data.balance_usdt);
    } catch (error) {
      console.error(error);
    }
  };

  const getTypeConfig = (type) => {
    const configs = {
      offer_created: { label: "Создание объявления", icon: ListOrdered, color: "#F59E0B", bgColor: "#F59E0B" },
      offer_closed: { label: "Закрытие объявления", icon: CheckCircle, color: "#10B981", bgColor: "#10B981" },
      sale_completed: { label: "Продажа", icon: TrendingUp, color: "#10B981", bgColor: "#10B981" },
      purchase_completed: { label: "Покупка", icon: ShoppingBag, color: "#10B981", bgColor: "#10B981" },
      marketplace_purchase: { label: "Покупка в маркете", icon: Store, color: "#F59E0B", bgColor: "#F59E0B" },
      marketplace_sale: { label: "Продажа в маркете", icon: Store, color: "#10B981", bgColor: "#10B981" },
      transfer_sent: { label: "Перевод отправлен", icon: ArrowUpRight, color: "#EF4444", bgColor: "#EF4444" },
      transfer_received: { label: "Перевод получен", icon: ArrowDownRight, color: "#10B981", bgColor: "#10B981" },
      referral_bonus: { label: "Реферальный бонус", icon: Users, color: "#7C3AED", bgColor: "#7C3AED" },
      commission: { label: "Комиссия платформы", icon: DollarSign, color: "#EF4444", bgColor: "#EF4444" },
      deposit: { label: "Пополнение", icon: ArrowDownRight, color: "#10B981", bgColor: "#10B981" },
      withdrawal: { label: "Вывод", icon: ArrowUpRight, color: "#EF4444", bgColor: "#EF4444" }
    };
    return configs[type] || { label: type, icon: DollarSign, color: "#71717A", bgColor: "#71717A" };
  };

  const filteredTransactions = transactions.filter(tx => {
    if (filter === "all") return true;
    if (filter === "income") return tx.amount > 0;
    if (filter === "expense") return tx.amount < 0;
    if (filter === "commission") return tx.type === "commission";
    if (filter === "marketplace") return ["marketplace_purchase", "marketplace_sale"].includes(tx.type);
    if (filter === "offers") return ["offer_created", "offer_closed"].includes(tx.type);
    if (filter === "transfers") return ["transfer_sent", "transfer_received"].includes(tx.type);
    return true;
  });

  const totalIncome = transactions.filter(t => t.amount > 0).reduce((sum, t) => sum + t.amount, 0);
  const totalExpense = Math.abs(transactions.filter(t => t.amount < 0).reduce((sum, t) => sum + t.amount, 0));

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with Balance */}
      <div className="bg-gradient-to-r from-[#7C3AED]/20 to-[#10B981]/20 border border-white/10 rounded-2xl p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white mb-2">История транзакций</h1>
            <p className="text-[#71717A]">Все финансовые операции вашего аккаунта</p>
          </div>
          <div className="text-right">
            <div className="text-sm text-[#71717A]">Текущий баланс</div>
            <div className="text-3xl font-bold text-[#10B981] font-['JetBrains_Mono']">
              {balance.toFixed(2)} USDT
            </div>
          </div>
        </div>
        
        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mt-6 pt-6 border-t border-white/10">
          <div className="bg-white/5 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <ArrowDownRight className="w-4 h-4 text-[#10B981]" />
              <span className="text-[#71717A] text-sm">Поступления</span>
            </div>
            <div className="text-xl font-bold text-[#10B981]">+{totalIncome.toFixed(2)} USDT</div>
          </div>
          <div className="bg-white/5 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <ArrowUpRight className="w-4 h-4 text-[#EF4444]" />
              <span className="text-[#71717A] text-sm">Списания</span>
            </div>
            <div className="text-xl font-bold text-[#EF4444]">−{totalExpense.toFixed(2)} USDT</div>
          </div>
          <div className="bg-white/5 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <History className="w-4 h-4 text-[#7C3AED]" />
              <span className="text-[#71717A] text-sm">Всего операций</span>
            </div>
            <div className="text-xl font-bold text-white">{transactions.length}</div>
          </div>
        </div>
      </div>
      
      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        {[
          { value: "all", label: "Все" },
          { value: "income", label: "Поступления" },
          { value: "expense", label: "Списания" },
          { value: "commission", label: "Комиссии" },
          { value: "marketplace", label: "Маркетплейс" },
          { value: "offers", label: "Объявления" },
          { value: "transfers", label: "Переводы" }
        ].map(f => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
              filter === f.value
                ? "bg-[#7C3AED] text-white"
                : "bg-white/5 text-[#71717A] hover:bg-white/10"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>
      
      {/* Transactions List */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl overflow-hidden">
        {filteredTransactions.length === 0 ? (
          <div className="text-center py-12">
            <History className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
            <p className="text-[#71717A]">Транзакций не найдено</p>
          </div>
        ) : (
          <div className="divide-y divide-white/5">
            {filteredTransactions.map((tx) => {
              const config = getTypeConfig(tx.type);
              const Icon = config.icon;
              const isPositive = tx.amount > 0;
              
              return (
                <div key={tx.id} className="p-4 hover:bg-white/5 transition-colors">
                  <div className="flex items-center gap-4">
                    {/* Icon */}
                    <div 
                      className="w-10 h-10 rounded-xl flex items-center justify-center"
                      style={{ backgroundColor: `${config.bgColor}20` }}
                    >
                      <Icon className="w-5 h-5" style={{ color: config.color }} />
                    </div>
                    
                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-white">{config.label}</span>
                        <span 
                          className="px-2 py-0.5 rounded text-xs"
                          style={{ backgroundColor: `${config.bgColor}20`, color: config.color }}
                        >
                          {tx.reference_type}
                        </span>
                      </div>
                      <p className="text-sm text-[#71717A] truncate mt-1">{tx.description}</p>
                      {tx.reference_id && (
                        <p className="text-xs text-[#52525B] font-['JetBrains_Mono'] mt-1">
                          ID: {tx.reference_id.slice(0, 20)}...
                        </p>
                      )}
                    </div>
                    
                    {/* Amount & Date */}
                    <div className="text-right">
                      <div className={`font-bold font-['JetBrains_Mono'] ${isPositive ? "text-[#10B981]" : "text-[#EF4444]"}`}>
                        {isPositive ? "+" : ""}{tx.amount.toFixed(2)} {tx.currency || "USDT"}
                      </div>
                      {tx.commission > 0 && (
                        <div className="text-xs text-[#EF4444]">
                          −{tx.commission.toFixed(2)} USDT комиссия
                        </div>
                      )}
                      <div className="text-xs text-[#52525B] mt-1">
                        {new Date(tx.created_at).toLocaleString("ru-RU", {
                          day: "2-digit",
                          month: "2-digit",
                          year: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit"
                        })}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ==================== TRADER TRANSFERS ====================
function TraderTransfers() {
  const { token } = useAuth();
  const [recipient, setRecipient] = useState("");
  const [amount, setAmount] = useState("");
  const [balance, setBalance] = useState(0);
  const [transfers, setTransfers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchResults, setSearchResults] = useState([]);

  useEffect(() => {
    fetchBalance();
  }, []);

  const fetchBalance = async () => {
    try {
      const response = await axios.get(`${API}/traders/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setBalance(response.data.balance_usdt);
    } catch (error) {
      console.error(error);
    }
  };

  const handleSearch = async (query) => {
    setRecipient(query);
    if (query.length < 2) {
      setSearchResults([]);
      return;
    }
    try {
      const response = await axios.get(`${API}/users/search?query=${query}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSearchResults(response.data || []);
    } catch (error) {
      console.error(error);
    }
  };

  const handleTransfer = async (e) => {
    e.preventDefault();
    if (!recipient || !amount || parseFloat(amount) <= 0) {
      toast.error("Заполните все поля");
      return;
    }
    if (parseFloat(amount) > balance) {
      toast.error("Недостаточно средств");
      return;
    }

    setLoading(true);
    try {
      await axios.post(`${API}/transfers/send`, {
        recipient_nickname: recipient,
        amount: parseFloat(amount)
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(`Переведено ${amount} USDT пользователю @${recipient}`);
      setRecipient("");
      setAmount("");
      fetchBalance();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка перевода");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white font-['Unbounded']">Переводы</h1>
        <p className="text-[#71717A]">Перевод средств другим пользователям</p>
      </div>

      {/* Balance Info */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
        <div className="flex items-center justify-between">
          <div className="text-[#71717A]">Доступно для перевода</div>
          <div className="text-xl font-bold text-[#10B981] font-['JetBrains_Mono']">{balance.toFixed(2)} USDT</div>
        </div>
      </div>

      {/* Transfer Form */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Новый перевод</h3>
        <form onSubmit={handleTransfer} className="space-y-4">
          <div className="relative">
            <label className="block text-sm text-[#A1A1AA] mb-2">Получатель (никнейм)</label>
            <Input
              value={recipient}
              onChange={(e) => handleSearch(e.target.value)}
              placeholder="@username"
              className="bg-[#0A0A0A] border-white/10 text-white h-12 rounded-xl"
            />
            {searchResults.length > 0 && (
              <div className="absolute z-10 w-full mt-1 bg-[#1A1A1A] border border-white/10 rounded-xl overflow-hidden">
                {searchResults.map((user) => (
                  <button
                    key={user.id}
                    type="button"
                    onClick={() => { setRecipient(user.nickname); setSearchResults([]); }}
                    className="w-full px-4 py-3 text-left hover:bg-white/5 flex items-center gap-2"
                  >
                    <div className="w-8 h-8 rounded-full bg-[#7C3AED]/20 flex items-center justify-center text-[#A78BFA] text-sm">
                      {user.nickname[0].toUpperCase()}
                    </div>
                    <span className="text-white">@{user.nickname}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          <div>
            <label className="block text-sm text-[#A1A1AA] mb-2">Сумма (USDT)</label>
            <Input
              type="number"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.00"
              className="bg-[#0A0A0A] border-white/10 text-white h-12 rounded-xl font-['JetBrains_Mono']"
            />
          </div>
          <Button 
            type="submit" 
            disabled={loading || !recipient || !amount}
            className="w-full bg-[#7C3AED] hover:bg-[#6D28D9] h-12 rounded-xl"
          >
            {loading ? (
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <>
                <ArrowUpRight className="w-4 h-4 mr-2" />
                Перевести
              </>
            )}
          </Button>
        </form>
      </div>
    </div>
  );
}

// ==================== MY GUARANTOR DEALS ====================
function MyGuarantorDeals() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [deals, setDeals] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDeals();
  }, []);

  const fetchDeals = async () => {
    try {
      const response = await axios.get(`${API}/guarantor/deals`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setDeals(response.data || []);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    const styles = {
      pending_counterparty: "bg-[#F59E0B]/10 text-[#F59E0B]",
      pending_payment: "bg-[#3B82F6]/10 text-[#3B82F6]",
      funded: "bg-[#10B981]/10 text-[#10B981]",
      completed: "bg-[#10B981]/10 text-[#10B981]",
      disputed: "bg-[#EF4444]/10 text-[#EF4444]",
      cancelled: "bg-[#71717A]/10 text-[#71717A]"
    };
    const labels = {
      pending_counterparty: "Ожидает участника",
      pending_payment: "Ожидает оплаты",
      funded: "Средства внесены",
      completed: "Завершена",
      disputed: "Спор",
      cancelled: "Отменена"
    };
    return (
      <span className={`px-2 py-1 text-xs rounded-full font-medium ${styles[status] || styles.pending_counterparty}`}>
        {labels[status] || status}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-[#7C3AED] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white font-['Unbounded']">Мои гарант-сделки</h1>
          <p className="text-[#71717A]">Сделки с гарантом как покупатель или продавец</p>
        </div>
        <Link to="/guarantor/create">
          <Button className="bg-[#7C3AED] hover:bg-[#6D28D9] rounded-full">
            <Plus className="w-4 h-4 mr-2" />
            Создать сделку
          </Button>
        </Link>
      </div>

      {deals.length === 0 ? (
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-12 text-center">
          <Shield className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
          <p className="text-[#71717A]">У вас пока нет гарант-сделок</p>
          <p className="text-sm text-[#52525B] mt-1">Создайте новую сделку или присоединитесь по ссылке</p>
          <Link to="/guarantor/create">
            <Button className="mt-4 bg-[#7C3AED] hover:bg-[#6D28D9] rounded-full px-6">
              Создать сделку
            </Button>
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {deals.map((deal) => (
            <Link key={deal.id} to={`/guarantor/deal/${deal.id}`}>
              <div className="bg-[#121212] border border-white/5 hover:border-[#7C3AED]/30 rounded-xl p-5 transition-colors">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="text-white font-semibold">{deal.title}</div>
                    <div className="text-sm text-[#71717A]">
                      {deal.creator_role === 'buyer' ? 'Вы покупатель' : 'Вы продавец'}
                      {deal.counterparty_nickname && ` • с @${deal.counterparty_nickname}`}
                    </div>
                  </div>
                  {getStatusBadge(deal.status)}
                </div>
                <div className="flex items-center justify-between">
                  <div className="text-sm text-[#52525B]">
                    {new Date(deal.created_at).toLocaleDateString("ru-RU")}
                  </div>
                  <div className="text-lg font-bold text-[#10B981] font-['JetBrains_Mono']">
                    {deal.amount} {deal.currency}
                  </div>
                </div>
                {deal.invite_link && deal.status === 'pending_counterparty' && (
                  <div className="mt-3 p-2 bg-[#7C3AED]/10 rounded-lg">
                    <div className="text-xs text-[#A78BFA]">Ссылка для приглашения:</div>
                    <div className="text-sm text-white font-mono truncate">{window.location.origin}{deal.invite_link}</div>
                  </div>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}



// ==================== TRADER ACCOUNT ====================
function TraderAccount() {
  const { user, token } = useAuth();
  const [trader, setTrader] = useState(null);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    fetchTraderInfo();
  }, []);

  const fetchTraderInfo = async () => {
    try {
      const [traderRes, statsRes] = await Promise.all([
        axios.get(`${API}/traders/me`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/traders/stats`, { headers: { Authorization: `Bearer ${token}` } })
      ]);
      setTrader(traderRes.data);
      setStats(statsRes.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-[#7C3AED] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold text-white font-['Unbounded']">Аккаунт</h1>
        <p className="text-[#71717A]">Информация о вашем профиле</p>
      </div>

      {/* Profile Card */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl overflow-hidden">
        {/* Header with avatar */}
        <div className="bg-gradient-to-br from-[#7C3AED]/20 to-[#A855F7]/10 p-6 border-b border-white/5">
          <div className="flex items-center gap-4">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-[#7C3AED] to-[#A855F7] flex items-center justify-center text-white text-3xl font-bold">
              {(trader?.nickname || trader?.login || "U")[0].toUpperCase()}
            </div>
            <div>
              <h2 className="text-2xl font-bold text-white">@{trader?.nickname || trader?.login}</h2>
              <div className="flex items-center gap-2 text-[#71717A] text-sm mt-1">
                <Calendar className="w-4 h-4" />
                <span>Зарегистрирован: {trader?.created_at ? new Date(trader.created_at).toLocaleDateString("ru-RU", { day: 'numeric', month: 'long', year: 'numeric' }) : '—'}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Info Grid */}
        <div className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-[#0A0A0A] rounded-xl p-4">
              <div className="text-xs text-[#71717A] mb-1">Никнейм</div>
              <div className="text-white font-medium">@{trader?.nickname || '—'}</div>
            </div>
            <div className="bg-[#0A0A0A] rounded-xl p-4">
              <div className="text-xs text-[#71717A] mb-1">Логин</div>
              <div className="text-white font-medium">{trader?.login || '—'}</div>
            </div>
            <div className="bg-[#0A0A0A] rounded-xl p-4">
              <div className="text-xs text-[#71717A] mb-1">Баланс USDT</div>
              <div className="text-[#10B981] font-bold font-['JetBrains_Mono']">{trader?.balance_usdt?.toFixed(2) || '0.00'}</div>
            </div>
          </div>

          {/* Referral */}
          {trader?.referral_code && (
            <div className="bg-[#0A0A0A] rounded-xl p-4">
              <div className="text-xs text-[#71717A] mb-1">Реферальный код</div>
              <div className="flex items-center gap-2">
                <code className="text-[#F59E0B] font-['JetBrains_Mono']">{trader.referral_code}</code>
                <button 
                  onClick={() => {
                    navigator.clipboard.writeText(trader.referral_code);
                    toast.success('Скопировано!');
                  }}
                  className="p-1 hover:bg-white/10 rounded"
                >
                  <Copy className="w-4 h-4 text-[#71717A]" />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Stats Card */}
      {stats && (
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Статистика P2P</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-4 bg-[#0A0A0A] rounded-xl">
              <div className="text-2xl font-bold text-[#10B981]">{stats.salesCount || 0}</div>
              <div className="text-xs text-[#71717A]">Продаж</div>
            </div>
            <div className="text-center p-4 bg-[#0A0A0A] rounded-xl">
              <div className="text-2xl font-bold text-[#3B82F6]">{stats.purchasesCount || 0}</div>
              <div className="text-xs text-[#71717A]">Покупок</div>
            </div>
            <div className="text-center p-4 bg-[#0A0A0A] rounded-xl">
              <div className="text-lg font-bold text-[#10B981] font-['JetBrains_Mono']">{(stats.salesVolume || 0).toFixed(2)}</div>
              <div className="text-xs text-[#71717A]">Оборот продаж</div>
            </div>
            <div className="text-center p-4 bg-[#0A0A0A] rounded-xl">
              <div className="text-lg font-bold text-[#3B82F6] font-['JetBrains_Mono']">{(stats.purchasesVolume || 0).toFixed(2)}</div>
              <div className="text-xs text-[#71717A]">Оборот покупок</div>
            </div>
          </div>
        </div>
      )}

      {/* Shop Info if has shop */}
      {trader?.has_shop && trader?.shop_settings && (
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Store className="w-5 h-5 text-[#A78BFA]" />
            Мой магазин
          </h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[#71717A]">Название</span>
              <span className="text-white">{trader.shop_settings.shop_name || '—'}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[#71717A]">Комиссия платформы</span>
              <span className="text-[#F59E0B]">{trader.shop_settings.commission_rate || 5}%</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[#71717A]">Статус</span>
              <span className={`px-2 py-1 rounded text-xs ${trader.shop_settings.is_active ? 'bg-[#10B981]/10 text-[#10B981]' : 'bg-[#EF4444]/10 text-[#EF4444]'}`}>
                {trader.shop_settings.is_active ? 'Активен' : 'Неактивен'}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

