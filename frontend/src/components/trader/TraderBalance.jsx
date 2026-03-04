import { useState, useEffect, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAuth, API } from "@/App";
import { useWebSocket } from "@/hooks/useWebSocket";
import axios from "axios";
import { toast } from "sonner";
import { 
  ArrowUpRight, CreditCard, TrendingUp, AlertTriangle, 
  Bell, Clock, CheckCircle, ListOrdered, Plus, MessageCircle, DollarSign, Users, XCircle
} from "lucide-react";

// Icon mapping for notification types
const NOTIF_ICONS = {
  trade_created: TrendingUp,
  trade_completed: CheckCircle,
  trade_cancelled: XCircle,
  payout_order_created: DollarSign,
  new_message: MessageCircle,
  broadcast: Bell,
  new_referral: Users,
  default: Bell
};

export default function TraderBalance() {
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const [trader, setTrader] = useState(null);
  const [activeTrades, setActiveTrades] = useState({ sales: [], purchases: [] });
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [baseRate, setBaseRate] = useState(null);

  // WebSocket: listen for new trades, trade status updates, and new notifications
  const onWsMessage = useCallback((data) => {
    if (data.type === "new_trade") {
      // New trade created for this trader - show notification and refresh
      toast.info(`Новая сделка #${data.trade_id?.slice(-6)} на ${data.amount_usdt} USDT`, {
        duration: 10000,
        action: {
          label: "Открыть",
          onClick: () => window.location.href = `/trader/sales/${data.trade_id}`
        }
      });
      // Refresh data to show the new trade
      fetchData();
    } else if (data.type === "trade_resolved" || data.type === "status_update") {
      // Trade status changed - refresh
      fetchData();
    } else if (data.type === "new_notification" && data.notification) {
      // Real-time notification - add to list
      setNotifications(prev => [data.notification, ...prev.slice(0, 4)]);
    }
  }, []);

  useWebSocket(
    user ? `/ws/user/${user.id}` : null,
    onWsMessage,
    { enabled: !!user }
  );

  useEffect(() => {
    fetchData();
    // Reduced polling since we have WebSocket
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      const [traderRes, statsRes, salesRes, purchasesRes, notifsRes, rateRes] = await Promise.all([
        axios.get(`${API}/traders/me`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/traders/stats`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/trades/sales/active`, { headers: { Authorization: `Bearer ${token}` } }).catch(() => ({ data: [] })),
        axios.get(`${API}/trades/purchases/active`, { headers: { Authorization: `Bearer ${token}` } }).catch(() => ({ data: [] })),
        axios.get(`${API}/event-notifications?limit=5`, { headers: { Authorization: `Bearer ${token}` } }).catch(() => ({ data: [] })),
        axios.get(`${API}/payout-settings/public`).catch(() => ({ data: { base_rate: null } }))
      ]);
      setTrader({ ...traderRes.data, ...statsRes.data });
      setActiveTrades({ 
        sales: salesRes.data.filter(t => t.status === 'paid' || t.status === 'disputed' || t.status === 'pending'),
        purchases: purchasesRes.data.filter(t => t.status === 'pending')
      });
      setNotifications(notifsRes.data || []);
      setBaseRate(rateRes.data?.base_rate || null);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };
  
  const handleNotificationClick = async (notif) => {
    try {
      await axios.post(
        `${API}/event-notifications/mark-read`,
        { notification_id: notif.id },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setNotifications(prev => prev.filter(n => n.id !== notif.id));
      if (notif.link) {
        navigate(notif.link);
      }
    } catch (e) {
      console.error(e);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-[#7C3AED] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Quick Stats Row */}
      <div className="grid sm:grid-cols-3 gap-4">
        {/* Base Rate Card */}
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[#71717A] text-sm">Базовый курс</span>
            <DollarSign className="w-4 h-4 text-[#3B82F6]" />
          </div>
          <div className="text-xl font-bold text-[#3B82F6] font-['JetBrains_Mono']">
            {baseRate ? `${baseRate.toFixed(2)} ₽` : "—"}
          </div>
          <div className="text-xs text-[#71717A]">USDT/RUB</div>
        </div>

        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[#71717A] text-sm">Продажи</span>
            <TrendingUp className="w-4 h-4 text-[#10B981]" />
          </div>
          <div className="text-xl font-bold text-white">{trader?.salesCount || 0}</div>
          <div className="text-xs text-[#10B981] font-['JetBrains_Mono']">{(trader?.salesVolume || 0).toFixed(0)} USDT</div>
        </div>

        <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[#71717A] text-sm">Покупки</span>
            <CheckCircle className="w-4 h-4 text-[#7C3AED]" />
          </div>
          <div className="text-xl font-bold text-white">{trader?.purchasesCount || 0}</div>
          <div className="text-xs text-[#7C3AED] font-['JetBrains_Mono']">{(trader?.purchasesVolume || 0).toFixed(0)} USDT</div>
        </div>
      </div>

      {/* Stats Row */}
      <div className="bg-[#121212] border border-white/5 rounded-2xl p-5">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[#71717A] text-sm">Завершённых сделок</span>
          <CheckCircle className="w-4 h-4 text-[#10B981]" />
        </div>
        <div className="text-xl font-bold text-white">{(trader?.salesCount || 0) + (trader?.purchasesCount || 0)}</div>
        <div className="text-xs text-[#71717A]">всего</div>
      </div>

      {/* Quick Actions */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <Link to="/trader/offers">
          <div className="bg-[#121212] border border-white/5 hover:border-[#7C3AED]/50 rounded-xl p-4 transition-colors h-full">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-[#7C3AED]/10 flex items-center justify-center">
                <ListOrdered className="w-4 h-4 text-[#7C3AED]" />
              </div>
              <div>
                <div className="text-white font-medium text-sm">Мои объявления</div>
                <div className="text-xs text-[#71717A]">Управление офферами</div>
              </div>
            </div>
          </div>
        </Link>
        <Link to="/trader/sales">
          <div className="bg-[#121212] border border-white/5 hover:border-[#10B981]/50 rounded-xl p-4 transition-colors h-full">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-[#10B981]/10 flex items-center justify-center">
                <TrendingUp className="w-4 h-4 text-[#10B981]" />
              </div>
              <div>
                <div className="text-white font-medium text-sm">Продажи</div>
                <div className="text-xs text-[#71717A]">Активные сделки</div>
              </div>
            </div>
          </div>
        </Link>
        <Link to="/trader/payment-details">
          <div className="bg-[#121212] border border-white/5 hover:border-[#F59E0B]/50 rounded-xl p-4 transition-colors h-full">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-[#F59E0B]/10 flex items-center justify-center">
                <CreditCard className="w-4 h-4 text-[#F59E0B]" />
              </div>
              <div>
                <div className="text-white font-medium text-sm">Реквизиты</div>
                <div className="text-xs text-[#71717A]">Способы оплаты</div>
              </div>
            </div>
          </div>
        </Link>
        <Link to="/trader/transfers">
          <div className="bg-[#121212] border border-white/5 hover:border-[#3B82F6]/50 rounded-xl p-4 transition-colors h-full">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-[#3B82F6]/10 flex items-center justify-center">
                <ArrowUpRight className="w-4 h-4 text-[#3B82F6]" />
              </div>
              <div>
                <div className="text-white font-medium text-sm">Переводы</div>
                <div className="text-xs text-[#71717A]">Другим пользователям</div>
              </div>
            </div>
          </div>
        </Link>
      </div>
    </div>
  );
}
