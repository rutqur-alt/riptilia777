import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Store, MessageCircle, History, Package, ShoppingBag, Search, XCircle } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { Badge, LoadingSpinner, EmptyState, PageHeader } from "@/components/admin/SharedComponents";
import { MarketplaceChatHistoryModal } from "@/components/admin/MarketplaceChatHistoryModal";

const statusLabels = {
  pending_confirmation: "Ожидание",
  confirmed: "Подтверждён",
  completed: "Завершён",
  delivered: "Доставлен",
  cancelled: "Отменён",
  disputed: "Спор",
  refunded: "Возврат"
};

const statusColors = {
  pending_confirmation: "yellow",
  confirmed: "blue",
  completed: "green",
  delivered: "green",
  cancelled: "gray",
  disputed: "red",
  refunded: "orange"
};

export function MarketplaceOrders() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedOrderId, setSelectedOrderId] = useState(null);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => { fetchOrders(); }, []);

  const fetchOrders = async () => {
    try {
      const response = await axios.get(`${API}/admin/marketplace-history`, { 
        headers: { Authorization: `Bearer ${token}` } 
      });
      const data = response.data || [];
      setOrders(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error("Error fetching orders:", error);
      toast.error("Ошибка загрузки заказов");
    } finally {
      setLoading(false);
    }
  };

  const openChatHistory = (e, orderId) => {
    e.stopPropagation();
    setSelectedOrderId(orderId);
    setShowHistory(true);
  };

  const filtered = orders.filter(o => {
    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      const matchesId = o.id?.toLowerCase().includes(query);
      const matchesBuyer = o.buyer_nickname?.toLowerCase().includes(query) || o.buyer_login?.toLowerCase().includes(query);
      const matchesShop = o.shop_name?.toLowerCase().includes(query);
      const matchesProduct = o.product_name?.toLowerCase().includes(query);
      if (!matchesId && !matchesBuyer && !matchesShop && !matchesProduct) return false;
    }
    // Status filter
    if (filter === "active") return ["pending_confirmation", "confirmed"].includes(o.status);
    if (filter === "disputed") return o.status === "disputed";
    if (filter === "completed") return ["completed", "delivered"].includes(o.status);
    if (filter === "cancelled") return ["cancelled", "refunded"].includes(o.status);
    return true;
  });

  return (
    <div className="space-y-4" data-testid="marketplace-orders">
      <PageHeader title="Заказы маркетплейса" subtitle={`Всего: ${orders.length}`} />

      {/* Search + Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#52525B]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Поиск по ID, покупателю, магазину..."
            className="w-full bg-[#121212] border border-white/10 rounded-xl pl-10 pr-10 py-2 text-sm text-white placeholder-[#52525B] focus:outline-none focus:border-[#7C3AED]"
            data-testid="search-orders"
          />
          {searchQuery && (
            <button onClick={() => setSearchQuery("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#52525B] hover:text-white">
              <XCircle className="w-4 h-4" />
            </button>
          )}
        </div>
        <div className="flex gap-2 flex-wrap">
          {[
            { key: "all", label: "Все" },
            { key: "active", label: "Активные" },
            { key: "disputed", label: "Споры" },
            { key: "completed", label: "Завершённые" },
            { key: "cancelled", label: "Отменённые" },
        ].map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-3 py-1 rounded-lg text-xs ${filter === f.key ? "bg-[#10B981]/15 text-[#10B981]" : "text-[#71717A] hover:text-white"}`}
            data-testid={`filter-${f.key}`}
          >
            {f.label}
            {f.key === "disputed" && orders.filter(o => o.status === "disputed").length > 0 && (
              <span className="ml-1 bg-[#EF4444] text-white text-[9px] px-1 rounded-full">
                {orders.filter(o => o.status === "disputed").length}
              </span>
            )}
          </button>
        ))}
        </div>
      </div>

      {/* Results count */}
      {searchQuery && (
        <div className="text-xs text-[#71717A]">
          Найдено: {filtered.length} из {orders.length}
        </div>
      )}

      {loading ? <LoadingSpinner /> : filtered.length === 0 ? (
        <EmptyState icon={ShoppingBag} text={searchQuery ? "Ничего не найдено" : "Нет заказов"} />
      ) : (
        <div className="space-y-2">
          {filtered.slice(0, 50).map(order => (
            <div 
              key={order.id} 
              className={`bg-[#121212] border rounded-xl p-3 transition-all ${
                order.status === "disputed" 
                  ? "border-[#EF4444]/30" 
                  : "border-white/5"
              }`}
              data-testid={`order-${order.id}`}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <Package className="w-4 h-4 text-[#7C3AED]" />
                  <span className="text-white text-xs font-medium">#{order.id?.slice(0, 8)}</span>
                  <Badge color={statusColors[order.status]}>{statusLabels[order.status] || order.status}</Badge>
                  {order.messages_count > 0 && (
                    <span className="text-[#52525B] text-[10px]">
                      💬 {order.messages_count}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {/* Кнопка История чата */}
                  <button
                    onClick={(e) => openChatHistory(e, order.id)}
                    className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] bg-[#7C3AED]/10 text-[#7C3AED] hover:bg-[#7C3AED]/20 transition-colors"
                    data-testid={`history-${order.id}`}
                  >
                    <History className="w-3 h-3" />
                    История чата
                  </button>
                  <span className="text-[#52525B] text-[10px]">{new Date(order.created_at).toLocaleString("ru-RU")}</span>
                </div>
              </div>
              <div className="text-[#A1A1AA] text-xs">
                <span className="text-white">{order.product_name || 'Товар'}</span>
                <span className="text-[#52525B]"> • </span>
                <span className="text-[#10B981] font-mono">{order.total_price} USDT</span>
                <span className="text-[#52525B]"> × {order.quantity || 1} шт.</span>
                {order.buyer_nickname && <span className="text-[#52525B]"> • Покупатель: {order.buyer_nickname}</span>}
                {order.seller_nickname && <span className="text-[#52525B]"> • Продавец: {order.seller_nickname}</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal для истории чата */}
      <MarketplaceChatHistoryModal
        isOpen={showHistory}
        onClose={() => setShowHistory(false)}
        orderId={selectedOrderId}
      />
    </div>
  );
}

export default MarketplaceOrders;
