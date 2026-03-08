import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { useAuth, API } from "@/App";
import axios from "axios";
import { Key, Lock, Eye, EyeOff, AlertTriangle } from "lucide-react";

export default function TraderSettings() {
  const { token, user } = useAuth();
  const [trader, setTrader] = useState(null);
  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [show2FAForm, setShow2FAForm] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [saving, setSaving] = useState(false);
  const [twoFAEnabled, setTwoFAEnabled] = useState(false);

  useEffect(() => {
    fetchTrader();
  }, []);

  const fetchTrader = async () => {
    try {
      const response = await axios.get(`${API}/traders/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTrader(response.data);
      setTwoFAEnabled(response.data.two_fa_enabled || false);
    } catch (error) {
      console.error(error);
    }
  };

  const handleChangePassword = async () => {
    if (newPassword !== confirmPassword) {
      toast.error("Пароли не совпадают");
      return;
    }
    if (newPassword.length < 6) {
      toast.error("Пароль должен быть не менее 6 символов");
      return;
    }
    
    setSaving(true);
    try {
      await axios.post(`${API}/traders/change-password`, {
        current_password: currentPassword,
        new_password: newPassword
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Пароль успешно изменён");
      setShowPasswordForm(false);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка смены пароля");
    } finally {
      setSaving(false);
    }
  };

  const handleToggle2FA = async () => {
    setSaving(true);
    try {
      await axios.post(`${API}/traders/toggle-2fa`, {
        enabled: !twoFAEnabled
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTwoFAEnabled(!twoFAEnabled);
      toast.success(twoFAEnabled ? "2FA отключена" : "2FA включена");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-white font-['Unbounded']">Настройки аккаунта</h1>

      {/* Смена пароля */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-[#7C3AED]/20 flex items-center justify-center">
            <Key className="w-5 h-5 text-[#7C3AED]" />
          </div>
          <div>
            <h3 className="text-white font-semibold">Смена пароля</h3>
            <p className="text-sm text-[#71717A]">Изменить пароль для входа в аккаунт</p>
          </div>
        </div>
        
        {!showPasswordForm ? (
          <Button 
            onClick={() => setShowPasswordForm(true)}
            variant="outline"
            className="border-white/10 text-white hover:bg-white/5"
           title="Изменить пароль аккаунта">
            Изменить пароль
          </Button>
        ) : (
          <div className="space-y-4">
            <div>
              <Label className="text-[#71717A] text-sm">Текущий пароль</Label>
              <div className="relative mt-1">
                <Input
                  type={showCurrentPassword ? "text" : "password"}
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="bg-[#0A0A0A] border-white/10 text-white pr-10"
                  placeholder="Введите текущий пароль"
                />
                <button
                  type="button"
                  onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#71717A] hover:text-white"
                >
                  {showCurrentPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            
            <div>
              <Label className="text-[#71717A] text-sm">Новый пароль</Label>
              <div className="relative mt-1">
                <Input
                  type={showNewPassword ? "text" : "password"}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="bg-[#0A0A0A] border-white/10 text-white pr-10"
                  placeholder="Введите новый пароль"
                />
                <button
                  type="button"
                  onClick={() => setShowNewPassword(!showNewPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#71717A] hover:text-white"
                >
                  {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            
            <div>
              <Label className="text-[#71717A] text-sm">Подтвердите пароль</Label>
              <Input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="bg-[#0A0A0A] border-white/10 text-white mt-1"
                placeholder="Повторите новый пароль"
              />
            </div>
            
            <div className="flex gap-3">
              <Button 
                onClick={handleChangePassword}
                disabled={saving || !currentPassword || !newPassword || !confirmPassword}
                className="bg-[#7C3AED] hover:bg-[#6D28D9]"
              >
                {saving ? <div className="spinner" /> : "Сохранить"}
              </Button>
              <Button 
                onClick={() => {
                  setShowPasswordForm(false);
                  setCurrentPassword("");
                  setNewPassword("");
                  setConfirmPassword("");
                }}
                variant="outline"
                className="border-white/10 text-white hover:bg-white/5"
              >
                Отмена
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* 2FA */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${twoFAEnabled ? "bg-[#10B981]/20" : "bg-[#F59E0B]/20"}`}>
              <Lock className={`w-5 h-5 ${twoFAEnabled ? "text-[#10B981]" : "text-[#F59E0B]"}`} />
            </div>
            <div>
              <h3 className="text-white font-semibold">Двухфакторная аутентификация</h3>
              <p className="text-sm text-[#71717A]">
                {twoFAEnabled ? "2FA включена — аккаунт защищён" : "Рекомендуем включить для безопасности"}
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <span className={`px-3 py-1 rounded-full text-xs font-medium ${
              twoFAEnabled 
                ? "bg-[#10B981]/20 text-[#10B981]" 
                : "bg-[#F59E0B]/20 text-[#F59E0B]"
            }`}>
              {twoFAEnabled ? "Включено" : "Отключено"}
            </span>
            <Button 
              onClick={handleToggle2FA}
              disabled={saving}
              variant={twoFAEnabled ? "outline" : "default"}
              className={twoFAEnabled 
                ? "border-[#EF4444]/50 text-[#EF4444] hover:bg-[#EF4444]/10" 
                : "bg-[#10B981] hover:bg-[#059669]"
              }
            >
              {saving ? <div className="spinner" /> : (twoFAEnabled ? "Отключить" : "Включить")}
            </Button>
          </div>
        </div>
        
        {!twoFAEnabled && (
          <div className="mt-4 p-4 bg-[#F59E0B]/10 border border-[#F59E0B]/20 rounded-xl">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-[#F59E0B] flex-shrink-0 mt-0.5" />
              <div className="text-sm text-[#F59E0B]">
                <p className="font-medium">Защитите свой аккаунт</p>
                <p className="opacity-80 mt-1">При входе будет запрашиваться дополнительный код подтверждения.</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Информация */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
        <h3 className="text-white font-semibold mb-4">Информация об аккаунте</h3>
        <div className="space-y-3 text-sm">
          <div className="flex justify-between">
            <span className="text-[#71717A]">Логин</span>
            <span className="text-white">{user?.login}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#71717A]">Комиссия</span>
            <span className="text-white">{trader?.commission_rate}%</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#71717A]">Баланс</span>
            <span className="text-white font-['JetBrains_Mono']">{trader?.balance_usdt?.toFixed(2)} USDT</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#71717A]">Дата регистрации</span>
            <span className="text-white">{trader?.created_at ? new Date(trader.created_at).toLocaleDateString("ru-RU") : "—"}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
