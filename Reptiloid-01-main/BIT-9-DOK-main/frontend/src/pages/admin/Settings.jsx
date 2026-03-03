import React, { useState, useEffect, useCallback } from 'react';
import DashboardLayout from '@/components/DashboardLayout';
import SecurityVerification from '@/components/SecurityVerification';
import { api, formatUSDT } from '@/lib/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { toast } from 'sonner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Settings, Wallet, Key, Shield, Play, Pause, RefreshCw, Send,
  Eye, EyeOff, Copy, Zap, Save, Bot, Bell, Lock, Globe, Sliders,
  Image, Link, Megaphone, Users, Download, Database
} from 'lucide-react';

const copyToClipboard = async (text, label = 'Текст') => {
  try {
    await navigator.clipboard.writeText(text);
    toast.success(`${label} скопирован`);
  } catch (err) {
    toast.error('Не удалось скопировать');
  }
};

// Компонент кнопки синхронизации
const SyncWalletsButton = () => {
  const [syncing, setSyncing] = useState(false);
  
  const handleSync = async () => {
    setSyncing(true);
    try {
      const res = await api.post('/admin/sync-wallets');
      toast.success(`Синхронизировано кошельков: ${res.data.synced_count}`);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка синхронизации');
    } finally {
      setSyncing(false);
    }
  };
  
  return (
    <Button onClick={handleSync} disabled={syncing} className="bg-orange-600 hover:bg-orange-700">
      {syncing ? (
        <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
      ) : (
        <RefreshCw className="w-4 h-4 mr-2" />
      )}
      {syncing ? 'Синхронизация...' : 'Синхронизировать балансы'}
    </Button>
  );
};

// Компонент кнопки экспорта БД
const BackupDatabaseButton = () => {
  const [downloading, setDownloading] = useState(false);
  
  const handleBackup = async () => {
    setDownloading(true);
    try {
      const response = await api.get('/admin/backup-database', {
        responseType: 'blob'
      });
      
      // Создаём ссылку для скачивания
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      const filename = `bitarbitr_backup_${new Date().toISOString().slice(0,19).replace(/[-:T]/g, '')}.json`;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      toast.success('База данных экспортирована');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка экспорта');
    } finally {
      setDownloading(false);
    }
  };
  
  return (
    <Button onClick={handleBackup} disabled={downloading} className="bg-blue-600 hover:bg-blue-700">
      {downloading ? (
        <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
      ) : (
        <Download className="w-4 h-4 mr-2" />
      )}
      {downloading ? 'Экспорт...' : 'Скачать бэкап базы'}
    </Button>
  );
};

const AdminSettings = () => {
  const [activeTab, setActiveTab] = useState('wallet');
  const [loading, setLoading] = useState(true);
  
  // Security verification for wallet settings
  const [isWalletVerified, setIsWalletVerified] = useState(false);
  const [showSecurityModal, setShowSecurityModal] = useState(false);
  const [verificationToken, setVerificationToken] = useState(null);
  
  // Wallet state
  const [walletAddress, setWalletAddress] = useState('');
  const [seedPhrase, setSeedPhrase] = useState('');
  const [usdtContract, setUsdtContract] = useState('EQDcBkGHmC4pTf34x3Gm05XvepO5w60DNxZ-XT4I6-UGG5L5');
  const [toncenterApiKey, setToncenterApiKey] = useState('');
  const [encryptionPassword, setEncryptionPassword] = useState('');
  const [showSeed, setShowSeed] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [savingWallet, setSavingWallet] = useState(false);
  const [walletConfig, setWalletConfig] = useState(null);
  const [walletStatus, setWalletStatus] = useState({ is_running: false, balance: 0 });
  
  // Testing
  const [testAddress, setTestAddress] = useState('');
  const [testAmount, setTestAmount] = useState(0.001);
  const [testing, setTesting] = useState(false);
  
  // Telegram settings
  const [telegramBotToken, setTelegramBotToken] = useState('');
  const [telegramEnabled, setTelegramEnabled] = useState(false);
  const [savingTelegram, setSavingTelegram] = useState(false);
  
  // Broadcast
  const [broadcastTarget, setBroadcastTarget] = useState('all');
  const [broadcastMessage, setBroadcastMessage] = useState('');
  const [sendingBroadcast, setSendingBroadcast] = useState(false);
  
  // Platform settings
  const [platformSettings, setPlatformSettings] = useState({
    platform_ton_address: '',
    withdrawal_fee_percent: 0,
    network_fee: 0,
    min_deposit: 0,
    min_withdrawal: 0,
    order_expiration_minutes: 30,
    cancel_delay_minutes: 30,
    site_name: 'BITARBITR',
    support_email: ''
  });
  const [savingPlatform, setSavingPlatform] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [statusRes, configRes, usdtSettingsRes, telegramRes] = await Promise.all([
        api.get('/admin/auto-withdraw/status'),
        api.get('/admin/auto-withdraw/config'),
        api.get('/admin/usdt/settings'),
        api.get('/admin/telegram/settings').catch(() => ({ data: {} }))
      ]);
      
      setWalletStatus(statusRes.data);
      setWalletConfig(configRes.data);
      
      if (configRes.data.configured) {
        setWalletAddress(configRes.data.wallet_address || '');
        setUsdtContract(configRes.data.usdt_contract || '');
      }
      
      if (usdtSettingsRes.data.settings) {
        setPlatformSettings(prev => ({
          ...prev,
          ...usdtSettingsRes.data.settings
        }));
      }
      
      if (telegramRes.data) {
        setTelegramEnabled(telegramRes.data.enabled || false);
        setTelegramBotToken(telegramRes.data.bot_token ? '********' : '');
      }
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Broadcast handler
  const handleSendBroadcast = async () => {
    if (!broadcastMessage.trim()) {
      toast.error('Введите сообщение');
      return;
    }
    
    setSendingBroadcast(true);
    try {
      const res = await api.post('/admin/telegram/broadcast', {
        message: broadcastMessage,
        target: broadcastTarget
      });
      toast.success(res.data.message);
      setBroadcastMessage('');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка отправки');
    } finally {
      setSendingBroadcast(false);
    }
  };

  // Wallet handlers
  const handleSaveWallet = async (e) => {
    e.preventDefault();
    if (!walletAddress || !seedPhrase || !toncenterApiKey || !encryptionPassword) {
      toast.error('Заполните все обязательные поля');
      return;
    }
    
    setSavingWallet(true);
    try {
      await api.post('/admin/auto-withdraw/setup', {
        wallet_address: walletAddress,
        seed_phrase: seedPhrase,
        usdt_contract: usdtContract,
        toncenter_api_key: toncenterApiKey,
        encryption_password: encryptionPassword
      });
      toast.success('Кошелёк настроен');
      setSeedPhrase('');
      setEncryptionPassword('');
      setToncenterApiKey('');
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка');
    } finally {
      setSavingWallet(false);
    }
  };

  const toggleAutoWithdraw = async () => {
    try {
      if (walletStatus.is_running) {
        await api.post('/admin/auto-withdraw/stop');
        toast.success('Автовывод остановлен');
      } else {
        await api.post('/admin/auto-withdraw/start');
        toast.success('Автовывод запущен');
      }
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка');
    }
  };

  const testWithdraw = async () => {
    if (!testAddress || testAmount <= 0) {
      toast.error('Укажите адрес и сумму');
      return;
    }
    
    setTesting(true);
    try {
      const res = await api.post('/admin/auto-withdraw/test', {
        to_address: testAddress,
        amount: testAmount
      });
      toast.success(res.data.message || 'Тест выполнен');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка');
    } finally {
      setTesting(false);
    }
  };

  // Telegram handlers
  const saveTelegramSettings = async () => {
    setSavingTelegram(true);
    try {
      await api.put('/admin/telegram/settings', {
        bot_token: telegramBotToken !== '********' ? telegramBotToken : undefined,
        enabled: telegramEnabled
      });
      toast.success('Настройки Telegram сохранены');
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка');
    } finally {
      setSavingTelegram(false);
    }
  };

  // Platform settings handlers  
  const savePlatformSettings = async () => {
    setSavingPlatform(true);
    try {
      await api.put('/admin/usdt/settings', platformSettings);
      toast.success('Настройки платформы сохранены');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка');
    } finally {
      setSavingPlatform(false);
    }
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-8 h-8 animate-spin text-emerald-500" />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6" data-testid="admin-settings">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold font-['Chivo']">Настройки</h1>
            <p className="text-zinc-400 mt-1">Кошелёк, Telegram, параметры платформы</p>
          </div>
          <Button onClick={fetchData} variant="outline" size="sm">
            <RefreshCw className="w-4 h-4 mr-2" />
            Обновить
          </Button>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="bg-zinc-800 border border-zinc-700 flex-wrap h-auto gap-1 p-1">
            <TabsTrigger value="wallet" className="data-[state=active]:bg-emerald-600">
              <Wallet className="w-4 h-4 mr-2" />
              Кошелёк
            </TabsTrigger>
            <TabsTrigger value="telegram" className="data-[state=active]:bg-emerald-600">
              <Bot className="w-4 h-4 mr-2" />
              Telegram
            </TabsTrigger>
            <TabsTrigger value="broadcast" className="data-[state=active]:bg-emerald-600">
              <Megaphone className="w-4 h-4 mr-2" />
              Рассылка
            </TabsTrigger>
            <TabsTrigger value="platform" className="data-[state=active]:bg-emerald-600">
              <Sliders className="w-4 h-4 mr-2" />
              Платформа
            </TabsTrigger>
          </TabsList>

          {/* Wallet Tab - PROTECTED */}
          <TabsContent value="wallet" className="space-y-6 mt-6">
            {!isWalletVerified ? (
              // Security verification required
              <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader className="text-center">
                  <div className="w-16 h-16 rounded-full bg-emerald-500/10 flex items-center justify-center mx-auto mb-4">
                    <Lock className="w-8 h-8 text-emerald-400" />
                  </div>
                  <CardTitle className="text-xl">Защищённый раздел</CardTitle>
                  <CardDescription>
                    Настройки кошелька и seed-фразы требуют подтверждения личности
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4 max-w-md mx-auto">
                  <div className="bg-orange-500/10 border border-orange-500/20 rounded-lg p-4">
                    <div className="flex items-start gap-3">
                      <Shield className="w-5 h-5 text-orange-400 flex-shrink-0 mt-0.5" />
                      <div className="text-sm text-orange-300">
                        Для доступа к настройкам кошелька необходимо подтвердить пароль
                        {' '}и код 2FA (если включён). Это защищает приватные ключи.
                      </div>
                    </div>
                  </div>
                  <Button 
                    onClick={() => setShowSecurityModal(true)}
                    className="w-full bg-emerald-500 hover:bg-emerald-600"
                  >
                    <Shield className="w-4 h-4 mr-2" />
                    Подтвердить личность
                  </Button>
                </CardContent>
              </Card>
            ) : (
              <>
                {/* Verified Badge */}
                <div className="flex items-center gap-2 px-4 py-2 bg-emerald-500/10 border border-emerald-500/30 rounded-lg w-fit">
                  <Shield className="w-4 h-4 text-emerald-400" />
                  <span className="text-sm text-emerald-400">Доступ подтверждён</span>
                </div>

                {/* Инструкция по настройке */}
                <Card className="bg-gradient-to-r from-blue-900/30 to-emerald-900/30 border-blue-700/50">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-blue-400">
                      <Shield className="w-5 h-5" />
                      📋 Инструкция по настройке горячего кошелька
                    </CardTitle>
                    <CardDescription className="text-zinc-300">
                      Этот кошелёк используется для автоматических депозитов И выводов USDT
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4 text-sm">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      {/* Левая колонка - Что нужно */}
                      <div className="space-y-4">
                        <h4 className="font-bold text-emerald-400 border-b border-zinc-700 pb-2">Что нужно подготовить:</h4>
                    
                    <div className="space-y-3">
                      <div className="p-3 bg-zinc-800/50 rounded-lg">
                        <p className="font-medium text-white">1️⃣ TON Кошелёк (Tonkeeper)</p>
                        <ul className="mt-2 text-zinc-400 space-y-1">
                          <li>• Скачайте <span className="text-blue-400">Tonkeeper</span> на телефон</li>
                          <li>• Создайте новый кошелёк</li>
                          <li>• <span className="text-orange-400">ВАЖНО:</span> Сохраните 24 слова!</li>
                        </ul>
                        <div className="mt-3 p-2 bg-zinc-900 rounded border border-zinc-700">
                          <p className="text-xs text-zinc-500 mb-1">Где взять адрес в Tonkeeper:</p>
                          <p className="text-xs text-emerald-400">Главный экран → Нажмите на адрес сверху → Копировать</p>
                          <p className="text-xs text-zinc-500 mt-1">Адрес начинается с <span className="text-emerald-400">UQ...</span> (это нужный формат!)</p>
                          <p className="text-xs text-zinc-400 mt-1">ℹ️ Tonkeeper автоматически создаёт современный кошелёк</p>
                        </div>
                      </div>
                      
                      <div className="p-3 bg-zinc-800/50 rounded-lg">
                        <p className="font-medium text-white">2️⃣ Пополните кошелёк</p>
                        <ul className="mt-2 text-zinc-400 space-y-1">
                          <li>• <span className="text-emerald-400">TON</span> - для оплаты комиссий (мин. 0.5 TON)</li>
                          <li>• <span className="text-emerald-400">USDT</span> - для автоматических выводов</li>
                        </ul>
                      </div>
                      
                      <div className="p-3 bg-zinc-800/50 rounded-lg">
                        <p className="font-medium text-white">3️⃣ TonCenter API Key</p>
                        <ul className="mt-2 text-zinc-400 space-y-1">
                          <li>• Перейдите на <a href="https://toncenter.com" target="_blank" rel="noopener noreferrer" className="text-blue-400 underline">toncenter.com</a></li>
                          <li>• Зарегистрируйтесь → My Apps → Create</li>
                          <li>• Скопируйте API Key</li>
                        </ul>
                      </div>
                    </div>
                  </div>
                  
                  {/* Правая колонка - Как заполнить */}
                  <div className="space-y-4">
                    <h4 className="font-bold text-emerald-400 border-b border-zinc-700 pb-2">Как заполнить форму:</h4>
                    
                    <div className="space-y-3">
                      <div className="p-3 bg-zinc-800/50 rounded-lg">
                        <p className="font-medium text-white">📍 TON Адрес кошелька</p>
                        <p className="text-zinc-400 mt-1">Скопируйте из Tonkeeper (главный экран, сверху)</p>
                        <code className="text-xs bg-zinc-900 px-2 py-1 rounded text-emerald-400 block mt-1">UQDqsQMz1OsKtj4UlXJFbU4WYJghZKyugYVvWZE0WwA5liux</code>
                        <p className="text-xs text-zinc-500 mt-1">UQ... и EQ... - это один адрес в разных форматах</p>
                      </div>
                      
                      <div className="p-3 bg-zinc-800/50 rounded-lg">
                        <p className="font-medium text-white">🔐 Seed-фраза (24 слова)</p>
                        <p className="text-zinc-400 mt-1">Tonkeeper → Настройки → Резервная копия</p>
                        <code className="text-xs bg-zinc-900 px-2 py-1 rounded text-emerald-400 block mt-1">word1 word2 word3 ... word24</code>
                        <p className="text-orange-400 text-xs mt-2">⚠️ Не делитесь seed ни с кем! Храните безопасно!</p>
                      </div>
                      
                      <div className="p-3 bg-zinc-800/50 rounded-lg">
                        <p className="font-medium text-white">🔑 TonCenter API Key</p>
                        <p className="text-zinc-400 mt-1">toncenter.com → My Apps → Create → Copy Key</p>
                        <code className="text-xs bg-zinc-900 px-2 py-1 rounded text-emerald-400 block mt-1">42e807604...b2 (длинная строка)</code>
                      </div>
                      
                      <div className="p-3 bg-zinc-800/50 rounded-lg">
                        <p className="font-medium text-white">🔒 Пароль шифрования</p>
                        <p className="text-zinc-400 mt-1">Любой надёжный пароль для защиты seed в базе</p>
                      </div>
                    </div>
                  </div>
                </div>
                
                <div className="p-3 bg-emerald-900/30 border border-emerald-700/50 rounded-lg mt-4">
                  <p className="text-emerald-300 font-medium">✅ После настройки:</p>
                  <ul className="text-zinc-300 mt-2 space-y-1">
                    <li>• <strong>Депозиты</strong> - система будет мониторить входящие USDT на этот адрес</li>
                    <li>• <strong>Выводы</strong> - автоматически отправлять USDT трейдерам с этого кошелька</li>
                    <li>• Нажмите «Запустить» для активации автовывода</li>
                  </ul>
                </div>
              </CardContent>
            </Card>
            
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Setup Form */}
              <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Key className="w-5 h-5 text-emerald-400" />
                    Привязка кошелька
                  </CardTitle>
                  <CardDescription>Для автоматических депозитов и выводов USDT</CardDescription>
                </CardHeader>
                <CardContent>
                  <form onSubmit={handleSaveWallet} className="space-y-4">
                    <div>
                      <Label>TON Адрес кошелька *</Label>
                      <Input
                        value={walletAddress}
                        onChange={(e) => setWalletAddress(e.target.value)}
                        placeholder="UQ... или EQ..."
                        className="font-mono text-sm"
                      />
                    </div>
                    
                    <div>
                      <Label>Seed-фраза (24 слова) *</Label>
                      <div className="relative">
                        <Input
                          type={showSeed ? 'text' : 'password'}
                          value={seedPhrase}
                          onChange={(e) => setSeedPhrase(e.target.value)}
                          placeholder="word1 word2 word3 ..."
                          className="pr-10"
                        />
                        <button type="button" onClick={() => setShowSeed(!showSeed)} className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400">
                          {showSeed ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                      </div>
                    </div>
                    
                    <div>
                      <Label>USDT Contract</Label>
                      <Input value={usdtContract} onChange={(e) => setUsdtContract(e.target.value)} className="font-mono text-xs" />
                    </div>
                    
                    <div>
                      <Label>TonCenter API Key *</Label>
                      <Input type="password" value={toncenterApiKey} onChange={(e) => setToncenterApiKey(e.target.value)} placeholder="Получите на toncenter.com" />
                    </div>
                    
                    <div>
                      <Label>Пароль шифрования *</Label>
                      <div className="relative">
                        <Input
                          type={showPassword ? 'text' : 'password'}
                          value={encryptionPassword}
                          onChange={(e) => setEncryptionPassword(e.target.value)}
                          placeholder="Для защиты seed-фразы"
                          className="pr-10"
                        />
                        <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400">
                          {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                      </div>
                    </div>
                    
                    <Button type="submit" className="w-full" disabled={savingWallet}>
                      {savingWallet ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                      {walletConfig?.configured ? 'Обновить кошелёк' : 'Привязать кошелёк'}
                    </Button>
                  </form>
                </CardContent>
              </Card>

              {/* Status & Control */}
              <div className="space-y-6">
                <Card className="bg-zinc-900 border-zinc-800">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Zap className="w-5 h-5 text-emerald-400" />
                      Статус автовывода
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {walletConfig?.configured ? (
                      <>
                        <div className="p-4 bg-zinc-800 rounded-lg space-y-2">
                          <div className="flex justify-between text-sm">
                            <span className="text-zinc-400">Кошелёк:</span>
                            <div className="flex items-center gap-1">
                              <span className="font-mono text-xs">{walletStatus.wallet_address?.slice(0, 10)}...{walletStatus.wallet_address?.slice(-6)}</span>
                              <button onClick={() => copyToClipboard(walletStatus.wallet_address, 'Адрес')}>
                                <Copy className="w-3 h-3 text-zinc-500 hover:text-white" />
                              </button>
                            </div>
                          </div>
                          <div className="flex justify-between text-sm">
                            <span className="text-zinc-400">Баланс:</span>
                            <span className="font-mono text-emerald-400">{formatUSDT(walletStatus.balance)} USDT</span>
                          </div>
                          <div className="flex justify-between text-sm">
                            <span className="text-zinc-400">Статус:</span>
                            <span className={walletStatus.is_running ? 'text-emerald-400' : 'text-zinc-500'}>
                              {walletStatus.is_running ? '● Работает' : '○ Остановлен'}
                            </span>
                          </div>
                        </div>
                        
                        <Button onClick={toggleAutoWithdraw} className={`w-full ${walletStatus.is_running ? 'bg-red-600 hover:bg-red-700' : 'bg-emerald-600 hover:bg-emerald-700'}`}>
                          {walletStatus.is_running ? <><Pause className="w-4 h-4 mr-2" /> Остановить</> : <><Play className="w-4 h-4 mr-2" /> Запустить</>}
                        </Button>
                      </>
                    ) : (
                      <div className="text-center p-6 text-zinc-500">
                        <Shield className="w-12 h-12 mx-auto mb-2 opacity-50" />
                        <p>Сначала привяжите кошелёк</p>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {walletConfig?.configured && (
                  <Card className="bg-zinc-900 border-zinc-800">
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Send className="w-5 h-5 text-blue-400" />
                        Тестовая транзакция
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div>
                        <Label>Адрес получателя</Label>
                        <Input value={testAddress} onChange={(e) => setTestAddress(e.target.value)} placeholder="UQ... или EQ..." className="font-mono text-sm" />
                      </div>
                      <div>
                        <Label>Сумма (макс 0.01 USDT)</Label>
                        <Input type="number" step="0.001" max="0.01" value={testAmount} onChange={(e) => setTestAmount(parseFloat(e.target.value))} />
                      </div>
                      <Button onClick={testWithdraw} disabled={testing} className="w-full bg-blue-600 hover:bg-blue-700">
                        {testing ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Send className="w-4 h-4 mr-2" />}
                        Отправить тест
                      </Button>
                    </CardContent>
                  </Card>
                )}
              </div>
            </div>
              </>
            )}
          </TabsContent>

          {/* Telegram Tab */}
          <TabsContent value="telegram" className="space-y-6 mt-6">
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Bot className="w-5 h-5 text-blue-400" />
                  Telegram бот
                </CardTitle>
                <CardDescription>Настройте бота для отправки уведомлений пользователям</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-4">
                    <div>
                      <Label>Bot Token *</Label>
                      <Input
                        type="password"
                        value={telegramBotToken}
                        onChange={(e) => setTelegramBotToken(e.target.value)}
                        placeholder="123456:ABC-DEF..."
                      />
                      <p className="text-xs text-zinc-500 mt-1">Получите у @BotFather в Telegram</p>
                    </div>
                    
                    <div className="flex items-center justify-between p-4 bg-zinc-800 rounded-lg">
                      <div>
                        <p className="font-medium">Уведомления</p>
                        <p className="text-sm text-zinc-500">Отправка сообщений пользователям</p>
                      </div>
                      <Button
                        variant={telegramEnabled ? 'default' : 'outline'}
                        onClick={() => setTelegramEnabled(!telegramEnabled)}
                        className={telegramEnabled ? 'bg-emerald-600' : ''}
                      >
                        {telegramEnabled ? 'Вкл' : 'Выкл'}
                      </Button>
                    </div>
                    
                    <Button onClick={saveTelegramSettings} disabled={savingTelegram} className="w-full">
                      {savingTelegram ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                      Сохранить
                    </Button>
                  </div>
                  
                  <div className="p-4 bg-zinc-800 rounded-lg">
                    <h4 className="font-medium mb-3 flex items-center gap-2">
                      <Bell className="w-4 h-4 text-emerald-400" />
                      Типы уведомлений
                    </h4>
                    <ul className="text-sm text-zinc-400 space-y-2">
                      <li>• Новые заказы для трейдеров</li>
                      <li>• Подтверждения оплаты</li>
                      <li>• Решения споров</li>
                      <li>• Депозиты и выводы</li>
                      <li>• Ответы в тикетах</li>
                      <li>• Системные сообщения</li>
                    </ul>
                    
                    <div className="mt-4 p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg text-sm">
                      <p className="text-blue-300">
                        <strong>Инструкция:</strong>
                      </p>
                      <ol className="text-blue-300/80 mt-2 space-y-1 list-decimal list-inside">
                        <li>Создайте бота у @BotFather</li>
                        <li>Скопируйте токен бота</li>
                        <li>Вставьте токен выше</li>
                        <li>Включите уведомления</li>
                      </ol>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Broadcast Tab */}
          <TabsContent value="broadcast" className="space-y-6 mt-6">
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Megaphone className="w-5 h-5 text-emerald-400" />
                  Рассылка сообщений
                </CardTitle>
                <CardDescription>Отправка уведомлений через Telegram</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-4">
                  <div>
                    <Label>Получатели</Label>
                    <Select value={broadcastTarget} onValueChange={setBroadcastTarget}>
                      <SelectTrigger className="bg-zinc-800 border-zinc-700">
                        <SelectValue placeholder="Выберите группу" />
                      </SelectTrigger>
                      <SelectContent className="bg-zinc-800 border-zinc-700">
                        <SelectItem value="all">
                          <div className="flex items-center gap-2">
                            <Users className="w-4 h-4" />
                            Все пользователи
                          </div>
                        </SelectItem>
                        <SelectItem value="traders">Трейдеры</SelectItem>
                        <SelectItem value="merchants">Мерчанты</SelectItem>
                        <SelectItem value="staff">Персонал</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div>
                    <Label>Сообщение</Label>
                    <Textarea
                      value={broadcastMessage}
                      onChange={(e) => setBroadcastMessage(e.target.value)}
                      placeholder="Введите текст сообщения..."
                      className="min-h-[150px] bg-zinc-800 border-zinc-700"
                    />
                    <p className="text-xs text-zinc-500 mt-1">Поддерживается HTML форматирование: &lt;b&gt;, &lt;i&gt;, &lt;a&gt;</p>
                  </div>
                  
                  <Button 
                    onClick={handleSendBroadcast} 
                    disabled={sendingBroadcast || !broadcastMessage.trim()}
                    className="w-full bg-emerald-600 hover:bg-emerald-700"
                  >
                    {sendingBroadcast ? (
                      <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                    ) : (
                      <Send className="w-4 h-4 mr-2" />
                    )}
                    Отправить рассылку
                  </Button>
                </div>
                
                <div className="p-4 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                  <p className="text-amber-300 text-sm">
                    <strong>⚠️ Важно:</strong> Сообщения получат только пользователи с подключённым Telegram.
                  </p>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Platform Tab */}
          <TabsContent value="platform" className="space-y-6 mt-6">
            {/* Database Backup Card */}
            <Card className="bg-gradient-to-r from-blue-900/30 to-cyan-900/30 border-blue-700/50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-blue-400">
                  <Database className="w-5 h-5" />
                  Резервное копирование
                </CardTitle>
                <CardDescription className="text-zinc-300">
                  Скачайте полную копию базы данных для восстановления
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                <BackupDatabaseButton />
                <p className="text-xs text-zinc-500">
                  Файл содержит: пользователей, кошельки, ордера, споры, тикеты и все транзакции
                </p>
              </CardContent>
            </Card>

            {/* Sync Wallets Card */}
            <Card className="bg-gradient-to-r from-orange-900/30 to-amber-900/30 border-orange-700/50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-orange-400">
                  <RefreshCw className="w-5 h-5" />
                  Синхронизация балансов
                </CardTitle>
                <CardDescription className="text-zinc-300">
                  Если баланс на Dashboard и в Финансах отличается — нажмите для синхронизации
                </CardDescription>
              </CardHeader>
              <CardContent>
                <SyncWalletsButton />
              </CardContent>
            </Card>

            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Globe className="w-5 h-5 text-emerald-400" />
                  Настройки платформы
                </CardTitle>
                <CardDescription>Глобальные параметры системы</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-4">
                    <div>
                      <Label>Адрес платформы (TON)</Label>
                      <Input
                        value={platformSettings.platform_ton_address || ''}
                        onChange={(e) => setPlatformSettings({...platformSettings, platform_ton_address: e.target.value})}
                        placeholder="UQ... или EQ..."
                        className="font-mono text-sm"
                      />
                      <p className="text-xs text-zinc-500 mt-1">Для приёма депозитов</p>
                    </div>
                    
                    <div>
                      <Label>Комиссия на вывод (%)</Label>
                      <Input
                        type="number"
                        step="0.1"
                        value={platformSettings.withdrawal_fee_percent || 0}
                        onChange={(e) => setPlatformSettings({...platformSettings, withdrawal_fee_percent: parseFloat(e.target.value) || 0})}
                      />
                    </div>
                    
                    <div>
                      <Label>Сетевая комиссия (%)</Label>
                      <Input
                        type="number"
                        step="0.1"
                        value={platformSettings.network_fee || 0}
                        onChange={(e) => setPlatformSettings({...platformSettings, network_fee: parseFloat(e.target.value) || 0})}
                      />
                    </div>
                  </div>
                  
                  <div className="space-y-4">
                    <div>
                      <Label>Мин. депозит (USDT)</Label>
                      <Input
                        type="number"
                        step="0.01"
                        value={platformSettings.min_deposit || 0}
                        onChange={(e) => setPlatformSettings({...platformSettings, min_deposit: parseFloat(e.target.value) || 0})}
                      />
                      <p className="text-xs text-zinc-500 mt-1">0 = без ограничений</p>
                    </div>
                    
                    <div>
                      <Label>Мин. вывод (USDT)</Label>
                      <Input
                        type="number"
                        step="0.01"
                        value={platformSettings.min_withdrawal || 0}
                        onChange={(e) => setPlatformSettings({...platformSettings, min_withdrawal: parseFloat(e.target.value) || 0})}
                      />
                    </div>
                    
                    <div>
                      <Label>Срок действия заказа (мин)</Label>
                      <Input
                        type="number"
                        value={platformSettings.order_expiration_minutes || 30}
                        onChange={(e) => setPlatformSettings({...platformSettings, order_expiration_minutes: parseInt(e.target.value) || 30})}
                      />
                    </div>
                  </div>
                </div>
                
                <Button onClick={savePlatformSettings} disabled={savingPlatform} className="w-full mt-6">
                  {savingPlatform ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                  Сохранить настройки
                </Button>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
      
      {/* Security Verification Modal for Wallet Settings */}
      <SecurityVerification
        open={showSecurityModal}
        onOpenChange={setShowSecurityModal}
        onVerified={(data) => {
          setIsWalletVerified(true);
          setVerificationToken(data.verificationToken);
          setShowSecurityModal(false);
          toast.success('Доступ к настройкам кошелька подтверждён');
        }}
        title="Доступ к настройкам кошелька"
        description="Введите пароль и код 2FA для доступа к защищённому разделу с seed-фразой"
        actionLabel="Получить доступ"
      />
    </DashboardLayout>
  );
};

export default AdminSettings;
