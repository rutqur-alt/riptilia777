import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Briefcase, Settings as SettingsIcon, Lock, Unlock } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { Badge, LoadingSpinner, EmptyState, PageHeader } from "@/components/admin/SharedComponents";

export function MerchantsList() {
  const { token } = useAuth();
  const [merchants, setMerchants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [settingsModal, setSettingsModal] = useState(null);
  const [commissionData, setCommissionData] = useState({ rate: "", useCustom: false });

  useEffect(() => { fetchMerchants(); }, []);

  const fetchMerchants = async () => {
    try {
      const response = await axios.get(`${API}/admin/merchants`, { headers: { Authorization: `Bearer ${token}` } });
      setMerchants(response.data || []);
    } catch (error) {
      toast.error("Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  };

  const handleBlock = async (merchantId, status) => {
    const newStatus = status === "blocked" ? "active" : "blocked";
    try {
      await axios.post(`${API}/admin/merchants/${merchantId}/status?status=${newStatus}`, {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(newStatus === "blocked" ? "Заблокирован" : "Разблокирован");
      fetchMerchants();
    } catch (error) {
      toast.error("Ошибка");
    }
  };

  const openSettings = async (merchant) => {
    try {
      const response = await axios.get(`${API}/admin/merchants/${merchant.id}/settings`, 
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setCommissionData({
        rate: response.data.custom_commission_rate || response.data.global_commission_rate,
        useCustom: response.data.use_custom_commission,
        globalRate: response.data.global_commission_rate
      });
      setSettingsModal(merchant);
    } catch (error) {
      toast.error("Ошибка загрузки настроек");
    }
  };

  const saveCommission = async () => {
    try {
      await axios.put(`${API}/admin/merchants/${settingsModal.id}/commission`, {
        commission_rate: parseFloat(commissionData.rate),
        use_custom: commissionData.useCustom
      }, { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Комиссия сохранена");
      setSettingsModal(null);
      fetchMerchants();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка");
    }
  };

  return (
    <div className="space-y-4" data-testid="merchants-list">
      <PageHeader title="Мерчанты" subtitle="API интеграции" />

      {/* Settings Modal */}
      {settingsModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-[#1A1A1A] border border-white/10 rounded-xl p-6 w-full max-w-md">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <SettingsIcon className="w-5 h-5 text-[#7C3AED]" />
              Настройки: {settingsModal.merchant_name}
            </h3>
            
            <div className="space-y-4">
              <div>
                <label className="text-sm text-[#A1A1AA] block mb-2">Комиссия (%)</label>
                <div className="flex items-center gap-3">
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="100"
                    value={commissionData.rate}
                    onChange={(e) => setCommissionData({ ...commissionData, rate: e.target.value })}
                    className="flex-1 bg-[#0A0A0A] border border-white/10 rounded-lg px-3 py-2 text-white"
                    disabled={!commissionData.useCustom}
                  />
                  <span className="text-[#71717A] text-sm">%</span>
                </div>
                <p className="text-xs text-[#52525B] mt-1">
                  Глобальная: {commissionData.globalRate}%
                </p>
              </div>
              
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={commissionData.useCustom}
                  onChange={(e) => setCommissionData({ 
                    ...commissionData, 
                    useCustom: e.target.checked,
                    rate: e.target.checked ? commissionData.rate : commissionData.globalRate
                  })}
                  className="w-4 h-4 rounded border-white/20 bg-[#0A0A0A] text-[#7C3AED]"
                />
                <span className="text-sm text-white">Использовать индивидуальную комиссию</span>
              </label>
            </div>
            
            <div className="flex gap-3 mt-6">
              <Button onClick={saveCommission} className="flex-1 bg-[#7C3AED] hover:bg-[#6D28D9]">
                Сохранить
              </Button>
              <Button onClick={() => setSettingsModal(null)} variant="outline" className="border-white/10 text-white">
                Отмена
              </Button>
            </div>
          </div>
        </div>
      )}

      {loading ? <LoadingSpinner /> : merchants.length === 0 ? (
        <EmptyState icon={Briefcase} text="Нет мерчантов" />
      ) : (
        <div className="space-y-2">
          {merchants.map(m => (
            <div key={m.id} className="bg-[#121212] border border-white/5 rounded-xl p-3 flex items-center justify-between">
              <div>
                <div className="text-white text-sm font-medium">{m.merchant_name}</div>
                <div className="text-[#52525B] text-[10px]">@{m.nickname || m.login} • {m.merchant_type}</div>
              </div>
              <div className="flex items-center gap-3">
                <div className="text-right">
                  <div className="text-[#10B981] font-mono text-xs">{(m.balance_usdt || 0).toFixed(2)} USDT</div>
                  <div className="text-[#F59E0B] text-[10px]">
                    {m.use_custom_commission ? `${m.custom_commission_rate}% (индив.)` : `${m.commission_rate || 1}%`}
                  </div>
                </div>
                <Badge color={m.status === "blocked" ? "red" : m.status === "active" || m.status === "approved" ? "green" : "yellow"}>
                  {m.status}
                </Badge>
                <Button 
                  size="sm" 
                  variant="ghost" 
                  onClick={() => openSettings(m)}
                  className="h-7 w-7 p-0 text-[#71717A] hover:text-[#7C3AED]"
                  title="Настройки"
                >
                  <SettingsIcon className="w-3.5 h-3.5" />
                </Button>
                <Button 
                  size="sm" 
                  variant="ghost" 
                  onClick={() => handleBlock(m.id, m.status)}
                  className={`h-7 w-7 p-0 ${m.status === "blocked" ? "text-[#10B981]" : "text-[#EF4444]"}`}
                >
                  {m.status === "blocked" ? <Unlock className="w-3.5 h-3.5" /> : <Lock className="w-3.5 h-3.5" />}
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default MerchantsList;
