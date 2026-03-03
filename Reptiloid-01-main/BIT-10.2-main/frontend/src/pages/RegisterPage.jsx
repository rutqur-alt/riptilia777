import React, { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '@/lib/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import { DollarSign, ArrowLeft, Eye, EyeOff, User, Building2, Shield, AtSign } from 'lucide-react';

const RegisterPage = () => {
  const [searchParams] = useSearchParams();
  const initialRole = searchParams.get('role') || 'trader';
  const referralCode = searchParams.get('ref') || '';  // Получаем реферальный код из URL
  
  const [login, setLogin] = useState('');
  const [nickname, setNickname] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [role, setRole] = useState(initialRole);
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (login.length < 3) {
      toast.error('Логин должен быть не менее 3 символов');
      return;
    }
    
    if (!/^[a-zA-Z0-9]+$/.test(login)) {
      toast.error('Логин может содержать только буквы и цифры');
      return;
    }
    
    if (!nickname.trim()) {
      toast.error('Введите никнейм');
      return;
    }
    
    if (password !== confirmPassword) {
      toast.error('Пароли не совпадают');
      return;
    }
    
    if (password.length < 6) {
      toast.error('Пароль должен быть не менее 6 символов');
      return;
    }

    setLoading(true);

    try {
      const res = await register(login, nickname, password, role, referralCode || null);
      toast.success('Регистрация успешна!');
      
      const dashboards = {
        trader: '/trader',
        merchant: '/merchant',
        admin: '/admin',
      };
      navigate(dashboards[res.role] || '/dashboard');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка регистрации');
    } finally {
      setLoading(false);
    }
  };

  const roles = [
    { id: 'trader', label: 'Трейдер', icon: User, description: 'Провайдер ликвидности' },
    { id: 'merchant', label: 'Мерчант', icon: Building2, description: 'Владелец магазина' },
  ];

  return (
    <div className="min-h-screen bg-[#09090B] flex items-center justify-center p-6">
      <div className="w-full max-w-md">
        <Link to="/" className="inline-flex items-center gap-2 text-zinc-400 hover:text-white mb-8 transition-colors">
          <ArrowLeft className="w-4 h-4" />
          На главную
        </Link>

        <div className="card-solid rounded-2xl p-8">
          <div className="flex items-center gap-3 mb-8">
            <div className="w-12 h-12 rounded-xl bg-emerald-500 flex items-center justify-center">
              <DollarSign className="w-7 h-7 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold font-['Chivo']">BITARBITR</h1>
              <p className="text-sm text-zinc-400">Регистрация</p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Referral Badge */}
            {referralCode && (
              <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-emerald-500/20 flex items-center justify-center">
                  <User className="w-4 h-4 text-emerald-400" />
                </div>
                <div>
                  <div className="text-sm font-medium text-emerald-400">Регистрация по приглашению</div>
                  <div className="text-xs text-zinc-400">Код: {referralCode}</div>
                </div>
              </div>
            )}
            
            {/* Role Selection */}
            <div className="space-y-2">
              <Label>Тип аккаунта</Label>
              <div className="grid grid-cols-2 gap-3">
                {roles.map((r) => (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => setRole(r.id)}
                    className={`p-4 rounded-xl border text-left transition-all ${
                      role === r.id
                        ? 'border-emerald-500 bg-emerald-500/10'
                        : 'border-zinc-800 hover:border-zinc-700'
                    }`}
                    data-testid={`role-${r.id}-btn`}
                  >
                    <r.icon className={`w-5 h-5 mb-2 ${role === r.id ? 'text-emerald-400' : 'text-zinc-400'}`} />
                    <div className="font-medium">{r.label}</div>
                    <div className="text-xs text-zinc-500">{r.description}</div>
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="login">Логин</Label>
              <div className="relative">
                <AtSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                <Input
                  id="login"
                  type="text"
                  placeholder="mylogin123"
                  value={login}
                  onChange={(e) => setLogin(e.target.value.toLowerCase())}
                  required
                  className="bg-zinc-950 border-zinc-800 focus:border-emerald-500 pl-10"
                  data-testid="register-login-input"
                />
              </div>
              <p className="text-xs text-zinc-500">Только буквы и цифры, минимум 3 символа</p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="nickname">Никнейм</Label>
              <Input
                id="nickname"
                type="text"
                placeholder="Ваше имя на платформе"
                value={nickname}
                onChange={(e) => setNickname(e.target.value)}
                required
                className="bg-zinc-950 border-zinc-800 focus:border-emerald-500"
                data-testid="register-nickname-input"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Пароль</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Минимум 6 символов"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="bg-zinc-950 border-zinc-800 focus:border-emerald-500 pr-10"
                  data-testid="register-password-input"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-white"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Подтвердите пароль</Label>
              <Input
                id="confirmPassword"
                type="password"
                placeholder="Повторите пароль"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                className="bg-zinc-950 border-zinc-800 focus:border-emerald-500"
                data-testid="register-confirm-password-input"
              />
            </div>

            <div className="flex items-start gap-2 text-sm text-zinc-400">
              <Shield className="w-4 h-4 mt-0.5 text-emerald-400 flex-shrink-0" />
              <span>Регистрируясь, вы соглашаетесь с условиями использования платформы</span>
            </div>

            <Button 
              type="submit" 
              className="w-full bg-emerald-500 hover:bg-emerald-600" 
              disabled={loading}
              data-testid="register-submit-btn"
            >
              {loading ? 'Регистрация...' : 'Создать аккаунт'}
            </Button>
          </form>

          <div className="mt-6 pt-6 border-t border-zinc-800 text-center">
            <p className="text-zinc-400 text-sm">
              Уже есть аккаунт?{' '}
              <Link to="/login" className="text-emerald-400 hover:text-emerald-300">
                Войти
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RegisterPage;
