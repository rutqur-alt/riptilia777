import React, { useState, useEffect, useCallback } from 'react';
import DashboardLayout from '@/components/DashboardLayout';
import { api, formatUSDT, formatRUB, formatDate, useAuth } from '@/lib/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { toast } from 'sonner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  RefreshCw, ArrowUpCircle, ArrowDownCircle, Clock, 
  CheckCircle, XCircle, ExternalLink, TrendingUp, 
  Wallet, BarChart3, DollarSign, Calendar, Trash2
} from 'lucide-react';

const AdminFinances = () => {
  const { user: currentUser } = useAuth();
  const isSupport = currentUser?.role === 'support';
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(true);
  
  // Overview data
  const [stats, setStats] = useState(null);
  const [usdtRate, setUsdtRate] = useState(0);
  
  // Withdrawals
  const [withdrawals, setWithdrawals] = useState([]);
  const [withdrawFilter, setWithdrawFilter] = useState('pending');
  const [processingId, setProcessingId] = useState(null);
  const [txHashInput, setTxHashInput] = useState('');
  const [showTxModal, setShowTxModal] = useState(null);
  const [deleteWithdrawalConfirm, setDeleteWithdrawalConfirm] = useState(null);
  
  // Deposits  
  const [depositRequests, setDepositRequests] = useState([]);
  const [depositFilter, setDepositFilter] = useState('pending');
  const [manualCreditAmount, setManualCreditAmount] = useState('');
  const [manualCreditUserId, setManualCreditUserId] = useState('');
  const [showCreditModal, setShowCreditModal] = useState(null);
  const [deleteDepositConfirm, setDeleteDepositConfirm] = useState(null);
  
  // Unidentified deposits
  const [unidentifiedDeposits, setUnidentifiedDeposits] = useState([]);
  const [unidentifiedWithdrawals, setUnidentifiedWithdrawals] = useState([]);
  const [assigningDepositId, setAssigningDepositId] = useState(null);
  const [assignUserId, setAssignUserId] = useState('');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [accountingRes, rateRes] = await Promise.all([
        api.get('/admin/accounting'),
        api.get('/rates/usdt')
      ]);
      
      setStats(accountingRes.data);
      setUsdtRate(rateRes.data.usdt_rub || 0);
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchWithdrawals = async () => {
    try {
      const res = await api.get(`/admin/usdt/withdrawals?status=${withdrawFilter !== 'all' ? withdrawFilter : ''}`);
      setWithdrawals(res.data.withdrawals || []);
    } catch (error) {
      console.error('Error:', error);
    }
  };

  const fetchDeposits = async () => {
    try {
      const res = await api.get(`/admin/usdt/deposit-requests?status=${depositFilter !== 'all' ? depositFilter : ''}`);
      setDepositRequests(res.data.requests || []);
    } catch (error) {
      console.error('Error:', error);
    }
  };

  const fetchUnidentifiedDeposits = async () => {
    try {
      const res = await api.get('/admin/usdt/unidentified-deposits');
      setUnidentifiedDeposits(res.data.deposits || res.data || []);
    } catch (error) {
      console.error('Error fetching unidentified deposits:', error);
    }
  };

  const fetchUnidentifiedWithdrawals = async () => {
    try {
      const res = await api.get('/admin/usdt/unidentified-withdrawals');
      setUnidentifiedWithdrawals(res.data.withdrawals || res.data || []);
    } catch (error) {
      console.error('Error fetching unidentified withdrawals:', error);
    }
  };

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    if (activeTab === 'withdrawals') {
      fetchWithdrawals();
      fetchUnidentifiedWithdrawals();
    }
    if (activeTab === 'deposits') {
      fetchDeposits();
      fetchUnidentifiedDeposits();
    }
  }, [activeTab, withdrawFilter, depositFilter]);

  // Manual deposit handler
  const handleManualDeposit = async () => {
    if (!manualCreditUserId || !manualCreditAmount || parseFloat(manualCreditAmount) <= 0) {
      toast.error('Укажите ID пользователя и сумму');
      return;
    }
    
    try {
      const res = await api.post(`/admin/usdt/manual-deposit?user_id=${manualCreditUserId}&amount_usdt=${parseFloat(manualCreditAmount)}`);
      toast.success(res.data.message || 'Депозит зачислен');
      setManualCreditUserId('');
      setManualCreditAmount('');
      fetchDeposits();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка зачисления');
    }
  };

  // Delete handlers
  const deleteWithdrawal = async (id) => {
    try {
      await api.delete(`/admin/withdrawals/${id}`);
      toast.success('Заявка на вывод удалена');
      setDeleteWithdrawalConfirm(null);
      fetchWithdrawals();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка удаления');
    }
  };

  const deleteDeposit = async (id) => {
    try {
      await api.delete(`/admin/deposits/${id}`);
      toast.success('Заявка на депозит удалена');
      setDeleteDepositConfirm(null);
      fetchDeposits();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка удаления');
    }
  };

  // Withdrawal handlers
  const processWithdrawal = async (id, txHash = null) => {
    setProcessingId(id);
    try {
      const url = txHash ? `/admin/usdt/withdrawal/${id}/process?tx_hash=${txHash}` : `/admin/usdt/withdrawal/${id}/process`;
      const response = await api.post(url);
      const newTxHash = response.data?.tx_hash;
      if (newTxHash) {
        toast.success(`✅ Вывод выполнен! TX: ${newTxHash.slice(0, 16)}...`);
      } else {
        toast.success('Вывод подтверждён');
      }
      setShowTxModal(null);
      setTxHashInput('');
      fetchWithdrawals();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка отправки');
    } finally {
      setProcessingId(null);
    }
  };

  const rejectWithdrawal = async (id) => {
    setProcessingId(id);
    try {
      await api.post(`/admin/usdt/withdrawal/${id}/reject`);
      toast.success('Заявка отклонена');
      fetchWithdrawals();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка');
    } finally {
      setProcessingId(null);
    }
  };

  // Deposit handlers
  const manualCreditDeposit = async (requestId) => {
    if (!manualCreditAmount || parseFloat(manualCreditAmount) <= 0) {
      toast.error('Укажите сумму');
      return;
    }
    
    setProcessingId(requestId);
    try {
      await api.post(`/admin/usdt/deposit-request/${requestId}/manual-credit?amount_usdt=${parseFloat(manualCreditAmount)}`);
      toast.success('Депозит зачислен');
      setShowCreditModal(null);
      setManualCreditAmount('');
      fetchDeposits();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка');
    } finally {
      setProcessingId(null);
    }
  };

  const formatDate = (iso) => {
    if (!iso) return '-';
    return new Date(iso).toLocaleString('ru-RU');
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-8 h-8 animate-spin text-emerald-500" />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6" data-testid="admin-finances">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold font-['Chivo']">Финансы</h1>
            <p className="text-zinc-400 mt-1">Бухгалтерия, депозиты и выводы</p>
          </div>
          <div className="flex items-center gap-4">
            <div className="px-3 py-1.5 bg-zinc-800 rounded-lg">
              <span className="text-xs text-zinc-500">Курс USDT:</span>
              <span className="font-mono ml-2">{usdtRate.toFixed(2)} ₽</span>
            </div>
            <Button onClick={fetchData} variant="outline" size="sm">
              <RefreshCw className="w-4 h-4 mr-2" />
              Обновить
            </Button>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="bg-zinc-800 border border-zinc-700">
            <TabsTrigger value="overview" className="data-[state=active]:bg-emerald-600">
              <BarChart3 className="w-4 h-4 mr-2" />
              Обзор
            </TabsTrigger>
            <TabsTrigger value="withdrawals" className="data-[state=active]:bg-emerald-600">
              <ArrowUpCircle className="w-4 h-4 mr-2" />
              Выводы
            </TabsTrigger>
            <TabsTrigger value="deposits" className="data-[state=active]:bg-emerald-600">
              <ArrowDownCircle className="w-4 h-4 mr-2" />
              Депозиты
            </TabsTrigger>
          </TabsList>

          {/* Overview Tab */}
          <TabsContent value="overview" className="space-y-6 mt-6">
            {/* Stats Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Card className="bg-zinc-900 border-zinc-800">
                <CardContent className="p-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
                      <TrendingUp className="w-5 h-5 text-blue-400" />
                    </div>
                    <div>
                      <p className="text-xs text-zinc-500">Оборот</p>
                      <p className="font-['JetBrains_Mono'] font-bold">{formatRUB(stats?.summary?.total_volume_rub || 0)}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
              
              <Card className="bg-zinc-900 border-zinc-800">
                <CardContent className="p-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                      <DollarSign className="w-5 h-5 text-emerald-400" />
                    </div>
                    <div>
                      <p className="text-xs text-zinc-500">USDT оборот</p>
                      <p className="font-['JetBrains_Mono'] font-bold">{formatUSDT(stats?.summary?.total_volume_usdt || 0)}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
              
              <Card className="bg-zinc-900 border-zinc-800">
                <CardContent className="p-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center">
                      <Wallet className="w-5 h-5 text-purple-400" />
                    </div>
                    <div>
                      <p className="text-xs text-zinc-500">Комиссия</p>
                      <p className="font-['JetBrains_Mono'] font-bold text-emerald-400">
                        +{formatUSDT(stats?.summary?.platform_commission_usdt || 0)}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
              
              <Card className="bg-zinc-900 border-zinc-800">
                <CardContent className="p-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-orange-500/10 flex items-center justify-center">
                      <Calendar className="w-5 h-5 text-orange-400" />
                    </div>
                    <div>
                      <p className="text-xs text-zinc-500">Сделок</p>
                      <p className="font-['JetBrains_Mono'] font-bold">{stats?.summary?.total_orders || 0}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Daily Stats */}
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <CardTitle>Статистика по дням</CardTitle>
              </CardHeader>
              <CardContent>
                {stats?.daily_stats?.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-zinc-800">
                          <th className="text-left py-2 px-3 text-zinc-400">Дата</th>
                          <th className="text-right py-2 px-3 text-zinc-400">Сделок</th>
                          <th className="text-right py-2 px-3 text-zinc-400">Оборот (₽)</th>
                          <th className="text-right py-2 px-3 text-zinc-400">Комиссия (USDT)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {stats.daily_stats.map((day, i) => (
                          <tr key={i} className="border-b border-zinc-800/50">
                            <td className="py-2 px-3">{day.date}</td>
                            <td className="py-2 px-3 text-right font-mono">{day.orders}</td>
                            <td className="py-2 px-3 text-right font-mono">{formatRUB(day.volume_rub)}</td>
                            <td className="py-2 px-3 text-right font-mono text-emerald-400">
                              +{formatUSDT(day.commission_usdt)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-center py-8 text-zinc-500">
                    <BarChart3 className="w-12 h-12 mx-auto mb-2 opacity-50" />
                    <p>Нет данных за последние дни</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Withdrawals Tab */}
          <TabsContent value="withdrawals" className="space-y-4 mt-6">
            <div className="flex gap-2 flex-wrap">
              {['pending', 'completed', 'rejected', 'all', 'unidentified'].map(f => (
                <Button
                  key={f}
                  variant={withdrawFilter === f ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setWithdrawFilter(f)}
                  className={withdrawFilter === f ? (f === 'unidentified' ? 'bg-orange-600' : 'bg-emerald-600') : ''}
                >
                  {f === 'pending' ? '⏳ Ожидают' : f === 'completed' ? '✓ Выполнены' : f === 'rejected' ? '✗ Отклонены' : f === 'unidentified' ? '⚠️ Неопознанные' : '📋 Все'}
                </Button>
              ))}
            </div>

            {/* Unidentified Withdrawals View */}
            {withdrawFilter === 'unidentified' ? (
              <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader className="border-b border-zinc-800">
                  <CardTitle className="text-lg text-orange-400">Неопознанные выводы</CardTitle>
                  <CardDescription>
                    Исходящие транзакции с горячего кошелька которые не привязаны к заявкам
                  </CardDescription>
                </CardHeader>
                <CardContent className="p-0">
                  {unidentifiedWithdrawals.length === 0 ? (
                    <div className="p-8 text-center text-zinc-500">
                      <Clock className="w-12 h-12 mx-auto mb-2 opacity-50" />
                      <p>Нет неопознанных выводов</p>
                    </div>
                  ) : (
                    <div className="divide-y divide-zinc-800">
                      {unidentifiedWithdrawals.map(w => (
                        <div key={w.id} className="p-4">
                          <div className="flex items-center justify-between mb-2">
                            <span className="font-mono font-bold text-red-400">-{(w.amount_usdt || 0).toFixed(2)} USDT</span>
                            <span className="text-xs text-zinc-500">{formatDate(w.created_at)}</span>
                          </div>
                          {w.comment && (
                            <p className="text-xs text-yellow-400 mb-2">
                              💬 Комментарий: <span className="font-mono">{w.comment}</span>
                            </p>
                          )}
                          <p className="text-sm text-zinc-400 mb-1 truncate">
                            → Получатель: {(w.recipient || w.to_address || 'unknown').slice(0, 40)}...
                          </p>
                          {w.tx_hash && (
                            <p className="text-xs text-zinc-500 truncate">
                              TX: {w.tx_hash.slice(0, 40)}...
                            </p>
                          )}
                          <div className="mt-2 flex gap-2">
                            <span className="px-2 py-1 rounded text-xs bg-orange-500/20 text-orange-400">
                              ⚠️ Неопознанный
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            ) : (
              /* Regular Withdrawals View */
              <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader className="border-b border-zinc-800">
                  <CardTitle className="text-lg">Заявки на вывод USDT</CardTitle>
                  <CardDescription>
                    {withdrawFilter === 'pending' && 'Заявки ожидающие подтверждения администратора'}
                    {withdrawFilter === 'completed' && 'Успешно выполненные выводы'}
                    {withdrawFilter === 'rejected' && 'Отклонённые заявки'}
                    {withdrawFilter === 'all' && 'Все заявки на вывод'}
                  </CardDescription>
                </CardHeader>
                <CardContent className="p-0">
                  {withdrawals.length === 0 ? (
                    <div className="p-8 text-center text-zinc-500">
                      <ArrowUpCircle className="w-12 h-12 mx-auto mb-2 opacity-50" />
                      <p>Нет заявок на вывод</p>
                    </div>
                  ) : (
                    <div className="divide-y divide-zinc-800">
                      {withdrawals.map(w => (
                        <div key={w.id} className="p-4 flex items-center justify-between hover:bg-zinc-800/30">
                          <div className="flex-1">
                            <div className="flex items-center gap-3">
                              <span className="font-mono font-bold text-lg">{formatUSDT(w.amount_usdt)} USDT</span>
                              <span className={`px-2 py-0.5 rounded text-xs ${
                                w.status === 'pending' ? 'bg-yellow-500/20 text-yellow-400' :
                                (w.status === 'processed' || w.status === 'completed') ? 'bg-emerald-500/20 text-emerald-400' :
                                'bg-red-500/20 text-red-400'
                              }`}>
                                {w.status === 'pending' ? '⏳ Ожидает подтверждения' : (w.status === 'processed' || w.status === 'completed') ? '✓ Выполнен' : '✗ Отклонён'}
                            </span>
                            {!w.user_trusted && w.status === 'pending' && (
                              <span className="px-2 py-0.5 rounded text-xs bg-orange-500/20 text-orange-400">
                                ⚠ Недоверенный
                              </span>
                            )}
                          </div>
                          
                          {/* User info */}
                          <div className="flex items-center gap-2 mt-2">
                            <span className="text-sm text-zinc-300">👤 {w.username || w.user_id}</span>
                            <span className="text-xs text-zinc-500 font-mono">ID: {w.user_id}</span>
                          </div>
                          
                          <p className="text-sm text-zinc-400 font-mono mt-1">→ {w.to_address}</p>
                          <p className="text-xs text-zinc-500 mt-1">{formatDate(w.created_at)}</p>
                          
                          {w.tx_hash && (
                            <div className="flex items-center gap-2 mt-2 p-2 bg-emerald-900/20 rounded">
                              <span className="text-xs text-emerald-400">TX Hash:</span>
                              <a 
                                href={`https://tonscan.org/tx/${w.tx_hash}`} 
                                target="_blank" 
                                rel="noopener noreferrer" 
                                className="text-xs font-mono text-blue-400 hover:text-blue-300 hover:underline"
                              >
                                {w.tx_hash.slice(0, 20)}...{w.tx_hash.slice(-10)}
                              </a>
                              <ExternalLink className="w-3 h-3 text-blue-400" />
                            </div>
                          )}
                        </div>
                        
                        <div className="flex items-center gap-2">
                          {w.status === 'pending' && !isSupport && (
                            <>
                              <Button 
                                size="sm" 
                                onClick={() => processWithdrawal(w.id)} 
                                disabled={processingId === w.id} 
                                className="bg-emerald-600 hover:bg-emerald-700"
                              >
                                {processingId === w.id ? (
                                  <>⏳ Отправка...</>
                                ) : (
                                  <><CheckCircle className="w-4 h-4 mr-1" /> Отправить USDT</>
                                )}
                              </Button>
                              <Button size="sm" variant="destructive" onClick={() => rejectWithdrawal(w.id)} disabled={processingId === w.id}>
                                <XCircle className="w-4 h-4" />
                              </Button>
                            </>
                          )}
                          {w.status === 'pending' && isSupport && (
                            <span className="text-xs text-zinc-500">Только админ может одобрить</span>
                          )}
                          
                          {!isSupport && (
                            <Button 
                              size="sm" 
                              variant="ghost" 
                              onClick={() => setDeleteWithdrawalConfirm(w)}
                              className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
            )}

            {/* Delete Withdrawal Dialog */}
            <AlertDialog open={!!deleteWithdrawalConfirm} onOpenChange={() => setDeleteWithdrawalConfirm(null)}>
              <AlertDialogContent className="bg-zinc-900 border-zinc-800">
                <AlertDialogHeader>
                  <AlertDialogTitle>Удалить заявку на вывод?</AlertDialogTitle>
                  <AlertDialogDescription>
                    Заявка на {formatUSDT(deleteWithdrawalConfirm?.amount)} USDT будет удалена.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel className="bg-zinc-800 border-zinc-700 hover:bg-zinc-700">Отмена</AlertDialogCancel>
                  <AlertDialogAction onClick={() => deleteWithdrawal(deleteWithdrawalConfirm?.id)} className="bg-red-600 hover:bg-red-700">
                    Удалить
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>

            {showTxModal && (
              <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                <Card className="bg-zinc-900 border-zinc-700 w-full max-w-md mx-4">
                  <CardHeader><CardTitle>Подтверждение вывода</CardTitle></CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <Label>TX Hash (опционально)</Label>
                      <Input value={txHashInput} onChange={(e) => setTxHashInput(e.target.value)} placeholder="Хэш транзакции" />
                    </div>
                    <div className="flex gap-2">
                      <Button onClick={() => setShowTxModal(null)} variant="outline" className="flex-1">Отмена</Button>
                      <Button onClick={() => processWithdrawal(showTxModal, txHashInput)} className="flex-1">Подтвердить</Button>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}
          </TabsContent>

          {/* Deposits Tab */}
          <TabsContent value="deposits" className="space-y-4 mt-6">
            {/* Manual Deposit Form */}
            <Card className="bg-emerald-900/20 border-emerald-700/50">
              <CardHeader className="pb-2">
                <CardTitle className="text-base text-emerald-400">Ручное зачисление USDT</CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="flex gap-3 items-end">
                  <div className="flex-1">
                    <Label className="text-xs">ID пользователя</Label>
                    <Input
                      value={manualCreditUserId}
                      onChange={(e) => setManualCreditUserId(e.target.value)}
                      placeholder="user_xxx или merchant_xxx"
                      className="h-9"
                    />
                  </div>
                  <div className="w-32">
                    <Label className="text-xs">Сумма USDT</Label>
                    <Input
                      type="number"
                      step="0.01"
                      value={manualCreditAmount}
                      onChange={(e) => setManualCreditAmount(e.target.value)}
                      placeholder="100.00"
                      className="h-9"
                    />
                  </div>
                  <Button onClick={handleManualDeposit} className="bg-emerald-600 hover:bg-emerald-700 h-9">
                    Зачислить
                  </Button>
                </div>
              </CardContent>
            </Card>

            <div className="flex gap-2 flex-wrap">
              {['pending', 'credited', 'expired', 'all', 'unidentified'].map(f => (
                <Button
                  key={f}
                  variant={depositFilter === f ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setDepositFilter(f)}
                  className={depositFilter === f ? (f === 'unidentified' ? 'bg-orange-600' : '') : ''}
                >
                  {f === 'pending' ? 'Ожидают' : f === 'credited' ? 'Зачислены' : f === 'expired' ? 'Истекли' : f === 'unidentified' ? '⚠️ Неопознанные' : 'Все'}
                </Button>
              ))}
            </div>

            {/* Unidentified Deposits View */}
            {depositFilter === 'unidentified' ? (
              <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader className="border-b border-zinc-800">
                  <CardTitle className="text-lg text-orange-400">Неопознанные депозиты</CardTitle>
                  <CardDescription>
                    Входящие транзакции которые не привязаны к заявкам пользователей
                  </CardDescription>
                </CardHeader>
                <CardContent className="p-0">
                  {unidentifiedDeposits.filter(d => d.status !== 'assigned').length === 0 ? (
                    <div className="p-8 text-center text-zinc-500">
                      <Clock className="w-12 h-12 mx-auto mb-2 opacity-50" />
                      <p>Нет неопознанных депозитов</p>
                    </div>
                  ) : (
                    <div className="divide-y divide-zinc-800">
                      {unidentifiedDeposits.filter(d => d.status !== 'assigned').map(deposit => (
                        <div key={deposit.id} className="p-4">
                          <div className="flex justify-between items-start mb-2">
                            <span className="text-green-400 font-mono font-bold">
                              +{formatUSDT(deposit.amount_usdt)} USDT
                            </span>
                            <span className="text-xs text-zinc-500">
                              {formatDate(deposit.created_at)}
                            </span>
                          </div>
                          {deposit.comment && (
                            <p className="text-xs text-yellow-400 mb-1">
                              💬 Комментарий: <span className="font-mono">{deposit.comment}</span>
                            </p>
                          )}
                          {(deposit.sender || deposit.sender_address) && (
                            <p className="text-xs text-zinc-400 mb-2 truncate">
                              От: {(deposit.sender || deposit.sender_address).substring(0, 40)}...
                            </p>
                          )}
                          <p className="text-xs text-zinc-500 mb-2 truncate">
                            TX: {deposit.tx_hash?.substring(0, 30)}...
                          </p>
                          <div className="flex gap-2 mt-2">
                            <Input
                              placeholder="ID пользователя (usr_...)"
                              className="flex-1 h-8 text-xs"
                              value={assigningDepositId === deposit.id ? assignUserId : ''}
                              onChange={(e) => {
                                setAssigningDepositId(deposit.id);
                                setAssignUserId(e.target.value);
                              }}
                            />
                            <Button 
                              size="sm" 
                              className="h-8 text-xs bg-green-600 hover:bg-green-700"
                              disabled={assigningDepositId !== deposit.id || !assignUserId}
                              onClick={async () => {
                                try {
                                  await api.post(`/admin/usdt/unidentified-deposit/${deposit.id}/assign?user_id=${assignUserId}`);
                                  toast.success('Депозит привязан');
                                  setAssigningDepositId(null);
                                  setAssignUserId('');
                                  fetchUnidentifiedDeposits();
                                } catch (error) {
                                  toast.error(error.response?.data?.detail || 'Ошибка');
                                }
                              }}
                            >
                              Привязать
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            ) : (
            <Card className="bg-zinc-900 border-zinc-800">
              <CardContent className="p-0">
                {depositRequests.length === 0 ? (
                  <div className="p-8 text-center text-zinc-500">
                    <ArrowDownCircle className="w-12 h-12 mx-auto mb-2 opacity-50" />
                    <p>Нет заявок на депозит</p>
                  </div>
                ) : (
                  <div className="divide-y divide-zinc-800">
                    {depositRequests.map(req => (
                      <div key={req.id || req.request_id} className="p-4 flex items-center justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-mono font-bold">
                              {req.status === 'credited' 
                                ? `${formatUSDT(req.actual_amount_usdt || req.exact_amount_usdt || req.amount_usdt)} USDT`
                                : req.status === 'pending'
                                  ? 'Ожидает перевода'
                                  : '—'
                              }
                            </span>
                            <span className={`px-2 py-0.5 rounded text-xs ${
                              req.status === 'pending' ? 'bg-yellow-500/20 text-yellow-400' :
                              req.status === 'credited' ? 'bg-emerald-500/20 text-emerald-400' :
                              'bg-red-500/20 text-red-400'
                            }`}>
                              {req.status === 'pending' ? 'Ожидает' : req.status === 'credited' ? 'Зачислен' : 'Истёк'}
                            </span>
                          </div>
                          <p className="text-xs text-zinc-400 mt-1">
                            <span className="text-emerald-400 font-medium">{req.user_nickname || req.user_login || 'Unknown'}</span>
                            <span className="text-zinc-600 ml-2">({req.user_id})</span>
                          </p>
                          <p className="text-xs text-zinc-500">
                            Комментарий: <span className="text-cyan-400 font-mono">{req.deposit_comment}</span>
                          </p>
                          <p className="text-xs text-zinc-500">{formatDate(req.created_at)}</p>
                        </div>
                        
                        <div className="flex gap-2 items-center">
                          <Button 
                            size="sm" 
                            variant="ghost" 
                            onClick={() => setDeleteDepositConfirm(req)}
                            className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
            )}

            {/* Delete Deposit Dialog */}
            <AlertDialog open={!!deleteDepositConfirm} onOpenChange={() => setDeleteDepositConfirm(null)}>
              <AlertDialogContent className="bg-zinc-900 border-zinc-800">
                <AlertDialogHeader>
                  <AlertDialogTitle>Удалить заявку на депозит?</AlertDialogTitle>
                  <AlertDialogDescription>
                    Заявка на {formatUSDT(deleteDepositConfirm?.amount_usdt)} USDT будет удалена.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel className="bg-zinc-800 border-zinc-700 hover:bg-zinc-700">Отмена</AlertDialogCancel>
                  <AlertDialogAction onClick={() => deleteDeposit(deleteDepositConfirm?.id)} className="bg-red-600 hover:bg-red-700">
                    Удалить
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </TabsContent>
        </Tabs>
      </div>
    </DashboardLayout>
  );
};

export default AdminFinances;
