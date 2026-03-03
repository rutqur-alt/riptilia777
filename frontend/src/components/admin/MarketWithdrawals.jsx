import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { ArrowDownRight, CheckCircle, XCircle } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { Badge, LoadingSpinner, EmptyState, PageHeader } from "@/components/admin/SharedComponents";

export function MarketWithdrawals() {
  const { token } = useAuth();
  const [withdrawals, setWithdrawals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("pending");

  useEffect(() => { fetchWithdrawals(); }, [filter]);

  const fetchWithdrawals = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/admin/withdrawals?status_filter=${filter}`, 
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const data = response.data;
      const allWithdrawals = [
        ...(data.trader_withdrawals || []).map(w => ({...w, source: 'trader'})),
        ...(data.merchant_withdrawals || []).map(w => ({...w, source: 'merchant'}))
      ];
      setWithdrawals(allWithdrawals);
    } catch (error) {
      toast.error("Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  };

  const handleProcess = async (id, decision) => {
    try {
      await axios.post(`${API}/admin/withdrawals/${id}/process?decision=${decision}`, {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(decision === "approve" ? "Одобрено" : "Отклонено");
      fetchWithdrawals();
    } catch (error) {
      toast.error("Ошибка");
    }
  };

  return (
    <div className="space-y-4" data-testid="market-withdrawals">
      <PageHeader title="Выводы средств" subtitle="Заявки на вывод" />

      <div className="flex gap-2">
        {["pending", "completed", "rejected", "all"].map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1 rounded-lg text-xs ${filter === f ? "bg-[#10B981]/15 text-[#10B981]" : "text-[#71717A] hover:text-white"}`}
          >
            {f === "pending" ? "Ожидают" : f === "completed" ? "Выполнены" : f === "rejected" ? "Отклонены" : "Все"}
          </button>
        ))}
      </div>

      {loading ? <LoadingSpinner /> : withdrawals.length === 0 ? (
        <EmptyState icon={ArrowDownRight} text="Нет заявок" />
      ) : (
        <div className="space-y-3">
          {withdrawals.map(w => (
            <div key={w.id} className="bg-[#121212] border border-white/5 rounded-xl p-4">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-white font-semibold">{w.amount} USDT</span>
                    <Badge color={w.status === "pending" ? "yellow" : w.status === "completed" ? "green" : "red"}>
                      {w.status === "pending" ? "Ожидает" : w.status === "completed" ? "Выполнен" : "Отклонён"}
                    </Badge>
                  </div>
                  <div className="text-[#A1A1AA] text-xs">@{w.seller_nickname} • {w.method}</div>
                  <div className="bg-[#0A0A0A] rounded-lg p-2 mt-2 text-[10px] font-mono text-white break-all">{w.details}</div>
                </div>
                {w.status === "pending" && (
                  <div className="flex gap-2">
                    <Button size="sm" onClick={() => handleProcess(w.id, "approve")} className="bg-[#10B981] hover:bg-[#059669] text-white text-xs h-7">
                      <CheckCircle className="w-3 h-3 mr-1" /> Одобрить
                    </Button>
                    <Button size="sm" onClick={() => handleProcess(w.id, "reject")} variant="ghost" className="text-[#EF4444] text-xs h-7">
                      <XCircle className="w-3 h-3 mr-1" /> Отклонить
                    </Button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default MarketWithdrawals;
