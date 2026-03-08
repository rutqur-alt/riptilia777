import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { useAuth, API } from "@/App";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { History, Loader } from "lucide-react";

export default function MerchantWithdraw() {
  const { token, user, refreshUserBalance } = useAuth();
  const [withdrawals, setWithdrawals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [amount, setAmount] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchWithdrawals();
  }, []);

  const fetchWithdrawals = async () => {
    try {
      const response = await axios.get(`${API}/merchants/withdrawals`, {
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
      await axios.post(`${API}/merchants/withdrawals`, { amount: amt, address: "to_balance" }, {
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

      <div className="bg-gradient-to-br from-[#F97316] to-[#EA580C] rounded-2xl p-5">
        <div className="text-white/70 text-sm mb-1">Доступно для вывода</div>
        <div className="text-3xl font-bold text-white font-['JetBrains_Mono']">
          {((user?.balance_usdt || 0) - (user?.frozen_usdt || 0)).toFixed(2)} <span className="text-lg">USDT</span>
        </div>
        {(user?.frozen_usdt || 0) > 0 && (
          <div className="text-sm text-yellow-200 mt-1">
            +{(user?.frozen_usdt || 0).toFixed(2)} заморожено
          </div>
        )}
      </div>

      <div className="bg-[#121212] border border-white/5 rounded-2xl p-6 space-y-4">
        <h3 className="text-lg font-medium text-white">Вывод на баланс аккаунта</h3>
        <p className="text-[#71717A] text-sm">Средства будут переведены на ваш основной баланс аккаунта</p>
        <div className="space-y-2">
          <Label className="text-[#A1A1AA]">Сумма USDT</Label>
          <Input
            type="number"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0.00"
            className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl"
          />
        </div>
        <Button onClick={handleWithdraw} disabled={submitting} className="w-full bg-[#F97316] hover:bg-[#EA580C] h-12 rounded-xl">
          {submitting ? <Loader className="w-4 h-4 animate-spin" /> : "Вывести на баланс"}
        </Button>
      </div>

      {/* Withdrawal History */}
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
