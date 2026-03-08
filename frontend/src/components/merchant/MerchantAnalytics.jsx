import { useState, useEffect } from "react";
import axios from "axios";
import { ArrowDownRight, ArrowUpRight, Loader, Percent, RefreshCw, Target, TrendingUp, Wallet } from "lucide-react";
import { useAuth, API } from "@/App";
import { Button } from "@/components/ui/button";

export default function MerchantAnalytics() {
  const { token, user } = useAuth();
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exchangeRate, setExchangeRate] = useState(null);

  useEffect(() => {
    fetchAnalytics();
    fetchExchangeRate();
    // Auto-refresh rate every 5 minutes
    const rateInterval = setInterval(fetchExchangeRate, 300000);
    return () => clearInterval(rateInterval);
  }, []);

  const fetchExchangeRate = async () => {
    try {
      const response = await axios.get(`${API.replace('/api', '')}/api/exchange-rate`);
      setExchangeRate(response.data);
    } catch (error) {
      console.error("Failed to fetch exchange rate:", error);
    }
  };

  const fetchAnalytics = async () => {
    try {
      const response = await axios.get(`${API}/merchant/analytics`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setAnalytics(response.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader className="w-8 h-8 text-[#F97316] animate-spin" />
      </div>
    );
  }

  const merchant = analytics?.merchant || {};
  const deposits = analytics?.deposits || {};
  const payouts = analytics?.payouts || {};
  const invoices = analytics?.invoices || {};
  const withdrawals = analytics?.withdrawals || {};
  const rates = analytics?.rates || {};

  const totalVolume = (deposits.total_usdt || 0) + (payouts.total_usdt_deducted || 0);
  const totalRub = (deposits.total_rub || 0) + (payouts.total_rub || 0);
  const successRate = deposits.count > 0 
    ? ((deposits.count / (deposits.count + deposits.cancelled_count)) * 100).toFixed(1) 
    : "0.0";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Аналитика</h1>
          <p className="text-[#71717A] text-sm mt-1">Подробная статистика вашей деятельности</p>
        </div>
        <Button onClick={fetchAnalytics} variant="outline" size="sm" className="border-white/10 text-[#71717A] hover:text-white">
          <RefreshCw className="w-4 h-4 mr-2" /> Обновить
        </Button>
      </div>

      {/* Commission Overview */}
      <div className="bg-gradient-to-r from-[#1a1a2e] to-[#16213e] border border-[#3B82F6]/20 rounded-2xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Percent className="w-5 h-5 text-[#3B82F6]" />
          <h2 className="text-lg font-semibold text-white">Комиссии</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-black/20 rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Комиссия на платежи</div>
            <div className="text-3xl font-bold text-[#3B82F6] font-['JetBrains_Mono']">{merchant.commission_rate || 0}%</div>
            <div className="text-xs text-[#52525B] mt-1">С каждого пополнения</div>
          </div>
          <div className="bg-black/20 rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Комиссия на выплаты</div>
            <div className="text-3xl font-bold text-[#10B981] font-['JetBrains_Mono']">{merchant.withdrawal_commission || 3}%</div>
            <div className="text-xs text-[#52525B] mt-1">С каждой выплаты</div>
          </div>
          <div className="bg-black/20 rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Оплачено комиссий</div>
            <div className="text-3xl font-bold text-[#EF4444] font-['JetBrains_Mono']">{(merchant.total_commission_paid || 0).toFixed(2)}</div>
            <div className="text-xs text-[#52525B] mt-1">USDT за всё время</div>
          </div>
          <div className="bg-black/20 rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Ваш курс выплат</div>
            <div className="text-3xl font-bold text-[#F97316] font-['JetBrains_Mono']">{rates.merchant_rate || "—"}</div>
            <div className="text-xs text-[#52525B] mt-1">₽ за 1 USDT</div>
          </div>
        </div>
      </div>

      {/* Deposits Stats */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <ArrowDownRight className="w-5 h-5 text-[#3B82F6]" />
          <h2 className="text-lg font-semibold text-white">Пополнения (Платежи)</h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Всего сделок</div>
            <div className="text-2xl font-bold text-white">{deposits.count || 0}</div>
          </div>
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Оборот USDT</div>
            <div className="text-2xl font-bold text-[#3B82F6] font-['JetBrains_Mono']">{(deposits.total_usdt || 0).toFixed(2)}</div>
          </div>
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Оборот RUB</div>
            <div className="text-2xl font-bold text-white font-['JetBrains_Mono']">{(deposits.total_rub || 0).toLocaleString("ru-RU", {maximumFractionDigits: 0})}</div>
          </div>
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Комиссия</div>
            <div className="text-2xl font-bold text-[#EF4444] font-['JetBrains_Mono']">{(deposits.total_commission || 0).toFixed(4)}</div>
            <div className="text-xs text-[#52525B]">USDT</div>
          </div>
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Активные</div>
            <div className="text-2xl font-bold text-[#F59E0B]">{deposits.active_count || 0}</div>
          </div>
        </div>
        
        {/* Progress bars */}
        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-[#71717A]">Успешность</span>
              <span className="text-xs text-[#10B981] font-medium">{successRate}%</span>
            </div>
            <div className="w-full bg-white/5 rounded-full h-2">
              <div className="bg-[#10B981] h-2 rounded-full transition-all" style={{ width: `${Math.min(parseFloat(successRate), 100)}%` }} />
            </div>
          </div>
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-[#71717A]">Споры</span>
              <span className="text-xs text-[#EF4444] font-medium">{deposits.disputed_count || 0}</span>
            </div>
            <div className="w-full bg-white/5 rounded-full h-2">
              <div className="bg-[#EF4444] h-2 rounded-full transition-all" style={{ width: `${deposits.count > 0 ? ((deposits.disputed_count || 0) / deposits.count * 100) : 0}%` }} />
            </div>
          </div>
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-[#71717A]">Отменённые</span>
              <span className="text-xs text-[#71717A] font-medium">{deposits.cancelled_count || 0}</span>
            </div>
            <div className="w-full bg-white/5 rounded-full h-2">
              <div className="bg-[#71717A] h-2 rounded-full transition-all" style={{ width: `${deposits.count > 0 ? ((deposits.cancelled_count || 0) / (deposits.count + (deposits.cancelled_count || 0)) * 100) : 0}%` }} />
            </div>
          </div>
        </div>
      </div>

      {/* Payouts Stats */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <ArrowUpRight className="w-5 h-5 text-[#10B981]" />
          <h2 className="text-lg font-semibold text-white">Выплаты (Payouts)</h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Активные заявки</div>
            <div className="text-2xl font-bold text-[#F59E0B]">{payouts.active_count || 0}</div>
          </div>
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Завершённые</div>
            <div className="text-2xl font-bold text-[#10B981]">{payouts.completed_count || 0}</div>
          </div>
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Списано USDT</div>
            <div className="text-2xl font-bold text-white font-['JetBrains_Mono']">{(payouts.total_usdt_deducted || 0).toFixed(2)}</div>
          </div>
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Выплачено RUB</div>
            <div className="text-2xl font-bold text-white font-['JetBrains_Mono']">{(payouts.total_rub || 0).toLocaleString("ru-RU", {maximumFractionDigits: 0})}</div>
          </div>
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="text-xs text-[#71717A] mb-1">Заказы (споры)</div>
            <div className="text-2xl font-bold text-[#EF4444]">{payouts.orders_disputed || 0}</div>
          </div>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-gradient-to-br from-[#10B981]/10 to-[#10B981]/5 border border-[#10B981]/20 rounded-2xl p-5">
          <div className="flex items-center gap-2 text-[#10B981] text-sm mb-2">
            <TrendingUp className="w-4 h-4" /> Общий оборот
          </div>
          <div className="text-2xl font-bold text-white font-['JetBrains_Mono']">
            {totalVolume.toFixed(2)} <span className="text-sm text-[#71717A]">USDT</span>
          </div>
          <div className="text-sm text-[#71717A] mt-1">
            {totalRub.toLocaleString("ru-RU", {maximumFractionDigits: 0})} ₽
          </div>
        </div>

        <div className="bg-gradient-to-br from-[#3B82F6]/10 to-[#3B82F6]/5 border border-[#3B82F6]/20 rounded-2xl p-5">
          <div className="flex items-center gap-2 text-[#3B82F6] text-sm mb-2">
            <Target className="w-4 h-4" /> Успешность
          </div>
          <div className="text-2xl font-bold text-white font-['JetBrains_Mono']">
            {successRate}%
          </div>
          <div className="text-sm text-[#71717A] mt-1">
            {deposits.count || 0} из {(deposits.count || 0) + (deposits.cancelled_count || 0)} сделок
          </div>
        </div>

        <div className="bg-gradient-to-br from-[#F97316]/10 to-[#F97316]/5 border border-[#F97316]/20 rounded-2xl p-5">
          <div className="flex items-center gap-2 text-[#F97316] text-sm mb-2">
            <Wallet className="w-4 h-4" /> Текущий баланс
          </div>
          <div className="text-2xl font-bold text-white font-['JetBrains_Mono']">
            {(merchant.balance_usdt || 0).toFixed(2)} <span className="text-sm text-[#71717A]">USDT</span>
          </div>
          <div className="text-sm text-[#71717A] mt-1">
            + {(merchant.frozen_usdt || 0).toFixed(2)} заморожено
          </div>
        </div>
      </div>
    </div>
  );
}
