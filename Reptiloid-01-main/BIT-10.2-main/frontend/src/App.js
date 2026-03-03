import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/lib/auth";
import { BalanceProvider } from "@/contexts/BalanceContext";
import { Toaster } from "@/components/ui/sonner";
import PWAInstallPrompt from "@/components/PWAInstallPrompt";

// Pages
import LandingPage from "@/pages/LandingPage";
import LoginPage from "@/pages/LoginPage";
import RegisterPage from "@/pages/RegisterPage";
import TwoFactorPage from "@/pages/TwoFactorPage";
import TraderWorkspace from "@/pages/trader/Workspace";
import TraderPaymentDetails from "@/pages/trader/PaymentDetails";
import TraderAnalytics from "@/pages/trader/Analytics";
import TraderPendingApproval from "@/pages/trader/PendingApproval";
import MerchantOrders from "@/pages/merchant/Orders";
import MerchantAPI from "@/pages/merchant/API";
import MerchantStats from "@/pages/merchant/Stats";
import MerchantAnalytics from "@/pages/merchant/Analytics";
import AdminDashboard from "@/pages/admin/Dashboard";
import AdminUsers from "@/pages/admin/Users";
import AdminStaff from "@/pages/admin/Staff";
import AdminOrders from "@/pages/admin/Orders";
import AdminDisputes from "@/pages/admin/Disputes";
import AdminTickets from "@/pages/admin/Tickets";
import AdminFinances from "@/pages/admin/Finances";
import AdminSettings from "@/pages/admin/Settings";
import AdminNotifications from "@/pages/admin/Notifications";
import AdminAccounting from "@/pages/admin/Accounting";
import AdminMaintenance from "@/pages/admin/Maintenance";
import PaymentPage from "@/pages/PaymentPage";
// ShopPage removed - using DemoShop instead
import DisputeChat from "@/pages/DisputeChat";
import AccountSettings from "@/pages/AccountSettings";
import UnifiedFinances from "@/pages/UnifiedFinances";
import Referrals from "@/pages/Referrals";
import MaintenancePage from "@/pages/MaintenancePage";
import { TicketsList, TicketChat } from "@/pages/Support";
import MerchantPendingApproval from "@/pages/merchant/PendingApproval";
import PublicDispute from "@/pages/PublicDispute";
import DemoShop from "@/pages/DemoShop";

// Protected Route Component
const ProtectedRoute = ({ children, allowedRoles, allowPending = false }) => {
  const { user, loading } = useAuth();
  const [maintenanceChecked, setMaintenanceChecked] = React.useState(false);
  const [maintenanceActive, setMaintenanceActive] = React.useState(false);
  const navigate = React.useCallback((path) => window.location.href = path, []);
  
  // Check maintenance mode for traders/merchants
  React.useEffect(() => {
    const checkMaintenance = async () => {
      if (user && (user.role === 'trader' || user.role === 'merchant')) {
        try {
          const res = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/public/maintenance?role=${user.role}`);
          const data = await res.json();
          if (data.active) {
            localStorage.setItem('userRole', user.role);
            setMaintenanceActive(true);
          }
        } catch (e) {
          console.error('Maintenance check failed:', e);
        }
      }
      setMaintenanceChecked(true);
    };
    
    if (user) {
      checkMaintenance();
    } else {
      setMaintenanceChecked(true);
    }
  }, [user]);
  
  if (loading || !maintenanceChecked) {
    return (
      <div className="min-h-screen bg-[#09090B] flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full"></div>
      </div>
    );
  }
  
  // Redirect to maintenance page if active
  if (maintenanceActive) {
    return <Navigate to="/maintenance" replace />;
  }
  
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  
  // Check if trader or merchant is pending approval
  if ((user.role === 'trader' || user.role === 'merchant') && user.approval_status === 'pending' && !allowPending) {
    const pendingPath = user.role === 'trader' ? '/trader/pending' : '/merchant/pending';
    return <Navigate to={pendingPath} replace />;
  }
  
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    // Redirect to appropriate dashboard
    const dashboards = {
      trader: '/trader/workspace',
      merchant: '/merchant',
      admin: '/admin',
    };
    return <Navigate to={dashboards[user.role] || '/login'} replace />;
  }
  
  return children;
};

// Dashboard redirect based on role
const DashboardRedirect = () => {
  const { user, loading } = useAuth();
  
  if (loading) {
    return (
      <div className="min-h-screen bg-[#09090B] flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full"></div>
      </div>
    );
  }
  
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  
  // Check if trader or merchant is pending approval
  if ((user.role === 'trader' || user.role === 'merchant') && user.approval_status === 'pending') {
    const pendingPath = user.role === 'trader' ? '/trader/pending' : '/merchant/pending';
    return <Navigate to={pendingPath} replace />;
  }
  
  const dashboards = {
    trader: '/trader/workspace',
    merchant: '/merchant',
    admin: '/admin',
    support: '/admin',
  };
  
  return <Navigate to={dashboards[user.role] || '/login'} replace />;
};

function App() {
  return (
    <AuthProvider>
      <BalanceProvider>
        <BrowserRouter>
          <div className="min-h-screen bg-[#09090B]">
            <Routes>
            {/* Public Routes - no gate verification needed */}
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/two-factor" element={<TwoFactorPage />} />
            <Route path="/pay/:orderId" element={<PaymentPage />} />
            <Route path="/shop" element={<Navigate to="/demo" replace />} />
            <Route path="/demo" element={<DemoShop />} />
            
            {/* Публичная страница спора - БЕЗ проверки авторизации */}
            <Route path="/dispute/:id" element={<PublicDispute />} />
            
            {/* Dashboard Redirect */}
            <Route path="/dashboard" element={<DashboardRedirect />} />
            
            {/* Trader Routes */}
            <Route path="/trader/pending" element={
              <ProtectedRoute allowedRoles={['trader']} allowPending={true}>
                <TraderPendingApproval />
              </ProtectedRoute>
            } />
            <Route path="/trader" element={
              <Navigate to="/trader/workspace" replace />
            } />
            <Route path="/trader/workspace" element={
              <ProtectedRoute allowedRoles={['trader']}>
                <TraderWorkspace />
              </ProtectedRoute>
            } />
            <Route path="/trader/payment-details" element={
              <ProtectedRoute allowedRoles={['trader']}>
                <TraderPaymentDetails />
              </ProtectedRoute>
            } />
            <Route path="/trader/finances" element={
              <ProtectedRoute allowedRoles={['trader']}>
                <UnifiedFinances />
              </ProtectedRoute>
            } />
            <Route path="/trader/analytics" element={
              <ProtectedRoute allowedRoles={['trader']}>
                <TraderAnalytics />
              </ProtectedRoute>
            } />
            <Route path="/trader/disputes/:disputeId" element={
              <ProtectedRoute allowedRoles={['trader']}>
                <DisputeChat />
              </ProtectedRoute>
            } />
            
            {/* Merchant Routes */}
            <Route path="/merchant/pending" element={
              <ProtectedRoute allowedRoles={['merchant']} allowPending={true}>
                <MerchantPendingApproval />
              </ProtectedRoute>
            } />
            <Route path="/merchant" element={
              <ProtectedRoute allowedRoles={['merchant']}>
                <Navigate to="/merchant/orders" replace />
              </ProtectedRoute>
            } />
            <Route path="/merchant/orders" element={
              <ProtectedRoute allowedRoles={['merchant']}>
                <MerchantOrders />
              </ProtectedRoute>
            } />
            <Route path="/merchant/api" element={
              <ProtectedRoute allowedRoles={['merchant']}>
                <MerchantAPI />
              </ProtectedRoute>
            } />
            <Route path="/merchant/stats" element={
              <ProtectedRoute allowedRoles={['merchant']}>
                <MerchantStats />
              </ProtectedRoute>
            } />
            <Route path="/merchant/finances" element={
              <ProtectedRoute allowedRoles={['merchant']}>
                <UnifiedFinances />
              </ProtectedRoute>
            } />
            <Route path="/merchant/analytics" element={
              <ProtectedRoute allowedRoles={['merchant']}>
                <MerchantAnalytics />
              </ProtectedRoute>
            } />
            <Route path="/merchant/disputes/:disputeId" element={
              <ProtectedRoute allowedRoles={['merchant']}>
                <DisputeChat />
              </ProtectedRoute>
            } />
            
            {/* Account Settings - доступен для всех авторизованных */}
            <Route path="/settings" element={
              <ProtectedRoute allowedRoles={['trader', 'merchant', 'admin', 'support']} allowPending={true}>
                <AccountSettings />
              </ProtectedRoute>
            } />
            
            {/* Admin Routes */}
            <Route path="/admin" element={
              <ProtectedRoute allowedRoles={['admin', 'support']}>
                <AdminDashboard />
              </ProtectedRoute>
            } />
            <Route path="/admin/users" element={
              <ProtectedRoute allowedRoles={['admin', 'support']}>
                <AdminUsers />
              </ProtectedRoute>
            } />
            <Route path="/admin/staff" element={
              <ProtectedRoute allowedRoles={['admin']}>
                <AdminStaff />
              </ProtectedRoute>
            } />
            <Route path="/admin/orders" element={
              <ProtectedRoute allowedRoles={['admin', 'support']}>
                <AdminOrders />
              </ProtectedRoute>
            } />
            <Route path="/admin/disputes" element={
              <ProtectedRoute allowedRoles={['admin', 'support']}>
                <AdminDisputes />
              </ProtectedRoute>
            } />
            <Route path="/admin/disputes/:disputeId" element={
              <ProtectedRoute allowedRoles={['admin', 'support']}>
                <DisputeChat />
              </ProtectedRoute>
            } />
            <Route path="/admin/tickets" element={
              <ProtectedRoute allowedRoles={['admin', 'support']}>
                <AdminTickets />
              </ProtectedRoute>
            } />
            <Route path="/admin/finances" element={
              <ProtectedRoute allowedRoles={['admin']}>
                <AdminFinances />
              </ProtectedRoute>
            } />
            <Route path="/admin/accounting" element={
              <ProtectedRoute allowedRoles={['admin']}>
                <AdminAccounting />
              </ProtectedRoute>
            } />
            <Route path="/admin/settings" element={
              <ProtectedRoute allowedRoles={['admin']}>
                <AdminSettings />
              </ProtectedRoute>
            } />
            <Route path="/admin/notifications" element={
              <ProtectedRoute allowedRoles={['admin']}>
                <AdminNotifications />
              </ProtectedRoute>
            } />
            <Route path="/admin/maintenance" element={
              <ProtectedRoute allowedRoles={['admin']}>
                <AdminMaintenance />
              </ProtectedRoute>
            } />
            
            {/* Referrals - доступен для трейдеров и мерчантов */}
            <Route path="/referrals" element={
              <ProtectedRoute allowedRoles={['trader', 'merchant']}>
                <Referrals />
              </ProtectedRoute>
            } />
            
            {/* Maintenance Page - публичная */}
            <Route path="/maintenance" element={<MaintenancePage />} />
            
            {/* Support/Tickets - доступен для всех пользователей включая pending трейдеров */}
            <Route path="/support" element={
              <ProtectedRoute allowedRoles={['trader', 'merchant']} allowPending={true}>
                <TicketsList />
              </ProtectedRoute>
            } />
            <Route path="/support/:ticketId" element={
              <ProtectedRoute allowedRoles={['trader', 'merchant', 'admin', 'support']} allowPending={true}>
                <TicketChat />
              </ProtectedRoute>
            } />
            
            {/* 404 Redirect */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          <Toaster position="top-right" richColors />
        </div>
      </BrowserRouter>
      </BalanceProvider>
    </AuthProvider>
  );
}

export default App;
