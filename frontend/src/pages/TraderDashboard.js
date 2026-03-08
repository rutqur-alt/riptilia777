import { useCallback, useEffect, useState } from "react";
import { Link, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import axios from "axios";
import {
  ChevronDown,
  ChevronRight,
  CreditCard,
  DollarSign,
  ExternalLink,
  History,
  LayoutDashboard,
  ListOrdered,
  LogOut,
  Menu,
  MessageCircle,
  Settings,
  ShoppingBag,
  Store,
  TrendingUp,
  User,
  Wallet,
  XCircle,
  Users
} from "lucide-react";

import { API, useAuth } from "@/App";
import EventNotificationDropdown from "@/components/EventNotificationDropdown";
import SidebarBadge from "@/components/shared/SidebarBadge";
import TraderBalance from "@/components/trader/TraderBalance";
import TraderHistory from "@/components/trader/TraderHistory";
import TraderHistoryPurchases from "@/components/trader/TraderHistoryPurchases";
import TraderHistorySales from "@/components/trader/TraderHistorySales";
import MyMarketPurchases from "@/components/trader/MyMarketPurchases";
import TraderAccount from "@/components/trader/TraderAccount";
import TraderOffers from "@/components/trader/TraderOffers";
import TraderPurchases from "@/components/trader/TraderPurchases";
import TraderReferral from "@/components/trader/TraderReferral";
import TraderSales from "@/components/trader/TraderSales";
import TraderSettings from "@/components/trader/TraderSettings";
import TraderTransactions from "@/components/trader/TraderTransactions";
import TraderWithdraw from "@/components/trader/TraderWithdraw";
import TradingSettings from "@/components/trader/TradingSettings";
import TradingStats from "@/components/trader/TradingStats";
import { useWebSocket } from "@/hooks/useWebSocket";

import MarketplaceGuarantorChat from "./MarketplaceGuarantorChat";
import MyMessagesPage from "./MyMessagesPage";
import BuyerTradePage from "./BuyerTradePage";
import PaymentDetailsPage from "./trader/PaymentDetails";
import ShopChats from "./ShopChats";
import TraderShop from "./TraderShop";
import TraderTradePage from "./TraderTradePage";
import UserFinancePage from "./finance/UserFinancePage";

export default function TraderDashboard() {
  const { user, token, logout, refreshUserBalance } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [traderInfo, setTraderInfo] = useState(null);
  const [sidebarBadges, setSidebarBadges] = useState({});
  
  // Calculate balance from user context (single source of truth)
  const balance = user ? (user.balance_usdt || 0) - (user.frozen_usdt || 0) : null;
  const frozenBalance = user?.frozen_usdt || 0;
  
  // WebSocket for real-time balance updates
  const handleWsMessage = useCallback((data) => {
    if (data.type === "balance_update" || data.type === "trade_completed" || data.type === "deposit_credited") {
      // Refresh user balance from server
      refreshUserBalance();
    }
  }, [refreshUserBalance]);
  
  useWebSocket(
    user?.id ? `/ws/user/${user.id}` : null,
    handleWsMessage,
    { enabled: !!user?.id }
  );
  
  // Collapsible sections state - auto-expand active sections
  const [expandedSections, setExpandedSections] = useState(() => {
    const path = window.location.pathname;
    return {
      trading: path.startsWith("/trader/offers") || path.startsWith("/trader/sales") || path.startsWith("/trader/purchases") || path.startsWith("/trader/payment-details") || path.startsWith("/trader/history") || path.startsWith("/trader/trading"),
      market: path.startsWith("/trader/my-purchases") || path.startsWith("/trader/shop") || path.startsWith("/marketplace") || path.startsWith("/trader/shop-chats"),
      finances: path.startsWith("/trader/transactions") || (path === "/trader"),
      other: false,
      account: path.startsWith("/trader/account") || path.startsWith("/trader/settings")
    };
  });

  const toggleSection = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  // Auto-expand active section on route change
  useEffect(() => {
    const path = location.pathname;
    setExpandedSections(prev => {
      const newState = { ...prev };
      if (path.startsWith("/trader/offers") || path.startsWith("/trader/sales") || path.startsWith("/trader/purchases") || path.startsWith("/trader/payment-details") || path.startsWith("/trader/history") || path.startsWith("/trader/trading")) {
        newState.trading = true;
      }
      if (path.startsWith("/trader/my-purchases") || path.startsWith("/trader/shop") || path.startsWith("/marketplace") || path.startsWith("/trader/shop-chats")) {
        newState.market = true;
      }
      if (path.startsWith("/trader/transactions") || path.startsWith("/trader/transfers")) {
        newState.finances = true;
      }
      if (path.startsWith("/trader/account") || path.startsWith("/trader/settings")) {
        newState.account = true;
      }
      return newState;
    });
  }, [location.pathname]);

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

  // Fetch trader info and urgent trades on mount
  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await axios.get(`${API}/traders/me`, {
          headers: { Authorization: `Bearer ${token}` }
        });
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

  // Badge component for sidebar (shared)
  const Badge = SidebarBadge;

  // Navigation sections with collapsible items
  const sections = [
    {
      key: "dashboard",
      title: "Дашборд",
      icon: LayoutDashboard,
      single: true,
      path: "/trader",
      exact: true
    },
    {
      key: "trading",
      title: "Торговля",
      icon: TrendingUp,
      notifyKey: "trades",
      items: [
        { path: "/trader/offers", icon: ListOrdered, label: "Объявления" },
        { path: "/trader/sales", icon: TrendingUp, label: "Продажи", notifyKey: "trades" },
        { path: "/trader/purchases", icon: DollarSign, label: "Покупки", notifyKey: "trades" },
        { path: "/trader/payment-details", icon: CreditCard, label: "Реквизиты" },
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
        { path: "/trader/shop-chats", icon: MessageCircle, label: "Сообщения магазинов", notifyKey: "shop_chats" },
        { path: "/trader/shop", icon: Store, label: "Мой магазин", notifyKey: "shop_messages" }
      ]
    },
    {
      key: "finances",
      title: "Финансы",
      icon: Wallet,
      single: true,
      path: "/trader/wallet"
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

  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Close sidebar on route change (mobile)
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
        <Link to="/" className="flex items-center gap-2">
          <img src="/logo.png" alt="Reptiloid" className="h-8 w-8" />
          <span className="text-white font-medium">{user?.display_name || user?.nickname || user?.login}</span>
        </Link>
        <div className="text-[#7C3AED] font-medium text-sm font-mono">
          {balance !== null ? balance.toFixed(2) : "—"}
        </div>
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
        w-64 bg-[#121212] border-r border-white/5 flex-col h-screen overflow-y-auto
        fixed lg:sticky top-0 z-50
        transform transition-transform duration-200 ease-in-out
        ${sidebarOpen ? 'translate-x-0 flex' : '-translate-x-full lg:translate-x-0 hidden lg:flex'}
      `}>
        {/* Header with Logo */}
        <div className="p-5 border-b border-white/5 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3">
            <img src="/logo.png" alt="Reptiloid" className="h-9 w-9" />
            <div>
              <div className="text-white font-semibold font-['Unbounded'] text-sm">Reptiloid</div>
              <div className="text-xs text-[#52525B]">Личный кабинет</div>
            </div>
          </Link>
          <button 
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden w-8 h-8 rounded-lg hover:bg-white/5 flex items-center justify-center text-[#71717A]"
          >
            <XCircle className="w-5 h-5" />
          </button>
        </div>

        {/* Balance Card - Inside sidebar, not floating */}
        <div className="p-4 border-b border-white/5">
          <div className="bg-gradient-to-br from-[#7C3AED]/20 to-[#A855F7]/10 border border-[#7C3AED]/30 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-[#A78BFA]">Доступно</span>
              <EventNotificationDropdown token={token} role="trader" />
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-white font-['JetBrains_Mono']">
                {balance !== null ? balance.toFixed(2) : "—"}
              </span>
              <span className="text-sm text-[#71717A]">USDT</span>
            </div>
            {frozenBalance > 0 && (
              <div className="text-xs text-yellow-500 mt-2">
                +{frozenBalance.toFixed(2)} заморожено
              </div>
            )}
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {/* Collapsible Sections */}
          {sections.map((section) => (
            <div key={section.key}>
              {section.single ? (
                /* Single Item (not collapsible) */
                <Link
                  to={section.path}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-colors ${
                    section.exact 
                      ? (location.pathname === section.path ? "bg-[#7C3AED]/10 text-[#A78BFA]" : "text-[#A1A1AA] hover:bg-white/5 hover:text-white")
                      : (location.pathname.startsWith(section.path) ? "bg-[#7C3AED]/10 text-[#A78BFA]" : "text-[#A1A1AA] hover:bg-white/5 hover:text-white")
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
              {(user?.display_name || user?.nickname || user?.login || "U")[0].toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-white font-medium text-sm truncate">@{user?.display_name || user?.nickname || user?.login}</div>
              <div className="text-[10px] text-[#52525B]">
                {traderInfo?.created_at ? `с ${new Date(traderInfo.created_at).toLocaleDateString("ru-RU")}` : ""}
              </div>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-[#EF4444]/70 hover:bg-[#EF4444]/10 hover:text-[#EF4444] transition-colors w-full text-sm"
            data-testid="logout-btn"
           title="Выйти из аккаунта">
            <LogOut className="w-4 h-4" />
            <span>Выйти</span>
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-4 lg:p-8 overflow-y-auto pt-20 lg:pt-8">
                <Routes>
          <Route index element={<TraderBalance />} />
          <Route path="payment-details" element={<PaymentDetailsPage />} />
          <Route path="offers" element={<TraderOffers />} />
          <Route path="sales" element={<TraderSales />} />
          <Route path="sales/:tradeId" element={<TraderTradePage />} />
          <Route path="purchases" element={<TraderPurchases />} />
          <Route path="purchases/:tradeId" element={<BuyerTradePage />} />
          <Route path="history" element={<TraderHistory />} />
          <Route path="history/sales" element={<TraderHistorySales />} />
          <Route path="history/purchases" element={<TraderHistoryPurchases />} />
          <Route path="transactions" element={<TraderTransactions />} />
          <Route path="wallet" element={<UserFinancePage />} />
          <Route path="trading-stats" element={<TradingStats />} />
          <Route path="trading-settings" element={<TradingSettings />} />
          <Route path="shop-chats" element={<ShopChats />} />
          <Route path="guarantor-chat/:purchaseId" element={<MarketplaceGuarantorChat />} />
          <Route path="shop" element={<TraderShop />} />
          <Route path="my-purchases" element={<MyMarketPurchases />} />
          <Route path="withdraw" element={<TraderWithdraw />} />
          <Route path="messages" element={<MyMessagesPage />} />
          <Route path="referral" element={<TraderReferral />} />
          <Route path="settings" element={<TraderSettings />} />
          <Route path="account" element={<TraderAccount />} />
        </Routes>
      </main>
    </div>
  );
}

// Inline sub-components extracted to @/components/trader/*.jsx (Etap 2.1).
// Old inline implementations moved to frontend/_old/TraderDashboard.inline-components.old.js
