import React, { useState, useEffect } from 'react';
import { api } from '@/lib/auth';
import DashboardLayout from '@/components/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { toast } from 'sonner';
import { 
  Wrench, Users, Gift, Save, Power, Clock,
  Percent, Wallet, AlertTriangle
} from 'lucide-react';

const AdminMaintenance = () => {
  // Maintenance State
  const [maintenance, setMaintenance] = useState({
    enabled: false,
    target: 'all',
    duration_minutes: 60,
    message: 'Платформа на техническом обслуживании',
    ends_at: null
  });
  const [maintenanceLoading, setMaintenanceLoading] = useState(true);

  // Referral State
  const [referral, setReferral] = useState({
    level1_percent: 5.0,
    level2_percent: 2.0,
    level3_percent: 1.0,
    min_withdrawal_usdt: 1,
    enabled: true
  });
  const [referralLoading, setReferralLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Database Reset State
  const [showResetModal, setShowResetModal] = useState(false);
  const [resetPassword, setResetPassword] = useState('');
  const [resetting, setResetting] = useState(false);

  useEffect(() => {
    fetchMaintenanceSettings();
    fetchReferralSettings();
  }, []);

  const fetchMaintenanceSettings = async () => {
    try {
      const res = await api.get('/admin/maintenance');
      setMaintenance(res.data);
    } catch (error) {
      toast.error('Ошибка загрузки настроек техобслуживания');
    } finally {
      setMaintenanceLoading(false);
    }
  };

  const fetchReferralSettings = async () => {
    try {
      const res = await api.get('/admin/referral/settings');
      setReferral(res.data);
    } catch (error) {
      toast.error('Ошибка загрузки реферальных настроек');
    } finally {
      setReferralLoading(false);
    }
  };

  const toggleMaintenance = async () => {
    try {
      if (maintenance.enabled) {
        // Выключаем
        await api.post('/admin/maintenance/disable');
        toast.success('Техобслуживание выключено');
        setMaintenance(prev => ({ ...prev, enabled: false, ends_at: null }));
      } else {
        // Включаем
        const res = await api.post('/admin/maintenance/enable', {
          enabled: true,
          target: maintenance.target,
          duration_minutes: maintenance.duration_minutes,
          message: maintenance.message
        });
        toast.success(res.data.message);
        setMaintenance(prev => ({ ...prev, enabled: true, ends_at: res.data.ends_at }));
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка');
    }
  };

  const saveReferralSettings = async () => {
    setSaving(true);
    try {
      await api.put('/admin/referral/settings', referral);
      toast.success('Реферальные настройки сохранены');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка сохранения');
    } finally {
      setSaving(false);
    }
  };

  const handleDatabaseReset = async () => {
    if (!resetPassword) {
      toast.error('Введите пароль');
      return;
    }
    
    setResetting(true);
    try {
      const res = await api.post('/admin/reset-database', { password: resetPassword });
      toast.success(res.data.message);
      setShowResetModal(false);
      setResetPassword('');
      
      // Показываем детали
      const details = res.data.details;
      const total = Object.values(details).reduce((a, b) => a + b, 0);
      toast.info(`Удалено записей: ${total}`, { duration: 5000 });
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка сброса');
    } finally {
      setResetting(false);
    }
  };

  const formatEndsAt = (dateStr) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString('ru-RU');
  };

  if (maintenanceLoading || referralLoading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <div className="w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin" />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
      {/* Maintenance Mode */}
      <Card className={`border-2 ${maintenance.enabled ? 'border-amber-500 bg-amber-500/5' : 'border-zinc-800 bg-zinc-900'}`}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Wrench className={`w-5 h-5 ${maintenance.enabled ? 'text-amber-400' : 'text-zinc-400'}`} />
            Режим техобслуживания
            {maintenance.enabled && (
              <span className="ml-auto px-3 py-1 bg-amber-500 text-black text-xs font-bold rounded-full animate-pulse">
                АКТИВЕН
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {maintenance.enabled && maintenance.ends_at && (
            <div className="p-3 bg-amber-500/20 border border-amber-500/30 rounded-lg flex items-center gap-2">
              <Clock className="w-5 h-5 text-amber-400" />
              <span>Завершится: <strong>{formatEndsAt(maintenance.ends_at)}</strong></span>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Target */}
            <div className="space-y-2">
              <label className="text-sm text-zinc-400">Для кого</label>
              <Select 
                value={maintenance.target} 
                onValueChange={(v) => setMaintenance(prev => ({ ...prev, target: v }))}
                disabled={maintenance.enabled}
              >
                <SelectTrigger className="bg-zinc-950 border-zinc-700">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-zinc-900 border-zinc-700">
                  <SelectItem value="all">Все (трейдеры + мерчанты)</SelectItem>
                  <SelectItem value="traders">Только трейдеры</SelectItem>
                  <SelectItem value="merchants">Только мерчанты</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Duration */}
            <div className="space-y-2">
              <label className="text-sm text-zinc-400">Длительность (минуты)</label>
              <Input
                type="number"
                min="5"
                max="1440"
                value={maintenance.duration_minutes}
                onChange={(e) => setMaintenance(prev => ({ ...prev, duration_minutes: parseInt(e.target.value) || 60 }))}
                disabled={maintenance.enabled}
                className="bg-zinc-950 border-zinc-700"
              />
            </div>
          </div>

          {/* Message */}
          <div className="space-y-2">
            <label className="text-sm text-zinc-400">Сообщение для пользователей</label>
            <Input
              value={maintenance.message}
              onChange={(e) => setMaintenance(prev => ({ ...prev, message: e.target.value }))}
              disabled={maintenance.enabled}
              className="bg-zinc-950 border-zinc-700"
              placeholder="Платформа на техническом обслуживании"
            />
          </div>

          {/* Toggle Button */}
          <Button
            onClick={toggleMaintenance}
            className={`w-full h-12 ${
              maintenance.enabled 
                ? 'bg-red-500 hover:bg-red-600' 
                : 'bg-amber-500 hover:bg-amber-600'
            }`}
          >
            <Power className="w-5 h-5 mr-2" />
            {maintenance.enabled ? 'Выключить техобслуживание' : 'Включить техобслуживание'}
          </Button>

          {!maintenance.enabled && (
            <div className="flex items-start gap-2 p-3 bg-zinc-800/50 rounded-lg text-sm text-zinc-400">
              <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
              <span>
                При включении трейдеры/мерчанты будут видеть страницу &quot;Техобслуживание&quot; 
                с таймером обратного отсчёта. Админы не затрагиваются.
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Referral Settings */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Gift className="w-5 h-5 text-emerald-400" />
            Реферальная программа
            <div className="ml-auto flex items-center gap-2">
              <span className="text-sm text-zinc-400">Активна</span>
              <Switch
                checked={referral.enabled}
                onCheckedChange={(checked) => setReferral(prev => ({ ...prev, enabled: checked }))}
              />
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Percentages */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <label className="text-sm text-zinc-400 flex items-center gap-2">
                <div className="w-6 h-6 rounded bg-emerald-500/20 flex items-center justify-center text-xs font-bold text-emerald-400">L1</div>
                Уровень 1 (%)
              </label>
              <Input
                type="number"
                min="0"
                max="50"
                step="0.5"
                value={referral.level1_percent}
                onChange={(e) => setReferral(prev => ({ ...prev, level1_percent: parseFloat(e.target.value) || 0 }))}
                className="bg-zinc-950 border-zinc-700"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm text-zinc-400 flex items-center gap-2">
                <div className="w-6 h-6 rounded bg-cyan-500/20 flex items-center justify-center text-xs font-bold text-cyan-400">L2</div>
                Уровень 2 (%)
              </label>
              <Input
                type="number"
                min="0"
                max="50"
                step="0.5"
                value={referral.level2_percent}
                onChange={(e) => setReferral(prev => ({ ...prev, level2_percent: parseFloat(e.target.value) || 0 }))}
                className="bg-zinc-950 border-zinc-700"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm text-zinc-400 flex items-center gap-2">
                <div className="w-6 h-6 rounded bg-blue-500/20 flex items-center justify-center text-xs font-bold text-blue-400">L3</div>
                Уровень 3 (%)
              </label>
              <Input
                type="number"
                min="0"
                max="50"
                step="0.5"
                value={referral.level3_percent}
                onChange={(e) => setReferral(prev => ({ ...prev, level3_percent: parseFloat(e.target.value) || 0 }))}
                className="bg-zinc-950 border-zinc-700"
              />
            </div>
          </div>

          {/* Min Withdrawal */}
          <div className="space-y-2">
            <label className="text-sm text-zinc-400 flex items-center gap-2">
              <Wallet className="w-4 h-4" />
              Минимальная сумма для вывода (USDT)
            </label>
            <Input
              type="number"
              min="0"
              step="0.1"
              value={referral.min_withdrawal_usdt}
              onChange={(e) => setReferral(prev => ({ ...prev, min_withdrawal_usdt: parseFloat(e.target.value) || 0 }))}
              className="bg-zinc-950 border-zinc-700 max-w-xs"
            />
          </div>

          {/* Example */}
          <div className="p-4 bg-zinc-800/50 rounded-lg">
            <div className="text-sm font-medium mb-2">Пример расчёта</div>
            <div className="text-sm text-zinc-400">
              Трейдер заработал <strong className="text-white">1 USDT</strong> на сделке:
            </div>
            <div className="mt-2 space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-emerald-400">Уровень 1 получит:</span>
                <span className="font-mono">{(1 * referral.level1_percent / 100).toFixed(4)} USDT</span>
              </div>
              <div className="flex justify-between">
                <span className="text-cyan-400">Уровень 2 получит:</span>
                <span className="font-mono">{(1 * referral.level2_percent / 100).toFixed(4)} USDT</span>
              </div>
              <div className="flex justify-between">
                <span className="text-blue-400">Уровень 3 получит:</span>
                <span className="font-mono">{(1 * referral.level3_percent / 100).toFixed(4)} USDT</span>
              </div>
            </div>
            <div className="mt-3 text-xs text-amber-400/80">
              * Бонусы считаются от заработка трейдера, но платит площадка
            </div>
          </div>

          {/* Save Button */}
          <Button
            onClick={saveReferralSettings}
            disabled={saving}
            className="bg-emerald-500 hover:bg-emerald-600"
          >
            {saving ? (
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
            ) : (
              <Save className="w-4 h-4 mr-2" />
            )}
            Сохранить настройки
          </Button>
        </CardContent>
      </Card>

      {/* Опасная зона - Сброс базы данных */}
      <Card className="bg-red-950/30 border-red-500/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-red-400">
            <AlertTriangle className="w-5 h-5" />
            Опасная зона
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
            <div className="text-sm text-red-300 mb-3">
              <strong>⚠️ ВНИМАНИЕ!</strong> Эта операция полностью очистит базу данных:
            </div>
            <ul className="text-sm text-red-300/80 space-y-1 ml-4 list-disc">
              <li>Все пользователи (кроме вас)</li>
              <li>Все заказы и инвойсы</li>
              <li>Все споры и сообщения</li>
              <li>Все транзакции (депозиты, выводы)</li>
              <li>Все тикеты и уведомления</li>
              <li>Все реквизиты и кошельки</li>
            </ul>
            <div className="mt-3 text-sm text-red-400 font-semibold">
              Это действие НЕОБРАТИМО!
            </div>
          </div>

          <Button
            onClick={() => setShowResetModal(true)}
            variant="destructive"
            className="bg-red-600 hover:bg-red-700"
            data-testid="reset-database-btn"
          >
            <AlertTriangle className="w-4 h-4 mr-2" />
            Очистить базу данных
          </Button>
        </CardContent>
      </Card>

      {/* Модальное окно подтверждения сброса */}
      {showResetModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
          <Card className="w-full max-w-md bg-zinc-900 border-red-500/50">
            <CardHeader>
              <CardTitle className="text-red-400 flex items-center gap-2">
                <AlertTriangle className="w-5 h-5" />
                Подтверждение сброса
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-zinc-400">
                Для подтверждения очистки базы данных введите пароль:
              </p>
              
              <Input
                type="password"
                placeholder="Пароль для сброса"
                value={resetPassword}
                onChange={(e) => setResetPassword(e.target.value)}
                className="bg-zinc-950 border-red-500/50"
                data-testid="reset-password-input"
              />

              <div className="flex gap-3 pt-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowResetModal(false);
                    setResetPassword('');
                  }}
                  className="flex-1"
                >
                  Отмена
                </Button>
                <Button
                  onClick={handleDatabaseReset}
                  disabled={resetting || !resetPassword}
                  className="flex-1 bg-red-600 hover:bg-red-700"
                  data-testid="confirm-reset-btn"
                >
                  {resetting ? (
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    'Подтвердить сброс'
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
      </div>
    </DashboardLayout>
  );
};

export default AdminMaintenance;
