import React, { useState, useEffect } from "react";
import { toast } from "sonner";
import { Activity, Store, ArrowDownRight } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { LoadingSpinner, PageHeader } from "@/components/admin/SharedComponents";

export function FinancesOverview() {
  const { token } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState("7d");

  useEffect(() => { fetchData(); }, [period]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/super-admin/finances?period=${period}`, 
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setData(response.data);
    } catch (error) {
      toast.error("Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4" data-testid="finances-overview">
      <PageHeader 
        title="Финансы" 
        subtitle="Обзор доходов платформы"
        action={
          <div className="flex gap-1">
            {["1d", "7d", "30d", "90d"].map(p => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-2 py-1 rounded text-[10px] ${period === p ? "bg-[#10B981]/15 text-[#10B981]" : "text-[#71717A] hover:text-white"}`}
              >
                {p === "1d" ? "День" : p === "7d" ? "Неделя" : p === "30d" ? "Месяц" : "Квартал"}
              </button>
            ))}
          </div>
        }
      />

      {loading ? <LoadingSpinner /> : (
        <>
          <div className="grid md:grid-cols-3 gap-3">
            <div className="bg-[#121212] border border-white/5 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="w-4 h-4 text-[#10B981]" />
                <span className="text-xs text-[#71717A]">P2P Торговля</span>
              </div>
              <div className="text-xl font-bold text-white">{data?.p2p?.total_volume_usdt?.toLocaleString() || 0} USDT</div>
              <div className="text-[#52525B] text-[10px] mt-1">≈ {data?.p2p?.total_volume_rub?.toLocaleString() || 0} ₽</div>
              <div className="mt-2 pt-2 border-t border-white/5">
                <div className="text-[#10B981] text-sm">+{data?.p2p?.total_commission?.toFixed(4) || 0} USDT</div>
                <div className="text-[10px] text-[#52525B]">комиссия ({data?.p2p?.trade_count || 0} сделок)</div>
              </div>
            </div>

            <div className="bg-[#121212] border border-white/5 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <Store className="w-4 h-4 text-[#F59E0B]" />
                <span className="text-xs text-[#71717A]">Маркетплейс</span>
              </div>
              <div className="text-xl font-bold text-white">{data?.marketplace?.total_volume?.toLocaleString() || 0} USDT</div>
              <div className="mt-2 pt-2 border-t border-white/5">
                <div className="text-[#10B981] text-sm">+{data?.marketplace?.total_commission?.toFixed(4) || 0} USDT</div>
                <div className="text-[10px] text-[#52525B]">комиссия ({data?.marketplace?.order_count || 0} заказов)</div>
              </div>
            </div>

            <div className="bg-[#121212] border border-white/5 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <ArrowDownRight className="w-4 h-4 text-[#EF4444]" />
                <span className="text-xs text-[#71717A]">Ожидают вывода</span>
              </div>
              <div className="text-xl font-bold text-white">{data?.pending_withdrawals?.total_amount?.toLocaleString() || 0} USDT</div>
              <div className="text-[10px] text-[#52525B] mt-1">{data?.pending_withdrawals?.count || 0} заявок</div>
            </div>
          </div>

          {/* Daily chart placeholder */}
          <div className="bg-[#121212] border border-white/5 rounded-xl p-4">
            <h3 className="text-sm font-semibold text-white mb-3">Сделки по дням</h3>
            <div className="h-32 flex items-end gap-1">
              {data?.daily_trades?.map((day, i) => (
                <div key={i} className="flex-1 flex flex-col items-center gap-1">
                  <div 
                    className="w-full bg-[#10B981]/20 rounded-t"
                    style={{ height: `${Math.max(4, (day.trades / Math.max(...data.daily_trades.map(d => d.trades), 1)) * 100)}%` }}
                  />
                  <span className="text-[8px] text-[#52525B]">{day.date?.slice(5)}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default FinancesOverview;
