import React, { useState, useEffect } from 'react';
import DashboardLayout from '@/components/DashboardLayout';
import { api } from '@/lib/auth';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import {
  Shield, Key, Smartphone, Lock, Eye, EyeOff, Copy, Check, X, MessageCircle
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";

const AccountSettings = () => {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  
  // Password change
  const [passwordDialog, setPasswordDialog] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  
  // 2FA setup
  const [twoFADialog, setTwoFADialog] = useState(false);
  const [twoFAStep, setTwoFAStep] = useState(1);
  const [twoFAPassword, setTwoFAPassword] = useState('');
  const [twoFASecret, setTwoFASecret] = useState('');
  const [twoFAQRCode, setTwoFAQRCode] = useState('');
  const [twoFACode, setTwoFACode] = useState('');
  
  // 2FA disable
  const [disableDialog, setDisableDialog] = useState(false);
  const [disablePassword, setDisablePassword] = useState('');
  const [disableCode, setDisableCode] = useState('');
  
  // Telegram
  const [telegramDialog, setTelegramDialog] = useState(false);
  const [telegramId, setTelegramId] = useState('');
  
  const [processing, setProcessing] = useState(false);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const res = await api.get('/account/settings');
      setSettings(res.data);
    } catch (error) {
      toast.error('Ошибка загрузки настроек');
    } finally {
      setLoading(false);
    }
  };

  const handleChangePassword = async () => {
    if (newPassword !== confirmPassword) {
      toast.error('Пароли не совпадают');
      return;
    }
    if (newPassword.length < 6) {
      toast.error('Пароль должен быть не менее 6 символов');
      return;
    }
    
    setProcessing(true);
    try {
      await api.post('/account/change-password', {
        current_password: currentPassword,
        new_password: newPassword
      });
      toast.success('Пароль успешно изменён');
      setPasswordDialog(false);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка смены пароля');
    } finally {
      setProcessing(false);
    }
  };

  const handleSetup2FA = async () => {
    setProcessing(true);
    try {
      const res = await api.post('/auth/2fa/setup', {
        password: twoFAPassword
      });
      setTwoFASecret(res.data.secret);
      setTwoFAQRCode(res.data.qr_code);
      setTwoFAStep(2);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка настройки 2FA');
    } finally {
      setProcessing(false);
    }
  };

  const handleVerify2FA = async () => {
    if (twoFACode.length !== 6) {
      toast.error('Введите 6-значный код');
      return;
    }
    
    setProcessing(true);
    try {
      await api.post('/auth/2fa/verify-setup', {
        code: twoFACode
      });
      toast.success('2FA успешно активирована!');
      setTwoFADialog(false);
      setTwoFAStep(1);
      setTwoFAPassword('');
      setTwoFACode('');
      fetchSettings();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Неверный код');
    } finally {
      setProcessing(false);
    }
  };

  const handleDisable2FA = async () => {
    setProcessing(true);
    try {
      await api.post('/auth/2fa/disable', {
        password: disablePassword,
        code: disableCode
      });
      toast.success('2FA отключена');
      setDisableDialog(false);
      setDisablePassword('');
      setDisableCode('');
      fetchSettings();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка отключения 2FA');
    } finally {
      setProcessing(false);
    }
  };

  const handleLinkTelegram = async () => {
    if (!telegramId || !/^\d+$/.test(telegramId)) {
      toast.error('Введите корректный Telegram ID (только цифры)');
      return;
    }
    
    setProcessing(true);
    try {
      await api.post('/auth/link-telegram', {
        telegram_id: parseInt(telegramId)
      });
      toast.success('Telegram успешно привязан!');
      setTelegramDialog(false);
      setTelegramId('');
      fetchSettings();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка привязки Telegram');
    } finally {
      setProcessing(false);
    }
  };

  const handleUnlinkTelegram = async () => {
    setProcessing(true);
    try {
      await api.post('/auth/link-telegram', {
        telegram_id: 0  // Обнуляем ID для отвязки
      });
      toast.success('Telegram отвязан');
      fetchSettings();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка отвязки Telegram');
    } finally {
      setProcessing(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('Скопировано');
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-[60vh]">
          <div className="animate-spin w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full" />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="max-w-3xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold font-['Chivo']">Настройки аккаунта</h1>
          <p className="text-zinc-400 text-sm">Управление безопасностью и профилем</p>
        </div>

        {/* Account Info */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-6">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Shield className="w-5 h-5 text-blue-400" />
              Информация об аккаунте
            </h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between py-2 border-b border-zinc-800">
                <span className="text-zinc-400">Логин</span>
                <span className="font-medium">@{settings?.login}</span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-zinc-800">
                <span className="text-zinc-400">Никнейм</span>
                <span className="font-medium">{settings?.nickname}</span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-zinc-800">
                <span className="text-zinc-400">Роль</span>
                <span className="px-2 py-1 bg-zinc-800 rounded text-sm font-medium">
                  {settings?.role}
                </span>
              </div>
              <div className="flex items-center justify-between py-2">
                <span className="text-zinc-400">Дата регистрации</span>
                <span className="text-sm">{new Date(settings?.created_at).toLocaleDateString('ru-RU')}</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Password */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-orange-500/10 flex items-center justify-center">
                  <Key className="w-5 h-5 text-orange-400" />
                </div>
                <div>
                  <h3 className="font-semibold">Пароль</h3>
                  <p className="text-sm text-zinc-400">Изменить пароль аккаунта</p>
                </div>
              </div>
              <Button 
                variant="outline" 
                className="border-zinc-700"
                onClick={() => setPasswordDialog(true)}
              >
                <Lock className="w-4 h-4 mr-2" />
                Изменить
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* 2FA */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                  settings?.two_factor_enabled ? 'bg-emerald-500/10' : 'bg-zinc-800'
                }`}>
                  <Smartphone className={`w-5 h-5 ${
                    settings?.two_factor_enabled ? 'text-emerald-400' : 'text-zinc-400'
                  }`} />
                </div>
                <div>
                  <h3 className="font-semibold">Двухфакторная аутентификация</h3>
                  <p className="text-sm text-zinc-400">
                    {settings?.two_factor_enabled 
                      ? 'Защита включена (Google Authenticator)' 
                      : 'Дополнительная защита аккаунта'
                    }
                  </p>
                </div>
              </div>
              {settings?.two_factor_enabled ? (
                <Button 
                  variant="outline" 
                  className="border-red-500/50 text-red-400 hover:bg-red-500/10"
                  onClick={() => setDisableDialog(true)}
                >
                  <X className="w-4 h-4 mr-2" />
                  Отключить
                </Button>
              ) : (
                <Button 
                  className="bg-emerald-500 hover:bg-emerald-600"
                  onClick={() => setTwoFADialog(true)}
                >
                  <Check className="w-4 h-4 mr-2" />
                  Включить
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Telegram Notifications */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                  settings?.telegram_id ? 'bg-blue-500/10' : 'bg-zinc-800'
                }`}>
                  <MessageCircle className={`w-5 h-5 ${
                    settings?.telegram_id ? 'text-blue-400' : 'text-zinc-400'
                  }`} />
                </div>
                <div>
                  <h3 className="font-semibold">Telegram уведомления</h3>
                  <p className="text-sm text-zinc-400">
                    {settings?.telegram_id 
                      ? `Привязан (ID: ${settings.telegram_id})` 
                      : 'Получайте уведомления о депозитах и выводах'
                    }
                  </p>
                </div>
              </div>
              {settings?.telegram_id ? (
                <div className="flex gap-2">
                  <Button 
                    variant="outline" 
                    className="border-red-500/50 text-red-400 hover:bg-red-500/10"
                    onClick={handleUnlinkTelegram}
                    disabled={processing}
                  >
                    <X className="w-4 h-4 mr-2" />
                    Отвязать
                  </Button>
                </div>
              ) : (
                <Button 
                  className="bg-blue-500 hover:bg-blue-600"
                  onClick={() => setTelegramDialog(true)}
                >
                  <MessageCircle className="w-4 h-4 mr-2" />
                  Привязать
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Password Change Dialog */}
        <Dialog open={passwordDialog} onOpenChange={setPasswordDialog}>
          <DialogContent className="bg-zinc-900 border-zinc-800">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Key className="w-5 h-5 text-orange-400" />
                Изменить пароль
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Текущий пароль</Label>
                <div className="relative">
                  <Input
                    type={showPassword ? 'text' : 'password'}
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    className="bg-zinc-950 border-zinc-800 pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <div className="space-y-2">
                <Label>Новый пароль</Label>
                <Input
                  type={showPassword ? 'text' : 'password'}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="bg-zinc-950 border-zinc-800"
                />
              </div>
              <div className="space-y-2">
                <Label>Подтвердите пароль</Label>
                <Input
                  type={showPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="bg-zinc-950 border-zinc-800"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setPasswordDialog(false)} className="border-zinc-700">
                Отмена
              </Button>
              <Button 
                onClick={handleChangePassword}
                disabled={processing || !currentPassword || !newPassword}
                className="bg-orange-500 hover:bg-orange-600"
              >
                {processing ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : 'Изменить'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* 2FA Setup Dialog */}
        <Dialog open={twoFADialog} onOpenChange={setTwoFADialog}>
          <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Smartphone className="w-5 h-5 text-emerald-400" />
                Настройка 2FA
              </DialogTitle>
            </DialogHeader>
            
            {twoFAStep === 1 && (
              <div className="space-y-4">
                <p className="text-sm text-zinc-400">
                  Введите текущий пароль для начала настройки двухфакторной аутентификации.
                </p>
                <div className="space-y-2">
                  <Label>Пароль</Label>
                  <Input
                    type="password"
                    value={twoFAPassword}
                    onChange={(e) => setTwoFAPassword(e.target.value)}
                    className="bg-zinc-950 border-zinc-800"
                  />
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setTwoFADialog(false)} className="border-zinc-700">
                    Отмена
                  </Button>
                  <Button 
                    onClick={handleSetup2FA}
                    disabled={processing || !twoFAPassword}
                    className="bg-emerald-500 hover:bg-emerald-600"
                  >
                    {processing ? (
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    ) : 'Продолжить'}
                  </Button>
                </DialogFooter>
              </div>
            )}
            
            {twoFAStep === 2 && (
              <div className="space-y-4">
                <div className="text-center">
                  <p className="text-sm text-zinc-400 mb-4">
                    Отсканируйте QR-код в приложении Google Authenticator:
                  </p>
                  {twoFAQRCode && (
                    <img src={twoFAQRCode} alt="QR Code" className="mx-auto rounded-lg" />
                  )}
                </div>
                
                <div className="bg-zinc-800 rounded-lg p-3">
                  <div className="text-xs text-zinc-500 mb-1">Или введите код вручную:</div>
                  <div className="flex items-center gap-2">
                    <code className="font-['JetBrains_Mono'] text-sm flex-1 break-all">{twoFASecret}</code>
                    <button onClick={() => copyToClipboard(twoFASecret)}>
                      <Copy className="w-4 h-4 text-zinc-400 hover:text-white" />
                    </button>
                  </div>
                </div>
                
                <div className="space-y-2">
                  <Label>Код из приложения</Label>
                  <Input
                    type="text"
                    value={twoFACode}
                    onChange={(e) => setTwoFACode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    placeholder="000000"
                    className="bg-zinc-950 border-zinc-800 text-center font-['JetBrains_Mono'] text-2xl tracking-widest"
                    maxLength={6}
                  />
                </div>
                
                <DialogFooter>
                  <Button variant="outline" onClick={() => {setTwoFADialog(false); setTwoFAStep(1);}} className="border-zinc-700">
                    Отмена
                  </Button>
                  <Button 
                    onClick={handleVerify2FA}
                    disabled={processing || twoFACode.length !== 6}
                    className="bg-emerald-500 hover:bg-emerald-600"
                  >
                    {processing ? (
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    ) : 'Активировать'}
                  </Button>
                </DialogFooter>
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* Disable 2FA Dialog */}
        <Dialog open={disableDialog} onOpenChange={setDisableDialog}>
          <DialogContent className="bg-zinc-900 border-zinc-800">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-red-400">
                <X className="w-5 h-5" />
                Отключить 2FA
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <p className="text-sm text-zinc-400">
                Для отключения двухфакторной аутентификации введите пароль и код из приложения.
              </p>
              <div className="space-y-2">
                <Label>Пароль</Label>
                <Input
                  type="password"
                  value={disablePassword}
                  onChange={(e) => setDisablePassword(e.target.value)}
                  className="bg-zinc-950 border-zinc-800"
                />
              </div>
              <div className="space-y-2">
                <Label>Код 2FA</Label>
                <Input
                  type="text"
                  value={disableCode}
                  onChange={(e) => setDisableCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="000000"
                  className="bg-zinc-950 border-zinc-800 text-center font-['JetBrains_Mono'] text-xl"
                  maxLength={6}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDisableDialog(false)} className="border-zinc-700">
                Отмена
              </Button>
              <Button 
                onClick={handleDisable2FA}
                disabled={processing || !disablePassword || disableCode.length !== 6}
                className="bg-red-500 hover:bg-red-600"
              >
                {processing ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : 'Отключить'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Telegram Link Dialog */}
        <Dialog open={telegramDialog} onOpenChange={setTelegramDialog}>
          <DialogContent className="bg-zinc-900 border-zinc-800">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <MessageCircle className="w-5 h-5 text-blue-400" />
                Привязать Telegram
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4">
                <h4 className="font-medium mb-2">Как узнать свой Telegram ID:</h4>
                <ol className="text-sm text-zinc-400 space-y-2">
                  <li>1. Откройте Telegram и найдите бота <span className="text-blue-400">@userinfobot</span></li>
                  <li>2. Напишите ему любое сообщение</li>
                  <li>3. Бот ответит вам информацией, включая ваш ID</li>
                  <li>4. Скопируйте число из поля <span className="text-blue-400">Id</span></li>
                </ol>
              </div>
              
              <div className="space-y-2">
                <Label>Ваш Telegram ID</Label>
                <Input
                  type="text"
                  value={telegramId}
                  onChange={(e) => setTelegramId(e.target.value.replace(/\D/g, ''))}
                  placeholder="Например: 123456789"
                  className="bg-zinc-950 border-zinc-800 font-['JetBrains_Mono']"
                />
              </div>
              
              <p className="text-xs text-zinc-500">
                После привязки вы будете получать уведомления о депозитах, выводах и других важных событиях.
              </p>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setTelegramDialog(false)} className="border-zinc-700">
                Отмена
              </Button>
              <Button 
                onClick={handleLinkTelegram}
                disabled={processing || !telegramId}
                className="bg-blue-500 hover:bg-blue-600"
              >
                {processing ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : 'Привязать'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </DashboardLayout>
  );
};

export default AccountSettings;
