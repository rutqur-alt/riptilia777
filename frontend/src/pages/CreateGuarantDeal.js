import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Wallet, ArrowLeft, Shield, Users, AlertCircle, CheckCircle } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { toast } from "sonner";

export default function CreateGuarantDeal() {
  const { isAuthenticated, user, token, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [ready, setReady] = useState(false);
  
  const [formData, setFormData] = useState({
    role: "", // buyer or seller
    amount: "",
    currency: "USDT",
    title: "",
    description: "",
    conditions: "",
    counterpartyNickname: ""
  });

  // Wait for auth check to complete
  useEffect(() => {
    const timeout = setTimeout(() => setReady(true), 500);
    return () => clearTimeout(timeout);
  }, []);

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!isAuthenticated) {
      toast.error("Войдите в систему");
      navigate("/auth");
      return;
    }

    if (!formData.role || !formData.amount || !formData.title || !formData.description) {
      toast.error("Заполните все обязательные поля");
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post(
        `${API}/guarantor/deals`,
        {
          role: formData.role,
          amount: parseFloat(formData.amount),
          currency: formData.currency,
          title: formData.title,
          description: formData.description,
          conditions: formData.conditions,
          counterparty_nickname: formData.counterpartyNickname || null
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      toast.success("Сделка создана!");
      navigate(`/guarantor/deal/${response.data.id}`);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка создания сделки");
    } finally {
      setLoading(false);
    }
  };

  const commission = formData.amount ? (parseFloat(formData.amount) * 0.05).toFixed(2) : "0";
  const sellerReceives = formData.amount ? (parseFloat(formData.amount) * 0.95).toFixed(2) : "0";

  // Loading state while checking auth
  if (authLoading || !ready) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-[#7C3AED] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
        <div className="text-center">
          <Shield className="w-16 h-16 text-[#7C3AED] mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-white mb-2">Требуется авторизация</h2>
          <p className="text-[#71717A] mb-6">Войдите, чтобы создать сделку с гарантом</p>
          <Link to="/auth">
            <Button className="bg-[#7C3AED] hover:bg-[#6D28D9] text-white rounded-xl" title="Войти в аккаунт">
              Войти
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0A0A0A]">
      {/* Header */}
      <header className="border-b border-white/5">
        <div className="max-w-2xl mx-auto px-4 py-4">
          <div className="flex items-center gap-4">
            <Link to="/guarantor">
              <Button variant="ghost" size="icon" className="text-[#A1A1AA] hover:text-white hover:bg-white/5">
                <ArrowLeft className="w-5 h-5" />
              </Button>
            </Link>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-[#7C3AED] flex items-center justify-center">
                <Wallet className="w-4 h-4 text-white" />
              </div>
              <span className="text-lg font-semibold text-white">Создать сделку</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-2xl mx-auto px-4 py-8">
        {/* Info banner */}
        <div className="bg-[#7C3AED]/10 border border-[#7C3AED]/30 rounded-xl p-4 mb-8">
          <div className="flex items-start gap-3">
            <Shield className="w-5 h-5 text-[#7C3AED] mt-0.5" />
            <div>
              <p className="text-[#E4E4E7] text-sm">
                Создайте сделку и пригласите второго участника. Деньги будут заморожены у гаранта 
                до выполнения условий. Комиссия 5% удерживается только с успешных сделок.
              </p>
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Role selection */}
          <div>
            <label className="block text-sm font-medium text-[#A1A1AA] mb-2">
              Ваша роль в сделке *
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => handleChange("role", "buyer")}
                className={`p-4 rounded-xl border text-left transition-all ${
                  formData.role === "buyer" 
                    ? "bg-[#10B981]/10 border-[#10B981]/50 text-white" 
                    : "bg-[#121212] border-white/10 text-[#71717A] hover:border-white/20"
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <Users className="w-4 h-4" />
                  <span className="font-medium">Покупатель</span>
                </div>
                <p className="text-xs opacity-70">Я плачу и получаю товар/услугу</p>
              </button>
              <button
                type="button"
                onClick={() => handleChange("role", "seller")}
                className={`p-4 rounded-xl border text-left transition-all ${
                  formData.role === "seller" 
                    ? "bg-[#3B82F6]/10 border-[#3B82F6]/50 text-white" 
                    : "bg-[#121212] border-white/10 text-[#71717A] hover:border-white/20"
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <Users className="w-4 h-4" />
                  <span className="font-medium">Продавец</span>
                </div>
                <p className="text-xs opacity-70">Я выполняю условия и получаю оплату</p>
              </button>
            </div>
          </div>

          {/* Amount and currency */}
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <label className="block text-sm font-medium text-[#A1A1AA] mb-2">
                Сумма сделки *
              </label>
              <Input
                type="number"
                step="0.01"
                min="1"
                value={formData.amount}
                onChange={(e) => handleChange("amount", e.target.value)}
                placeholder="1000"
                className="bg-[#121212] border-white/10 text-white h-11 rounded-xl"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[#A1A1AA] mb-2">
                Валюта
              </label>
              <Select value={formData.currency} onValueChange={(v) => handleChange("currency", v)}>
                <SelectTrigger className="bg-[#121212] border-white/10 text-white h-11 rounded-xl">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-[#121212] border-white/10">
                  <SelectItem value="USDT" className="text-white">USDT</SelectItem>
                  <SelectItem value="TON" className="text-white">TON</SelectItem>
                  <SelectItem value="BTC" className="text-white">BTC</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Commission preview */}
          {formData.amount && parseFloat(formData.amount) > 0 && (
            <div className="bg-[#121212] border border-white/5 rounded-xl p-4">
              <div className="grid grid-cols-3 gap-4 text-center text-sm">
                <div>
                  <div className="text-white font-medium">{formData.amount} {formData.currency}</div>
                  <div className="text-[#52525B] text-xs">Сумма</div>
                </div>
                <div>
                  <div className="text-[#F59E0B] font-medium">{commission} {formData.currency}</div>
                  <div className="text-[#52525B] text-xs">Комиссия 5%</div>
                </div>
                <div>
                  <div className="text-[#10B981] font-medium">{sellerReceives} {formData.currency}</div>
                  <div className="text-[#52525B] text-xs">Продавец получит</div>
                </div>
              </div>
            </div>
          )}

          {/* Title */}
          <div>
            <label className="block text-sm font-medium text-[#A1A1AA] mb-2">
              Название сделки *
            </label>
            <Input
              value={formData.title}
              onChange={(e) => handleChange("title", e.target.value)}
              placeholder="Например: Покупка аккаунта Steam"
              maxLength={100}
              className="bg-[#121212] border-white/10 text-white h-11 rounded-xl"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-[#A1A1AA] mb-2">
              Описание сделки *
            </label>
            <Textarea
              value={formData.description}
              onChange={(e) => handleChange("description", e.target.value)}
              placeholder="Подробно опишите что именно продаётся/покупается"
              rows={3}
              maxLength={1000}
              className="bg-[#121212] border-white/10 text-white rounded-xl resize-none"
            />
          </div>

          {/* Conditions */}
          <div>
            <label className="block text-sm font-medium text-[#A1A1AA] mb-2">
              Условия выполнения
            </label>
            <Textarea
              value={formData.conditions}
              onChange={(e) => handleChange("conditions", e.target.value)}
              placeholder="Когда сделка считается выполненной? Например: после передачи данных аккаунта и проверки входа"
              rows={2}
              maxLength={500}
              className="bg-[#121212] border-white/10 text-white rounded-xl resize-none"
            />
          </div>

          {/* Counterparty */}
          <div>
            <label className="block text-sm font-medium text-[#A1A1AA] mb-2">
              Никнейм второго участника (опционально)
            </label>
            <Input
              value={formData.counterpartyNickname}
              onChange={(e) => handleChange("counterpartyNickname", e.target.value)}
              placeholder="Если знаете никнейм — укажите, иначе получите ссылку-приглашение"
              className="bg-[#121212] border-white/10 text-white h-11 rounded-xl"
            />
            <p className="text-xs text-[#52525B] mt-1">
              Если не указан — вы получите ссылку для приглашения второго участника
            </p>
          </div>

          {/* Submit */}
          <Button
            type="submit"
            disabled={loading || !formData.role || !formData.amount || !formData.title || !formData.description}
            className="w-full bg-[#7C3AED] hover:bg-[#6D28D9] text-white rounded-xl h-12 text-lg"
          >
            {loading ? "Создание..." : "Создать сделку"}
          </Button>

          {/* Warning */}
          <div className="flex items-start gap-2 text-xs text-[#52525B]">
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <p>
              После создания сделки второй участник должен подтвердить условия. 
              Затем покупатель переводит средства на платформу.
            </p>
          </div>
        </form>
      </main>
    </div>
  );
}
