import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '@/lib/auth';
import { Bell, X, Check, AlertTriangle, Info, CheckCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

const NotificationIcon = ({ type }) => {
  switch (type) {
    case 'success':
      return <CheckCircle className="w-4 h-4 text-emerald-400" />;
    case 'warning':
      return <AlertTriangle className="w-4 h-4 text-yellow-400" />;
    case 'error':
      return <AlertTriangle className="w-4 h-4 text-red-400" />;
    default:
      return <Info className="w-4 h-4 text-blue-400" />;
  }
};

const UserNotifications = () => {
  const navigate = useNavigate();
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [markingAll, setMarkingAll] = useState(false);

  const fetchNotifications = async () => {
    try {
      const response = await api.get('/notifications?limit=10');
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
    // Refresh every 30 seconds
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
  }, []);

  const markAsRead = async (id) => {
    try {
      await api.post(`/notifications/${id}/read`);
      setNotifications(prev => 
        prev.map(n => n.id === id ? { ...n, read: true, is_read: true } : n)
      );
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch (error) {
      console.error('Failed to mark as read:', error);
    }
  };

  const markAllAsRead = async () => {
    if (unreadCount === 0) return;
    setMarkingAll(true);
    try {
      await api.post('/notifications/read-all');
      setNotifications(prev => prev.map(n => ({ ...n, read: true, is_read: true })));
      setUnreadCount(0);
    } catch (error) {
      console.error('Failed to mark all as read:', error);
    } finally {
      setMarkingAll(false);
    }
  };

  const handleNotificationClick = (notification) => {
    markAsRead(notification.id);
    setOpen(false);
    
    if (notification.link) {
      navigate(notification.link);
    }
  };

  const formatTime = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    
    if (diff < 60000) return 'Только что';
    if (diff < 3600000) return `${Math.floor(diff / 60000)} мин. назад`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)} ч. назад`;
    return date.toLocaleDateString('ru-RU');
  };

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="relative">
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <Badge 
              className="absolute -top-1 -right-1 h-5 w-5 flex items-center justify-center p-0 bg-red-500 text-white text-xs"
            >
              {unreadCount > 9 ? '9+' : unreadCount}
            </Badge>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-80 bg-zinc-900 border-zinc-800" align="end">
        <div className="p-3 border-b border-zinc-800 flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-white">Уведомления</h3>
            <p className="text-xs text-zinc-500">
              {unreadCount > 0 ? `${unreadCount} непрочитанных` : 'Нет новых уведомлений'}
            </p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className={`text-xs ${unreadCount > 0 ? 'text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10' : 'text-zinc-600 cursor-not-allowed'}`}
            onClick={markAllAsRead}
            disabled={markingAll || unreadCount === 0}
            data-testid="mark-all-read-btn"
          >
            {markingAll ? 'Читаю...' : 'Прочитать все'}
          </Button>
        </div>
        
        <div className="max-h-80 overflow-y-auto">
          {loading ? (
            <div className="p-4 text-center text-zinc-500 text-sm">
              Загрузка...
            </div>
          ) : notifications.length === 0 ? (
            <div className="p-4 text-center text-zinc-500 text-sm">
              Нет уведомлений
            </div>
          ) : (
            notifications.map(notification => (
              <div
                key={notification.id}
                className={`p-3 border-b border-zinc-800 hover:bg-zinc-800/50 cursor-pointer transition-colors ${
                  !notification.read && !notification.is_read ? 'bg-zinc-800/30' : ''
                }`}
                onClick={() => handleNotificationClick(notification)}
              >
                <div className="flex items-start gap-3">
                  <div className="mt-0.5">
                    <NotificationIcon type={notification.type} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <p className={`text-sm font-medium truncate ${!notification.read && !notification.is_read ? 'text-white' : 'text-zinc-400'}`}>
                        {notification.title}
                      </p>
                      {!notification.read && !notification.is_read && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 w-6 p-0 shrink-0"
                          onClick={(e) => {
                            e.stopPropagation();
                            markAsRead(notification.id);
                          }}
                        >
                          <Check className="w-3 h-3" />
                        </Button>
                      )}
                    </div>
                    <p className="text-xs text-zinc-500 line-clamp-2 mt-0.5">
                      {notification.message}
                    </p>
                    <p className="text-xs text-zinc-600 mt-1">
                      {formatTime(notification.created_at)}
                    </p>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export default UserNotifications;
