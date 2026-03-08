import { useEffect, useState } from "react";
import { Link, Route, Routes, useLocation } from "react-router-dom";

import { useAuth } from "@/App";
import { Button } from "@/components/ui/button";
import EventNotificationDropdown from "@/components/EventNotificationDropdown";

import {
  ArrowUpRight,
  BarChart3,
  ChevronDown,
  DollarSign,
  Home,
  Key,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageCircle,
  Settings,
  TrendingUp,
  User,
  Wallet,
  XCircle,
} from "lucide-react";
import MerchantMessagesPage from "./MerchantMessagesPage";
import MerchantAPI from "./MerchantAPI";
import MerchantDisputesPage from "./MerchantDisputesPage";
import UserFinancePage from "./finance/UserFinancePage";
import PendingMerchantChat from "@/components/merchant/PendingMerchantChat";
import RejectedView from "@/components/merchant/RejectedView";
import MerchantMainDashboard from "@/components/merchant/MerchantMainDashboard";
import MerchantAnalytics from "@/components/merchant/MerchantAnalytics";
import MerchantWithdrawalRequests from "@/components/merchant/MerchantWithdrawalRequests";
import MerchantPayments from "@/components/merchant/MerchantPayments";
import MerchantTransactions from "@/components/merchant/MerchantTransactions";
import MerchantWithdraw from "@/components/merchant/MerchantWithdraw";
import MerchantAccount from "@/components/merchant/MerchantAccount";
import MerchantSettings from "@/components/merchant/MerchantSettings";
import MerchantShop from "@/components/merchant/MerchantShop";

export default function MerchantDashboard() {
  const { user, token, logout } = useAuth();
  const location = useLocation();

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

  const isPending = user?.status === "pending";
  const isRejected = user?.status === "rejected";

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
      items: [
        { path: "/merchant/withdrawal-requests", icon: ArrowUpRight, label: "Заявки на выплаты" },
        { path: "/merchant/payments", icon: DollarSign, label: "Платежи" }
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
      single: true,
      path: "/merchant/wallet"
    },
    {
      key: "messages",
      title: "Сообщения",
      icon: MessageCircle,
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
            {((user?.balance_usdt || 0) - (user?.frozen_usdt || 0)).toFixed(2)}
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
              <div className="text-[10px] text-[#52525B] uppercase tracking-wider">Доступно</div>
              <EventNotificationDropdown token={token} role="merchant" />
            </div>
            <div className="text-xl font-bold text-white font-['JetBrains_Mono']">
              {((user?.balance_usdt || 0) - (user?.frozen_usdt || 0)).toFixed(2)} <span className="text-[#F97316]">USDT</span>
            </div>
            {(user?.frozen_usdt || 0) > 0 && (
              <div className="text-xs text-yellow-500 mt-1">
                +{(user?.frozen_usdt || 0).toFixed(2)} заморожено
              </div>
            )}
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
            <Route path="wallet" element={<UserFinancePage />} />
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

// Inline components were extracted to frontend/_old/MerchantDashboard.inline-components.old.js

