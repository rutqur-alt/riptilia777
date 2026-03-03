import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Power } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { LoadingSpinner, PageHeader } from "@/components/admin/SharedComponents";

export function SystemSettings() {
  const { token } = useAuth();
  const [settings, setSettings] = useState(null);
  const [maintenance, setMaintenance] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { fetchSettings(); }, []);

  const fetchSettings = async () => {
    try {
      const [sysRes, maintRes] = await Promise.all([
        axios.get(`${API}/admin/system-settings`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/maintenance-status`, { headers: { Authorization: `Bearer ${token}` } })
      ]);
      setSettings(sysRes.data);
      setMaintenance(maintRes.data);
    } catch (error) {
      console.error("Error loading settings:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (key, value) => {
    try {
      await axios.put(`${API}/admin/system-settings?${key}=${value}`, {}, { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Сохранено");
    } catch (error) {
      toast.error("Ошибка");
    }
  };

  const toggleMaintenance = async () => {
    try {
      await axios.post(`${API}/super-admin/maintenance`, 
        { enabled: !maintenance?.enabled, message: "Ведутся технические работы" },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success("Статус изменён");
      fetchSettings();
    } catch (error) {
      toast.error("Ошибка");
    }
  };

  return (
    <div className="space-y-4" data-testid="system-settings">
      <PageHeader title="Системные настройки" subtitle="Глобальные параметры" />

      {loading ? <LoadingSpinner /> : (
        <div className="space-y-4">
          {/* Maintenance Mode */}
          <div className="bg-[#121212] border border-white/5 rounded-xl p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-white text-sm flex items-center gap-2">
                  <Power className="w-4 h-4 text-[#F59E0B]" />
                  Режим обслуживания
                </div>
                <div className="text-[#52525B] text-[10px]">Блокирует доступ для обычных пользователей</div>
              </div>
              <Button
                onClick={toggleMaintenance}
                size="sm"
                className={`text-xs h-7 ${maintenance?.enabled ? 'bg-[#EF4444] hover:bg-[#DC2626]' : 'bg-[#52525B] hover:bg-[#71717A]'}`}
              >
                {maintenance?.enabled ? 'Выключить' : 'Включить'}
              </Button>
            </div>
          </div>

          {/* Other settings */}
          <div className="bg-[#121212] border border-white/5 rounded-xl p-4 space-y-4">
            <div className="flex items-center justify-between py-2 border-b border-white/5">
              <div>
                <div className="text-white text-sm">Таймаут сделки (мин)</div>
                <div className="text-[#52525B] text-[10px]">Время на оплату</div>
              </div>
              <Input
                type="number"
                defaultValue={settings?.trade_timeout_minutes || 30}
                className="w-20 h-7 bg-[#0A0A0A] border-white/10 text-white text-xs rounded text-center"
                onBlur={(e) => handleSave("trade_timeout_minutes", e.target.value)}
              />
            </div>

            <div className="flex items-center justify-between py-2 border-b border-white/5">
              <div>
                <div className="text-white text-sm">Таймаут диспута (мин)</div>
                <div className="text-[#52525B] text-[10px]">Время на открытие спора</div>
              </div>
              <Input
                type="number"
                defaultValue={settings?.dispute_timeout_minutes || 10}
                className="w-20 h-7 bg-[#0A0A0A] border-white/10 text-white text-xs rounded text-center"
                onBlur={(e) => handleSave("dispute_timeout_minutes", e.target.value)}
              />
            </div>

            <div className="flex items-center justify-between py-2">
              <div>
                <div className="text-white text-sm">Реферальная ставка (%)</div>
                <div className="text-[#52525B] text-[10px]">% от комиссии рефералу</div>
              </div>
              <Input
                type="number"
                step="0.1"
                defaultValue={settings?.referral_rate || 0.5}
                className="w-20 h-7 bg-[#0A0A0A] border-white/10 text-white text-xs rounded text-center"
                onBlur={(e) => handleSave("referral_rate", e.target.value)}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default SystemSettings;
