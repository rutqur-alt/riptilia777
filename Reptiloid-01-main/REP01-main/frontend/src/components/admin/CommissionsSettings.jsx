import React, { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { useAuth, API } from "@/App";
import axios from "axios";
import { LoadingSpinner, PageHeader } from "@/components/admin/SharedComponents";

export function CommissionsSettings() {
  const { token } = useAuth();
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { fetchSettings(); }, []);

  const fetchSettings = async () => {
    try {
      const response = await axios.get(`${API}/super-admin/commissions/all`, { headers: { Authorization: `Bearer ${token}` } });
      setSettings(response.data);
    } catch (error) {
      toast.error("Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (key, value) => {
    try {
      await axios.put(`${API}/super-admin/commissions/update`, { [key]: parseFloat(value) }, { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Сохранено");
      fetchSettings();
    } catch (error) {
      toast.error("Ошибка");
    }
  };

  const commissionFields = [
    { key: "trader_commission", label: "P2P комиссия", desc: "% с каждой P2P сделки" },
    { key: "casino_commission", label: "Казино мерчанты", desc: "% для типа 'casino'" },
    { key: "shop_commission", label: "Магазины мерчанты", desc: "% для типа 'shop'" },
    { key: "stream_commission", label: "Стримеры мерчанты", desc: "% для типа 'stream'" },
    { key: "other_commission", label: "Прочие мерчанты", desc: "% для типа 'other'" },
    { key: "guarantor_commission_percent", label: "Гарант-сервис", desc: "% с гарант-сделок" },
  ];

  return (
    <div className="space-y-4" data-testid="commissions-settings">
      <PageHeader title="Комиссии" subtitle="Настройка ставок комиссий" />

      {loading ? <LoadingSpinner /> : (
        <div className="bg-[#121212] border border-white/5 rounded-xl p-4 space-y-4">
          {commissionFields.map(field => (
            <div key={field.key} className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
              <div>
                <div className="text-white text-sm">{field.label}</div>
                <div className="text-[#52525B] text-[10px]">{field.desc}</div>
              </div>
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  step="0.1"
                  defaultValue={settings?.[field.key] || 0}
                  className="w-20 h-7 bg-[#0A0A0A] border-white/10 text-white text-xs rounded text-center"
                  onBlur={(e) => handleSave(field.key, e.target.value)}
                />
                <span className="text-[#71717A] text-xs">%</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default CommissionsSettings;
