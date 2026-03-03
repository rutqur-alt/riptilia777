import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { TrendingUp, FileText, Loader } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { LoadingSpinner, PageHeader } from "@/components/admin/SharedComponents";

export function PayoutRulesSettings() {
  const { token } = useAuth();
  const [rules, setRules] = useState("");
  const [exchangeRate, setExchangeRate] = useState(96.5);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => { fetchSettings(); }, []);

  const fetchSettings = async () => {
    try {
      const res = await axios.get(`${API}/admin/payout-settings`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setRules(res.data.rules || "");
      setExchangeRate(res.data.exchange_rate || 96.5);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const saveSettings = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/admin/payout-settings`, 
        { rules, exchange_rate: exchangeRate },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success("Настройки сохранены");
    } catch (e) {
      toast.error("Ошибка сохранения");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-6" data-testid="payout-rules-settings">
      <PageHeader title="Правила выплат" subtitle="Настройки для покупки криптовалюты" />
      
      {/* Exchange Rate */}
      <div className="bg-[#121212] border border-white/5 rounded-xl p-6">
        <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-[#10B981]" />
          Курс биржи
        </h3>
        <div className="flex items-center gap-4">
          <div className="flex-1 max-w-xs">
            <label className="text-[#71717A] text-xs mb-1 block">Курс RUB/USDT</label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                step="0.01"
                value={exchangeRate}
                onChange={(e) => setExchangeRate(parseFloat(e.target.value) || 0)}
                className="flex-1 bg-[#0A0A0A] border border-white/10 rounded-lg px-3 py-2 text-white font-mono"
              />
              <span className="text-[#71717A]">₽</span>
            </div>
            <p className="text-[#52525B] text-xs mt-1">
              1 USDT = {exchangeRate} ₽
            </p>
          </div>
        </div>
      </div>

      {/* Rules Text */}
      <div className="bg-[#121212] border border-white/5 rounded-xl p-6">
        <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
          <FileText className="w-5 h-5 text-[#3B82F6]" />
          Правила покупки
        </h3>
        <p className="text-[#71717A] text-sm mb-4">
          Этот текст будет показан покупателю перед совершением покупки. Он должен принять правила для продолжения.
        </p>
        <textarea
          value={rules}
          onChange={(e) => setRules(e.target.value)}
          placeholder="Введите правила покупки криптовалюты..."
          rows={12}
          className="w-full bg-[#0A0A0A] border border-white/10 rounded-lg px-4 py-3 text-white text-sm resize-none"
        />
        <p className="text-[#52525B] text-xs mt-2">
          Поддерживается форматирование: **жирный**, *курсив*, - списки
        </p>
      </div>

      {/* Preview */}
      <div className="bg-[#121212] border border-white/5 rounded-xl p-6">
        <h3 className="text-white font-semibold mb-4">Предпросмотр</h3>
        <div className="bg-[#0A0A0A] border border-[#3B82F6]/20 rounded-lg p-4 max-h-64 overflow-y-auto">
          <pre className="text-white text-sm whitespace-pre-wrap font-sans">
            {rules || "Правила не заданы"}
          </pre>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end">
        <Button 
          onClick={saveSettings} 
          disabled={saving}
          className="bg-[#10B981] hover:bg-[#059669] text-white px-8"
        >
          {saving ? <Loader className="w-4 h-4 animate-spin mr-2" /> : null}
          Сохранить настройки
        </Button>
      </div>
    </div>
  );
}

export default PayoutRulesSettings;
