import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/lib/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import { DollarSign, Smartphone, ArrowLeft } from 'lucide-react';

const TwoFactorPage = () => {
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const { login: authLogin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  
  // Get credentials from state (passed from login page)
  const { loginStr, password, captchaToken } = location.state || {};

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (code.length !== 6) {
      toast.error('Введите 6-значный код');
      return;
    }
    
    if (!loginStr || !password) {
      toast.error('Сессия истекла, войдите снова');
      navigate('/login');
      return;
    }
    
    setLoading(true);

    try {
      // Don't pass captchaToken on 2FA verification - it was verified on first login step
      const res = await authLogin(loginStr, password, code, null);
      
      if (res.requires_2fa) {
        toast.error('Неверный код 2FA');
        setCode('');
        setLoading(false);
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
      toast.error(error.response?.data?.detail || 'Неверный код 2FA');
      setCode('');
    } finally {
      setLoading(false);
    }
  };

  // Redirect if no credentials
  if (!loginStr || !password) {
    return (
      <div className="min-h-screen bg-[#09090B] flex items-center justify-center p-6">
        <div className="text-center">
          <p className="text-zinc-400 mb-4">Сессия истекла</p>
          <Button onClick={() => navigate('/login')} className="bg-emerald-500 hover:bg-emerald-600">
            Войти снова
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#09090B] flex items-center justify-center p-6">
      <div className="w-full max-w-md">
        <button 
          onClick={() => navigate('/login')}
          className="inline-flex items-center gap-2 text-zinc-400 hover:text-white mb-8 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Назад
        </button>

        <div className="card-solid rounded-2xl p-8">
          <div className="flex items-center gap-3 mb-8">
            <div className="w-12 h-12 rounded-xl bg-emerald-500 flex items-center justify-center">
              <DollarSign className="w-7 h-7 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold font-['Chivo']">BITARBITR</h1>
              <p className="text-sm text-zinc-400">Двухфакторная аутентификация</p>
            </div>
          </div>

          <div className="mb-6 p-4 bg-zinc-800/50 rounded-lg">
            <div className="flex items-center gap-3 mb-2">
              <Smartphone className="w-5 h-5 text-emerald-400" />
              <span className="font-medium">Google Authenticator</span>
            </div>
            <p className="text-sm text-zinc-400">
              Введите 6-значный код из приложения Google Authenticator
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="code">Код подтверждения</Label>
              <Input
                id="code"
                type="text"
                inputMode="numeric"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="000000"
                className="bg-zinc-900 border-zinc-800 focus:border-emerald-500 text-center font-['JetBrains_Mono'] text-3xl tracking-[0.5em] h-16"
                maxLength={6}
                autoFocus
              />
            </div>

            <Button
              type="submit"
              className="w-full bg-emerald-500 hover:bg-emerald-600 h-12"
              disabled={loading || code.length !== 6}
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                'Подтвердить'
              )}
            </Button>
          </form>

          <p className="mt-6 text-center text-xs text-zinc-500">
            Код обновляется каждые 30 секунд
          </p>
        </div>
      </div>
    </div>
  );
};

export default TwoFactorPage;
