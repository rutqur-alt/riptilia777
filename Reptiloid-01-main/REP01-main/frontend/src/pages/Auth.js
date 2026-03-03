import { useState } from "react";
import { useNavigate, Link, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import { useAuth } from "@/App";
import { ArrowLeft, Eye, EyeOff, AtSign, User, Copy, Key, AlertTriangle } from "lucide-react";

export default function Auth() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const refCode = searchParams.get("ref");
  
  const { login, registerTrader, isAuthenticated, user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [recoveryKey, setRecoveryKey] = useState(null);

  const [loginData, setLoginData] = useState({ login: "", password: "" });
  const [registerData, setRegisterData] = useState({ 
    login: "", 
    nickname: "",
    password: "", 
    confirmPassword: "",
    referralCode: refCode || ""
  });

  // Redirect if already authenticated (but not if showing recovery key)
  if (isAuthenticated && user && !recoveryKey) {
    const dashboardPath = user.role === "trader" ? "/trader" : user.role === "merchant" ? "/merchant" : "/admin";
    navigate(dashboardPath, { replace: true });
    return null;
  }

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const userData = await login(loginData);
      toast.success("Добро пожаловать!");
      const dashboardPath = userData.role === "trader" ? "/trader" : userData.role === "merchant" ? "/merchant" : "/admin";
      navigate(dashboardPath);
    } catch (error) {
      const detail = error.response?.data?.detail;
      // Check if it's a blocked user response
      if (detail?.blocked) {
        toast.error(detail.message || "Ваш аккаунт заблокирован");
        // Show additional hint
        setTimeout(() => {
          toast.info(detail.recovery_hint || "Обратитесь в поддержку с ключом восстановления", { duration: 6000 });
        }, 1000);
      } else {
        toast.error(typeof detail === 'string' ? detail : "Неверный логин или пароль");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    if (registerData.password !== registerData.confirmPassword) {
      toast.error("Пароли не совпадают");
      return;
    }
    if (registerData.password.length < 6) {
      toast.error("Пароль должен быть не менее 6 символов");
      return;
    }
    if (registerData.nickname.length < 3 || registerData.nickname.length > 20) {
      toast.error("Никнейм должен быть от 3 до 20 символов");
      return;
    }
    setLoading(true);
    try {
      const userData = await registerTrader({
        login: registerData.login,
        nickname: registerData.nickname,
        password: registerData.password,
        referral_code: registerData.referralCode || undefined
      });
      // Show recovery key modal
      if (userData.recovery_key) {
        setRecoveryKey(userData.recovery_key);
      } else {
        toast.success("Регистрация успешна!");
        navigate("/trader");
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка регистрации");
    } finally {
      setLoading(false);
    }
  };

  const copyRecoveryKey = () => {
    navigator.clipboard.writeText(recoveryKey);
    toast.success("Ключ скопирован!");
  };

  const continueAfterRecoveryKey = () => {
    setRecoveryKey(null);
    navigate("/trader");
  };

  // Recovery Key Modal
  if (recoveryKey) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-[#121212] border border-white/10 rounded-3xl p-8">
          <div className="text-center mb-6">
            <div className="w-16 h-16 rounded-full bg-[#F59E0B]/10 flex items-center justify-center mx-auto mb-4">
              <Key className="w-8 h-8 text-[#F59E0B]" />
            </div>
            <h2 className="text-2xl font-bold text-white font-['Unbounded'] mb-2">
              Ключ восстановления
            </h2>
            <p className="text-[#A1A1AA] text-sm">
              Сохраните этот ключ в надёжном месте
            </p>
          </div>

          <div className="bg-[#F59E0B]/5 border border-[#F59E0B]/20 rounded-xl p-4 mb-6">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-[#F59E0B] flex-shrink-0 mt-0.5" />
              <p className="text-[#F59E0B] text-sm">
                <strong>Внимание!</strong> Этот ключ показывается только один раз. 
                Он понадобится для восстановления аккаунта. Запишите его!
              </p>
            </div>
          </div>

          <div className="bg-[#0A0A0A] border border-white/10 rounded-xl p-4 mb-6">
            <div className="flex items-center justify-between gap-3">
              <code className="text-[#10B981] font-mono text-sm break-all flex-1">
                {recoveryKey}
              </code>
              <Button
                size="sm"
                variant="ghost"
                onClick={copyRecoveryKey}
                className="text-[#A1A1AA] hover:text-white flex-shrink-0"
              >
                <Copy className="w-4 h-4" />
              </Button>
            </div>
          </div>

          <Button
            onClick={continueAfterRecoveryKey}
            className="w-full bg-gradient-to-r from-[#7C3AED] to-[#A855F7] hover:from-[#6D28D9] hover:to-[#9333EA] text-white rounded-xl h-12"
          >
            Я сохранил ключ, продолжить
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0A0A0A] flex">
      {/* Left side - Form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md space-y-8">
          <div>
            <Link to="/" className="inline-flex items-center gap-2 text-[#A1A1AA] hover:text-white transition-colors mb-8">
              <ArrowLeft className="w-4 h-4" />
              <span>На главную</span>
            </Link>
            
            <div className="flex items-center gap-3 mb-2">
              <img src="/logo.jpg" alt="Reptiloid" className="h-10 w-10 rounded-lg" />
              <span className="text-xl font-bold text-white font-['Unbounded']">Reptiloid</span>
            </div>
            <p className="text-[#71717A] mt-4">Войдите или создайте аккаунт трейдера</p>
          </div>

          <Tabs defaultValue="login" className="w-full">
            <TabsList className="w-full bg-[#1A1A1A] border border-white/5 p-1 rounded-xl">
              <TabsTrigger 
                value="login" 
                className="flex-1 rounded-lg data-[state=active]:bg-[#7C3AED] data-[state=active]:text-white"
                data-testid="login-tab"
              >
                Вход
              </TabsTrigger>
              <TabsTrigger 
                value="register" 
                className="flex-1 rounded-lg data-[state=active]:bg-[#7C3AED] data-[state=active]:text-white"
                data-testid="register-tab"
              >
                Регистрация
              </TabsTrigger>
            </TabsList>

            <TabsContent value="login" className="mt-6">
              <form onSubmit={handleLogin} className="space-y-5">
                <div className="space-y-2">
                  <Label htmlFor="login-username" className="text-[#A1A1AA]">Логин</Label>
                  <Input
                    id="login-username"
                    type="text"
                    placeholder="Введите логин"
                    value={loginData.login}
                    onChange={(e) => setLoginData({ ...loginData, login: e.target.value })}
                    className="bg-[#1A1A1A] border-white/10 text-white placeholder:text-[#52525B] h-12 rounded-xl focus:border-[#7C3AED] focus:ring-[#7C3AED]/20"
                    data-testid="login-username-input"
                    required
                  />
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="login-password" className="text-[#A1A1AA]">Пароль</Label>
                  <div className="relative">
                    <Input
                      id="login-password"
                      type={showPassword ? "text" : "password"}
                      placeholder="Введите пароль"
                      value={loginData.password}
                      onChange={(e) => setLoginData({ ...loginData, password: e.target.value })}
                      className="bg-[#1A1A1A] border-white/10 text-white placeholder:text-[#52525B] h-12 rounded-xl focus:border-[#7C3AED] focus:ring-[#7C3AED]/20 pr-12"
                      data-testid="login-password-input"
                      required
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-4 top-1/2 -translate-y-1/2 text-[#71717A] hover:text-white transition-colors"
                    >
                      {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                    </button>
                  </div>
                </div>

                <Button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-[#7C3AED] hover:bg-[#6D28D9] text-white h-12 rounded-xl font-semibold"
                  data-testid="login-submit-btn"
                >
                  {loading ? <div className="spinner" /> : "Войти"}
                </Button>

                <p className="text-center text-[#52525B] text-xs mt-4">
                  Забыли пароль? Войдите в аккаунт и создайте тикет в поддержку с ключом восстановления
                </p>
              </form>
            </TabsContent>

            <TabsContent value="register" className="mt-6">
              <form onSubmit={handleRegister} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="register-username" className="text-[#A1A1AA]">Логин (для входа)</Label>
                  <Input
                    id="register-username"
                    type="text"
                    placeholder="Придумайте логин"
                    value={registerData.login}
                    onChange={(e) => setRegisterData({ ...registerData, login: e.target.value })}
                    className="bg-[#1A1A1A] border-white/10 text-white placeholder:text-[#52525B] h-11 rounded-xl focus:border-[#7C3AED] focus:ring-[#7C3AED]/20"
                    data-testid="register-username-input"
                    required
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="register-nickname" className="text-[#A1A1AA]">Никнейм (для идентификации)</Label>
                  <div className="relative">
                    <AtSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#52525B]" />
                    <Input
                      id="register-nickname"
                      type="text"
                      placeholder="Ваш публичный никнейм"
                      value={registerData.nickname}
                      onChange={(e) => setRegisterData({ ...registerData, nickname: e.target.value })}
                      className="bg-[#1A1A1A] border-white/10 text-white placeholder:text-[#52525B] h-11 rounded-xl focus:border-[#7C3AED] focus:ring-[#7C3AED]/20 pl-9"
                      data-testid="register-nickname-input"
                      minLength={3}
                      maxLength={20}
                      required
                    />
                  </div>
                  <p className="text-[10px] text-[#52525B]">Виден другим пользователям (3-20 символов)</p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="register-password" className="text-[#A1A1AA]">Пароль</Label>
                  <Input
                    id="register-password"
                    type="password"
                    placeholder="Минимум 6 символов"
                    value={registerData.password}
                    onChange={(e) => setRegisterData({ ...registerData, password: e.target.value })}
                    className="bg-[#1A1A1A] border-white/10 text-white placeholder:text-[#52525B] h-11 rounded-xl focus:border-[#7C3AED] focus:ring-[#7C3AED]/20"
                    data-testid="register-password-input"
                    required
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="register-confirm-password" className="text-[#A1A1AA]">Подтвердите пароль</Label>
                  <Input
                    id="register-confirm-password"
                    type="password"
                    placeholder="Повторите пароль"
                    value={registerData.confirmPassword}
                    onChange={(e) => setRegisterData({ ...registerData, confirmPassword: e.target.value })}
                    className="bg-[#1A1A1A] border-white/10 text-white placeholder:text-[#52525B] h-11 rounded-xl focus:border-[#7C3AED] focus:ring-[#7C3AED]/20"
                    data-testid="register-confirm-password-input"
                    required
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="register-referral" className="text-[#A1A1AA]">Реферальный код (опционально)</Label>
                  <Input
                    id="register-referral"
                    type="text"
                    placeholder="Код друга, например T1A2B3"
                    value={registerData.referralCode}
                    onChange={(e) => setRegisterData({ ...registerData, referralCode: e.target.value.toUpperCase() })}
                    className="bg-[#1A1A1A] border-white/10 text-white placeholder:text-[#52525B] h-11 rounded-xl focus:border-[#7C3AED] focus:ring-[#7C3AED]/20"
                    data-testid="register-referral-input"
                  />
                </div>

                <Button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-[#7C3AED] hover:bg-[#6D28D9] text-white h-12 rounded-xl font-semibold"
                  data-testid="register-submit-btn"
                >
                  {loading ? <div className="spinner" /> : "Создать аккаунт"}
                </Button>
              </form>
            </TabsContent>
          </Tabs>

          <div className="text-center">
            <p className="text-[#71717A] text-sm">
              Хотите подключить бизнес?{" "}
              <Link to="/merchant/register" className="text-[#7C3AED] hover:text-[#A855F7] transition-colors">
                Регистрация мерчанта
              </Link>
            </p>
          </div>
        </div>
      </div>

      {/* Right side - Image */}
      <div className="hidden lg:flex flex-1 items-center justify-center bg-[#121212] relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-[#7C3AED]/10 to-transparent" />
        <img 
          src="https://images.unsplash.com/photo-1639503547276-90230c4a4198?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2Nzh8MHwxfHNlYXJjaHwxfHxjeWJlcnNlY3VyaXR5JTIwZGlnaXRhbCUyMHNoaWVsZCUyMGRhcmt8ZW58MHx8fHwxNzY4NjAzMTg4fDA&ixlib=rb-4.1.0&q=85"
          alt="Security"
          className="w-full h-full object-cover opacity-50"
        />
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="text-center px-12">
            <h2 className="text-3xl font-bold text-white font-['Unbounded'] mb-4">
              Безопасная торговля
            </h2>
            <p className="text-[#A1A1AA] max-w-md">
              Все сделки защищены эскроу-системой. Ваши средства в безопасности.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
