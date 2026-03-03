import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Briefcase, Settings as SettingsIcon, Lock, Unlock, Search, XCircle } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { Badge, LoadingSpinner, EmptyState, PageHeader } from "@/components/admin/SharedComponents";

export function MerchantsList() {
  const { token } = useAuth();
  const [merchants, setMerchants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [settingsModal, setSettingsModal] = useState(null);
  const [commissionData, setCommissionData] = useState({ rate: "", feeModel: "merchant_pays" });

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
      const response = await axios.get(`${API}/admin/merchants/${merchant.id}/fee-settings`, 
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setCommissionData({
        rate: response.data.commission_rate || 3.0,
        feeModel: "merchant_pays",
        withdrawalCommission: response.data.withdrawal_commission || 3.0
      });
      setSettingsModal(merchant);
    } catch (error) {
      toast.error("Ошибка загрузки настроек");
    }
  };

  const saveCommission = async () => {
    try {
      await axios.put(`${API}/admin/merchants/${settingsModal.id}/fee-settings`, {
        fee_model: commissionData.feeModel,
        commission_rate: parseFloat(commissionData.rate),
        withdrawal_commission: parseFloat(commissionData.withdrawalCommission || 3.0)
      }, { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Настройки комиссии сохранены");
      setSettingsModal(null);
      fetchMerchants();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка");
    }
  };

  // Filter merchants by search
  const filtered = merchants.filter(m => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      m.id?.toLowerCase().includes(query) ||
      m.merchant_name?.toLowerCase().includes(query) ||
      m.nickname?.toLowerCase().includes(query) ||
      m.login?.toLowerCase().includes(query)
    );
  });

  return (
    <div className="space-y-4" data-testid="merchants-list">
      <PageHeader title="Мерчанты" subtitle="API интеграции" />

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#52525B]" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Поиск по ID, названию, логину..."
          className="w-full bg-[#121212] border border-white/10 rounded-xl pl-10 pr-10 py-2 text-sm text-white placeholder-[#52525B] focus:outline-none focus:border-[#7C3AED]"
          data-testid="search-merchants"
        />
        {searchQuery && (
          <button onClick={() => setSearchQuery("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#52525B] hover:text-white">
            <XCircle className="w-4 h-4" />
          </button>
        )}
      </div>

      {searchQuery && (
        <div className="text-xs text-[#71717A]">
          Найдено: {filtered.length} из {merchants.length}
        </div>
      )}

      {/* Settings Modal */}
      {settingsModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-[#1A1A1A] border border-white/10 rounded-xl p-6 w-full max-w-md">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <SettingsIcon className="w-5 h-5 text-[#7C3AED]" />
              Настройки: {settingsModal.merchant_name}
            </h3>
            
            <div className="space-y-4">
              {/* Commission Rate */}
              <div>
                <label className="text-sm text-[#A1A1AA] block mb-2">Комиссия на платежи (%)</label>
                <p className="text-xs text-[#52525B] mb-2">Вычитается из каждого входящего платежа мерчанта</p>
                <div className="flex items-center gap-3">
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="100"
                    value={commissionData.rate}
                    onChange={(e) => setCommissionData({ ...commissionData, rate: e.target.value })}
                    className="flex-1 bg-[#0A0A0A] border border-white/10 rounded-lg px-3 py-2 text-white"
                  />
                  <span className="text-[#71717A] text-sm">%</span>
                </div>
              </div>

              {/* Withdrawal Commission */}
              <div>
                <label className="text-sm text-[#A1A1AA] block mb-2">Комиссия на выплаты (%)</label>
                <p className="text-xs text-[#52525B] mb-2">Вычитается при продаже USDT через раздел выплат</p>
                <div className="flex items-center gap-3">
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="100"
                    value={commissionData.withdrawalCommission}
                    onChange={(e) => setCommissionData({ ...commissionData, withdrawalCommission: e.target.value })}
                    className="flex-1 bg-[#0A0A0A] border border-white/10 rounded-lg px-3 py-2 text-white"
                  />
                  <span className="text-[#71717A] text-sm">%</span>
                </div>
              </div>
            </div>
            
            <div className="flex gap-3 mt-6">
              <Button onClick={saveCommission} className="flex-1 bg-[#7C3AED] hover:bg-[#6D28D9]" title="Сохранить изменения">
                Сохранить
              </Button>
              <Button onClick={() => setSettingsModal(null)} variant="outline" className="border-white/10 text-white">
                Отмена
              </Button>
            </div>
          </div>
        </div>
      )}

      {loading ? <LoadingSpinner /> : filtered.length === 0 ? (
        <EmptyState icon={Briefcase} text={searchQuery ? "Ничего не найдено" : "Нет мерчантов"} />
      ) : (
        <div className="space-y-2">
          {filtered.map(m => (
            <div key={m.id} className="bg-[#121212] border border-white/5 rounded-xl p-3 flex items-center justify-between">
              <div>
                <div className="text-white text-sm font-medium">{m.merchant_name}</div>
                <div className="text-[#52525B] text-[10px]">@{m.nickname || m.login}</div>
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
