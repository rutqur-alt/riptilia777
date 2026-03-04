import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useAuth, API } from '@/App';
import axios from 'axios';
import { toast } from 'sonner';
import { 
  Wallet, ArrowDownCircle, ArrowUpCircle, Clock, CheckCircle, XCircle,
  Copy, RefreshCw, TrendingUp, TrendingDown, AlertTriangle, Search,
  Shield, Activity, Users, Download, Eye, Check, X, FileText, Settings,
  PlusCircle, MinusCircle, ExternalLink, BarChart3
} from 'lucide-react';

const formatUSDT = (amount) => {
  const num = parseFloat(amount) || 0;
  return `${num.toFixed(2)} USDT`;
};

const formatDate = (dateStr) => {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
};

/**
 * Admin Finance Dashboard - Full Version
 */
export default function AdminFinancePage() {
  const { token, user } = useAuth();
  const [analytics, setAnalytics] = useState(null);
  const [fullAnalytics, setFullAnalytics] = useState(null);
  const [hotWallet, setHotWallet] = useState(null);
  const [pendingWithdrawals, setPendingWithdrawals] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [topTraders, setTopTraders] = useState([]);
  const [topMerchants, setTopMerchants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState('7d');
  
  // Search
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  
  // Wallet management
  const [showWalletModal, setShowWalletModal] = useState(false);
  const [walletHistory, setWalletHistory] = useState([]);
  const [newWalletAddress, setNewWalletAddress] = useState('');
  const [newWalletMnemonic, setNewWalletMnemonic] = useState('');
  
  // Balance adjustment
  const [showAdjustModal, setShowAdjustModal] = useState(false);
  const [adjustAmount, setAdjustAmount] = useState('');
  const [adjustReason, setAdjustReason] = useState('');

  const isAdmin = user?.admin_role === 'owner' || user?.admin_role === 'admin';

  useEffect(() => {
    fetchData();
  }, [period]);

  const fetchData = async () => {
    setLoading(true);
    const headers = { Authorization: `Bearer ${token}` };
    
    // Запускаем ВСЕ запросы параллельно для максимальной скорости
    const requests = [
      axios.get(`${API}/admin/finance/analytics`, { headers }).catch(() => ({ data: { analytics: null } })),
      axios.get(`${API}/admin/finance/pending-withdrawals`, { headers }).catch(() => ({ data: { pending_withdrawals: [] } })),
      axios.get(`${API}/admin/analytics/full?period=${period}`, { headers }).catch(() => ({ data: { analytics: null } })),
    ];
    
    // Добавляем admin-only запросы
    if (isAdmin) {
      requests.push(
        axios.get(`${API}/admin/finance/hot-wallet`, { headers }).catch(() => ({ data: { hot_wallet: null } })),
        axios.get(`${API}/admin/finance/audit-logs?limit=50`, { headers }).catch(() => ({ data: { logs: [] } })),
        axios.get(`${API}/admin/analytics/top-traders?limit=10`, { headers }).catch(() => ({ data: { traders: [] } })),
        axios.get(`${API}/admin/analytics/top-merchants?limit=10`, { headers }).catch(() => ({ data: { merchants: [] } }))
      );
    }
    
    try {
      const results = await Promise.all(requests);
      
      // Устанавливаем данные по мере получения
      setAnalytics(results[0].data.analytics);
      setPendingWithdrawals(results[1].data.pending_withdrawals || []);
      setFullAnalytics(results[2].data.analytics);
      
      if (isAdmin && results.length > 3) {
        setHotWallet(results[3].data.hot_wallet);
        setAuditLogs(results[4].data.logs || []);
        setTopTraders(results[5].data.traders || []);
        setTopMerchants(results[6].data.merchants || []);
      }
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  const searchUsers = async () => {
    if (!searchQuery.trim()) return;
    
    setSearchLoading(true);
    try {
      const res = await axios.get(`${API}/admin/users/search?query=${encodeURIComponent(searchQuery)}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSearchResults(res.data.users || []);
    } catch (error) {
      toast.error('Ошибка поиска');
    } finally {
      setSearchLoading(false);
    }
  };

  const selectUser = async (userId) => {
    try {
      const res = await axios.get(`${API}/admin/users/${userId}/details`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSelectedUser(res.data);
    } catch (error) {
      toast.error('Ошибка загрузки данных пользователя');
    }
  };

  const copyToClipboard = (text, label = 'ID') => {
    navigator.clipboard.writeText(text);
    toast.success(`${label} скопирован`);
  };

  const approveWithdrawal = async (txId) => {
    try {
      await axios.post(`${API}/admin/finance/approve-withdrawal/${txId}`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Вывод одобрен');
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка');
    }
  };

  const rejectWithdrawal = async (txId) => {
    const reason = prompt('Причина отклонения:');
    if (!reason) return;
    
    try {
      await axios.post(`${API}/admin/finance/reject-withdrawal/${txId}?reason=${encodeURIComponent(reason)}`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Вывод отклонён');
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка');
    }
  };

  const adjustBalance = async () => {
    if (!selectedUser || !adjustAmount || !adjustReason) {
      toast.error('Заполните все поля');
      return;
    }
    
    try {
      await axios.post(`${API}/admin/users/adjust-balance`, {
        user_id: selectedUser.user.id,
        amount: parseFloat(adjustAmount),
        reason: adjustReason
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      toast.success('Баланс изменен');
      setShowAdjustModal(false);
      setAdjustAmount('');
      setAdjustReason('');
      selectUser(selectedUser.user.id);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка');
    }
  };

  const changeWallet = async () => {
    if (!newWalletAddress || !newWalletMnemonic) {
      toast.error('Заполните все поля');
      return;
    }
    
    if (!confirm('Вы уверены? Это критическая операция!')) return;
    
    try {
      const res = await axios.post(`${API}/admin/wallet/change`, {
        new_address: newWalletAddress,
        new_mnemonic: newWalletMnemonic,
        confirm: true
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      toast.success(res.data.message);
      setShowWalletModal(false);
      setNewWalletAddress('');
      setNewWalletMnemonic('');
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка');
    }
  };

  const generateWallet = async () => {
    if (!confirm('Сгенерировать новый кошелек?')) return;
    
    try {
      const res = await axios.post(`${API}/admin/wallet/generate`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      toast.success(res.data.message);
      alert(`Новый адрес: ${res.data.wallet.address}\n\nМнемоника сохранена в файл на сервере.`);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="animate-spin w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  const overview = fullAnalytics?.overview || {};
  const periodStats = fullAnalytics?.period_stats || {};
  const dailyStats = fullAnalytics?.daily_stats || [];

  return (
    <div className="space-y-6 pb-10" data-testid="admin-finance-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Финансовый дашборд</h1>
          <p className="text-zinc-400 text-sm">Полная аналитика и управление средствами</p>
        </div>
        <div className="flex items-center gap-2">
          {/* Period selector */}
          <div className="flex gap-1 bg-zinc-900 rounded-lg p-1">
            {['1d', '7d', '30d', '90d'].map(p => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-3 py-1 rounded text-sm transition-colors ${
                  period === p ? 'bg-emerald-500/20 text-emerald-400' : 'text-zinc-400 hover:text-white'
                }`}
              >
                {p === '1d' ? 'День' : p === '7d' ? 'Неделя' : p === '30d' ? 'Месяц' : 'Квартал'}
              </button>
            ))}
          </div>
          <Button onClick={fetchData} variant="outline" size="sm">
            <RefreshCw className="w-4 h-4 mr-2" />
            Обновить
          </Button>
        </div>
      </div>

      {/* Main Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Hot Wallet */}
        <Card className="bg-gradient-to-br from-blue-600 to-blue-800 border-0">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-blue-100 text-sm">Кошелёк биржи (Hot Wallet)</p>
                <p className="text-2xl font-bold text-white font-mono mt-1">
                  {formatUSDT(overview.hot_wallet_balance)}
                </p>
              </div>
              <Wallet className="w-10 h-10 text-blue-300/50" />
            </div>
          </CardContent>
        </Card>

        {/* Traders Balance */}
        <Card className="bg-gradient-to-br from-purple-600 to-purple-800 border-0">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-purple-100 text-sm">Долг трейдерам</p>
                <p className="text-2xl font-bold text-white font-mono mt-1">
                  {formatUSDT(overview.traders_balance)}
                </p>
                <p className="text-purple-200 text-xs mt-1">{fullAnalytics?.users?.traders_count || 0} трейдеров</p>
              </div>
              <Users className="w-10 h-10 text-purple-300/50" />
            </div>
          </CardContent>
        </Card>

        {/* Merchants Balance */}
        <Card className="bg-gradient-to-br from-orange-600 to-orange-800 border-0">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-orange-100 text-sm">Долг мерчантам</p>
                <p className="text-2xl font-bold text-white font-mono mt-1">
                  {formatUSDT(overview.merchants_balance)}
                </p>
                <p className="text-orange-200 text-xs mt-1">{fullAnalytics?.users?.merchants_count || 0} мерчантов</p>
              </div>
              <Users className="w-10 h-10 text-orange-300/50" />
            </div>
          </CardContent>
        </Card>

        {/* Platform Profit / Health */}
        <Card className={`border-0 ${overview.is_healthy ? 'bg-gradient-to-br from-emerald-600 to-emerald-800' : 'bg-gradient-to-br from-red-600 to-red-800'}`}>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-white/80 text-sm">
                  {overview.platform_profit >= 0 ? 'Прибыль платформы' : 'ДЕФИЦИТ!'}
                </p>
                <p className="text-2xl font-bold text-white font-mono mt-1">
                  {formatUSDT(Math.abs(overview.platform_profit || 0))}
                </p>
                <p className="text-white/60 text-xs mt-1">Reserve: {overview.reserve_ratio?.toFixed(1)}%</p>
              </div>
              {overview.is_healthy ? (
                <CheckCircle className="w-10 h-10 text-emerald-300/50" />
              ) : (
                <AlertTriangle className="w-10 h-10 text-red-300/50" />
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Period Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="pt-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-emerald-500/10">
                <BarChart3 className="w-5 h-5 text-emerald-400" />
              </div>
              <div>
                <p className="text-xs text-zinc-500">Объём ({period})</p>
                <p className="text-lg font-bold text-white">{formatUSDT(periodStats.total_volume)}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="pt-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-blue-500/10">
                <Activity className="w-5 h-5 text-blue-400" />
              </div>
              <div>
                <p className="text-xs text-zinc-500">Сделок ({period})</p>
                <p className="text-lg font-bold text-white">{periodStats.total_trades || 0}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="pt-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-yellow-500/10">
                <TrendingUp className="w-5 h-5 text-yellow-400" />
              </div>
              <div>
                <p className="text-xs text-zinc-500">Комиссии ({period})</p>
                <p className="text-lg font-bold text-emerald-400">{formatUSDT(periodStats.total_fees_usdt)}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="pt-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-red-500/10">
                <Clock className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <p className="text-xs text-zinc-500">Ожидают вывода</p>
                <p className="text-lg font-bold text-white">{fullAnalytics?.pending?.withdrawals_count || 0}</p>
                <p className="text-xs text-zinc-500">{formatUSDT(fullAnalytics?.pending?.withdrawals_amount)}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Chart */}
      {dailyStats.length > 0 && (
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-lg">Объём торгов по дням</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-40 flex items-end gap-1">
              {dailyStats.map((day, i) => {
                const maxVolume = Math.max(...dailyStats.map(d => d.volume || 0), 1);
                const height = Math.max(4, (day.volume / maxVolume) * 100);
                return (
                  <div key={i} className="flex-1 flex flex-col items-center gap-1">
                    <div className="text-xs text-zinc-500">{day.trades}</div>
                    <div 
                      className="w-full bg-emerald-500/30 hover:bg-emerald-500/50 rounded-t transition-colors cursor-pointer"
                      style={{ height: `${height}%` }}
                      title={`${formatUSDT(day.volume)} (${day.trades} сделок)`}
                    />
                    <span className="text-[10px] text-zinc-500">{day.date?.slice(5)}</span>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tabs */}
      <Tabs defaultValue="withdrawals" className="space-y-4">
        <TabsList className="bg-zinc-900">
          <TabsTrigger value="withdrawals">Заявки на вывод</TabsTrigger>
          <TabsTrigger value="search">Поиск пользователя</TabsTrigger>
          <TabsTrigger value="top">Топ пользователей</TabsTrigger>
          {isAdmin && <TabsTrigger value="wallet">Управление кошельком</TabsTrigger>}
          <TabsTrigger value="audit">Аудит</TabsTrigger>
        </TabsList>

        {/* Withdrawals Tab */}
        <TabsContent value="withdrawals">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="w-5 h-5 text-yellow-400" />
                Заявки на вывод (требуют одобрения)
              </CardTitle>
            </CardHeader>
            <CardContent>
              {pendingWithdrawals.length === 0 ? (
                <p className="text-zinc-500 text-center py-8">Нет заявок, ожидающих одобрения</p>
              ) : (
                <div className="space-y-3">
                  {pendingWithdrawals.map((w) => (
                    <div key={w.id} className="flex items-center justify-between p-3 bg-zinc-800 rounded-lg">
                      <div>
                        <p className="text-white font-mono">{formatUSDT(w.amount)}</p>
                        <p className="text-xs text-zinc-500">
                          User: {w.user_id?.slice(0, 8)}... → {w.to_address?.slice(0, 16)}...
                        </p>
                        <p className="text-xs text-zinc-600">{formatDate(w.created_at)}</p>
                      </div>
                      <div className="flex gap-2">
                        <Button size="sm" variant="outline" className="text-emerald-400 border-emerald-400/50"
                          onClick={() => approveWithdrawal(w.id)}>
                          <Check className="w-4 h-4" />
                        </Button>
                        <Button size="sm" variant="outline" className="text-red-400 border-red-400/50"
                          onClick={() => rejectWithdrawal(w.id)}>
                          <X className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Search Tab */}
        <TabsContent value="search">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Search className="w-5 h-5" />
                Поиск пользователя
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Input
                  placeholder="ID пользователя, логин или никнейм..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && searchUsers()}
                  className="bg-zinc-800 border-zinc-700"
                />
                <Button onClick={searchUsers} disabled={searchLoading}>
                  {searchLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                </Button>
              </div>

              {/* Search Results */}
              {searchResults.length > 0 && (
                <div className="border border-zinc-800 rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-zinc-800">
                      <tr>
                        <th className="px-4 py-2 text-left text-zinc-400">ID</th>
                        <th className="px-4 py-2 text-left text-zinc-400">Логин</th>
                        <th className="px-4 py-2 text-left text-zinc-400">Роль</th>
                        <th className="px-4 py-2 text-right text-zinc-400">Баланс</th>
                        <th className="px-4 py-2 text-center text-zinc-400">Действия</th>
                      </tr>
                    </thead>
                    <tbody>
                      {searchResults.map((u) => (
                        <tr key={u.id} className="border-t border-zinc-800 hover:bg-zinc-800/50">
                          <td className="px-4 py-2">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-xs text-zinc-400">{u.id?.slice(0, 8)}...</span>
                              <button onClick={() => copyToClipboard(u.id)} className="text-zinc-500 hover:text-white">
                                <Copy className="w-3 h-3" />
                              </button>
                            </div>
                          </td>
                          <td className="px-4 py-2 text-white">{u.login || u.nickname}</td>
                          <td className="px-4 py-2">
                            <span className={`px-2 py-0.5 rounded text-xs ${
                              u.role === 'trader' ? 'bg-blue-500/20 text-blue-400' : 'bg-purple-500/20 text-purple-400'
                            }`}>
                              {u.role === 'trader' ? 'Трейдер' : 'Мерчант'}
                            </span>
                          </td>
                          <td className="px-4 py-2 text-right font-mono text-emerald-400">
                            {formatUSDT(u.balance_usdt)}
                          </td>
                          <td className="px-4 py-2 text-center">
                            <Button size="sm" variant="ghost" onClick={() => selectUser(u.id)}>
                              <Eye className="w-4 h-4" />
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Selected User Details */}
              {selectedUser && (
                <div className="mt-4 p-4 bg-zinc-800 rounded-lg space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-lg font-bold text-white">
                        {selectedUser.user.nickname || selectedUser.user.login}
                      </h3>
                      <p className="text-xs text-zinc-500 font-mono">{selectedUser.user.id}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-1 rounded text-xs ${
                        selectedUser.user.role === 'trader' ? 'bg-blue-500/20 text-blue-400' : 'bg-purple-500/20 text-purple-400'
                      }`}>
                        {selectedUser.user.role === 'trader' ? 'Трейдер' : 'Мерчант'}
                      </span>
                      <Button size="sm" variant="ghost" onClick={() => copyToClipboard(selectedUser.user.id)}>
                        <Copy className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-4">
                    <div className="bg-zinc-900 p-3 rounded">
                      <p className="text-xs text-zinc-500">Баланс</p>
                      <p className="text-xl font-bold text-emerald-400 font-mono">
                        {formatUSDT(selectedUser.user.balance_usdt)}
                      </p>
                    </div>
                    <div className="bg-zinc-900 p-3 rounded">
                      <p className="text-xs text-zinc-500">Сделок</p>
                      <p className="text-xl font-bold text-white">
                        {(selectedUser.user.salesCount || 0) + (selectedUser.user.purchasesCount || 0)}
                      </p>
                    </div>
                    <div className="bg-zinc-900 p-3 rounded">
                      <p className="text-xs text-zinc-500">Регистрация</p>
                      <p className="text-sm text-white">{formatDate(selectedUser.user.created_at)}</p>
                    </div>
                  </div>

                  {/* Admin Actions */}
                  {isAdmin && (
                    <div className="flex gap-2 pt-2 border-t border-zinc-700">
                      <Button size="sm" variant="outline" onClick={() => setShowAdjustModal(true)}>
                        <PlusCircle className="w-4 h-4 mr-2" />
                        Корректировка баланса
                      </Button>
                    </div>
                  )}

                  {/* Recent Trades */}
                  {selectedUser.recent_trades?.length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold text-zinc-400 mb-2">Последние сделки</h4>
                      <div className="space-y-1 max-h-48 overflow-y-auto">
                        {selectedUser.recent_trades.slice(0, 5).map((t, i) => (
                          <div key={i} className="flex justify-between text-xs p-2 bg-zinc-900 rounded">
                            <span className="text-zinc-400">{formatDate(t.created_at)}</span>
                            <span className="text-white">{formatUSDT(t.amount_usdt)}</span>
                            <span className={t.status === 'completed' ? 'text-emerald-400' : 'text-yellow-400'}>
                              {t.status}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Top Users Tab */}
        <TabsContent value="top">
          <div className="grid md:grid-cols-2 gap-4">
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <CardTitle className="text-lg">Топ-10 трейдеров</CardTitle>
              </CardHeader>
              <CardContent>
                {topTraders.length === 0 ? (
                  <p className="text-zinc-500 text-center py-4">Нет данных</p>
                ) : (
                  <div className="space-y-2">
                    {topTraders.map((t, i) => (
                      <div key={t.id} className="flex items-center justify-between p-2 bg-zinc-800 rounded">
                        <div className="flex items-center gap-3">
                          <span className="w-6 h-6 flex items-center justify-center bg-zinc-700 rounded text-xs">
                            {i + 1}
                          </span>
                          <div>
                            <p className="text-white text-sm">{t.nickname || t.login}</p>
                            <p className="text-xs text-zinc-500">{(t.salesCount || 0) + (t.purchasesCount || 0)} сделок</p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-emerald-400 font-mono text-sm">{formatUSDT(t.balance_usdt)}</p>
                          <button onClick={() => copyToClipboard(t.id)} className="text-xs text-zinc-500 hover:text-white">
                            Копировать ID
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <CardTitle className="text-lg">Топ-10 мерчантов</CardTitle>
              </CardHeader>
              <CardContent>
                {topMerchants.length === 0 ? (
                  <p className="text-zinc-500 text-center py-4">Нет данных</p>
                ) : (
                  <div className="space-y-2">
                    {topMerchants.map((m, i) => (
                      <div key={m.id} className="flex items-center justify-between p-2 bg-zinc-800 rounded">
                        <div className="flex items-center gap-3">
                          <span className="w-6 h-6 flex items-center justify-center bg-zinc-700 rounded text-xs">
                            {i + 1}
                          </span>
                          <div>
                            <p className="text-white text-sm">{m.merchant_name || m.nickname || m.login}</p>
                            <p className="text-xs text-zinc-500">{m.merchant_type}</p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-emerald-400 font-mono text-sm">{formatUSDT(m.balance_usdt)}</p>
                          <button onClick={() => copyToClipboard(m.id)} className="text-xs text-zinc-500 hover:text-white">
                            Копировать ID
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Wallet Management Tab (Admin Only) */}
        {isAdmin && (
          <TabsContent value="wallet">
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Settings className="w-5 h-5" />
                  Управление кошельком
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Current Wallet */}
                <div className="p-4 bg-zinc-800 rounded-lg">
                  <h4 className="text-sm font-semibold text-zinc-400 mb-3">Текущий кошелёк</h4>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-zinc-500">Адрес:</span>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-emerald-400">{hotWallet?.address || '-'}</span>
                        {hotWallet?.address && (
                          <>
                            <button onClick={() => copyToClipboard(hotWallet.address, 'Адрес')} className="text-zinc-500 hover:text-white">
                              <Copy className="w-4 h-4" />
                            </button>
                            <a 
                              href={`https://tonviewer.com/${hotWallet.address}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-zinc-500 hover:text-white"
                            >
                              <ExternalLink className="w-4 h-4" />
                            </a>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-zinc-500">Баланс:</span>
                      <span className="font-mono text-white">{formatUSDT(hotWallet?.balance_usd || hotWallet?.balance_ton)}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-zinc-500">Сеть:</span>
                      <span className={hotWallet?.network === 'mainnet' ? 'text-emerald-400 font-semibold' : 'text-yellow-400'}>
                        {hotWallet?.network === 'mainnet' ? '🟢 MAINNET' : '⚠️ testnet'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex gap-3">
                  <Button variant="outline" onClick={() => setShowWalletModal(true)} className="flex-1">
                    <Settings className="w-4 h-4 mr-2" />
                    Сменить кошелёк
                  </Button>
                  <Button variant="outline" onClick={generateWallet} className="flex-1">
                    <PlusCircle className="w-4 h-4 mr-2" />
                    Сгенерировать новый
                  </Button>
                </div>

                {/* Wallet Change Modal */}
                {showWalletModal && (
                  <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
                    <div className="bg-zinc-900 p-6 rounded-xl max-w-lg w-full mx-4">
                      <h3 className="text-xl font-bold text-white mb-4">Смена кошелька</h3>
                      <p className="text-red-400 text-sm mb-4">
                        ⚠️ ВНИМАНИЕ: Это критическая операция! Убедитесь что все средства переведены.
                      </p>
                      <div className="space-y-4">
                        <div>
                          <label className="text-sm text-zinc-400">Новый адрес</label>
                          <Input
                            value={newWalletAddress}
                            onChange={(e) => setNewWalletAddress(e.target.value)}
                            placeholder="EQ... или kQ..."
                            className="bg-zinc-800 border-zinc-700"
                          />
                        </div>
                        <div>
                          <label className="text-sm text-zinc-400">Мнемоника (24 слова)</label>
                          <textarea
                            value={newWalletMnemonic}
                            onChange={(e) => setNewWalletMnemonic(e.target.value)}
                            placeholder="word1 word2 word3 ..."
                            rows={3}
                            className="w-full bg-zinc-800 border border-zinc-700 rounded-md p-3 text-white"
                          />
                        </div>
                      </div>
                      <div className="flex gap-3 mt-6">
                        <Button variant="outline" onClick={() => setShowWalletModal(false)} className="flex-1">
                          Отмена
                        </Button>
                        <Button onClick={changeWallet} className="flex-1 bg-red-600 hover:bg-red-700">
                          Подтвердить смену
                        </Button>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {/* Audit Tab */}
        <TabsContent value="audit">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="w-5 h-5" />
                Журнал аудита
              </CardTitle>
            </CardHeader>
            <CardContent>
              {auditLogs.length === 0 ? (
                <p className="text-zinc-500 text-center py-8">Нет записей</p>
              ) : (
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {auditLogs.map((log, i) => (
                    <div key={i} className="p-3 bg-zinc-800 rounded text-sm">
                      <div className="flex justify-between">
                        <span className="text-white font-semibold">{log.action}</span>
                        <span className="text-zinc-500">{formatDate(log.created_at)}</span>
                      </div>
                      <p className="text-zinc-400 text-xs mt-1">{log.details || '-'}</p>
                      {log.target_user_id && (
                        <p className="text-zinc-500 text-xs">User: {log.target_user_id}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Balance Adjustment Modal */}
      {showAdjustModal && selectedUser && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
          <div className="bg-zinc-900 p-6 rounded-xl max-w-md w-full mx-4">
            <h3 className="text-xl font-bold text-white mb-4">Корректировка баланса</h3>
            <p className="text-zinc-400 text-sm mb-4">
              Пользователь: <span className="text-white">{selectedUser.user.nickname || selectedUser.user.login}</span>
              <br />
              Текущий баланс: <span className="text-emerald-400">{formatUSDT(selectedUser.user.balance_usdt)}</span>
            </p>
            <div className="space-y-4">
              <div>
                <label className="text-sm text-zinc-400">Сумма (+ добавить, - списать)</label>
                <Input
                  type="number"
                  step="0.01"
                  value={adjustAmount}
                  onChange={(e) => setAdjustAmount(e.target.value)}
                  placeholder="10.00 или -5.00"
                  className="bg-zinc-800 border-zinc-700"
                />
              </div>
              <div>
                <label className="text-sm text-zinc-400">Причина (обязательно)</label>
                <Input
                  value={adjustReason}
                  onChange={(e) => setAdjustReason(e.target.value)}
                  placeholder="Причина корректировки..."
                  className="bg-zinc-800 border-zinc-700"
                />
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <Button variant="outline" onClick={() => setShowAdjustModal(false)} className="flex-1">
                Отмена
              </Button>
              <Button onClick={adjustBalance} className="flex-1">
                Применить
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
