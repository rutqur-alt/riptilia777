import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { 
  Users, Copy, Link2, Wallet, ArrowDownToLine, 
  TrendingUp, Gift, Clock
} from 'lucide-react';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const Referrals = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [withdrawing, setWithdrawing] = useState(false);

  useEffect(() => {
    fetchReferralData();
  }, []);

  const fetchReferralData = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/referral`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const json = await res.json();
        setData(json);
      }
    } catch (error) {
      toast.error('Ошибка загрузки данных');
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('Скопировано!');
  };

  const handleWithdraw = async () => {
    setWithdrawing(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/referral/withdraw`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const json = await res.json();
      if (res.ok) {
        toast.success(json.message);
        fetchReferralData();
      } else {
        toast.error(json.detail || 'Ошибка вывода');
      }
    } catch (error) {
      toast.error('Ошибка вывода');
    } finally {
      setWithdrawing(false);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('ru-RU', {
      day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit'
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 text-white p-6">
        <div className="flex items-center justify-center h-64">
          <div className="w-8 h-8 border-4 border-purple-500 border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  const referralLink = data?.referral_code 
    ? `${window.location.origin}/auth?ref=${data.referral_code}`
    : `${window.location.origin}/auth`;
  const totalReferrals = data?.level_stats?.reduce((acc, l) => acc + l.count, 0) || 0;

  return (
    <div className="min-h-screen bg-zinc-950 text-white p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Gift className="w-7 h-7 text-purple-400" />
            Реферальная программа
          </h1>
          <p className="text-zinc-400 mt-1">
            Приглашайте друзей и получайте % от их заработка
          </p>
        </div>

        {/* Referral Link Card */}
        <Card className="bg-gradient-to-br from-purple-500/20 to-cyan-500/20 border-purple-500/30">
          <CardContent className="p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-xl bg-purple-500/20 flex items-center justify-center">
                <Link2 className="w-6 h-6 text-purple-400" />
              </div>
              <div>
                <div className="text-sm text-zinc-400">Ваша реферальная ссылка</div>
                <div className="text-lg font-bold text-purple-400">Код: {data?.referral_code}</div>
              </div>
            </div>
            
            <div className="flex gap-2">
              <input
                type="text"
                value={referralLink}
                readOnly
                className="flex-1 px-4 py-3 bg-zinc-900/50 border border-zinc-700 rounded-lg text-sm font-mono"
              />
              <Button
                onClick={() => copyToClipboard(referralLink)}
                className="bg-purple-500 hover:bg-purple-600"
                data-testid="copy-referral-link"
              >
                <Copy className="w-4 h-4" />
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Balance */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="p-5">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-amber-500/20 flex items-center justify-center">
                  <Wallet className="w-5 h-5 text-amber-400" />
                </div>
                <div>
                  <div className="text-xs text-zinc-500">Реферальный баланс</div>
                  <div className="text-xl font-bold text-amber-400">
                    {data?.referral_balance_usdt?.toFixed(4) || '0.0000'} USDT
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Total Earned */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="p-5">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center">
                  <TrendingUp className="w-5 h-5 text-emerald-400" />
                </div>
                <div>
                  <div className="text-xs text-zinc-500">Всего заработано</div>
                  <div className="text-xl font-bold text-emerald-400">
                    {data?.total_earned_usdt?.toFixed(4) || '0.0000'} USDT
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Total Referrals */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="p-5">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
                  <Users className="w-5 h-5 text-blue-400" />
                </div>
                <div>
                  <div className="text-xs text-zinc-500">Всего рефералов</div>
                  <div className="text-xl font-bold text-blue-400">
                    {totalReferrals}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Withdraw Card */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="p-5">
              <Button
                onClick={handleWithdraw}
                disabled={withdrawing || (data?.referral_balance_usdt || 0) < (data?.settings?.min_withdrawal_usdt || 1)}
                className="w-full bg-gradient-to-r from-purple-500 to-cyan-500 hover:opacity-90"
                data-testid="referral-withdraw-btn"
               title="Вывести средства">
                {withdrawing ? (
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <>
                    <ArrowDownToLine className="w-5 h-5 mr-2" />
                    Вывести
                  </>
                )}
              </Button>
              <div className="text-xs text-zinc-500 text-center mt-2">
                Мин. сумма: {data?.settings?.min_withdrawal_usdt || 1} USDT
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Levels & Percentages */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-lg">Уровни и проценты</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {[
                { level: 1, percent: data?.settings?.level1_percent || 5, color: 'purple', desc: 'Ваши прямые рефералы' },
                { level: 2, percent: data?.settings?.level2_percent || 3, color: 'cyan', desc: 'Рефералы ваших рефералов' },
                { level: 3, percent: data?.settings?.level3_percent || 1, color: 'blue', desc: '3-й уровень' }
              ].map((item) => {
                const levelData = data?.level_stats?.find(l => l.level === item.level);
                const colors = {
                  purple: 'from-purple-500/20 to-purple-500/5 border-purple-500/30 text-purple-400',
                  cyan: 'from-cyan-500/20 to-cyan-500/5 border-cyan-500/30 text-cyan-400',
                  blue: 'from-blue-500/20 to-blue-500/5 border-blue-500/30 text-blue-400'
                };
                
                return (
                  <div 
                    key={item.level}
                    className={`p-4 rounded-xl bg-gradient-to-br border ${colors[item.color]}`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">Уровень {item.level}</span>
                      <span className="text-2xl font-bold">{item.percent}%</span>
                    </div>
                    <div className="text-xs text-zinc-400">{item.desc}</div>
                    <div className="mt-2 flex items-center gap-1">
                      <Users className="w-4 h-4" />
                      <span className="font-medium">{levelData?.count || 0}</span>
                      <span className="text-zinc-500">человек</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* History */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Clock className="w-5 h-5" />
              История начислений
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data?.history?.length > 0 ? (
              <div className="space-y-2 max-h-[400px] overflow-y-auto">
                {data.history.map((item, idx) => (
                  <div 
                    key={idx}
                    className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                        item.level === 1 ? 'bg-purple-500/20 text-purple-400' :
                        item.level === 2 ? 'bg-cyan-500/20 text-cyan-400' :
                        'bg-blue-500/20 text-blue-400'
                      }`}>
                        L{item.level}
                      </div>
                      <div>
                        <div className="font-medium">{item.from_nickname}</div>
                        <div className="text-xs text-zinc-500">
                          {item.percent}% от заработка
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-bold text-emerald-400">+{item.bonus_usdt?.toFixed(4)} USDT</div>
                      <div className="text-xs text-zinc-500">{formatDate(item.created_at)}</div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-zinc-500">
                <Gift className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>Пока нет начислений</p>
                <p className="text-sm mt-1">Поделитесь реферальной ссылкой чтобы начать зарабатывать!</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Referrals;
