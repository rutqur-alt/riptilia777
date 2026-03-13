import React, { useState, useEffect } from "react";
import { toast } from "sonner";
import {
  DollarSign, TrendingUp, Users, Briefcase,
  ArrowDownRight, Store, ChevronDown, ChevronRight,
  Calendar, RefreshCw, QrCode, BarChart3
} from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { LoadingSpinner, PageHeader } from "@/components/admin/SharedComponents";

// Period options for filter
const PERIODS = [
  { value: "today", label: "Сегодня" },
  { value: "yesterday", label: "Вчера" },
  { value: "week", label: "Неделя" },
  { value: "month", label: "Месяц" },
  { value: "year", label: "Год" },
  { value: "all", label: "Всё время" },
];

// Source config: icon, color
const SOURCE_CONFIG = {
  qr_aggregator: { icon: QrCode, color: "#8B5CF6", bg: "from-[#8B5CF6]/20 to-[#8B5CF6]/5 border-[#8B5CF6]/20" },
  trader_commissions: { icon: Users, color: "#10B981", bg: "from-[#10B981]/20 to-[#10B981]/5 border-[#10B981]/20" },
  merchant_commissions: { icon: Briefcase, color: "#F59E0B", bg: "from-[#F59E0B]/20 to-[#F59E0B]/5 border-[#F59E0B]/20" },
  withdrawal_fees: { icon: ArrowDownRight, color: "#3B82F6", bg: "from-[#3B82F6]/20 to-[#3B82F6]/5 border-[#3B82F6]/20" },
  marketplace: { icon: Store, color: "#EF4444", bg: "from-[#EF4444]/20 to-[#EF4444]/5 border-[#EF4444]/20" },
};

function IncomeSourceCard({ sourceKey, source, expanded, onToggle }) {
  const config = SOURCE_CONFIG[sourceKey] || { icon: DollarSign, color: "#71717A", bg: "from-white/5 to-white/2 border-white/10" };
  const Icon = config.icon;
  const hasDetails = source.details && source.details.length > 0;
  const hasBreakdown = source.breakdown && Object.keys(source.breakdown).length > 0;

  return (
    <div className="bg-[#121212] border border-white/5 rounded-xl overflow-hidden">
      {/* Header */}
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 p-4 hover:bg-white/[0.02] transition-colors text-left"
      >
        <div
          className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ backgroundColor: config.color + "20" }}
        >
          <Icon className="w-4.5 h-4.5" style={{ color: config.color }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-white">{source.label}</div>
          <div className="text-[10px] text-[#71717A] mt-0.5">
            {source.trade_count != null && `${source.trade_count} сделок`}
            {source.count != null && `${source.count} операций`}
            {source.order_count != null && ` | ${source.order_count} заказов`}
            {source.guarantor_count != null && source.guarantor_count > 0 && ` | ${source.guarantor_count} гарант`}
            {source.volume_usdt != null && source.volume_usdt > 0 && ` | объём ${source.volume_usdt.toLocaleString()} USDT`}
          </div>
        </div>
        <div className="text-right flex-shrink-0">
          <div className="text-lg font-bold" style={{ color: config.color }}>
            +{source.total_usdt?.toFixed(4) || "0"} <span className="text-xs font-normal text-[#71717A]">USDT</span>
          </div>
          {source.total_rub != null && source.total_rub > 0 && (
            <div className="text-[10px] text-[#52525B]">{source.total_rub.toLocaleString()} RUB</div>
          )}
        </div>
        {(hasDetails || hasBreakdown) && (
          <div className="ml-1 text-[#52525B]">
            {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </div>
        )}
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="border-t border-white/5 px-4 pb-4">
          {/* Breakdown */}
          {hasBreakdown && (
            <div className="mt-3 space-y-1.5">
              <div className="text-[10px] uppercase tracking-wider text-[#52525B] font-semibold mb-2">Детализация</div>
              {Object.entries(source.breakdown).map(([key, val]) => (
                <div key={key} className="flex items-center justify-between text-xs">
                  <span className="text-[#A1A1AA]">
                    {key === "platform_markup" ? "Наценка платформы" :
                     key === "merchant_commission" ? "Комиссия мерчантов" :
                     key === "shop_orders" ? "Заказы магазинов" :
                     key === "guarantor_deals" ? "Гарант-сделки" :
                     key}
                  </span>
                  <span className="text-white font-medium">{val?.toFixed(4)} USDT</span>
                </div>
              ))}
            </div>
          )}

          {/* Sub-counts */}
          {source.sub && (
            <div className="mt-3 flex gap-3">
              {Object.entries(source.sub).map(([key, val]) => (
                <div key={key} className="bg-white/5 rounded-lg px-3 py-1.5 text-[10px]">
                  <span className="text-[#71717A]">
                    {key === "exchange_trades" ? "Обменных" :
                     key === "merchant_trades" ? "Мерчантских" :
                     key}
                  </span>
                  <span className="ml-1.5 text-white font-semibold">{val}</span>
                </div>
              ))}
            </div>
          )}

          {/* Details table */}
          {hasDetails && (
            <div className="mt-3">
              <div className="text-[10px] uppercase tracking-wider text-[#52525B] font-semibold mb-2">
                {sourceKey === "qr_aggregator" ? "По провайдерам" :
                 sourceKey === "trader_commissions" ? "Топ трейдеры" :
                 sourceKey === "merchant_commissions" ? "Топ мерчанты" :
                 "Детали"}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-[#52525B] text-[10px]">
                      <th className="text-left py-1.5 pr-2 font-medium">Имя</th>
                      <th className="text-right py-1.5 px-2 font-medium">Сделок</th>
                      <th className="text-right py-1.5 px-2 font-medium">Объём</th>
                      <th className="text-right py-1.5 pl-2 font-medium">Доход</th>
                    </tr>
                  </thead>
                  <tbody>
                    {source.details.map((d, i) => (
                      <tr key={i} className="border-t border-white/[0.03]">
                        <td className="py-1.5 pr-2 text-[#A1A1AA] truncate max-w-[140px]">
                          {d.name || d.login || d.provider_id || d.trader_id || d.merchant_id || "—"}
                        </td>
                        <td className="py-1.5 px-2 text-right text-[#71717A]">{d.trades}</td>
                        <td className="py-1.5 px-2 text-right text-[#71717A]">{d.volume_usdt?.toLocaleString()}</td>
                        <td className="py-1.5 pl-2 text-right text-white font-medium">
                          {(d.total_income || d.commission_usdt || 0)?.toFixed(4)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function DailyChart({ daily }) {
  if (!daily || daily.length === 0) return null;

  const maxIncome = Math.max(...daily.map(d => d.income), 0.01);

  return (
    <div className="bg-[#121212] border border-white/5 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <BarChart3 className="w-4 h-4 text-[#10B981]" />
        <span className="text-sm font-medium text-white">Доход по дням</span>
      </div>
      <div className="h-36 flex items-end gap-[3px]">
        {daily.map((day, i) => {
          const heightPct = Math.max(4, (day.income / maxIncome) * 100);
          return (
            <div
              key={i}
              className="flex-1 flex flex-col items-center gap-1 group relative"
            >
              {/* Tooltip */}
              <div className="absolute bottom-full mb-2 hidden group-hover:block z-10 pointer-events-none">
                <div className="bg-[#1a1a1a] border border-white/10 rounded-lg px-2.5 py-1.5 text-[10px] whitespace-nowrap shadow-xl">
                  <div className="text-white font-medium">{day.date}</div>
                  <div className="text-[#10B981]">+{day.income?.toFixed(4)} USDT</div>
                  <div className="text-[#71717A]">{day.trades} сделок | {day.volume?.toFixed(2)} USDT</div>
                </div>
              </div>
              <div
                className="w-full bg-gradient-to-t from-[#10B981]/40 to-[#10B981]/20 rounded-t hover:from-[#10B981]/60 hover:to-[#10B981]/30 transition-colors cursor-pointer"
                style={{ height: `${heightPct}%` }}
              />
              {daily.length <= 31 && (
                <span className="text-[7px] text-[#52525B] truncate w-full text-center">
                  {day.date?.slice(5)}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function AccountingPage() {
  const { token } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState("month");
  const [expanded, setExpanded] = useState({});

  useEffect(() => {
    fetchData();
  }, [period]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/admin/accounting?period=${period}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(response.data);
    } catch (error) {
      toast.error("Ошибка загрузки бухгалтерии");
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const toggleExpand = (key) => {
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  // Compute percentage of each source
  const getPercent = (val) => {
    if (!data || !data.total_income_usdt || data.total_income_usdt === 0) return 0;
    return ((val / data.total_income_usdt) * 100).toFixed(1);
  };

  return (
    <div className="space-y-4" data-testid="accounting-page">
      <PageHeader
        title="Бухгалтерия"
        subtitle="Доходы платформы по источникам"
        action={
          <div className="flex items-center gap-2">
            <div className="flex gap-1 bg-white/5 rounded-lg p-0.5">
              {PERIODS.map((p) => (
                <button
                  key={p.value}
                  onClick={() => setPeriod(p.value)}
                  className={`px-2.5 py-1 rounded-md text-[10px] font-medium transition-colors ${
                    period === p.value
                      ? "bg-[#10B981]/15 text-[#10B981]"
                      : "text-[#71717A] hover:text-white"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
            <button
              onClick={fetchData}
              className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center text-[#71717A] hover:text-white hover:bg-white/10 transition-colors"
              title="Обновить"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>
        }
      />

      {loading ? (
        <LoadingSpinner />
      ) : data ? (
        <>
          {/* Main metric: Total Income */}
          <div className="bg-gradient-to-br from-[#10B981]/20 to-[#10B981]/5 border border-[#10B981]/20 rounded-xl p-5">
            <div className="flex items-center gap-3 mb-1">
              <div className="w-10 h-10 rounded-xl bg-[#10B981]/20 flex items-center justify-center">
                <DollarSign className="w-5 h-5 text-[#10B981]" />
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wider text-[#10B981]/70 font-semibold">
                  Общий доход платформы
                </div>
                <div className="text-3xl font-bold text-white">
                  {data.total_income_usdt?.toFixed(4)}{" "}
                  <span className="text-lg text-[#10B981]">USDT</span>
                </div>
              </div>
            </div>
            <div className="flex gap-4 mt-3 text-xs text-[#71717A]">
              <div>
                <span className="text-[#52525B]">Объём: </span>
                <span className="text-white">{data.total_volume_usdt?.toLocaleString()} USDT</span>
              </div>
              <div>
                <span className="text-[#52525B]">Сделок: </span>
                <span className="text-white">{data.total_trades}</span>
              </div>
              <div>
                <span className="text-[#52525B]">Курс: </span>
                <span className="text-white">{data.base_rate} RUB/USDT</span>
              </div>
              <div>
                <span className="text-[#52525B]">Период: </span>
                <span className="text-white">
                  {data.date_from?.slice(0, 10)} — {data.date_to?.slice(0, 10)}
                </span>
              </div>
            </div>
          </div>

          {/* Income distribution bar */}
          {data.total_income_usdt > 0 && (
            <div className="bg-[#121212] border border-white/5 rounded-xl p-4">
              <div className="text-[10px] uppercase tracking-wider text-[#52525B] font-semibold mb-2">
                Распределение доходов
              </div>
              <div className="h-3 rounded-full overflow-hidden flex bg-white/5">
                {data.sources && Object.entries(data.sources).map(([key, src]) => {
                  const pct = getPercent(src.total_usdt);
                  if (pct <= 0) return null;
                  const cfg = SOURCE_CONFIG[key];
                  return (
                    <div
                      key={key}
                      className="h-full transition-all"
                      style={{
                        width: `${pct}%`,
                        backgroundColor: cfg?.color || "#71717A",
                        minWidth: pct > 0 ? "4px" : "0",
                      }}
                      title={`${src.label}: ${pct}%`}
                    />
                  );
                })}
              </div>
              <div className="flex flex-wrap gap-3 mt-2">
                {data.sources && Object.entries(data.sources).map(([key, src]) => {
                  const pct = getPercent(src.total_usdt);
                  const cfg = SOURCE_CONFIG[key];
                  return (
                    <div key={key} className="flex items-center gap-1.5 text-[10px]">
                      <div
                        className="w-2 h-2 rounded-full"
                        style={{ backgroundColor: cfg?.color || "#71717A" }}
                      />
                      <span className="text-[#71717A]">{src.label}</span>
                      <span className="text-white font-medium">{pct}%</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Income source cards */}
          <div className="space-y-2">
            {data.sources && Object.entries(data.sources).map(([key, source]) => (
              <IncomeSourceCard
                key={key}
                sourceKey={key}
                source={source}
                expanded={expanded[key]}
                onToggle={() => toggleExpand(key)}
              />
            ))}
          </div>

          {/* Daily chart */}
          <DailyChart daily={data.daily} />
        </>
      ) : (
        <div className="bg-[#121212] border border-white/5 rounded-xl p-12 text-center">
          <DollarSign className="w-10 h-10 text-[#3F3F46] mx-auto mb-3" />
          <p className="text-[#71717A] text-sm">Нет данных за выбранный период</p>
        </div>
      )}
    </div>
  );
}

export default AccountingPage;
