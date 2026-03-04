import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { 
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useAuth, API } from '@/App';
import axios from 'axios';
import { toast } from 'sonner';
import { 
  Wallet, ArrowDownCircle, ArrowUpCircle, Clock, CheckCircle, XCircle,
  Copy, RefreshCw, TrendingUp, TrendingDown, AlertTriangle, Search,
  Shield, Activity, Users, Download, Eye, Check, X, FileText
} from 'lucide-react';

// Transaction type icons and colors
const TX_TYPES = {
  deposit: { label: 'Пополнение', color: 'text-emerald-400', bg: 'bg-emerald-500/10', sign: '+' },
  withdraw: { label: 'Вывод', color: 'text-red-400', bg: 'bg-red-500/10', sign: '-' },
  fee: { label: 'Комиссия', color: 'text-orange-400', bg: 'bg-orange-500/10', sign: '-' },
  internal_transfer: { label: 'Перевод', color: 'text-blue-400', bg: 'bg-blue-500/10', sign: '↔' },
  refund: { label: 'Возврат', color: 'text-purple-400', bg: 'bg-purple-500/10', sign: '+' },
};

const TX_STATUSES = {
  pending: { label: 'Ожидает', color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
  success: { label: 'Успешно', color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
  failed: { label: 'Ошибка', color: 'text-red-400', bg: 'bg-red-500/10' },
  review: { label: 'Проверка', color: 'text-orange-400', bg: 'bg-orange-500/10' },
  queued: { label: 'В очереди', color: 'text-blue-400', bg: 'bg-blue-500/10' },
};

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

const shortenHash = (hash) => {
  if (!hash) return '-';
  return `${hash.slice(0, 8)}...${hash.slice(-8)}`;
};

/**
 * Admin Finance Dashboard
 */
export default function AdminFinancePage() {
  const { token, user } = useAuth();
  const [analytics, setAnalytics] = useState(null);
  const [hotWallet, setHotWallet] = useState(null);
  const [pendingWithdrawals, setPendingWithdrawals] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Search user
  const [searchUserId, setSearchUserId] = useState('');
  const [userFinance, setUserFinance] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);

  const isAdmin = user?.role === 'admin' || user?.admin_role === 'admin' || user?.admin_role === 'owner';
  const isMod = user?.role === 'mod' || user?.admin_role?.includes('mod');

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const requests = [
        axios.get(`${API}/admin/finance/analytics`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/admin/finance/pending-withdrawals`, { headers: { Authorization: `Bearer ${token}` } })
      ];
      
      if (isAdmin) {
        requests.push(
          axios.get(`${API}/admin/finance/hot-wallet`, { headers: { Authorization: `Bearer ${token}` } }),
          axios.get(`${API}/admin/finance/audit-logs?limit=50`, { headers: { Authorization: `Bearer ${token}` } })
        );
      }
      
      const results = await Promise.all(requests);
      
      setAnalytics(results[0].data.analytics);
      setPendingWithdrawals(results[1].data.pending_withdrawals || []);
      
      if (isAdmin && results[2]) {
        setHotWallet(results[2].data.hot_wallet);
      }
      if (isAdmin && results[3]) {
        setAuditLogs(results[3].data.logs || []);
      }
    } catch (error) {
      console.error('Error fetching admin finance data:', error);
      toast.error('Ошибка загрузки данных');
    } finally {
      setLoading(false);
    }
  };

  const searchUser = async () => {
    if (!searchUserId.trim()) return;
    
    setSearchLoading(true);
    try {
      const res = await axios.get(`${API}/admin/finance/user/${searchUserId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setUserFinance(res.data);
    } catch (error) {
      toast.error('Пользователь не найден');
      setUserFinance(null);
    } finally {
      setSearchLoading(false);
    }
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
      toast.success('Вывод отклонён, средства возвращены');
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка');
    }
  };

  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text);
    toast.success(`${label} скопирован`);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="animate-spin w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="admin-finance-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Финансовый дашборд</h1>
          <p className="text-zinc-400 text-sm">Аналитика и управление средствами</p>
        </div>
        <Button onClick={fetchData} variant="outline">
          <RefreshCw className="w-4 h-4 mr-2" />
          Обновить
        </Button>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Hot Wallet */}
        {hotWallet && (
          <Card className="bg-gradient-to-br from-blue-600 to-blue-800 border-0">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-blue-100 text-sm">Кошелёк биржи</p>
                  <p className="text-2xl font-bold text-white font-mono mt-1">
                    {formatUSDT(hotWallet.balance_usd)}
                  </p>
                </div>
                <Wallet className="w-10 h-10 text-blue-300/50" />
              </div>
            </CardContent>
          </Card>
        )}

        {/* User Balances */}
        <Card className="bg-gradient-to-br from-purple-600 to-purple-800 border-0">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-purple-100 text-sm">Балансы пользователей</p>
                <p className="text-2xl font-bold text-white font-mono mt-1">
                  {formatUSDT(analytics?.liabilities?.total_ton)}
                </p>
              </div>
              <Users className="w-10 h-10 text-purple-300/50" />
            </div>
          </CardContent>
        </Card>

        {/* Reserve Ratio */}
        <Card className={`border-0 ${analytics?.reserve_healthy ? 'bg-emerald-900' : 'bg-red-900'}`}>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-zinc-300 text-sm">Reserve Ratio</p>
                <p className={`text-2xl font-bold font-mono mt-1 ${analytics?.reserve_healthy ? 'text-emerald-400' : 'text-red-400'}`}>
                  {analytics?.reserve_ratio?.toFixed(1)}%
                </p>
              </div>
              {analytics?.reserve_healthy ? (
                <CheckCircle className="w-10 h-10 text-emerald-400/50" />
              ) : (
                <AlertTriangle className="w-10 h-10 text-red-400/50" />
              )}
            </div>
          </CardContent>
        </Card>

        {/* Net Flow 24h */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-zinc-400 text-sm">Net Flow (24ч)</p>
                <p className={`text-2xl font-bold font-mono mt-1 ${
                  (analytics?.stats_24h?.net_flow || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
                }`}>
                  {(analytics?.stats_24h?.net_flow || 0) >= 0 ? '+' : ''}{formatUSDT(analytics?.stats_24h?.net_flow)}
                </p>
              </div>
              <Activity className="w-10 h-10 text-zinc-600" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 24h Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="pt-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-emerald-500/10">
                <ArrowDownCircle className="w-5 h-5 text-emerald-400" />
              </div>
              <div>
                <p className="text-xs text-zinc-500">Депозиты (24ч)</p>
                <p className="text-lg font-bold text-white">{analytics?.stats_24h?.deposit_count || 0}</p>
                <p className="text-xs text-emerald-400">{formatUSDT(analytics?.stats_24h?.deposits)}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="pt-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-red-500/10">
                <ArrowUpCircle className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <p className="text-xs text-zinc-500">Выводы (24ч)</p>
                <p className="text-lg font-bold text-white">{analytics?.stats_24h?.withdrawal_count || 0}</p>
                <p className="text-xs text-red-400">{formatUSDT(analytics?.stats_24h?.withdrawals)}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="pt-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-orange-500/10">
                <TrendingUp className="w-5 h-5 text-orange-400" />
              </div>
              <div>
                <p className="text-xs text-zinc-500">Комиссии (24ч)</p>
                <p className="text-lg font-bold text-orange-400">{formatUSDT(analytics?.stats_24h?.fees_collected)}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="pt-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-yellow-500/10">
                <Clock className="w-5 h-5 text-yellow-400" />
              </div>
              <div>
                <p className="text-xs text-zinc-500">Pending / Review</p>
                <p className="text-lg font-bold text-yellow-400">
                  {analytics?.pending_transactions || 0} / {analytics?.review_transactions || 0}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="withdrawals" className="space-y-4">
        <TabsList className="bg-zinc-800">
          <TabsTrigger value="withdrawals">
            Заявки на вывод
            {pendingWithdrawals.length > 0 && (
              <span className="ml-2 bg-red-500 text-white text-xs px-2 py-0.5 rounded-full">
                {pendingWithdrawals.length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="search">Поиск пользователя</TabsTrigger>
          {isAdmin && <TabsTrigger value="audit">Аудит</TabsTrigger>}
        </TabsList>

        {/* Pending Withdrawals */}
        <TabsContent value="withdrawals">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Clock className="w-5 h-5 text-yellow-400" />
                Заявки на вывод (требуют одобрения)
              </CardTitle>
            </CardHeader>
            <CardContent>
              {pendingWithdrawals.length === 0 ? (
                <div className="text-center py-8 text-zinc-500">
                  Нет заявок, ожидающих одобрения
                </div>
              ) : (
                <div className="space-y-3">
                  {pendingWithdrawals.map((w) => (
                    <div 
                      key={w.tx_id}
                      className="flex items-center justify-between p-4 bg-zinc-800 rounded-lg"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-lg font-bold text-red-400">
                            -{formatUSDT(w.amount)}
                          </span>
                          <span className="text-xs bg-yellow-500/20 text-yellow-400 px-2 py-0.5 rounded">
                            Ожидает
                          </span>
                        </div>
                        <div className="text-xs text-zinc-500">
                          User: <code className="text-zinc-400">{w.user_id?.slice(0, 8)}...</code>
                          {' • '}
                          Баланс: {formatUSDT(w.balance_usd)}
                        </div>
                        <div className="text-xs text-zinc-500">
                          Адрес: <code className="text-zinc-400">{w.to_address?.slice(0, 20)}...</code>
                        </div>
                        <div className="text-xs text-zinc-600">
                          {formatDate(w.created_at)}
                        </div>
                      </div>
                      
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          className="bg-emerald-600 hover:bg-emerald-700"
                          onClick={() => approveWithdrawal(w.tx_id)}
                        >
                          <Check className="w-4 h-4 mr-1" />
                          Одобрить
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="border-red-500 text-red-400 hover:bg-red-500/10"
                          onClick={() => rejectWithdrawal(w.tx_id)}
                        >
                          <X className="w-4 h-4 mr-1" />
                          Отклонить
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Search User */}
        <TabsContent value="search">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Search className="w-5 h-5 text-blue-400" />
                Поиск пользователя
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-3">
                <Input
                  placeholder="User ID"
                  value={searchUserId}
                  onChange={(e) => setSearchUserId(e.target.value)}
                  className="bg-zinc-800 border-zinc-700 font-mono"
                />
                <Button onClick={searchUser} disabled={searchLoading}>
                  {searchLoading ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <Search className="w-4 h-4" />
                  )}
                </Button>
              </div>
              
              {userFinance && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-zinc-800 rounded-lg p-4">
                      <p className="text-sm text-zinc-500">Баланс TON</p>
                      <p className="text-xl font-bold text-emerald-400 font-mono">
                        {formatUSDT(userFinance.balance?.balance_usd)}
                      </p>
                    </div>
                    <div className="bg-zinc-800 rounded-lg p-4">
                      <p className="text-sm text-zinc-500">Заморожено</p>
                      <p className="text-xl font-bold text-yellow-400 font-mono">
                        {formatUSDT(userFinance.balance?.frozen_usd)}
                      </p>
                    </div>
                  </div>
                  
                  <div>
                    <h4 className="text-sm font-medium text-zinc-400 mb-2">Последние транзакции</h4>
                    <div className="space-y-2">
                      {userFinance.recent_transactions?.map((tx) => (
                        <div 
                          key={tx.tx_id}
                          className="flex items-center justify-between p-2 bg-zinc-800 rounded text-sm"
                        >
                          <div className="flex items-center gap-2">
                            <span className={TX_TYPES[tx.type]?.color || 'text-zinc-400'}>
                              {TX_TYPES[tx.type]?.label || tx.type}
                            </span>
                            <span className={TX_STATUSES[tx.status]?.color || 'text-zinc-400'}>
                              ({TX_STATUSES[tx.status]?.label || tx.status})
                            </span>
                          </div>
                          <span className={`font-mono ${
                            tx.type === 'deposit' ? 'text-emerald-400' : 'text-red-400'
                          }`}>
                            {tx.type === 'deposit' ? '+' : '-'}{formatUSDT(tx.amount)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Audit Logs */}
        {isAdmin && (
          <TabsContent value="audit">
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <FileText className="w-5 h-5 text-purple-400" />
                  Аудит действий
                </CardTitle>
              </CardHeader>
              <CardContent>
                {auditLogs.length === 0 ? (
                  <div className="text-center py-8 text-zinc-500">
                    Логов пока нет
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-zinc-800">
                          <th className="text-left py-2 px-2 text-zinc-500">Дата</th>
                          <th className="text-left py-2 px-2 text-zinc-500">Админ</th>
                          <th className="text-left py-2 px-2 text-zinc-500">Действие</th>
                          <th className="text-left py-2 px-2 text-zinc-500">Цель</th>
                          <th className="text-left py-2 px-2 text-zinc-500">IP</th>
                        </tr>
                      </thead>
                      <tbody>
                        {auditLogs.map((log, idx) => (
                          <tr key={idx} className="border-b border-zinc-800/50">
                            <td className="py-2 px-2 text-zinc-400 text-xs">
                              {formatDate(log.created_at)}
                            </td>
                            <td className="py-2 px-2">
                              <code className="text-xs text-zinc-400">{log.admin_user_id?.slice(0, 8)}...</code>
                            </td>
                            <td className="py-2 px-2">
                              <span className={`text-xs px-2 py-0.5 rounded ${
                                log.action?.includes('approve') ? 'bg-emerald-500/20 text-emerald-400' :
                                log.action?.includes('reject') ? 'bg-red-500/20 text-red-400' :
                                'bg-zinc-700 text-zinc-300'
                              }`}>
                                {log.action}
                              </span>
                            </td>
                            <td className="py-2 px-2">
                              <code className="text-xs text-zinc-500">{log.target_user_id?.slice(0, 8) || '-'}...</code>
                            </td>
                            <td className="py-2 px-2 text-xs text-zinc-600">{log.ip_address || '-'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>

      {/* Hot Wallet Info (Admin only) */}
      {isAdmin && hotWallet && (
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Shield className="w-5 h-5 text-blue-400" />
              Адрес кошелька (TON)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <code className="flex-1 bg-zinc-950 px-3 py-2 rounded text-sm font-mono text-blue-400">
                {hotWallet.address}
              </code>
              <Button 
                variant="ghost" 
                size="icon"
                onClick={() => copyToClipboard(hotWallet.address, 'Адрес')}
              >
                <Copy className="w-4 h-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
