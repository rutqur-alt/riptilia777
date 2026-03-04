import React, { useState, useEffect, useRef } from 'react';
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
  Copy, RefreshCw, TrendingUp, TrendingDown, Repeat, DollarSign
} from 'lucide-react';

// Transaction type icons and colors
const TX_TYPES = {
  deposit: { label: 'Пополнение', icon: ArrowDownCircle, color: 'text-emerald-400', bg: 'bg-emerald-500/10', sign: '+' },
  withdraw: { label: 'Вывод', icon: ArrowUpCircle, color: 'text-red-400', bg: 'bg-red-500/10', sign: '-' },
  withdrawal: { label: 'Вывод', icon: ArrowUpCircle, color: 'text-red-400', bg: 'bg-red-500/10', sign: '-' },
  fee: { label: 'Комиссия', icon: TrendingDown, color: 'text-orange-400', bg: 'bg-orange-500/10', sign: '-' },
  internal_transfer: { label: 'Перевод', icon: Repeat, color: 'text-blue-400', bg: 'bg-blue-500/10', sign: '↔' },
  refund: { label: 'Возврат', icon: TrendingUp, color: 'text-emerald-400', bg: 'bg-emerald-500/10', sign: '+' },
  trade_fee: { label: 'Торговая комиссия', icon: TrendingDown, color: 'text-orange-400', bg: 'bg-orange-500/10', sign: '-' },
  trade: { label: 'Сделка P2P', icon: Repeat, color: 'text-blue-400', bg: 'bg-blue-500/10', sign: '' },
};

const TX_STATUSES = {
  pending: { label: 'Ожидает', icon: Clock, color: 'text-yellow-400' },
  confirming: { label: 'Подтверждается', icon: RefreshCw, color: 'text-blue-400' },
  success: { label: 'Успешно', icon: CheckCircle, color: 'text-emerald-400' },
  completed: { label: 'Выполнено', icon: CheckCircle, color: 'text-emerald-400' },
  failed: { label: 'Ошибка', icon: XCircle, color: 'text-red-400' },
  rejected: { label: 'Отклонено', icon: XCircle, color: 'text-red-400' },
  review: { label: 'На проверке', icon: Clock, color: 'text-orange-400' },
  cancelled: { label: 'Отменено', icon: XCircle, color: 'text-zinc-400' },
};

// Format USDT amount
const formatUSDT = (amount) => {
  const num = parseFloat(amount) || 0;
  return `${num.toFixed(2)} USDT`;
};

// Format date
const formatDate = (dateStr) => {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
};

// Shorten hash
const shortenHash = (hash) => {
  if (!hash) return '-';
  return `${hash.slice(0, 8)}...${hash.slice(-8)}`;
};

/**
 * User Finance Page - For Traders and Merchants
 * USDT in TON network
 */
export default function UserFinancePage() {
  const { token, user, refreshUserBalance } = useAuth();
  const [balance, setBalance] = useState(null);
  const [depositInfo, setDepositInfo] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [txLoading, setTxLoading] = useState(false);
  
  // Filters
  const [filters, setFilters] = useState({
    type: 'all',
    status: 'all',
    limit: 50
  });
  
  // Withdraw modal
  const [showWithdraw, setShowWithdraw] = useState(false);
  const [withdrawData, setWithdrawData] = useState({
    amount: '',
    to_address: ''
  });
  const [withdrawing, setWithdrawing] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    fetchTransactions();
  }, [filters]);

  const fetchData = async () => {
    try {
      const [balanceRes, depositRes] = await Promise.all([
        axios.get(`${API}/wallet/balance`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/wallet/deposit-address`, { headers: { Authorization: `Bearer ${token}` } })
      ]);
      
      setBalance(balanceRes.data.balance);
      setDepositInfo(depositRes.data.deposit_info);
    } catch (error) {
      console.error('Error fetching finance data:', error);
      toast.error('Ошибка загрузки данных');
    } finally {
      setLoading(false);
    }
  };

  const fetchTransactions = async () => {
    setTxLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.type !== 'all') params.append('type', filters.type);
      if (filters.status !== 'all') params.append('status', filters.status);
      params.append('limit', filters.limit);
      
      const res = await axios.get(`${API}/wallet/transactions?${params}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setTransactions(res.data.transactions || []);
    } catch (error) {
      console.error('Error fetching transactions:', error);
    } finally {
      setTxLoading(false);
    }
  };

  // Ref to prevent double-click
  const isSubmittingRef = useRef(false);

  const handleWithdraw = async () => {
    // Prevent double submission
    if (isSubmittingRef.current || withdrawing) {
      return;
    }
    
    if (!withdrawData.amount || !withdrawData.to_address) {
      toast.error('Заполните все поля');
      return;
    }
    
    const amount = parseFloat(withdrawData.amount);
    if (amount <= 0) {
      toast.error('Сумма должна быть больше 0');
      return;
    }
    
    const available = balance?.available_usd || balance?.usd || 0;
    if (amount > available) {
      toast.error('Недостаточно средств');
      return;
    }
    
    // Lock immediately
    isSubmittingRef.current = true;
    setWithdrawing(true);
    
    try {
      const res = await axios.post(`${API}/wallet/withdraw`, {
        amount: amount,
        to_address: withdrawData.to_address,
        comment: ''
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (res.data.success) {
        toast.success(res.data.message || 'Заявка на вывод создана');
        setShowWithdraw(false);
        setWithdrawData({ amount: '', to_address: '' });
        fetchData();
        fetchTransactions();
        // Refresh user balance in context immediately
        await refreshUserBalance();
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка при создании заявки');
    } finally {
      setWithdrawing(false);
      isSubmittingRef.current = false;
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

  // Use USD balance (which represents USDT)
  const available = balance?.available_usd || balance?.usd || 0;
  const frozen = balance?.frozen_usd || 0;
  const total = available + frozen;

  return (
    <div className="space-y-6" data-testid="user-finance-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Кошелёк</h1>
          <p className="text-zinc-400 text-sm">USDT • Сеть TON</p>
        </div>
        <Button 
          onClick={() => setShowWithdraw(true)}
          className="bg-red-600 hover:bg-red-700"
          data-testid="withdraw-button"
        >
          <ArrowUpCircle className="w-4 h-4 mr-2" />
          Вывести
        </Button>
      </div>

      {/* Balance Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="bg-gradient-to-br from-emerald-600 to-emerald-800 border-0">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-emerald-100 text-sm">Доступный баланс</p>
                <p className="text-3xl font-bold text-white font-mono mt-1">
                  {formatUSDT(available)}
                </p>
              </div>
              <DollarSign className="w-12 h-12 text-emerald-300/50" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-zinc-400 text-sm">Заморожено</p>
                <p className="text-2xl font-bold text-white font-mono mt-1">
                  {formatUSDT(frozen)}
                </p>
              </div>
              <Clock className="w-10 h-10 text-yellow-500/50" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-zinc-400 text-sm">Общий баланс</p>
                <p className="text-2xl font-bold text-white font-mono mt-1">
                  {formatUSDT(total)}
                </p>
              </div>
              <Wallet className="w-10 h-10 text-blue-500/50" />
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="deposit" className="space-y-4">
        <TabsList className="bg-zinc-800">
          <TabsTrigger value="deposit">Пополнить</TabsTrigger>
          <TabsTrigger value="history">История</TabsTrigger>
        </TabsList>

        {/* Deposit Tab */}
        <TabsContent value="deposit">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <ArrowDownCircle className="w-5 h-5 text-emerald-400" />
                Пополнение USDT
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-4">
                <p className="text-sm text-emerald-300 mb-4">
                  Отправьте <span className="font-bold">USDT</span> в сети <span className="font-bold">TON</span> на адрес ниже с указанным комментарием.
                </p>
                
                <div className="space-y-3">
                  <div>
                    <label className="text-xs text-zinc-500 uppercase">Адрес для пополнения</label>
                    <div className="flex items-center gap-2 mt-1">
                      <code className="flex-1 bg-zinc-950 px-3 py-2 rounded text-sm font-mono text-emerald-400 truncate">
                        {depositInfo?.address}
                      </code>
                      <Button 
                        variant="ghost" 
                        size="icon"
                        onClick={() => copyToClipboard(depositInfo?.address, 'Адрес')}
                      >
                        <Copy className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                  
                  <div>
                    <label className="text-xs text-zinc-500 uppercase">Комментарий (ОБЯЗАТЕЛЬНО!)</label>
                    <div className="flex items-center gap-2 mt-1">
                      <code className="flex-1 bg-zinc-950 px-3 py-2 rounded text-sm font-mono text-yellow-400 truncate">
                        {depositInfo?.comment}
                      </code>
                      <Button 
                        variant="ghost" 
                        size="icon"
                        onClick={() => copyToClipboard(depositInfo?.comment, 'Комментарий')}
                      >
                        <Copy className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </div>
                
                <div className="mt-4 p-3 bg-zinc-900/50 rounded-lg">
                  <p className="text-xs text-zinc-400">
                    <span className="text-white font-medium">Сеть:</span> TON (The Open Network)
                  </p>
                  <p className="text-xs text-zinc-400 mt-1">
                    <span className="text-white font-medium">Валюта:</span> USDT (Tether)
                  </p>
                  <p className="text-xs text-zinc-400 mt-1">
                    <span className="text-white font-medium">Мин. сумма:</span> 1 USDT
                  </p>
                </div>
                
                <p className="text-xs text-orange-400 mt-3">
                  ⚠️ Отправляйте только USDT в сети TON! Другие токены будут потеряны.
                </p>
                <p className="text-xs text-orange-400 mt-1">
                  ⚠️ Без комментария средства не будут зачислены автоматически!
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* History Tab */}
        <TabsContent value="history">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">История операций</CardTitle>
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={fetchTransactions}
                  disabled={txLoading}
                >
                  <RefreshCw className={`w-4 h-4 mr-2 ${txLoading ? 'animate-spin' : ''}`} />
                  Обновить
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {/* Filters */}
              <div className="flex gap-3 mb-4">
                <Select value={filters.type} onValueChange={(v) => setFilters({...filters, type: v})}>
                  <SelectTrigger className="w-40 bg-zinc-800 border-zinc-700">
                    <SelectValue placeholder="Тип" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Все типы</SelectItem>
                    <SelectItem value="deposit">Пополнение</SelectItem>
                    <SelectItem value="withdrawal">Вывод</SelectItem>
                    <SelectItem value="refund">Возврат</SelectItem>
                    <SelectItem value="trade">Сделка P2P</SelectItem>
                  </SelectContent>
                </Select>
                
                <Select value={filters.status} onValueChange={(v) => setFilters({...filters, status: v})}>
                  <SelectTrigger className="w-40 bg-zinc-800 border-zinc-700">
                    <SelectValue placeholder="Статус" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Все статусы</SelectItem>
                    <SelectItem value="completed">Выполнено</SelectItem>
                    <SelectItem value="pending">Ожидает</SelectItem>
                    <SelectItem value="rejected">Отклонено</SelectItem>
                    <SelectItem value="failed">Ошибка</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Transactions Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-zinc-800">
                      <th className="text-left py-3 px-2 text-zinc-500 font-medium">Дата</th>
                      <th className="text-left py-3 px-2 text-zinc-500 font-medium">Тип</th>
                      <th className="text-right py-3 px-2 text-zinc-500 font-medium">Сумма</th>
                      <th className="text-center py-3 px-2 text-zinc-500 font-medium">Статус</th>
                      <th className="text-left py-3 px-2 text-zinc-500 font-medium">Hash</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transactions.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="text-center py-8 text-zinc-500">
                          Операций пока нет
                        </td>
                      </tr>
                    ) : (
                      transactions.map((tx) => {
                        const txType = TX_TYPES[tx.type] || TX_TYPES.deposit;
                        const txStatus = TX_STATUSES[tx.status] || TX_STATUSES.pending;
                        const Icon = txType.icon;
                        const StatusIcon = txStatus.icon;
                        const amount = parseFloat(tx.amount) || 0;
                        
                        return (
                          <tr key={tx.tx_id} className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
                            <td className="py-3 px-2 text-zinc-400">
                              {formatDate(tx.created_at)}
                            </td>
                            <td className="py-3 px-2">
                              <div className="flex items-center gap-2">
                                <div className={`p-1.5 rounded ${txType.bg}`}>
                                  <Icon className={`w-4 h-4 ${txType.color}`} />
                                </div>
                                <span className="text-zinc-300">{txType.label}</span>
                              </div>
                            </td>
                            <td className={`py-3 px-2 text-right font-mono ${txType.color}`}>
                              {txType.sign}{amount.toFixed(2)} USDT
                            </td>
                            <td className="py-3 px-2">
                              <div className="flex items-center justify-center gap-1.5">
                                <StatusIcon className={`w-4 h-4 ${txStatus.color}`} />
                                <span className={txStatus.color}>{txStatus.label}</span>
                              </div>
                            </td>
                            <td className="py-3 px-2">
                              {tx.tx_hash ? (
                                <div className="flex items-center gap-1">
                                  <code className="text-xs text-zinc-500 font-mono">
                                    {shortenHash(tx.tx_hash)}
                                  </code>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-6 w-6"
                                    onClick={() => copyToClipboard(tx.tx_hash, 'Hash')}
                                  >
                                    <Copy className="w-3 h-3" />
                                  </Button>
                                </div>
                              ) : (
                                <span className="text-zinc-600">-</span>
                              )}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Withdraw Modal */}
      {showWithdraw && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <Card className="bg-zinc-900 border-zinc-700 w-full max-w-md">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ArrowUpCircle className="w-5 h-5 text-red-400" />
                Вывод USDT
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm text-zinc-400 mb-1 block">
                  Сумма (доступно: {available.toFixed(2)} USDT)
                </label>
                <Input
                  type="number"
                  step="0.01"
                  placeholder="0.00"
                  value={withdrawData.amount}
                  onChange={(e) => setWithdrawData({...withdrawData, amount: e.target.value})}
                  className="bg-zinc-800 border-zinc-700"
                />
              </div>
              
              <div>
                <label className="text-sm text-zinc-400 mb-1 block">Адрес кошелька (сеть TON)</label>
                <Input
                  placeholder="EQ... или UQ..."
                  value={withdrawData.to_address}
                  onChange={(e) => setWithdrawData({...withdrawData, to_address: e.target.value})}
                  className="bg-zinc-800 border-zinc-700 font-mono text-sm"
                />
              </div>
              
              <div className="bg-zinc-800 rounded-lg p-3 text-sm space-y-2">
                <div className="flex justify-between text-zinc-400">
                  <span>Сумма к выводу:</span>
                  <span className="text-white">{withdrawData.amount || '0'} USDT</span>
                </div>
                <div className="flex justify-between text-zinc-400">
                  <span>Комиссия:</span>
                  <span className="text-orange-400">1 USDT</span>
                </div>
                <div className="flex justify-between text-zinc-400 border-t border-zinc-700 pt-2">
                  <span>Вы получите:</span>
                  <span className="text-emerald-400 font-medium">
                    {Math.max(0, (parseFloat(withdrawData.amount) || 0) - 1).toFixed(2)} USDT
                  </span>
                </div>
              </div>
              
              <div className="bg-zinc-800/50 rounded-lg p-3 text-xs text-zinc-500">
                <p><span className="text-zinc-300">Сеть:</span> TON</p>
                <p className="mt-1"><span className="text-zinc-300">Мин. вывод:</span> 5 USDT</p>
              </div>
              
              {parseFloat(withdrawData.amount) >= 500 && (
                <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-3 text-sm text-yellow-300">
                  ⚠️ Крупный вывод требует подтверждения модератора
                </div>
              )}
              
              <div className="flex gap-3">
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => setShowWithdraw(false)}
                >
                  Отмена
                </Button>
                <Button
                  className="flex-1 bg-red-600 hover:bg-red-700"
                  onClick={handleWithdraw}
                  disabled={withdrawing}
                >
                  {withdrawing ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    'Вывести'
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
