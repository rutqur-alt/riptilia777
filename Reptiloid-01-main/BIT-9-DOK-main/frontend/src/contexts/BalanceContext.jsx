import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/auth';
import { useAuth } from '@/lib/auth';

const BalanceContext = createContext(null);

export const BalanceProvider = ({ children }) => {
  const { user } = useAuth();
  const [traderBalance, setTraderBalance] = useState(null);
  const [merchantBalance, setMerchantBalance] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  // Fetch trader balance
  const fetchTraderBalance = useCallback(async () => {
    if (user?.role !== 'trader') return;
    
    try {
      const res = await api.get('/trader/balance');
      setTraderBalance(res.data);
      setLastUpdate(Date.now());
    } catch (error) {
      console.error('Error fetching trader balance:', error);
    }
  }, [user?.role]);

  // Fetch merchant balance
  const fetchMerchantBalance = useCallback(async () => {
    if (user?.role !== 'merchant') return;
    
    try {
      const res = await api.get('/merchant/balance');
      setMerchantBalance({
        available: res.data.available_usdt || 0,
        pending: res.data.pending_usdt || 0,
        locked: res.data.locked_usdt || 0,
      });
      setLastUpdate(Date.now());
    } catch (error) {
      console.error('Error fetching merchant balance:', error);
    }
  }, [user?.role]);

  // Refresh balance based on user role
  const refreshBalance = useCallback(async () => {
    if (user?.role === 'trader') {
      await fetchTraderBalance();
    } else if (user?.role === 'merchant') {
      await fetchMerchantBalance();
    }
  }, [user?.role, fetchTraderBalance, fetchMerchantBalance]);

  // Auto-refresh on mount and periodically
  useEffect(() => {
    if (!user) return;

    refreshBalance();
    
    // Refresh every 30 seconds (reduced from 10s to decrease server load)
    const interval = setInterval(refreshBalance, 30000);
    return () => clearInterval(interval);
  }, [user, refreshBalance]);

  // Expose method to trigger refresh from anywhere
  const triggerRefresh = useCallback(() => {
    // Immediately refresh
    refreshBalance();
  }, [refreshBalance]);

  const value = {
    traderBalance,
    merchantBalance,
    lastUpdate,
    refreshBalance: triggerRefresh,
  };

  return (
    <BalanceContext.Provider value={value}>
      {children}
    </BalanceContext.Provider>
  );
};

export const useBalance = () => {
  const context = useContext(BalanceContext);
  if (!context) {
    throw new Error('useBalance must be used within BalanceProvider');
  }
  return context;
};

export default BalanceContext;
