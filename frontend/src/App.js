import React from 'react';
import ReactDOM from 'react-dom';
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, Link, useLocation, useNavigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { createContext, useContext, useState, useEffect } from "react";
import axios from "axios";

// Pages
import Landing from "@/pages/Landing";
import Auth from "@/pages/Auth";
import MerchantRegister from "@/pages/MerchantRegister";
import TraderDashboard from "@/pages/TraderDashboard";
import MerchantDashboard from "@/pages/MerchantDashboard";
import AdminPanel from "@/pages/AdminPanel";
import TradePage from "@/pages/TradePage";
import PayPage from "@/pages/PayPage";
import DepositPage from "@/pages/DepositPage";
import DemoShop from "@/pages/DemoShop";
import ApiDocs from "@/pages/ApiDocs";
import DirectBuyPage from "@/pages/DirectBuyPage";
import Forum from "@/pages/Forum";
import Marketplace from "@/pages/Marketplace";
import ShopPage from "@/pages/ShopPage";
import ProductPage from "@/pages/ProductPage";
import MaintenancePage from "@/pages/MaintenancePage";
import BuyCrypto from "@/pages/BuyCrypto";
import Referrals from "@/pages/Referrals";
import PublicDisputePage from "@/pages/PublicDisputePage";
import SelectOperatorPage from "@/pages/SelectOperatorPage";
import QRProviderDashboard from "@/pages/QRProviderDashboard";


const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

// Auth Context
const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
};

const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem("token"));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      const savedToken = localStorage.getItem("token");
      if (savedToken) {
        try {
          const response = await axios.get(`${API}/auth/me`, {
            headers: { Authorization: `Bearer ${savedToken}` }
          });
          setUser(response.data.user);
          setToken(savedToken);
        } catch (error) {
          localStorage.removeItem("token");
          setToken(null);
          setUser(null);
        }
      }
      setLoading(false);
    };
    initAuth();
  }, []);

  // Function to refresh user balance from server
  const refreshUserBalance = async () => {
    if (!token) return;
    try {
      const response = await axios.get(`${API}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setUser(response.data.user);
    } catch (error) {
      console.error("Failed to refresh balance:", error);
    }
  };

  // Function to update balance locally (for immediate UI update)
  const updateUserBalance = (newBalance, newFrozen) => {
    setUser(prev => ({
      ...prev,
      balance_usdt: newBalance,
      frozen_usdt: newFrozen
    }));
  };

  const login = async (credentials) => {
    const response = await axios.post(`${API}/auth/login`, credentials);
    const { token: newToken, user: userData } = response.data;
    localStorage.setItem("token", newToken);
    setToken(newToken);
    setUser(userData);
    return userData;
  };

  const registerTrader = async (data) => {
    const response = await axios.post(`${API}/auth/trader/register`, data);
    const { token: newToken, user: userData } = response.data;
    localStorage.setItem("token", newToken);
    setToken(newToken);
    setUser(userData);
    return userData;
  };

  const registerMerchant = async (data) => {
    const response = await axios.post(`${API}/auth/merchant/register`, data);
    const { token: newToken, user: userData } = response.data;
    localStorage.setItem("token", newToken);
    setToken(newToken);
    setUser(userData);
    return userData;
  };

  const logout = () => {
    localStorage.removeItem("token");
    setToken(null);
    setUser(null);
  };

  const value = {
    user,
    token,
    loading,
    login,
    registerTrader,
    registerMerchant,
    logout,
    refreshUserBalance,
    updateUserBalance,
    isAuthenticated: !!token
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

// Protected Route
const ProtectedRoute = ({ children, allowedRoles }) => {
  const { user, loading, isAuthenticated } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
        <div className="spinner"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/auth" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user?.role)) {
    return <Navigate to="/" replace />;
  }

  return children;
};


// ==================== AUTHENTICATED LAYOUT ====================
// Shows sidebar on ALL pages when user is logged in
function AuthenticatedLayout({ children }) {
  const { user, isAuthenticated } = useAuth();
  
  if (!isAuthenticated || !user) {
    return children;
  }

  const role = user.role;
  if (role === "admin") return children;
  
  return (
    <div className="min-h-screen bg-[#0A0A0A] flex">
      <AuthSidebar role={role} />
      <main className="flex-1 ml-0 lg:ml-64 pt-16 lg:pt-0">
        {children}
      </main>
    </div>
  );
}


// ==================== AUTH NOTIFICATION DROPDOWN ====================
function AuthNotificationDropdown({ badges, token, role, prefix }) {
  const [open, setOpen] = React.useState(false);
  const [localBadges, setLocalBadges] = React.useState(badges);
  const [notifications, setNotifications] = React.useState([]);
  const [loading, setLoading] = React.useState(false);
  const dropdownRef = React.useRef(null);
  const buttonRef = React.useRef(null);

  React.useEffect(() => { setLocalBadges(badges); }, [badges]);

  // Load actual notifications when dropdown opens
  React.useEffect(() => {
    if (!open || !token) return;
    const loadNotifications = async () => {
      setLoading(true);
      try {
        const r = await axios.get(`${API}/event-notifications?limit=10`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setNotifications(r.data || []);
      } catch (e) { 
        console.error(e);
        setNotifications([]);
      } finally {
        setLoading(false);
      }
    };
    loadNotifications();
  }, [open, token]);

  React.useEffect(() => {
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

  const handleReadAll = async () => {
    const zeroed = {};
    Object.keys(localBadges).forEach(k => zeroed[k] = 0);
    setLocalBadges(zeroed);
    setNotifications([]);
    setOpen(false);
    try {
      await axios.post(`${API}/event-notifications/mark-read`, { all: true }, { headers: { Authorization: `Bearer ${token}` } });
    } catch (e) { console.error(e); }
  };

  const getIcon = (type) => {
    if (type?.includes('new_trade') || type === 'trade_created') return '📈';
    if (type?.includes('cancelled') || type?.includes('cancel')) return '❌';
    if (type?.includes('completed') || type?.includes('complete')) return '✅';
    if (type?.includes('payment') || type?.includes('paid')) return '💰';
    if (type?.includes('dispute')) return '⚠️';
    if (type?.includes('message')) return '💬';
    return '🔔';
  };

  const formatTime = (dateStr) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const now = new Date();
    const diff = (now - date) / 1000 / 60;
    if (diff < 1) return 'только что';
    if (diff < 60) return `${Math.floor(diff)} мин`;
    if (diff < 1440) return `${Math.floor(diff / 60)} ч`;
    return `${Math.floor(diff / 1440)} д`;
  };

  const total = localBadges.event_notifications || localBadges.total || 0;

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
      {open && ReactDOM.createPortal(
        <div ref={dropdownRef} style={{position: "fixed", top: getDropdownPos().top, left: getDropdownPos().left, zIndex: 99999, minWidth: "320px", width: "360px"}} className="bg-[#1A1A1A] border border-white/10 rounded-xl shadow-2xl overflow-hidden">
          <div className="p-3 border-b border-white/5">
            <div className="text-xs font-medium text-white">Оповещения</div>
          </div>
          <div className="max-h-96 overflow-y-auto">
            {loading ? (
              <div className="p-4 text-center text-xs text-[#52525B]">Загрузка...</div>
            ) : notifications.length === 0 ? (
              <div className="p-4 text-center text-xs text-[#52525B]">Нет оповещений</div>
            ) : (
              notifications.map((notif, idx) => (
                <div
                  key={notif.id || idx}
                  className="px-4 py-3 hover:bg-white/5 transition-colors border-b border-white/5 last:border-0 flex items-start gap-3"
                >
                  <span className="text-lg flex-shrink-0">{getIcon(notif.type)}</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-white font-medium truncate">{notif.title || notif.message?.split(' ').slice(0, 3).join(' ')}</div>
                    <div className="text-xs text-[#71717A] truncate">{notif.message}</div>
                  </div>
                  <span className="text-[10px] text-[#52525B] flex-shrink-0">{formatTime(notif.created_at)}</span>
                </div>
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

function AuthSidebar({ role }) {
  const { user, token, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarBadges, setSidebarBadges] = useState({});

  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    const fetchBadges = async () => {
      try {
        const response = await axios.get(`${API}/notifications/sidebar-badges`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setSidebarBadges(response.data);
      } catch (error) {
        console.error("Failed to fetch sidebar badges:", error);
      }
    };
    if (token) {
      fetchBadges();
      const interval = setInterval(fetchBadges, 30000);
      return () => clearInterval(interval);
    }
  }, [token]);

  const isActive = (path) => {
    if (path === "/") return location.pathname === "/";
    return location.pathname === path || location.pathname.startsWith(path + "/");
  };

  const prefix = role === "merchant" ? "/merchant" : "/trader";

  const navItems = [
    { label: "Главная", path: "/", icon: "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" },
    { label: "Личный кабинет", path: prefix, icon: "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" },
    { label: "Купить USDT", path: "/buy-crypto", icon: "M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" },
    { label: "Маркет", path: "/marketplace", icon: "M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z", badge: sidebarBadges.purchases },
    { label: "Форум", path: "/forum", icon: "M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0 01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z" },
  ];

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  return (
    <>
      {/* Mobile Header */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-40 bg-[#0A0A0A] border-b border-white/5 px-4 py-3 flex items-center justify-between">
        <button onClick={() => setSidebarOpen(true)} className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center text-white">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="18" y2="18"/></svg>
        </button>
        <Link to="/" className="flex items-center gap-2">
          <img src="/logo.png" alt="Reptiloid" className="h-8 w-8" />
          <span className="text-white font-medium text-sm">{user?.nickname || user?.merchant_name || user?.login}</span>
        </Link>
        <Link to={prefix} className="text-[#7C3AED] font-medium text-sm font-mono">
          {(user?.balance_usdt || 0).toFixed(2)}
        </Link>
      </div>

      {/* Mobile Overlay */}
      {sidebarOpen && (
        <div className="lg:hidden fixed inset-0 bg-black/60 z-40" onClick={() => setSidebarOpen(false)} />
      )}

      {/* Sidebar */}
      <aside className={`w-64 bg-[#0A0A0A] border-r border-white/5 flex flex-col h-screen fixed top-0 z-50 transform transition-transform duration-200 ease-in-out ${sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}`}>
        {/* Logo */}
        <div className="p-4 border-b border-white/5 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3">
            <img src="/logo.png" alt="Reptiloid" className="h-9 w-9" />
            <div>
              <div className="text-white font-bold">Reptiloid</div>
              <div className="text-[10px] text-[#7C3AED] font-medium uppercase">{role === "merchant" ? "Merchant" : "Trader"}</div>
            </div>
          </Link>
          <button onClick={() => setSidebarOpen(false)} className="lg:hidden w-8 h-8 rounded-lg hover:bg-white/5 flex items-center justify-center text-[#71717A]">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/></svg>
          </button>
        </div>

        {/* Balance */}
        <div className="p-4 border-b border-white/5">
          <div className="bg-gradient-to-br from-[#7C3AED]/20 to-[#A855F7]/10 border border-[#7C3AED]/30 rounded-xl p-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-[#A78BFA]">Доступно</span>
              <AuthNotificationDropdown badges={sidebarBadges} token={token} role={role} prefix={prefix} />
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-xl font-bold text-white font-mono">{((user?.balance_usdt || 0) - (user?.frozen_usdt || 0)).toFixed(2)}</span>
              <span className="text-sm text-[#71717A]">USDT</span>
            </div>
            {(user?.frozen_usdt || 0) > 0 && (
              <div className="text-xs text-yellow-500 mt-1">
                +{(user?.frozen_usdt || 0).toFixed(2)} заморожено
              </div>
            )}
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl transition-colors ${
                isActive(item.path)
                  ? "bg-[#7C3AED]/10 text-[#A78BFA]"
                  : "text-[#A1A1AA] hover:bg-white/5 hover:text-white"
              }`}
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d={item.icon} />
              </svg>
              <span className="text-sm font-medium">{item.label}</span>
              {item.badge > 0 && (
                <span className="ml-auto bg-[#EF4444] text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center">
                  {item.badge > 99 ? "99+" : item.badge}
                </span>
              )}
            </Link>
          ))}
        </nav>

        {/* User Info */}
        <div className="p-4 border-t border-white/5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 bg-[#7C3AED]/10 rounded-xl flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-[#A78BFA]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-white text-sm font-medium truncate">{user?.nickname || user?.merchant_name || user?.login}</div>
              <div className="text-[10px] text-[#7C3AED]">{role === "merchant" ? "Мерчант" : "Трейдер"}</div>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl border border-white/10 text-[#71717A] hover:text-white hover:bg-white/5 transition-colors text-sm"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            Выйти
          </button>
        </div>
      </aside>
    </>
  );
}

function App() {
  const [maintenanceMode, setMaintenanceMode] = useState(false);
  const [maintenanceMessage, setMaintenanceMessage] = useState("");
  const [checkingMaintenance, setCheckingMaintenance] = useState(true);

  // Check maintenance mode on app load
  useEffect(() => {
    const checkMaintenance = async () => {
      try {
        const response = await axios.get(`${API}/maintenance-status`);
        if (response.data?.maintenance) {
          setMaintenanceMode(true);
          setMaintenanceMessage(response.data.message || "Ведутся технические работы");
        }
      } catch (error) {
        // If error is 503 with maintenance flag, show maintenance page
        if (error.response?.status === 503 && error.response?.data?.maintenance) {
          setMaintenanceMode(true);
          setMaintenanceMessage(error.response.data.message || "Ведутся технические работы");
        }
      } finally {
        setCheckingMaintenance(false);
      }
    };
    
    checkMaintenance();
    
    // Re-check every 30 seconds
    const interval = setInterval(checkMaintenance, 30000);
    return () => clearInterval(interval);
  }, []);

  // Show loading while checking maintenance
  if (checkingMaintenance) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
        <div className="spinner"></div>
      </div>
    );
  }

  // Show maintenance page if in maintenance mode
  if (maintenanceMode) {
    return <MaintenancePage message={maintenanceMessage} />;
  }

  return (
    <AuthProvider>
      <div className="app-container">
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<AuthenticatedLayout><Landing /></AuthenticatedLayout>} />
            <Route path="/auth" element={<Auth />} />
            <Route path="/register" element={<Auth />} />
            <Route path="/login" element={<Auth />} />
            <Route path="/forum" element={<AuthenticatedLayout><Forum /></AuthenticatedLayout>} />
            <Route path="/buy-crypto" element={<AuthenticatedLayout><BuyCrypto /></AuthenticatedLayout>} />
            <Route path="/marketplace" element={<AuthenticatedLayout><Marketplace /></AuthenticatedLayout>} />
            <Route path="/marketplace/shop/:shopId" element={<AuthenticatedLayout><ShopPage /></AuthenticatedLayout>} />
            <Route path="/marketplace/product/:productId" element={<AuthenticatedLayout><ProductPage /></AuthenticatedLayout>} />
            <Route path="/merchant/register" element={<MerchantRegister />} />
            <Route path="/pay/:linkId" element={<PayPage />} />
            <Route path="/deposit/:linkId" element={<DepositPage />} />
            <Route path="/trade/:tradeId" element={<TradePage />} />
            <Route path="/dispute/:tradeId" element={<PublicDisputePage />} />
            <Route path="/select-operator/:invoiceId" element={<SelectOperatorPage />} />
            <Route path="/qr-provider" element={<QRProviderDashboard />} />
            <Route path="/demo" element={<DemoShop />} />
            <Route path="/docs" element={<ApiDocs />} />
            <Route path="/buy/:offerId" element={<DirectBuyPage />} />
            <Route 
              path="/referrals" 
              element={
                <ProtectedRoute allowedRoles={["trader", "merchant"]}>
                  <Referrals />
                </ProtectedRoute>
              } 
            />
            <Route
              path="/trader/*"
              element={
                <ProtectedRoute allowedRoles={["trader"]}>
                  <TraderDashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/merchant/*"
              element={
                <ProtectedRoute allowedRoles={["merchant"]}>
                  <MerchantDashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/*"
              element={
                <ProtectedRoute allowedRoles={["admin"]}>
                  <AdminPanel />
                </ProtectedRoute>
              }
            />
          </Routes>
        </BrowserRouter>
        <Toaster position="top-right" richColors />
      </div>
    </AuthProvider>
  );
}

export default App;
