// ReferralSettings - Admin page for referral program configuration
import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { 
  Users, Percent, DollarSign, TrendingUp, Save, 
  RefreshCw, Gift, Loader
} from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { PageHeader } from "@/components/admin/SharedComponents";

export function ReferralSettings() {
  const { token } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [settings, setSettings] = useState({
    enabled: true,
    min_withdrawal_usdt: 1.0,
    levels: [
      { level: 1, percent: 5 },
      { level: 2, percent: 3 },
      { level: 3, percent: 1 }
    ]
  });
  const [stats, setStats] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [settingsRes, statsRes] = await Promise.all([
        axios.get(`${API}/admin/referral/settings`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/admin/referral/stats`, { headers: { Authorization: `Bearer ${token}` } })
      ]);
      setSettings(settingsRes.data);
      setStats(statsRes.data);
    } catch (error) {
      console.error("Error loading referral settings:", error);
      toast.error("Ошибка загрузки настроек");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/admin/referral/settings`, settings, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Настройки сохранены");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка сохранения");
    } finally {
      setSaving(false);
    }
  };

  const updateLevel = (index, percent) => {
    const newLevels = [...settings.levels];
    newLevels[index] = { ...newLevels[index], percent: parseFloat(percent) || 0 };
    setSettings({ ...settings, levels: newLevels });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader className="w-8 h-8 animate-spin text-[#7C3AED]" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="referral-settings">
      <PageHeader 
        title="Реферальная программа" 
        subtitle="Настройка процентов и статистика"
      />

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard 
          icon={Users} 
          label="Всего рефералов" 
          value={stats?.total_referrals || 0}
          color="#7C3AED"
        />
        <StatCard 
          icon={DollarSign} 
          label="Выплачено бонусов" 
          value={`${(stats?.total_paid || 0).toFixed(2)} USDT`}
          color="#10B981"
        />
        <StatCard 
          icon={Gift} 
          label="Выведено" 
          value={`${(stats?.total_withdrawn || 0).toFixed(2)} USDT`}
          color="#F59E0B"
        />
        <StatCard 
          icon={TrendingUp} 
          label="1-й уровень" 
          value={stats?.level1_count || 0}
          color="#3B82F6"
        />
      </div>

      {/* Settings */}
      <div className="bg-[#121212] border border-white/5 rounded-xl p-6">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-white font-semibold text-lg flex items-center gap-2">
            <Percent className="w-5 h-5 text-[#7C3AED]" />
            Настройки процентов
          </h3>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={fetchData}
              className="text-[#71717A] hover:text-white"
            >
              <RefreshCw className="w-4 h-4" />
            </Button>
            <Button
              onClick={handleSave}
              disabled={saving}
              className="bg-[#10B981] hover:bg-[#059669] text-white"
             title="Сохранить изменения">
              {saving ? <Loader className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
              Сохранить
            </Button>
          </div>
        </div>

        {/* Enable/Disable */}
        <div className="flex items-center justify-between p-4 bg-white/5 rounded-xl mb-6">
          <div>
            <div className="text-white font-medium">Реферальная программа</div>
            <div className="text-[#71717A] text-sm">Включить/выключить начисление бонусов</div>
          </div>
          <button
            onClick={() => setSettings({ ...settings, enabled: !settings.enabled })}
            className={`w-14 h-7 rounded-full transition-colors relative ${
              settings.enabled ? "bg-[#10B981]" : "bg-[#52525B]"
            }`}
          >
            <div className={`w-5 h-5 rounded-full bg-white absolute top-1 transition-transform ${
              settings.enabled ? "right-1" : "left-1"
            }`} />
          </button>
        </div>

        {/* Levels */}
        <div className="space-y-4">
          <div className="text-[#71717A] text-sm mb-2">
            Проценты начисляются от комиссии трейдера за каждую завершённую сделку
          </div>
          
          {settings.levels.map((level, idx) => (
            <div key={level.level} className="flex items-center gap-4 p-4 bg-white/5 rounded-xl">
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                idx === 0 ? "bg-[#10B981]/20 text-[#10B981]" :
                idx === 1 ? "bg-[#F59E0B]/20 text-[#F59E0B]" :
                "bg-[#71717A]/20 text-[#71717A]"
              }`}>
                {level.level}
              </div>
              <div className="flex-1">
                <div className="text-white font-medium">
                  {idx === 0 ? "Прямой реферал" : idx === 1 ? "Реферал 2-го уровня" : "Реферал 3-го уровня"}
                </div>
                <div className="text-[#71717A] text-xs">
                  {idx === 0 ? "Пользователь, которого вы пригласили напрямую" :
                   idx === 1 ? "Реферал вашего реферала" :
                   "Третий уровень реферальной цепочки"}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  min="0"
                  max="100"
                  step="0.1"
                  value={level.percent}
                  onChange={(e) => updateLevel(idx, e.target.value)}
                  className="w-20 bg-[#0A0A0A] border-white/10 text-white text-center"
                />
                <span className="text-[#71717A]">%</span>
              </div>
            </div>
          ))}
        </div>

        {/* Min Withdrawal */}
        <div className="mt-6 p-4 bg-white/5 rounded-xl">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-white font-medium">Минимальная сумма вывода</div>
              <div className="text-[#71717A] text-sm">Минимум USDT для перевода на основной баланс</div>
            </div>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                min="0"
                step="0.1"
                value={settings.min_withdrawal_usdt}
                onChange={(e) => setSettings({ ...settings, min_withdrawal_usdt: parseFloat(e.target.value) || 0 })}
                className="w-24 bg-[#0A0A0A] border-white/10 text-white text-center"
              />
              <span className="text-[#71717A]">USDT</span>
            </div>
          </div>
        </div>
      </div>

      {/* Level Stats */}
      <div className="bg-[#121212] border border-white/5 rounded-xl p-6">
        <h3 className="text-white font-semibold mb-4">Статистика по уровням</h3>
        <div className="grid grid-cols-3 gap-4">
          <div className="p-4 bg-[#10B981]/10 rounded-xl text-center">
            <div className="text-2xl font-bold text-[#10B981]">{stats?.level1_count || 0}</div>
            <div className="text-[#71717A] text-sm">1-й уровень</div>
          </div>
          <div className="p-4 bg-[#F59E0B]/10 rounded-xl text-center">
            <div className="text-2xl font-bold text-[#F59E0B]">{stats?.level2_count || 0}</div>
            <div className="text-[#71717A] text-sm">2-й уровень</div>
          </div>
          <div className="p-4 bg-[#71717A]/10 rounded-xl text-center">
            <div className="text-2xl font-bold text-[#71717A]">{stats?.level3_count || 0}</div>
            <div className="text-[#71717A] text-sm">3-й уровень</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, color }) {
  return (
    <div className="bg-[#121212] border border-white/5 rounded-xl p-4">
      <div className="flex items-center gap-3">
        <div 
          className="w-10 h-10 rounded-lg flex items-center justify-center"
          style={{ backgroundColor: `${color}20` }}
        >
          <Icon className="w-5 h-5" style={{ color }} />
        </div>
        <div>
          <div className="text-[#71717A] text-xs">{label}</div>
          <div className="text-white font-semibold">{value}</div>
        </div>
      </div>
    </div>
  );
}

export default ReferralSettings;
