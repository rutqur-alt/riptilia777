import React, { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth, api } from '@/lib/auth';
import { useBalance } from '@/contexts/BalanceContext';
import { Button } from '@/components/ui/button';
import AdminNotifications from '@/components/AdminNotifications';
import UserNotifications from '@/components/UserNotifications';
import { usePWA } from '@/hooks/usePWA';
import { toast } from 'sonner';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Coins, LayoutDashboard, Briefcase, CreditCard, Wallet,
  Users, FileText, AlertTriangle, Settings, LogOut, ChevronDown, Menu, X, MessageCircle, PiggyBank, Shield, BarChart3, BarChart2, Zap, Download, Smartphone, Clock, Gift, Wrench, Activity
} from 'lucide-react';

const DashboardLayout = ({ children }) => {
  const { user, logout } = useAuth();
  const { traderBalance, merchantBalance, refreshBalance } = useBalance();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = React.useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [usdtRate, setUsdtRate] = useState(null);
  
  // PWA install
  const { isInstallable, isInstalled, isIOS, installApp } = usePWA();
  const [installing, setInstalling] = useState(false);
  const [showInstallModal, setShowInstallModal] = useState(false);
  
  const handleInstallApp = async () => {
    setInstalling(true);
    const result = await installApp();
    setInstalling(false);
    
    // Если нативная установка сработала (true) - ничего не показываем
    if (result === true) {
      return;
    }
    
    // Если iOS или нет нативного промпта - показываем инструкции
    if (result === 'ios' || result === 'manual' || result === false) {
      setShowInstallModal(true);
    }
  };

  // Получаем курс USDT/RUB
  useEffect(() => {
    const fetchRate = async () => {
      try {
        const res = await api.get('/usdt/rate');
        setUsdtRate(res.data.usdt_rub);
      } catch (error) {
        console.error('Error fetching USDT rate:', error);
      }
    };
    
    fetchRate();
    // Обновляем каждые 5 минут
    const interval = setInterval(fetchRate, 300000);
    return () => clearInterval(interval);
  }, []);

  // Перевод заработанного на баланс
  const handleWithdrawEarnings = async () => {
    try {
      const res = await api.post('/trader/withdraw-earnings');
      toast.success(`${res.data.withdrawn.toFixed(2)} USDT зачислено на баланс!`);
      // Обновляем баланс через контекст
      refreshBalance();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка перевода');
    }
  };

  // Получаем количество непрочитанных сообщений
  useEffect(() => {
    const fetchUnread = async () => {
      try {
        const res = await api.get('/tickets/unread-count');
        setUnreadCount(res.data.unread_count || 0);
      } catch (error) {
        console.error('Error fetching unread count:', error);
      }
    };
    
    fetchUnread();
    // Обновляем каждые 30 секунд
    const interval = setInterval(fetchUnread, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const getNavItems = () => {
    switch (user?.role) {
      case 'trader':
        return [
          { path: '/trader/workspace', label: 'Рабочий стол', icon: Briefcase },
          { path: '/trader/payment-details', label: 'Реквизиты', icon: CreditCard },
          { path: '/trader/finances', label: 'Финансы', icon: Wallet },
          { path: '/trader/analytics', label: 'Аналитика', icon: BarChart3 },
          { path: '/referrals', label: 'Рефералы', icon: Gift },
          { path: '/support', label: 'Поддержка', icon: MessageCircle },
        ];
      case 'merchant':
        return [
          { path: '/merchant/orders', label: 'Заказы', icon: FileText },
          { path: '/merchant/finances', label: 'Финансы', icon: Wallet },
          { path: '/merchant/analytics', label: 'Аналитика', icon: BarChart3 },
          { path: '/merchant/stats', label: 'API Статистика', icon: Activity },
          { path: '/merchant/api', label: 'API', icon: Settings },
          { path: '/referrals', label: 'Рефералы', icon: Gift },
          { path: '/support', label: 'Поддержка', icon: MessageCircle },
        ];
      case 'admin':
        return [
          { path: '/admin', label: 'Дашборд', icon: LayoutDashboard },
          { path: '/admin/users', label: 'Пользователи', icon: Users },
          { path: '/admin/staff', label: 'Персонал', icon: Shield },
          { path: '/admin/orders', label: 'Ордера', icon: FileText },
          { path: '/admin/disputes', label: 'Споры', icon: AlertTriangle },
          { path: '/admin/tickets', label: 'Тикеты', icon: MessageCircle },
          { path: '/admin/finances', label: 'Финансы', icon: PiggyBank },
          { path: '/admin/accounting', label: 'Аналитика', icon: BarChart2 },
          { path: '/admin/maintenance', label: 'Обслуживание', icon: Wrench },
          { path: '/admin/settings', label: 'Настройки', icon: Settings },
        ];
      case 'support':
        return [
          { path: '/admin', label: 'Дашборд', icon: LayoutDashboard },
          { path: '/admin/users', label: 'Пользователи', icon: Users },
          { path: '/admin/orders', label: 'Ордера', icon: FileText },
          { path: '/admin/disputes', label: 'Споры', icon: AlertTriangle },
          { path: '/admin/tickets', label: 'Тикеты', icon: MessageCircle },
        ];
      default:
        return [];
    }
  };

  const navItems = getNavItems();

  const getRoleLabel = () => {
    const labels = {
      trader: 'Трейдер',
      merchant: 'Мерчант',
      admin: 'Администратор',
      support: 'Саппорт',
    };
    return labels[user?.role] || user?.role;
  };

  return (
    <div className="min-h-screen bg-[#09090B]">
      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-[#09090B]/95 backdrop-blur-xl border-b border-zinc-800">
        <div className="px-4 lg:px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link to={`/${user?.role}`} className="flex items-center gap-2">
              <div className="w-9 h-9 rounded-lg bg-emerald-500 flex items-center justify-center">
                <Coins className="w-5 h-5 text-white" />
              </div>
              <span className="font-bold text-lg font-['Chivo'] hidden sm:block">BITARBITR</span>
            </Link>
            
            {/* Desktop Navigation */}
            <nav className="hidden lg:flex items-center gap-1 ml-8">
              {navItems.map((item) => {
                const isTicketsOrSupport = item.path === '/admin/tickets' || item.path === '/support';
                const showBadge = isTicketsOrSupport && unreadCount > 0;
                
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors relative ${
                      location.pathname === item.path
                        ? 'bg-emerald-500/10 text-emerald-400'
                        : 'text-zinc-400 hover:text-white hover:bg-zinc-800'
                    }`}
                  >
                    <div className="relative">
                      <item.icon className="w-4 h-4" />
                      {showBadge && (
                        <span className="absolute -top-2 -right-2 w-4 h-4 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
                          {unreadCount > 9 ? '9+' : unreadCount}
                        </span>
                      )}
                    </div>
                    <span className="text-sm font-medium">{item.label}</span>
                  </Link>
                );
              })}
            </nav>
          </div>

          <div className="flex items-center gap-2">
            {/* Trader Balance Display - Compact */}
            {user?.role === 'trader' && traderBalance && (
              <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 bg-zinc-800/50 rounded-lg border border-zinc-700/50 text-xs">
                <div className="flex items-center gap-1">
                  <Wallet className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-zinc-500">Бал:</span>
                  <span className="font-['JetBrains_Mono'] text-emerald-400 font-medium">
                    {(traderBalance.available || 0).toFixed(2)}
                  </span>
                </div>
                <div className="w-px h-5 bg-zinc-700" />
                <div className="flex items-center gap-1">
                  <Zap className="w-3.5 h-3.5 text-orange-400" />
                  <span className="text-zinc-500">Лок:</span>
                  <span className="font-['JetBrains_Mono'] text-orange-400 font-medium">
                    {(traderBalance.locked || 0).toFixed(2)}
                  </span>
                </div>
                <div className="w-px h-5 bg-zinc-700" />
                <div className="flex items-center gap-1">
                  <PiggyBank className="w-3.5 h-3.5 text-blue-400" />
                  <span className="text-zinc-500">Зар:</span>
                  <span className="font-['JetBrains_Mono'] text-blue-400 font-medium">
                    {(traderBalance.earned || 0).toFixed(2)}
                  </span>
                  {(traderBalance.earned || 0) > 0 && (
                    <button
                      onClick={handleWithdrawEarnings}
                      className="ml-1 px-1.5 py-0.5 text-[9px] bg-blue-500/20 text-blue-400 rounded hover:bg-blue-500/30 transition-colors whitespace-nowrap"
                      title="Зачислить на баланс"
                    >
                      →Бал
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* Merchant Balance Display - Simple */}
            {user?.role === 'merchant' && merchantBalance && (
              <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-zinc-800/50 rounded-lg border border-zinc-700/50 text-xs">
                <Wallet className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-zinc-500">Баланс:</span>
                <span className="font-['JetBrains_Mono'] text-emerald-400 font-medium">
                  {(merchantBalance.available || 0).toFixed(2)} USDT
                </span>
              </div>
            )}

            {/* Mobile Balance Badge - visible only on mobile */}
            {user?.role === 'trader' && traderBalance && (
              <div className="flex sm:hidden items-center gap-1.5 px-2 py-1 bg-zinc-800/50 rounded-lg border border-zinc-700/50 text-[10px]">
                <span className="text-emerald-400 font-medium">{(traderBalance.available || 0).toFixed(0)}</span>
                <span className="text-zinc-600">|</span>
                <span className="text-orange-400 font-medium">{(traderBalance.locked || 0).toFixed(0)}</span>
                <span className="text-zinc-600">|</span>
                <span className="text-blue-400 font-medium">{(traderBalance.earned || 0).toFixed(0)}</span>
              </div>
            )}
            {user?.role === 'merchant' && merchantBalance && (
              <div className="flex sm:hidden items-center gap-1 px-2 py-1 bg-emerald-500/10 rounded-lg text-xs">
                <Wallet className="w-3 h-3 text-emerald-400" />
                <span className="font-['JetBrains_Mono'] text-emerald-400 font-medium">
                  {(merchantBalance.available || 0).toFixed(0)}
                </span>
              </div>
            )}
            
            {/* USDT Rate Display */}
            {usdtRate && (
              <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-zinc-800/50 rounded-lg border border-zinc-700/50">
                <Coins className="w-4 h-4 text-emerald-400" />
                <span className="font-['JetBrains_Mono'] text-sm text-zinc-300">
                  USDT: {usdtRate.toLocaleString('ru-RU')} ₽
                </span>
              </div>
            )}
            
            {/* Admin Notifications */}
            {(user?.role === 'admin' || user?.role === 'support') && (
              <AdminNotifications />
            )}
            
            {/* User Notifications (for traders and merchants) */}
            {(user?.role === 'trader' || user?.role === 'merchant') && (
              <UserNotifications />
            )}
            
            {/* User Menu */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="gap-2 text-zinc-300 hover:text-white" data-testid="user-menu-btn">
                  <div className="w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center">
                    {user?.email?.[0]?.toUpperCase()}
                  </div>
                  <span className="hidden sm:block max-w-[150px] truncate">{user?.email}</span>
                  <ChevronDown className="w-4 h-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56 bg-zinc-900 border-zinc-800">
                <div className="px-3 py-2">
                  <div className="text-sm font-medium">{user?.nickname || user?.login}</div>
                  <div className="text-xs text-zinc-500">{getRoleLabel()}</div>
                </div>
                <DropdownMenuSeparator className="bg-zinc-800" />
                <DropdownMenuItem 
                  onClick={() => navigate('/settings')}
                  className="cursor-pointer"
                >
                  <Settings className="w-4 h-4 mr-2" />
                  Настройки
                </DropdownMenuItem>
                <DropdownMenuSeparator className="bg-zinc-800" />
                <DropdownMenuItem 
                  onClick={handleLogout}
                  className="text-red-400 focus:text-red-400 focus:bg-red-500/10 cursor-pointer"
                  data-testid="logout-btn"
                >
                  <LogOut className="w-4 h-4 mr-2" />
                  Выйти
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            {/* Mobile Menu Toggle */}
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </Button>
          </div>
        </div>

        {/* Mobile Navigation */}
        {mobileMenuOpen && (
          <nav className="lg:hidden border-t border-zinc-800 p-4">
            <div className="flex flex-col gap-1">
              {navItems.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                    location.pathname === item.path
                      ? 'bg-emerald-500/10 text-emerald-400'
                      : 'text-zinc-400 hover:text-white hover:bg-zinc-800'
                  }`}
                >
                  <item.icon className="w-5 h-5" />
                  <span className="font-medium">{item.label}</span>
                </Link>
              ))}
            </div>
          </nav>
        )}
      </header>

      {/* Main Content */}
      <main className="pt-16 min-h-screen">
        <div className="p-4 lg:p-6">
          {children}
        </div>
      </main>

      {/* Floating Install App Button - Bottom Right */}
      {!isInstalled && (
        <button
          onClick={async () => {
            // Сразу пробуем установить через нативный промпт
            setInstalling(true);
            const result = await installApp();
            setInstalling(false);
            
            // Если нативный промпт сработал - ничего не делаем
            if (result === true) {
              return;
            }
            
            // Если iOS или нет нативного промпта - показываем модал
            setShowInstallModal(true);
          }}
          disabled={installing}
          className="fixed bottom-6 right-6 w-14 h-14 rounded-full bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 text-white shadow-lg shadow-emerald-500/30 flex items-center justify-center transition-all hover:scale-110 z-50"
          title="Скачать приложение"
        >
          {installing ? (
            <div className="animate-spin w-6 h-6 border-2 border-white border-t-transparent rounded-full" />
          ) : (
            <Download className="w-6 h-6" />
          )}
        </button>
      )}

      {/* Simple Install Modal - shows only when native prompt unavailable */}
      {showInstallModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-[100] p-4">
          <div className="bg-zinc-900 border border-zinc-700 rounded-2xl max-w-sm w-full p-6 shadow-2xl">
            <div className="text-center mb-6">
              <div className="w-16 h-16 rounded-2xl bg-emerald-500/20 flex items-center justify-center mx-auto mb-4">
                <Download className="w-8 h-8 text-emerald-400" />
              </div>
              <h3 className="text-xl font-bold text-white mb-2">Установить приложение</h3>
              <p className="text-sm text-zinc-400">
                {isIOS 
                  ? 'Нажмите "Поделиться" (□↑) → "На экран Домой"'
                  : 'Откройте меню браузера (⋮) → "Установить приложение"'}
              </p>
            </div>

            <div className="flex gap-3">
              <Button
                onClick={() => setShowInstallModal(false)}
                variant="outline"
                className="flex-1 border-zinc-700 hover:bg-zinc-800"
              >
                Отмена
              </Button>
              <Button
                onClick={() => setShowInstallModal(false)}
                className="flex-1 bg-emerald-500 hover:bg-emerald-600"
              >
                Понятно
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DashboardLayout;
