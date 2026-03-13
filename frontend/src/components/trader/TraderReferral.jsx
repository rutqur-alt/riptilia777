import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useAuth, API } from "@/App";
import axios from "axios";
import { TrendingUp, CheckCircle, Copy } from "lucide-react";

export default function TraderReferral() {
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
            <h3 className="text-white font-semibold text-lg mb-2">Пассивный доход без усилий</h3>
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
        <h3 className="text-white font-medium mb-4">Ваша реферальная ссылка</h3>
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
