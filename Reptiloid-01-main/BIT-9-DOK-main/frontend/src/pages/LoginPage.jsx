import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '@/lib/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import { DollarSign, ArrowLeft, Eye, EyeOff, AtSign } from 'lucide-react';

const LoginPage = () => {
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const { login: authLogin, user } = useAuth();
  const navigate = useNavigate();

  // Debug: check if token exists on page load
  useEffect(() => {
    const token = localStorage.getItem('token');
    const savedUser = localStorage.getItem('user');
    console.log('LoginPage mounted - Token exists:', !!token, 'User exists:', !!savedUser);
    
    // If already logged in, redirect to dashboard
    if (user) {
      const dashboards = {
        trader: '/trader',
        merchant: '/merchant',
        admin: '/admin',
        support: '/admin',
      };
      navigate(dashboards[user.role] || '/dashboard', { replace: true });
    }
  }, [user, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    setLoading(true);

    try {
      const res = await authLogin(login, password, null, null);
      
      // Check if 2FA is required - redirect to 2FA page
      if (res.requires_2fa) {
        navigate('/two-factor', { 
          state: { 
            loginStr: login, 
            password: password
          },
          replace: true
        });
        return;
      }
      
      toast.success('Добро пожаловать!');
      
      const dashboards = {
        trader: '/trader',
        merchant: '/merchant',
        admin: '/admin',
        support: '/admin',
      };
      navigate(dashboards[res.role] || '/dashboard');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка авторизации');
    } finally {
      setLoading(false);
    }
  };

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
              <p className="text-sm text-zinc-400">Вход в систему</p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="login">Логин</Label>
              <div className="relative">
                <AtSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                <Input
                  id="login"
                  type="text"
                  value={login}
                  onChange={(e) => setLogin(e.target.value)}
                  placeholder="Ваш логин"
                  className="pl-10 bg-zinc-900 border-zinc-800 focus:border-emerald-500"
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Пароль</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="pr-10 bg-zinc-900 border-zinc-800 focus:border-emerald-500"
                  required
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

            <Button
              type="submit"
              className="w-full bg-emerald-500 hover:bg-emerald-600 h-12"
              disabled={loading}
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                'Войти'
              )}
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-zinc-400">
            Нет аккаунта?{' '}
            <Link to="/register" className="text-emerald-400 hover:text-emerald-300">
              Зарегистрироваться
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
