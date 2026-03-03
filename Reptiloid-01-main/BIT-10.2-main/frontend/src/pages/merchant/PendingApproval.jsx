import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth, api } from '@/lib/auth';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Coins, Clock, MessageCircle, LogOut, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';

const MerchantPendingApproval = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [checking, setChecking] = useState(false);

  const checkStatus = async () => {
    setChecking(true);
    try {
      const res = await api.get('/auth/me');
      if (res.data.approval_status === 'approved' && res.data.is_active) {
        toast.success('Ваша заявка одобрена! Добро пожаловать!');
        localStorage.setItem('user', JSON.stringify(res.data));
        window.location.href = '/merchant';  // Full reload to update auth context
      } else if (res.data.approval_status === 'rejected') {
        toast.error('К сожалению, ваша заявка отклонена.');
      } else {
        toast.info('Ваша заявка ещё на рассмотрении');
      }
    } catch (error) {
      toast.error('Ошибка проверки статуса');
    } finally {
      setChecking(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-[#09090B] flex flex-col">
      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-[#09090B]/95 backdrop-blur-xl border-b border-zinc-800">
        <div className="px-4 lg:px-6 py-3 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-9 h-9 rounded-lg bg-emerald-500 flex items-center justify-center">
              <Coins className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-lg font-['Chivo']">BITARBITR</span>
          </Link>
          <Button 
            variant="ghost" 
            onClick={handleLogout}
            className="text-zinc-400 hover:text-white"
          >
            <LogOut className="w-4 h-4 mr-2" />
            Выйти
          </Button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex items-center justify-center p-4 pt-20">
        <Card className="bg-zinc-900 border-zinc-800 max-w-lg w-full">
          <CardContent className="p-8 text-center">
            {/* Icon */}
            <div className="w-20 h-20 rounded-full bg-orange-500/10 flex items-center justify-center mx-auto mb-6">
              <Clock className="w-10 h-10 text-orange-400" />
            </div>

            {/* Title */}
            <h1 className="text-2xl font-bold font-['Chivo'] mb-2">
              Заявка на рассмотрении
            </h1>
            <p className="text-zinc-400 mb-6">
              Ваша заявка на регистрацию мерчанта находится на рассмотрении администрации. 
              Обычно это занимает от нескольких часов до 1 рабочего дня.
            </p>

            {/* Status Box */}
            <div className="bg-zinc-800 rounded-xl p-4 mb-6">
              <div className="flex items-center justify-between mb-3">
                <span className="text-zinc-400 text-sm">Логин:</span>
                <span className="font-['JetBrains_Mono'] text-sm">@{user?.login}</span>
              </div>
              <div className="flex items-center justify-between mb-3">
                <span className="text-zinc-400 text-sm">Никнейм:</span>
                <span className="text-sm">{user?.nickname}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-zinc-400 text-sm">Статус:</span>
                <span className="px-3 py-1 bg-orange-500/20 text-orange-400 rounded-full text-sm font-medium">
                  Ожидает одобрения
                </span>
              </div>
            </div>

            {/* Info */}
            <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-4 mb-6 text-left">
              <h3 className="font-medium text-emerald-400 mb-2">Что происходит дальше?</h3>
              <ul className="text-sm text-zinc-300 space-y-2">
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400">1.</span>
                  Администратор проверит вашу заявку
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400">2.</span>
                  После одобрения вы получите доступ к панели мерчанта
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400">3.</span>
                  Интегрируйте API и начните принимать оплаты
                </li>
              </ul>
            </div>

            {/* Actions */}
            <div className="flex flex-col sm:flex-row gap-3">
              <Button 
                onClick={checkStatus}
                disabled={checking}
                className="flex-1 bg-emerald-500 hover:bg-emerald-600"
              >
                {checking ? (
                  <span className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Проверяю...
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <RefreshCw className="w-4 h-4" />
                    Проверить статус
                  </span>
                )}
              </Button>
              <Link to="/support" className="flex-1">
                <Button variant="outline" className="w-full border-zinc-700">
                  <MessageCircle className="w-4 h-4 mr-2" />
                  Написать в поддержку
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
};

export default MerchantPendingApproval;
