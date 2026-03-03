import React, { useState, useEffect, useCallback } from 'react';
import DashboardLayout from '@/components/DashboardLayout';
import SecurityVerification from '@/components/SecurityVerification';
import { useAuth, api } from '@/lib/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import {
  ArrowDownCircle,
  ArrowUpCircle,
  Copy,
  RefreshCw,
  Clock,
  CheckCircle,
  XCircle,
  Wallet,
  QrCode,
  AlertTriangle,
  ExternalLink,
  TrendingUp,
  DollarSign,
  Coins,
  Shield
} from 'lucide-react';

// Функция форматирования USDT
const formatUSDT = (amount) => {
  if (!amount && amount !== 0) return '0.00';
  return parseFloat(amount).toFixed(2);
};

const UnifiedFinances = () => {
  const { user } = useAuth();
  const [wallet, setWallet] = useState(null);
  const [usdtWallet, setUsdtWallet] = useState(null);
  const [deposits, setDeposits] = useState([]);
  const [withdrawals, setWithdrawals] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [depositRequests, setDepositRequests] = useState([]);
  const [activeDepositRequest, setActiveDepositRequest] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  
  // Modals
  const [showDeposit, setShowDeposit] = useState(false);
  const [showWithdraw, setShowWithdraw] = useState(false);
  
  // Form states
  const [withdrawAmount, setWithdrawAmount] = useState('');
  const [withdrawAddress, setWithdrawAddress] = useState('');
  const [withdrawing, setWithdrawing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [transferringEarnings, setTransferringEarnings] = useState(false);
  
  // Security verification
  const [showSecurityModal, setShowSecurityModal] = useState(false);
  const [pendingWithdrawal, setPendingWithdrawal] = useState(null);
  
  // Config
  const [config, setConfig] = useState({
    platformTonAddress: '',
    minDeposit: 0,
    minWithdrawal: 0,
    withdrawalFeePercent: 0,
    withdrawalMinFee: 0,
    networkFee: 0,
    usdtRubRate: 100
  });

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      // Fetch USDT wallet
      const usdtRes = await api.get('/usdt/wallet');
      setUsdtWallet(usdtRes.data.wallet);
      setDeposits(usdtRes.data.deposits || []);
      setWithdrawals(usdtRes.data.withdrawals || []);
      setConfig({
        platformTonAddress: usdtRes.data.platform_ton_address,
        minDeposit: usdtRes.data.min_deposit ?? 0,
        minWithdrawal: usdtRes.data.min_withdrawal ?? 0,
        withdrawalFeePercent: usdtRes.data.withdrawal_fee_percent ?? 0,
        withdrawalMinFee: usdtRes.data.withdrawal_min_fee ?? 0,
        networkFee: usdtRes.data.network_fee ?? 0,
        usdtRubRate: usdtRes.data.usdt_rub_rate ?? 100
      });

      // Fetch active deposit request
      try {
        const activeReqRes = await api.get('/usdt/deposit/active-request');
        setActiveDepositRequest(activeReqRes.data.active_request);
      } catch (e) {
        setActiveDepositRequest(null);
      }

      // Fetch deposit requests history
      try {
        const reqsRes = await api.get('/usdt/deposit/requests');
        setDepositRequests(reqsRes.data.requests || []);
      } catch (e) {
        setDepositRequests([]);
      }

      // Fetch internal wallet (for traders/merchants)
      try {
        const walletRes = await api.get('/wallet');
        setWallet(walletRes.data);
        
        const txRes = await api.get('/wallet/transactions');
        setTransactions(txRes.data.transactions || []);
      } catch (e) {
        // May not have internal wallet
      }
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Create new deposit request
  const createDepositRequest = async () => {
    setGenerating(true);
    try {
      const res = await api.post('/usdt/deposit/create-request', {});
      setActiveDepositRequest({
        request_id: res.data.request_id,
        deposit_comment: res.data.deposit_comment,
        ton_address: res.data.ton_address,
        expires_at: res.data.expires_at,
        status: res.data.status
      });
      setConfig(prev => ({
        ...prev, 
        platformTonAddress: res.data.ton_address,
        minDeposit: res.data.min_deposit || prev.minDeposit
      }));
      toast.success(`Заявка ${res.data.request_id} создана!`);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка создания заявки');
    } finally {
      setGenerating(false);
    }
  };

  // Create withdrawal request
  // STEP 1: Validate and show security modal
  const handleWithdraw = () => {
    if (!withdrawAmount || !withdrawAddress) {
      toast.error('Заполните все поля');
      return;
    }

    const amount = parseFloat(withdrawAmount);
    if (amount <= 0) {
      toast.error('Сумма должна быть больше 0');
      return;
    }

    // Close withdraw dialog and store pending data
    setShowWithdraw(false);
    setPendingWithdrawal({ amount, address: withdrawAddress });
    
    // Show security verification modal
    setTimeout(() => {
      setShowSecurityModal(true);
    }, 300);
  };

  // STEP 2: Execute withdrawal after security verification
  const handleSecurityVerified = async (securityData) => {
    if (!pendingWithdrawal) return;
    
    setWithdrawing(true);
    try {
      const res = await api.post('/usdt/withdrawal/create', {
        amount: pendingWithdrawal.amount,
        ton_address: pendingWithdrawal.address,
        verification_token: securityData.verificationToken
      });
      
      // Immediately update local balance state for instant feedback
      const withdrawnAmount = pendingWithdrawal.amount;
      setWallet(prev => prev ? {
        ...prev,
        available_balance_usdt: (prev.available_balance_usdt || 0) - withdrawnAmount,
        pending_withdrawal_usdt: (prev.pending_withdrawal_usdt || 0) + withdrawnAmount
      } : prev);
      
      toast.success(`Заявка на вывод ${withdrawnAmount} USDT создана! Баланс обновлён.`);
      setWithdrawAmount('');
      setWithdrawAddress('');
      setPendingWithdrawal(null);
      
      // Refresh data in background for consistency
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка создания заявки');
    } finally {
      setWithdrawing(false);
    }
  };

  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text);
    toast.success(`${label} скопирован!`);
  };

  // Transfer earnings to available balance (for traders)
  const handleTransferEarnings = async () => {
    setTransferringEarnings(true);
    try {
      const res = await api.post('/trader/withdraw-earnings');
      toast.success(`Переведено ${formatUSDT(res.data.withdrawn)} USDT на баланс!`);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка перевода средств');
    } finally {
      setTransferringEarnings(false);
    }
  };

  // Для трейдеров и мерчантов используем wallet (основной баланс из wallets коллекции)
  const balance = wallet?.available_balance_usdt || 0;
  const earned = wallet?.earned_balance_usdt || 0;
  const pendingIn = usdtWallet?.pending_deposit_usdt || 0;
  const pendingOut = wallet?.pending_withdrawal_usdt || usdtWallet?.pending_withdrawal_usdt || 0;
  const balanceRub = balance * config.usdtRubRate;

  const getStatusBadge = (status) => {
    const styles = {
      pending: 'bg-yellow-500/20 text-yellow-400',
      processing: 'bg-blue-500/20 text-blue-400',
      confirmed: 'bg-emerald-500/20 text-emerald-400',
      completed: 'bg-emerald-500/20 text-emerald-400',
      credited: 'bg-emerald-500/20 text-emerald-400',
      manual_review: 'bg-orange-500/20 text-orange-400',
      rejected: 'bg-red-500/20 text-red-400',
      cancelled: 'bg-zinc-500/20 text-zinc-400',
      expired: 'bg-zinc-500/20 text-zinc-400'
    };
    const labels = {
      pending: 'Ожидание',
      processing: 'Обработка',
      confirmed: 'Подтверждён',
      completed: 'Выполнен',
      credited: 'Зачислено',
      manual_review: 'На проверке',
      rejected: 'Отклонён',
      cancelled: 'Отменён',
      expired: 'Истёк'
    };
    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${styles[status] || styles.pending}`}>
        {labels[status] || status}
      </span>
    );
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-8 h-8 animate-spin text-orange-500" />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6" data-testid="unified-finances">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Coins className="w-6 h-6 text-emerald-400" />
              Финансы
            </h1>
            <p className="text-sm text-zinc-400 mt-1">USDT (TON Network)</p>
          </div>
          <div className="flex gap-2">
            {/* Кнопка Пополнить только для трейдеров */}
            {user?.role === 'trader' && (
              <Button onClick={() => setShowDeposit(true)} className="bg-emerald-500 hover:bg-emerald-600" data-testid="deposit-btn">
                <ArrowDownCircle className="w-4 h-4 mr-2" />
                Пополнить
              </Button>
            )}
            <Button onClick={() => setShowWithdraw(true)} variant="outline" data-testid="withdraw-btn">
              <ArrowUpCircle className="w-4 h-4 mr-2" />
              Вывести
            </Button>
            <Button onClick={fetchData} variant="ghost" size="icon">
              <RefreshCw className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 border-b border-zinc-800 pb-2 overflow-x-auto">
          <button
            onClick={() => setActiveTab('overview')}
            className={`px-4 py-2 rounded-lg transition-colors whitespace-nowrap ${
              activeTab === 'overview' ? 'bg-emerald-500 text-white' : 'text-zinc-400 hover:text-white'
            }`}
          >
            Обзор
          </button>
          {/* Заявки на депозит - только для трейдеров */}
          {user?.role === 'trader' && (
            <button
              onClick={() => setActiveTab('requests')}
              className={`px-4 py-2 rounded-lg transition-colors whitespace-nowrap ${
                activeTab === 'requests' ? 'bg-emerald-500 text-white' : 'text-zinc-400 hover:text-white'
              }`}
            >
              Заявки на депозит
              {depositRequests.filter(r => r.status === 'pending').length > 0 && (
                <span className="ml-2 bg-yellow-500 text-black text-xs px-2 py-0.5 rounded-full">
                  {depositRequests.filter(r => r.status === 'pending').length}
                </span>
              )}
            </button>
          )}
          {/* История депозитов - только для трейдеров */}
          {user?.role === 'trader' && (
            <button
              onClick={() => setActiveTab('deposits')}
              className={`px-4 py-2 rounded-lg transition-colors whitespace-nowrap ${
                activeTab === 'deposits' ? 'bg-emerald-500 text-white' : 'text-zinc-400 hover:text-white'
              }`}
            >
              История депозитов
            </button>
          )}
          <button
            onClick={() => setActiveTab('withdrawals')}
            className={`px-4 py-2 rounded-lg transition-colors whitespace-nowrap ${
              activeTab === 'withdrawals' ? 'bg-emerald-500 text-white' : 'text-zinc-400 hover:text-white'
            }`}
          >
            Выводы USDT (TON)
          </button>
        </div>

        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div className="space-y-4">
            {/* Earned Balance Card - only for traders with earnings */}
            {user?.role === 'trader' && earned > 0 && (
              <div className="bg-gradient-to-r from-amber-500/10 to-orange-500/10 border border-amber-500/30 rounded-xl p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-amber-500/20 flex items-center justify-center">
                      <TrendingUp className="w-5 h-5 text-amber-400" />
                    </div>
                    <div>
                      <div className="text-sm text-zinc-400">Заработано с ордеров</div>
                      <div className="text-xl font-bold text-amber-400">{formatUSDT(earned)} USDT</div>
                    </div>
                  </div>
                  <Button 
                    onClick={handleTransferEarnings}
                    disabled={transferringEarnings || earned <= 0}
                    className="bg-amber-500 hover:bg-amber-600"
                    data-testid="transfer-earnings-btn"
                  >
                    {transferringEarnings ? (
                      <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                    ) : (
                      <ArrowUpCircle className="w-4 h-4 mr-2" />
                    )}
                    Перевести на баланс
                  </Button>
                </div>
              </div>
            )}
            
            <div className={`grid ${user?.role === 'merchant' ? 'md:grid-cols-2' : 'md:grid-cols-3'} gap-4`}>
              {/* Всего внесено - только для трейдеров */}
              {user?.role === 'trader' && (
                <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4 text-center">
                  <div className="text-2xl font-bold text-emerald-400">
                    {formatUSDT(usdtWallet?.total_deposited_usdt)}
                  </div>
                  <div className="text-xs text-zinc-500">Всего внесено USDT</div>
                </div>
              )}
              <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4 text-center">
                <div className="text-2xl font-bold text-blue-400">
                  {formatUSDT(usdtWallet?.total_withdrawn_usdt)}
                </div>
                <div className="text-xs text-zinc-500">Всего выведено USDT</div>
              </div>
              {/* Заявок на депозит - только для трейдеров */}
              {user?.role === 'trader' && (
                <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4 text-center">
                  <div className="text-2xl font-bold text-yellow-400">{depositRequests.length}</div>
                  <div className="text-xs text-zinc-500">Заявок на депозит</div>
                </div>
              )}
              <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4 text-center">
                <div className="text-2xl font-bold text-purple-400">{withdrawals.length}</div>
                <div className="text-xs text-zinc-500">Выводов</div>
              </div>
            </div>
          </div>
        )}

        {/* Deposit Requests Tab - только для трейдеров */}
        {activeTab === 'requests' && user?.role === 'trader' && (
          <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
            <h3 className="font-semibold mb-4 flex items-center gap-2">
              <QrCode className="w-5 h-5 text-emerald-400" />
              История заявок на депозит
            </h3>
            
            {depositRequests.length === 0 ? (
              <div className="text-center py-8">
                <QrCode className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
                <p className="text-zinc-500">Нет заявок на депозит</p>
                <Button className="mt-4 bg-emerald-500 hover:bg-emerald-600" onClick={() => setShowDeposit(true)}>
                  Создать заявку
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                {depositRequests.map((req) => (
                  <div key={req.id} className="bg-zinc-800/50 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-3">
                        <span className="font-mono font-bold text-emerald-400">{req.request_id}</span>
                        {getStatusBadge(req.status)}
                      </div>
                      <span className="font-mono text-cyan-400">{req.deposit_comment}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-sm text-zinc-400">
                      <div>Создана: <span className="text-white">{new Date(req.created_at).toLocaleString()}</span></div>
                      <div>Истекает: <span className="text-white">{new Date(req.expires_at).toLocaleString()}</span></div>
                      {req.actual_amount_usdt && (
                        <div className="col-span-2 text-emerald-400">
                          Зачислено: {formatUSDT(req.actual_amount_usdt)} USDT
                        </div>
                      )}
                      {req.tx_hash && (
                        <div className="col-span-2 flex items-center gap-1">
                          TX: <span className="font-mono text-xs">{req.tx_hash?.slice(0, 24)}...</span>
                          <a 
                            href={`https://tonscan.org/tx/${req.tx_hash}`} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="text-blue-400 hover:text-blue-300"
                          >
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Deposits Tab - только для трейдеров */}
        {activeTab === 'deposits' && user?.role === 'trader' && (
          <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
            <h3 className="font-semibold mb-4 flex items-center gap-2">
              <ArrowDownCircle className="w-5 h-5 text-emerald-400" />
              История депозитов
            </h3>
            
            {deposits.length === 0 ? (
              <div className="text-center py-8 text-zinc-500">
                Нет депозитов
              </div>
            ) : (
              <div className="space-y-3">
                {deposits.map((dep) => (
                  <div key={dep.id} className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-lg">
                    <div className="flex items-center gap-3">
                      <ArrowDownCircle className="w-5 h-5 text-emerald-400" />
                      <div>
                        <div className="font-semibold text-emerald-400">+{formatUSDT(dep.amount_usdt)} USDT</div>
                        <div className="text-xs text-zinc-500">{new Date(dep.created_at).toLocaleString()}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      {getStatusBadge(dep.status)}
                      {dep.tx_hash && (
                        <a 
                          href={`https://tonscan.org/tx/${dep.tx_hash}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 mt-1"
                        >
                          {dep.tx_hash.slice(0, 12)}...
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Withdrawals Tab */}
        {activeTab === 'withdrawals' && (
          <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
            <h3 className="font-semibold mb-4 flex items-center gap-2">
              <ArrowUpCircle className="w-5 h-5 text-blue-400" />
              История выводов
            </h3>
            
            {withdrawals.length === 0 ? (
              <div className="text-center py-8 text-zinc-500">
                Нет выводов
              </div>
            ) : (
              <div className="space-y-3">
                {withdrawals.map((w) => (
                  <div key={w.id} className="p-4 bg-zinc-800/50 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-3">
                        <ArrowUpCircle className="w-5 h-5 text-blue-400" />
                        <div>
                          <div className="font-semibold text-blue-400">-{formatUSDT(w.amount_usdt)} USDT</div>
                          <div className="text-xs text-zinc-500">
                            Комиссия: {formatUSDT(w.total_fee_usdt)} USDT
                          </div>
                        </div>
                      </div>
                      {getStatusBadge(w.status)}
                    </div>
                    <div className="text-xs text-zinc-400 mt-2">
                      <div>Адрес: <span className="font-mono">{w.to_address?.slice(0, 24)}...</span></div>
                      <div>Дата: {new Date(w.created_at).toLocaleString()}</div>
                      {w.tx_hash && (
                        <a 
                          href={`https://tonscan.org/tx/${w.tx_hash}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-400 hover:text-blue-300 flex items-center gap-1 mt-1"
                        >
                          TX: {w.tx_hash.slice(0, 20)}...
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Deposit Modal - USDT TON */}
        {showDeposit && (
          <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50">
            <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 max-w-lg w-full max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold flex items-center gap-2">
                  <ArrowDownCircle className="w-5 h-5 text-emerald-400" />
                  Пополнение USDT (TON)
                </h2>
                <button onClick={() => setShowDeposit(false)} className="text-zinc-400 hover:text-white">
                  <XCircle className="w-6 h-6" />
                </button>
              </div>

              {!activeDepositRequest ? (
                <div className="text-center py-8">
                  <Coins className="w-16 h-16 text-emerald-400 mx-auto mb-4" />
                  <p className="text-zinc-400 mb-4">Создайте заявку на пополнение</p>
                  <p className="text-sm text-zinc-500 mb-6">
                    Система сгенерирует уникальный комментарий для перевода USDT в сети TON
                  </p>
                  <Button onClick={createDepositRequest} disabled={generating} className="bg-emerald-500 hover:bg-emerald-600">
                    {generating ? 'Создание...' : 'Создать заявку'}
                  </Button>
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Request ID Banner */}
                  <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-4 text-center">
                    <div className="text-sm text-zinc-400 mb-1">Номер заявки</div>
                    <div className="text-2xl font-bold text-emerald-400 font-mono">
                      {activeDepositRequest.request_id}
                    </div>
                  </div>

                  {/* Important Warning */}
                  <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4">
                    <div className="flex items-start gap-3">
                      <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="text-sm text-yellow-200 font-medium">
                          Обязательно укажите комментарий!
                        </p>
                        <p className="text-xs text-yellow-300/70 mt-1">
                          Без комментария депозит не будет зачислен автоматически
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-3">
                    {/* Comment */}
                    <div>
                      <label className="text-sm text-zinc-400 block mb-1">💬 Комментарий (ОБЯЗАТЕЛЬНО):</label>
                      <div className="flex items-center gap-2">
                        <code className="flex-1 bg-cyan-500/20 border border-cyan-500/30 px-3 py-3 rounded-lg text-xl font-mono font-bold text-cyan-400 text-center">
                          {activeDepositRequest.deposit_comment}
                        </code>
                        <Button size="sm" variant="outline" onClick={() => copyToClipboard(activeDepositRequest.deposit_comment, 'Комментарий')}>
                          <Copy className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>

                    {/* TON Address */}
                    <div>
                      <label className="text-sm text-zinc-400 block mb-1">📍 TON адрес для USDT:</label>
                      <div className="flex items-center gap-2">
                        <code className="flex-1 bg-zinc-800 px-3 py-2 rounded-lg text-sm font-mono break-all">
                          {activeDepositRequest.ton_address || config.platformTonAddress}
                        </code>
                        <Button size="sm" variant="outline" onClick={() => copyToClipboard(activeDepositRequest.ton_address || config.platformTonAddress, 'Адрес')}>
                          <Copy className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  </div>

                  {/* Instructions */}
                  <div className="bg-zinc-800/50 rounded-xl p-4 space-y-2 text-sm">
                    <p className="font-medium text-white">📱 Инструкция:</p>
                    <ol className="list-decimal list-inside space-y-1 text-zinc-400">
                      <li>Откройте кошелёк TON (Tonkeeper, Wallet и др.)</li>
                      <li>Выберите <strong className="text-emerald-400">USDT (TON)</strong> для отправки</li>
                      <li>Вставьте адрес выше</li>
                      <li>В поле «Комментарий» введите: <strong className="text-cyan-400">{activeDepositRequest.deposit_comment}</strong></li>
                      <li>Введите любую сумму и отправьте</li>
                    </ol>
                  </div>

                  {/* Timer and Info */}
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div className="bg-zinc-800/50 rounded-lg p-3">
                      <div className="flex items-center gap-2 text-zinc-400 mb-1">
                        <Clock className="w-4 h-4" />
                        Действует до:
                      </div>
                      <div className="font-medium text-white">
                        {new Date(activeDepositRequest.expires_at).toLocaleString()}
                      </div>
                    </div>
                    <div className="bg-zinc-800/50 rounded-lg p-3">
                      <div className="flex items-center gap-2 text-zinc-400 mb-1">
                        <DollarSign className="w-4 h-4" />
                        Минимум:
                      </div>
                      <div className="font-medium text-emerald-400">
                        Без ограничений
                      </div>
                    </div>
                  </div>

                  {/* Status */}
                  <div className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-lg">
                    <span className="text-zinc-400">Статус заявки:</span>
                    {getStatusBadge(activeDepositRequest.status)}
                  </div>

                  {/* New Request Button */}
                  <Button variant="outline" className="w-full" onClick={createDepositRequest} disabled={generating}>
                    <RefreshCw className={`w-4 h-4 mr-2 ${generating ? 'animate-spin' : ''}`} />
                    Создать новую заявку
                  </Button>

                  {/* Help Text */}
                  <p className="text-xs text-zinc-500 text-center">
                    Зачисление в течение 1-2 минут после отправки. При проблемах напишите в поддержку с номером заявки.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Withdrawal Modal */}
        {showWithdraw && (
          <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50">
            <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 max-w-md w-full">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold flex items-center gap-2">
                  <ArrowUpCircle className="w-5 h-5 text-blue-400" />
                  Вывод USDT (TON)
                </h2>
                <button onClick={() => setShowWithdraw(false)} className="text-zinc-400 hover:text-white">
                  <XCircle className="w-6 h-6" />
                </button>
              </div>

              <div className="space-y-4">
                <div className="bg-zinc-800/50 rounded-lg p-3">
                  <div className="text-sm text-zinc-400">Доступно для вывода:</div>
                  <div className="text-2xl font-bold text-emerald-400">{formatUSDT(balance)} USDT</div>
                  <div className="text-sm text-zinc-400">≈ {Math.round(balanceRub).toLocaleString('ru-RU')} ₽</div>
                </div>

                <div>
                  <label className="text-sm text-zinc-400 block mb-1">TON адрес получателя:</label>
                  <Input
                    value={withdrawAddress}
                    onChange={(e) => setWithdrawAddress(e.target.value)}
                    placeholder="UQ... или EQ..."
                    className="bg-zinc-800 border-zinc-700"
                  />
                </div>

                <div>
                  <label className="text-sm text-zinc-400 block mb-1">Сумма USDT:</label>
                  <Input
                    type="number"
                    value={withdrawAmount}
                    onChange={(e) => setWithdrawAmount(e.target.value)}
                    placeholder="Введите сумму"
                    className="bg-zinc-800 border-zinc-700"
                  />
                </div>

                <div className="bg-zinc-800/50 rounded-lg p-3 text-sm space-y-1">
                  <div className="flex justify-between">
                    <span className="text-zinc-400">Доступно:</span>
                    <span className="text-green-400">{wallet?.available_balance_usdt?.toFixed(2) || 0} USDT</span>
                  </div>
                  <div className="flex justify-between text-zinc-500">
                    <span>Комиссия:</span>
                    <span>Без комиссии</span>
                  </div>
                </div>

                {/* Security notice */}
                <div className="bg-orange-500/10 border border-orange-500/20 rounded-lg p-3 flex items-start gap-2">
                  <Shield className="w-4 h-4 text-orange-400 flex-shrink-0 mt-0.5" />
                  <div className="text-xs text-orange-300">
                    После нажатия потребуется подтвердить операцию паролем и кодом 2FA (если включён)
                  </div>
                </div>

                <Button 
                  onClick={handleWithdraw} 
                  disabled={withdrawing || !withdrawAmount || !withdrawAddress}
                  className="w-full bg-blue-500 hover:bg-blue-600"
                >
                  <Shield className="w-4 h-4 mr-2" />
                  {withdrawing ? 'Создание заявки...' : 'Далее'}
                </Button>
              </div>
            </div>
          </div>
        )}
        
        {/* Security Verification Modal */}
        <SecurityVerification
          open={showSecurityModal}
          onOpenChange={(open) => {
            setShowSecurityModal(open);
            if (!open) setPendingWithdrawal(null);
          }}
          onVerified={handleSecurityVerified}
          title="Подтверждение вывода"
          description={pendingWithdrawal ? 
            `Вы собираетесь вывести ${formatUSDT(pendingWithdrawal.amount)} USDT на адрес ${pendingWithdrawal.address.slice(0, 10)}...` : 
            'Подтвердите операцию'
          }
          actionLabel="Подтвердить вывод"
        />
      </div>
    </DashboardLayout>
  );
};

export default UnifiedFinances;
