import { useState, useEffect } from "react";
import axios from "axios";
import { useAuth, API } from "@/App";
import { CheckCircle, History, Loader, XCircle } from "lucide-react";

export default function MerchantHistory() {
  const { token } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("completed");

  useEffect(() => {
    fetchHistory();
  }, [filter]);

  const fetchHistory = async () => {
    try {
      const response = await axios.get(`${API}/merchant/trades`, {
        params: { type: "sell", status: filter },
        headers: { Authorization: `Bearer ${token}` }
      });
      setItems(response.data || []);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">История</h1>

      <div className="flex gap-2">
        {[
          { key: "completed", label: "Завершённые" },
          { key: "cancelled", label: "Отменённые" }
        ].map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-4 py-2 rounded-lg text-sm transition-colors ${
              filter === f.key ? "bg-white/10 text-white" : "text-[#71717A] hover:bg-white/5"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-20"><Loader className="w-8 h-8 animate-spin text-[#71717A]" /></div>
      ) : items.length === 0 ? (
        <div className="text-center py-20">
          <History className="w-16 h-16 text-[#52525B] mx-auto mb-4" />
          <h3 className="text-lg font-medium text-white mb-2">История пуста</h3>
          <p className="text-[#71717A]">{filter === "completed" ? "Нет завершённых сделок" : "Нет отменённых сделок"}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map(item => (
            <div key={item.id} className="bg-[#121212] border border-white/5 rounded-xl p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                    filter === "completed" ? "bg-[#10B981]/10" : "bg-[#71717A]/10"
                  }`}>
                    {filter === "completed" ? (
                      <CheckCircle className="w-6 h-6 text-[#10B981]" />
                    ) : (
                      <XCircle className="w-6 h-6 text-[#71717A]" />
                    )}
                  </div>
                  <div>
                    <div className="text-white font-medium">{item.client_nickname || "Клиент"}</div>
                    <div className="text-sm text-[#71717A]">
                      {item.amount} {item.currency || "USDT"} • {item.fiat_amount?.toFixed(2) || "—"} ₽
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className={`text-sm ${filter === "completed" ? "text-[#10B981]" : "text-[#71717A]"}`}>
                    {filter === "completed" ? "Завершено" : "Отменено"}
                  </div>
                  <div className="text-xs text-[#52525B]">
                    {new Date(item.created_at).toLocaleDateString("ru-RU")}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
