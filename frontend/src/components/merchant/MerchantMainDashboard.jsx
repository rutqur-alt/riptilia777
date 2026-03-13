import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";
import {
  Activity,
  AlertTriangle,
  ArrowDown,
  ArrowDownRight,
  ArrowUp,
  ArrowUpRight,
  Banknote,
  Clock,
  DollarSign,
  Loader,
  Percent,
  RefreshCw,
  TrendingUp,
  Wallet
} from "lucide-react";

import { API, useAuth } from "@/App";
import { Button } from "@/components/ui/button";

export default function MerchantMainDashboard() {
  const { user, token } = useAuth();
  const navigate = useNavigate();
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
  const rates = analytics?.rates || {};
  const recent = analytics?.recent_activity || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Дашборд</h1>
          <p className="text-[#71717A] text-sm mt-1">Добро пожаловать, {merchant.name || user?.merchant_name || user?.login}</p>
        </div>
        <div className="flex items-center gap-3">
          {exchangeRate && (
            <div className="bg-[#121212] border border-white/5 rounded-xl px-4 py-2 flex items-center gap-2">
              <div className="w-2 h-2 bg-[#10B981] rounded-full animate-pulse" />
              <span className="text-[#71717A] text-sm">USDT/RUB</span>
              <span className="text-white font-bold font-['JetBrains_Mono']">{exchangeRate.base_rate?.toFixed(2)} ₽</span>
              <span className="text-[#52525B] text-xs">({exchangeRate.rate_source})</span>
            </div>
          )}
          <Button
            onClick={() => {
              fetchAnalytics();
              fetchExchangeRate();
            }}
            variant="outline"
            size="sm"
            className="border-white/10 text-[#71717A] hover:text-white"
          >
            <RefreshCw className="w-4 h-4 mr-2" /> Обновить
          </Button>
        </div>
      </div>

      {/* Live Exchange Rate Banner */}
      {exchangeRate && (
        <div className="bg-gradient-to-r from-[#1E3A5F] to-[#0F172A] border border-[#3B82F6]/20 rounded-2xl p-5">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-[#3B82F6]/10 rounded-xl flex items-center justify-center">
                <TrendingUp className="w-6 h-6 text-[#3B82F6]" />
              </div>
              <div>
                <div className="text-white font-semibold text-lg">Базовый курс USDT</div>
                <div className="text-[#71717A] text-xs">Источник: биржа {exchangeRate.rate_source} · Обновляется каждые 5 мин</div>
              </div>
            </div>
            <div className="flex items-center gap-6">
              <div className="text-center">
                <div className="text-[#71717A] text-xs mb-1">Базовый курс</div>
                <div className="text-3xl font-bold text-[#3B82F6] font-['JetBrains_Mono']">{exchangeRate.base_rate?.toFixed(2)} ₽</div>
              </div>
              {exchangeRate.rate_updated_at && (
                <div className="text-center">
                  <div className="text-[#71717A] text-xs mb-1">Обновлено</div>
                  <div className="text-sm text-white">{new Date(exchangeRate.rate_updated_at).toLocaleTimeString("ru-RU")}</div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Balance Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-gradient-to-br from-[#F97316] to-[#EA580C] rounded-2xl p-5 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-white/5 rounded-full -mr-10 -mt-10" />
          <div className="relative">
            <div className="flex items-center gap-2 text-white/80 text-sm mb-2">
              <Wallet className="w-4 h-4" /> Доступный баланс
            </div>
            <div className="text-3xl font-bold text-white font-['JetBrains_Mono']">
              {((merchant.balance_usdt || 0) - (merchant.frozen_usdt || 0)).toFixed(2)}
            </div>
            <div className="text-white/60 text-sm mt-1">USDT</div>
          </div>
        </div>

        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="flex items-center gap-2 text-[#71717A] text-sm mb-2">
            <Clock className="w-4 h-4" /> Заморожено
          </div>
          <div className="text-3xl font-bold text-[#F59E0B] font-['JetBrains_Mono']">{(merchant.frozen_usdt || 0).toFixed(2)}</div>
          <div className="text-[#52525B] text-sm mt-1">USDT</div>
        </div>

        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="flex items-center gap-2 text-[#71717A] text-sm mb-2">
            <TrendingUp className="w-4 h-4" /> Всего комиссий оплачено
          </div>
          <div className="text-3xl font-bold text-[#EF4444] font-['JetBrains_Mono']">
            {(merchant.total_commission_paid || 0).toFixed(2)}
          </div>
          <div className="text-[#52525B] text-sm mt-1">USDT</div>
        </div>
      </div>

      {/* Commission Info */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Percent className="w-5 h-5 text-[#F97316]" />
          <h2 className="text-lg font-semibold text-white">Ваши комиссии</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-[#0A0A0A] rounded-xl p-4 border border-white/5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className="w-10 h-10 bg-[#3B82F6]/10 rounded-xl flex items-center justify-center">
                  <ArrowDown className="w-5 h-5 text-[#3B82F6]" />
                </div>
                <div>
                  <div className="text-white font-medium">Пополнение (Платежи)</div>
                  <div className="text-xs text-[#71717A]">Комиссия с входящих платежей</div>
                </div>
              </div>
              <div className="text-2xl font-bold text-[#3B82F6] font-['JetBrains_Mono']">{merchant.commission_rate || 0}%</div>
            </div>
            <div className="text-xs text-[#52525B]">Списывается с каждого успешного пополнения от клиента</div>
          </div>

          <div className="bg-[#0A0A0A] rounded-xl p-4 border border-white/5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className="w-10 h-10 bg-[#10B981]/10 rounded-xl flex items-center justify-center">
                  <ArrowUp className="w-5 h-5 text-[#10B981]" />
                </div>
                <div>
                  <div className="text-white font-medium">Выплаты (Payouts)</div>
                  <div className="text-xs text-[#71717A]">Комиссия с выплат</div>
                </div>
              </div>
              <div className="text-2xl font-bold text-[#10B981] font-['JetBrains_Mono']">{merchant.withdrawal_commission || 3}%</div>
            </div>
            <div className="text-xs text-[#52525B]">
              Курс для вас: {rates.merchant_rate || "—"} ₽/USDT (базовый: {exchangeRate?.base_rate?.toFixed(2) || rates.base_rate || "—"} ₽)
            </div>
          </div>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div
          className="bg-[#121212] border border-white/5 rounded-xl p-4 cursor-pointer hover:bg-white/5 transition-colors"
          onClick={() => navigate("/merchant/payments")}
        >
          <div className="flex items-center gap-2 text-[#71717A] text-xs mb-2">
            <DollarSign className="w-3.5 h-3.5" /> Платежи
          </div>
          <div className="text-2xl font-bold text-white">{deposits.count || 0}</div>
          <div className="text-xs text-[#10B981] mt-1">+{(deposits.total_usdt || 0).toFixed(2)} USDT</div>
        </div>

        <div
          className="bg-[#121212] border border-white/5 rounded-xl p-4 cursor-pointer hover:bg-white/5 transition-colors"
          onClick={() => navigate("/merchant/withdrawal-requests")}
        >
          <div className="flex items-center gap-2 text-[#71717A] text-xs mb-2">
            <ArrowUpRight className="w-3.5 h-3.5" /> Выплаты
          </div>
          <div className="text-2xl font-bold text-white">{(payouts.active_count || 0) + (payouts.completed_count || 0)}</div>
          <div className="text-xs text-[#F59E0B] mt-1">{payouts.active_count || 0} активных</div>
        </div>

        <div className="bg-[#121212] border border-white/5 rounded-xl p-4">
          <div className="flex items-center gap-2 text-[#71717A] text-xs mb-2">
            <Banknote className="w-3.5 h-3.5" /> Оборот (RUB)
          </div>
          <div className="text-2xl font-bold text-white font-['JetBrains_Mono']">
            {((deposits.total_rub || 0) + (payouts.total_rub || 0)).toLocaleString("ru-RU", { maximumFractionDigits: 0 })}
          </div>
          <div className="text-xs text-[#71717A] mt-1">Всего в рублях</div>
        </div>

        <div className="bg-[#121212] border border-white/5 rounded-xl p-4">
          <div className="flex items-center gap-2 text-[#71717A] text-xs mb-2">
            <AlertTriangle className="w-3.5 h-3.5" /> Споры
          </div>
          <div className="text-2xl font-bold text-white">{(deposits.disputed_count || 0) + (payouts.orders_disputed || 0)}</div>
          <div className="text-xs text-[#EF4444] mt-1">Требуют внимания</div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl overflow-hidden">
        <div className="p-4 border-b border-white/5 flex items-center justify-between">
          <h3 className="text-white font-medium flex items-center gap-2">
            <Activity className="w-4 h-4 text-[#F97316]" /> Последние операции
          </h3>
          <Link to="/merchant/analytics" className="text-[#F97316] text-sm hover:underline">
            Вся аналитика
          </Link>
        </div>

        {recent.length === 0 ? (
          <div className="p-8 text-center">
            <Activity className="w-12 h-12 text-[#52525B] mx-auto mb-3" />
            <p className="text-[#71717A]">Пока нет операций</p>
          </div>
        ) : (
          <div className="divide-y divide-white/5">
            {recent.slice(0, 8).map((item, idx) => (
              <div key={idx} className="p-4 flex items-center justify-between hover:bg-white/5 transition-colors">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${item.type === "deposit" ? "bg-[#3B82F6]/10" : "bg-[#10B981]/10"}`}>
                    {item.type === "deposit" ? (
                      <ArrowDownRight className="w-5 h-5 text-[#3B82F6]" />
                    ) : (
                      <ArrowUpRight className="w-5 h-5 text-[#10B981]" />
                    )}
                  </div>
                  <div>
                    <div className="text-white text-sm font-medium">{item.type === "deposit" ? "Пополнение" : "Выплата"}</div>
                    <div className="text-xs text-[#52525B]">{item.created_at ? new Date(item.created_at).toLocaleString("ru-RU") : "—"}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div
                    className={`font-medium font-['JetBrains_Mono'] text-sm ${item.type === "deposit" ? "text-[#3B82F6]" : "text-[#10B981]"}`}
                  >
                    {item.type === "deposit" ? "+" : "-"}
                    {(item.amount_usdt || 0).toFixed(2)} USDT
                  </div>
                  <div className="text-xs text-[#52525B]">{(item.amount_rub || 0).toLocaleString("ru-RU", { maximumFractionDigits: 0 })} ₽</div>
                </div>
                <div>
                  <span
                    className={`text-xs px-2 py-1 rounded-lg ${
                      item.status === "completed"
                        ? "bg-[#10B981]/10 text-[#10B981]"
                        : item.status === "active"
                          ? "bg-[#3B82F6]/10 text-[#3B82F6]"
                          : item.status === "cancelled"
                            ? "bg-[#71717A]/10 text-[#71717A]"
                            : item.status === "dispute"
                              ? "bg-[#EF4444]/10 text-[#EF4444]"
                              : "bg-[#F59E0B]/10 text-[#F59E0B]"
                    }`}
                  >
                    {item.status === "completed"
                      ? "Завершено"
                      : item.status === "active"
                        ? "Активно"
                        : item.status === "cancelled"
                          ? "Отменено"
                          : item.status === "dispute"
                            ? "Спор"
                            : item.status === "in_progress"
                              ? "В процессе"
                              : item.status || "—"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
