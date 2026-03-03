import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '@/lib/auth';
import { Bell, X, Check, AlertTriangle, Info, CheckCircle, UserPlus, MessageCircle, Wallet, FileWarning } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

const NotificationIcon = ({ type }) => {
  switch (type) {
    case 'success':
      return <CheckCircle className="w-4 h-4 text-emerald-400" />;
    case 'warning':
    case 'new_dispute':
    case 'dispute':
      return <AlertTriangle className="w-4 h-4 text-yellow-400" />;
    case 'error':
      return <AlertTriangle className="w-4 h-4 text-red-400" />;
    case 'new_user_request':
    case 'new_trader_request':
    case 'new_merchant':
      return <UserPlus className="w-4 h-4 text-emerald-400" />;
    case 'ticket_reply':
    case 'new_ticket':
      return <MessageCircle className="w-4 h-4 text-blue-400" />;
    case 'withdrawal_request':
    case 'withdrawal':
      return <Wallet className="w-4 h-4 text-orange-400" />;
    default:
      return <Info className="w-4 h-4 text-blue-400" />;
  }
};

const AdminNotifications = () => {
  const navigate = useNavigate();
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);

  const fetchNotifications = async () => {
    try {
      const response = await api.get('/admin/notifications?limit=10');
      setNotifications(response.data.notifications || []);
      setUnreadCount(response.data.unread_count || 0);
    } catch (error) {
      console.error('Failed to fetch notifications:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotifications();
    // Poll every 30 seconds
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
  }, []);

  const markAsRead = async (notificationId) => {
    try {
      await api.post(`/admin/notifications/${notificationId}/read`);
      setNotifications(prev =>
        prev.map(n => n.id === notificationId ? { ...n, read: true, is_read: true } : n)
      );
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch (error) {
      console.error('Failed to mark notification as read:', error);
    }
  };

  const markAllAsRead = async () => {
    try {
      await api.post('/admin/notifications/read-all');
      setNotifications(prev => prev.map(n => ({ ...n, read: true, is_read: true })));
      setUnreadCount(0);
    } catch (error) {
      console.error('Failed to mark all as read:', error);
    }
  };

  const handleNotificationClick = async (notification) => {
    // Помечаем как прочитанное
    if (!notification.is_read && !notification.read) {
      await markAsRead(notification.id);
    }
    
    const data = notification.data || {};
    const type = notification.type;
    
    // Навигация в зависимости от типа
    if (notification.link) {
      navigate(notification.link);
    } else if (type === 'new_user_request' || type === 'new_trader_request' || type === 'new_merchant' || type === 'trader_approval') {
      navigate('/admin/users');
    } else if (type === 'new_order' || type === 'order_payment' || data.order_id) {
      navigate('/admin/orders');
    } else if (type === 'dispute' || type === 'new_dispute' || data.dispute_id) {
      navigate('/admin/disputes');
    } else if (type === 'ticket' || type === 'new_ticket' || type === 'ticket_reply' || data.ticket_id) {
      navigate('/admin/tickets');
    } else if (type === 'new_withdrawal_request' || type === 'withdrawal_request' || type === 'withdrawal' || data.withdrawal_id) {
      navigate('/admin/finances');
    } else if (type === 'new_deposit' || type === 'deposit' || type === 'new_unidentified_deposit' || data.deposit_id) {
      navigate('/admin/finances');
    } else if (type === 'user' || data.user_id) {
      navigate('/admin/users');
    }
  };

  const formatTime = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Только что';
    if (diffMins < 60) return `${diffMins} мин. назад`;
    if (diffHours < 24) return `${diffHours} ч. назад`;
    if (diffDays < 7) return `${diffDays} дн. назад`;
    return date.toLocaleDateString('ru-RU');
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="relative"
          data-testid="notifications-trigger"
        >
          <Bell className="w-5 h-5 text-zinc-400 hover:text-white transition-colors" />
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full text-xs flex items-center justify-center font-medium">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        className="w-80 bg-zinc-900 border-zinc-800 p-0"
        data-testid="notifications-dropdown"
      >
        <div className="flex items-center justify-between p-3 border-b border-zinc-800">
          <h3 className="font-semibold">Уведомления</h3>
          {unreadCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="text-xs text-blue-400 hover:text-blue-300"
              onClick={markAllAsRead}
            >
              Прочитать все
            </Button>
          )}
        </div>

        <div className="max-h-96 overflow-y-auto">
          {loading ? (
            <div className="p-4 text-center text-zinc-500">Загрузка...</div>
          ) : notifications.length === 0 ? (
            <div className="p-4 text-center text-zinc-500">
              <Bell className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>Нет уведомлений</p>
            </div>
          ) : (
            notifications.map((notification) => (
              <div
                key={notification.id}
                className={`p-3 border-b border-zinc-800 hover:bg-zinc-800/50 transition-colors cursor-pointer ${
                  !notification.read && !notification.is_read ? 'bg-zinc-800/30' : ''
                }`}
                onClick={() => handleNotificationClick(notification)}
                data-testid={`notification-${notification.id}`}
              >
                <div className="flex items-start gap-3">
                  <div className="mt-0.5">
                    <NotificationIcon type={notification.type} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">
                      {notification.title}
                    </p>
                    <p className="text-xs text-zinc-400 line-clamp-2">
                      {notification.message}
                    </p>
                    <p className="text-xs text-zinc-500 mt-1">
                      {formatTime(notification.created_at)}
                    </p>
                  </div>
                  {!notification.read && !notification.is_read && (
                    <div className="w-2 h-2 bg-blue-500 rounded-full mt-1.5" />
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        {notifications.length > 0 && (
          <div className="p-2 border-t border-zinc-800">
            <Button
              variant="ghost"
              size="sm"
              className="w-full text-xs text-zinc-400 hover:text-white"
              onClick={() => {
                navigate('/admin/notifications');
              }}
            >
              Все уведомления
            </Button>
          </div>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export default AdminNotifications;
