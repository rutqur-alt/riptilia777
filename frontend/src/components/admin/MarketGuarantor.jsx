import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Shield, ChevronRight, CheckCircle, XCircle, ShoppingBag, ArrowRightLeft, MessageCircle } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { Badge, LoadingSpinner, EmptyState, PageHeader } from "@/components/admin/SharedComponents";

export function MarketGuarantor() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [resolving, setResolving] = useState(null);
  const [showResolveModal, setShowResolveModal] = useState(null);
  const [resolveReason, setResolveReason] = useState("");

  useEffect(() => { fetchTrades(); }, [filter]);

  const fetchTrades = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/msg/admin/guarantor-orders?include_resolved=true`, 
        { headers: { Authorization: `Bearer ${token}` } }
      );
      let data = response.data || [];
      
      if (filter === "active") {
        data = data.filter(t => ["pending_confirmation", "pending", "funded", "pending_counterparty", "pending_payment"].includes(t.status));
      } else if (filter === "completed") {
        data = data.filter(t => ["completed", "released", "refunded", "partially_refunded"].includes(t.status));
      } else if (filter === "disputed") {
        data = data.filter(t => t.status === "disputed");
      } else if (filter === "marketplace") {
        data = data.filter(t => t.deal_type === "marketplace");
      } else if (filter === "p2p") {
        data = data.filter(t => t.deal_type === "p2p");
      }
      
      setTrades(data);
    } catch (error) {
      console.error("Error fetching guarantor trades:", error);
      setTrades([]);
    } finally {
      setLoading(false);
    }
  };

  const openChat = (trade) => {
    const convId = trade.conversation_id || trade.id;
    navigate("/admin/messages", { state: { category: "guarantor", tradeId: convId } });
  };

  const handleResolve = async (trade, resolution) => {
    setResolving(trade.id);
    try {
      const endpoint = trade.deal_type === "marketplace"
        ? `${API}/msg/admin/marketplace-guarantor/${trade.id}/resolve`
        : `${API}/msg/admin/guarantor-orders/${trade.id}/resolve`;
      
      await axios.post(endpoint, {
        resolution,
        reason: resolveReason
      }, { headers: { Authorization: `Bearer ${token}` } });
      
      toast.success(resolution === "complete" ? "Сделка подтверждена" : "Средства возвращены покупателю");
      setShowResolveModal(null);
      setResolveReason("");
      fetchTrades();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка при обработке сделки");
    } finally {
      setResolving(null);
    }
  };

  const getStatusBadge = (status) => {
    const statusMap = {
      pending_confirmation: { color: "blue", label: "Ожидает подтверждения" },
      pending: { color: "blue", label: "Ожидает" },
      pending_counterparty: { color: "yellow", label: "Ожидает контрагента" },
      pending_payment: { color: "yellow", label: "Ожидает оплаты" },
      funded: { color: "blue", label: "Оплачена" },
      completed: { color: "green", label: "Завершена" },
      released: { color: "green", label: "Средства выданы" },
      refunded: { color: "red", label: "Возврат" },
      partially_refunded: { color: "orange", label: "Частичный возврат" },
      disputed: { color: "red", label: "Спор" },
    };
    const s = statusMap[status] || { color: "gray", label: status };
    return <Badge color={s.color}>{s.label}</Badge>;
  };

  const getDealTypeIcon = (type) => {
    if (type === "marketplace") return <ShoppingBag className="w-4 h-4 text-[#8B5CF6]" />;
    return <ArrowRightLeft className="w-4 h-4 text-[#10B981]" />;
  };

  const canResolve = (trade) => {
    return ["pending_confirmation", "pending", "funded", "disputed"].includes(trade.status);
  };

  const activeCount = trades.filter(t => ["pending_confirmation", "pending", "funded", "pending_counterparty", "pending_payment"].includes(t.status)).length;
  const disputedCount = trades.filter(t => t.status === "disputed").length;
  const marketplaceCount = trades.filter(t => t.deal_type === "marketplace").length;
  const p2pCount = trades.filter(t => t.deal_type === "p2p").length;

  return (
    <div className="space-y-4" data-testid="market-guarantor">
      <PageHeader title="Гарант-сделки" subtitle="Управление всеми гарант-сделками (P2P и Маркетплейс)" />

      <div className="flex gap-2 flex-wrap">
        {[
          { key: "all", label: "Все", count: trades.length },
          { key: "active", label: "Активные", count: activeCount },
          { key: "disputed", label: "Споры", count: disputedCount },
          { key: "marketplace", label: "Маркетплейс", count: marketplaceCount },
          { key: "p2p", label: "P2P", count: p2pCount },
          { key: "completed", label: "Завершены" },
        ].map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-3 py-1 rounded-lg text-xs flex items-center gap-1 ${filter === f.key ? "bg-[#7C3AED]/15 text-[#7C3AED]" : "text-[#71717A] hover:text-white"}`}
          >
            {f.label}
            {f.count > 0 && (
              <span className={`text-[10px] px-1 rounded-full ${filter === f.key ? "bg-[#7C3AED]/30" : "bg-white/10"}`}>
                {f.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {loading ? <LoadingSpinner /> : trades.length === 0 ? (
        <EmptyState icon={Shield} text="Нет гарант-сделок" />
      ) : (
        <div className="space-y-3">
          {trades.map(trade => (
            <div key={trade.id} className="bg-[#121212] border border-white/5 rounded-xl p-4">
              <div className="flex items-center justify-between">
                <div className="flex-1 cursor-pointer" onClick={() => openChat(trade)}>
                  <div className="flex items-center gap-2 mb-1">
                    {getDealTypeIcon(trade.deal_type)}
                    <span className="text-white font-semibold text-sm">
                      {trade.title || trade.data?.product_name || "Гарант-сделка"}
                    </span>
                    {getStatusBadge(trade.status)}
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-[#71717A]">
                      {trade.deal_type === "marketplace" ? "Маркетплейс" : "P2P"}
                    </span>
                  </div>
                  <div className="text-[#A1A1AA] text-xs">
                    {trade.data?.total_price || trade.data?.amount || "—"} USDT
                    {trade.data?.guarantor_fee > 0 && ` (+ ${trade.data.guarantor_fee.toFixed(2)} комиссия гаранта)`}
                    {" • "}Покупатель: @{trade.data?.buyer_nickname || "—"}
                    {" • "}Продавец: @{trade.data?.seller_nickname || "—"}
                  </div>
                  <div className="text-[#71717A] text-xs mt-1">
                    ID: {trade.id?.slice(0, 8)}... • {trade.created_at ? new Date(trade.created_at).toLocaleString("ru-RU") : ""}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {canResolve(trade) && (
                    <>
                      <button
                        onClick={(e) => { e.stopPropagation(); setShowResolveModal({ trade, action: "complete" }); }}
                        className="p-2 rounded-lg bg-[#10B981]/10 text-[#10B981] hover:bg-[#10B981]/20 transition-colors"
                        title="Подтвердить сделку"
                      >
                        <CheckCircle className="w-4 h-4" />
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); setShowResolveModal({ trade, action: "refund" }); }}
                        className="p-2 rounded-lg bg-[#EF4444]/10 text-[#EF4444] hover:bg-[#EF4444]/20 transition-colors"
                        title="Возврат покупателю"
                      >
                        <XCircle className="w-4 h-4" />
                      </button>
                    </>
                  )}
                  <button
                    onClick={() => openChat(trade)}
                    className="p-2 rounded-lg bg-[#7C3AED]/10 text-[#7C3AED] hover:bg-[#7C3AED]/20 transition-colors"
                    title="Открыть чат"
                  >
                    <MessageCircle className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Resolve Modal */}
      {showResolveModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setShowResolveModal(null)}>
          <div className="bg-[#1a1a1a] border border-white/10 rounded-xl p-6 w-full max-w-md" onClick={e => e.stopPropagation()}>
            <h3 className="text-white font-bold text-lg mb-2">
              {showResolveModal.action === "complete" ? "Подтвердить сделку" : "Возврат средств"}
            </h3>
            <p className="text-[#A1A1AA] text-sm mb-4">
              {showResolveModal.action === "complete"
                ? "Средства будут переведены продавцу. Это действие необратимо."
                : "Средства будут возвращены покупателю. Это действие необратимо."}
            </p>
            <div className="mb-4">
              <div className="text-[#71717A] text-xs mb-1">Сделка: {showResolveModal.trade.title}</div>
              <div className="text-white text-sm">
                Сумма: {showResolveModal.trade.data?.total_price || showResolveModal.trade.data?.amount || 0} USDT
              </div>
            </div>
            <textarea
              value={resolveReason}
              onChange={e => setResolveReason(e.target.value)}
              placeholder="Причина решения (необязательно)"
              className="w-full bg-[#121212] border border-white/10 rounded-lg p-3 text-white text-sm mb-4 resize-none"
              rows={3}
            />
            <div className="flex gap-2">
              <button
                onClick={() => { setShowResolveModal(null); setResolveReason(""); }}
                className="flex-1 px-4 py-2 rounded-lg bg-white/5 text-[#A1A1AA] hover:bg-white/10 text-sm"
              >
                Отмена
              </button>
              <button
                onClick={() => handleResolve(showResolveModal.trade, showResolveModal.action)}
                disabled={resolving === showResolveModal.trade.id}
                className={`flex-1 px-4 py-2 rounded-lg text-white text-sm ${
                  showResolveModal.action === "complete"
                    ? "bg-[#10B981] hover:bg-[#059669]"
                    : "bg-[#EF4444] hover:bg-[#DC2626]"
                } disabled:opacity-50`}
              >
                {resolving === showResolveModal.trade.id ? "Обработка..." :
                  showResolveModal.action === "complete" ? "Подтвердить" : "Вернуть средства"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default MarketGuarantor;
