import { useState, useEffect } from "react";
import { useAuth, API } from "@/App";
import axios from "axios";

export default function TradingStats() {
  const { token } = useAuth();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API}/traders/me/stats`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setStats(response.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white font-['Unbounded']">Статистика торговли</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Всего сделок</div>
          <div className="text-2xl font-bold text-white">{stats?.total_trades || 0}</div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Завершённых</div>
          <div className="text-2xl font-bold text-[#10B981]">{stats?.completed_trades || 0}</div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Отменённых</div>
          <div className="text-2xl font-bold text-[#71717A]">{stats?.cancelled_trades || 0}</div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Диспутов</div>
          <div className="text-2xl font-bold text-[#EF4444]">{stats?.disputed_trades || 0}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Общая сумма сделок</div>
          <div className="text-xl font-bold text-white">{(stats?.total_volume_usdt || 0).toFixed(2)} USDT</div>
          <div className="text-sm text-[#71717A]">≈ {Math.round(stats?.total_volume_rub || 0).toLocaleString()} ₽</div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Средний курс</div>
          <div className="text-xl font-bold text-white">{Math.round(stats?.avg_rate || 0)} ₽</div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Среднее время сделки</div>
          <div className="text-xl font-bold text-white">{stats?.avg_time_minutes || 0} мин</div>
        </div>
      </div>
    </div>
  );
}
