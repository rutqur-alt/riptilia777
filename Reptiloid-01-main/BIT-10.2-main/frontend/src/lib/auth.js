import React, { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Create axios instance
const api = axios.create({
  baseURL: API,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401, 403 and 503 errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Don't clear tokens for network errors or timeouts
    if (!error.response) {
      console.warn('Network error - keeping session:', error.message);
      return Promise.reject(error);
    }
    
    // Public pages that should NEVER redirect
    const currentPath = window.location.pathname;
    const publicPaths = ['/pay/', '/dispute/', '/demo', '/login', '/register', '/'];
    const isPublicPage = publicPaths.some(path => 
      path === '/' ? currentPath === '/' : currentPath.startsWith(path)
    );
    
    // Handle maintenance mode (503)
    if (error.response?.status === 503 && error.response?.data?.maintenance) {
      if (!currentPath.includes('/maintenance') && !currentPath.includes('/login')) {
        window.location.replace('/maintenance');
      }
      return Promise.reject(error);
    }
    
    if (error.response?.status === 401) {
      // Skip redirect for public pages
      if (isPublicPage) {
        return Promise.reject(error);
      }
      
      // Only clear tokens if we actually have a token (prevents double-clear)
      const token = localStorage.getItem('token');
      if (token) {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        window.location.replace('/login');
      }
    }
    
    // Handle blocked user (403)
    if (error.response?.status === 403 && error.response?.data?.detail?.includes('заблокирован')) {
      // Skip for public pages
      if (isPublicPage) {
        return Promise.reject(error);
      }
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      alert('Ваш аккаунт был заблокирован. Обратитесь в поддержку.');
      window.location.replace('/login');
    }
    return Promise.reject(error);
  }
);

// Auth Context
const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Check user status periodically (every 30 seconds)
  // Note: This effect should NOT depend on 'user' to prevent infinite loops
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) return;

    const checkUserStatus = async () => {
      try {
        const res = await api.get('/auth/me');
        // If user is blocked, log them out
        if (!res.data.is_active) {
          localStorage.removeItem('token');
          localStorage.removeItem('user');
          setUser(null);
          alert('Ваш аккаунт был заблокирован. Обратитесь в поддержку.');
          window.location.href = '/login';
          return;
        }
        // Update user data including approval_status
        setUser(res.data);
        localStorage.setItem('user', JSON.stringify(res.data));
      } catch (error) {
        // 403 will be handled by interceptor
        console.error('Status check failed:', error);
      }
    };

    // Check immediately and then every 30 seconds
    checkUserStatus();
    const interval = setInterval(checkUserStatus, 30000);

    return () => clearInterval(interval);
  }, []); // Empty deps - runs once on mount, not on every user state change

  // Auto-refresh token every 6 hours to keep session alive
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) return;

    const refreshToken = async () => {
      try {
        const res = await api.post('/auth/refresh-token');
        if (res.data.token) {
          localStorage.setItem('token', res.data.token);
          console.log('Token refreshed successfully');
        }
      } catch (error) {
        console.error('Token refresh failed:', error);
      }
    };

    // Refresh token every 6 hours (21600000 ms)
    const interval = setInterval(refreshToken, 6 * 60 * 60 * 1000);

    // Also refresh on app visibility change (when user returns to tab)
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        const lastRefresh = localStorage.getItem('lastTokenRefresh');
        const now = Date.now();
        // Refresh if more than 1 hour since last refresh
        if (!lastRefresh || now - parseInt(lastRefresh) > 3600000) {
          refreshToken();
          localStorage.setItem('lastTokenRefresh', now.toString());
        }
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  useEffect(() => {
    const token = localStorage.getItem('token');
    const savedUser = localStorage.getItem('user');
    
    if (token && savedUser) {
      // Set user from localStorage first (instant UI)
      setUser(JSON.parse(savedUser));
      
      // Then verify token with backend
      api.get('/auth/me')
        .then(res => {
          setUser(res.data);
          localStorage.setItem('user', JSON.stringify(res.data));
        })
        .catch((error) => {
          // Only clear session on 401 (unauthorized), not on network errors
          if (error.response?.status === 401) {
            console.log('Token invalid - clearing session');
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            setUser(null);
          } else {
            // Network error or other issue - keep user logged in with cached data
            console.warn('Auth verification failed, keeping cached session:', error.message);
          }
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (loginStr, password, twoFactorCode = null, captchaToken = null) => {
    const payload = { login: loginStr, password };
    if (twoFactorCode) payload.two_factor_code = twoFactorCode;
    if (captchaToken) payload.captcha_token = captchaToken;
    
    const res = await api.post('/auth/login', payload);
    
    // Check if 2FA is required
    if (res.data.requires_2fa) {
      return res.data;
    }
    
    localStorage.setItem('token', res.data.token);
    
    const userRes = await api.get('/auth/me');
    setUser(userRes.data);
    localStorage.setItem('user', JSON.stringify(userRes.data));
    
    return res.data;
  };

  const register = async (loginStr, nickname, password, role, referralCode = null) => {
    const payload = { login: loginStr, nickname, password, role };
    if (referralCode) payload.referral_code = referralCode;
    
    const res = await api.post('/auth/register', payload);
    localStorage.setItem('token', res.data.token);
    
    const userRes = await api.get('/auth/me');
    setUser(userRes.data);
    localStorage.setItem('user', JSON.stringify(userRes.data));
    
    return res.data;
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, register, logout, loading, api }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

// Format helpers
export const formatBTC = (value) => {
  // Legacy - kept for compatibility
  return Number(value || 0).toFixed(2);
};

export const formatUSDT = (value) => {
  const num = Number(value || 0);
  // Корректируем очень маленькие значения (погрешность float)
  if (Math.abs(num) < 0.001) {
    return '0.00';
  }
  // For very small amounts, show more decimal places
  if (num > 0 && num < 0.01) {
    return num.toFixed(4);
  }
  return num.toFixed(2);
};

export const formatRUB = (value) => {
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value || 0);
};

export const formatDate = (dateString) => {
  if (!dateString) return '-';
  const date = new Date(dateString);
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

export const getStatusLabel = (status) => {
  const labels = {
    new: 'Новый',
    waiting_requisites: 'Ожидание реквизитов',
    waiting_buyer_confirmation: 'Ожидание оплаты',
    waiting_trader_confirmation: 'Ожидание подтверждения',
    paid: 'Оплачен',
    completed: 'Завершён',
    cancelled: 'Отменён',
    expired: 'Истёк',
    dispute: 'Спор',
    disputed: 'Спор',
    refunded: 'Возврат',
    open: 'Открыт',
    investigating: 'Расследование',
    resolved: 'Решён',
    pending: 'Ожидание',
    credited: 'Зачислен',
    approved: 'Одобрен',
    rejected: 'Отклонён',
  };
  return labels[status] || status;
};

export const getStatusClass = (status) => {
  const classes = {
    new: 'status-new',
    waiting_requisites: 'status-waiting',
    waiting_buyer_confirmation: 'status-waiting',
    waiting_trader_confirmation: 'status-pending',
    paid: 'status-completed',
    completed: 'status-completed',
    cancelled: 'status-cancelled',
    expired: 'status-cancelled',
    dispute: 'status-dispute',
    disputed: 'status-dispute',
    open: 'status-pending',
    resolved: 'status-completed',
    pending: 'status-waiting',
    credited: 'status-completed',
    approved: 'status-completed',
    rejected: 'status-cancelled',
  };
  return classes[status] || 'status-waiting';
};

export { api, API, BACKEND_URL };
