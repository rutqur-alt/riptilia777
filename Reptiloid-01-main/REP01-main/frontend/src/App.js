import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
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
import TestShop from "@/pages/TestShop";
import TestCasino from "@/pages/TestCasino";
import ApiDocs from "@/pages/ApiDocs";
import DirectBuyPage from "@/pages/DirectBuyPage";
import Forum from "@/pages/Forum";
import Marketplace from "@/pages/Marketplace";
import ShopPage from "@/pages/ShopPage";
import ProductPage from "@/pages/ProductPage";
import MaintenancePage from "@/pages/MaintenancePage";
import BuyCrypto from "@/pages/BuyCrypto";

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
            <Route path="/" element={<Landing />} />
            <Route path="/auth" element={<Auth />} />
            <Route path="/forum" element={<Forum />} />
            <Route path="/buy-crypto" element={<BuyCrypto />} />
            <Route path="/marketplace" element={<Marketplace />} />
            <Route path="/marketplace/shop/:shopId" element={<ShopPage />} />
            <Route path="/marketplace/product/:productId" element={<ProductPage />} />
            <Route path="/merchant/register" element={<MerchantRegister />} />
            <Route path="/pay/:linkId" element={<PayPage />} />
            <Route path="/deposit/:linkId" element={<DepositPage />} />
            <Route path="/trade/:tradeId" element={<TradePage />} />
            <Route path="/shop" element={<TestShop />} />
            <Route path="/casino" element={<TestCasino />} />
            <Route path="/docs" element={<ApiDocs />} />
            <Route path="/buy/:offerId" element={<DirectBuyPage />} />
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
