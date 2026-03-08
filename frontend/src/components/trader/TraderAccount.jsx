import { useState, useEffect } from "react";
import { toast } from "sonner";
import { useAuth, API } from "@/App";
import axios from "axios";
import { Calendar, Copy, Store } from "lucide-react";

export default function TraderAccount() {
  const { user, token } = useAuth();
  const [trader, setTrader] = useState(null);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    fetchTraderInfo();
  }, []);

  const fetchTraderInfo = async () => {
    try {
      const [traderRes, statsRes] = await Promise.all([
        axios.get(`${API}/traders/me`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/traders/stats`, { headers: { Authorization: `Bearer ${token}` } })
      ]);
      setTrader(traderRes.data);
      setStats(statsRes.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-[#7C3AED] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold text-white font-['Unbounded']">Аккаунт</h1>
        <p className="text-[#71717A]">Информация о вашем профиле</p>
      </div>

      {/* Profile Card */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl overflow-hidden">
        {/* Header with avatar */}
        <div className="bg-gradient-to-br from-[#7C3AED]/20 to-[#A855F7]/10 p-6 border-b border-white/5">
          <div className="flex items-center gap-4">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-[#7C3AED] to-[#A855F7] flex items-center justify-center text-white text-3xl font-bold">
              {(trader?.nickname || trader?.login || "U")[0].toUpperCase()}
            </div>
            <div>
              <h2 className="text-2xl font-bold text-white">@{trader?.nickname || trader?.login}</h2>
              <div className="flex items-center gap-2 text-[#71717A] text-sm mt-1">
                <Calendar className="w-4 h-4" />
                <span>Зарегистрирован: {trader?.created_at ? new Date(trader.created_at).toLocaleDateString("ru-RU", { day: 'numeric', month: 'long', year: 'numeric' }) : '\u2014'}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Info Grid */}
        <div className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-[#0A0A0A] rounded-xl p-4">
              <div className="text-xs text-[#71717A] mb-1">Никнейм</div>
              <div className="text-white font-medium">@{trader?.nickname || '\u2014'}</div>
            </div>
            <div className="bg-[#0A0A0A] rounded-xl p-4">
              <div className="text-xs text-[#71717A] mb-1">Логин</div>
              <div className="text-white font-medium">{trader?.login || '\u2014'}</div>
            </div>
            <div className="bg-[#0A0A0A] rounded-xl p-4">
              <div className="text-xs text-[#71717A] mb-1">Баланс USDT</div>
              <div className="text-[#10B981] font-bold font-['JetBrains_Mono']">{trader?.balance_usdt?.toFixed(2) || '0.00'}</div>
            </div>
          </div>

          {/* Referral */}
          {trader?.referral_code && (
            <div className="bg-[#0A0A0A] rounded-xl p-4">
              <div className="text-xs text-[#71717A] mb-1">Реферальный код</div>
              <div className="flex items-center gap-2">
                <code className="text-[#F59E0B] font-['JetBrains_Mono']">{trader.referral_code}</code>
                <button 
                  onClick={() => {
                    navigator.clipboard.writeText(trader.referral_code);
                    toast.success('Скопировано!');
                  }}
                  className="p-1 hover:bg-white/10 rounded"
                >
                  <Copy className="w-4 h-4 text-[#71717A]" />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Stats Card */}
      {stats && (
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Статистика P2P</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-4 bg-[#0A0A0A] rounded-xl">
              <div className="text-2xl font-bold text-[#10B981]">{stats.salesCount || 0}</div>
              <div className="text-xs text-[#71717A]">Продаж</div>
            </div>
            <div className="text-center p-4 bg-[#0A0A0A] rounded-xl">
              <div className="text-2xl font-bold text-[#3B82F6]">{stats.purchasesCount || 0}</div>
              <div className="text-xs text-[#71717A]">Покупок</div>
            </div>
            <div className="text-center p-4 bg-[#0A0A0A] rounded-xl">
              <div className="text-lg font-bold text-[#10B981] font-['JetBrains_Mono']">{(stats.salesVolume || 0).toFixed(2)}</div>
              <div className="text-xs text-[#71717A]">Оборот продаж</div>
            </div>
            <div className="text-center p-4 bg-[#0A0A0A] rounded-xl">
              <div className="text-lg font-bold text-[#3B82F6] font-['JetBrains_Mono']">{(stats.purchasesVolume || 0).toFixed(2)}</div>
              <div className="text-xs text-[#71717A]">Оборот покупок</div>
            </div>
          </div>
        </div>
      )}

      {/* Shop Info if has shop */}
      {trader?.has_shop && trader?.shop_settings && (
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Store className="w-5 h-5 text-[#A78BFA]" />
            Мой магазин
          </h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[#71717A]">Название</span>
              <span className="text-white">{trader.shop_settings.shop_name || '\u2014'}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[#71717A]">Комиссия платформы</span>
              <span className="text-[#F59E0B]">{trader.shop_settings.commission_rate || 5}%</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[#71717A]">Статус</span>
              <span className={`px-2 py-1 rounded text-xs ${trader.shop_settings.is_active ? 'bg-[#10B981]/10 text-[#10B981]' : 'bg-[#EF4444]/10 text-[#EF4444]'}`}>
                {trader.shop_settings.is_active ? 'Активен' : 'Неактивен'}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
