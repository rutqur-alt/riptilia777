import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { useAuth, API } from "@/App";
import axios from "axios";

export default function TradingSettings() {
  const { token } = useAuth();
  const [displayName, setDisplayName] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const response = await axios.get(`${API}/traders/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setDisplayName(response.data.display_name || response.data.nickname || "");
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!displayName.trim()) {
      toast.error("Введите отображаемое имя");
      return;
    }
    setSaving(true);
    try {
      await axios.put(`${API}/traders/me`, {
        display_name: displayName.trim()
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Настройки сохранены");
    } catch (error) {
      toast.error("Ошибка сохранения");
    } finally {
      setSaving(false);
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
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-white font-['Unbounded']">Настройки торговли</h1>

      <div className="bg-[#121212] border border-white/5 rounded-2xl p-6 space-y-6">
        <div>
          <h3 className="text-white font-semibold mb-4">Отображаемое имя</h3>
          <p className="text-sm text-[#71717A] mb-4">
            Это имя будет отображаться в стакане объявлений вместо вашего логина
          </p>
          <Input
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Введите отображаемое имя"
            className="bg-white/5 border-white/10 text-white h-12 rounded-xl max-w-md"
            maxLength={30}
          />
          <p className="text-xs text-[#71717A] mt-2">Максимум 30 символов</p>
        </div>

        <Button onClick={handleSave} disabled={saving} className="bg-[#7C3AED] hover:bg-[#6D28D9] h-11 rounded-xl px-8" data-testid="save-trading-settings-btn">
          {saving ? <div className="spinner" /> : "Сохранить"}
        </Button>
      </div>
    </div>
  );
}
