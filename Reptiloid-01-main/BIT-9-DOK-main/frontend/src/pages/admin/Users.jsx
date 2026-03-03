import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import DashboardLayout from '@/components/DashboardLayout';
import { api, formatDate, useAuth } from '@/lib/auth';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
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
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { 
  RefreshCw, Search, Users, Shield, Ban, CheckCircle, Clock, XCircle, 
  UserCheck, Trash2, MessageCircle, MoreVertical, Settings, Key, Copy, ShieldCheck,
  BarChart3, Wallet, AlertTriangle, Percent, CreditCard, Phone, Smartphone, QrCode, Globe, Banknote, Plus, Save, Lock, Unlock
} from 'lucide-react';

// Методы оплаты для inline компонента
const PAYMENT_METHODS = {
  sbp: { name: 'SBP', icon: Phone, color: 'text-blue-400' },
  card: { name: 'Card', icon: CreditCard, color: 'text-emerald-400' },
  sim: { name: 'SIM', icon: Smartphone, color: 'text-orange-400' },
  mono_bank: { name: 'Mono Bank', icon: Banknote, color: 'text-purple-400' },
  sng_sbp: { name: 'SNG-SBP', icon: Globe, color: 'text-cyan-400' },
  sng_card: { name: 'SNG-Card', icon: Globe, color: 'text-teal-400' },
  qr_code: { name: 'QR-code', icon: QrCode, color: 'text-pink-400' },
};

// Inline компонент для настройки комиссий по методам оплаты (встроенный в диалог)
const MerchantMethodCommissionsInline = ({ merchantId, merchantName }) => {
  const [methods, setMethods] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [selectedMethod, setSelectedMethod] = useState('sbp');

  useEffect(() => {
    if (merchantId) {
      fetchCommissions();
    }
  }, [merchantId]);

  const fetchCommissions = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/admin/merchants/${merchantId}/method-commissions`);
      setMethods(res.data.methods || []);
    } catch (error) {
      console.error('Ошибка загрузки комиссий');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put(`/admin/merchants/${merchantId}/method-commissions`, {
        methods: methods
      });
      toast.success('Настройки комиссий сохранены');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка сохранения');
    } finally {
      setSaving(false);
    }
  };

  const addMethod = () => {
    if (methods.find(m => m.payment_method === selectedMethod)) {
      toast.error('Этот метод уже добавлен');
      return;
    }
    setMethods([...methods, {
      payment_method: selectedMethod,
      intervals: [{ min_amount: 100, max_amount: 999, percent: 15 }]
    }]);
  };

  const removeMethod = (index) => {
    setMethods(methods.filter((_, i) => i !== index));
  };

  const addInterval = (methodIndex) => {
    const newMethods = [...methods];
    const lastInterval = newMethods[methodIndex].intervals.slice(-1)[0];
    const newMin = lastInterval ? lastInterval.max_amount + 1 : 100;
    newMethods[methodIndex].intervals.push({
      min_amount: newMin,
      max_amount: newMin + 4999,
      percent: lastInterval ? Math.max(lastInterval.percent - 0.5, 1) : 10
    });
    setMethods(newMethods);
  };

  const removeInterval = (methodIndex, intervalIndex) => {
    const newMethods = [...methods];
    newMethods[methodIndex].intervals = newMethods[methodIndex].intervals.filter((_, i) => i !== intervalIndex);
    setMethods(newMethods);
  };

  const updateInterval = (methodIndex, intervalIndex, field, value) => {
    const newMethods = [...methods];
    newMethods[methodIndex].intervals[intervalIndex][field] = parseFloat(value) || 0;
    setMethods(newMethods);
  };

  if (loading) {
    return (
      <div className="flex justify-center py-4">
        <div className="w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-3 border-t border-zinc-700 pt-4 mt-4">
      <div className="flex items-center gap-2 text-sm font-medium text-amber-400">
        <Percent className="w-4 h-4" />
        Комиссии по методам оплаты (Тип 1)
      </div>

      {/* Добавить метод */}
      <div className="flex gap-2">
        <Select value={selectedMethod} onValueChange={setSelectedMethod}>
          <SelectTrigger className="bg-zinc-950 border-zinc-800 flex-1 h-9">
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="bg-zinc-900 border-zinc-800">
            {Object.entries(PAYMENT_METHODS).map(([key, method]) => {
              const Icon = method.icon;
              const isAdded = methods.find(m => m.payment_method === key);
              return (
                <SelectItem key={key} value={key} disabled={isAdded}>
                  <div className="flex items-center gap-2">
                    <Icon className={`w-4 h-4 ${method.color}`} />
                    <span>{method.name}</span>
                    {isAdded && <span className="text-xs text-zinc-500">(добавлен)</span>}
                  </div>
                </SelectItem>
              );
            })}
          </SelectContent>
        </Select>
        <Button onClick={addMethod} size="sm" className="bg-emerald-500 hover:bg-emerald-600 h-9">
          <Plus className="w-4 h-4" />
        </Button>
      </div>

      {/* Список методов */}
      <div className="max-h-[300px] overflow-y-auto space-y-3 pr-1">
        {methods.length === 0 ? (
          <div className="text-center py-4 text-zinc-500 text-sm">
            Нет настроенных методов. Добавьте метод оплаты.
          </div>
        ) : (
          methods.map((method, methodIndex) => {
            const methodInfo = PAYMENT_METHODS[method.payment_method];
            const Icon = methodInfo?.icon || CreditCard;
            
            return (
              <Card key={methodIndex} className="bg-zinc-800/50 border-zinc-700">
                <CardContent className="p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm font-medium">
                      <Icon className={`w-4 h-4 ${methodInfo?.color || 'text-zinc-400'}`} />
                      {methodInfo?.name || method.payment_method}
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => removeMethod(methodIndex)}
                      className="text-red-400 hover:text-red-300 h-6 w-6 p-0"
                    >
                      <Trash2 className="w-3 h-3" />
                    </Button>
                  </div>
                  
                  {/* Заголовки интервалов */}
                  <div className="grid grid-cols-4 gap-1 text-[10px] text-zinc-500">
                    <span>От (₽)</span>
                    <span>До (₽)</span>
                    <span>Процент (%)</span>
                    <span></span>
                  </div>
                  
                  {/* Интервалы */}
                  {method.intervals.map((interval, intervalIndex) => (
                    <div key={intervalIndex} className="grid grid-cols-4 gap-1 items-center">
                      <Input
                        type="number"
                        value={interval.min_amount}
                        onChange={(e) => updateInterval(methodIndex, intervalIndex, 'min_amount', e.target.value)}
                        className="bg-zinc-950 border-zinc-700 h-7 text-xs"
                      />
                      <Input
                        type="number"
                        value={interval.max_amount}
                        onChange={(e) => updateInterval(methodIndex, intervalIndex, 'max_amount', e.target.value)}
                        className="bg-zinc-950 border-zinc-700 h-7 text-xs"
                      />
                      <Input
                        type="number"
                        step="0.1"
                        value={interval.percent}
                        onChange={(e) => updateInterval(methodIndex, intervalIndex, 'percent', e.target.value)}
                        className="bg-zinc-950 border-zinc-700 h-7 text-xs"
                      />
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeInterval(methodIndex, intervalIndex)}
                        className="text-red-400 hover:text-red-300 h-7 w-7 p-0"
                        disabled={method.intervals.length === 1}
                      >
                        <Trash2 className="w-3 h-3" />
                      </Button>
                    </div>
                  ))}
                  
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => addInterval(methodIndex)}
                    className="w-full h-7 text-xs border-dashed border-zinc-600 text-zinc-400"
                  >
                    <Plus className="w-3 h-3 mr-1" />
                    Добавить интервал
                  </Button>
                </CardContent>
              </Card>
            );
          })
        )}
      </div>

      {/* Пример */}
      {methods.length > 0 && (
        <div className="bg-blue-500/10 border border-blue-500/30 rounded p-2 text-xs text-blue-300">
          <strong>Пример:</strong> Если выбран метод SBP и сумма заявки 3000₽, система найдёт интервал 1000-5000₽ и применит соответствующий процент.
        </div>
      )}

      {/* Кнопка сохранения */}
      <Button 
        onClick={handleSave} 
        disabled={saving} 
        className="w-full bg-emerald-500 hover:bg-emerald-600"
        data-testid="save-method-commissions-btn"
      >
        {saving ? (
          <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
        ) : (
          <Save className="w-4 h-4 mr-2" />
        )}
        Сохранить комиссии по методам
      </Button>
    </div>
  );
};

// Inline компонент для настройки комиссий трейдера по интервалам сумм
const TraderFeeIntervalsInline = ({ traderId, traderName, onClose }) => {
  const [intervals, setIntervals] = useState([]);
  const [defaultPercent, setDefaultPercent] = useState(10);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (traderId) {
      fetchFeeSettings();
    }
  }, [traderId]);

  const fetchFeeSettings = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/admin/traders/${traderId}/fee-settings`);
      setIntervals(res.data.intervals || []);
      setDefaultPercent(res.data.default_percent || 10);
    } catch (error) {
      console.error('Ошибка загрузки настроек');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put(`/admin/traders/${traderId}/fee-settings`, {
        intervals: intervals,
        default_percent: defaultPercent
      });
      toast.success('Комиссии трейдера сохранены');
      if (onClose) onClose();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка сохранения');
    } finally {
      setSaving(false);
    }
  };

  const addInterval = () => {
    const lastInterval = intervals.slice(-1)[0];
    const newMin = lastInterval ? lastInterval.max_amount + 1 : 100;
    setIntervals([...intervals, {
      min_amount: newMin,
      max_amount: newMin + 4999,
      percent: lastInterval ? Math.max(lastInterval.percent - 1, 1) : 10
    }]);
  };

  const removeInterval = (index) => {
    setIntervals(intervals.filter((_, i) => i !== index));
  };

  const updateInterval = (index, field, value) => {
    const newIntervals = [...intervals];
    newIntervals[index][field] = parseFloat(value) || 0;
    setIntervals(newIntervals);
  };

  if (loading) {
    return (
      <div className="flex justify-center py-4">
        <div className="w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="text-sm text-zinc-400">
        Настройте процент комиссии трейдера в зависимости от суммы заказа
      </div>

      {/* Процент по умолчанию */}
      <div className="bg-zinc-800 rounded-lg p-3">
        <label className="text-sm text-zinc-400 mb-2 block">Процент по умолчанию (если сумма не попадает в интервалы)</label>
        <Input
          type="number"
          min="0"
          max="100"
          step="0.5"
          value={defaultPercent}
          onChange={(e) => setDefaultPercent(parseFloat(e.target.value) || 0)}
          className="bg-zinc-950 border-zinc-700 w-32"
        />
      </div>

      {/* Интервалы */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-sm font-medium text-cyan-400">Интервалы сумм</label>
          <Button onClick={addInterval} size="sm" className="bg-cyan-500 hover:bg-cyan-600 h-8">
            <Plus className="w-4 h-4 mr-1" />
            Добавить
          </Button>
        </div>

        {intervals.length === 0 ? (
          <div className="text-center py-4 text-zinc-500 text-sm bg-zinc-800/50 rounded-lg">
            Интервалы не настроены. Будет использоваться процент по умолчанию.
          </div>
        ) : (
          <div className="space-y-2 max-h-[250px] overflow-y-auto pr-1">
            {/* Заголовки */}
            <div className="grid grid-cols-4 gap-2 text-xs text-zinc-500 px-1">
              <span>От (₽)</span>
              <span>До (₽)</span>
              <span>Процент (%)</span>
              <span></span>
            </div>
            
            {intervals.map((interval, index) => (
              <div key={index} className="grid grid-cols-4 gap-2 items-center bg-zinc-800/50 rounded p-2">
                <Input
                  type="number"
                  value={interval.min_amount}
                  onChange={(e) => updateInterval(index, 'min_amount', e.target.value)}
                  className="bg-zinc-950 border-zinc-700 h-8 text-sm"
                />
                <Input
                  type="number"
                  value={interval.max_amount}
                  onChange={(e) => updateInterval(index, 'max_amount', e.target.value)}
                  className="bg-zinc-950 border-zinc-700 h-8 text-sm"
                />
                <Input
                  type="number"
                  step="0.5"
                  value={interval.percent}
                  onChange={(e) => updateInterval(index, 'percent', e.target.value)}
                  className="bg-zinc-950 border-zinc-700 h-8 text-sm"
                />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => removeInterval(index)}
                  className="text-red-400 hover:text-red-300 h-8 w-8 p-0"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Пример */}
      <div className="bg-cyan-500/10 border border-cyan-500/30 rounded p-3 text-xs text-cyan-300">
        <strong>Пример:</strong> Если заказ на 3000₽ и настроен интервал 1000-5000₽ → 8%, то трейдер получит 8% от покупки клиента мерчанта.
      </div>

      {/* Кнопка сохранения */}
      <Button 
        onClick={handleSave} 
        disabled={saving} 
        className="w-full bg-cyan-500 hover:bg-cyan-600"
        data-testid="save-trader-fee-btn"
      >
        {saving ? (
          <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
        ) : (
          <Save className="w-4 h-4 mr-2" />
        )}
        Сохранить комиссии трейдера
      </Button>
    </div>
  );
};

const AdminUsers = () => {
  const { user: currentUser } = useAuth();
  const isSupport = currentUser?.role === 'support';
  const [users, setUsers] = useState([]);
  const [pendingTraders, setPendingTraders] = useState([]);
  const [pendingMerchants, setPendingMerchants] = useState([]);
  const [merchants, setMerchants] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [roleFilter, setRoleFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [processingId, setProcessingId] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [chatDialog, setChatDialog] = useState(null);
  const [chatMessage, setChatMessage] = useState('');
  const [resetPasswordDialog, setResetPasswordDialog] = useState(null);
  const [newPassword, setNewPassword] = useState('');
  const [trustUpdating, setTrustUpdating] = useState(null);
  // Статистика пользователя
  const [statsDialog, setStatsDialog] = useState(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [userStats, setUserStats] = useState(null);
  // Финансовая модель мерчанта
  const [feeSettingsDialog, setFeeSettingsDialog] = useState(null);
  const [feeSettings, setFeeSettings] = useState({
    fee_model: 'customer_pays',
    total_fee_percent: 30
  });
  // Настройки комиссии трейдера
  const [traderFeeDialog, setTraderFeeDialog] = useState(null);
  
  // Проверка и разморозка баланса трейдера
  const [lockedCheckDialog, setLockedCheckDialog] = useState(null);
  const [lockedCheckData, setLockedCheckData] = useState(null);
  const [lockedCheckLoading, setLockedCheckLoading] = useState(false);
  const [unfreezeAmount, setUnfreezeAmount] = useState('');
  const [unfreezeReason, setUnfreezeReason] = useState('');
  const [unfreezeLoading, setUnfreezeLoading] = useState(false);

  // Функция для открытия диалога проверки баланса
  const openLockedCheckDialog = async (user) => {
    // Сначала получаем trader данные
    const trader = await api.get('/admin/traders').then(res => 
      res.data.traders?.find(t => t.user_id === user.id)
    ).catch(() => null);
    
    if (!trader) {
      toast.error('Не удалось найти трейдера');
      return;
    }
    
    setLockedCheckDialog({ user, trader });
    setLockedCheckData(null);
    setLockedCheckLoading(true);
    setUnfreezeAmount('');
    setUnfreezeReason('');
    
    try {
      const res = await api.get(`/admin/traders/${trader.id}/locked-check`);
      setLockedCheckData(res.data);
      // Автозаполнение суммы разницей, если есть
      if (res.data.has_mismatch && res.data.difference > 0) {
        setUnfreezeAmount(res.data.difference.toString());
      }
    } catch (error) {
      toast.error('Ошибка проверки баланса');
      setLockedCheckData({ error: true });
    } finally {
      setLockedCheckLoading(false);
    }
  };

  // Функция разморозки баланса
  const handleUnfreeze = async () => {
    if (!lockedCheckDialog?.trader?.id || !unfreezeAmount || !unfreezeReason.trim()) {
      toast.error('Укажите сумму и причину');
      return;
    }
    
    setUnfreezeLoading(true);
    try {
      const res = await api.post(
        `/admin/traders/${lockedCheckDialog.trader.id}/unfreeze?amount=${unfreezeAmount}&reason=${encodeURIComponent(unfreezeReason)}`
      );
      toast.success(res.data.message || 'Баланс разморожен');
      setLockedCheckDialog(null);
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка разморозки');
    } finally {
      setUnfreezeLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
    fetchPendingTraders();
    fetchPendingMerchants();
    fetchMerchants();
  }, [roleFilter]);

  const fetchUsers = async () => {
    try {
      const params = { limit: 100 };
      if (roleFilter !== 'all') params.role = roleFilter;
      
      const res = await api.get('/admin/users', { params });
      setUsers(res.data.users || []);
      setTotal(res.data.total || 0);
    } catch (error) {
      toast.error('Ошибка загрузки пользователей');
    } finally {
      setLoading(false);
    }
  };

  const fetchPendingTraders = async () => {
    try {
      const res = await api.get('/admin/traders/pending');
      setPendingTraders(res.data.traders || []);
    } catch (error) {
      console.error('Error fetching pending traders:', error);
    }
  };

  const fetchMerchants = async () => {
    try {
      const res = await api.get('/admin/merchants');
      setMerchants(res.data.merchants || []);
    } catch (error) {
      console.error('Error fetching merchants:', error);
    }
  };

  const fetchPendingMerchants = async () => {
    try {
      const res = await api.get('/admin/merchants/pending');
      setPendingMerchants(res.data.merchants || []);
    } catch (error) {
      console.error('Error fetching pending merchants:', error);
    }
  };

  const approveTrader = async (userId) => {
    setProcessingId(userId);
    try {
      await api.post(`/admin/traders/${userId}/approve`);
      toast.success('Трейдер одобрен и активирован');
      fetchUsers();
      fetchPendingTraders();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка одобрения');
    } finally {
      setProcessingId(null);
    }
  };

  const rejectTrader = async (userId) => {
    setProcessingId(userId);
    try {
      await api.post(`/admin/traders/${userId}/reject`);
      toast.success('Заявка отклонена');
      fetchUsers();
      fetchPendingTraders();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка отклонения');
    } finally {
      setProcessingId(null);
    }
  };

  const approveMerchant = async (userId) => {
    setProcessingId(userId);
    try {
      await api.post(`/admin/merchants/${userId}/approve`);
      toast.success('Мерчант одобрен и активирован');
      fetchUsers();
      fetchPendingMerchants();
      fetchMerchants();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка одобрения');
    } finally {
      setProcessingId(null);
    }
  };

  const rejectMerchant = async (userId) => {
    setProcessingId(userId);
    try {
      await api.post(`/admin/merchants/${userId}/reject`);
      toast.success('Заявка мерчанта отклонена');
      fetchUsers();
      fetchPendingMerchants();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка отклонения');
    } finally {
      setProcessingId(null);
    }
  };

  const toggleUserActive = async (userId) => {
    setProcessingId(userId);
    try {
      const res = await api.post(`/admin/users/${userId}/toggle-active`);
      toast.success(res.data.is_active ? 'Пользователь активирован' : 'Пользователь заблокирован');
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка');
    } finally {
      setProcessingId(null);
    }
  };

  const deleteUser = async (userId) => {
    setProcessingId(userId);
    try {
      await api.delete(`/admin/users/${userId}`);
      toast.success('Пользователь удалён');
      setDeleteConfirm(null);
      fetchUsers();
      fetchPendingTraders();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка удаления');
    } finally {
      setProcessingId(null);
    }
  };

  const toggleUserTrust = async (user) => {
    setTrustUpdating(user.id);
    try {
      const newTrustStatus = !user.withdrawal_auto_approve;
      await api.put(`/admin/users/${user.id}/trust?trusted=${newTrustStatus}`);
      toast.success(newTrustStatus ? 'Доверие включено — автовывод без подтверждения' : 'Доверие отключено — вывод только с подтверждением');
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка');
    } finally {
      setTrustUpdating(null);
    }
  };

  // Открыть статистику пользователя
  const openStatsDialog = async (user) => {
    setStatsDialog(user);
    setStatsLoading(true);
    setUserStats(null);
    try {
      const res = await api.get(`/admin/users/${user.id}/stats`);
      setUserStats(res.data);
    } catch (error) {
      toast.error('Ошибка загрузки статистики');
      setUserStats({ error: true });
    } finally {
      setStatsLoading(false);
    }
  };

  const openChatWithTrader = async (user) => {
    // Создаём тикет для общения с пользователем
    try {
      const parts = chatMessage.split('\n');
      const subject = parts[0] || `Сообщение для ${user.nickname || user.login}`;
      const message = parts.slice(1).join('\n') || 'Здравствуйте!';
      
      const res = await api.post('/tickets', {
        subject: subject,
        message: message,
        user_id: user.id
      });
      toast.success('Тикет создан');
      setChatDialog(null);
      setChatMessage('');
      // Перенаправляем в чат
      window.location.href = `/support/${res.data.ticket_id}`;
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка отправки');
    }
  };

  const resetUserPassword = async () => {
    if (!resetPasswordDialog || !newPassword) return;
    
    if (newPassword.length < 6) {
      toast.error('Пароль должен быть не менее 6 символов');
      return;
    }
    
    setProcessingId(resetPasswordDialog.id);
    try {
      await api.post(`/admin/users/${resetPasswordDialog.id}/reset-password`, {
        new_password: newPassword
      });
      toast.success('Пароль сброшен');
      setResetPasswordDialog(null);
      setNewPassword('');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка сброса пароля');
    } finally {
      setProcessingId(null);
    }
  };

  // ================== ФИНАНСОВАЯ МОДЕЛЬ МЕРЧАНТА ==================
  const openFeeSettingsDialog = async (user) => {
    const merchant = merchants.find(m => m.user_id === user.id);
    if (!merchant) {
      toast.error('Мерчант не найден');
      return;
    }
    
    try {
      const res = await api.get(`/admin/merchants/${merchant.id}/fee-settings`);
      setFeeSettings({
        fee_model: res.data.fee_model || 'customer_pays',
        total_fee_percent: res.data.total_fee_percent || 30
      });
      setFeeSettingsDialog({ user, merchant, merchantName: res.data.merchant_name });
    } catch (error) {
      // Если настройки не найдены, используем дефолтные
      setFeeSettings({
        fee_model: merchant.fee_model || 'customer_pays',
        total_fee_percent: merchant.total_fee_percent || 30
      });
      setFeeSettingsDialog({ user, merchant, merchantName: merchant.company_name || user.nickname });
    }
  };

  const saveFeeSettings = async () => {
    if (!feeSettingsDialog?.merchant) return;
    
    setProcessingId(feeSettingsDialog.user.id);
    try {
      await api.put(`/admin/merchants/${feeSettingsDialog.merchant.id}/fee-settings`, feeSettings);
      toast.success(`Финансовая модель обновлена: ${feeSettings.fee_model === 'merchant_pays' ? 'Мерчант платит' : 'Покупатель платит'}`);
      setFeeSettingsDialog(null);
      fetchMerchants();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка сохранения настроек');
    } finally {
      setProcessingId(null);
    }
  };

  // ================== НАСТРОЙКИ КОМИССИИ ТРЕЙДЕРА ==================
  const openTraderFeeDialog = async (user) => {
    try {
      // Сначала найдём trader профиль
      const usersRes = await api.get('/admin/users');
      const traders = await api.get('/admin/traders');
      const trader = traders.data.traders?.find(t => t.user_id === user.id);
      
      if (!trader) {
        toast.error('Профиль трейдера не найден');
        return;
      }
      
      const res = await api.get(`/admin/traders/${trader.id}/fee-settings`);
      setTraderFeeDialog({ user, trader, traderName: res.data.trader_name });
    } catch (error) {
      // Если настройки не найдены, показываем диалог с дефолтными значениями
      const traders = await api.get('/admin/traders');
      const trader = traders.data.traders?.find(t => t.user_id === user.id);
      setTraderFeeDialog({ user, trader, traderName: user.nickname });
      if (!trader) {
        toast.error('Профиль трейдера не найден');
      }
    }
  };

  const copyToClipboard = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success(`Скопировано: ${text}`);
    } catch (err) {
      // Fallback для случаев когда Clipboard API недоступен
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      try {
        document.execCommand('copy');
        toast.success(`Скопировано: ${text}`);
      } catch (e) {
        toast.error('Не удалось скопировать');
      }
      document.body.removeChild(textarea);
    }
  };

  const getMerchantCommission = (userId) => {
    const merchant = merchants.find(m => m.user_id === userId);
    return merchant?.commission_percent;
  };

  const filteredUsers = users.filter(user => {
    if (!searchQuery) return true;
    const searchLower = searchQuery.toLowerCase();
    return (user.login && user.login.toLowerCase().includes(searchLower)) ||
           (user.nickname && user.nickname.toLowerCase().includes(searchLower)) ||
           user.id.toLowerCase().includes(searchLower);
  });

  const getRoleLabel = (role) => {
    const labels = { trader: 'Трейдер', merchant: 'Мерчант', admin: 'Админ', support: 'Саппорт' };
    return labels[role] || role;
  };

  const getRoleColor = (role) => {
    const colors = {
      trader: 'bg-blue-500/20 text-blue-400',
      merchant: 'bg-purple-500/20 text-purple-400',
      admin: 'bg-red-500/20 text-red-400',
      support: 'bg-orange-500/20 text-orange-400',
    };
    return colors[role] || 'bg-zinc-500/20 text-zinc-400';
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-[60vh]">
          <div className="animate-spin w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full" />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold font-['Chivo']">Пользователи</h1>
            <p className="text-zinc-400 text-sm">Всего: {total}</p>
          </div>
          <div className="flex gap-2">
            {/* Управление персоналом - только для админа */}
            {!isSupport && (
              <Link to="/admin/staff">
                <Button variant="outline" className="border-zinc-800">
                  <Shield className="w-4 h-4 mr-2" />
                  Управление персоналом
                </Button>
              </Link>
            )}
            <Button variant="outline" onClick={() => { fetchUsers(); fetchPendingTraders(); }} className="border-zinc-800">
              <RefreshCw className="w-4 h-4 mr-2" />
              Обновить
            </Button>
          </div>
        </div>

        {/* Pending Traders Section */}
        {pendingTraders.length > 0 && (
          <div className="bg-gradient-to-r from-orange-500/10 to-yellow-500/10 border border-orange-500/30 rounded-xl p-6">
            <div className="flex items-center gap-2 mb-4">
              <Clock className="w-5 h-5 text-orange-400" />
              <h2 className="text-lg font-semibold">
                Заявки на регистрацию трейдеров
                <span className="ml-2 px-2 py-0.5 bg-orange-500 text-white text-sm rounded-full">
                  {pendingTraders.length}
                </span>
              </h2>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {pendingTraders.map((trader) => (
                <Card key={trader.id} className="bg-zinc-900 border-orange-500/50">
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between mb-3">
                      <span className="font-['JetBrains_Mono'] text-xs text-zinc-500">
                        {trader.id.substring(0, 12)}...
                      </span>
                      <Badge variant="outline" className="bg-orange-500/20 text-orange-400 border-orange-500/50">
                        <Clock className="w-3 h-3 mr-1" />
                        Ожидает
                      </Badge>
                    </div>

                    <div className="font-medium mb-1 truncate">{trader.nickname || trader.login}</div>
                    <div className="text-sm text-zinc-500 mb-1">@{trader.login}</div>
                    <div className="text-sm text-zinc-400 mb-4">
                      Зарегистрирован: {formatDate(trader.created_at)}
                    </div>

                    <div className="flex gap-2">
                      <Button
                        onClick={() => approveTrader(trader.id)}
                        disabled={processingId === trader.id}
                        className="flex-1 bg-emerald-500 hover:bg-emerald-600"
                        size="sm"
                      >
                        {processingId === trader.id ? (
                          <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        ) : (
                          <>
                            <UserCheck className="w-4 h-4 mr-1" />
                            Одобрить
                          </>
                        )}
                      </Button>
                      <Button
                        onClick={() => rejectTrader(trader.id)}
                        disabled={processingId === trader.id}
                        variant="outline"
                        className="border-red-500/50 text-red-400 hover:bg-red-500/10"
                        size="sm"
                      >
                        <XCircle className="w-4 h-4" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* Pending Merchants Section */}
        {pendingMerchants.length > 0 && (
          <div className="bg-gradient-to-r from-purple-500/10 to-pink-500/10 border border-purple-500/30 rounded-xl p-6">
            <div className="flex items-center gap-2 mb-4">
              <Clock className="w-5 h-5 text-purple-400" />
              <h2 className="text-lg font-semibold">
                Заявки на регистрацию мерчантов
                <span className="ml-2 px-2 py-0.5 bg-purple-500 text-white text-sm rounded-full">
                  {pendingMerchants.length}
                </span>
              </h2>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {pendingMerchants.map((merchant) => (
                <Card key={merchant.id || merchant.user_id} className="bg-zinc-900 border-purple-500/50">
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between mb-3">
                      <span className="font-['JetBrains_Mono'] text-xs text-zinc-500">
                        {(merchant.user_id || merchant.id)?.substring(0, 12)}...
                      </span>
                      <Badge variant="outline" className="bg-purple-500/20 text-purple-400 border-purple-500/50">
                        <Clock className="w-3 h-3 mr-1" />
                        Ожидает
                      </Badge>
                    </div>

                    <div className="font-medium mb-1 truncate">{merchant.nickname || merchant.login}</div>
                    <div className="text-sm text-zinc-500 mb-1">@{merchant.login}</div>
                    {merchant.company_name && (
                      <div className="text-sm text-zinc-400 mb-1">🏢 {merchant.company_name}</div>
                    )}
                    <div className="text-sm text-zinc-400 mb-4">
                      Зарегистрирован: {formatDate(merchant.created_at)}
                    </div>

                    <div className="flex gap-2">
                      <Button
                        onClick={() => approveMerchant(merchant.user_id || merchant.id)}
                        disabled={processingId === (merchant.user_id || merchant.id)}
                        className="flex-1 bg-emerald-500 hover:bg-emerald-600"
                        size="sm"
                      >
                        {processingId === (merchant.user_id || merchant.id) ? (
                          <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        ) : (
                          <>
                            <UserCheck className="w-4 h-4 mr-1" />
                            Одобрить
                          </>
                        )}
                      </Button>
                      <Button
                        onClick={() => rejectMerchant(merchant.user_id || merchant.id)}
                        disabled={processingId === (merchant.user_id || merchant.id)}
                        variant="outline"
                        className="border-red-500/50 text-red-400 hover:bg-red-500/10"
                        size="sm"
                      >
                        <XCircle className="w-4 h-4" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <Input
              placeholder="Поиск по логину, никнейму или ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 bg-zinc-900 border-zinc-800"
            />
          </div>
          <Select value={roleFilter} onValueChange={setRoleFilter}>
            <SelectTrigger className="w-full sm:w-[180px] bg-zinc-900 border-zinc-800">
              <SelectValue placeholder="Все роли" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Все роли</SelectItem>
              <SelectItem value="trader">Трейдеры</SelectItem>
              <SelectItem value="merchant">Мерчанты</SelectItem>
              <SelectItem value="admin">Админы</SelectItem>
              <SelectItem value="support">Саппорт</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Users Table */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1200px]">
                <thead className="bg-zinc-800/50">
                  <tr>
                    <th className="px-3 py-3 text-left text-sm font-medium text-zinc-400 w-[90px]">ID</th>
                    <th className="px-3 py-3 text-left text-sm font-medium text-zinc-400">Логин</th>
                    <th className="px-3 py-3 text-left text-sm font-medium text-zinc-400 w-[80px]">Роль</th>
                    <th className="px-3 py-3 text-right text-sm font-medium text-zinc-400 w-[100px]">Баланс</th>
                    <th className="px-3 py-3 text-center text-sm font-medium text-zinc-400 w-[70px]">Сделок</th>
                    <th className="px-3 py-3 text-center text-sm font-medium text-zinc-400 w-[70px]">Споры</th>
                    <th className="px-3 py-3 text-left text-sm font-medium text-zinc-400 w-[80px]">Статус</th>
                    <th className="px-3 py-3 text-right text-sm font-medium text-zinc-400 w-[280px]">Действия</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800">
                  {filteredUsers.map((user) => (
                    <tr key={user.id} className="hover:bg-zinc-800/30">
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-1">
                          <span className="font-['JetBrains_Mono'] text-xs text-zinc-500">
                            {user.id.substring(0, 8)}...
                          </span>
                          <button 
                            onClick={() => copyToClipboard(user.id)}
                            className="text-zinc-600 hover:text-emerald-400 p-0.5"
                            title="Копировать ID"
                          >
                            <Copy className="w-3 h-3" />
                          </button>
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-1">
                          <span className="font-medium text-sm">{user.nickname || user.login}</span>
                          <span className="text-xs text-zinc-500">@{user.login}</span>
                          {/* Кнопка статистики для трейдеров и мерчантов */}
                          {(user.role === 'trader' || user.role === 'merchant') && (
                            <button
                              onClick={(e) => {
                                e.preventDefault();
                                e.stopPropagation();
                                openStatsDialog(user);
                              }}
                              className="text-zinc-500 hover:text-cyan-400 p-0.5 transition-colors"
                              title="Статистика пользователя"
                              data-testid={`stats-btn-${user.id}`}
                            >
                              <BarChart3 className="w-3.5 h-3.5" />
                            </button>
                          )}
                          {user.telegram_id && (
                            <span title="Telegram" className="text-blue-400">
                              <svg className="w-3 h-3" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.562 8.161c-.18 1.897-.962 6.502-1.359 8.627-.168.9-.5 1.201-.82 1.23-.697.064-1.226-.461-1.901-.903-1.056-.692-1.653-1.123-2.678-1.799-1.185-.781-.417-1.21.258-1.911.177-.184 3.247-2.977 3.307-3.23.007-.032.015-.15-.056-.212s-.174-.041-.248-.024c-.106.024-1.793 1.139-5.062 3.345-.479.329-.913.489-1.302.481-.428-.009-1.252-.242-1.865-.442-.751-.244-1.349-.374-1.297-.789.027-.216.324-.437.893-.663 3.498-1.524 5.831-2.529 6.998-3.015 3.333-1.386 4.025-1.627 4.477-1.635.099-.002.321.023.465.142.12.099.153.232.168.326.015.094.033.31.018.478z"/></svg>
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${getRoleColor(user.role)}`}>
                          {getRoleLabel(user.role)}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-right">
                        <span className="font-mono text-sm text-emerald-400">
                          {(user.balance_usdt || 0).toFixed(2)}
                        </span>
                        <span className="text-xs text-zinc-500 ml-1">USDT</span>
                        {user.locked_balance_usdt > 0 && (
                          <div className="text-xs text-orange-400">
                            +{user.locked_balance_usdt.toFixed(2)} в сделках
                          </div>
                        )}
                      </td>
                      <td className="px-3 py-3 text-center">
                        <div className="flex flex-col items-center">
                          <span className="font-semibold text-sm">{user.orders_count || user.total_deals || 0}</span>
                          {(user.completed_orders > 0) && (
                            <span className="text-xs text-emerald-400">{user.completed_orders} ✓</span>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-3 text-center">
                        <div className="flex flex-col items-center">
                          <span className={`font-semibold text-sm ${user.open_disputes > 0 ? 'text-red-400' : ''}`}>
                            {user.disputes_count || 0}
                          </span>
                          {user.open_disputes > 0 && (
                            <span className="text-xs text-red-400">{user.open_disputes} открыто</span>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex flex-col gap-0.5">
                          {user.is_blocked ? (
                            <span className="px-2 py-0.5 rounded text-xs bg-red-500/20 text-red-400">Заблок.</span>
                          ) : user.withdrawal_auto_approve ? (
                            <span className="px-2 py-0.5 rounded text-xs bg-emerald-500/20 text-emerald-400">Доверен</span>
                          ) : (
                            <span className="px-2 py-0.5 rounded text-xs bg-zinc-700 text-zinc-400">Активен</span>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex items-center justify-end gap-1">
                          {/* Переключатель доверия (автовывод) - только для трейдеров/мерчантов и только для админа */}
                          {!isSupport && (user.role === 'trader' || user.role === 'merchant') && (
                            <div className="flex items-center gap-1 mr-2">
                              <Switch
                                checked={user.withdrawal_auto_approve || false}
                                onCheckedChange={() => toggleUserTrust(user)}
                                disabled={trustUpdating === user.id}
                                className="scale-75"
                              />
                              <span className={`text-xs whitespace-nowrap ${user.withdrawal_auto_approve ? 'text-emerald-400' : 'text-orange-400'}`}>
                                {user.withdrawal_auto_approve ? '✓ Доверен' : '⚠ Подтв.'}
                              </span>
                            </div>
                          )}
                          {/* Настройки финансовой модели - только для мерчантов и только для админа */}
                          {user.role === 'merchant' && !isSupport && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openFeeSettingsDialog(user)}
                              className="text-amber-400 hover:text-amber-300 hover:bg-amber-500/10 h-7 w-7 p-0"
                              title="Финансовая модель"
                              data-testid={`fee-settings-btn-${user.id}`}
                            >
                              <Settings className="w-4 h-4" />
                            </Button>
                          )}
                          {/* Настройки комиссии трейдера - только для трейдеров и только для админа */}
                          {user.role === 'trader' && !isSupport && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openTraderFeeDialog(user)}
                              className="text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/10 h-7 w-7 p-0"
                              title="Доля трейдера (%)"
                              data-testid={`trader-fee-btn-${user.id}`}
                            >
                              <Settings className="w-4 h-4" />
                            </Button>
                          )}
                          {/* Проверка и разморозка баланса - только для трейдеров и только для админа */}
                          {user.role === 'trader' && !isSupport && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openLockedCheckDialog(user)}
                              className={`h-7 w-7 p-0 ${user.locked_balance_usdt > 0 ? 'text-amber-400 hover:text-amber-300 hover:bg-amber-500/10' : 'text-zinc-500 hover:text-zinc-400 hover:bg-zinc-500/10'}`}
                              title="Проверить замороженный баланс"
                              data-testid={`locked-check-btn-${user.id}`}
                            >
                              <Lock className="w-4 h-4" />
                            </Button>
                          )}
                          {/* Кнопка написать - для всех кроме себя */}
                          {user.id !== currentUser?.id && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setChatDialog(user)}
                              className="text-blue-400 hover:text-blue-300 hover:bg-blue-500/10 h-7 w-7 p-0"
                              title="Написать сообщение"
                            >
                              <MessageCircle className="w-4 h-4" />
                            </Button>
                          )}
                          {/* Сброс пароля - только для админа */}
                          {!isSupport && user.id !== currentUser?.id && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setResetPasswordDialog(user)}
                              className="text-orange-400 hover:text-orange-300 hover:bg-orange-500/10 h-7 w-7 p-0"
                              title="Сбросить пароль"
                            >
                              <Key className="w-4 h-4" />
                            </Button>
                          )}
                          {/* Блокировка */}
                          {user.id !== currentUser?.id && !(isSupport && (user.role === 'admin' || user.role === 'merchant' || user.role === 'support')) && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => toggleUserActive(user.id)}
                              disabled={processingId === user.id}
                              className={`h-7 w-7 p-0 ${user.is_active ? 'text-red-400 hover:text-red-300' : 'text-emerald-400 hover:text-emerald-300'}`}
                              title={user.is_active ? 'Заблокировать' : 'Разблокировать'}
                            >
                              {user.is_active ? <Ban className="w-4 h-4" /> : <CheckCircle className="w-4 h-4" />}
                            </Button>
                          )}
                          {/* Удаление - только для админа */}
                          {!isSupport && user.id !== currentUser?.id && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setDeleteConfirm(user)}
                              disabled={processingId === user.id}
                              className="text-red-400 hover:text-red-300 hover:bg-red-500/10 h-7 w-7 p-0"
                              title="Удалить"
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {/* Delete Confirmation Dialog */}
        <AlertDialog open={!!deleteConfirm} onOpenChange={() => setDeleteConfirm(null)}>
          <AlertDialogContent className="bg-zinc-900 border-zinc-800">
            <AlertDialogHeader>
              <AlertDialogTitle>Удалить пользователя?</AlertDialogTitle>
              <AlertDialogDescription className="text-zinc-400">
                Вы уверены, что хотите удалить пользователя <strong className="text-white">{deleteConfirm?.nickname || deleteConfirm?.login}</strong>?
                <br />
                Это действие необратимо. Все данные пользователя будут удалены.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel className="bg-zinc-800 border-zinc-700">Отмена</AlertDialogCancel>
              <AlertDialogAction
                onClick={() => deleteUser(deleteConfirm?.id)}
                className="bg-red-500 hover:bg-red-600"
              >
                Удалить
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Chat Dialog */}
        <Dialog open={!!chatDialog} onOpenChange={() => setChatDialog(null)}>
          <DialogContent className="bg-zinc-900 border-zinc-800">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <MessageCircle className="w-5 h-5 text-blue-400" />
                Написать пользователю
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="bg-zinc-800 rounded-lg p-3">
                <div className="text-sm text-zinc-400">Пользователь:</div>
                <div className="font-medium">{chatDialog?.nickname || chatDialog?.login}</div>
                <div className="text-sm text-zinc-500">@{chatDialog?.login} ({getRoleLabel(chatDialog?.role)})</div>
              </div>
              <div className="space-y-2">
                <label className="text-sm text-zinc-400">Тема:</label>
                <Input
                  value={chatMessage.split('\n')[0] || ''}
                  onChange={(e) => {
                    const parts = chatMessage.split('\n');
                    parts[0] = e.target.value;
                    setChatMessage(parts.join('\n'));
                  }}
                  placeholder="Тема обращения"
                  className="bg-zinc-950 border-zinc-800"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm text-zinc-400">Сообщение:</label>
                <textarea
                  value={chatMessage.includes('\n') ? chatMessage.split('\n').slice(1).join('\n') : ''}
                  onChange={(e) => {
                    const subject = chatMessage.split('\n')[0] || '';
                    setChatMessage(subject + '\n' + e.target.value);
                  }}
                  placeholder="Введите сообщение..."
                  className="w-full h-32 bg-zinc-950 border border-zinc-800 rounded-lg p-3 resize-none focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setChatDialog(null)} className="border-zinc-700">
                Отмена
              </Button>
              <Button 
                onClick={() => openChatWithTrader(chatDialog)}
                disabled={!chatMessage.trim()}
                className="bg-blue-500 hover:bg-blue-600"
              >
                <MessageCircle className="w-4 h-4 mr-2" />
                Отправить
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Reset Password Dialog */}
        <Dialog open={!!resetPasswordDialog} onOpenChange={() => {setResetPasswordDialog(null); setNewPassword('');}}>
          <DialogContent className="bg-zinc-900 border-zinc-800">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Key className="w-5 h-5 text-orange-400" />
                Сброс пароля
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="bg-zinc-800 rounded-lg p-3">
                <div className="text-sm text-zinc-400">Пользователь:</div>
                <div className="font-medium">{resetPasswordDialog?.nickname || resetPasswordDialog?.login}</div>
                <div className="text-sm text-zinc-500">@{resetPasswordDialog?.login}</div>
              </div>
              
              <div className="space-y-2">
                <Label>Новый пароль</Label>
                <Input
                  type="text"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Минимум 6 символов"
                  className="bg-zinc-950 border-zinc-800 font-['JetBrains_Mono']"
                />
              </div>
              
              <div className="bg-orange-500/10 border border-orange-500/30 rounded-lg p-3 text-sm text-orange-400">
                ⚠️ Пользователь должен будет использовать этот пароль при следующем входе
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => {setResetPasswordDialog(null); setNewPassword('');}} className="border-zinc-700">
                Отмена
              </Button>
              <Button 
                onClick={resetUserPassword}
                disabled={processingId || newPassword.length < 6}
                className="bg-orange-500 hover:bg-orange-600"
              >
                {processingId ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                ) : (
                  <Key className="w-4 h-4 mr-2" />
                )}
                Сбросить пароль
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Fee Settings Dialog - Финансовая модель мерчанта */}
        <Dialog open={!!feeSettingsDialog} onOpenChange={() => setFeeSettingsDialog(null)}>
          <DialogContent className={`bg-zinc-900 border-zinc-800 ${feeSettings.fee_model === 'merchant_pays' ? 'max-w-2xl' : 'max-w-lg'}`}>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Settings className="w-5 h-5 text-amber-400" />
                Финансовая модель мерчанта
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-5">
              {/* Информация о мерчанте */}
              <div className="bg-zinc-800 rounded-lg p-3">
                <div className="text-sm text-zinc-400">Мерчант:</div>
                <div className="font-medium">{feeSettingsDialog?.merchantName || feeSettingsDialog?.user?.nickname}</div>
                <div className="text-sm text-zinc-500">@{feeSettingsDialog?.user?.login}</div>
              </div>
              
              {/* Выбор типа */}
              <div className="space-y-3">
                <label className="text-sm font-medium text-zinc-300">Тип распределения комиссии:</label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    onClick={() => setFeeSettings(s => ({ ...s, fee_model: 'merchant_pays' }))}
                    className={`p-4 rounded-lg border-2 text-left transition-all ${
                      feeSettings.fee_model === 'merchant_pays' 
                        ? 'border-amber-500 bg-amber-500/10' 
                        : 'border-zinc-700 bg-zinc-800/50 hover:border-zinc-600'
                    }`}
                    data-testid="fee-model-merchant-pays"
                  >
                    <div className="font-medium text-amber-400 mb-1">Тип 1</div>
                    <div className="text-sm text-zinc-400">Мерчант платит</div>
                    <div className="text-xs text-zinc-500 mt-2">Гибкие комиссии по методам</div>
                  </button>
                  <button
                    onClick={() => setFeeSettings(s => ({ ...s, fee_model: 'customer_pays' }))}
                    className={`p-4 rounded-lg border-2 text-left transition-all ${
                      feeSettings.fee_model === 'customer_pays' 
                        ? 'border-emerald-500 bg-emerald-500/10' 
                        : 'border-zinc-700 bg-zinc-800/50 hover:border-zinc-600'
                    }`}
                    data-testid="fee-model-customer-pays"
                  >
                    <div className="font-medium text-emerald-400 mb-1">Тип 2</div>
                    <div className="text-sm text-zinc-400">Покупатель платит</div>
                    <div className="text-xs text-zinc-500 mt-2">Цена + накрутка + маркер</div>
                  </button>
                </div>
              </div>

              {/* Тип 1: Комиссии по методам оплаты */}
              {feeSettings.fee_model === 'merchant_pays' && feeSettingsDialog?.merchant && (
                <MerchantMethodCommissionsInline 
                  merchantId={feeSettingsDialog.merchant.id}
                  merchantName={feeSettingsDialog.merchantName}
                />
              )}

              {/* Тип 2: Общая накрутка */}
              {feeSettings.fee_model === 'customer_pays' && (
                <>
                  <div className="space-y-2">
                    <label className="text-sm text-zinc-400">Общая накрутка (%)</label>
                    <Input
                      type="number"
                      min="1"
                      max="100"
                      value={feeSettings.total_fee_percent}
                      onChange={(e) => setFeeSettings(s => ({ ...s, total_fee_percent: Number(e.target.value) }))}
                      className="bg-zinc-950 border-zinc-800"
                      data-testid="total-fee-percent"
                    />
                    <p className="text-xs text-zinc-500">
                      Накрутка делится: трейдер (его %) + платформа (остаток). Маркер идёт платформе.
                    </p>
                  </div>

                  {/* Информация о маркере */}
                  <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
                    <div className="text-sm text-amber-400 font-medium mb-1">📌 Маркер (5-20₽)</div>
                    <p className="text-xs text-zinc-400">
                      К каждому счёту добавляется случайная сумма от 5 до 20₽ для идентификации платежа.
                    </p>
                  </div>

                  {/* Пример расчёта для Типа 2 */}
                  <div className="bg-zinc-800/50 rounded-lg p-4 space-y-3">
                    <div className="text-sm font-medium text-zinc-300">Пример расчёта (заказ 1000 ₽, доля трейдера 10%):</div>
                    <div className="flex justify-between text-sm">
                      <span className="text-zinc-400">Покупатель платит:</span>
                      <span className="text-white font-mono">{(1000 * (1 + feeSettings.total_fee_percent / 100)).toFixed(0)} + [5-20] ₽</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-zinc-400">Мерчант получает:</span>
                      <span className="text-purple-400 font-mono">1000 ₽</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-zinc-400">Трейдер получает (10%):</span>
                      <span className="text-blue-400 font-mono">100 ₽</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-zinc-400">Платформа получает:</span>
                      <span className="text-emerald-400 font-mono">{(1000 * (feeSettings.total_fee_percent / 100) - 100).toFixed(0)} + [5-20] ₽</span>
                    </div>
                  </div>
                </>
              )}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setFeeSettingsDialog(null)} className="border-zinc-700">
                Отмена
              </Button>
              <Button 
                onClick={saveFeeSettings}
                disabled={processingId}
                className="bg-amber-500 hover:bg-amber-600"
                data-testid="save-fee-settings-btn"
              >
                {processingId ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                ) : (
                  <Settings className="w-4 h-4 mr-2" />
                )}
                Сохранить тип
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Trader Fee Dialog - Настройка комиссии трейдера с интервалами */}
        <Dialog open={!!traderFeeDialog} onOpenChange={() => setTraderFeeDialog(null)}>
          <DialogContent className="bg-zinc-900 border-zinc-800 max-w-lg">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Percent className="w-5 h-5 text-cyan-400" />
                Комиссия трейдера
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              {/* Информация о трейдере */}
              <div className="bg-zinc-800 rounded-lg p-3">
                <div className="text-sm text-zinc-400">Трейдер:</div>
                <div className="font-medium">{traderFeeDialog?.traderName || traderFeeDialog?.user?.nickname}</div>
                <div className="text-sm text-zinc-500">@{traderFeeDialog?.user?.login}</div>
              </div>
              
              {/* Компонент настройки интервалов */}
              {traderFeeDialog?.trader && (
                <TraderFeeIntervalsInline 
                  traderId={traderFeeDialog.trader.id}
                  traderName={traderFeeDialog.traderName}
                  onClose={() => setTraderFeeDialog(null)}
                />
              )}
            </div>
          </DialogContent>
        </Dialog>

        {/* Locked Balance Check Dialog - Проверка и разморозка баланса трейдера */}
        <Dialog open={!!lockedCheckDialog} onOpenChange={() => setLockedCheckDialog(null)}>
          <DialogContent className="bg-zinc-900 border-zinc-800 max-w-lg">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Lock className="w-5 h-5 text-amber-400" />
                Проверка баланса трейдера
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              {/* Информация о трейдере */}
              <div className="bg-zinc-800 rounded-lg p-3">
                <div className="text-sm text-zinc-400">Трейдер:</div>
                <div className="font-medium">{lockedCheckDialog?.user?.nickname || lockedCheckDialog?.user?.login}</div>
                <div className="text-sm text-zinc-500">@{lockedCheckDialog?.user?.login}</div>
              </div>

              {lockedCheckLoading ? (
                <div className="flex justify-center py-8">
                  <div className="w-8 h-8 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : lockedCheckData?.error ? (
                <div className="text-center py-6 text-red-400">
                  Ошибка загрузки данных
                </div>
              ) : lockedCheckData ? (
                <>
                  {/* Балансы */}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-zinc-800/50 rounded-lg p-3 text-center">
                      <div className="text-zinc-400 text-xs mb-1">Доступно</div>
                      <div className="text-lg font-mono text-emerald-400">
                        {lockedCheckData.available_balance_usdt?.toFixed(2)} <span className="text-xs text-zinc-500">USDT</span>
                      </div>
                    </div>
                    <div className="bg-zinc-800/50 rounded-lg p-3 text-center">
                      <div className="text-zinc-400 text-xs mb-1">Заморожено</div>
                      <div className="text-lg font-mono text-orange-400">
                        {lockedCheckData.locked_balance_usdt?.toFixed(2)} <span className="text-xs text-zinc-500">USDT</span>
                      </div>
                    </div>
                  </div>

                  {/* Активные заказы */}
                  <div className="bg-zinc-800/50 rounded-lg p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-zinc-400 text-sm">Активных заказов:</span>
                      <span className="font-semibold">{lockedCheckData.active_orders_count}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-zinc-400 text-sm">Сумма заказов:</span>
                      <span className="font-mono text-blue-400">
                        {lockedCheckData.active_orders_total_usdt?.toFixed(2)} USDT
                      </span>
                    </div>
                  </div>

                  {/* Статус проверки */}
                  {lockedCheckData.has_mismatch ? (
                    <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                      <div className="flex items-center gap-2 text-red-400 font-medium mb-2">
                        <AlertTriangle className="w-4 h-4" />
                        Обнаружено несоответствие!
                      </div>
                      <div className="text-sm text-zinc-300">
                        {lockedCheckData.mismatch_type === 'locked_without_orders' 
                          ? 'Есть замороженные средства, но нет активных заказов'
                          : 'Замороженная сумма превышает сумму активных заказов'}
                      </div>
                      <div className="text-sm text-amber-400 mt-2">
                        Разница: <span className="font-mono">{lockedCheckData.difference?.toFixed(2)} USDT</span>
                      </div>
                    </div>
                  ) : (
                    <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-3">
                      <div className="flex items-center gap-2 text-emerald-400">
                        <CheckCircle className="w-4 h-4" />
                        Баланс соответствует активным заказам
                      </div>
                    </div>
                  )}

                  {/* Список активных заказов */}
                  {lockedCheckData.active_orders?.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-sm text-zinc-400">Активные заказы:</div>
                      <div className="max-h-32 overflow-y-auto space-y-1">
                        {lockedCheckData.active_orders.map((order, i) => (
                          <div key={i} className="text-xs bg-zinc-800/50 rounded px-2 py-1 flex justify-between items-center">
                            <span className="font-mono text-zinc-500">{order.id?.slice(0, 15)}...</span>
                            <span className={`px-1.5 py-0.5 rounded ${
                              order.status === 'dispute' ? 'bg-red-500/20 text-red-400' : 'bg-blue-500/20 text-blue-400'
                            }`}>
                              {order.status}
                            </span>
                            <span className="font-mono">{order.amount_usdt?.toFixed(2)} USDT</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Форма разморозки - только если есть несоответствие и админ */}
                  {lockedCheckData.has_mismatch && !isSupport && (
                    <div className="border-t border-zinc-700 pt-4 space-y-3">
                      <div className="text-sm font-medium text-amber-400 flex items-center gap-2">
                        <Unlock className="w-4 h-4" />
                        Разморозить средства
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <Label className="text-xs text-zinc-400">Сумма (USDT)</Label>
                          <Input
                            type="number"
                            step="0.01"
                            min="0"
                            max={lockedCheckData.locked_balance_usdt}
                            value={unfreezeAmount}
                            onChange={(e) => setUnfreezeAmount(e.target.value)}
                            placeholder="0.00"
                            className="bg-zinc-950 border-zinc-700 h-9"
                            data-testid="unfreeze-amount-input"
                          />
                        </div>
                        <div>
                          <Label className="text-xs text-zinc-400">Макс. доступно</Label>
                          <div className="h-9 flex items-center text-sm font-mono text-zinc-400">
                            {lockedCheckData.locked_balance_usdt?.toFixed(2)} USDT
                          </div>
                        </div>
                      </div>
                      <div>
                        <Label className="text-xs text-zinc-400">Причина разморозки *</Label>
                        <Input
                          value={unfreezeReason}
                          onChange={(e) => setUnfreezeReason(e.target.value)}
                          placeholder="Опишите причину..."
                          className="bg-zinc-950 border-zinc-700"
                          data-testid="unfreeze-reason-input"
                        />
                      </div>
                      <Button
                        onClick={handleUnfreeze}
                        disabled={unfreezeLoading || !unfreezeAmount || !unfreezeReason.trim()}
                        className="w-full bg-amber-500 hover:bg-amber-600"
                        data-testid="unfreeze-submit-btn"
                      >
                        {unfreezeLoading ? (
                          <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                        ) : (
                          <Unlock className="w-4 h-4 mr-2" />
                        )}
                        Разморозить
                      </Button>
                    </div>
                  )}
                </>
              ) : null}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setLockedCheckDialog(null)} className="border-zinc-700">
                Закрыть
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Stats Dialog - Статистика пользователя */}
        <Dialog open={!!statsDialog} onOpenChange={() => setStatsDialog(null)}>
          <DialogContent className="bg-zinc-900 border-zinc-800 max-w-sm">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-base">
                <BarChart3 className="w-4 h-4 text-cyan-400" />
                Статистика
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              {/* Шапка с информацией о пользователе */}
              <div className="flex items-center justify-between bg-zinc-800 rounded-lg p-3">
                <div>
                  <div className="font-medium text-sm">{userStats?.nickname || statsDialog?.nickname || statsDialog?.login}</div>
                  <div className="text-xs text-zinc-500">@{statsDialog?.login}</div>
                </div>
                <div className="text-right">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    (userStats?.role || statsDialog?.role) === 'trader' 
                      ? 'bg-blue-500/20 text-blue-400' 
                      : 'bg-purple-500/20 text-purple-400'
                  }`}>
                    {(userStats?.role || statsDialog?.role) === 'trader' ? 'Трейдер' : 'Мерчант'}
                  </span>
                  {userStats?.registered_at && (
                    <div className="text-xs text-zinc-500 mt-1">{formatDate(userStats.registered_at)}</div>
                  )}
                </div>
              </div>
              
              {statsLoading ? (
                <div className="flex items-center justify-center py-6">
                  <div className="w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : userStats?.error ? (
                <div className="text-center py-4 text-zinc-500 text-sm">
                  Ошибка загрузки
                </div>
              ) : userStats ? (
                <div className="space-y-2">
                  {/* Баланс - компактный */}
                  <div className="bg-zinc-800/50 rounded-lg p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-zinc-400 text-xs flex items-center gap-1.5">
                        <Wallet className="w-3.5 h-3.5" /> Баланс
                      </span>
                      <span className="text-lg font-mono text-emerald-400">
                        {(userStats.balance_usdt || 0).toFixed(2)} <span className="text-xs text-zinc-500">USDT</span>
                      </span>
                    </div>
                    {userStats.locked_balance_usdt > 0 && (
                      <div className="text-xs text-orange-400 text-right mt-1">
                        В сделках: {userStats.locked_balance_usdt.toFixed(2)}
                      </div>
                    )}
                  </div>
                  
                  {/* Депозиты и Выводы */}
                  <div className="grid grid-cols-2 gap-2">
                    <div className="bg-zinc-800/50 rounded-lg p-2.5">
                      <div className="flex items-center justify-between">
                        <span className="text-zinc-400 text-xs">Депозиты</span>
                        <span className="text-emerald-400 font-mono text-sm">
                          +{(userStats.total_deposited_usdt || userStats.wallet?.total_deposited_usdt || 0).toFixed(2)}
                        </span>
                      </div>
                    </div>
                    <div className="bg-zinc-800/50 rounded-lg p-2.5">
                      <div className="flex items-center justify-between">
                        <span className="text-zinc-400 text-xs">Выводы</span>
                        <span className="text-red-400 font-mono text-sm">
                          -{(userStats.total_withdrawn_usdt || userStats.wallet?.total_withdrawn_usdt || 0).toFixed(2)}
                        </span>
                      </div>
                    </div>
                  </div>
                  
                  {/* Сделки + Оборот в одну строку */}
                  <div className="grid grid-cols-3 gap-2">
                    <div className="bg-zinc-800/50 rounded-lg p-2.5 text-center">
                      <div className="text-lg font-semibold">{userStats.total_orders || 0}</div>
                      <div className="text-zinc-500 text-xs">Сделок</div>
                    </div>
                    <div className="bg-zinc-800/50 rounded-lg p-2.5 text-center">
                      <div className="text-lg font-semibold text-emerald-400">{userStats.completed_orders || 0}</div>
                      <div className="text-zinc-500 text-xs">Завершено</div>
                    </div>
                    <div className="bg-zinc-800/50 rounded-lg p-2.5 text-center">
                      <div className="text-lg font-semibold">{(userStats.volume_rub || 0).toLocaleString()}</div>
                      <div className="text-zinc-500 text-xs">Оборот ₽</div>
                    </div>
                  </div>
                  
                  {/* Оборот USDT */}
                  {(userStats.volume_usdt || userStats.volume?.total_usdt) > 0 && (
                    <div className="bg-zinc-800/50 rounded-lg p-2.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-zinc-400">Оборот USDT</span>
                        <span className="text-blue-400 font-mono">
                          {(userStats.volume_usdt || userStats.volume?.total_usdt || 0).toFixed(2)} USDT
                        </span>
                      </div>
                    </div>
                  )}
                  
                  {/* Споры - компактно */}
                  <div className="bg-zinc-800/50 rounded-lg p-2.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-zinc-400 flex items-center gap-1.5">
                        <AlertTriangle className="w-3.5 h-3.5" /> Споры
                      </span>
                      <div className="flex gap-3">
                        <span>{userStats.total_disputes || 0} всего</span>
                        <span className="text-orange-400">{userStats.open_disputes || 0} открыто</span>
                        <span className="text-emerald-400">{userStats.resolved_disputes || 0} решено</span>
                      </div>
                    </div>
                  </div>
                  
                  {/* Реферальный баланс */}
                  {(userStats.user?.referral_balance > 0) && (
                    <div className="bg-zinc-800/50 rounded-lg p-2.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-zinc-400">Реферальный баланс</span>
                        <span className="text-purple-400 font-mono">
                          {(userStats.user?.referral_balance || 0).toFixed(4)} USDT
                        </span>
                      </div>
                    </div>
                  )}
                  
                  {/* Процент успеха */}
                  {userStats.total_orders > 0 && (
                    <div className="bg-gradient-to-r from-emerald-500/10 to-transparent rounded-lg p-2.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-zinc-400">Успешность</span>
                        <span className="text-emerald-400 font-medium">
                          {((userStats.completed_orders / userStats.total_orders) * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  )}
                  
                  {/* Дата регистрации */}
                  <div className="bg-zinc-800/30 rounded-lg p-2.5 mt-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-zinc-500">Регистрация</span>
                      <span className="text-zinc-400">
                        {userStats.user?.created_at ? new Date(userStats.user.created_at).toLocaleDateString('ru-RU') : '-'}
                      </span>
                    </div>
                    {userStats.user?.last_login_at && (
                      <div className="flex items-center justify-between text-xs mt-1">
                        <span className="text-zinc-500">Последний вход</span>
                        <span className="text-zinc-400">
                          {new Date(userStats.user.last_login_at).toLocaleString('ru-RU')}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              ) : null}
            </div>
            <DialogFooter className="mt-2">
              <Button variant="outline" onClick={() => setStatsDialog(null)} className="border-zinc-700 w-full h-8 text-sm">
                Закрыть
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </DashboardLayout>
  );
};

export default AdminUsers;
