import { useState } from "react";
import { useNavigate, Link, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from "sonner";
import { useAuth } from "@/App";
import { Wallet, ArrowLeft, MessageCircle, CheckCircle, Clock } from "lucide-react";

export default function MerchantRegister() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const refCode = searchParams.get("ref");
  
  const { registerMerchant, isAuthenticated, user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [agreed, setAgreed] = useState(false);
  const [registrationComplete, setRegistrationComplete] = useState(false);
  
  const [formData, setFormData] = useState({
    login: "",
    password: "",
    confirmPassword: "",
    nickname: "",
    merchant_name: "",
    referral_code: refCode || ""
  });

  // Only redirect if already authenticated AND not just registered
  if (isAuthenticated && user?.role === "merchant" && !registrationComplete) {
    navigate("/merchant", { replace: true });
    return null;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!agreed) {
      toast.error("Необходимо принять правила платформы");
      return;
    }
    
    if (formData.password !== formData.confirmPassword) {
      toast.error("Пароли не совпадают");
      return;
    }
    
    if (formData.password.length < 6) {
      toast.error("Пароль должен быть не менее 6 символов");
      return;
    }

    if (!formData.merchant_name.trim()) {
      toast.error("Укажите название площадки");
      return;
    }

    setLoading(true);
    try {
      await registerMerchant({
        login: formData.login,
        password: formData.password,
        nickname: formData.nickname || formData.merchant_name,
        merchant_name: formData.merchant_name,
        merchant_type: "default",
        referral_code: formData.referral_code || undefined
      });
      setRegistrationComplete(true);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка регистрации");
    } finally {
      setLoading(false);
    }
  };

  // Success screen after registration
  if (registrationComplete) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center px-4">
        <div className="max-w-md w-full bg-[#121212] border border-white/5 rounded-3xl p-8 text-center">
          <div className="w-20 h-20 rounded-full bg-[#10B981]/10 flex items-center justify-center mx-auto mb-6">
            <CheckCircle className="w-10 h-10 text-[#10B981]" />
          </div>
          
          <h1 className="text-2xl font-bold text-white font-['Unbounded'] mb-4">
            Регистрация успешна!
          </h1>
          
          <p className="text-[#A1A1AA] mb-6">
            Ваша заявка на регистрацию получена
          </p>

          <div className="bg-[#0A0A0A] border border-white/5 rounded-2xl p-4 mb-6 text-left space-y-3">
            <div className="flex items-center gap-3">
              <Clock className="w-5 h-5 text-[#F59E0B]" />
              <div>
                <div className="text-sm text-[#71717A]">Статус</div>
                <div className="text-[#F59E0B] font-medium">ОЖИДАЕТ ОДОБРЕНИЯ</div>
              </div>
            </div>
            
            <div className="flex items-start gap-3">
              <MessageCircle className="w-5 h-5 text-[#7C3AED] mt-0.5" />
              <div className="text-sm text-[#A1A1AA]">
                Для ускорения проверки перейдите в чат с администрацией, где вы сможете ответить на вопросы и предоставить дополнительную информацию.
              </div>
            </div>
          </div>

          <p className="text-sm text-[#52525B] mb-6">
            ⏳ Обычно проверка занимает 1-24 часа
          </p>

          <Button
            onClick={() => navigate("/merchant")}
            className="w-full bg-[#7C3AED] hover:bg-[#6D28D9] h-12 rounded-xl font-semibold"
            title="Перейти в чат с администрацией"
          >
            <MessageCircle className="w-5 h-5 mr-2" />
            Перейти в чат с администрацией
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0A0A0A]">
      {/* Header */}
      <div className="border-b border-white/5">
        <div className="max-w-4xl mx-auto px-6 py-6 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#7C3AED] to-[#A855F7] flex items-center justify-center">
              <Wallet className="w-5 h-5 text-white" />
            </div>
            <img src="/logo.png" alt="Reptiloid" className="h-9 w-9" />
            <span className="text-xl font-bold text-white font-['Unbounded']">Reptiloid</span>
          </Link>
          <Link to="/" className="text-[#A1A1AA] hover:text-white transition-colors flex items-center gap-2">
            <ArrowLeft className="w-4 h-4" />
            <span>На главную</span>
          </Link>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-lg mx-auto px-6 py-12">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white font-['Unbounded'] mb-3">
            Регистрация мерчанта
          </h1>
          <p className="text-[#A1A1AA]">
            Подключите ваш бизнес к P2P платежам
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="space-y-6 animate-fade-in-up">
            <div className="bg-[#121212] border border-white/5 rounded-2xl p-6 space-y-5">
              <div className="space-y-2">
                <Label htmlFor="login" className="text-[#A1A1AA]">Логин</Label>
                <Input
                  id="login"
                  type="text"
                  placeholder="Придумайте логин"
                  value={formData.login}
                  onChange={(e) => setFormData({ ...formData, login: e.target.value })}
                  className="bg-[#1A1A1A] border-white/10 text-white placeholder:text-[#52525B] h-12 rounded-xl focus:border-[#7C3AED]"
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="merchant_name" className="text-[#A1A1AA]">Название площадки</Label>
                <Input
                  id="merchant_name"
                  type="text"
                  placeholder="Название вашего бизнеса"
                  value={formData.merchant_name}
                  onChange={(e) => setFormData({ ...formData, merchant_name: e.target.value })}
                  className="bg-[#1A1A1A] border-white/10 text-white placeholder:text-[#52525B] h-12 rounded-xl focus:border-[#7C3AED]"
                  required
                />
              </div>

              <div className="grid sm:grid-cols-2 gap-5">
                <div className="space-y-2">
                  <Label htmlFor="password" className="text-[#A1A1AA]">Пароль</Label>
                  <Input
                    id="password"
                    type="password"
                    placeholder="Минимум 6 символов"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    className="bg-[#1A1A1A] border-white/10 text-white placeholder:text-[#52525B] h-12 rounded-xl focus:border-[#7C3AED]"
                    required
                  />
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="confirmPassword" className="text-[#A1A1AA]">Подтвердите пароль</Label>
                  <Input
                    id="confirmPassword"
                    type="password"
                    placeholder="Повторите пароль"
                    value={formData.confirmPassword}
                    onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                    className="bg-[#1A1A1A] border-white/10 text-white placeholder:text-[#52525B] h-12 rounded-xl focus:border-[#7C3AED]"
                    required
                  />
                </div>
              </div>

              {/* Referral indicator */}
              {refCode && (
                <div className="flex items-center gap-2 p-3 bg-[#10B981]/10 border border-[#10B981]/30 rounded-xl">
                  <div className="w-6 h-6 rounded-full bg-[#10B981] flex items-center justify-center">
                    <span className="text-white text-sm">✓</span>
                  </div>
                  <span className="text-[#10B981] text-sm font-medium">Вы регистрируетесь по приглашению</span>
                </div>
              )}
            </div>

            <div className="flex items-start gap-3">
              <Checkbox
                id="agree"
                checked={agreed}
                onCheckedChange={setAgreed}
                className="mt-1 border-white/20 data-[state=checked]:bg-[#7C3AED] data-[state=checked]:border-[#7C3AED]"
              />
              <label htmlFor="agree" className="text-sm text-[#A1A1AA] cursor-pointer">
                Я согласен с правилами платформы и понимаю, что мой аккаунт будет активирован после проверки администратором
              </label>
            </div>

            <Button
              type="submit"
              disabled={loading || !agreed}
              className="w-full bg-[#7C3AED] hover:bg-[#6D28D9] text-white h-12 rounded-xl font-semibold disabled:opacity-50"
              title="Отправить заявку на регистрацию"
            >
              {loading ? <div className="spinner" /> : "Отправить заявку"}
            </Button>
          </div>
        </form>

        {/* Info box */}
        <div className="mt-8 p-6 bg-[#7C3AED]/10 border border-[#7C3AED]/20 rounded-2xl">
          <h3 className="text-white font-semibold mb-2">Что дальше?</h3>
          <ul className="space-y-2 text-sm text-[#A1A1AA]">
            <li className="flex items-start gap-2">
              <span className="text-[#7C3AED]">1.</span>
              После регистрации вы попадете в чат с администрацией
            </li>
            <li className="flex items-start gap-2">
              <span className="text-[#7C3AED]">2.</span>
              Расскажите о вашей площадке и планируемых объемах
            </li>
            <li className="flex items-start gap-2">
              <span className="text-[#7C3AED]">3.</span>
              После одобрения получите доступ к API и платежным ссылкам
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
