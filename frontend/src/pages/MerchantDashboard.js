import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { useWebSocket } from "@/hooks/useWebSocket";
import { Routes, Route, Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { toast } from "sonner";
import { useAuth, API } from "@/App";
import axios from "axios";
import { 
  Wallet, LogOut, History, MessageCircle, Settings, Key, BarChart3,
  Copy, DollarSign, Clock, CheckCircle, Send, AlertTriangle, Home,
  User, Lock, Eye, EyeOff, ArrowUpRight, ArrowDownRight, CreditCard,
  ChevronDown, ChevronRight, Store, TrendingUp, XCircle, Plus, ChevronLeft,
  RefreshCw, Loader, ArrowRightLeft, ShoppingBag, HelpCircle, Users,
  ListOrdered, FileText, Menu, PieChart, Activity, Percent, Banknote,
  ArrowDown, ArrowUp, Shield, Zap, Target, TrendingDown, LayoutDashboard, Package, Edit, Trash2, Download} from "lucide-react";
import MerchantMessagesPage from "./MerchantMessagesPage";
import MerchantAPI from "./MerchantAPI";
import MerchantDisputesPage from "./MerchantDisputesPage";
import ShopChats from "./ShopChats";
import MarketplaceGuarantorChat from "./MarketplaceGuarantorChat";
import EventNotificationDropdown from "@/components/EventNotificationDropdown";
import UserFinancePage from "./finance/UserFinancePage";

export default function MerchantDashboard() {
  const { user, token, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarBadges, setSidebarBadges] = useState({});
  
  const [expandedSections, setExpandedSections] = useState({
    trading: true,
        finances: false,
    account: false
  });

  const toggleSection = (key) => {
    setExpandedSections(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  // Fetch sidebar badges (same as trader)
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
      const interval = setInterval(fetchBadges, 30000);
      return () => clearInterval(interval);
    }
  }, [token]);

  const isPending = user?.status === "pending";
  const isRejected = user?.status === "rejected";

  const Badge = ({ count }) => {
    if (!count || count === 0) return null;
    return (
      <span className="ml-auto bg-[#EF4444] text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center">
        {count > 99 ? "99+" : count}
      </span>
    );
  };

  const sections = isPending ? [] : [
    {
      key: "dashboard",
      title: "Дашборд",
      icon: LayoutDashboard,
      single: true,
      path: "/merchant"
    },
    {
      key: "trading",
      title: "Торговля",
      icon: TrendingUp,
      notifyKey: "trades",
      items: [
        { path: "/merchant/withdrawal-requests", icon: ArrowUpRight, label: "Заявки на выплаты", notifyKey: "withdrawals" },
        { path: "/merchant/payments", icon: DollarSign, label: "Платежи", notifyKey: "payments" }
      ]
    },
    {
      key: "analytics",
      title: "Аналитика",
      icon: BarChart3,
      single: true,
      path: "/merchant/analytics"
    },

    {
      key: "api",
      title: "API Интеграция",
      icon: Key,
      single: true,
      path: "/merchant/api"
    },

    {
      key: "finances",
      title: "Финансы",
      icon: Wallet,
      items: [
        { path: "/merchant/ton-finance", icon: Wallet, label: "TON Кошелёк" },
        { path: "/merchant/transactions", icon: History, label: "Транзакции" },
        { path: "/merchant/withdraw", icon: ArrowUpRight, label: "Вывод средств" }
      ]
    },
    {
      key: "messages",
      title: "Сообщения",
      icon: MessageCircle,
      notifyKey: "messages",
      single: true,
      path: "/merchant/messages"
    },
    {
      key: "account",
      title: "Аккаунт",
      icon: User,
      items: [
        { path: "/merchant/account", icon: User, label: "Профиль" },
        { path: "/merchant/settings", icon: Settings, label: "Настройки" }
      ]
    }
  ];

  const isActive = (path, exact) => {
    if (exact) return location.pathname === path;
    return location.pathname === path || location.pathname.startsWith(path + "/");
  };

  const isSectionActive = (section) => {
    if (section.single) {
      if (section.key === "dashboard") return location.pathname === "/merchant";
      return isActive(section.path);
    }
    return section.items?.some(item => isActive(item.path, item.exact));
  };

  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Auto-expand active section on route change
  useEffect(() => {
    const path = location.pathname;
    setExpandedSections(prev => {
      const newState = { ...prev };
      if (path.startsWith("/merchant/withdrawal-requests") || path.startsWith("/merchant/payments") || path.startsWith("/merchant/disputes")) {
        newState.trading = true;
      }

      if (path.startsWith("/merchant/transactions") || path.startsWith("/merchant/withdraw")) {
        newState.finances = true;
      }
      if (path.startsWith("/merchant/account") || path.startsWith("/merchant/settings")) {
        newState.account = true;
      }
      return newState;
    });
  }, [location.pathname]);

  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  return (
    <div className="min-h-screen bg-[#0A0A0A] flex">
      {/* Mobile Header */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-40 bg-[#0A0A0A] border-b border-white/5 px-4 py-3 flex items-center justify-between">
        <button 
          onClick={() => setSidebarOpen(true)}
          className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center text-white"
        >
          <Menu className="w-5 h-5" />
        </button>
        <div className="flex items-center gap-2">
          <img src="/logo.png" alt="Reptiloid" className="h-8 w-8" />
          <div className="text-white text-sm font-medium">{user?.merchant_name || user?.login}</div>
        </div>
        {!isPending && (
          <div className="text-[#F97316] font-medium text-sm font-mono">
            {(user?.balance_usdt || 0).toFixed(2)}
          </div>
        )}
      </div>

      {/* Mobile Overlay */}
      {sidebarOpen && (
        <div 
          className="lg:hidden fixed inset-0 bg-black/60 z-40"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        w-64 bg-[#0A0A0A] border-r border-white/5 flex flex-col h-full
        fixed z-50
        transform transition-transform duration-200 ease-in-out
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
        {/* Logo */}
        <div className="p-4 border-b border-white/5 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3">
            <img src="/logo.png" alt="Reptiloid" className="h-9 w-9" />
            <div>
              <div className="text-white font-bold">Reptiloid</div>
              <div className="text-[10px] text-[#F97316] font-medium">MERCHANT</div>
            </div>
          </Link>
          <button 
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden w-8 h-8 rounded-lg hover:bg-white/5 flex items-center justify-center text-[#71717A]"
          >
            <XCircle className="w-5 h-5" />
          </button>
        </div>

        {/* Balance Preview */}
        {!isPending && (
          <div className="p-4 border-b border-white/5">
            <div className="flex items-center justify-between mb-1">
              <div className="text-[10px] text-[#52525B] uppercase tracking-wider">Баланс</div>
              <EventNotificationDropdown token={token} role="merchant" />
            </div>
            <div className="text-xl font-bold text-white font-['JetBrains_Mono']">
              {(user?.balance_usdt || 0).toFixed(2)} <span className="text-[#F97316]">USDT</span>
            </div>
          </div>
        )}

        {/* Navigation */}
        <nav className="flex-1 p-2 space-y-1 overflow-y-auto">
          {/* Home link */}
          <Link to="/">
            <div className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-[#71717A] hover:text-white hover:bg-white/5 transition-colors">
              <Home className="w-4 h-4" />
              <span className="text-sm">Главная</span>
            </div>
          </Link>

          {isPending ? (
            <Link to="/merchant">
              <div className={`flex items-center gap-3 px-3 py-2.5 rounded-xl transition-colors ${
                location.pathname === "/merchant" 
                  ? "bg-[#F97316]/10 text-[#F97316]" 
                  : "text-[#71717A] hover:text-white hover:bg-white/5"
              }`}>
                <MessageCircle className="w-4 h-4" />
                <span className="text-sm">Чат с админом</span>
              </div>
            </Link>
          ) : (
            <>
              {sections.map(section => (
                <div key={section.key}>
                  {section.single ? (
                    <Link to={section.path}>
                      <div className={`flex items-center gap-3 px-3 py-2.5 rounded-xl transition-colors ${
                        isSectionActive(section)
                          ? "bg-[#F97316]/10 text-[#F97316]"
                          : "text-[#71717A] hover:text-white hover:bg-white/5"
                      }`}>
                        <section.icon className="w-4 h-4" />
                        <span className="text-sm">{section.title}</span>
                        <Badge count={sidebarBadges[section.notifyKey]} />
                      </div>
                    </Link>
                  ) : (
                    <>
                      <button
                        onClick={() => toggleSection(section.key)}
                        className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-colors ${
                          isSectionActive(section)
                            ? "bg-[#F97316]/10 text-[#F97316]"
                            : "text-[#71717A] hover:text-white hover:bg-white/5"
                        }`}
                      >
                        <section.icon className="w-4 h-4" />
                        <span className="text-sm flex-1 text-left">{section.title}</span>
                        <Badge count={sidebarBadges[section.notifyKey]} />
                        <ChevronDown className={`w-4 h-4 transition-transform ${expandedSections[section.key] ? "rotate-180" : ""}`} />
                      </button>
                      
                      {expandedSections[section.key] && section.items && (
                        <div className="ml-4 mt-1 space-y-1 border-l border-white/5 pl-3">
                          {section.items.map(item => (
                            <Link key={item.path} to={item.path}>
                              <div className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                                isActive(item.path, item.exact)
                                  ? "bg-white/5 text-white"
                                  : "text-[#52525B] hover:text-[#A1A1AA] hover:bg-white/5"
                              }`}>
                                <item.icon className="w-3.5 h-3.5" />
                                <span className="text-xs">{item.label}</span>
                                <Badge count={sidebarBadges[item.notifyKey]} />
                              </div>
                            </Link>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                </div>
              ))}
            </>
          )}
        </nav>

        {/* User Info & Logout */}
        <div className="p-4 border-t border-white/5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 bg-[#F97316]/10 rounded-xl flex items-center justify-center">
              <User className="w-5 h-5 text-[#F97316]" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-white text-sm font-medium truncate">
                {user?.nickname || user?.merchant_name || user?.login}
              </div>
              <div className="text-[10px] text-[#F97316]">Мерчант</div>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={logout}
            className="w-full border-white/10 text-[#71717A] hover:text-white hover:bg-white/5"
           title="Выйти из аккаунта">
            <LogOut className="w-4 h-4 mr-2" />
            Выйти
          </Button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 ml-0 lg:ml-64 p-4 lg:p-6 pt-20 lg:pt-6">
        {isPending ? (
          <PendingMerchantChat />
        ) : isRejected ? (
          <RejectedView />
        ) : (
          <Routes>
            <Route index element={<MerchantMainDashboard />} />
            <Route path="withdrawal-requests" element={<MerchantWithdrawalRequests />} />
            <Route path="payments" element={<MerchantPayments />} />
            <Route path="analytics" element={<MerchantAnalytics />} />
            <Route path="disputes" element={<MerchantDisputesPage />} />
            <Route path="api" element={<MerchantAPI />} />
            <Route path="transactions" element={<MerchantTransactions />} />
            <Route path="ton-finance" element={<UserFinancePage />} />
            <Route path="withdraw" element={<MerchantWithdraw />} />
            <Route path="account" element={<MerchantAccount />} />
            <Route path="settings" element={<MerchantSettings />} />
            <Route path="messages" element={<MerchantMessagesPage />} />
                                    <Route path="shop" element={<MerchantShop />} />
                      </Routes>
        )}
      </main>
    </div>
  );
}


function NotificationDropdown({ badges, token, role }) {
  const [open, setOpen] = useState(false);
  const [localBadges, setLocalBadges] = useState(badges);
  const dropdownRef = useRef(null);
  const buttonRef = useRef(null);
  const prefix = role === "merchant" ? "/merchant" : "/trader";

  useEffect(() => { setLocalBadges(badges); }, [badges]);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target) && buttonRef.current && !buttonRef.current.contains(event.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const declension = (n) => {
    const abs = Math.abs(n) % 100;
    const n1 = abs % 10;
    if (abs > 10 && abs < 20) return "событий";
    if (n1 > 1 && n1 < 5) return "события";
    if (n1 === 1) return "событие";
    return "событий";
  };

  const buildNotificationList = () => {
    const b = localBadges;
    const items = [];
    if (b.trades > 0) items.push({ key: "trades", label: "Активные сделки", path: `${prefix}/payments`, count: b.trades });
    if (b.shop_messages > 0) items.push({ key: "shop_messages", label: "Сообщения магазина", path: `${prefix}/shop`, count: b.shop_messages });
    if (b.messages > 0) items.push({ key: "messages", label: "Сообщения", path: `${prefix}/messages`, count: b.messages });
    if (b.deposits > 0) items.push({ key: "deposits", label: "Пополнения", path: `${prefix}/transactions`, count: b.deposits });
    if (b.withdrawals > 0) items.push({ key: "withdrawals", label: "Вывод средств", path: `${prefix}/withdraw`, count: b.withdrawals });
    if (b.trade_payment > 0) items.push({ key: "trade_payment", label: "Оплата в сделке", path: `${prefix}/payments`, count: b.trade_payment });
    if (b.trade_message > 0) items.push({ key: "trade_message", label: "Сообщение в сделке", path: `${prefix}/payments`, count: b.trade_message });
    if (b.trade_dispute > 0) items.push({ key: "trade_dispute", label: "Спор в сделке", path: `${prefix}/disputes`, count: b.trade_dispute });
    return items;
  };

  const handleItemClick = async (item) => {
    const updated = { ...localBadges, [item.key]: 0 };
    updated.total = Object.entries(updated).filter(([k]) => !["total","trade_payments","trade_events","disputes","guarantor_unread","support","shop_customer_messages"].includes(k)).reduce((s, [, v]) => s + (v || 0), 0);
    setLocalBadges(updated);
    setOpen(false);
    try {
      await axios.post(`${API}/notifications/read`, { type: item.key }, { headers: { Authorization: `Bearer ${token}` } });
    } catch (e) { console.error(e); }
    window.location.href = item.path;
  };

  const handleReadAll = async () => {
    const zeroed = {};
    Object.keys(localBadges).forEach(k => zeroed[k] = 0);
    setLocalBadges(zeroed);
    setOpen(false);
    try {
      await axios.post(`${API}/notifications/read`, {}, { headers: { Authorization: `Bearer ${token}` } });
    } catch (e) { console.error(e); }
  };

  const total = localBadges.total || 0;
  const items = buildNotificationList();

  const getDropdownPos = () => {
    if (!buttonRef.current) return { top: 100, left: 60 };
    const r = buttonRef.current.getBoundingClientRect();
    return { top: r.bottom + 4, left: Math.max(r.left, 10) };
  };

  return (
    <>
      <button
        ref={buttonRef}
        onClick={() => setOpen(!open)}
        className={total > 0 ? "text-xs text-[#EF4444] bg-[#EF4444]/10 px-2 py-0.5 rounded-full hover:bg-[#EF4444]/20 transition-colors cursor-pointer whitespace-nowrap" : "text-xs text-[#52525B] bg-white/5 px-2 py-0.5 rounded-full hover:bg-white/10 transition-colors cursor-pointer whitespace-nowrap"}
      >
        {total > 0 ? `${total} ${declension(total)}` : "Нет событий"}
      </button>
      {open && createPortal(
        <div ref={dropdownRef} style={{position: "fixed", top: getDropdownPos().top, left: getDropdownPos().left, zIndex: 99999, minWidth: "300px", width: "320px"}} className="bg-[#1A1A1A] border border-white/10 rounded-xl shadow-2xl overflow-hidden">
          <div className="p-3 border-b border-white/5">
            <div className="text-xs font-medium text-white">Оповещения</div>
          </div>
          <div className="max-h-80 overflow-y-auto">
            {items.length === 0 ? (
              <div className="p-4 text-center text-xs text-[#52525B]">Нет оповещений</div>
            ) : (
              items.map((item) => (
                <button
                  key={item.key}
                  onClick={() => handleItemClick(item)}
                  className="w-full text-left px-4 py-3 hover:bg-white/5 transition-colors border-b border-white/5 last:border-0 flex items-center justify-between gap-3"
                >
                  <span className="text-sm text-[#A1A1AA]">{item.label}</span>
                  <span className="text-[10px] bg-[#EF4444] text-white rounded-full px-1.5 py-0.5 min-w-[20px] text-center font-bold flex-shrink-0">
                    {item.count}
                  </span>
                </button>
              ))
            )}
          </div>
          <div className="p-2 border-t border-white/5">
            <button onClick={handleReadAll} className="w-full text-center py-2 text-xs text-[#7C3AED] hover:bg-[#7C3AED]/10 rounded-lg transition-colors">
              Прочитать всё
            </button>
          </div>
        </div>,
        document.body
      )}
    </>
  );
}

// ==================== PENDING MERCHANT CHAT ====================
function PendingMerchantChat() {
  const { user, token } = useAuth();
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [conversation, setConversation] = useState(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    fetchConversation();
    const interval = setInterval(fetchMessages, 15000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const fetchConversation = async () => {
    try {
      const response = await axios.get(`${API}/msg/merchant/conversations`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const conv = response.data?.find(c => c.type === "merchant_application");
      if (conv) {
        setConversation(conv);
        await fetchMessages(conv.id);
      }
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const fetchMessages = async (convId) => {
    const id = convId || conversation?.id;
    if (!id) return;
    try {
      const response = await axios.get(`${API}/msg/merchant/conversations/${id}/messages`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setMessages(response.data || []);
    } catch (error) {
      console.error(error);
    }
  };

  const handleSend = async () => {
    if (!newMessage.trim() || !conversation) return;
    setSending(true);
    try {
      await axios.post(`${API}/msg/merchant/conversations/${conversation.id}/messages`,
        { content: newMessage },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setNewMessage("");
      await fetchMessages();
    } catch (error) {
      toast.error("Ошибка отправки");
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader className="w-8 h-8 text-[#F97316] animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto">
      <div className="bg-[#F97316]/10 border border-[#F97316]/20 rounded-2xl p-4 mb-6">
        <div className="flex items-center gap-3">
          <Clock className="w-6 h-6 text-[#F97316]" />
          <div>
            <div className="text-white font-medium">Заявка на рассмотрении</div>
            <div className="text-sm text-[#A1A1AA]">Администратор рассмотрит вашу заявку в ближайшее время</div>
          </div>
        </div>
      </div>

      <div className="bg-[#121212] border border-white/5 rounded-2xl overflow-hidden" style={{ height: "500px" }}>
        <div className="p-4 border-b border-white/5">
          <h3 className="text-white font-medium">Чат с администратором</h3>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3" style={{ height: "380px" }}>
          {messages.map(msg => (
            <div key={msg.id} className={`flex ${msg.sender_id === user?.id ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[70%] rounded-2xl px-4 py-2 ${
                msg.sender_id === user?.id
                  ? "bg-[#F97316] text-white"
                  : "bg-white/5 text-white"
              }`}>
                <p className="text-sm">{msg.content}</p>
                <p className="text-[10px] opacity-60 mt-1">
                  {new Date(msg.created_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}
                </p>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        <div className="p-4 border-t border-white/5 flex gap-2">
          <Input
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Написать сообщение..."
            className="bg-[#1A1A1A] border-white/10 text-white h-10 rounded-xl"
          />
          <Button onClick={handleSend} disabled={sending} className="bg-[#F97316] hover:bg-[#EA580C] h-10 px-4 rounded-xl">
            {sending ? <Loader className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ==================== REJECTED VIEW ====================
function RejectedView() {
  return (
    <div className="flex items-center justify-center h-[60vh]">
      <div className="text-center">
        <XCircle className="w-16 h-16 text-[#EF4444] mx-auto mb-4" />
        <h2 className="text-xl font-bold text-white mb-2">Заявка отклонена</h2>
        <p className="text-[#71717A]">К сожалению, ваша заявка на мерчанта была отклонена.</p>
      </div>
    </div>
  );
}

// ==================== MAIN DASHBOARD (Главная страница) ====================
function MerchantMainDashboard() {
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exchangeRate, setExchangeRate] = useState(null);

  useEffect(() => {
    fetchAnalytics();
    fetchExchangeRate();
    // Auto-refresh rate every 5 minutes
    const rateInterval = setInterval(fetchExchangeRate, 300000);
    return () => clearInterval(rateInterval);
  }, []);

  const fetchExchangeRate = async () => {
    try {
      const response = await axios.get(`${API.replace('/api', '')}/api/exchange-rate`);
      setExchangeRate(response.data);
    } catch (error) {
      console.error("Failed to fetch exchange rate:", error);
    }
  };

  const fetchAnalytics = async () => {
    try {
      const response = await axios.get(`${API}/merchant/analytics`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setAnalytics(response.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader className="w-8 h-8 text-[#F97316] animate-spin" />
      </div>
    );
  }

  const merchant = analytics?.merchant || {};
  const deposits = analytics?.deposits || {};
  const payouts = analytics?.payouts || {};
  const rates = analytics?.rates || {};
  const recent = analytics?.recent_activity || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Дашборд</h1>
          <p className="text-[#71717A] text-sm mt-1">Добро пожаловать, {merchant.name || user?.merchant_name || user?.login}</p>
        </div>
        <div className="flex items-center gap-3">
          {exchangeRate && (
            <div className="bg-[#121212] border border-white/5 rounded-xl px-4 py-2 flex items-center gap-2">
              <div className="w-2 h-2 bg-[#10B981] rounded-full animate-pulse" />
              <span className="text-[#71717A] text-sm">USDT/RUB</span>
              <span className="text-white font-bold font-['JetBrains_Mono']">{exchangeRate.base_rate?.toFixed(2)} ₽</span>
              <span className="text-[#52525B] text-xs">({exchangeRate.rate_source})</span>
            </div>
          )}
          <Button onClick={() => { fetchAnalytics(); fetchExchangeRate(); }} variant="outline" size="sm" className="border-white/10 text-[#71717A] hover:text-white">
            <RefreshCw className="w-4 h-4 mr-2" /> Обновить
          </Button>
        </div>
      </div>

      {/* Live Exchange Rate Banner */}
      {exchangeRate && (
        <div className="bg-gradient-to-r from-[#1E3A5F] to-[#0F172A] border border-[#3B82F6]/20 rounded-2xl p-5">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-[#3B82F6]/10 rounded-xl flex items-center justify-center">
                <TrendingUp className="w-6 h-6 text-[#3B82F6]" />
              </div>
              <div>
                <div className="text-white font-semibold text-lg">Базовый курс USDT</div>
                <div className="text-[#71717A] text-xs">Источник: биржа {exchangeRate.rate_source} · Обновляется каждые 5 мин</div>
              </div>
            </div>
            <div className="flex items-center gap-6">
              <div className="text-center">
                <div className="text-[#71717A] text-xs mb-1">Базовый курс</div>
                <div className="text-3xl font-bold text-[#3B82F6] font-['JetBrains_Mono']">{exchangeRate.base_rate?.toFixed(2)} ₽</div>
              </div>
              {exchangeRate.rate_updated_at && (
                <div className="text-center">
                  <div className="text-[#71717A] text-xs mb-1">Обновлено</div>
                  <div className="text-sm text-white">{new Date(exchangeRate.rate_updated_at).toLocaleTimeString("ru-RU")}</div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Balance Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-gradient-to-br from-[#F97316] to-[#EA580C] rounded-2xl p-5 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-white/5 rounded-full -mr-10 -mt-10" />
          <div className="relative">
            <div className="flex items-center gap-2 text-white/80 text-sm mb-2">
              <Wallet className="w-4 h-4" /> Доступный баланс
            </div>
            <div className="text-3xl font-bold text-white font-['JetBrains_Mono']">
              {(merchant.balance_usdt || 0).toFixed(2)}
            </div>
            <div className="text-white/60 text-sm mt-1">USDT</div>
          </div>
        </div>

        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="flex items-center gap-2 text-[#71717A] text-sm mb-2">
            <Clock className="w-4 h-4" /> Заморожено
          </div>
          <div className="text-3xl font-bold text-[#F59E0B] font-['JetBrains_Mono']">
            {(merchant.frozen_balance || 0).toFixed(2)}
          </div>
          <div className="text-[#52525B] text-sm mt-1">USDT</div>
        </div>

        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="flex items-center gap-2 text-[#71717A] text-sm mb-2">
            <TrendingUp className="w-4 h-4" /> Всего комиссий оплачено
          </div>
          <div className="text-3xl font-bold text-[#EF4444] font-['JetBrains_Mono']">
            {(merchant.total_commission_paid || 0).toFixed(2)}
          </div>
          <div className="text-[#52525B] text-sm mt-1">USDT</div>
        </div>
      </div>

      {/* Commission Info */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Percent className="w-5 h-5 text-[#F97316]" />
          <h2 className="text-lg font-semibold text-white">Ваши комиссии</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-[#0A0A0A] rounded-xl p-4 border border-white/5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className="w-10 h-10 bg-[#3B82F6]/10 rounded-xl flex items-center justify-center">
                  <ArrowDown className="w-5 h-5 text-[#3B82F6]" />
                </div>
                <div>
                  <div className="text-white font-medium">Пополнение (Платежи)</div>
                  <div className="text-xs text-[#71717A]">Комиссия с входящих платежей</div>
                </div>
              </div>
              <div className="text-2xl font-bold text-[#3B82F6] font-['JetBrains_Mono']">
                {merchant.commission_rate || 0}%
              </div>
            </div>
            <div className="text-xs text-[#52525B]">
              Списывается с каждого успешного пополнения от клиента
            </div>
          </div>

          <div className="bg-[#0A0A0A] rounded-xl p-4 border border-white/5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className="w-10 h-10 bg-[#10B981]/10 rounded-xl flex items-center justify-center">
                  <ArrowUp className="w-5 h-5 text-[#10B981]" />
                </div>
                <div>
                  <div className="text-white font-medium">Выплаты (Payouts)</div>
                  <div className="text-xs text-[#71717A]">Комиссия с выплат</div>
                </div>
              </div>
              <div className="text-2xl font-bold text-[#10B981] font-['JetBrains_Mono']">
                {merchant.withdrawal_commission || 3}%
              </div>
            </div>
            <div className="text-xs text-[#52525B]">
              Курс для вас: {rates.merchant_rate || "—"} ₽/USDT (базовый: {exchangeRate?.base_rate?.toFixed(2) || rates.base_rate || "—"} ₽)
            </div>
          </div>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-[#121212] border border-white/5 rounded-xl p-4 cursor-pointer hover:bg-white/5 transition-colors" onClick={() => navigate("/merchant/payments")}>
          <div className="flex items-center gap-2 text-[#71717A] text-xs mb-2">
            <DollarSign className="w-3.5 h-3.5" /> Платежи
          </div>
          <div className="text-2xl font-bold text-white">{deposits.count || 0}</div>
          <div className="text-xs text-[#10B981] mt-1">+{(deposits.total_usdt || 0).toFixed(2)} USDT</div>
        </div>

        <div className="bg-[#121212] border border-white/5 rounded-xl p-4 cursor-pointer hover:bg-white/5 transition-colors" onClick={() => navigate("/merchant/withdrawal-requests")}>
          <div className="flex items-center gap-2 text-[#71717A] text-xs mb-2">
            <ArrowUpRight className="w-3.5 h-3.5" /> Выплаты
          </div>
          <div className="text-2xl font-bold text-white">{(payouts.active_count || 0) + (payouts.completed_count || 0)}</div>
          <div className="text-xs text-[#F59E0B] mt-1">{payouts.active_count || 0} активных</div>
        </div>

        <div className="bg-[#121212] border border-white/5 rounded-xl p-4">
          <div className="flex items-center gap-2 text-[#71717A] text-xs mb-2">
            <Banknote className="w-3.5 h-3.5" /> Оборот (RUB)
          </div>
          <div className="text-2xl font-bold text-white font-['JetBrains_Mono']">
            {((deposits.total_rub || 0) + (payouts.total_rub || 0)).toLocaleString("ru-RU", {maximumFractionDigits: 0})}
          </div>
          <div className="text-xs text-[#71717A] mt-1">Всего в рублях</div>
        </div>

        <div className="bg-[#121212] border border-white/5 rounded-xl p-4">
          <div className="flex items-center gap-2 text-[#71717A] text-xs mb-2">
            <AlertTriangle className="w-3.5 h-3.5" /> Споры
          </div>
          <div className="text-2xl font-bold text-white">{(deposits.disputed_count || 0) + (payouts.orders_disputed || 0)}</div>
          <div className="text-xs text-[#EF4444] mt-1">Требуют внимания</div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl overflow-hidden">
        <div className="p-4 border-b border-white/5 flex items-center justify-between">
          <h3 className="text-white font-medium flex items-center gap-2">
            <Activity className="w-4 h-4 text-[#F97316]" /> Последние операции
          </h3>
          <Link to="/merchant/analytics" className="text-[#F97316] text-sm hover:underline">
            Вся аналитика
          </Link>
        </div>
        
        {recent.length === 0 ? (
          <div className="p-8 text-center">
            <Activity className="w-12 h-12 text-[#52525B] mx-auto mb-3" />
            <p className="text-[#71717A]">Пока нет операций</p>
          </div>
        ) : (
          <div className="divide-y divide-white/5">
            {recent.slice(0, 8).map((item, idx) => (
              <div key={idx} className="p-4 flex items-center justify-between hover:bg-white/5 transition-colors">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                    item.type === "deposit" ? "bg-[#3B82F6]/10" : "bg-[#10B981]/10"
                  }`}>
                    {item.type === "deposit" ? (
                      <ArrowDownRight className="w-5 h-5 text-[#3B82F6]" />
                    ) : (
                      <ArrowUpRight className="w-5 h-5 text-[#10B981]" />
                    )}
                  </div>
                  <div>
                    <div className="text-white text-sm font-medium">
                      {item.type === "deposit" ? "Пополнение" : "Выплата"}
                    </div>
                    <div className="text-xs text-[#52525B]">
                      {item.created_at ? new Date(item.created_at).toLocaleString("ru-RU") : "—"}
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className={`font-medium font-['JetBrains_Mono'] text-sm ${
                    item.type === "deposit" ? "text-[#3B82F6]" : "text-[#10B981]"
                  }`}>
                    {item.type === "deposit" ? "+" : "-"}{(item.amount_usdt || 0).toFixed(2)} USDT
                  </div>
                  <div className="text-xs text-[#52525B]">
                    {(item.amount_rub || 0).toLocaleString("ru-RU", {maximumFractionDigits: 0})} ₽
                  </div>
                </div>
                <div>
                  <span className={`text-xs px-2 py-1 rounded-lg ${
                    item.status === "completed" ? "bg-[#10B981]/10 text-[#10B981]" :
                    item.status === "active" ? "bg-[#3B82F6]/10 text-[#3B82F6]" :
                    item.status === "cancelled" ? "bg-[#71717A]/10 text-[#71717A]" :
                    item.status === "dispute" ? "bg-[#EF4444]/10 text-[#EF4444]" :
                    "bg-[#F59E0B]/10 text-[#F59E0B]"
                  }`}>
                    {item.status === "completed" ? "Завершено" :
                     item.status === "active" ? "Активно" :
                     item.status === "cancelled" ? "Отменено" :
                     item.status === "dispute" ? "Спор" :
                     item.status === "in_progress" ? "В процессе" :
                     item.status || "—"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ==================== ANALYTICS (Аналитика) ====================
function MerchantAnalytics() {
  const { token, user } = useAuth();
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exchangeRate, setExchangeRate] = useState(null);

  useEffect(() => {
    fetchAnalytics();
    fetchExchangeRate();
    // Auto-refresh rate every 5 minutes
    const rateInterval = setInterval(fetchExchangeRate, 300000);
    return () => clearInterval(rateInterval);
  }, []);

  const fetchExchangeRate = async () => {
    try {
      const response = await axios.get(`${API.replace('/api', '')}/api/exchange-rate`);
      setExchangeRate(response.data);
    } catch (error) {
      console.error("Failed to fetch exchange rate:", error);
    }
  };

  const fetchAnalytics = async () => {
    try {
      const response = await axios.get(`${API}/merchant/analytics`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setAnalytics(response.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader className="w-8 h-8 text-[#F97316] animate-spin" />
      </div>
    );
  }

  const merchant = analytics?.merchant || {};
  const deposits = analytics?.deposits || {};
  const payouts = analytics?.payouts || {};
  const invoices = analytics?.invoices || {};
  const withdrawals = analytics?.withdrawals || {};
  const rates = analytics?.rates || {};

  const totalVolume = (deposits.total_usdt || 0) + (payouts.total_usdt_deducted || 0);
  const totalRub = (deposits.total_rub || 0) + (payouts.total_rub || 0);
  const successRate = deposits.count > 0 
    ? ((deposits.count / (deposits.count + deposits.cancelled_count)) * 100).toFixed(1) 
    : "0.0";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Аналитика</h1>
          <p className="text-[#71717A] text-sm mt-1">Подробная статистика вашей деятельности</p>
        </div>
        <Button onClick={fetchAnalytics} variant="outline" size="sm" className="border-white/10 text-[#71717A] hover:text-white">
          <RefreshCw className="w-4 h-4 mr-2" /> Обновить
        </Button>
      </div>

      {/* Commission Overview */}
      <div className="bg-gradient-to-r from-[#1a1a2e] to-[#16213e] border border-[#3B82F6]/20 rounded-2xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Percent className="w-5 h-5 text-[#3B82F6]" />
          <h2 className="text-lg font-semibold text-white">Комиссии</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-black/20 rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Комиссия на платежи</div>
            <div className="text-3xl font-bold text-[#3B82F6] font-['JetBrains_Mono']">{merchant.commission_rate || 0}%</div>
            <div className="text-xs text-[#52525B] mt-1">С каждого пополнения</div>
          </div>
          <div className="bg-black/20 rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Комиссия на выплаты</div>
            <div className="text-3xl font-bold text-[#10B981] font-['JetBrains_Mono']">{merchant.withdrawal_commission || 3}%</div>
            <div className="text-xs text-[#52525B] mt-1">С каждой выплаты</div>
          </div>
          <div className="bg-black/20 rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Оплачено комиссий</div>
            <div className="text-3xl font-bold text-[#EF4444] font-['JetBrains_Mono']">{(merchant.total_commission_paid || 0).toFixed(2)}</div>
            <div className="text-xs text-[#52525B] mt-1">USDT за всё время</div>
          </div>
          <div className="bg-black/20 rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Ваш курс выплат</div>
            <div className="text-3xl font-bold text-[#F97316] font-['JetBrains_Mono']">{rates.merchant_rate || "—"}</div>
            <div className="text-xs text-[#52525B] mt-1">₽ за 1 USDT</div>
          </div>
        </div>
      </div>

      {/* Deposits Stats */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <ArrowDownRight className="w-5 h-5 text-[#3B82F6]" />
          <h2 className="text-lg font-semibold text-white">Пополнения (Платежи)</h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Всего сделок</div>
            <div className="text-2xl font-bold text-white">{deposits.count || 0}</div>
          </div>
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Оборот USDT</div>
            <div className="text-2xl font-bold text-[#3B82F6] font-['JetBrains_Mono']">{(deposits.total_usdt || 0).toFixed(2)}</div>
          </div>
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Оборот RUB</div>
            <div className="text-2xl font-bold text-white font-['JetBrains_Mono']">{(deposits.total_rub || 0).toLocaleString("ru-RU", {maximumFractionDigits: 0})}</div>
          </div>
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Комиссия</div>
            <div className="text-2xl font-bold text-[#EF4444] font-['JetBrains_Mono']">{(deposits.total_commission || 0).toFixed(4)}</div>
            <div className="text-xs text-[#52525B]">USDT</div>
          </div>
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Активные</div>
            <div className="text-2xl font-bold text-[#F59E0B]">{deposits.active_count || 0}</div>
          </div>
        </div>
        
        {/* Progress bars */}
        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-[#71717A]">Успешность</span>
              <span className="text-xs text-[#10B981] font-medium">{successRate}%</span>
            </div>
            <div className="w-full bg-white/5 rounded-full h-2">
              <div className="bg-[#10B981] h-2 rounded-full transition-all" style={{ width: `${Math.min(parseFloat(successRate), 100)}%` }} />
            </div>
          </div>
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-[#71717A]">Споры</span>
              <span className="text-xs text-[#EF4444] font-medium">{deposits.disputed_count || 0}</span>
            </div>
            <div className="w-full bg-white/5 rounded-full h-2">
              <div className="bg-[#EF4444] h-2 rounded-full transition-all" style={{ width: `${deposits.count > 0 ? ((deposits.disputed_count || 0) / deposits.count * 100) : 0}%` }} />
            </div>
          </div>
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-[#71717A]">Отменённые</span>
              <span className="text-xs text-[#71717A] font-medium">{deposits.cancelled_count || 0}</span>
            </div>
            <div className="w-full bg-white/5 rounded-full h-2">
              <div className="bg-[#71717A] h-2 rounded-full transition-all" style={{ width: `${deposits.count > 0 ? ((deposits.cancelled_count || 0) / (deposits.count + (deposits.cancelled_count || 0)) * 100) : 0}%` }} />
            </div>
          </div>
        </div>
      </div>

      {/* Payouts Stats */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <ArrowUpRight className="w-5 h-5 text-[#10B981]" />
          <h2 className="text-lg font-semibold text-white">Выплаты (Payouts)</h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Активные заявки</div>
            <div className="text-2xl font-bold text-[#F59E0B]">{payouts.active_count || 0}</div>
          </div>
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Завершённые</div>
            <div className="text-2xl font-bold text-[#10B981]">{payouts.completed_count || 0}</div>
          </div>
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Списано USDT</div>
            <div className="text-2xl font-bold text-white font-['JetBrains_Mono']">{(payouts.total_usdt_deducted || 0).toFixed(2)}</div>
          </div>
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Выплачено RUB</div>
            <div className="text-2xl font-bold text-white font-['JetBrains_Mono']">{(payouts.total_rub || 0).toLocaleString("ru-RU", {maximumFractionDigits: 0})}</div>
          </div>
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Заказы (споры)</div>
            <div className="text-2xl font-bold text-[#EF4444]">{payouts.orders_disputed || 0}</div>
          </div>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-gradient-to-br from-[#10B981]/10 to-[#10B981]/5 border border-[#10B981]/20 rounded-2xl p-5">
          <div className="flex items-center gap-2 text-[#10B981] text-sm mb-2">
            <TrendingUp className="w-4 h-4" /> Общий оборот
          </div>
          <div className="text-2xl font-bold text-white font-['JetBrains_Mono']">
            {totalVolume.toFixed(2)} <span className="text-sm text-[#71717A]">USDT</span>
          </div>
          <div className="text-sm text-[#71717A] mt-1">
            {totalRub.toLocaleString("ru-RU", {maximumFractionDigits: 0})} ₽
          </div>
        </div>

        <div className="bg-gradient-to-br from-[#3B82F6]/10 to-[#3B82F6]/5 border border-[#3B82F6]/20 rounded-2xl p-5">
          <div className="flex items-center gap-2 text-[#3B82F6] text-sm mb-2">
            <Target className="w-4 h-4" /> Успешность
          </div>
          <div className="text-2xl font-bold text-white font-['JetBrains_Mono']">
            {successRate}%
          </div>
          <div className="text-sm text-[#71717A] mt-1">
            {deposits.count || 0} из {(deposits.count || 0) + (deposits.cancelled_count || 0)} сделок
          </div>
        </div>

        <div className="bg-gradient-to-br from-[#F97316]/10 to-[#F97316]/5 border border-[#F97316]/20 rounded-2xl p-5">
          <div className="flex items-center gap-2 text-[#F97316] text-sm mb-2">
            <Wallet className="w-4 h-4" /> Текущий баланс
          </div>
          <div className="text-2xl font-bold text-white font-['JetBrains_Mono']">
            {(merchant.balance_usdt || 0).toFixed(2)} <span className="text-sm text-[#71717A]">USDT</span>
          </div>
          <div className="text-sm text-[#71717A] mt-1">
            + {(merchant.frozen_balance || 0).toFixed(2)} заморожено
          </div>
        </div>
      </div>
    </div>
  );
}

// ==================== CHAT HISTORY MODAL ====================
function ChatHistoryModal({ open, onClose, tradeId, token, canOpenDispute, onDisputeOpened, isCryptoOrder = false }) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [trade, setTrade] = useState(null);
  const [openingDispute, setOpeningDispute] = useState(false);
  const [newMessage, setNewMessage] = useState('');
  const [sendingMessage, setSendingMessage] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (open && tradeId) {
      fetchChat();
      // Poll for new messages in disputes
      const interval = setInterval(() => {
        if (trade && ['dispute', 'disputed'].includes(trade.status)) {
          fetchChat(true);
        }
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [open, tradeId, trade?.status]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const fetchChat = async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      // Use different API for crypto orders (payouts)
      const endpoint = isCryptoOrder 
        ? `${API}/merchant/crypto-orders/${tradeId}/chat`
        : `${API}/merchant/trades/${tradeId}/chat`;
      const res = await axios.get(endpoint, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setMessages(res.data.messages || []);
      setTrade(res.data.trade || null);
    } catch (error) {
      console.error(error);
      if (!silent) toast.error("Не удалось загрузить чат");
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const sendMessage = async () => {
    if (!newMessage.trim() || !tradeId) return;
    setSendingMessage(true);
    try {
      await axios.post(`${API}/merchant/disputes/${tradeId}/messages`, 
        { content: newMessage.trim() },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setNewMessage('');
      await fetchChat(true);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка отправки сообщения');
    } finally {
      setSendingMessage(false);
    }
  };

  const handleOpenDispute = async () => {
    if (!window.confirm("Вы уверены что хотите открыть спор по этой сделке?")) return;
    setOpeningDispute(true);
    try {
      await axios.post(`${API}/merchant/disputes/${tradeId}/open`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Спор открыт");
      if (onDisputeOpened) onDisputeOpened();
      onClose();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка открытия спора");
    } finally {
      setOpeningDispute(false);
    }
  };

  const getStatusLabel = (status) => {
    const labels = {
      pending: "Ожидает", active: "Активна", paid: "Оплачено", waiting: "Ожидание",
      completed: "Завершено", cancelled: "Отменено", dispute: "Спор", disputed: "Спор"
    };
    return labels[status] || status;
  };

  const getStatusColor = (status) => {
    if (["completed"].includes(status)) return "text-[#10B981]";
    if (["cancelled"].includes(status)) return "text-[#71717A]";
    if (["dispute", "disputed"].includes(status)) return "text-[#EF4444]";
    return "text-[#F59E0B]";
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="bg-[#121212] border-white/10 text-white max-w-lg max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <MessageCircle className="w-5 h-5 text-[#3B82F6]" />
            История чата
            {trade && (
              <span className={`text-sm font-normal ml-2 ${getStatusColor(trade.status)}`}>
                ({getStatusLabel(trade.status)})
              </span>
            )}
          </DialogTitle>
        </DialogHeader>

        {/* Trade info */}
        {trade && (
          <div className="bg-[#1A1A1A] rounded-xl p-3 flex items-center justify-between">
            <div>
              <div className="text-sm text-white font-medium">
                {trade.buyer_nickname || trade.client_nickname || "Клиент"}
              </div>
              <div className="text-xs text-[#71717A]">
                {(trade.client_amount_rub || trade.amount_rub || 0).toLocaleString("ru-RU", {maximumFractionDigits: 0})} ₽
              </div>
            </div>
            <div className="text-xs text-[#52525B]">
              #{tradeId?.slice(-6)}
            </div>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto space-y-2 min-h-[200px] max-h-[400px] pr-1" style={{scrollbarWidth: "thin", scrollbarColor: "#333 transparent"}}>
          {loading ? (
            <div className="flex justify-center py-10">
              <Loader className="w-6 h-6 animate-spin text-[#71717A]" />
            </div>
          ) : messages.length === 0 ? (
            <div className="text-center py-10">
              <MessageCircle className="w-12 h-12 text-[#52525B] mx-auto mb-3" />
              <p className="text-[#71717A] text-sm">Сообщений нет</p>
            </div>
          ) : (
            messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.sender_role === "merchant" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[80%] rounded-xl px-3 py-2 ${
                  msg.sender_role === "merchant"
                    ? "bg-[#3B82F6]/20 text-white"
                    : msg.sender_role === "admin" || msg.sender_role === "moderator"
                    ? "bg-[#F59E0B]/20 text-white"
                    : "bg-white/10 text-white"
                }`}>
                  <div className="text-xs font-medium mb-1" style={{color:
                    msg.sender_role === "merchant" ? "#3B82F6" :
                    msg.sender_role === "admin" ? "#F59E0B" :
                    msg.sender_role === "moderator" ? "#F59E0B" :
                    msg.sender_role === "trader" ? "#10B981" : "#A1A1AA"
                  }}>
                    {msg.sender_name || msg.sender_role || "Пользователь"}
                  </div>
                  <div className="text-sm whitespace-pre-wrap break-words">{msg.text || msg.content || msg.message}</div>
                  <div className="text-[10px] text-[#52525B] mt-1 text-right">
                    {msg.created_at ? new Date(msg.created_at).toLocaleString("ru-RU") : ""}
                  </div>
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Message Input for Disputes */}
        {trade && ['dispute', 'disputed'].includes(trade.status) && (
          <div className="pt-3 border-t border-white/5">
            <div className="flex gap-2">
              <input
                type="text"
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                placeholder="Написать сообщение в спор..."
                className="flex-1 px-4 py-2.5 bg-[#0A0A0A] border border-white/10 rounded-xl text-white text-sm placeholder-[#52525B] focus:outline-none focus:border-[#3B82F6]/50"
              />
              <button
                onClick={sendMessage}
                disabled={!newMessage.trim() || sendingMessage}
                className="px-4 py-2.5 bg-[#3B82F6] hover:bg-[#2563EB] disabled:opacity-50 text-white rounded-xl transition-colors"
              >
                {sendingMessage ? (
                  <Loader className="w-5 h-5 animate-spin" />
                ) : (
                  <Send className="w-5 h-5" />
                )}
              </button>
            </div>
          </div>
        )}

        {/* Open Dispute button */}
        {canOpenDispute && trade && !["dispute", "disputed", "completed", "cancelled"].includes(trade.status) && (
          <div className="pt-2 border-t border-white/5">
            <Button
              onClick={handleOpenDispute}
              disabled={openingDispute}
              className="w-full bg-[#EF4444] hover:bg-[#DC2626] text-white h-10 rounded-xl"
            >
              {openingDispute ? (
                <Loader className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <AlertTriangle className="w-4 h-4 mr-2" />
              )}
              Открыть спор
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ==================== WITHDRAWAL REQUESTS (Заявки на выплаты) ====================
function MerchantWithdrawalRequests() {
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("active");
  const [showCreate, setShowCreate] = useState(false);
  const [payoutSettings, setPayoutSettings] = useState({ base_rate: 100 });
  const [liveRate, setLiveRate] = useState(null);
  const [form, setForm] = useState({ 
    amount_rub: "", 
    payment_type: "card",
    card_number: "",
    sbp_phone: "",
    bank_name: ""
  });

  const [chatTradeId, setChatTradeId] = useState(null);
  const [showChat, setShowChat] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const commissionRate = user?.withdrawal_commission || 3;
  const merchantRate = payoutSettings.base_rate * (1 - commissionRate / 100);
  const calculatedUsdt = form.amount_rub ? (parseFloat(form.amount_rub) / merchantRate).toFixed(2) : "0.00";

  useEffect(() => {
    fetchRequests();
    fetchPayoutSettings();
  }, [filter]);

  const fetchPayoutSettings = async () => {
    try {
      const res = await axios.get(`${API}/payout-settings/public`);
      setPayoutSettings({
        base_rate: res.data.base_rate || 100
      });
    } catch (e) {
      console.error(e);
    }
  };

  const fetchRequests = async () => {
    try {
      const response = await axios.get(`${API}/crypto/my-offers`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      let data = response.data || [];
      if (filter === "active") {
        data = data.filter(r => r.status === "active" || r.status === "in_progress");
      } else if (filter === "completed") {
        // "sold" status means the offer was successfully completed
        data = data.filter(r => r.status === "completed" || r.status === "sold");
      } else if (filter === "cancelled") {
        data = data.filter(r => r.status === "cancelled");
      }
      setRequests(data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const createRequest = async () => {
    if (!form.amount_rub || parseFloat(form.amount_rub) <= 0) {
      toast.error("Укажите сумму в рублях");
      return;
    }
    if (form.payment_type === "card" && !form.card_number) {
      toast.error("Укажите номер карты");
      return;
    }
    if (form.payment_type === "sbp" && (!form.sbp_phone || !form.bank_name)) {
      toast.error("Укажите номер СБП и банк");
      return;
    }

    try {
      await axios.post(`${API}/crypto/sell-offers`, {
        amount_rub: parseFloat(form.amount_rub),
        payment_type: form.payment_type,
        card_number: form.card_number,
        sbp_phone: form.sbp_phone,
        bank_name: form.bank_name
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Заявка создана");
      setShowCreate(false);
      setForm({ amount_rub: "", payment_type: "card", card_number: "", sbp_phone: "", bank_name: "" });
      fetchRequests();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка создания");
    }
  };

  const cancelRequest = async (id) => {
    try {
      await axios.delete(`${API}/crypto/sell-offers/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Заявка отменена");
      fetchRequests();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка");
    }
  };

  const filteredRequests = requests.filter(r => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.trim().toLowerCase();
    return (r.id && r.id.toLowerCase().includes(q)) ||
           (r.amount_rub && String(r.amount_rub).includes(q)) ||
           (r.card_number && r.card_number.includes(q)) ||
           (r.sbp_phone && r.sbp_phone.includes(q));
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Заявки на выплаты</h1>
        <Button onClick={() => setShowCreate(true)} className="bg-[#10B981] hover:bg-[#059669]">
          <Plus className="w-4 h-4 mr-2" /> Создать заявку
        </Button>
      </div>

      {/* Commission Info Banner */}
      <div className="bg-gradient-to-r from-[#10B981]/10 to-transparent border border-[#10B981]/20 rounded-xl p-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-[#10B981]/20 rounded-xl flex items-center justify-center">
            <Percent className="w-5 h-5 text-[#10B981]" />
          </div>
          <div>
            <p className="text-white font-medium">Ваша комиссия на выплаты: <span className="text-[#10B981]">{commissionRate}%</span></p>
            <p className="text-[#71717A] text-sm">Базовый курс: <span className="text-[#3B82F6] font-bold">{payoutSettings.base_rate} ₽/USDT</span> (биржа) | Ваш курс: <span className="text-[#10B981] font-bold">{merchantRate.toFixed(2)} ₽/USDT</span></p>
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <Input
          placeholder="Поиск по номеру сделки или сумме..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="bg-[#121212] border-white/10 text-white pl-10"
        />
        <Target className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#71717A]" />
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        {[
          { key: "active", label: "Активные" },
          { key: "completed", label: "Завершённые" },
          { key: "cancelled", label: "Отменённые" }
        ].map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-4 py-2 rounded-lg text-sm transition-colors ${
              filter === f.key
                ? "bg-white/10 text-white"
                : "text-[#71717A] hover:bg-white/5"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Create Dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="bg-[#121212] border-white/10 text-white max-w-md">
          <DialogHeader>
            <DialogTitle>Создать заявку на выплату</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="text-[#A1A1AA]">Сумма в рублях</Label>
              <Input
                type="number"
                value={form.amount_rub}
                onChange={(e) => setForm({...form, amount_rub: e.target.value})}
                placeholder="10000"
                className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl"
              />
              {form.amount_rub && (
                <div className="text-sm text-[#71717A]">
                  Будет списано: <span className="text-[#F97316] font-medium">{calculatedUsdt} USDT</span> (курс {merchantRate.toFixed(2)} ₽)
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label className="text-[#A1A1AA]">Способ оплаты</Label>
              <div className="flex gap-2">
                <button
                  onClick={() => setForm({...form, payment_type: "card"})}
                  className={`flex-1 py-2 rounded-lg text-sm ${form.payment_type === "card" ? "bg-[#F97316] text-white" : "bg-white/5 text-[#71717A]"}`}
                >
                  Карта
                </button>
                <button
                  onClick={() => setForm({...form, payment_type: "sbp"})}
                  className={`flex-1 py-2 rounded-lg text-sm ${form.payment_type === "sbp" ? "bg-[#F97316] text-white" : "bg-white/5 text-[#71717A]"}`}
                >
                  СБП
                </button>
              </div>
            </div>

            {form.payment_type === "card" ? (
              <div className="space-y-2">
                <Label className="text-[#A1A1AA]">Номер карты</Label>
                <Input
                  value={form.card_number}
                  onChange={(e) => setForm({...form, card_number: e.target.value})}
                  placeholder="0000 0000 0000 0000"
                  className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl"
                />
              </div>
            ) : (
              <>
                <div className="space-y-2">
                  <Label className="text-[#A1A1AA]">Номер телефона (СБП)</Label>
                  <Input
                    value={form.sbp_phone}
                    onChange={(e) => setForm({...form, sbp_phone: e.target.value})}
                    placeholder="+7 999 999 99 99"
                    className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-[#A1A1AA]">Банк</Label>
                  <Input
                    value={form.bank_name}
                    onChange={(e) => setForm({...form, bank_name: e.target.value})}
                    placeholder="Сбербанк"
                    className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl"
                  />
                </div>
              </>
            )}

            <Button onClick={createRequest} className="w-full bg-[#10B981] hover:bg-[#059669] h-12 rounded-xl">
              Создать заявку
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Requests List */}
      {loading ? (
        <div className="flex justify-center py-20"><Loader className="w-8 h-8 animate-spin text-[#71717A]" /></div>
      ) : filteredRequests.length === 0 ? (
        <div className="text-center py-20">
          <ArrowUpRight className="w-16 h-16 text-[#52525B] mx-auto mb-4" />
          <h3 className="text-lg font-medium text-white mb-2">Нет заявок</h3>
          <p className="text-[#71717A]">Создайте первую заявку на выплату</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredRequests.map(req => (
            <div key={req.id} className="bg-[#121212] border rounded-xl p-4 border-white/5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                    req.status === "dispute" ? "bg-[#EF4444]/20" :
                    req.status === "active" ? "bg-[#10B981]/10" : "bg-[#71717A]/10"
                  }`}>
                    {req.status === "dispute" ? (
                      <AlertTriangle className="w-6 h-6 text-[#EF4444]" />
                    ) : (
                      <ArrowUpRight className="w-6 h-6 text-[#10B981]" />
                    )}
                  </div>
                  <div>
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-xs text-[#71717A] font-['JetBrains_Mono']">#{req.id?.slice(0, 12)}</span>
                      <button onClick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(req.id); toast.success("Номер сделки скопирован"); }} className="p-0.5 rounded hover:bg-white/10 transition-colors" title="Скопировать номер сделки">
                        <Copy className="w-3 h-3 text-[#71717A] hover:text-white" />
                      </button>
                    </div>
                    <div className="text-white font-medium">
                      {(req.amount_rub || 0).toLocaleString("ru-RU")} ₽
                    </div>
                    <div className="text-sm text-[#71717A]">
                      {(req.usdt_from_merchant || 0).toFixed(2)} USDT | {req.payment_type === "card" ? "Карта" : "СБП"}
                    </div>
                    <div className="text-xs text-[#52525B]">
                      {req.created_at ? new Date(req.created_at).toLocaleString("ru-RU") : "—"}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-1 rounded-lg ${
                    req.status === "active" ? "bg-[#10B981]/10 text-[#10B981]" :
                    req.status === "dispute" ? "bg-[#EF4444]/10 text-[#EF4444]" :
                    req.status === "in_progress" ? "bg-[#F59E0B]/10 text-[#F59E0B]" :
                    "bg-[#71717A]/10 text-[#71717A]"
                  }`}>
                    {req.status === "active" ? "Активна" :
                     req.status === "dispute" ? "Спор" :
                     req.status === "in_progress" ? "В процессе" :
                     req.status === "completed" ? "Завершена" :
                     req.status === "cancelled" ? "Отменена" : req.status}
                  </span>
                  <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); setChatTradeId(req.id); setShowChat(true); }} className="border-[#3B82F6]/30 text-[#3B82F6] hover:bg-[#3B82F6]/10 text-xs">
                    <MessageCircle className="w-3 h-3 mr-1" /> Чат
                  </Button>
                  {req.status === "active" && (
                    <Button size="sm" variant="outline" onClick={() => cancelRequest(req.id)} className="border-[#EF4444]/30 text-[#EF4444] hover:bg-[#EF4444]/10 text-xs">
                      Отменить
                    </Button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Chat History Modal for Withdrawal Requests */}
      <ChatHistoryModal
        open={showChat}
        onClose={() => setShowChat(false)}
        tradeId={chatTradeId}
        token={token}
        canOpenDispute={false}
        isCryptoOrder={true}
      />
    </div>
  );
}

// ==================== PAYMENTS(Платежи) ====================
function MerchantPayments() {
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("active");
  const [chatTradeId, setChatTradeId] = useState(null);
  const [showChat, setShowChat] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    fetchPayments();
  }, [filter]);

  const fetchPayments = async () => {
    try {
      const response = await axios.get(`${API}/merchant/trades`, {
        params: { type: "sell", status: filter },
        headers: { Authorization: `Bearer ${token}` }
      });
      setPayments(response.data || []);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const disputeCount = payments.filter(p => p.status === "dispute" || p.status === "disputed").length;

  const filteredPayments = payments.filter(p => {
    // First filter by status tab
    if (filter === "active") {
      if (!["pending", "active", "paid", "waiting", "processing"].includes(p.status)) return false;
    } else if (filter === "completed") {
      if (p.status !== "completed") return false;
    } else if (filter === "cancelled") {
      if (!["cancelled", "rejected", "expired"].includes(p.status)) return false;
    } else if (filter === "dispute") {
      if (p.status !== "dispute" && p.status !== "disputed") return false;
    }
    
    // Then filter by search query
    if (!searchQuery.trim()) return true;
    const q = searchQuery.trim().toLowerCase();
    return (p.id && p.id.toLowerCase().includes(q)) ||
           (p.client_nickname && p.client_nickname.toLowerCase().includes(q)) ||
           (p.amount && String(p.amount).includes(q)) ||
           (p.fiat_amount && String(p.fiat_amount).includes(q));
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Платежи (Пополнения)</h1>
      </div>

      {/* Commission Info Banner */}
      <div className="bg-gradient-to-r from-[#3B82F6]/10 to-transparent border border-[#3B82F6]/20 rounded-xl p-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-[#3B82F6]/20 rounded-xl flex items-center justify-center">
            <Percent className="w-5 h-5 text-[#3B82F6]" />
          </div>
          <div>
            <p className="text-white font-medium">Комиссия на платежи: <span className="text-[#3B82F6]">{user?.commission_rate || 0}%</span></p>
            <p className="text-[#71717A] text-sm">Списывается с каждого успешного пополнения от клиента</p>
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <Input
          placeholder="Поиск по номеру сделки, клиенту или сумме..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="bg-[#121212] border-white/10 text-white pl-10"
        />
        <Target className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#71717A]" />
      </div>

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        {[
          { key: "active", label: "Активные" },
          { key: "completed", label: "Завершённые" },
          { key: "cancelled", label: "Отменённые" },
          { key: "dispute", label: `Споры${disputeCount > 0 ? ` (${disputeCount})` : ""}`, danger: true }
        ].map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-4 py-2 rounded-lg text-sm transition-colors ${
              filter === f.key
                ? f.danger ? "bg-[#EF4444]/20 text-[#EF4444]" : "bg-white/10 text-white"
                : f.danger && disputeCount > 0 ? "text-[#EF4444] hover:bg-[#EF4444]/10" : "text-[#71717A] hover:bg-white/5"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-20"><Loader className="w-8 h-8 animate-spin text-[#71717A]" /></div>
      ) : filteredPayments.length === 0 ? (
        <div className="text-center py-20">
          <DollarSign className="w-16 h-16 text-[#52525B] mx-auto mb-4" />
          <h3 className="text-lg font-medium text-white mb-2">Нет платежей</h3>
          <p className="text-[#71717A]">{filter === "dispute" ? "Нет открытых споров" : "Платежи появятся здесь"}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredPayments.map(payment => (
            <div 
              key={payment.id}
              onClick={() => { setChatTradeId(payment.id); setShowChat(true); }}
              className={`bg-[#121212] border rounded-xl p-4 cursor-pointer transition-all ${
                (payment.status === "dispute" || payment.status === "disputed") 
                  ? "border-[#EF4444]/30 bg-[#EF4444]/5 hover:bg-[#EF4444]/10" 
                  : "border-white/5 hover:bg-white/5"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                    (payment.status === "dispute" || payment.status === "disputed") ? "bg-[#EF4444]/20" : "bg-[#3B82F6]/10"
                  }`}>
                    {(payment.status === "dispute" || payment.status === "disputed") ? (
                      <AlertTriangle className="w-6 h-6 text-[#EF4444]" />
                    ) : (
                      <DollarSign className="w-6 h-6 text-[#3B82F6]" />
                    )}
                  </div>
                  <div>
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-xs text-[#71717A] font-['JetBrains_Mono']">#{payment.id}</span>
                      <button onClick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(payment.id); toast.success("Номер сделки скопирован"); }} className="p-0.5 rounded hover:bg-white/10 transition-colors" title="Скопировать номер сделки">
                        <Copy className="w-3 h-3 text-[#71717A] hover:text-white" />
                      </button>
                    </div>
                    <div className={`font-medium ${(payment.status === "dispute" || payment.status === "disputed") ? "text-[#EF4444]" : "text-white"}`}>
                      {payment.client_nickname || "Клиент"}
                    </div>
                    <div className="text-sm text-[#71717A]">
                      {(payment.original_amount_rub || payment.fiat_amount || payment.amount_rub || 0).toLocaleString("ru-RU", {maximumFractionDigits: 0})} ₽
                    </div>
                    <div className="text-xs text-[#52525B]">
                      {new Date(payment.created_at).toLocaleString("ru-RU")}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); setChatTradeId(payment.id); setShowChat(true); }} className="border-[#3B82F6]/30 text-[#3B82F6] hover:bg-[#3B82F6]/10 text-xs">
                    <MessageCircle className="w-3 h-3 mr-1" /> Чат
                  </Button>
                  {(payment.status === "dispute" || payment.status === "disputed") && (
                    <span className="px-2 py-1 bg-[#EF4444]/10 text-[#EF4444] rounded-lg text-xs flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" /> Спор
                    </span>
                  )}
                  {["pending", "active", "paid", "waiting"].includes(payment.status) && (
                    <span className={`px-2 py-1 rounded-lg text-xs ${
                      payment.status === "paid" ? "bg-[#3B82F6]/10 text-[#3B82F6]" :
                      payment.status === "waiting" ? "bg-[#F59E0B]/10 text-[#F59E0B]" :
                      "bg-[#10B981]/10 text-[#10B981]"
                    }`}>
                      {payment.status === "paid" ? "Оплачено" :
                       payment.status === "waiting" ? "Ожидание" :
                       payment.status === "pending" ? "Ожидает" : "Активна"}
                    </span>
                  )}
                  {payment.status === "completed" && (
                    <span className="px-2 py-1 bg-[#10B981]/10 text-[#10B981] rounded-lg text-xs">Завершено</span>
                  )}
                  {payment.status === "cancelled" && (
                    <span className="px-2 py-1 bg-[#71717A]/10 text-[#71717A] rounded-lg text-xs">Отменено</span>
                  )}
                  <ChevronRight className={`w-5 h-5 ${(payment.status === "dispute" || payment.status === "disputed") ? "text-[#EF4444]" : "text-[#71717A]"}`} />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Chat History Modal */}
      <ChatHistoryModal
        open={showChat}
        onClose={() => setShowChat(false)}
        tradeId={chatTradeId}
        token={token}
        canOpenDispute={true}
        onDisputeOpened={() => { setFilter("dispute"); fetchPayments(); }}
      />
    </div>
  );
}

// ==================== HISTORY ====================
function MerchantHistory() {
  const { token } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("completed");

  useEffect(() => {
    fetchHistory();
  }, [filter]);

  const fetchHistory = async () => {
    try {
      const response = await axios.get(`${API}/merchant/trades`, {
        params: { type: "sell", status: filter },
        headers: { Authorization: `Bearer ${token}` }
      });
      setItems(response.data || []);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">История</h1>

      <div className="flex gap-2">
        {[
          { key: "completed", label: "Завершённые" },
          { key: "cancelled", label: "Отменённые" }
        ].map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-4 py-2 rounded-lg text-sm transition-colors ${
              filter === f.key ? "bg-white/10 text-white" : "text-[#71717A] hover:bg-white/5"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-20"><Loader className="w-8 h-8 animate-spin text-[#71717A]" /></div>
      ) : items.length === 0 ? (
        <div className="text-center py-20">
          <History className="w-16 h-16 text-[#52525B] mx-auto mb-4" />
          <h3 className="text-lg font-medium text-white mb-2">История пуста</h3>
          <p className="text-[#71717A]">{filter === "completed" ? "Нет завершённых сделок" : "Нет отменённых сделок"}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map(item => (
            <div key={item.id} className="bg-[#121212] border border-white/5 rounded-xl p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                    filter === "completed" ? "bg-[#10B981]/10" : "bg-[#71717A]/10"
                  }`}>
                    {filter === "completed" ? (
                      <CheckCircle className="w-6 h-6 text-[#10B981]" />
                    ) : (
                      <XCircle className="w-6 h-6 text-[#71717A]" />
                    )}
                  </div>
                  <div>
                    <div className="text-white font-medium">{item.client_nickname || "Клиент"}</div>
                    <div className="text-sm text-[#71717A]">
                      {item.amount} {item.currency || "USDT"} • {item.fiat_amount?.toFixed(2) || "—"} ₽
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className={`text-sm ${filter === "completed" ? "text-[#10B981]" : "text-[#71717A]"}`}>
                    {filter === "completed" ? "Завершено" : "Отменено"}
                  </div>
                  <div className="text-xs text-[#52525B]">
                    {new Date(item.created_at).toLocaleDateString("ru-RU")}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ==================== DEALS ARCHIVE ====================
function MerchantDealsArchive() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [deals, setDeals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [chatTradeId, setChatTradeId] = useState(null);
  const [showChat, setShowChat] = useState(false);

  useEffect(() => {
    fetchDeals();
  }, []);

  const fetchDeals = async () => {
    try {
      const res = await axios.get(`${API}/merchant/trades`, {
        params: { type: "sell" },
        headers: { Authorization: `Bearer ${token}` }
      });
      setDeals(res.data || []);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const filteredDeals = filter === "all" ? deals : deals.filter(d => {
    if (filter === "active") return ["pending", "paid"].includes(d.status);
    return d.status === filter;
  });

  const getStatusBadge = (status) => {
    const styles = {
      pending: "bg-[#F59E0B]/10 text-[#F59E0B]",
      paid: "bg-[#3B82F6]/10 text-[#3B82F6]",
      completed: "bg-[#10B981]/10 text-[#10B981]",
      cancelled: "bg-[#71717A]/10 text-[#71717A]",
      dispute: "bg-[#EF4444]/10 text-[#EF4444]",
      disputed: "bg-[#EF4444]/10 text-[#EF4444]"
    };
    const labels = {
      pending: "Ожидает",
      paid: "Оплачено",
      completed: "Завершено",
      cancelled: "Отменено",
      dispute: "Спор",
      disputed: "Спор"
    };
    return <span className={`px-2 py-1 rounded-lg text-xs ${styles[status] || styles.pending}`}>{labels[status] || status}</span>;
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Архив сделок</h1>

      <div className="flex gap-2 flex-wrap">
        {[
          { key: "all", label: "Все" },
          { key: "active", label: "Активные" },
          { key: "completed", label: "Завершённые" },
          { key: "cancelled", label: "Отменённые" },
          { key: "dispute", label: "Споры" }
        ].map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-4 py-2 rounded-lg text-sm transition-colors ${
              filter === f.key ? "bg-white/10 text-white" : "text-[#71717A] hover:bg-white/5"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-20"><Loader className="w-8 h-8 animate-spin text-[#71717A]" /></div>
      ) : filteredDeals.length === 0 ? (
        <div className="text-center py-20">
          <FileText className="w-16 h-16 text-[#52525B] mx-auto mb-4" />
          <h3 className="text-lg font-medium text-white mb-2">Нет сделок</h3>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredDeals.map(deal => (
            <div 
              key={deal.id} 
              onClick={() => navigate(`/merchant/deals-archive/${deal.id}`)}
              className="bg-[#121212] border border-white/5 rounded-xl p-4 cursor-pointer hover:bg-white/5 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 bg-[#3B82F6]/10 rounded-xl flex items-center justify-center">
                    <FileText className="w-6 h-6 text-[#3B82F6]" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-xs text-[#71717A] font-['JetBrains_Mono']">#{deal.id?.slice(0, 12)}</span>
                      <button onClick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(deal.id); toast.success("Номер сделки скопирован"); }} className="p-0.5 rounded hover:bg-white/10 transition-colors" title="Скопировать номер сделки">
                        <Copy className="w-3 h-3 text-[#71717A] hover:text-white" />
                      </button>
                    </div>
                    <div className="text-white font-medium">{deal.client_nickname || "Клиент"}</div>
                    <div className="text-sm text-[#71717A]">
                      {deal.amount} {deal.currency || "USDT"} • {deal.fiat_amount?.toFixed(2) || "—"} ₽
                    </div>
                    <div className="text-xs text-[#52525B]">
                      {new Date(deal.created_at).toLocaleString("ru-RU")}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); setChatTradeId(deal.id); setShowChat(true); }} className="border-[#3B82F6]/30 text-[#3B82F6] hover:bg-[#3B82F6]/10 text-xs">
                    <MessageCircle className="w-3 h-3 mr-1" /> Чат
                  </Button>
                  {getStatusBadge(deal.status)}
                  <ChevronRight className="w-5 h-5 text-[#71717A]" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Chat History Modal */}
      <ChatHistoryModal
        open={showChat}
        onClose={() => setShowChat(false)}
        tradeId={chatTradeId}
        token={token}
        canOpenDispute={false}
      />
    </div>
  );
}

// ==================== DEAL DETAILS ====================
function MerchantDealDetails() {
  const { token } = useAuth();
  const { orderId } = useParams();
  const navigate = useNavigate();
  const [deal, setDeal] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showChat, setShowChat] = useState(false);

  useEffect(() => {
    fetchDeal();
  }, [orderId]);

  const fetchDeal = async () => {
    try {
      const res = await axios.get(`${API}/merchant/trades/${orderId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setDeal(res.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="flex justify-center py-20"><Loader className="w-8 h-8 animate-spin text-[#71717A]" /></div>;
  }

  if (!deal) {
    return (
      <div className="text-center py-20">
        <XCircle className="w-16 h-16 text-[#52525B] mx-auto mb-4" />
        <h3 className="text-lg font-medium text-white mb-2">Сделка не найдена</h3>
        <Button onClick={() => navigate("/merchant/deals-archive")} variant="outline" className="border-white/10 text-white">
          <ChevronLeft className="w-4 h-4 mr-2" /> Назад
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center gap-3">
        <Button onClick={() => navigate("/merchant/deals-archive")} variant="outline" size="sm" className="border-white/10 text-white">
          <ChevronLeft className="w-4 h-4" />
        </Button>
        <h1 className="text-2xl font-bold text-white">Сделка #{deal.id?.slice(-6)}</h1>
      </div>

      <div className="bg-[#121212] border border-white/5 rounded-2xl p-6 space-y-4">
        <div className="flex justify-between py-3 border-b border-white/5">
          <span className="text-[#71717A]">Статус</span>
          <span className={`font-medium ${
            deal.status === "completed" ? "text-[#10B981]" :
            deal.status === "cancelled" ? "text-[#71717A]" :
            deal.status === "dispute" ? "text-[#EF4444]" :
            "text-[#F59E0B]"
          }`}>
            {deal.status === "completed" ? "Завершено" :
             deal.status === "cancelled" ? "Отменено" :
             deal.status === "dispute" ? "Спор" :
             deal.status === "paid" ? "Оплачено" :
             deal.status === "pending" ? "Ожидает" : deal.status}
          </span>
        </div>
        <div className="flex justify-between py-3 border-b border-white/5">
          <span className="text-[#71717A]">Клиент</span>
          <span className="text-white">{deal.client_nickname || "—"}</span>
        </div>
        <div className="flex justify-between py-3 border-b border-white/5">
          <span className="text-[#71717A]">Сумма USDT</span>
          <span className="text-white font-['JetBrains_Mono']">{deal.amount} {deal.currency || "USDT"}</span>
        </div>
        <div className="flex justify-between py-3 border-b border-white/5">
          <span className="text-[#71717A]">Сумма RUB</span>
          <span className="text-white font-['JetBrains_Mono']">{deal.fiat_amount?.toFixed(2) || "—"} ₽</span>
        </div>
        {deal.merchant_commission > 0 && (
          <div className="flex justify-between py-3 border-b border-white/5">
            <span className="text-[#71717A]">Комиссия</span>
            <span className="text-[#EF4444] font-['JetBrains_Mono']">-{deal.merchant_commission?.toFixed(4)} USDT</span>
          </div>
        )}
        <div className="flex justify-between py-3 border-b border-white/5">
          <span className="text-[#71717A]">Трейдер</span>
          <span className="text-white">{deal.trader_login || "—"}</span>
        </div>
        <div className="flex justify-between py-3 border-b border-white/5">
          <span className="text-[#71717A]">Дата создания</span>
          <span className="text-white">{deal.created_at ? new Date(deal.created_at).toLocaleString("ru-RU") : "—"}</span>
        </div>
        {deal.completed_at && (
          <div className="flex justify-between py-3">
            <span className="text-[#71717A]">Дата завершения</span>
            <span className="text-white">{new Date(deal.completed_at).toLocaleString("ru-RU")}</span>
          </div>
        )}
      </div>

      {/* Chat History Button */}
      <Button
        onClick={() => setShowChat(true)}
        className="w-full bg-[#3B82F6] hover:bg-[#2563EB] text-white h-12 rounded-xl"
      >
        <MessageCircle className="w-5 h-5 mr-2" /> Показать историю чата
      </Button>

      {/* Chat History Modal */}
      <ChatHistoryModal
        open={showChat}
        onClose={() => setShowChat(false)}
        tradeId={orderId}
        token={token}
        canOpenDispute={deal.status && !["completed", "cancelled", "dispute", "disputed"].includes(deal.status)}
        onDisputeOpened={() => fetchDeal()}
      />
    </div>
  );
}

// ==================== TRANSACTIONS ====================
function MerchantTransactions() {
  const { token } = useAuth();
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTransactions();
  }, []);

  const fetchTransactions = async () => {
    try {
      const response = await axios.get(`${API}/merchants/transactions`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTransactions(response.data || []);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Транзакции</h1>

      {loading ? (
        <div className="flex justify-center py-20"><Loader className="w-8 h-8 animate-spin text-[#71717A]" /></div>
      ) : transactions.length === 0 ? (
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-6 text-center py-20">
          <History className="w-16 h-16 text-[#52525B] mx-auto mb-4" />
          <p className="text-[#71717A]">История транзакций пуста</p>
        </div>
      ) : (
        <div className="space-y-3">
          {transactions.map(tx => (
            <div key={tx.id} className="bg-[#121212] border border-white/5 rounded-xl p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                    tx.amount >= 0 ? "bg-[#10B981]/10" : "bg-[#EF4444]/10"
                  }`}>
                    {tx.amount >= 0 ? (
                      <ArrowDownRight className="w-5 h-5 text-[#10B981]" />
                    ) : (
                      <ArrowUpRight className="w-5 h-5 text-[#EF4444]" />
                    )}
                  </div>
                  <div>
                    <div className="text-white text-sm font-medium">{tx.description}</div>
                    <div className="text-xs text-[#52525B]">
                      {new Date(tx.created_at).toLocaleString("ru-RU")}
                    </div>
                  </div>
                </div>
                <div className={`font-medium font-['JetBrains_Mono'] ${
                  tx.amount >= 0 ? "text-[#10B981]" : "text-[#EF4444]"
                }`}>
                  {tx.amount >= 0 ? "+" : ""}{tx.amount?.toFixed(2)} USDT
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ==================== WITHDRAW ====================
function MerchantWithdraw() {
  const { token, user } = useAuth();
  const [withdrawals, setWithdrawals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [amount, setAmount] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchWithdrawals();
  }, []);

  const fetchWithdrawals = async () => {
    try {
      const response = await axios.get(`${API}/merchants/withdrawals`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setWithdrawals(response.data || []);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleWithdraw = async () => {
    const amt = parseFloat(amount);
    if (isNaN(amt) || amt <= 0) {
      toast.error("Укажите корректную сумму");
      return;
    }
    if (amt > (user?.balance_usdt || 0)) {
      toast.error("Недостаточно средств");
      return;
    }
    setSubmitting(true);
    try {
      await axios.post(`${API}/merchants/withdrawals`, { amount: amt, address: "to_balance" }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(`${amt} USDT переведено на баланс аккаунта`);
      setAmount("");
      fetchWithdrawals();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка вывода");
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusBadge = (status) => {
    const styles = { pending: "bg-[#F59E0B]/10 text-[#F59E0B]", completed: "bg-[#10B981]/10 text-[#10B981]", rejected: "bg-[#EF4444]/10 text-[#EF4444]", approved: "bg-[#10B981]/10 text-[#10B981]" };
    const labels = { pending: "Ожидает", completed: "Выполнено", rejected: "Отклонено", approved: "Выполнено" };
    return <span className={`px-2 py-1 rounded-lg text-xs ${styles[status] || styles.pending}`}>{labels[status] || status}</span>;
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Вывод средств</h1>

      <div className="bg-gradient-to-br from-[#F97316] to-[#EA580C] rounded-2xl p-5">
        <div className="text-white/70 text-sm mb-1">Доступно для вывода</div>
        <div className="text-3xl font-bold text-white font-['JetBrains_Mono']">
          {(user?.balance_usdt || 0).toFixed(2)} <span className="text-lg">USDT</span>
        </div>
      </div>

      <div className="bg-[#121212] border border-white/5 rounded-2xl p-6 space-y-4">
        <h3 className="text-lg font-medium text-white">Вывод на баланс аккаунта</h3>
        <p className="text-[#71717A] text-sm">Средства будут переведены на ваш основной баланс аккаунта</p>
        <div className="space-y-2">
          <Label className="text-[#A1A1AA]">Сумма USDT</Label>
          <Input
            type="number"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0.00"
            className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl"
          />
        </div>
        <Button onClick={handleWithdraw} disabled={submitting} className="w-full bg-[#F97316] hover:bg-[#EA580C] h-12 rounded-xl">
          {submitting ? <Loader className="w-4 h-4 animate-spin" /> : "Вывести на баланс"}
        </Button>
      </div>

      {/* Withdrawal History */}
      {withdrawals.length > 0 && (
        <div className="bg-[#121212] border border-white/5 rounded-2xl overflow-hidden">
          <div className="p-4 border-b border-white/5">
            <h3 className="text-white font-medium">История выводов</h3>
          </div>
          <div className="divide-y divide-white/5">
            {withdrawals.map(w => (
              <div key={w.id} className="p-4 flex items-center justify-between">
                <div>
                  <div className="text-white font-medium font-['JetBrains_Mono']">{w.amount?.toFixed(2)} USDT</div>
                  <div className="text-xs text-[#52525B] mt-1">На баланс аккаунта</div>
                  <div className="text-xs text-[#52525B]">{new Date(w.created_at).toLocaleString("ru-RU")}</div>
                </div>
                {getStatusBadge(w.status)}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ==================== ACCOUNT ====================
function MerchantAccount() {
  const { user } = useAuth();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Профиль</h1>

      <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-20 h-20 bg-[#F97316]/10 rounded-2xl flex items-center justify-center">
            <User className="w-10 h-10 text-[#F97316]" />
          </div>
          <div>
            <div className="text-xl font-bold text-white">{user?.nickname || user?.merchant_name || user?.login}</div>
            <div className="text-[#F97316]">Мерчант</div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex justify-between py-3 border-b border-white/5">
            <span className="text-[#71717A]">Логин</span>
            <span className="text-white">{user?.login}</span>
          </div>
          <div className="flex justify-between py-3 border-b border-white/5">
            <span className="text-[#71717A]">Комиссия на платежи</span>
            <span className="text-[#3B82F6] font-medium font-['JetBrains_Mono']">{user?.commission_rate || 0}%</span>
          </div>
          <div className="flex justify-between py-3 border-b border-white/5">
            <span className="text-[#71717A]">Комиссия на выплаты</span>
            <span className="text-[#10B981] font-medium font-['JetBrains_Mono']">{user?.withdrawal_commission || 3}%</span>
          </div>
          <div className="flex justify-between py-3">
            <span className="text-[#71717A]">Статус</span>
            <span className="text-[#10B981]">Активен</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ==================== SETTINGS ====================
function MerchantSettings() {
  const { token, user } = useAuth();
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [showOld, setShowOld] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [saving, setSaving] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

  const handleChangePassword = async () => {
    if (!oldPassword || !newPassword) {
      toast.error("Заполните все поля");
      return;
    }
    if (newPassword.length < 6) {
      toast.error("Минимум 6 символов");
      return;
    }
    setSaving(true);
    try {
      await axios.post(`${API}/merchants/change-password`, {
        old_password: oldPassword,
        new_password: newPassword
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Пароль изменён");
      setOldPassword("");
      setNewPassword("");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка смены пароля");
    } finally {
      setSaving(false);
    }
  };

  const handleRegenerateApiKey = async () => {
    setRegenerating(true);
    try {
      const res = await axios.post(`${API}/merchants/regenerate-api-key`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("API ключ обновлён");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка");
    } finally {
      setRegenerating(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Настройки</h1>

      <div className="bg-[#121212] border border-white/5 rounded-2xl p-6 space-y-4">
        <h3 className="text-lg font-medium text-white flex items-center gap-2"><Lock className="w-5 h-5" /> Смена пароля</h3>
        <div className="space-y-2">
          <Label className="text-[#A1A1AA]">Текущий пароль</Label>
          <div className="relative">
            <Input
              type={showOld ? "text" : "password"}
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl pr-10"
            />
            <button onClick={() => setShowOld(!showOld)} className="absolute right-3 top-3 text-[#71717A]">
              {showOld ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
            </button>
          </div>
        </div>
        <div className="space-y-2">
          <Label className="text-[#A1A1AA]">Новый пароль</Label>
          <div className="relative">
            <Input
              type={showNew ? "text" : "password"}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl pr-10"
            />
            <button onClick={() => setShowNew(!showNew)} className="absolute right-3 top-3 text-[#71717A]">
              {showNew ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
            </button>
          </div>
        </div>
        <Button onClick={handleChangePassword} disabled={saving} className="bg-[#7C3AED] hover:bg-[#6D28D9] h-12 rounded-xl">
          {saving ? <Loader className="w-4 h-4 animate-spin" /> : "Сменить пароль"}
        </Button>
      </div>
    </div>
  );
}

// ==================== PURCHASES ====================
function MerchantPurchases() {
  const { token } = useAuth();
  const navigate = useNavigate();
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

  const handleExpand = async (purchase) => {
    const newId = expandedId === purchase.id ? null : purchase.id;
    setExpandedId(newId);
    // Mark as viewed when expanding
    if (newId && !purchase.viewed) {
      try {
        await axios.post(`${API}/marketplace/purchases/${purchase.id}/mark-viewed`, {}, {
          headers: { Authorization: `Bearer ${token}` }
        });
        // Update local state
        setPurchases(prev => prev.map(p => p.id === purchase.id ? { ...p, viewed: true } : p));
      } catch (e) { console.error(e); }
    }
  };

  const getStatusBadge = (status) => {
    const styles = {
      completed: "bg-[#10B981]/10 text-[#10B981]",
      pending_confirmation: "bg-[#F59E0B]/10 text-[#F59E0B]",
      disputed: "bg-[#EF4444]/10 text-[#EF4444]",
      cancelled: "bg-[#71717A]/10 text-[#71717A]",
      refunded: "bg-[#3B82F6]/10 text-[#3B82F6]"
    };
    const labels = {
      completed: "Завершено",
      pending_confirmation: "Ожидает подтверждения",
      disputed: "Спор",
      cancelled: "Отменено",
      refunded: "Возврат",
      delivered: "Доставлено"
    };
    return (
      <span className={`text-xs px-2 py-1 rounded-lg ${styles[status] || "bg-[#71717A]/10 text-[#71717A]"}`}>
        {labels[status] || status}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Мои покупки</h1>
        <p className="text-[#71717A]">История заказов с маркетплейса</p>
      </div>

      {loading ? (
        <div className="flex justify-center py-20"><Loader className="w-8 h-8 animate-spin text-[#71717A]" /></div>
      ) : purchases.length === 0 ? (
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-6 text-center py-20">
          <ShoppingBag className="w-16 h-16 text-[#52525B] mx-auto mb-4" />
          <p className="text-[#71717A]">У вас пока нет покупок на маркетплейсе</p>
          <a href="/marketplace">
            <button className="mt-4 px-6 py-2 bg-[#7C3AED] hover:bg-[#6D28D9] text-white rounded-full text-sm">
              Перейти в каталог
            </button>
          </a>
        </div>
      ) : (
        <div className="space-y-3">
          {purchases.map(p => (
            <div key={p.id} 
              className={`bg-[#121212] border rounded-xl p-4 cursor-pointer transition-colors ${
                p.status === "pending_confirmation" ? "border-[#F59E0B]/30" : 
                !p.viewed ? "border-[#7C3AED]/30" : "border-white/5"
              }`}
              onClick={() => handleExpand(p)}
            >
              <div className="flex items-center justify-between text-xs text-[#52525B] mb-2">
                <div className="flex items-center gap-2">
                  <span>Заказ #{p.id?.slice(0, 8).toUpperCase()}</span>
                  {!p.viewed && (
                    <span className="px-1.5 py-0.5 text-[10px] rounded-full bg-[#7C3AED] text-white font-bold">
                      Новый
                    </span>
                  )}
                  {p.unread_messages > 0 && (
                    <span className="px-1.5 py-0.5 text-[10px] rounded-full bg-[#EF4444] text-white font-bold animate-pulse">
                      {p.unread_messages} новых
                    </span>
                  )}
                </div>
                <span>{new Date(p.created_at).toLocaleString("ru-RU")}</span>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-white font-medium">{p.product_name || "Товар"}</div>
                  <div className="text-sm text-[#71717A]">{p.quantity || 1} шт. | @{p.seller_nickname || "Продавец"}</div>
                </div>
                <div className="text-right">
                  <div className="text-white font-medium font-['JetBrains_Mono']">{p.total_price?.toFixed(2)} USDT</div>
                  {getStatusBadge(p.status)}
                </div>
              </div>
              
              {expandedId === p.id && (
                <div className="mt-3 pt-3 border-t border-white/5 space-y-2">
                  {p.delivered_content && p.delivered_content.length > 0 && (
                    <div>
                      <div className="text-xs text-[#71717A] mb-1">Содержимое:</div>
                      <div className="bg-black/30 rounded-lg p-3 text-sm text-white font-mono break-all whitespace-pre-wrap max-h-40 overflow-y-auto">
                        {Array.isArray(p.delivered_content) ? p.delivered_content.map((item, i) => (
                          <div key={i}>{typeof item === 'object' ? (item.text || JSON.stringify(item)) : item}</div>
                        )) : p.delivered_content}
                      </div>
                    </div>
                  )}
                  {p.purchase_type === "guarantor" && (
                    <button 
                      onClick={(e) => { e.stopPropagation(); navigate(`/merchant/guarantor-purchase/${p.id}`); }}
                      className="w-full py-2 bg-[#7C3AED]/20 text-[#A78BFA] rounded-lg text-sm hover:bg-[#7C3AED]/30 transition-colors"
                    >
                      Открыть чат с гарантом
                    </button>
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

// ==================== GUARANTOR DEALS ====================
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
      </div>

      {deals.length === 0 ? (
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-12 text-center">
          <Shield className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
          <p className="text-[#71717A]">У вас пока нет гарант-сделок</p>
          <p className="text-sm text-[#52525B] mt-1">Создайте новую сделку или присоединитесь по ссылке</p>
        </div>
      ) : (
        <div className="space-y-3">
          {deals.map((deal) => (
            <Link key={deal.id} to={`/merchant/guarantor-chat/${deal.id}`}>
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
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

// ==================== SHOP ====================
const SHOP_CATEGORIES = {
  accounts: "Аккаунты",
  software: "Софт",
  databases: "Базы данных",
  tools: "Инструменты",
  guides: "Гайды и схемы",
  keys: "Ключи",
  financial: "Финансовое",
  templates: "Шаблоны",
  games: "Игры",
  subscriptions: "Подписки",
  services: "Услуги",
  other: "Другое"
};

function MerchantShop() {
  const { token, user } = useAuth();
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStatus();
  }, []);

  const fetchStatus = async () => {
    try {
      const response = await axios.get(`${API}/shop/my-application`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setStatus(response.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="flex justify-center py-20"><Loader className="w-8 h-8 animate-spin text-[#71717A]" /></div>;
  }

  if (status?.has_shop) {
    return <MerchantShopManagement />;
  }

  return <MerchantShopApplication onSuccess={fetchStatus} />;
}

function MerchantShopApplication({ onSuccess }) {
  const { token, user } = useAuth();
  const [application, setApplication] = useState(null);
  const [conversation, setConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    shop_name: "",
    shop_description: "",
    categories: [],
    telegram: "",
    experience: ""
  });
  const messagesEndRef = useRef(null);

  useEffect(() => {
    checkExistingApplication();
    const interval = setInterval(fetchMessages, 5000);
    return () => clearInterval(interval);
  }, [token]);

  const checkExistingApplication = async () => {
    try {
      const response = await axios.get(`${API}/shop/my-application`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (response.data?.application) {
        setApplication(response.data.application);
        await fetchConversation(response.data.application.id);
      }
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const fetchConversation = async (applicationId) => {
    try {
      const response = await axios.get(`${API}/msg/user/conversations`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const conv = response.data.find(c => c.type === "shop_application" && c.related_id === applicationId);
      if (conv) {
        setConversation(conv);
        await fetchMessages(conv.id);
      }
    } catch (error) {
      console.error(error);
    }
  };

  const fetchMessages = async (convId) => {
    const id = convId || conversation?.id;
    if (!id) return;
    try {
      const response = await axios.get(`${API}/msg/user/conversations/${id}/messages`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setMessages(response.data || []);
      const appRes = await axios.get(`${API}/shop/my-application`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (appRes.data?.has_shop) {
        onSuccess?.();
      }
    } catch (error) {
      console.error(error);
    }
  };

  const createApplication = async () => {
    if (!formData.shop_name || !formData.shop_description || formData.categories.length === 0) {
      toast.error("Заполните все обязательные поля");
      return;
    }
    try {
      await axios.post(`${API}/shop/apply`, formData, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Заявка создана!");
      setShowForm(false);
      await checkExistingApplication();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка создания заявки");
    }
  };

  const handleSend = async () => {
    if (!newMessage.trim() || !conversation) return;
    setSending(true);
    try {
      await axios.post(`${API}/msg/user/conversations/${conversation.id}/messages`,
        { content: newMessage },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setNewMessage("");
      await fetchMessages();
    } catch (error) {
      toast.error("Ошибка отправки");
    } finally {
      setSending(false);
    }
  };

  const toggleCategory = (cat) => {
    setFormData(prev => ({
      ...prev,
      categories: prev.categories.includes(cat)
        ? prev.categories.filter(c => c !== cat)
        : [...prev.categories, cat]
    }));
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (loading) {
    return <div className="flex justify-center py-20"><Loader className="w-8 h-8 animate-spin text-[#71717A]" /></div>;
  }

  if (!application) {
    if (!showForm) {
      return (
        <div className="max-w-2xl mx-auto text-center py-12">
          <div className="w-20 h-20 bg-gradient-to-br from-[#10B981]/20 to-[#34D399]/10 rounded-3xl flex items-center justify-center mx-auto mb-6">
            <Store className="w-10 h-10 text-[#10B981]" />
          </div>
          <h2 className="text-2xl font-bold text-white mb-3">Открыть магазин</h2>
          <p className="text-[#71717A] mb-6 max-w-md mx-auto">
            Чтобы открыть магазин на маркетплейсе, заполните заявку. Администратор рассмотрит её и свяжется с вами.
          </p>
          <button onClick={() => setShowForm(true)} className="bg-[#10B981] hover:bg-[#059669] text-white rounded-xl h-12 px-8 inline-flex items-center gap-2">
            <MessageCircle className="w-5 h-5" />
            Подать заявку
          </button>
        </div>
      );
    }

    return (
      <div className="max-w-2xl mx-auto">
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
          <h2 className="text-xl font-bold text-white mb-6">Заявка на открытие магазина</h2>
          <div className="space-y-4">
            <div>
              <label className="text-sm text-[#A1A1AA] mb-2 block">Название магазина *</label>
              <input value={formData.shop_name} onChange={(e) => setFormData({...formData, shop_name: e.target.value})} placeholder="Мой магазин" className="w-full h-10 px-3 bg-[#0A0A0A] border border-white/10 text-white rounded-xl" />
            </div>
            <div>
              <label className="text-sm text-[#A1A1AA] mb-2 block">Категории товаров *</label>
              <div className="flex flex-wrap gap-2">
                {Object.entries(SHOP_CATEGORIES).map(([key, label]) => (
                  <button key={key} onClick={() => toggleCategory(key)} className={`px-3 py-1.5 rounded-lg text-xs transition-colors ${formData.categories.includes(key) ? "bg-[#10B981] text-white" : "bg-[#1A1A1A] text-[#71717A] hover:bg-white/10"}`}>{label}</button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-sm text-[#A1A1AA] mb-2 block">Описание магазина *</label>
              <textarea value={formData.shop_description} onChange={(e) => setFormData({...formData, shop_description: e.target.value})} placeholder="Расскажите о товарах..." className="w-full px-3 py-2 bg-[#0A0A0A] border border-white/10 text-white rounded-xl min-h-[100px] resize-none" />
            </div>
            <div>
              <label className="text-sm text-[#A1A1AA] mb-2 block">Telegram для связи</label>
              <input value={formData.telegram} onChange={(e) => setFormData({...formData, telegram: e.target.value})} placeholder="@username" className="w-full h-10 px-3 bg-[#0A0A0A] border border-white/10 text-white rounded-xl" />
            </div>
            <div>
              <label className="text-sm text-[#A1A1AA] mb-2 block">Опыт в продажах</label>
              <textarea value={formData.experience} onChange={(e) => setFormData({...formData, experience: e.target.value})} placeholder="Опишите ваш опыт (необязательно)" className="w-full px-3 py-2 bg-[#0A0A0A] border border-white/10 text-white rounded-xl resize-none" />
            </div>
          </div>
          <div className="flex gap-3 mt-6">
            <button onClick={() => setShowForm(false)} className="flex-1 bg-transparent border border-white/10 text-white rounded-xl h-10">Отмена</button>
            <button onClick={createApplication} className="flex-1 bg-[#10B981] hover:bg-[#059669] text-white rounded-xl h-10">Отправить заявку</button>
          </div>
        </div>
      </div>
    );
  }

  if (application.status === "rejected") {
    return (
      <div className="max-w-2xl mx-auto">
        <div className="bg-[#EF4444]/10 border border-[#EF4444]/20 rounded-2xl p-6 text-center">
          <XCircle className="w-12 h-12 text-[#EF4444] mx-auto mb-4" />
          <h3 className="text-xl font-bold text-white mb-2">Заявка отклонена</h3>
          <p className="text-[#A1A1AA] mb-4">{application.admin_comment || "Администратор отклонил вашу заявку"}</p>
          <button onClick={() => { setApplication(null); setShowForm(true); }} className="bg-[#10B981] hover:bg-[#059669] text-white rounded-xl h-10 px-6">Подать новую заявку</button>
        </div>
      </div>
    );
  }

  const statusColors = { pending: "bg-[#F59E0B]/10 text-[#F59E0B] border-[#F59E0B]/30", reviewing: "bg-[#3B82F6]/10 text-[#3B82F6] border-[#3B82F6]/30", approved: "bg-[#10B981]/10 text-[#10B981] border-[#10B981]/30" };
  const statusNames = { pending: "На рассмотрении", reviewing: "В обработке", approved: "Одобрено" };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="bg-[#121212] border border-white/5 rounded-2xl p-4 mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-[#10B981]/10 rounded-xl flex items-center justify-center"><Store className="w-5 h-5 text-[#10B981]" /></div>
          <div>
            <div className="text-white font-medium">{application.shop_name}</div>
            <div className="text-xs text-[#52525B]">Заявка на открытие магазина</div>
          </div>
        </div>
        <span className={`px-3 py-1.5 rounded-lg text-xs border ${statusColors[application.status] || statusColors.pending}`}>{statusNames[application.status] || "На рассмотрении"}</span>
      </div>
      <div className="bg-[#121212] border border-white/5 rounded-2xl overflow-hidden flex flex-col" style={{ height: "500px" }}>
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg) => (
            <div key={msg.id} className={`flex ${msg.sender_id === user?.id ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[75%] p-3 rounded-2xl ${msg.sender_id === user?.id ? "bg-[#10B981] text-white" : msg.sender_role === "system" || msg.is_system ? "bg-[#7C3AED]/20 text-[#A78BFA] border border-[#7C3AED]/30" : "bg-[#1A1A1A] text-white"}`}>
                {msg.sender_role && msg.sender_role !== "system" && msg.sender_id !== user?.id && (<div className="text-xs text-[#10B981] mb-1 font-medium">{msg.sender_nickname || "Модератор"}</div>)}
                <p className="whitespace-pre-wrap">{msg.content}</p>
                <div className={`text-xs mt-1 ${msg.sender_id === user?.id ? "text-white/70" : "text-[#52525B]"}`}>{new Date(msg.created_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}</div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
        <div className="border-t border-white/5 p-4">
          <div className="flex gap-2">
            <input value={newMessage} onChange={(e) => setNewMessage(e.target.value)} onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()} placeholder="Написать сообщение..." className="flex-1 h-10 px-3 bg-[#0A0A0A] border border-white/10 text-white rounded-xl" disabled={sending} />
            <button onClick={handleSend} disabled={sending || !newMessage.trim()} className="bg-[#10B981] hover:bg-[#059669] text-white rounded-xl h-10 w-10 flex items-center justify-center"><Send className="w-4 h-4" /></button>
          </div>
        </div>
      </div>
    </div>
  );
}

function MerchantShopManagement() {
  const { token, user } = useAuth();
  const [products, setProducts] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showAddProduct, setShowAddProduct] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [addingStock, setAddingStock] = useState(null);
  const [showWithdraw, setShowWithdraw] = useState(false);
  const [withdrawAmount, setWithdrawAmount] = useState("");
  const [withdrawing, setWithdrawing] = useState(false);
  const [productForm, setProductForm] = useState({ name: "", description: "", price: "", currency: "USDT", category: "accounts", type: "digital", delivery_text: "" });
  const [stockText, setStockText] = useState("");

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    try {
      const [dashboardRes, productsRes] = await Promise.all([
        axios.get(`${API}/shop/dashboard`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/shop/products`, { headers: { Authorization: `Bearer ${token}` } })
      ]);
      setDashboard(dashboardRes.data);
      setProducts(productsRes.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddProduct = async () => {
    if (!productForm.name || !productForm.price) { toast.error("Заполните название и цену"); return; }
    try {
      if (editingProduct) {
        await axios.put(`${API}/shop/products/${editingProduct.id}`, productForm, { headers: { Authorization: `Bearer ${token}` } });
        toast.success("Товар обновлён");
      } else {
        await axios.post(`${API}/shop/products`, productForm, { headers: { Authorization: `Bearer ${token}` } });
        toast.success("Товар добавлен");
      }
      setShowAddProduct(false); setEditingProduct(null);
      setProductForm({ name: "", description: "", price: "", currency: "USDT", category: "accounts", type: "digital", delivery_text: "" });
      fetchData();
    } catch (error) { toast.error(error.response?.data?.detail || "Ошибка"); }
  };

  const handleDeleteProduct = async (productId) => {
    if (!confirm("Удалить товар?")) return;
    try {
      await axios.delete(`${API}/shop/products/${productId}`, { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Товар удалён"); fetchData();
    } catch (error) { toast.error("Ошибка удаления"); }
  };

  const handleAddStock = async (productId) => {
    if (!stockText.trim()) return;
    const items = stockText.split("\n").filter(s => s.trim());
    try {
      await axios.post(`${API}/shop/products/${productId}/stock`, { items }, { headers: { Authorization: `Bearer ${token}` } });
      toast.success(`Добавлено ${items.length} единиц`);
      setAddingStock(null); setStockText(""); fetchData();
    } catch (error) { toast.error(error.response?.data?.detail || "Ошибка"); }
  };

  const handleWithdraw = async () => {
    const amount = parseFloat(withdrawAmount);
    if (!amount || amount <= 0) { toast.error("Введите корректную сумму"); return; }
    setWithdrawing(true);
    try {
      await axios.post(`${API}/shop/withdraw?amount=${amount}&method=to_balance&details=${encodeURIComponent("На баланс аккаунта")}`, {}, { headers: { Authorization: `Bearer ${token}` } });
      toast.success(`${amount} USDT переведено на баланс аккаунта`);
      setShowWithdraw(false); setWithdrawAmount(""); fetchData();
    } catch (error) { toast.error(error.response?.data?.detail || "Ошибка вывода"); }
    finally { setWithdrawing(false); }
  };

  if (loading) {
    return <div className="flex justify-center py-20"><Loader className="w-8 h-8 animate-spin text-[#71717A]" /></div>;
  }

  const shopBalance = dashboard?.shop?.shop_balance || 0;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Мой магазин</h1>
      <div className="grid sm:grid-cols-2 gap-4">
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 bg-[#10B981]/10 rounded-2xl flex items-center justify-center"><Store className="w-7 h-7 text-[#10B981]" /></div>
            <div>
              <div className="text-lg font-bold text-white">{dashboard?.shop?.shop_name || "Магазин"}</div>
              <div className="text-sm text-[#71717A]">{dashboard?.shop?.shop_description || ""}</div>
            </div>
          </div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
          <div className="text-sm text-[#71717A] mb-1">Баланс магазина</div>
          <div className="text-2xl font-bold text-[#10B981] font-['JetBrains_Mono']">{shopBalance.toFixed(2)} USDT</div>
          {shopBalance > 0 && (
            <button onClick={() => setShowWithdraw(true)} className="mt-3 bg-[#7C3AED] hover:bg-[#6D28D9] text-white rounded-xl h-9 px-4 text-sm inline-flex items-center gap-2">
              <Download className="w-4 h-4" />Вывести на баланс
            </button>
          )}
        </div>
      </div>
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-[#121212] border border-white/5 rounded-xl p-4 text-center">
          <div className="text-2xl font-bold text-white">{dashboard?.total_products || 0}</div>
          <div className="text-xs text-[#71717A]">Товаров</div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-xl p-4 text-center">
          <div className="text-2xl font-bold text-white">{dashboard?.total_sales || 0}</div>
          <div className="text-xs text-[#71717A]">Продаж</div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-xl p-4 text-center">
          <div className="text-2xl font-bold text-[#10B981] font-['JetBrains_Mono']">{(dashboard?.total_revenue || 0).toFixed(2)}</div>
          <div className="text-xs text-[#71717A]">Выручка USDT</div>
        </div>
      </div>
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium text-white">Товары ({products.length})</h3>
        <button onClick={() => { setEditingProduct(null); setProductForm({ name: "", description: "", price: "", currency: "USDT", category: "accounts", type: "digital", delivery_text: "" }); setShowAddProduct(true); }} className="bg-[#10B981] hover:bg-[#059669] text-white rounded-xl h-9 px-4 text-sm inline-flex items-center gap-2">
          <Plus className="w-4 h-4" />Добавить товар
        </button>
      </div>
      {products.length === 0 ? (
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-6 text-center py-10">
          <Package className="w-12 h-12 text-[#52525B] mx-auto mb-3" />
          <p className="text-[#71717A]">Нет товаров. Добавьте первый товар!</p>
        </div>
      ) : (
        <div className="space-y-3">
          {products.map(p => (
            <div key={p.id} className="bg-[#121212] border border-white/5 rounded-xl p-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-white font-medium">{p.name}</div>
                  <div className="text-sm text-[#71717A] mt-1">{p.description?.slice(0, 80)}</div>
                  <div className="flex items-center gap-4 mt-2">
                    <span className="text-[#10B981] font-medium font-['JetBrains_Mono']">{p.price} {p.currency || "USDT"}</span>
                    <span className="text-xs text-[#71717A]">В наличии: {p.stock_count ?? p.quantity ?? 0}</span>
                    <span className="text-xs px-2 py-0.5 rounded bg-white/5 text-[#71717A]">{SHOP_CATEGORIES[p.category] || p.category}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={() => setAddingStock(p)} className="text-[#10B981] hover:bg-[#10B981]/10 rounded-lg p-2" title="Добавить товар"><Plus className="w-4 h-4" /></button>
                  <button onClick={() => { setEditingProduct(p); setProductForm({ name: p.name, description: p.description || "", price: p.price, currency: p.currency || "USDT", category: p.category || "accounts", type: p.type || "digital", delivery_text: p.delivery_text || "" }); setShowAddProduct(true); }} className="text-[#3B82F6] hover:bg-[#3B82F6]/10 rounded-lg p-2" title="Редактировать"><Edit className="w-4 h-4" /></button>
                  <button onClick={() => handleDeleteProduct(p.id)} className="text-[#EF4444] hover:bg-[#EF4444]/10 rounded-lg p-2" title="Удалить"><Trash2 className="w-4 h-4" /></button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      {showAddProduct && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-[#121212] border border-white/10 rounded-2xl p-6 w-full max-w-md max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-semibold text-white mb-4">{editingProduct ? "Редактировать товар" : "Добавить товар"}</h3>
            <div className="space-y-3">
              <div><label className="text-sm text-[#A1A1AA] mb-1 block">Название *</label><input value={productForm.name} onChange={(e) => setProductForm({...productForm, name: e.target.value})} className="w-full h-10 px-3 bg-[#0A0A0A] border border-white/10 text-white rounded-xl" placeholder="Название товара" /></div>
              <div><label className="text-sm text-[#A1A1AA] mb-1 block">Описание</label><textarea value={productForm.description} onChange={(e) => setProductForm({...productForm, description: e.target.value})} className="w-full px-3 py-2 bg-[#0A0A0A] border border-white/10 text-white rounded-xl resize-none min-h-[80px]" placeholder="Описание товара" /></div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="text-sm text-[#A1A1AA] mb-1 block">Цена *</label><input type="number" step="0.01" value={productForm.price} onChange={(e) => setProductForm({...productForm, price: e.target.value})} className="w-full h-10 px-3 bg-[#0A0A0A] border border-white/10 text-white rounded-xl" placeholder="0.00" /></div>
                <div><label className="text-sm text-[#A1A1AA] mb-1 block">Категория</label><select value={productForm.category} onChange={(e) => setProductForm({...productForm, category: e.target.value})} className="w-full h-10 px-3 bg-[#0A0A0A] border border-white/10 text-white rounded-xl">{Object.entries(SHOP_CATEGORIES).map(([k, v]) => (<option key={k} value={k}>{v}</option>))}</select></div>
              </div>
              <div><label className="text-sm text-[#A1A1AA] mb-1 block">Текст после покупки</label><textarea value={productForm.delivery_text} onChange={(e) => setProductForm({...productForm, delivery_text: e.target.value})} className="w-full px-3 py-2 bg-[#0A0A0A] border border-white/10 text-white rounded-xl resize-none" placeholder="Что получит покупатель" /></div>
            </div>
            <div className="flex gap-3 mt-4">
              <button onClick={() => { setShowAddProduct(false); setEditingProduct(null); }} className="flex-1 bg-transparent border border-white/10 text-white rounded-xl h-10">Отмена</button>
              <button onClick={handleAddProduct} className="flex-1 bg-[#10B981] hover:bg-[#059669] text-white rounded-xl h-10">{editingProduct ? "Сохранить" : "Добавить"}</button>
            </div>
          </div>
        </div>
      )}
      {addingStock && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-[#121212] border border-white/10 rounded-2xl p-6 w-full max-w-md">
            <h3 className="text-lg font-semibold text-white mb-2">Добавить товар: {addingStock.name}</h3>
            <p className="text-sm text-[#71717A] mb-4">Каждая строка = 1 единица товара</p>
            <textarea value={stockText} onChange={(e) => setStockText(e.target.value)} className="w-full px-3 py-2 bg-[#0A0A0A] border border-white/10 text-white rounded-xl resize-none min-h-[150px] font-mono text-sm" placeholder={"login:password\nlogin2:password2\n..."} />
            <div className="flex gap-3 mt-4">
              <button onClick={() => { setAddingStock(null); setStockText(""); }} className="flex-1 bg-transparent border border-white/10 text-white rounded-xl h-10">Отмена</button>
              <button onClick={() => handleAddStock(addingStock.id)} className="flex-1 bg-[#10B981] hover:bg-[#059669] text-white rounded-xl h-10">Добавить ({stockText.split("\n").filter(s => s.trim()).length} шт)</button>
            </div>
          </div>
        </div>
      )}
      {showWithdraw && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-[#121212] border border-white/10 rounded-2xl p-6 w-full max-w-md">
            <h3 className="text-lg font-semibold text-white mb-2">Вывод на баланс аккаунта</h3>
            <p className="text-sm text-[#71717A] mb-4">Доступно: <span className="text-[#10B981] font-mono">{shopBalance.toFixed(2)} USDT</span></p>
            <p className="text-xs text-[#A1A1AA] mb-4">Средства будут переведены на ваш основной баланс аккаунта</p>
            <div><label className="text-sm text-[#A1A1AA] mb-1 block">Сумма (USDT)</label><input type="number" step="0.01" min="0.01" max={shopBalance} value={withdrawAmount} onChange={(e) => setWithdrawAmount(e.target.value)} className="w-full h-10 px-3 bg-[#0A0A0A] border border-white/10 text-white rounded-xl" placeholder="0.00" /></div>
            <div className="flex gap-3 mt-4">
              <button onClick={() => { setShowWithdraw(false); setWithdrawAmount(""); }} className="flex-1 bg-transparent border border-white/10 text-white rounded-xl h-10">Отмена</button>
              <button onClick={handleWithdraw} disabled={withdrawing} className="flex-1 bg-[#7C3AED] hover:bg-[#6D28D9] text-white rounded-xl h-10">{withdrawing ? "Вывод..." : "Вывести на баланс"}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

