import { useState, useEffect, useRef, useCallback } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { API, useAuth } from "@/App";
import { useWebSocket } from "@/hooks/useWebSocket";
import { toast } from "sonner";
import { 
  Bell, TrendingUp, DollarSign, CheckCircle, XCircle, AlertTriangle,
  MessageCircle, ShoppingBag, Package, Wallet, Users, ArrowUpRight,
  ArrowDownRight, Clock, User
} from "lucide-react";

// Icon mapping for notification types
const ICON_MAP = {
  TrendingUp: TrendingUp,
  DollarSign: DollarSign,
  CheckCircle: CheckCircle,
  XCircle: XCircle,
  AlertTriangle: AlertTriangle,
  MessageCircle: MessageCircle,
  ShoppingBag: ShoppingBag,
  Package: Package,
  Wallet: Wallet,
  Users: Users,
  ArrowUpRight: ArrowUpRight,
  ArrowDownRight: ArrowDownRight,
  Clock: Clock,
  User: User,
  Bell: Bell,
};

// Color scheme for different notification types
const TYPE_COLORS = {
  // Trade events - green/success or red/error
  trade_created: { bg: "bg-[#7C3AED]/10", text: "text-[#A78BFA]", icon: "text-[#7C3AED]" },
  trade_payment_sent: { bg: "bg-[#F59E0B]/10", text: "text-[#FCD34D]", icon: "text-[#F59E0B]" },
  trade_payment_received: { bg: "bg-[#10B981]/10", text: "text-[#6EE7B7]", icon: "text-[#10B981]" },
  trade_completed: { bg: "bg-[#10B981]/10", text: "text-[#6EE7B7]", icon: "text-[#10B981]" },
  trade_cancelled: { bg: "bg-[#EF4444]/10", text: "text-[#FCA5A5]", icon: "text-[#EF4444]" },
  trade_disputed: { bg: "bg-[#EF4444]/10", text: "text-[#FCA5A5]", icon: "text-[#EF4444]" },
  trade_message: { bg: "bg-[#3B82F6]/10", text: "text-[#93C5FD]", icon: "text-[#3B82F6]" },
  
  // Payout events
  payout_order_created: { bg: "bg-[#F97316]/10", text: "text-[#FDBA74]", icon: "text-[#F97316]" },
  payout_order_assigned: { bg: "bg-[#F97316]/10", text: "text-[#FDBA74]", icon: "text-[#F97316]" },
  payout_order_paid: { bg: "bg-[#10B981]/10", text: "text-[#6EE7B7]", icon: "text-[#10B981]" },
  payout_order_completed: { bg: "bg-[#10B981]/10", text: "text-[#6EE7B7]", icon: "text-[#10B981]" },
  payout_order_cancelled: { bg: "bg-[#EF4444]/10", text: "text-[#FCA5A5]", icon: "text-[#EF4444]" },
  
  // Marketplace
  marketplace_purchase: { bg: "bg-[#8B5CF6]/10", text: "text-[#C4B5FD]", icon: "text-[#8B5CF6]" },
  marketplace_delivered: { bg: "bg-[#10B981]/10", text: "text-[#6EE7B7]", icon: "text-[#10B981]" },
  marketplace_confirmed: { bg: "bg-[#10B981]/10", text: "text-[#6EE7B7]", icon: "text-[#10B981]" },
  marketplace_disputed: { bg: "bg-[#EF4444]/10", text: "text-[#FCA5A5]", icon: "text-[#EF4444]" },
  shop_new_order: { bg: "bg-[#F97316]/10", text: "text-[#FDBA74]", icon: "text-[#F97316]" },
  shop_message: { bg: "bg-[#3B82F6]/10", text: "text-[#93C5FD]", icon: "text-[#3B82F6]" },
  
  // Finance
  deposit_received: { bg: "bg-[#10B981]/10", text: "text-[#6EE7B7]", icon: "text-[#10B981]" },
  withdrawal_completed: { bg: "bg-[#10B981]/10", text: "text-[#6EE7B7]", icon: "text-[#10B981]" },
  withdrawal_processing: { bg: "bg-[#F59E0B]/10", text: "text-[#FCD34D]", icon: "text-[#F59E0B]" },
  balance_updated: { bg: "bg-[#7C3AED]/10", text: "text-[#A78BFA]", icon: "text-[#7C3AED]" },
  
  // Messages
  new_message: { bg: "bg-[#3B82F6]/10", text: "text-[#93C5FD]", icon: "text-[#3B82F6]" },
  support_reply: { bg: "bg-[#3B82F6]/10", text: "text-[#93C5FD]", icon: "text-[#3B82F6]" },
  broadcast: { bg: "bg-[#7C3AED]/10", text: "text-[#A78BFA]", icon: "text-[#7C3AED]" },
  
  // Referrals
  new_referral: { bg: "bg-[#EC4899]/10", text: "text-[#F9A8D4]", icon: "text-[#EC4899]" },
  referral_bonus: { bg: "bg-[#10B981]/10", text: "text-[#6EE7B7]", icon: "text-[#10B981]" },
  
  // Merchant
  merchant_payment_received: { bg: "bg-[#10B981]/10", text: "text-[#6EE7B7]", icon: "text-[#10B981]" },
  merchant_withdrawal_request: { bg: "bg-[#F59E0B]/10", text: "text-[#FCD34D]", icon: "text-[#F59E0B]" },
  merchant_withdrawal_completed: { bg: "bg-[#10B981]/10", text: "text-[#6EE7B7]", icon: "text-[#10B981]" },
};

// Default color scheme
const DEFAULT_COLORS = { bg: "bg-white/5", text: "text-[#A1A1AA]", icon: "text-[#71717A]" };

// Get icon component for notification type
const getNotificationIcon = (type) => {
  const iconName = {
    trade_created: "TrendingUp",
    trade_payment_sent: "DollarSign",
    trade_payment_received: "CheckCircle",
    trade_completed: "CheckCircle",
    trade_cancelled: "XCircle",
    trade_disputed: "AlertTriangle",
    trade_message: "MessageCircle",
    payout_order_created: "DollarSign",
    payout_order_assigned: "User",
    payout_order_paid: "CheckCircle",
    payout_order_completed: "CheckCircle",
    payout_order_cancelled: "XCircle",
    marketplace_purchase: "ShoppingBag",
    marketplace_delivered: "Package",
    marketplace_confirmed: "CheckCircle",
    marketplace_disputed: "AlertTriangle",
    shop_new_order: "ShoppingBag",
    shop_message: "MessageCircle",
    deposit_received: "ArrowDownRight",
    withdrawal_completed: "ArrowUpRight",
    withdrawal_processing: "Clock",
    balance_updated: "Wallet",
    new_message: "MessageCircle",
    support_reply: "MessageCircle",
    broadcast: "Bell",
    new_referral: "Users",
    referral_bonus: "DollarSign",
    merchant_payment_received: "DollarSign",
    merchant_withdrawal_request: "ArrowUpRight",
    merchant_withdrawal_completed: "CheckCircle",
  }[type] || "Bell";
  
  return ICON_MAP[iconName] || Bell;
};

// Format time ago
const formatTimeAgo = (dateString) => {
  const date = new Date(dateString);
  const now = new Date();
  const diff = Math.floor((now - date) / 1000); // seconds
  
  if (diff < 60) return "только что";
  if (diff < 3600) return `${Math.floor(diff / 60)} мин`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} ч`;
  if (diff < 604800) return `${Math.floor(diff / 86400)} д`;
  return date.toLocaleDateString("ru-RU");
};

export default function EventNotificationDropdown({ token, role = "trader" }) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const dropdownRef = useRef(null);
  const buttonRef = useRef(null);
  
  // WebSocket handler for real-time notifications
  const onWsMessage = useCallback((data) => {
    if (data.type === "new_notification" && data.notification) {
      // Add new notification to the top of the list
      setNotifications(prev => [data.notification, ...prev]);
      setUnreadCount(prev => prev + 1);
      
      // Show toast notification
      toast.info(data.notification.title, {
        description: data.notification.message,
        duration: 5000,
        action: data.notification.link ? {
          label: "Открыть",
          onClick: () => navigate(data.notification.link)
        } : undefined
      });
    }
  }, [navigate]);
  
  // Connect to WebSocket for real-time updates
  useWebSocket(
    user ? `/ws/user/${user.id}` : null,
    onWsMessage,
    { enabled: !!user }
  );
  
  // Fetch notifications
  const fetchNotifications = async () => {
    if (!token) return;
    try {
      setLoading(true);
      const [notifResponse, countResponse] = await Promise.all([
        axios.get(`${API}/event-notifications`, {
          headers: { Authorization: `Bearer ${token}` }
        }),
        axios.get(`${API}/event-notifications/unread-count`, {
          headers: { Authorization: `Bearer ${token}` }
        })
      ]);
      setNotifications(notifResponse.data || []);
      setUnreadCount(countResponse.data?.count || 0);
    } catch (error) {
      console.error("Failed to fetch notifications:", error);
    } finally {
      setLoading(false);
    }
  };
  
  // Initial fetch and reduced polling (WebSocket handles real-time)
  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 30000); // Poll every 30 sec as backup
    return () => clearInterval(interval);
  }, [token]);
  
  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        dropdownRef.current && !dropdownRef.current.contains(event.target) &&
        buttonRef.current && !buttonRef.current.contains(event.target)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);
  
  // Handle notification click - navigate and mark as read
  const handleNotificationClick = async (notification) => {
    // Mark as read
    try {
      await axios.post(
        `${API}/event-notifications/mark-read`,
        { notification_id: notification.id },
        { headers: { Authorization: `Bearer ${token}` } }
      );
    } catch (e) {
      console.error("Failed to mark notification as read:", e);
    }
    
    // Remove from local state
    setNotifications(prev => prev.filter(n => n.id !== notification.id));
    setUnreadCount(prev => Math.max(0, prev - 1));
    setOpen(false);
    
    // Navigate to the link
    if (notification.link) {
      navigate(notification.link);
    }
  };
  
  // Handle read all
  const handleReadAll = async () => {
    try {
      await axios.post(
        `${API}/event-notifications/mark-read`,
        { all: true },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setNotifications([]);
      setUnreadCount(0);
      setOpen(false);
    } catch (e) {
      console.error("Failed to mark all as read:", e);
    }
  };
  
  // Get dropdown position
  const getDropdownPos = () => {
    if (!buttonRef.current) return { top: 100, left: 60 };
    const r = buttonRef.current.getBoundingClientRect();
    // Position dropdown to the right of the button, or adjust if near edge
    const left = Math.min(r.left, window.innerWidth - 340);
    return { top: r.bottom + 8, left: Math.max(left, 10) };
  };
  
  // Declension for Russian
  const declension = (n) => {
    const abs = Math.abs(n) % 100;
    const n1 = abs % 10;
    if (abs > 10 && abs < 20) return "событий";
    if (n1 > 1 && n1 < 5) return "события";
    if (n1 === 1) return "событие";
    return "событий";
  };
  
  const hasNotifications = unreadCount > 0;
  
  return (
    <>
      {/* Trigger Button */}
      <button
        ref={buttonRef}
        onClick={() => setOpen(!open)}
        data-testid="notification-bell-btn"
        className={`
          text-xs px-2.5 py-1 rounded-full transition-colors cursor-pointer whitespace-nowrap
          flex items-center gap-1.5
          ${hasNotifications 
            ? "text-[#EF4444] bg-[#EF4444]/10 hover:bg-[#EF4444]/20" 
            : "text-[#52525B] bg-white/5 hover:bg-white/10"
          }
        `}
      >
        {hasNotifications ? (
          <>
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#EF4444] opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-[#EF4444]"></span>
            </span>
            <span>{unreadCount} {declension(unreadCount)}</span>
          </>
        ) : (
          <span>Нет событий</span>
        )}
      </button>
      
      {/* Dropdown Portal */}
      {open && createPortal(
        <div
          ref={dropdownRef}
          data-testid="notification-dropdown"
          style={{
            position: "fixed",
            top: getDropdownPos().top,
            left: getDropdownPos().left,
            zIndex: 99999,
            minWidth: "320px",
            width: "340px"
          }}
          className="bg-[#1A1A1A] border border-white/10 rounded-xl shadow-2xl overflow-hidden"
        >
          {/* Header */}
          <div className="p-3 border-b border-white/5 flex items-center justify-between">
            <span className="text-sm font-medium text-white">Оповещения</span>
            {loading && (
              <span className="w-4 h-4 border-2 border-[#7C3AED] border-t-transparent rounded-full animate-spin" />
            )}
          </div>
          
          {/* Notifications List */}
          <div className="max-h-96 overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="p-6 text-center">
                <Bell className="w-8 h-8 text-[#3F3F46] mx-auto mb-2" />
                <div className="text-sm text-[#52525B]">Нет оповещений</div>
              </div>
            ) : (
              notifications.map((notification) => {
                const colors = TYPE_COLORS[notification.type] || DEFAULT_COLORS;
                const IconComponent = getNotificationIcon(notification.type);
                
                return (
                  <button
                    key={notification.id}
                    onClick={() => handleNotificationClick(notification)}
                    data-testid={`notification-item-${notification.id}`}
                    className="w-full text-left px-4 py-3 hover:bg-white/5 transition-colors border-b border-white/5 last:border-0 flex items-start gap-3"
                  >
                    {/* Icon */}
                    <div className={`w-8 h-8 rounded-lg ${colors.bg} flex items-center justify-center flex-shrink-0`}>
                      <IconComponent className={`w-4 h-4 ${colors.icon}`} />
                    </div>
                    
                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-medium text-white truncate">
                          {notification.title}
                        </span>
                        <span className="text-[10px] text-[#52525B] flex-shrink-0">
                          {formatTimeAgo(notification.created_at)}
                        </span>
                      </div>
                      <div className="text-xs text-[#71717A] mt-0.5 line-clamp-2">
                        {notification.message}
                      </div>
                    </div>
                  </button>
                );
              })
            )}
          </div>
          
          {/* Footer */}
          <div className="p-2 border-t border-white/5">
            <button
              onClick={handleReadAll}
              data-testid="read-all-notifications-btn"
              className="w-full text-center py-2 text-xs text-[#7C3AED] hover:bg-[#7C3AED]/10 rounded-lg transition-colors disabled:opacity-50"
              disabled={notifications.length === 0}
            >
              Прочитать всё
            </button>
          </div>
        </div>,
        document.body
      )}
    </>
  );
}
