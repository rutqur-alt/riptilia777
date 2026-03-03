import React, { useState, useEffect } from 'react';
import DashboardLayout from '@/components/DashboardLayout';
import { api, formatUSDT, formatRUB } from '@/lib/auth';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import {
  TrendingUp, RefreshCw, DollarSign, Wallet,
  BarChart3, ShoppingCart, Percent
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, PieChart as RechartPie,
  Pie, Cell, Legend
} from 'recharts';

const COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444'];

const MerchantAnalytics = () => {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState('week');

  useEffect(() => {
    fetchAnalytics();
  }, [period]);

  const fetchAnalytics = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/merchant/analytics?period=${period}`);
      setAnalytics(res.data);
    } catch (error) {
      const message = error.response?.data?.detail || error.message || 'Ошибка загрузки';
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  const formatTooltipValue = (value, name) => {
    if (name === 'volume_btc') return `${value.toFixed(8)} BTC`;
    if (name === 'volume_rub' || name === 'commission_rub') return formatRUB(value);
    return value;
  };

  const pieData = analytics ? [
    { name: 'Завершённых', value: analytics.orders?.completed || 0 },
    { name: 'В обработке', value: analytics.orders?.pending || 0 },
    { name: 'Отменённых', value: analytics.orders?.cancelled || 0 },
  ].filter(d => d.value > 0) : [];

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
            <h1 className="text-2xl font-bold font-['Chivo']">Аналитика</h1>
            <p className="text-zinc-400 text-sm">Статистика заказов и платежей</p>
          </div>
          <div className="flex gap-2">
            <div className="flex bg-zinc-800 rounded-lg p-1">
              {[
                { id: 'week', label: 'Неделя' },
                { id: 'month', label: 'Месяц' },
                { id: 'year', label: 'Год' },
              ].map((p) => (
                <button
                  key={p.id}
                  onClick={() => setPeriod(p.id)}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    period === p.id ? 'bg-emerald-500 text-white' : 'text-zinc-400 hover:text-white'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
            <Button variant="outline" onClick={fetchAnalytics} className="border-zinc-800">
              <RefreshCw className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Main Stats */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Balance Card */}
          <Card className="bg-gradient-to-br from-emerald-500/10 to-teal-500/5 border-emerald-500/30">
            <CardContent className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center">
                  <Wallet className="w-5 h-5 text-emerald-400" />
                </div>
                <span className="text-xs text-emerald-400">Баланс</span>
              </div>
              <div className="font-['JetBrains_Mono'] text-2xl font-bold mb-1">
                {formatUSDT(analytics?.balance_usdt || 0)} <span className="text-sm text-zinc-500">USDT</span>
              </div>
            </CardContent>
          </Card>

          {/* Volume Card */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center">
                  <TrendingUp className="w-5 h-5 text-purple-400" />
                </div>
                <span className="text-xs text-purple-400">Оборот</span>
              </div>
              <div className="font-['JetBrains_Mono'] text-2xl font-bold mb-1">
                {formatRUB(analytics?.volume?.total_rub || 0)}
              </div>
              <div className="text-sm text-zinc-400">
                ≈ {formatUSDT(analytics?.volume?.total_usdt || 0)} USDT
              </div>
            </CardContent>
          </Card>

          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
                  <ShoppingCart className="w-5 h-5 text-blue-400" />
                </div>
              </div>
              <div className="font-['JetBrains_Mono'] text-2xl font-bold mb-1">
                {analytics?.orders?.total || 0}
              </div>
              <div className="text-sm text-zinc-400">Всего заказов</div>
            </CardContent>
          </Card>

          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="w-10 h-10 rounded-lg bg-orange-500/10 flex items-center justify-center">
                  <DollarSign className="w-5 h-5 text-orange-400" />
                </div>
              </div>
              <div className="font-['JetBrains_Mono'] text-2xl font-bold mb-1">
                {formatRUB(analytics?.avg_order_rub || 0)}
              </div>
              <div className="text-sm text-zinc-400">Средний чек</div>
            </CardContent>
          </Card>
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Volume Chart */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="p-6">
              <h3 className="text-lg font-semibold mb-4 font-['Chivo'] flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-emerald-400" />
                Оборот по дням
              </h3>
              <div className="h-64">
                {analytics?.daily_volume?.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={analytics.daily_volume}>
                      <defs>
                        <linearGradient id="colorVolume" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                      <XAxis dataKey="date" stroke="#666" fontSize={12} tickFormatter={(val) => val.slice(5)} />
                      <YAxis stroke="#666" fontSize={12} tickFormatter={(val) => `${(val/1000).toFixed(0)}k`} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: '#18181b', border: '1px solid #333', borderRadius: '8px' }}
                        formatter={formatTooltipValue}
                      />
                      <Area type="monotone" dataKey="volume_rub" stroke="#10b981" fillOpacity={1} fill="url(#colorVolume)" name="volume_rub" />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-full text-zinc-500">Нет данных</div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Orders Chart */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="p-6">
              <h3 className="text-lg font-semibold mb-4 font-['Chivo'] flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-blue-400" />
                Заказы по дням
              </h3>
              <div className="h-64">
                {analytics?.daily_orders?.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={analytics.daily_orders}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                      <XAxis dataKey="date" stroke="#666" fontSize={12} tickFormatter={(val) => val.slice(5)} />
                      <YAxis stroke="#666" fontSize={12} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: '#18181b', border: '1px solid #333', borderRadius: '8px' }}
                      />
                      <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Заказы" />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-full text-zinc-500">Нет данных</div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Pie & Summary */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="p-6">
              <h3 className="text-lg font-semibold mb-4 font-['Chivo']">Статусы заказов</h3>
              <div className="h-48">
                {pieData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <RechartPie>
                      <Pie
                        data={pieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={40}
                        outerRadius={70}
                        paddingAngle={5}
                        dataKey="value"
                      >
                        {pieData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Legend />
                      <Tooltip contentStyle={{ backgroundColor: '#18181b', border: '1px solid #333', borderRadius: '8px' }} />
                    </RechartPie>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-full text-zinc-500">Нет данных</div>
                )}
              </div>
            </CardContent>
          </Card>

          <Card className="bg-zinc-900 border-zinc-800 lg:col-span-2">
            <CardContent className="p-6">
              <h3 className="text-lg font-semibold mb-4 font-['Chivo']">Итоги периода</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 bg-zinc-800/50 rounded-lg">
                  <div className="text-sm text-zinc-400 mb-1">Всего заказов</div>
                  <div className="text-xl font-bold">{analytics?.orders?.total || 0}</div>
                </div>
                <div className="p-4 bg-zinc-800/50 rounded-lg">
                  <div className="text-sm text-zinc-400 mb-1">Завершённых</div>
                  <div className="text-xl font-bold text-emerald-400">{analytics?.orders?.completed || 0}</div>
                </div>
                <div className="p-4 bg-zinc-800/50 rounded-lg">
                  <div className="text-sm text-zinc-400 mb-1">В обработке</div>
                  <div className="text-xl font-bold text-yellow-400">{analytics?.orders?.pending || 0}</div>
                </div>
                <div className="p-4 bg-zinc-800/50 rounded-lg">
                  <div className="text-sm text-zinc-400 mb-1">Конверсия</div>
                  <div className="text-xl font-bold">{analytics?.conversion_rate?.toFixed(1) || 0}%</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </DashboardLayout>
  );
};

export default MerchantAnalytics;
