import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { Plus, ListOrdered, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useAuth, API } from "@/App";

export default function TraderStats() {
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
            <Button className="bg-[#10B981] hover:bg-[#059669] text-white rounded-full px-6" data-testid="deposit-btn">
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
              <Button onClick={handleDeposit} className="w-full bg-[#10B981] hover:bg-[#059669] h-12 rounded-xl">
                Пополнить
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Balance Card */}
      <div className="bg-gradient-to-br from-[#7C3AED] to-[#A855F7] rounded-2xl p-6">
        <div className="text-white/70 text-sm mb-1">Ваш баланс</div>
        <div className="text-4xl font-bold text-white font-['JetBrains_Mono']" data-testid="trader-balance">
          {trader?.balance_usdt?.toFixed(2) || "0.00"} <span className="text-xl text-white/70">USDT</span>
        </div>
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
