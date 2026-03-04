import React, { useState, useEffect } from "react";
import { Routes, Route, Link, useLocation, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { 
  LogOut, LayoutDashboard, Users, Settings, MessageCircle,
  DollarSign, TrendingUp, Eye, Wallet,
  Store, Package, Shield, AlertTriangle,
  ArrowDownRight, FileText, ShoppingBag,
  Activity, UserCog, History,
  ChevronRight, ChevronDown,
  Briefcase, Percent, Send, Menu, XCircle
} from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";

// Badge component for notification counts
const NotificationBadge = ({ count }) => {
  if (!count || count === 0) return null;
  return (
    <span className="ml-auto bg-[#EF4444] text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center">
      {count > 99 ? "99+" : count}
    </span>
  );
};

// Red dot indicator (no number)
const RedDotIndicator = ({ show }) => {
  if (!show) return null;
  return (
    <span className="ml-auto w-2 h-2 bg-[#EF4444] rounded-full flex-shrink-0" />
  );
};

// Import all admin components
import BroadcastPageComponent from "@/components/admin/BroadcastPage";
import StaffMonitoringComponent from "@/components/admin/StaffMonitoring";
import SuperAdminOverviewComponent from "@/components/admin/SuperAdminOverview";
import UsersManagementComponent from "@/components/admin/UsersManagement";
import UnifiedMessagesHubComponent from "@/components/admin/UnifiedMessagesHub";
import StaffManagementComponent from "@/components/admin/StaffManagement";
import FinancesOverviewComponent from "@/components/admin/FinancesOverview";
import P2PTradesComponent from "@/components/admin/P2PTrades";
import P2POffersComponent from "@/components/admin/P2POffers";
import MerchantsListComponent from "@/components/admin/MerchantsList";
import MarketShopsComponent from "@/components/admin/MarketShops";
import MarketProductsComponent from "@/components/admin/MarketProducts";
import MarketGuarantorComponent from "@/components/admin/MarketGuarantor";
import MarketWithdrawalsComponent from "@/components/admin/MarketWithdrawals";
import MarketplaceOrdersComponent from "@/components/admin/MarketplaceOrders";
import CommissionsSettingsComponent from "@/components/admin/CommissionsSettings";
import SystemSettingsComponent from "@/components/admin/SystemSettings";
import ActivityLogsComponent from "@/components/admin/ActivityLogs";
import PayoutRulesSettingsComponent from "@/components/admin/PayoutRulesSettings";
import CryptoPayoutsComponent from "@/components/admin/CryptoPayouts";
import AdminMessagesToStaffComponent from "@/components/admin/AdminMessagesToStaff";
import ReferralSettingsComponent from "@/components/admin/ReferralSettings";
import AdminFinancePage from "./finance/AdminFinancePage";

// ==================== MAIN ADMIN PANEL ====================
export default function AdminPanel() {
  const { user, logout, token } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState({});
  const [notifications, setNotifications] = useState({});
  
  const adminRole = user?.admin_role || "admin";

  useEffect(() => {
    if (user?.role !== "admin") navigate("/");
  }, [user, navigate]);

  useEffect(() => {
    const fetchNotifications = async () => {
      try {
        const response = await axios.get(`${API}/super-admin/notifications-count`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setNotifications(response.data);
      } catch (error) {
        console.error("Failed to fetch notifications:", error);
      }
    };
    
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
  }, [token]);

  const toggleSection = (title) => {
    setCollapsed(prev => ({ ...prev, [title]: !prev[title] }));
  };

  const roleAccess = {
    owner: ["*"],
    admin: ["*"],
    mod_p2p: ["Управление", "P2P Торговля", "Мерчанты", "Сообщения"],
    mod_market: ["Маркетплейс", "Сообщения"],
    support: ["Сообщения"]
  };

  const canAccessSection = (sectionTitle) => {
    const allowedSections = roleAccess[adminRole] || [];
    return allowedSections.includes("*") || allowedSections.includes(sectionTitle);
  };

  const allSections = [
    {
      title: "Управление",
      items: [
        { path: "/admin", icon: LayoutDashboard, label: "Обзор", roles: ["owner", "admin"] },
        { path: "/admin/users", icon: Users, label: "Пользователи", roles: ["owner", "admin", "mod_p2p"] },
        { path: "/admin/staff", icon: UserCog, label: "Персонал", roles: ["owner", "admin"] },
        { path: "/admin/staff/monitor", icon: Eye, label: "Мониторинг", roles: ["owner", "admin"] },
        { path: "/admin/finances", icon: DollarSign, label: "Финансы", roles: ["owner", "admin"] },
        { path: "/admin/wallet", icon: Wallet, label: "USDT Кошелёк", roles: ["owner", "admin", "mod_p2p"] },
      ]
    },
    {
      title: "P2P Торговля",
      items: [
        { path: "/admin/p2p/offers", icon: TrendingUp, label: "Объявления" },
        { path: "/admin/p2p/trades", icon: Activity, label: "Сделки" },
      ]
    },
    {
      title: "Мерчанты",
      items: [
        { path: "/admin/merchants", icon: Briefcase, label: "Список" },
        { path: "/admin/merchants/payouts", icon: ArrowDownRight, label: "Выплаты" },
        { path: "/admin/merchants/payout-rules", icon: FileText, label: "Правила выплат" },
      ]
    },
    {
      title: "Маркетплейс",
      items: [
        { path: "/admin/market/shops", icon: Store, label: "Магазины" },
        { path: "/admin/market/products", icon: Package, label: "Товары" },
        { path: "/admin/market/orders", icon: ShoppingBag, label: "Заказы" },
        { path: "/admin/market/guarantor", icon: Shield, label: "Гарант-сделки" },
        { path: "/admin/market/withdrawals", icon: ArrowDownRight, label: "Выводы", roles: ["owner", "admin"] },
      ]
    },
    {
      title: "Сообщения",
      items: [
        { path: "/admin/messages", icon: MessageCircle, label: "Все чаты", showDot: "messages_total" },
        { path: "/admin/messages/staff", icon: UserCog, label: "Персонал", showDot: "staff_messages", roles: ["owner", "admin", "mod_p2p", "mod_market", "support"] },
        { path: "/admin/broadcast", icon: Send, label: "Рассылка", roles: ["owner", "admin", "support"] },
      ]
    },
    {
      title: "Настройки",
      items: [
        { path: "/admin/settings/commissions", icon: Percent, label: "Комиссии" },
        { path: "/admin/settings/referral", icon: Users, label: "Рефералы" },
        { path: "/admin/settings/system", icon: Settings, label: "Система" },
        { path: "/admin/logs", icon: History, label: "Логи" },
      ],
      roles: ["owner", "admin"]
    }
  ];

  const filterSectionsByRole = () => {
    return allSections
      .filter(section => {
        if (section.roles && !section.roles.includes(adminRole)) return false;
        return canAccessSection(section.title);
      })
      .map(section => ({
        ...section,
        items: section.items.filter(item => {
          if (item.roles && !item.roles.includes(adminRole)) return false;
          return true;
        })
      }))
      .filter(section => section.items.length > 0);
  };

  const sections = filterSectionsByRole();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Close sidebar on route change (mobile)
  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  return (
    <div className="min-h-screen bg-[#0A0A0A] flex" data-testid="admin-panel">
      {/* Mobile Header */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-40 bg-[#0A0A0A] border-b border-white/5 px-4 py-3 flex items-center justify-between">
        <button 
          onClick={() => setSidebarOpen(true)}
          className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center text-white"
        >
          <Menu className="w-5 h-5" />
        </button>
        <div className="flex items-center gap-2">
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
            adminRole === "owner" || adminRole === "admin" 
              ? "bg-gradient-to-br from-[#10B981] to-[#059669]" 
              : adminRole === "mod_p2p" 
                ? "bg-gradient-to-br from-[#3B82F6] to-[#1D4ED8]"
                : adminRole === "mod_market"
                  ? "bg-gradient-to-br from-[#8B5CF6] to-[#6D28D9]"
                  : "bg-gradient-to-br from-[#F59E0B] to-[#D97706]"
          }`}>
            <Shield className="w-4 h-4 text-white" />
          </div>
          <span className="text-white text-sm font-medium">{user?.login}</span>
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
        w-60 border-r border-white/5 flex flex-col h-screen bg-[#0A0A0A]
        fixed lg:sticky top-0 z-50
        transform transition-transform duration-200 ease-in-out
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
        <div className="p-3 border-b border-white/5 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
              adminRole === "owner" || adminRole === "admin" 
                ? "bg-gradient-to-br from-[#10B981] to-[#059669]" 
                : adminRole === "mod_p2p" 
                  ? "bg-gradient-to-br from-[#3B82F6] to-[#1D4ED8]"
                  : adminRole === "mod_market"
                    ? "bg-gradient-to-br from-[#8B5CF6] to-[#6D28D9]"
                    : "bg-gradient-to-br from-[#F59E0B] to-[#D97706]"
            }`}>
              <Shield className="w-4 h-4 text-white" />
            </div>
            <div>
              <span className="font-bold text-white text-sm">
                {adminRole === "owner" ? "Super Admin" 
                  : adminRole === "admin" ? "Администратор"
                  : adminRole === "mod_p2p" ? "Мод P2P"
                  : adminRole === "mod_market" ? "Мод Маркетплейс"
                  : "Поддержка"}
              </span>
              <div className={`text-[9px] uppercase tracking-wider ${
                adminRole === "owner" || adminRole === "admin" ? "text-[#10B981]" 
                  : adminRole === "mod_p2p" ? "text-[#3B82F6]"
                  : adminRole === "mod_market" ? "text-[#8B5CF6]"
                  : "text-[#F59E0B]"
              }`}>
                {user?.login}
              </div>
            </div>
          </Link>
          <button 
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden w-8 h-8 rounded-lg hover:bg-white/5 flex items-center justify-center text-[#71717A]"
          >
            <XCircle className="w-5 h-5" />
          </button>
        </div>

        <nav className="flex-1 p-2 overflow-y-auto scrollbar-thin">
          {sections.map((section, idx) => {
            return (
              <div key={idx} className="mb-1">
                <button
                  onClick={() => toggleSection(section.title)}
                  className="w-full flex items-center justify-between px-2 py-1.5 text-[10px] uppercase tracking-wider text-[#52525B] font-semibold hover:text-[#71717A]"
                >
                  <span className="flex items-center gap-1">
                    {section.title}
                  </span>
                  {collapsed[section.title] ? <ChevronRight className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                </button>
                {!collapsed[section.title] && section.items.map((item) => {
                  const isActive = location.pathname === item.path;
                  const showRedDot = item.showDot && notifications[item.showDot] > 0;
                  return (
                    <Link
                      key={item.path}
                      to={item.path}
                      className={`flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-xs transition-all ${
                        isActive
                          ? "bg-[#10B981]/15 text-[#10B981] font-medium"
                          : "text-[#A1A1AA] hover:bg-white/5 hover:text-white"
                      }`}
                    >
                      <item.icon className="w-3.5 h-3.5" />
                      <span className="flex-1">{item.label}</span>
                      <RedDotIndicator show={showRedDot} />
                    </Link>
                  );
                })}
              </div>
            );
          })}
        </nav>

        <div className="p-3 border-t border-white/5 space-y-2">
          <div className="text-[10px] text-[#52525B] px-2">
            {user?.login} • <span className={
              adminRole === "owner" || adminRole === "admin" ? "text-[#10B981]" 
                : adminRole === "mod_p2p" ? "text-[#3B82F6]"
                : adminRole === "mod_market" ? "text-[#8B5CF6]"
                : "text-[#F59E0B]"
            }>
              {adminRole === "owner" ? "owner" 
                : adminRole === "admin" ? "admin"
                : adminRole === "mod_p2p" ? "mod_p2p"
                : adminRole === "mod_market" ? "mod_market"
                : "support"}
            </span>
          </div>
          <Button
            variant="ghost"
            onClick={logout}
            size="sm"
            className="w-full justify-start text-[#EF4444] hover:text-[#EF4444] hover:bg-[#EF4444]/10 text-xs h-8"
           title="Выйти из аккаунта">
            <LogOut className="w-3.5 h-3.5 mr-2" />
            Выйти
          </Button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-4 overflow-y-auto pt-20 lg:pt-4">
        <Routes>
          <Route index element={<SuperAdminOverviewComponent />} />
          <Route path="users" element={<UsersManagementComponent />} />
          <Route path="staff" element={<StaffManagementComponent />} />
          <Route path="staff/monitor" element={<StaffMonitoringComponent />} />
          <Route path="finances" element={<FinancesOverviewComponent />} />
          <Route path="ton-finance" element={<AdminFinancePage />} />
          <Route path="wallet" element={<AdminFinancePage />} />
          <Route path="p2p/offers" element={<P2POffersComponent />} />
          <Route path="p2p/trades" element={<P2PTradesComponent />} />
          <Route path="p2p/disputes" element={<P2PTradesComponent initialFilter="disputed" />} />
          <Route path="merchants" element={<MerchantsListComponent />} />
          <Route path="merchants/payouts" element={<CryptoPayoutsComponent />} />
          <Route path="merchants/payout-rules" element={<PayoutRulesSettingsComponent />} />
          <Route path="market/shops" element={<MarketShopsComponent />} />
          <Route path="market/products" element={<MarketProductsComponent />} />
          <Route path="market/orders" element={<MarketplaceOrdersComponent />} />
          <Route path="market/guarantor" element={<MarketGuarantorComponent />} />
          <Route path="market/withdrawals" element={<MarketWithdrawalsComponent />} />
          <Route path="messages" element={<UnifiedMessagesHubComponent />} />
          <Route path="messages/staff" element={<AdminMessagesToStaffComponent />} />
          <Route path="broadcast" element={<BroadcastPageComponent />} />
          <Route path="settings/commissions" element={<CommissionsSettingsComponent />} />
          <Route path="settings/referral" element={<ReferralSettingsComponent />} />
          <Route path="settings/system" element={<SystemSettingsComponent />} />
          <Route path="logs" element={<ActivityLogsComponent />} />
        </Routes>
      </main>
    </div>
  );
}
