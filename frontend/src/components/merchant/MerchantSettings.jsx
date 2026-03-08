import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { useAuth, API } from "@/App";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Eye, EyeOff, Loader, Lock } from "lucide-react";

export default function MerchantSettings() {
  const { token, user } = useAuth();
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [showOld, setShowOld] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [saving, setSaving] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

  const handleChangePassword = async () => {
    if (!oldPassword || !newPassword) {
      toast.error("Заполните все поля");
      return;
    }
    if (newPassword.length < 6) {
      toast.error("Минимум 6 символов");
      return;
    }
    setSaving(true);
    try {
      await axios.post(`${API}/merchants/change-password`, {
        old_password: oldPassword,
        new_password: newPassword
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Пароль изменён");
      setOldPassword("");
      setNewPassword("");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка смены пароля");
    } finally {
      setSaving(false);
    }
  };

  const handleRegenerateApiKey = async () => {
    setRegenerating(true);
    try {
      const res = await axios.post(`${API}/merchants/regenerate-api-key`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("API ключ обновлён");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка");
    } finally {
      setRegenerating(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Настройки</h1>

      <div className="bg-[#121212] border border-white/5 rounded-2xl p-6 space-y-4">
        <h3 className="text-lg font-medium text-white flex items-center gap-2"><Lock className="w-5 h-5" /> Смена пароля</h3>
        <div className="space-y-2">
          <Label className="text-[#A1A1AA]">Текущий пароль</Label>
          <div className="relative">
            <Input
              type={showOld ? "text" : "password"}
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl pr-10"
            />
            <button onClick={() => setShowOld(!showOld)} className="absolute right-3 top-3 text-[#71717A]">
              {showOld ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
            </button>
          </div>
        </div>
        <div className="space-y-2">
          <Label className="text-[#A1A1AA]">Новый пароль</Label>
          <div className="relative">
            <Input
              type={showNew ? "text" : "password"}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl pr-10"
            />
            <button onClick={() => setShowNew(!showNew)} className="absolute right-3 top-3 text-[#71717A]">
              {showNew ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
            </button>
          </div>
        </div>
        <Button onClick={handleChangePassword} disabled={saving} className="bg-[#7C3AED] hover:bg-[#6D28D9] h-12 rounded-xl">
          {saving ? <Loader className="w-4 h-4 animate-spin" /> : "Сменить пароль"}
        </Button>
      </div>
    </div>
  );
}
