import { useState, useEffect } from "react";
import axios from "axios";
import { useAuth, API } from "@/App";
import { ArrowDownRight, ArrowUpRight, History, Loader } from "lucide-react";

export default function MerchantTransactions() {
  const { token } = useAuth();
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTransactions();
  }, []);

  const fetchTransactions = async () => {
    try {
      const response = await axios.get(`${API}/merchants/transactions`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTransactions(response.data || []);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Транзакции</h1>

      {loading ? (
        <div className="flex justify-center py-20"><Loader className="w-8 h-8 animate-spin text-[#71717A]" /></div>
      ) : transactions.length === 0 ? (
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-6 text-center py-20">
          <History className="w-16 h-16 text-[#52525B] mx-auto mb-4" />
          <p className="text-[#71717A]">История транзакций пуста</p>
        </div>
      ) : (
        <div className="space-y-3">
          {transactions.map(tx => (
            <div key={tx.id} className="bg-[#121212] border border-white/5 rounded-xl p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                    tx.amount >= 0 ? "bg-[#10B981]/10" : "bg-[#EF4444]/10"
                  }`}>
                    {tx.amount >= 0 ? (
                      <ArrowDownRight className="w-5 h-5 text-[#10B981]" />
                    ) : (
                      <ArrowUpRight className="w-5 h-5 text-[#EF4444]" />
                    )}
                  </div>
                  <div>
                    <div className="text-white text-sm font-medium">{tx.description}</div>
                    <div className="text-xs text-[#52525B]">
                      {new Date(tx.created_at).toLocaleString("ru-RU")}
                    </div>
                  </div>
                </div>
                <div className={`font-medium font-['JetBrains_Mono'] ${
                  tx.amount >= 0 ? "text-[#10B981]" : "text-[#EF4444]"
                }`}>
                  {tx.amount >= 0 ? "+" : ""}{tx.amount?.toFixed(2)} USDT
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
