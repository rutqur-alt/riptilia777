import React, { useState, useEffect } from 'react';
import DashboardLayout from '@/components/DashboardLayout';
import { api, formatRUB, formatUSDT } from '@/lib/auth';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from 'sonner';
import { 
  BarChart3, 
  TrendingUp, 
  Clock, 
  CheckCircle, 
  XCircle, 
  AlertTriangle,
  RefreshCw,
  Gauge
} from 'lucide-react';

const MerchantStats = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState('today');

  useEffect(() => {
    fetchStats();
  }, [period]);

  const fetchStats = async () => {
    try {
      setLoading(true);
      const res = await api.get('/merchant/stats', { params: { period } });
      setStats(res.data.data);
    } catch (error) {
      toast.error('Ошибка загрузки статистики');
    } finally {
      setLoading(false);
    }
  };

  const getPeriodLabel = (p) => {
    switch (p) {
      case 'today': return 'Сегодня';
      case 'week': return 'Неделя';
      case 'month': return 'Месяц';
      case 'all': return 'Всё время';
      default: return p;
    }
  };

  if (loading && !stats) {
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
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold font-['Chivo']">Статистика API</h1>
            <p className="text-zinc-400 text-sm">Аналитика использования Invoice API</p>
          </div>
          <div className="flex gap-3">
            <Select value={period} onValueChange={setPeriod}>
              <SelectTrigger className="w-40 bg-zinc-900 border-zinc-800" data-testid="period-select">
                <SelectValue placeholder="Период" />
              </SelectTrigger>
              <SelectContent className="bg-zinc-900 border-zinc-800">
                <SelectItem value="today">Сегодня</SelectItem>
                <SelectItem value="week">Неделя</SelectItem>
                <SelectItem value="month">Месяц</SelectItem>
                <SelectItem value="all">Всё время</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={fetchStats} className="border-zinc-800" disabled={loading}>
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>

        {stats && (
          <>
            {/* Summary Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Card className="bg-zinc-900 border-zinc-800">
                <CardContent className="p-4">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-blue-500/20 rounded-lg">
                      <BarChart3 className="w-5 h-5 text-blue-400" />
                    </div>
                    <div>
                      <div className="text-2xl font-bold font-['JetBrains_Mono']">
                        {stats.summary.total_invoices}
                      </div>
                      <div className="text-xs text-zinc-500">Всего инвойсов</div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-zinc-900 border-zinc-800">
                <CardContent className="p-4">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-emerald-500/20 rounded-lg">
                      <CheckCircle className="w-5 h-5 text-emerald-400" />
                    </div>
                    <div>
                      <div className="text-2xl font-bold font-['JetBrains_Mono'] text-emerald-400">
                        {stats.summary.paid}
                      </div>
                      <div className="text-xs text-zinc-500">Оплачено</div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-zinc-900 border-zinc-800">
                <CardContent className="p-4">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-yellow-500/20 rounded-lg">
                      <Clock className="w-5 h-5 text-yellow-400" />
                    </div>
                    <div>
                      <div className="text-2xl font-bold font-['JetBrains_Mono'] text-yellow-400">
                        {stats.summary.pending}
                      </div>
                      <div className="text-xs text-zinc-500">В ожидании</div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-zinc-900 border-zinc-800">
                <CardContent className="p-4">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-orange-500/20 rounded-lg">
                      <AlertTriangle className="w-5 h-5 text-orange-400" />
                    </div>
                    <div>
                      <div className="text-2xl font-bold font-['JetBrains_Mono'] text-orange-400">
                        {stats.summary.disputes}
                      </div>
                      <div className="text-xs text-zinc-500">Споры</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Volume & Conversion */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader>
                  <CardTitle className="text-lg font-['Chivo'] flex items-center gap-2">
                    <TrendingUp className="w-5 h-5 text-emerald-400" />
                    Объём за {getPeriodLabel(period).toLowerCase()}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div>
                      <div className="text-sm text-zinc-500 mb-1">Рубли</div>
                      <div className="text-3xl font-bold font-['JetBrains_Mono']">
                        {formatRUB(stats.volume.total_rub)}
                      </div>
                    </div>
                    <div>
                      <div className="text-sm text-zinc-500 mb-1">USDT</div>
                      <div className="text-2xl font-bold font-['JetBrains_Mono'] text-emerald-400">
                        {formatUSDT(stats.volume.total_usdt)}
                      </div>
                    </div>
                    <div className="pt-3 border-t border-zinc-800">
                      <div className="text-sm text-zinc-500 mb-1">Средний чек</div>
                      <div className="text-xl font-['JetBrains_Mono']">
                        {formatRUB(stats.volume.average_amount_rub)}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader>
                  <CardTitle className="text-lg font-['Chivo'] flex items-center gap-2">
                    <Gauge className="w-5 h-5 text-blue-400" />
                    Конверсия
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-center h-32">
                    <div className="relative">
                      <div className="text-5xl font-bold font-['JetBrains_Mono']">
                        {stats.conversion_rate.toFixed(1)}%
                      </div>
                      <div className="text-center text-sm text-zinc-500 mt-2">
                        оплаченных инвойсов
                      </div>
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-4 pt-4 border-t border-zinc-800">
                    <div className="text-center">
                      <div className="text-lg font-bold text-emerald-400">{stats.summary.paid}</div>
                      <div className="text-xs text-zinc-500">Успех</div>
                    </div>
                    <div className="text-center">
                      <div className="text-lg font-bold text-red-400">{stats.summary.failed}</div>
                      <div className="text-xs text-zinc-500">Ошибки</div>
                    </div>
                    <div className="text-center">
                      <div className="text-lg font-bold text-yellow-400">{stats.summary.pending}</div>
                      <div className="text-xs text-zinc-500">Ожидание</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Rate Limits */}
            {stats.rate_limits && (
              <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader>
                  <CardTitle className="text-lg font-['Chivo']">Rate Limits</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {Object.entries(stats.rate_limits).map(([endpoint, info]) => (
                      <div key={endpoint} className="bg-zinc-800/50 rounded-lg p-4">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium capitalize">{endpoint}</span>
                          <span className="text-xs text-zinc-500">{info.limit}/мин</span>
                        </div>
                        <div className="w-full bg-zinc-700 rounded-full h-2 mb-2">
                          <div 
                            className="bg-emerald-500 h-2 rounded-full transition-all"
                            style={{ width: `${(info.remaining / info.limit) * 100}%` }}
                          />
                        </div>
                        <div className="flex justify-between text-xs text-zinc-500">
                          <span>Осталось: {info.remaining}</span>
                          <span>Сброс: {info.reset_in}с</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  );
};

export default MerchantStats;
