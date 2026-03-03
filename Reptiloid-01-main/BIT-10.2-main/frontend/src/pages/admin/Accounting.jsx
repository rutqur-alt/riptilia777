import React, { useState, useEffect } from 'react';
import DashboardLayout from '@/components/DashboardLayout';
import { api, formatUSDT, formatRUB, formatDate } from '@/lib/auth';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import {
  TrendingUp, TrendingDown, DollarSign, ArrowUpRight, ArrowDownRight,
  RefreshCw, BarChart3, Wallet, PiggyBank, Calendar
} from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const AdminAccounting = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [updatingRate, setUpdatingRate] = useState(false);
  const [rateForm, setRateForm] = useState({ currency: 'USD', rate_rub: '' });
  const [usdtRate, setUsdtRate] = useState(0);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [accountingRes, rateRes] = await Promise.all([
        api.get('/admin/accounting'),
        api.get('/rates/usdt')
      ]);
      setData(accountingRes.data);
      setUsdtRate(rateRes.data.usdt_rub || 0);
    } catch (error) {
      toast.error('Ошибка загрузки данных');
    } finally {
      setLoading(false);
    }
  };

  const updateRate = async (e) => {
    e.preventDefault();
    if (!rateForm.rate_rub) return;

    setUpdatingRate(true);
    try {
      await api.post('/admin/currency/rates', {
        currency: rateForm.currency,
        rate_rub: parseFloat(rateForm.rate_rub),
        source: 'manual'
      });
      toast.success(`Курс ${rateForm.currency} обновлён`);
      setRateForm({ ...rateForm, rate_rub: '' });
      fetchData();
    } catch (error) {
      toast.error('Ошибка обновления курса');
    } finally {
      setUpdatingRate(false);
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
            <h1 className="text-2xl font-bold font-['Chivo']">Бухгалтерия</h1>
            <p className="text-zinc-400 text-sm">Финансовая отчётность платформы</p>
          </div>
          <Button variant="outline" onClick={fetchData} className="border-zinc-800">
            <RefreshCw className="w-4 h-4 mr-2" />
            Обновить
          </Button>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center">
                  <TrendingUp className="w-5 h-5 text-emerald-400" />
                </div>
                <span className="text-xs text-emerald-400">+{data?.summary?.total_orders || 0} сделок</span>
              </div>
              <div className="text-2xl font-bold font-['JetBrains_Mono']">
                {formatRUB(data?.summary?.total_volume_rub || 0)}
              </div>
              <div className="text-sm text-zinc-400">Общий оборот</div>
            </CardContent>
          </Card>

          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="w-10 h-10 rounded-lg bg-orange-500/20 flex items-center justify-center">
                  <DollarSign className="w-5 h-5 text-orange-400" />
                </div>
              </div>
              <div className="text-2xl font-bold font-['JetBrains_Mono']">
                {formatUSDT(data?.summary?.total_volume_usdt || 0)} <span className="text-sm text-zinc-500">USDT</span>
              </div>
              <div className="text-xs text-zinc-500">
                ≈ {formatRUB((data?.summary?.total_volume_usdt || 0) * usdtRate)}
              </div>
              <div className="text-sm text-zinc-400 mt-1">Оборот в USDT</div>
            </CardContent>
          </Card>

          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center">
                  <PiggyBank className="w-5 h-5 text-purple-400" />
                </div>
                <span className="text-xs text-purple-400">+ маркеры</span>
              </div>
              <div className="text-2xl font-bold font-['JetBrains_Mono'] text-emerald-400">
                +{formatUSDT(data?.summary?.platform_commission_usdt || 0)} <span className="text-sm text-zinc-500">USDT</span>
              </div>
              <div className="text-xs text-zinc-500">
                ≈ {formatRUB((data?.summary?.platform_commission_usdt || 0) * usdtRate)}
              </div>
              <div className="text-sm text-zinc-400 mt-1">Комиссия платформы</div>
            </CardContent>
          </Card>

          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
                  <Wallet className="w-5 h-5 text-blue-400" />
                </div>
              </div>
              <div className="text-2xl font-bold font-['JetBrains_Mono'] text-blue-400">
                {formatUSDT(data?.summary?.trader_commission_usdt || 0)} <span className="text-sm text-zinc-500">USDT</span>
              </div>
              <div className="text-xs text-zinc-500">
                ≈ {formatRUB((data?.summary?.trader_commission_usdt || 0) * usdtRate)}
              </div>
              <div className="text-sm text-zinc-400 mt-1">Выплачено трейдерам</div>
            </CardContent>
          </Card>
        </div>

        {/* Commission Distribution */}
        <Card className="bg-gradient-to-br from-zinc-900 to-zinc-900/50 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-emerald-400" />
              Распределение комиссий
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Total Commission */}
              <div className="bg-zinc-800/50 rounded-xl p-5 border border-zinc-700">
                <div className="text-sm text-zinc-400 mb-2">Всего комиссий</div>
                <div className="text-xl font-bold font-['JetBrains_Mono']">
                  {formatUSDT((data?.summary?.platform_commission_usdt || 0) + (data?.summary?.trader_commission_usdt || 0))} USDT
                </div>
                <div className="text-xs text-zinc-500">
                  ≈ {formatRUB(((data?.summary?.platform_commission_usdt || 0) + (data?.summary?.trader_commission_usdt || 0)) * usdtRate)}
                </div>
                <div className="mt-3 h-2 bg-zinc-700 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-purple-500 to-blue-500" style={{ width: '100%' }}></div>
                </div>
              </div>

              {/* Platform Share */}
              <div className="bg-purple-500/10 rounded-xl p-5 border border-purple-500/30">
                <div className="text-sm text-purple-400 mb-2">Доход платформы</div>
                <div className="text-xl font-bold font-['JetBrains_Mono'] text-purple-400">
                  +{formatUSDT(data?.summary?.platform_commission_usdt || 0)} USDT
                </div>
                <div className="text-xs text-zinc-500">
                  ≈ {formatRUB((data?.summary?.platform_commission_usdt || 0) * usdtRate)}
                </div>
                <div className="mt-3 h-2 bg-zinc-700 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-purple-500" 
                    style={{ 
                      width: `${Math.round(((data?.summary?.platform_commission_usdt || 0) / ((data?.summary?.platform_commission_usdt || 0) + (data?.summary?.trader_commission_usdt || 1))) * 100)}%` 
                    }}
                  ></div>
                </div>
                <div className="text-xs text-zinc-500 mt-2">Включая маркеры</div>
              </div>

              {/* Traders Share */}
              <div className="bg-blue-500/10 rounded-xl p-5 border border-blue-500/30">
                <div className="text-sm text-blue-400 mb-2">Выплачено трейдерам</div>
                <div className="text-xl font-bold font-['JetBrains_Mono'] text-blue-400">
                  {formatUSDT(data?.summary?.trader_commission_usdt || 0)} USDT
                </div>
                <div className="text-xs text-zinc-500">
                  ≈ {formatRUB((data?.summary?.trader_commission_usdt || 0) * usdtRate)}
                </div>
                <div className="mt-3 h-2 bg-zinc-700 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-blue-500" 
                    style={{ 
                      width: `${Math.round(((data?.summary?.trader_commission_usdt || 0) / ((data?.summary?.platform_commission_usdt || 1) + (data?.summary?.trader_commission_usdt || 0))) * 100)}%` 
                    }}
                  ></div>
                </div>
                <div className="text-xs text-zinc-500 mt-2">По ставкам трейдеров</div>
              </div>
            </div>

            {/* Info */}
            <div className="mt-6 bg-zinc-800 rounded-lg p-4 text-sm">
              <div className="text-zinc-400 mb-2">💡 Как это работает:</div>
              <div className="text-zinc-300 space-y-1">
                <div>• <span className="text-amber-400">Накрутка</span> — настраивается для каждого мерчанта</div>
                <div>• <span className="text-blue-400">Доля трейдера</span> — настраивается в профиле трейдера</div>
                <div>• <span className="text-purple-400">Платформа</span> получает остаток + маркер (5-20₽)</div>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Курсы валют */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <DollarSign className="w-4 h-4" />
                Курсы валют
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                {data?.currency_rates && (
                  <div className="bg-zinc-800 rounded-lg p-3 col-span-2">
                    <div className="text-xs text-zinc-500">USDT</div>
                    <div className="font-['JetBrains_Mono'] font-medium text-emerald-400">
                      {formatRUB(data.currency_rates.USDT || 0)}
                    </div>
                    <div className="text-xs text-zinc-500 mt-1">
                      Источник: {data.currency_rates.source || 'fallback'}
                    </div>
                  </div>
                )}
              </div>
              
              {/* Обновление курса */}
              <form onSubmit={updateRate} className="space-y-3 pt-4 border-t border-zinc-800">
                <Label className="text-sm text-zinc-400">Обновить курс</Label>
                <div className="flex gap-2">
                  <Select 
                    value={rateForm.currency} 
                    onValueChange={(v) => setRateForm({...rateForm, currency: v})}
                  >
                    <SelectTrigger className="w-24 bg-zinc-800 border-zinc-700">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-zinc-900 border-zinc-800">
                      <SelectItem value="USD">USD</SelectItem>
                      <SelectItem value="EUR">EUR</SelectItem>
                      <SelectItem value="USDT">USDT</SelectItem>
                    </SelectContent>
                  </Select>
                  <Input
                    type="number"
                    step="0.01"
                    value={rateForm.rate_rub}
                    onChange={(e) => setRateForm({...rateForm, rate_rub: e.target.value})}
                    placeholder="Курс в RUB"
                    className="flex-1 bg-zinc-800 border-zinc-700"
                  />
                  <Button type="submit" disabled={updatingRate} className="bg-emerald-500 hover:bg-emerald-600">
                    OK
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          {/* Статистика по дням */}
          <Card className="bg-zinc-900 border-zinc-800 lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <BarChart3 className="w-4 h-4" />
                Статистика по дням
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-zinc-800">
                      <th className="text-left text-xs text-zinc-500 pb-2">Дата</th>
                      <th className="text-right text-xs text-zinc-500 pb-2">Сделок</th>
                      <th className="text-right text-xs text-zinc-500 pb-2">Оборот</th>
                      <th className="text-right text-xs text-zinc-500 pb-2">Комиссия</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data?.daily_stats?.map((day, i) => (
                      <tr key={day.date} className="border-b border-zinc-800/50">
                        <td className="py-2 text-sm">
                          <div className="flex items-center gap-2">
                            <Calendar className="w-3 h-3 text-zinc-500" />
                            {day.date}
                          </div>
                        </td>
                        <td className="py-2 text-right font-['JetBrains_Mono'] text-sm">
                          {day.orders}
                        </td>
                        <td className="py-2 text-right font-['JetBrains_Mono'] text-sm">
                          {formatRUB(day.volume_rub)}
                        </td>
                        <td className="py-2 text-right font-['JetBrains_Mono'] text-sm text-emerald-400">
                          +{formatUSDT(day.commission_usdt)}
                        </td>
                      </tr>
                    ))}
                    {(!data?.daily_stats || data.daily_stats.length === 0) && (
                      <tr>
                        <td colSpan={4} className="py-8 text-center text-zinc-500">
                          Нет данных за последние 30 дней
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Trader Commissions */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-base">Комиссии трейдеров</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-['JetBrains_Mono'] text-blue-400">
              {formatUSDT(data?.summary?.trader_commission_usdt || 0)}
            </div>
            <div className="text-sm text-zinc-400">Выплачено трейдерам за все время</div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
};

export default AdminAccounting;
