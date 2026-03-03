import React, { useState, useEffect } from 'react';
import { useAuth, api } from '@/lib/auth';
import DashboardLayout from '@/components/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import { 
  Users, Copy, Link2, Wallet, ArrowDownToLine, 
  TrendingUp, Gift, ChevronRight, Clock
} from 'lucide-react';

const Referrals = () => {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [withdrawing, setWithdrawing] = useState(false);

  useEffect(() => {
    fetchReferralData();
  }, []);

  const fetchReferralData = async () => {
    try {
      const res = await api.get('/user/referral');
      setData(res.data);
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
      const res = await api.post('/user/referral/withdraw');
      toast.success(res.data.message);
      fetchReferralData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка вывода');
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
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <div className="w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin" />
        </div>
      </DashboardLayout>
    );
  }

  const referralLink = data?.referral_code 
    ? `${window.location.origin}/register?ref=${data.referral_code}`
    : `${window.location.origin}/register`;
  const totalReferrals = data?.level_stats?.reduce((acc, l) => acc + l.count, 0) || 0;

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Gift className="w-7 h-7 text-emerald-400" />
            Реферальная программа
          </h1>
          <p className="text-zinc-400 mt-1">
            Приглашайте друзей и получайте % от их заработка
          </p>
        </div>

        {/* Referral Link Card */}
        <Card className="bg-gradient-to-br from-emerald-500/20 to-cyan-500/20 border-emerald-500/30">
          <CardContent className="p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-xl bg-emerald-500/20 flex items-center justify-center">
                <Link2 className="w-6 h-6 text-emerald-400" />
              </div>
              <div>
                <div className="text-sm text-zinc-400">Ваша реферальная ссылка</div>
                <div className="text-lg font-bold text-emerald-400">Код: {data?.referral_code}</div>
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
                className="bg-emerald-500 hover:bg-emerald-600"
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
                  <div className="text-xl font-bold">{totalReferrals}</div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Withdraw Button */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="p-5">
              <Button
                onClick={handleWithdraw}
                disabled={withdrawing || (data?.referral_balance_usdt || 0) < (data?.settings?.min_withdrawal_usdt || 1)}
                className="w-full h-full bg-gradient-to-r from-emerald-500 to-cyan-500 hover:from-emerald-600 hover:to-cyan-600"
                data-testid="referral-withdraw-btn"
              >
                {withdrawing ? (
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <>
                    <ArrowDownToLine className="w-5 h-5 mr-2" />
                    Вывести на кошелёк
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
                { level: 1, percent: data?.settings?.level1_percent, color: 'emerald', desc: 'Ваши прямые рефералы' },
                { level: 2, percent: data?.settings?.level2_percent, color: 'cyan', desc: 'Рефералы ваших рефералов' },
                { level: 3, percent: data?.settings?.level3_percent, color: 'blue', desc: '3-й уровень' }
              ].map((item) => {
                const levelData = data?.level_stats?.find(l => l.level === item.level);
                const colors = {
                  emerald: 'from-emerald-500/20 to-emerald-500/5 border-emerald-500/30 text-emerald-400',
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
                        item.level === 1 ? 'bg-emerald-500/20 text-emerald-400' :
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
    </DashboardLayout>
  );
};

export default Referrals;
