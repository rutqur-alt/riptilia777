import React, { useState, useEffect } from 'react';
import DashboardLayout from '@/components/DashboardLayout';
import { api, formatRUB } from '@/lib/auth';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import {
  Users, FileText, AlertTriangle, TrendingUp, RefreshCw, Activity, ArrowUpRight, Wallet, Clock
} from 'lucide-react';

const formatUSDT = (amount) => {
  if (!amount && amount !== 0) return '0.00';
  return parseFloat(amount).toFixed(2);
};

const StatCard = ({ icon: Icon, label, value, subValue, color, badge, onClick }) => (
  <Card 
    className={`bg-zinc-900/50 border-zinc-800/50 hover:border-zinc-700 transition-all duration-300 cursor-pointer group ${onClick ? 'hover:scale-[1.02]' : ''}`}
    onClick={onClick}
  >
    <CardContent className="p-5">
      <div className="flex items-start justify-between mb-3">
        <div className={`w-10 h-10 rounded-xl bg-${color}-500/10 flex items-center justify-center group-hover:scale-110 transition-transform`}>
          <Icon className={`w-5 h-5 text-${color}-400`} />
        </div>
        {badge !== undefined && badge > 0 && (
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium bg-${color}-500/20 text-${color}-400`}>
            {badge} активн.
          </span>
        )}
      </div>
      <div className="font-mono text-2xl font-bold mb-1 tracking-tight">{value}</div>
      <div className="text-sm text-zinc-500">{label}</div>
      {subValue && <div className="text-xs text-zinc-600 mt-1">{subValue}</div>}
    </CardContent>
  </Card>
);

const QuickAction = ({ icon: Icon, label, href, color, badge }) => (
  <a 
    href={href} 
    className="group relative flex flex-col items-center justify-center p-4 bg-zinc-800/50 rounded-xl hover:bg-zinc-800 border border-transparent hover:border-zinc-700 transition-all duration-200"
  >
    <div className={`w-10 h-10 rounded-lg bg-${color}-500/10 flex items-center justify-center mb-2 group-hover:scale-110 transition-transform`}>
      <Icon className={`w-5 h-5 text-${color}-400`} />
    </div>
    <span className="text-sm text-zinc-300">{label}</span>
    {badge > 0 && (
      <span className="absolute top-2 right-2 w-5 h-5 bg-red-500 rounded-full text-xs flex items-center justify-center font-medium">
        {badge > 9 ? '9+' : badge}
      </span>
    )}
  </a>
);

const AdminDashboard = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const res = await api.get('/admin/stats');
      setStats(res.data);
    } catch (error) {
      toast.error('Ошибка загрузки статистики');
    } finally {
      setLoading(false);
    }
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
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Админ-панель</h1>
            <p className="text-zinc-500 text-sm mt-0.5">Обзор системы и статистика</p>
          </div>
          <Button 
            variant="outline" 
            size="sm" 
            onClick={fetchStats} 
            className="border-zinc-800 hover:bg-zinc-800"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Обновить
          </Button>
        </div>

        {/* Main Stats Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            icon={Users}
            label="Пользователей"
            value={stats?.users?.total || 0}
            subValue={`${stats?.users?.traders || 0} трейдеров • ${stats?.users?.merchants || 0} мерчантов`}
            color="blue"
            onClick={() => window.location.href = '/admin/users'}
          />
          <StatCard
            icon={Activity}
            label="Завершённых ордеров"
            value={stats?.orders?.completed || 0}
            badge={stats?.orders?.active}
            color="emerald"
            onClick={() => window.location.href = '/admin/orders'}
          />
          <StatCard
            icon={AlertTriangle}
            label="Открытых споров"
            value={stats?.disputes?.open || 0}
            color="orange"
            onClick={() => window.location.href = '/admin/disputes'}
          />
          <StatCard
            icon={TrendingUp}
            label="Комиссия сегодня"
            value={`${formatUSDT(stats?.today?.platform_commission_usdt)} USDT`}
            color="purple"
          />
        </div>

        {/* Two Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* Today's Stats - Takes 3 columns */}
          <Card className="lg:col-span-3 bg-zinc-900/50 border-zinc-800/50">
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold flex items-center gap-2">
                  <Clock className="w-4 h-4 text-zinc-500" />
                  Статистика за сегодня
                </h3>
              </div>
              <div className="space-y-3">
                <div className="flex items-center justify-between py-2.5 px-3 rounded-lg bg-zinc-800/30">
                  <span className="text-zinc-400 text-sm">Количество сделок</span>
                  <span className="font-mono font-medium">{stats?.today?.deals_count || 0}</span>
                </div>
                <div className="flex items-center justify-between py-2.5 px-3 rounded-lg bg-zinc-800/30">
                  <span className="text-zinc-400 text-sm">Оборот в рублях</span>
                  <span className="font-mono font-medium">{formatRUB(stats?.today?.volume_rub)}</span>
                </div>
                <div className="flex items-center justify-between py-2.5 px-3 rounded-lg bg-zinc-800/30">
                  <span className="text-zinc-400 text-sm">Оборот в USDT</span>
                  <span className="font-mono font-medium">{formatUSDT(stats?.today?.volume_usdt)} USDT</span>
                </div>
                <div className="flex items-center justify-between py-2.5 px-3 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
                  <span className="text-zinc-400 text-sm">Комиссия платформы</span>
                  <span className="font-mono font-medium text-emerald-400">
                    {formatUSDT(stats?.today?.platform_commission_usdt)} USDT
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Quick Actions - Takes 2 columns */}
          <Card className="lg:col-span-2 bg-zinc-900/50 border-zinc-800/50">
            <CardContent className="p-5">
              <h3 className="font-semibold mb-4 flex items-center gap-2">
                <ArrowUpRight className="w-4 h-4 text-zinc-500" />
                Быстрые действия
              </h3>
              <div className="grid grid-cols-2 gap-3">
                <QuickAction icon={Users} label="Пользователи" href="/admin/users" color="blue" />
                <QuickAction icon={FileText} label="Ордера" href="/admin/orders" color="emerald" />
                <QuickAction icon={AlertTriangle} label="Споры" href="/admin/disputes" color="orange" badge={stats?.disputes?.open} />
                <QuickAction icon={TrendingUp} label="Аналитика" href="/admin/accounting" color="purple" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Exchange Rate Banner */}
        <Card className="bg-gradient-to-r from-emerald-500/5 via-teal-500/5 to-cyan-500/5 border-emerald-500/20">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-emerald-500/10 flex items-center justify-center">
                  <Wallet className="w-6 h-6 text-emerald-400" />
                </div>
                <div>
                  <div className="text-sm text-zinc-500 mb-0.5">Текущий курс USDT/RUB</div>
                  <div className="font-mono text-2xl font-bold text-emerald-400">
                    {(stats?.exchange_rate || 0).toFixed(2)} ₽
                  </div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-xs text-zinc-600">Источник: Rapira Exchange</div>
                <div className="text-xs text-zinc-500">Обновляется каждые 20 сек</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
};

export default AdminDashboard;
