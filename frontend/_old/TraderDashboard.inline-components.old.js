// Snapshot of old inline components from TraderDashboard.js (Etap 2.1 refactor)

/* === OLD INLINE COMPONENTS (kept for reference; can be deleted after verification) ===

// NOTE: NotificationDropdown was removed — dead code, replaced by EventNotificationDropdown.
// Shared version available at @/components/shared/NotificationDropdown.jsx if needed.

function TraderStats(){
  const { user, token } = useAuth();
  const [trader, setTrader] = useState(null);
  const [stats, setStats] = useState({ salesCount: 0, purchasesCount: 0, salesVolume: 0, purchasesVolume: 0 });
  const [depositAmount, setDepositAmount] = useState("");
  const [depositOpen, setDepositOpen] = useState(false);

  const fetchTrader = async () => {
    try {
      const response = await axios.get(`${API}/traders/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTrader(response.data);
    } catch (error) {
      console.error(error);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API}/traders/stats`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setStats(response.data);
    } catch (error) {
      console.error(error);
    }
  };

  useEffect(() => {
    if (token) {
      fetchTrader();
      fetchStats();
    }
  }, [token]);

  const handleDeposit = async () => {
    const amount = parseFloat(depositAmount);
    if (isNaN(amount) || amount <= 0) {
      toast.error("Введите корректную сумму");
      return;
    }
    try {
      await axios.post(`${API}/traders/deposit?amount=${amount}`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(`Пополнено ${amount} USDT`);
      setDepositOpen(false);
      setDepositAmount("");
      fetchTrader();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка пополнения");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white font-['Unbounded']">Статистика</h1>
        <Dialog open={depositOpen} onOpenChange={setDepositOpen}>
          <DialogTrigger asChild>
            <Button className="bg-[#10B981] hover:bg-[#059669] text-white rounded-full px-6" data-testid="deposit-btn" title="Пополнить баланс USDT">
              <Plus className="w-4 h-4 mr-2" />
              Пополнить
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-[#121212] border-white/10 text-white">
            <DialogHeader>
              <DialogTitle className="font-['Unbounded']">Пополнение баланса</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 pt-4">
              <div className="p-4 bg-[#7C3AED]/10 border border-[#7C3AED]/20 rounded-xl text-sm text-[#A1A1AA]">
                Для тестирования: введите сумму и нажмите "Пополнить".
              </div>
              <div className="space-y-2">
                <Label className="text-[#A1A1AA]">Сумма USDT</Label>
                <Input
                  type="number"
                  placeholder="100"
                  value={depositAmount}
                  onChange={(e) => setDepositAmount(e.target.value)}
                  className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl"
                />
              </div>
              <Button onClick={handleDeposit} className="w-full bg-[#10B981] hover:bg-[#059669] h-12 rounded-xl" title="Пополнить баланс USDT">
                Пополнить
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Balance Card */}
      <div className="bg-gradient-to-br from-[#7C3AED] to-[#A855F7] rounded-2xl p-6">
        <div className="text-white/70 text-sm mb-1">Общий баланс</div>
        <div className="text-4xl font-bold text-white font-['JetBrains_Mono']" data-testid="trader-balance">
          {trader?.balance_usdt?.toFixed(2) || "0.00"} <span className="text-xl text-white/70">USDT</span>
        </div>
        {(trader?.frozen_usdt || 0) > 0 && (
          <div className="text-sm text-yellow-300 mt-2">
            Заморожено: {trader?.frozen_usdt?.toFixed(2)} USDT · Доступно: {((trader?.balance_usdt || 0) - (trader?.frozen_usdt || 0)).toFixed(2)} USDT
          </div>
        )}
        <div className="text-sm text-white/50 mt-2">Комиссия платформы: {trader?.commission_rate || 1}%</div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Продаж</div>
          <div className="text-2xl font-bold text-white">{stats.salesCount || 0}</div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Объем продаж</div>
          <div className="text-2xl font-bold text-[#10B981] font-['JetBrains_Mono']">{(stats.salesVolume || 0).toFixed(0)} <span className="text-sm">USDT</span></div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Покупок</div>
          <div className="text-2xl font-bold text-white">{stats.purchasesCount || 0}</div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Объем покупок</div>
          <div className="text-2xl font-bold text-[#7C3AED] font-['JetBrains_Mono']">{(stats.purchasesVolume || 0).toFixed(0)} <span className="text-sm">USDT</span></div>
        </div>
      </div>

      {/* Quick Links */}
      <div className="grid sm:grid-cols-2 gap-4">
        <Link to="/trader/offers">
          <div className="bg-[#121212] border border-white/5 hover:border-[#7C3AED]/50 rounded-2xl p-5 transition-colors">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-[#7C3AED]/10 flex items-center justify-center">
                <ListOrdered className="w-5 h-5 text-[#7C3AED]" />
              </div>
              <div>
                <div className="text-white font-medium">Мои объявления</div>
                <div className="text-sm text-[#71717A]">Управление офферами</div>
              </div>
            </div>
          </div>
        </Link>
        <Link to="/">
          <div className="bg-[#121212] border border-white/5 hover:border-[#10B981]/50 rounded-2xl p-5 transition-colors">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-[#10B981]/10 flex items-center justify-center">
                <TrendingUp className="w-5 h-5 text-[#10B981]" />
              </div>
              <div>
                <div className="text-white font-medium">Купить USDT</div>
                <div className="text-sm text-[#71717A]">Перейти на главную</div>
              </div>
            </div>
          </div>
        </Link>
      </div>
    </div>
  );
}

function TraderReferral_OLD() {
  const { token } = useAuth();
  const [referralInfo, setReferralInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [withdrawing, setWithdrawing] = useState(false);

  useEffect(() => {
    fetchReferralInfo();
  }, []);

  const fetchReferralInfo = async () => {
    try {
      const response = await axios.get(`${API}/referral`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setReferralInfo(response.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success("Скопировано!");
  };

  const handleWithdraw = async () => {
    setWithdrawing(true);
    try {
      await axios.post(`${API}/referral/withdraw`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Бонус переведён на основной баланс");
      fetchReferralInfo();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка вывода");
    } finally {
      setWithdrawing(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="spinner" />
      </div>
    );
  }

  const level1Percent = referralInfo?.settings?.level1_percent || 5;
  const referralLink = `${window.location.origin}/register?ref=${referralInfo?.referral_code}`;
  const minWithdrawal = referralInfo?.settings?.min_withdrawal_usdt || 1;
  const canWithdraw = (referralInfo?.referral_balance_usdt || 0) >= minWithdrawal;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-white">Реферальная программа</h1>
      <p className="text-[#71717A]">Получайте {level1Percent}% от комиссии приглашённых трейдеров</p>

      {/* Promo Banner */}
      <div className="bg-gradient-to-br from-[#7C3AED]/20 via-[#A855F7]/15 to-[#EC4899]/20 border border-[#7C3AED]/30 rounded-2xl p-6">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-[#7C3AED]/30 flex items-center justify-center flex-shrink-0">
            <TrendingUp className="w-6 h-6 text-[#A78BFA]" />
          </div>
          <div>
            <h3 className="text-white font-semibold text-lg mb-2">💰 Пассивный доход без усилий</h3>
            <p className="text-[#A1A1AA] text-sm leading-relaxed">
              Приглашайте друзей и знакомых на Reptiloid и получайте <span className="text-[#10B981] font-semibold">{level1Percent}% комиссии</span> с каждой их сделки — навсегда! 
              Чем больше ваших рефералов торгует, тем выше ваш пассивный доход.
            </p>
            <div className="flex flex-wrap gap-4 mt-4 text-sm">
              <div className="flex items-center gap-2 text-[#A78BFA]">
                <CheckCircle className="w-4 h-4" />
                Без ограничений по времени
              </div>
              <div className="flex items-center gap-2 text-[#A78BFA]">
                <CheckCircle className="w-4 h-4" />
                Мгновенные выплаты
              </div>
              <div className="flex items-center gap-2 text-[#A78BFA]">
                <CheckCircle className="w-4 h-4" />
                Неограниченное число рефералов
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid sm:grid-cols-4 gap-4">
        <div className="bg-[#121212] border border-white/5 rounded-xl p-5">
          <div className="text-[#52525B] text-xs mb-1">Баланс бонусов</div>
          <div className="text-2xl font-semibold text-[#7C3AED] font-mono">
            {(referralInfo?.referral_balance_usdt || 0).toFixed(2)}
          </div>
          <div className="text-xs text-[#52525B]">USDT</div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-xl p-5">
          <div className="text-[#52525B] text-xs mb-1">Всего заработано</div>
          <div className="text-2xl font-semibold text-[#10B981] font-mono">
            {(referralInfo?.total_earned_usdt || 0).toFixed(2)}
          </div>
          <div className="text-xs text-[#52525B]">USDT</div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-xl p-5">
          <div className="text-[#52525B] text-xs mb-1">Рефералов</div>
          <div className="text-2xl font-semibold text-white">
            {referralInfo?.total_referrals || 0}
          </div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-xl p-5">
          <div className="text-[#52525B] text-xs mb-1">Ставка</div>
          <div className="text-2xl font-semibold text-white">{level1Percent}%</div>
          <div className="text-xs text-[#52525B]">от комиссии</div>
        </div>
      </div>

      {/* Withdraw */}
      {(referralInfo?.referral_balance_usdt || 0) > 0 && (
        <div className="bg-[#121212] border border-white/5 rounded-xl p-5">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-white font-medium">Вывод бонусов</h3>
              <p className="text-[#71717A] text-sm">Мин. сумма: {minWithdrawal} USDT</p>
            </div>
            <Button
              onClick={handleWithdraw}
              disabled={!canWithdraw || withdrawing}
              className={`${canWithdraw ? "bg-[#10B981] hover:bg-[#059669]" : "bg-[#52525B]"} text-white`}
            >
              {withdrawing ? "..." : "Вывести на баланс"}
            </Button>
          </div>
        </div>
      )}

      {/* Referral Link */}
      <div className="bg-[#121212] border border-white/5 rounded-xl p-5">
        <h3 className="text-white font-medium mb-4">🔗 Ваша реферальная ссылка</h3>
        <p className="text-[#71717A] text-sm mb-4">Отправьте эту ссылку друзьям — они автоматически станут вашими рефералами</p>
        
        <div className="flex items-center gap-2">
          <div className="flex-1 bg-[#0A0A0A] border border-white/10 rounded-lg px-4 py-3 text-sm text-[#A1A1AA] truncate">
            {referralLink}
          </div>
          <Button
            onClick={() => copyToClipboard(referralLink)}
            className="h-12 px-4 bg-[#7C3AED] hover:bg-[#6D28D9] text-white"
           title="Скопировать в буфер обмена">
            <Copy className="w-4 h-4 mr-2" />
            Копировать
          </Button>
        </div>
      </div>

      {/* Level Stats */}
      {referralInfo?.level_stats && (
        <div className="bg-[#121212] border border-white/5 rounded-xl p-5">
          <h3 className="text-white font-medium mb-4">Уровни рефералов</h3>
          <div className="grid grid-cols-3 gap-3">
            {referralInfo.level_stats.map((level, idx) => (
              <div key={level.level} className={`p-4 rounded-xl text-center ${
                idx === 0 ? "bg-[#10B981]/10" : idx === 1 ? "bg-[#F59E0B]/10" : "bg-[#71717A]/10"
              }`}>
                <div className={`text-xl font-bold ${
                  idx === 0 ? "text-[#10B981]" : idx === 1 ? "text-[#F59E0B]" : "text-[#71717A]"
                }`}>
                  {level.count}
                </div>
                <div className="text-[#71717A] text-xs">{level.level}-й уровень</div>
                <div className="text-[#52525B] text-xs">{level.percent}%</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* History */}
      {referralInfo?.history && referralInfo.history.length > 0 && (
        <div className="bg-[#121212] border border-white/5 rounded-xl p-5">
          <h3 className="text-white font-medium mb-4">История начислений</h3>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {referralInfo.history.map((item, idx) => (
              <div key={idx} className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
                <div>
                  <span className="text-white text-sm">+{item.bonus_usdt?.toFixed(4)} USDT</span>
                  <span className="text-[#71717A] text-xs ml-2">{item.level}-й уровень</span>
                </div>
                <span className="text-xs text-[#52525B]">
                  {new Date(item.created_at).toLocaleDateString("ru-RU")}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ==================== TRADING SETTINGS ====================
function TradingSettings_OLD() {
  const { token } = useAuth();
  const [displayName, setDisplayName] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const response = await axios.get(`${API}/traders/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setDisplayName(response.data.display_name || response.data.nickname || "");
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!displayName.trim()) {
      toast.error("Введите отображаемое имя");
      return;
    }
    setSaving(true);
    try {
      await axios.put(`${API}/traders/me`, {
        display_name: displayName.trim()
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Настройки сохранены");
    } catch (error) {
      toast.error("Ошибка сохранения");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-white font-['Unbounded']">Настройки торговли</h1>

      <div className="bg-[#121212] border border-white/5 rounded-2xl p-6 space-y-6">
        <div>
          <h3 className="text-white font-semibold mb-4">Отображаемое имя</h3>
          <p className="text-sm text-[#71717A] mb-4">
            Это имя будет отображаться в стакане объявлений вместо вашего логина
          </p>
          <Input
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Введите отображаемое имя"
            className="bg-white/5 border-white/10 text-white h-12 rounded-xl max-w-md"
            maxLength={30}
          />
          <p className="text-xs text-[#71717A] mt-2">Максимум 30 символов</p>
        </div>

        <Button onClick={handleSave} disabled={saving} className="bg-[#7C3AED] hover:bg-[#6D28D9] h-11 rounded-xl px-8" data-testid="save-trading-settings-btn">
          {saving ? <div className="spinner" /> : "Сохранить"}
        </Button>
      </div>
    </div>
  );
}

// ==================== TRADING STATS ====================
function TradingStats_OLD() {
  const { token } = useAuth();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API}/traders/me/stats`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setStats(response.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white font-['Unbounded']">Статистика торговли</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Всего сделок</div>
          <div className="text-2xl font-bold text-white">{stats?.total_trades || 0}</div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Завершённых</div>
          <div className="text-2xl font-bold text-[#10B981]">{stats?.completed_trades || 0}</div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Отменённых</div>
          <div className="text-2xl font-bold text-[#71717A]">{stats?.cancelled_trades || 0}</div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Диспутов</div>
          <div className="text-2xl font-bold text-[#EF4444]">{stats?.disputed_trades || 0}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Общая сумма сделок</div>
          <div className="text-xl font-bold text-white">{(stats?.total_volume_usdt || 0).toFixed(2)} USDT</div>
          <div className="text-sm text-[#71717A]">≈ {Math.round(stats?.total_volume_rub || 0).toLocaleString()} ₽</div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Средний курс</div>
          <div className="text-xl font-bold text-white">{Math.round(stats?.avg_rate || 0)} ₽</div>
        </div>
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="text-[#71717A] text-sm mb-2">Среднее время сделки</div>
          <div className="text-xl font-bold text-white">{stats?.avg_time_minutes || 0} мин</div>
        </div>
      </div>
    </div>
  );
}

function TraderSettings_OLD() {
  const { token, user } = useAuth();
  const [trader, setTrader] = useState(null);
  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [show2FAForm, setShow2FAForm] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [saving, setSaving] = useState(false);
  const [twoFAEnabled, setTwoFAEnabled] = useState(false);

  useEffect(() => {
    fetchTrader();
  }, []);

  const fetchTrader = async () => {
    try {
      const response = await axios.get(`${API}/traders/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTrader(response.data);
      setTwoFAEnabled(response.data.two_fa_enabled || false);
    } catch (error) {
      console.error(error);
    }
  };

  const handleChangePassword = async () => {
    if (newPassword !== confirmPassword) {
      toast.error("Пароли не совпадают");
      return;
    }
    if (newPassword.length < 6) {
      toast.error("Пароль должен быть не менее 6 символов");
      return;
    }
    
    setSaving(true);
    try {
      await axios.post(`${API}/traders/change-password`, {
        current_password: currentPassword,
        new_password: newPassword
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Пароль успешно изменён");
      setShowPasswordForm(false);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка смены пароля");
    } finally {
      setSaving(false);
    }
  };

  const handleToggle2FA = async () => {
    setSaving(true);
    try {
      await axios.post(`${API}/traders/toggle-2fa`, {
        enabled: !twoFAEnabled
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTwoFAEnabled(!twoFAEnabled);
      toast.success(twoFAEnabled ? "2FA отключена" : "2FA включена");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-white font-['Unbounded']">Настройки аккаунта</h1>

      {/* Смена пароля */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-[#7C3AED]/20 flex items-center justify-center">
            <Key className="w-5 h-5 text-[#7C3AED]" />
          </div>
          <div>
            <h3 className="text-white font-semibold">Смена пароля</h3>
            <p className="text-sm text-[#71717A]">Изменить пароль для входа в аккаунт</p>
          </div>
        </div>
        
        {!showPasswordForm ? (
          <Button 
            onClick={() => setShowPasswordForm(true)}
            variant="outline"
            className="border-white/10 text-white hover:bg-white/5"
           title="Изменить пароль аккаунта">
            Изменить пароль
          </Button>
        ) : (
          <div className="space-y-4">
            <div>
              <Label className="text-[#71717A] text-sm">Текущий пароль</Label>
              <div className="relative mt-1">
                <Input
                  type={showCurrentPassword ? "text" : "password"}
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="bg-[#0A0A0A] border-white/10 text-white pr-10"
                  placeholder="Введите текущий пароль"
                />
                <button
                  type="button"
                  onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#71717A] hover:text-white"
                >
                  {showCurrentPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            
            <div>
              <Label className="text-[#71717A] text-sm">Новый пароль</Label>
              <div className="relative mt-1">
                <Input
                  type={showNewPassword ? "text" : "password"}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="bg-[#0A0A0A] border-white/10 text-white pr-10"
                  placeholder="Введите новый пароль"
                />
                <button
                  type="button"
                  onClick={() => setShowNewPassword(!showNewPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#71717A] hover:text-white"
                >
                  {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            
            <div>
              <Label className="text-[#71717A] text-sm">Подтвердите пароль</Label>
              <Input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="bg-[#0A0A0A] border-white/10 text-white mt-1"
                placeholder="Повторите новый пароль"
              />
            </div>
            
            <div className="flex gap-3">
              <Button 
                onClick={handleChangePassword}
                disabled={saving || !currentPassword || !newPassword || !confirmPassword}
                className="bg-[#7C3AED] hover:bg-[#6D28D9]"
              >
                {saving ? <div className="spinner" /> : "Сохранить"}
              </Button>
              <Button 
                onClick={() => {
                  setShowPasswordForm(false);
                  setCurrentPassword("");
                  setNewPassword("");
                  setConfirmPassword("");
                }}
                variant="outline"
                className="border-white/10 text-white hover:bg-white/5"
              >
                Отмена
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* 2FA */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${twoFAEnabled ? "bg-[#10B981]/20" : "bg-[#F59E0B]/20"}`}>
              <Lock className={`w-5 h-5 ${twoFAEnabled ? "text-[#10B981]" : "text-[#F59E0B]"}`} />
            </div>
            <div>
              <h3 className="text-white font-semibold">Двухфакторная аутентификация</h3>
              <p className="text-sm text-[#71717A]">
                {twoFAEnabled ? "2FA включена — аккаунт защищён" : "Рекомендуем включить для безопасности"}
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <span className={`px-3 py-1 rounded-full text-xs font-medium ${
              twoFAEnabled 
                ? "bg-[#10B981]/20 text-[#10B981]" 
                : "bg-[#F59E0B]/20 text-[#F59E0B]"
            }`}>
              {twoFAEnabled ? "Включено" : "Отключено"}
            </span>
            <Button 
              onClick={handleToggle2FA}
              disabled={saving}
              variant={twoFAEnabled ? "outline" : "default"}
              className={twoFAEnabled 
                ? "border-[#EF4444]/50 text-[#EF4444] hover:bg-[#EF4444]/10" 
                : "bg-[#10B981] hover:bg-[#059669]"
              }
            >
              {saving ? <div className="spinner" /> : (twoFAEnabled ? "Отключить" : "Включить")}
            </Button>
          </div>
        </div>
        
        {!twoFAEnabled && (
          <div className="mt-4 p-4 bg-[#F59E0B]/10 border border-[#F59E0B]/20 rounded-xl">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-[#F59E0B] flex-shrink-0 mt-0.5" />
              <div className="text-sm text-[#F59E0B]">
                <p className="font-medium">Защитите свой аккаунт</p>
                <p className="opacity-80 mt-1">При входе будет запрашиваться дополнительный код подтверждения.</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Информация */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
        <h3 className="text-white font-semibold mb-4">Информация об аккаунте</h3>
        <div className="space-y-3 text-sm">
          <div className="flex justify-between">
            <span className="text-[#71717A]">Логин</span>
            <span className="text-white">{user?.login}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#71717A]">Комиссия</span>
            <span className="text-white">{trader?.commission_rate}%</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#71717A]">Баланс</span>
            <span className="text-white font-['JetBrains_Mono']">{trader?.balance_usdt?.toFixed(2)} USDT</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#71717A]">Дата регистрации</span>
            <span className="text-white">{trader?.created_at ? new Date(trader.created_at).toLocaleDateString("ru-RU") : "—"}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ==================== MY MARKET PURCHASES ====================
function MyMarketPurchases_OLD() {
  const { token } = useAuth();
  const [purchases, setPurchases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    fetchPurchases();
  }, []);

  const fetchPurchases = async () => {
    try {
      const response = await axios.get(`${API}/marketplace/my-purchases`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setPurchases(response.data || []);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const toggleExpand = async (id) => {
    const newId = expandedId === id ? null : id;
    setExpandedId(newId);
    // Mark purchase as viewed when expanding
    if (newId) {
      const purchase = purchases.find(p => p.id === id);
      if (purchase && !purchase.viewed) {
        try {
          await axios.post(`${API}/marketplace/purchases/${id}/mark-viewed`, {}, {
            headers: { Authorization: `Bearer ${token}` }
          });
          setPurchases(prev => prev.map(p => p.id === id ? { ...p, viewed: true } : p));
        } catch (e) { console.error(e); }
      }
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success("Скопировано!");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-[#7C3AED] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white font-['Unbounded']">Мои покупки</h1>
        <p className="text-[#71717A]">История заказов с маркетплейса</p>
      </div>

      {purchases.length === 0 ? (
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-12 text-center">
          <ShoppingBag className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
          <p className="text-[#71717A]">Вы ещё ничего не покупали</p>
          <Link to="/marketplace">
            <Button className="mt-4 bg-[#7C3AED] hover:bg-[#6D28D9] rounded-full px-6">
              Перейти в каталог
            </Button>
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {purchases.map((purchase) => (
            <PurchaseCard 
              key={purchase.id} 
              purchase={purchase} 
              expandedId={expandedId}
              toggleExpand={toggleExpand}
              copyToClipboard={copyToClipboard}
              onRefresh={fetchPurchases}
              token={token}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// Purchase card with guarantor support
function PurchaseCard_OLD({ purchase, expandedId, toggleExpand, copyToClipboard, onRefresh, token }) {
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [disputing, setDisputing] = useState(false);
  const [disputeReason, setDisputeReason] = useState("");
  const [showDisputeForm, setShowDisputeForm] = useState(false);

  const handleConfirm = async () => {
    setConfirming(true);
    try {
      const response = await axios.post(
        `${API}/marketplace/purchases/${purchase.id}/confirm`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      // Format delivered content for display
      const formatContent = (content) => {
        if (!content) return null;
        const items = Array.isArray(content) ? content : [content];
        return items.map(item => {
          if (typeof item === 'string') return item;
          if (typeof item === 'object' && item !== null) return item.text || '';
          return String(item);
        }).filter(Boolean).join('\n---\n');
      };
      
      toast.success(
        <div>
          <div className="font-semibold">Покупка подтверждена!</div>
          {response.data.delivered_content && (
            <div className="text-sm mt-2 font-mono bg-black/20 p-2 rounded break-all whitespace-pre-wrap max-h-32 overflow-y-auto">
              {formatContent(response.data.delivered_content)}
            </div>
          )}
        </div>,
        { duration: 15000 }
      );
      onRefresh();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка подтверждения");
    } finally {
      setConfirming(false);
    }
  };

  const handleCancel = async () => {
    setCancelling(true);
    try {
      await axios.post(
        `${API}/marketplace/purchases/${purchase.id}/cancel`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success("Заказ отменён, средства возвращены");
      onRefresh();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка отмены");
    } finally {
      setCancelling(false);
    }
  };

  const handleDispute = async () => {
    if (!disputeReason.trim()) {
      toast.error("Укажите причину спора");
      return;
    }
    setDisputing(true);
    try {
      await axios.post(
        `${API}/marketplace/purchases/${purchase.id}/dispute`,
        {},
        { 
          headers: { Authorization: `Bearer ${token}` },
          params: { reason: disputeReason }
        }
      );
      toast.success("Спор открыт. Администратор рассмотрит вашу заявку.");
      setShowDisputeForm(false);
      onRefresh();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка открытия спора");
    } finally {
      setDisputing(false);
    }
  };

  // Status badge
  const getStatusBadge = () => {
    switch (purchase.status) {
      case "completed":
        return <span className="px-2 py-1 text-xs rounded-full bg-[#10B981]/10 text-[#10B981]">Завершено</span>;
      case "pending_confirmation":
        return <span className="px-2 py-1 text-xs rounded-full bg-[#F59E0B]/10 text-[#F59E0B] flex items-center gap-1"><Clock className="w-3 h-3" />Ожидает подтверждения</span>;
      case "disputed":
        return <span className="px-2 py-1 text-xs rounded-full bg-[#EF4444]/10 text-[#EF4444]">Спор</span>;
      case "cancelled":
        return <span className="px-2 py-1 text-xs rounded-full bg-[#71717A]/10 text-[#71717A]">Отменено</span>;
      case "refunded":
        return <span className="px-2 py-1 text-xs rounded-full bg-[#3B82F6]/10 text-[#3B82F6]">Возврат</span>;
      default:
        return <span className="px-2 py-1 text-xs rounded-full bg-[#71717A]/10 text-[#71717A]">{purchase.status}</span>;
    }
  };

  const isGuarantor = purchase.purchase_type === "guarantor";
  const isPending = purchase.status === "pending_confirmation";
  const hasContent = purchase.delivered_content && (Array.isArray(purchase.delivered_content) ? purchase.delivered_content.length > 0 : purchase.delivered_content);

  return (
    <div className={`bg-[#121212] border rounded-xl p-5 ${isPending ? "border-[#F59E0B]/30" : "border-white/5"}`}>
      {/* Order Number */}
      <div className="flex items-center justify-between text-xs text-[#52525B] mb-2">
        <div className="flex items-center gap-2">
          <span>Заказ #{purchase.id?.slice(0, 8).toUpperCase()}</span>
          {purchase.unread_messages > 0 && (
            <span className="px-1.5 py-0.5 text-[10px] rounded-full bg-[#EF4444] text-white font-bold animate-pulse">
              {purchase.unread_messages} новых
            </span>
          )}
        </div>
        <span>{new Date(purchase.created_at).toLocaleString("ru-RU")}</span>
      </div>
      
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-white font-semibold">{purchase.product_name}</span>
            {isGuarantor && (
              <span className="px-1.5 py-0.5 text-[10px] rounded bg-[#7C3AED]/20 text-[#A78BFA] flex items-center gap-1">
                <Shield className="w-3 h-3" />Гарант
              </span>
            )}
          </div>
          <div className="text-sm text-[#71717A]">@{purchase.seller_nickname}</div>
        </div>
        {getStatusBadge()}
      </div>
      
      <div className="flex items-center justify-between text-sm mb-2">
        <span className="text-[#71717A]">Количество: {purchase.quantity}</span>
        <div className="text-right">
          <span className="text-[#10B981] font-mono">{purchase.total_price?.toFixed(2)} USDT</span>
          {isGuarantor && purchase.guarantor_fee > 0 && (
            <div className="text-xs text-[#7C3AED]">+{purchase.guarantor_fee?.toFixed(2)} гарант</div>
          )}
        </div>
      </div>

      {/* Auto-complete countdown for pending */}
      {isPending && purchase.auto_complete_at && (
        <div className="mb-3 p-2 bg-[#F59E0B]/5 border border-[#F59E0B]/20 rounded-lg text-xs text-[#F59E0B] flex items-center gap-2">
          <Clock className="w-4 h-4" />
          <span>Автозавершение: {new Date(purchase.auto_complete_at).toLocaleDateString("ru-RU")}</span>
        </div>
      )}

      {/* Action buttons for pending guarantor orders */}
      {isPending && (
        <div className="space-y-2 mt-3">
          <div className="flex gap-2">
            <Button
              onClick={handleConfirm}
              disabled={confirming}
              className="flex-1 bg-[#10B981] hover:bg-[#059669] text-white"
             title="Подтвердить получение оплаты">
              {confirming ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <CheckCircle className="w-4 h-4 mr-2" />
                  Подтвердить получение
                </>
              )}
            </Button>
            <Button
              onClick={handleCancel}
              disabled={cancelling}
              variant="outline"
              className="border-[#EF4444]/30 text-[#EF4444] hover:bg-[#EF4444]/10"
            >
              {cancelling ? (
                <div className="w-4 h-4 border-2 border-[#EF4444] border-t-transparent rounded-full animate-spin" />
              ) : (
                <XCircle className="w-4 h-4" />
              )}
            </Button>
          </div>
          
          {/* Chat button - different for guarantor vs regular purchases */}
          {isGuarantor ? (
            <Button
              onClick={() => navigate(`/trader/guarantor-chat/${purchase.id}`)}
              variant="outline"
              size="sm"
              className="w-full text-[#7C3AED] border-[#7C3AED]/30 hover:bg-[#7C3AED]/10 text-xs"
            >
              <Shield className="w-3 h-3 mr-1" />
              Чат гаранта
            </Button>
          ) : (
            <Button
              onClick={() => {
                const orderId = purchase.id?.slice(0, 8).toUpperCase();
                navigate(`/trader/shop-chats?shop=${purchase.seller_id}&subject=${encodeURIComponent(`Вопрос по заказу #${orderId}`)}`);
              }}
              variant="outline"
              size="sm"
              className="w-full text-[#7C3AED] border-[#7C3AED]/30 hover:bg-[#7C3AED]/10 text-xs"
            >
              <MessageCircle className="w-3 h-3 mr-1" />
              Вопрос по заказу
            </Button>
          )}
          
          {!showDisputeForm ? (
            <Button
              onClick={() => setShowDisputeForm(true)}
              variant="ghost"
              size="sm"
              className="w-full text-[#71717A] hover:text-[#EF4444] text-xs"
             title="Открыть спор по сделке">
              <AlertTriangle className="w-3 h-3 mr-1" />
              Открыть спор
            </Button>
          ) : (
            <div className="p-3 bg-[#0A0A0A] border border-[#EF4444]/20 rounded-lg space-y-2">
              <textarea
                value={disputeReason}
                onChange={(e) => setDisputeReason(e.target.value)}
                placeholder="Опишите проблему..."
                className="w-full bg-[#121212] border border-white/10 rounded-lg p-2 text-white text-sm resize-none h-20"
              />
              <div className="flex gap-2">
                <Button
                  onClick={handleDispute}
                  disabled={disputing}
                  size="sm"
                  className="flex-1 bg-[#EF4444] hover:bg-[#DC2626] text-white text-xs"
                >
                  {disputing ? "Отправка..." : "Отправить спор"}
                </Button>
                <Button
                  onClick={() => setShowDisputeForm(false)}
                  variant="outline"
                  size="sm"
                  className="text-xs"
                 title="Отменить действие">
                  Отмена
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
      
      {/* Show/Hide Product Button for completed orders */}
      {hasContent && (
        <div className="mt-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => toggleExpand(purchase.id)}
            className="w-full border-[#7C3AED]/30 text-[#A78BFA] hover:bg-[#7C3AED]/10"
          >
            {expandedId === purchase.id ? (
              <>
                <XCircle className="w-4 h-4 mr-2" />
                Скрыть товар
              </>
            ) : (
              <>
                <CheckCircle className="w-4 h-4 mr-2" />
                Показать товар
              </>
            )}
          </Button>
          
          {expandedId === purchase.id && (
            <div className="mt-3 p-4 bg-[#0A0A0A] border border-[#7C3AED]/20 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <div className="text-xs text-[#A78BFA]">Полученный товар ({Array.isArray(purchase.delivered_content) ? purchase.delivered_content.length : 1} шт.):</div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    const content = Array.isArray(purchase.delivered_content) 
                      ? purchase.delivered_content.map(item => typeof item === 'object' ? item.text : item).join('\n')
                      : (typeof purchase.delivered_content === 'object' ? purchase.delivered_content.text : purchase.delivered_content);
                    copyToClipboard(content);
                  }}
                  className="text-[#71717A] hover:text-white p-1 h-auto"
                >
                  <Copy className="w-4 h-4" />
                </Button>
              </div>
              <div className="space-y-2">
                {(Array.isArray(purchase.delivered_content) ? purchase.delivered_content : [purchase.delivered_content]).map((item, idx) => {
                  const itemText = typeof item === 'object' ? item.text : item;
                  const itemPhoto = typeof item === 'object' ? item.photo_url : null;
                  const itemFile = typeof item === 'object' ? item.file_url : null;
                  
                  return (
                    <div key={idx} className="bg-[#121212] p-3 rounded border border-white/5 space-y-2">
                      {/* Text content */}
                      {itemText && (
                        <div className="flex items-center justify-between">
                          <span className="text-sm text-white font-mono break-all">{itemText}</span>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => copyToClipboard(itemText)}
                            className="text-[#52525B] hover:text-white p-1 h-auto ml-2 flex-shrink-0"
                          >
                            <Copy className="w-3 h-3" />
                          </Button>
                        </div>
                      )}
                      
                      {/* Photo */}
                      {itemPhoto && !itemPhoto.includes("[") && (
                        <div className="mt-2">
                          <img src={itemPhoto} alt="" className="max-w-full max-h-48 rounded-lg" />
                        </div>
                      )}
                      {itemPhoto && itemPhoto.includes("[") && (
                        <div className="text-xs text-[#71717A] italic">{itemPhoto}</div>
                      )}
                      
                      {/* File */}
                      {itemFile && !itemFile.includes("[") && (
                        <div className="mt-2">
                          <a 
                            href={itemFile} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="text-xs text-[#7C3AED] hover:text-[#A78BFA] flex items-center gap-1"
                          >
                            <Download className="w-3 h-3" />
                            Скачать файл
                          </a>
                        </div>
                      )}
                      {itemFile && itemFile.includes("[") && (
                        <div className="text-xs text-[#71717A] italic">{itemFile}</div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
      
      {/* Question about order button - for all orders */}
      {!isPending && (
        <div className="mt-3">
          <Button
            onClick={() => {
              const orderId = purchase.id?.slice(0, 8).toUpperCase();
              navigate(`/trader/shop-chats?shop=${purchase.seller_id}&subject=${encodeURIComponent(`Вопрос по заказу #${orderId}`)}`);
            }}
            variant="outline"
            size="sm"
            className="w-full text-[#7C3AED] border-[#7C3AED]/30 hover:bg-[#7C3AED]/10 text-xs"
          >
            <MessageCircle className="w-3 h-3 mr-1" />
            Вопрос по заказу #{purchase.id?.slice(0, 8).toUpperCase()}
          </Button>
        </div>
      )}
      
      <div className="text-xs text-[#52525B] mt-3">
        {new Date(purchase.created_at).toLocaleString("ru-RU")}
      </div>
    </div>
  );
}

// ==================== TRADER TRANSACTIONS ====================
function TraderTransactions_OLD() {
  const { token, user } = useAuth();
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [balance, setBalance] = useState(0);

  useEffect(() => {
    fetchTransactions();
    fetchBalance();
  }, []);

  const fetchTransactions = async () => {
    try {
      const response = await axios.get(`${API}/traders/transactions`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTransactions(response.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const fetchBalance = async () => {
    try {
      const response = await axios.get(`${API}/traders/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setBalance(response.data.balance_usdt);
    } catch (error) {
      console.error(error);
    }
  };

  const getTypeConfig = (type) => {
    const configs = {
      offer_created: { label: "Создание объявления", icon: ListOrdered, color: "#F59E0B", bgColor: "#F59E0B" },
      offer_closed: { label: "Закрытие объявления", icon: CheckCircle, color: "#10B981", bgColor: "#10B981" },
      sale_completed: { label: "Продажа", icon: TrendingUp, color: "#10B981", bgColor: "#10B981" },
      purchase_completed: { label: "Покупка", icon: ShoppingBag, color: "#10B981", bgColor: "#10B981" },
      marketplace_purchase: { label: "Покупка в маркете", icon: Store, color: "#F59E0B", bgColor: "#F59E0B" },
      marketplace_sale: { label: "Продажа в маркете", icon: Store, color: "#10B981", bgColor: "#10B981" },
      transfer_sent: { label: "Перевод отправлен", icon: ArrowUpRight, color: "#EF4444", bgColor: "#EF4444" },
      transfer_received: { label: "Перевод получен", icon: ArrowDownRight, color: "#10B981", bgColor: "#10B981" },
      referral_bonus: { label: "Реферальный бонус", icon: Users, color: "#7C3AED", bgColor: "#7C3AED" },
      commission: { label: "Комиссия платформы", icon: DollarSign, color: "#EF4444", bgColor: "#EF4444" },
      deposit: { label: "Пополнение", icon: ArrowDownRight, color: "#10B981", bgColor: "#10B981" },
      withdrawal: { label: "Вывод", icon: ArrowUpRight, color: "#EF4444", bgColor: "#EF4444" }
    };
    return configs[type] || { label: type, icon: DollarSign, color: "#71717A", bgColor: "#71717A" };
  };

  const filteredTransactions = transactions.filter(tx => {
    if (filter === "all") return true;
    if (filter === "income") return tx.amount > 0;
    if (filter === "expense") return tx.amount < 0;
    if (filter === "commission") return tx.type === "commission";
    if (filter === "marketplace") return ["marketplace_purchase", "marketplace_sale"].includes(tx.type);
    if (filter === "offers") return ["offer_created", "offer_closed"].includes(tx.type);
    if (filter === "transfers") return ["transfer_sent", "transfer_received"].includes(tx.type);
    return true;
  });

  const totalIncome = transactions.filter(t => t.amount > 0).reduce((sum, t) => sum + t.amount, 0);
  const totalExpense = Math.abs(transactions.filter(t => t.amount < 0).reduce((sum, t) => sum + t.amount, 0));

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with Balance */}
      <div className="bg-gradient-to-r from-[#7C3AED]/20 to-[#10B981]/20 border border-white/10 rounded-2xl p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white mb-2">История транзакций</h1>
            <p className="text-[#71717A]">Все финансовые операции вашего аккаунта</p>
          </div>
          <div className="text-right">
            <div className="text-sm text-[#71717A]">Текущий баланс</div>
            <div className="text-3xl font-bold text-[#10B981] font-['JetBrains_Mono']">
              {balance.toFixed(2)} USDT
            </div>
          </div>
        </div>
        
        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mt-6 pt-6 border-t border-white/10">
          <div className="bg-white/5 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <ArrowDownRight className="w-4 h-4 text-[#10B981]" />
              <span className="text-[#71717A] text-sm">Поступления</span>
            </div>
            <div className="text-xl font-bold text-[#10B981]">+{totalIncome.toFixed(2)} USDT</div>
          </div>
          <div className="bg-white/5 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <ArrowUpRight className="w-4 h-4 text-[#EF4444]" />
              <span className="text-[#71717A] text-sm">Списания</span>
            </div>
            <div className="text-xl font-bold text-[#EF4444]">−{totalExpense.toFixed(2)} USDT</div>
          </div>
          <div className="bg-white/5 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <History className="w-4 h-4 text-[#7C3AED]" />
              <span className="text-[#71717A] text-sm">Всего операций</span>
            </div>
            <div className="text-xl font-bold text-white">{transactions.length}</div>
          </div>
        </div>
      </div>
      
      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        {[
          { value: "all", label: "Все" },
          { value: "income", label: "Поступления" },
          { value: "expense", label: "Списания" },
          { value: "commission", label: "Комиссии" },
          { value: "marketplace", label: "Маркетплейс" },
          { value: "offers", label: "Объявления" },
          { value: "transfers", label: "Переводы" }
        ].map(f => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
              filter === f.value
                ? "bg-[#7C3AED] text-white"
                : "bg-white/5 text-[#71717A] hover:bg-white/10"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>
      
      {/* Transactions List */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl overflow-hidden">
        {filteredTransactions.length === 0 ? (
          <div className="text-center py-12">
            <History className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
            <p className="text-[#71717A]">Транзакций не найдено</p>
          </div>
        ) : (
          <div className="divide-y divide-white/5">
            {filteredTransactions.map((tx) => {
              const config = getTypeConfig(tx.type);
              const Icon = config.icon;
              const isPositive = tx.amount > 0;
              
              return (
                <div key={tx.id} className="p-4 hover:bg-white/5 transition-colors">
                  <div className="flex items-center gap-4">
                    {/* Icon */}
                    <div 
                      className="w-10 h-10 rounded-xl flex items-center justify-center"
                      style={{ backgroundColor: `${config.bgColor}20` }}
                    >
                      <Icon className="w-5 h-5" style={{ color: config.color }} />
                    </div>
                    
                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-white">{config.label}</span>
                        <span 
                          className="px-2 py-0.5 rounded text-xs"
                          style={{ backgroundColor: `${config.bgColor}20`, color: config.color }}
                        >
                          {tx.reference_type}
                        </span>
                      </div>
                      <p className="text-sm text-[#71717A] truncate mt-1">{tx.description}</p>
                      {tx.reference_id && (
                        <p className="text-xs text-[#52525B] font-['JetBrains_Mono'] mt-1">
                          ID: {tx.reference_id.slice(0, 20)}...
                        </p>
                      )}
                    </div>
                    
                    {/* Amount & Date */}
                    <div className="text-right">
                      <div className={`font-bold font-['JetBrains_Mono'] ${isPositive ? "text-[#10B981]" : "text-[#EF4444]"}`}>
                        {isPositive ? "+" : ""}{tx.amount.toFixed(2)} {tx.currency || "USDT"}
                      </div>
                      {tx.commission > 0 && (
                        <div className="text-xs text-[#EF4444]">
                          −{tx.commission.toFixed(2)} USDT комиссия
                        </div>
                      )}
                      <div className="text-xs text-[#52525B] mt-1">
                        {new Date(tx.created_at).toLocaleString("ru-RU", {
                          day: "2-digit",
                          month: "2-digit",
                          year: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit"
                        })}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}


// ==================== TRADER WITHDRAW ====================
function TraderWithdraw_OLD() {
  const { token, user, refreshUserBalance } = useAuth();
  const [amount, setAmount] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [withdrawals, setWithdrawals] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchWithdrawals();
  }, []);

  const fetchWithdrawals = async () => {
    try {
      const response = await axios.get(`${API}/shop/withdrawals`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setWithdrawals(response.data || []);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleWithdraw = async () => {
    const amt = parseFloat(amount);
    if (isNaN(amt) || amt <= 0) {
      toast.error("Укажите корректную сумму");
      return;
    }
    const availableBalance = (user?.balance_usdt || 0) - (user?.frozen_usdt || 0);
    if (amt > availableBalance) {
      toast.error("Недостаточно средств");
      return;
    }
    setSubmitting(true);
    try {
      await axios.post(`${API}/shop/withdraw?amount=${amt}&method=to_balance&details=${encodeURIComponent("На баланс аккаунта")}`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(`${amt} USDT переведено на баланс аккаунта`);
      setAmount("");
      fetchWithdrawals();
      // Refresh user balance in context immediately
      await refreshUserBalance();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка вывода");
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusBadge = (status) => {
    const styles = { pending: "bg-[#F59E0B]/10 text-[#F59E0B]", completed: "bg-[#10B981]/10 text-[#10B981]", rejected: "bg-[#EF4444]/10 text-[#EF4444]", approved: "bg-[#10B981]/10 text-[#10B981]" };
    const labels = { pending: "Ожидает", completed: "Выполнено", rejected: "Отклонено", approved: "Выполнено" };
    return <span className={`px-2 py-1 rounded-lg text-xs ${styles[status] || styles.pending}`}>{labels[status] || status}</span>;
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Вывод средств</h1>

      <div className="bg-gradient-to-br from-[#7C3AED] to-[#6D28D9] rounded-2xl p-5">
        <div className="text-white/70 text-sm mb-1">Доступно для вывода</div>
        <div className="text-3xl font-bold text-white font-['JetBrains_Mono']">
          {((user?.balance_usdt || 0) - (user?.frozen_usdt || 0)).toFixed(2)} <span className="text-lg">USDT</span>
        </div>
        {(user?.frozen_usdt || 0) > 0 && (
          <div className="text-sm text-yellow-300 mt-1">
            +{(user?.frozen_usdt || 0).toFixed(2)} заморожено
          </div>
        )}
      </div>

      <div className="bg-[#121212] border border-white/5 rounded-2xl p-6 space-y-4">
        <h3 className="text-lg font-medium text-white">Вывод на баланс аккаунта</h3>
        <p className="text-[#71717A] text-sm">Средства будут переведены на ваш основной баланс аккаунта</p>
        <div className="space-y-2">
          <label className="text-sm text-[#A1A1AA]">Сумма USDT</label>
          <Input
            type="number"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0.00"
            className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl"
          />
        </div>
        <Button onClick={handleWithdraw} disabled={submitting} className="w-full bg-[#7C3AED] hover:bg-[#6D28D9] h-12 rounded-xl text-white">
          {submitting ? <Loader className="w-4 h-4 animate-spin" /> : "Вывести на баланс"}
        </Button>
      </div>

      {withdrawals.length > 0 && (
        <div className="bg-[#121212] border border-white/5 rounded-2xl overflow-hidden">
          <div className="p-4 border-b border-white/5">
            <h3 className="text-white font-medium">История выводов</h3>
          </div>
          <div className="divide-y divide-white/5">
            {withdrawals.map(w => (
              <div key={w.id} className="p-4 flex items-center justify-between">
                <div>
                  <div className="text-white font-medium font-['JetBrains_Mono']">{w.amount?.toFixed(2)} USDT</div>
                  <div className="text-xs text-[#52525B] mt-1">На баланс аккаунта</div>
                  <div className="text-xs text-[#52525B]">{new Date(w.created_at).toLocaleString("ru-RU")}</div>
                </div>
                {getStatusBadge(w.status)}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ==================== MY GUARANTOR DEALS ====================
function MyGuarantorDeals_OLD() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [deals, setDeals] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDeals();
  }, []);

  const fetchDeals = async () => {
    try {
      const response = await axios.get(`${API}/guarantor/deals`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setDeals(response.data || []);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    const styles = {
      pending_counterparty: "bg-[#F59E0B]/10 text-[#F59E0B]",
      pending_payment: "bg-[#3B82F6]/10 text-[#3B82F6]",
      funded: "bg-[#10B981]/10 text-[#10B981]",
      completed: "bg-[#10B981]/10 text-[#10B981]",
      disputed: "bg-[#EF4444]/10 text-[#EF4444]",
      cancelled: "bg-[#71717A]/10 text-[#71717A]"
    };
    const labels = {
      pending_counterparty: "Ожидает участника",
      pending_payment: "Ожидает оплаты",
      funded: "Средства внесены",
      completed: "Завершена",
      disputed: "Спор",
      cancelled: "Отменена"
    };
    return (
      <span className={`px-2 py-1 text-xs rounded-full font-medium ${styles[status] || styles.pending_counterparty}`}>
        {labels[status] || status}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-[#7C3AED] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white font-['Unbounded']">Мои гарант-сделки</h1>
          <p className="text-[#71717A]">Сделки с гарантом как покупатель или продавец</p>
        </div>
        <Link to="/guarantor/create">
          <Button className="bg-[#7C3AED] hover:bg-[#6D28D9] rounded-full" title="Создать новую сделку">
            <Plus className="w-4 h-4 mr-2" />
            Создать сделку
          </Button>
        </Link>
      </div>

      {deals.length === 0 ? (
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-12 text-center">
          <Shield className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
          <p className="text-[#71717A]">У вас пока нет гарант-сделок</p>
          <p className="text-sm text-[#52525B] mt-1">Создайте новую сделку или присоединитесь по ссылке</p>
          <Link to="/guarantor/create">
            <Button className="mt-4 bg-[#7C3AED] hover:bg-[#6D28D9] rounded-full px-6" title="Создать новую сделку">
              Создать сделку
            </Button>
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {deals.map((deal) => (
            <Link key={deal.id} to={`/guarantor/deal/${deal.id}`}>
              <div className="bg-[#121212] border border-white/5 hover:border-[#7C3AED]/30 rounded-xl p-5 transition-colors">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="text-white font-semibold">{deal.title}</div>
                    <div className="text-sm text-[#71717A]">
                      {deal.creator_role === 'buyer' ? 'Вы покупатель' : 'Вы продавец'}
                      {deal.counterparty_nickname && ` • с @${deal.counterparty_nickname}`}
                    </div>
                  </div>
                  {getStatusBadge(deal.status)}
                </div>
                <div className="flex items-center justify-between">
                  <div className="text-sm text-[#52525B]">
                    {new Date(deal.created_at).toLocaleDateString("ru-RU")}
                  </div>
                  <div className="text-lg font-bold text-[#10B981] font-['JetBrains_Mono']">
                    {deal.amount} {deal.currency}
                  </div>
                </div>
                {deal.invite_link && deal.status === 'pending_counterparty' && (
                  <div className="mt-3 p-2 bg-[#7C3AED]/10 rounded-lg">
                    <div className="text-xs text-[#A78BFA]">Ссылка для приглашения:</div>
                    <div className="text-sm text-white font-mono truncate">{window.location.origin}{deal.invite_link}</div>
                  </div>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}



// ==================== TRADER ACCOUNT ====================
function TraderAccount_OLD() {
  const { user, token } = useAuth();
  const [trader, setTrader] = useState(null);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    fetchTraderInfo();
  }, []);

  const fetchTraderInfo = async () => {
    try {
      const [traderRes, statsRes] = await Promise.all([
        axios.get(`${API}/traders/me`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/traders/stats`, { headers: { Authorization: `Bearer ${token}` } })
      ]);
      setTrader(traderRes.data);
      setStats(statsRes.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-[#7C3AED] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold text-white font-['Unbounded']">Аккаунт</h1>
        <p className="text-[#71717A]">Информация о вашем профиле</p>
      </div>

      {/* Profile Card */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl overflow-hidden">
        {/* Header with avatar */}
        <div className="bg-gradient-to-br from-[#7C3AED]/20 to-[#A855F7]/10 p-6 border-b border-white/5">
          <div className="flex items-center gap-4">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-[#7C3AED] to-[#A855F7] flex items-center justify-center text-white text-3xl font-bold">
              {(trader?.nickname || trader?.login || "U")[0].toUpperCase()}
            </div>
            <div>
              <h2 className="text-2xl font-bold text-white">@{trader?.nickname || trader?.login}</h2>
              <div className="flex items-center gap-2 text-[#71717A] text-sm mt-1">
                <Calendar className="w-4 h-4" />
                <span>Зарегистрирован: {trader?.created_at ? new Date(trader.created_at).toLocaleDateString("ru-RU", { day: 'numeric', month: 'long', year: 'numeric' }) : '—'}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Info Grid */}
        <div className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-[#0A0A0A] rounded-xl p-4">
              <div className="text-xs text-[#71717A] mb-1">Никнейм</div>
              <div className="text-white font-medium">@{trader?.nickname || '—'}</div>
            </div>
            <div className="bg-[#0A0A0A] rounded-xl p-4">
              <div className="text-xs text-[#71717A] mb-1">Логин</div>
              <div className="text-white font-medium">{trader?.login || '—'}</div>
            </div>
            <div className="bg-[#0A0A0A] rounded-xl p-4">
              <div className="text-xs text-[#71717A] mb-1">Баланс USDT</div>
              <div className="text-[#10B981] font-bold font-['JetBrains_Mono']">{trader?.balance_usdt?.toFixed(2) || '0.00'}</div>
            </div>
          </div>

          {/* Referral */}
          {trader?.referral_code && (
            <div className="bg-[#0A0A0A] rounded-xl p-4">
              <div className="text-xs text-[#71717A] mb-1">Реферальный код</div>
              <div className="flex items-center gap-2">
                <code className="text-[#F59E0B] font-['JetBrains_Mono']">{trader.referral_code}</code>
                <button 
                  onClick={() => {
                    navigator.clipboard.writeText(trader.referral_code);
                    toast.success('Скопировано!');
                  }}
                  className="p-1 hover:bg-white/10 rounded"
                >
                  <Copy className="w-4 h-4 text-[#71717A]" />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Stats Card */}
      {stats && (
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Статистика P2P</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-4 bg-[#0A0A0A] rounded-xl">
              <div className="text-2xl font-bold text-[#10B981]">{stats.salesCount || 0}</div>
              <div className="text-xs text-[#71717A]">Продаж</div>
            </div>
            <div className="text-center p-4 bg-[#0A0A0A] rounded-xl">
              <div className="text-2xl font-bold text-[#3B82F6]">{stats.purchasesCount || 0}</div>
              <div className="text-xs text-[#71717A]">Покупок</div>
            </div>
            <div className="text-center p-4 bg-[#0A0A0A] rounded-xl">
              <div className="text-lg font-bold text-[#10B981] font-['JetBrains_Mono']">{(stats.salesVolume || 0).toFixed(2)}</div>
              <div className="text-xs text-[#71717A]">Оборот продаж</div>
            </div>
            <div className="text-center p-4 bg-[#0A0A0A] rounded-xl">
              <div className="text-lg font-bold text-[#3B82F6] font-['JetBrains_Mono']">{(stats.purchasesVolume || 0).toFixed(2)}</div>
              <div className="text-xs text-[#71717A]">Оборот покупок</div>
            </div>
          </div>
        </div>
      )}

      {/* Shop Info if has shop */}
      {trader?.has_shop && trader?.shop_settings && (
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Store className="w-5 h-5 text-[#A78BFA]" />
            Мой магазин
          </h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[#71717A]">Название</span>
              <span className="text-white">{trader.shop_settings.shop_name || '—'}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[#71717A]">Комиссия платформы</span>
              <span className="text-[#F59E0B]">{trader.shop_settings.commission_rate || 5}%</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[#71717A]">Статус</span>
              <span className={`px-2 py-1 rounded text-xs ${trader.shop_settings.is_active ? 'bg-[#10B981]/10 text-[#10B981]' : 'bg-[#EF4444]/10 text-[#EF4444]'}`}>
                {trader.shop_settings.is_active ? 'Активен' : 'Неактивен'}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

*/

