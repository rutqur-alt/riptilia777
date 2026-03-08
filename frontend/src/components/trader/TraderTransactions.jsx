import { useState, useEffect } from "react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { 
  ListOrdered, TrendingUp, DollarSign, CheckCircle, ArrowUpRight, ArrowDownRight,
  Users, Store, ShoppingBag, History
} from "lucide-react";

export default function TraderTransactions() {
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
            <div className="text-xl font-bold text-[#EF4444]">{"\u2212"}{totalExpense.toFixed(2)} USDT</div>
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
                          {"\u2212"}{tx.commission.toFixed(2)} USDT комиссия
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
