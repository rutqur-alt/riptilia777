import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import DashboardLayout from '@/components/DashboardLayout';
import { api, formatDate } from '@/lib/auth';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Bell, Check, CheckCheck, Trash2, AlertTriangle, Info, CheckCircle, ArrowLeft } from 'lucide-react';
import { toast } from 'sonner';

const NotificationIcon = ({ type }) => {
  switch (type) {
    case 'success':
      return <CheckCircle className="w-5 h-5 text-emerald-400" />;
    case 'warning':
      return <AlertTriangle className="w-5 h-5 text-yellow-400" />;
    case 'error':
      return <AlertTriangle className="w-5 h-5 text-red-400" />;
    default:
      return <Info className="w-5 h-5 text-blue-400" />;
  }
};

const AdminNotificationsPage = () => {
  const navigate = useNavigate();
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all'); // all, unread, read

  const fetchNotifications = async () => {
    try {
      const response = await api.get('/admin/notifications?limit=100');
      setNotifications(response.data.notifications || []);
    } catch (error) {
      console.error('Failed to fetch notifications:', error);
      toast.error('Ошибка загрузки уведомлений');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotifications();
  }, []);

  const markAsRead = async (id) => {
    try {
      await api.post(`/admin/notifications/${id}/read`);
      setNotifications(prev => 
        prev.map(n => n.id === id ? { ...n, is_read: true } : n)
      );
    } catch (error) {
      toast.error('Ошибка');
    }
  };

  const markAllAsRead = async () => {
    try {
      await api.post('/admin/notifications/read-all');
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
      toast.success('Все уведомления прочитаны');
    } catch (error) {
      toast.error('Ошибка');
    }
  };

  const deleteNotification = async (id) => {
    try {
      await api.delete(`/admin/notifications/${id}`);
      setNotifications(prev => prev.filter(n => n.id !== id));
      toast.success('Уведомление удалено');
    } catch (error) {
      toast.error('Ошибка');
    }
  };

  const handleNotificationClick = (notification) => {
    markAsRead(notification.id);
    
    // Navigate based on notification type
    if (notification.link) {
      navigate(notification.link);
    } else if (notification.type === 'new_withdrawal_request') {
      navigate('/admin/finances');
    } else if (notification.type === 'new_trader_application' || notification.type === 'new_merchant_application') {
      navigate('/admin/users');
    } else if (notification.type === 'new_unidentified_deposit') {
      navigate('/admin/finances');
    } else if (notification.type === 'new_ticket_message') {
      navigate('/admin/tickets');
    }
  };

  const filteredNotifications = notifications.filter(n => {
    if (filter === 'unread') return !n.is_read;
    if (filter === 'read') return n.is_read;
    return true;
  });

  const unreadCount = notifications.filter(n => !n.is_read).length;

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button 
              variant="ghost" 
              size="sm"
              onClick={() => navigate(-1)}
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Назад
            </Button>
            <div>
              <h1 className="text-2xl font-bold flex items-center gap-2">
                <Bell className="w-6 h-6" />
                Все уведомления
              </h1>
              <p className="text-zinc-400 text-sm">
                {unreadCount > 0 ? `${unreadCount} непрочитанных` : 'Нет непрочитанных'}
              </p>
            </div>
          </div>
          
          {unreadCount > 0 && (
            <Button 
              variant="outline" 
              size="sm"
              onClick={markAllAsRead}
            >
              <CheckCheck className="w-4 h-4 mr-2" />
              Прочитать все
            </Button>
          )}
        </div>

        {/* Filters */}
        <div className="flex gap-2">
          <Button
            variant={filter === 'all' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilter('all')}
          >
            Все ({notifications.length})
          </Button>
          <Button
            variant={filter === 'unread' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilter('unread')}
          >
            Непрочитанные ({unreadCount})
          </Button>
          <Button
            variant={filter === 'read' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilter('read')}
          >
            Прочитанные ({notifications.length - unreadCount})
          </Button>
        </div>

        {/* Notifications List */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-0">
            {loading ? (
              <div className="p-8 text-center text-zinc-500">
                Загрузка...
              </div>
            ) : filteredNotifications.length === 0 ? (
              <div className="p-8 text-center text-zinc-500">
                <Bell className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>Нет уведомлений</p>
              </div>
            ) : (
              <div className="divide-y divide-zinc-800">
                {filteredNotifications.map(notification => (
                  <div
                    key={notification.id}
                    className={`p-4 hover:bg-zinc-800/50 cursor-pointer transition-colors ${
                      !notification.is_read ? 'bg-zinc-800/30' : ''
                    }`}
                    onClick={() => handleNotificationClick(notification)}
                  >
                    <div className="flex items-start gap-3">
                      <div className="mt-1">
                        <NotificationIcon type={notification.notification_type} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <p className={`font-medium ${!notification.is_read ? 'text-white' : 'text-zinc-400'}`}>
                            {notification.title}
                          </p>
                          {!notification.is_read && (
                            <Badge variant="secondary" className="bg-blue-500/20 text-blue-400 text-xs">
                              Новое
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm text-zinc-500 line-clamp-2">
                          {notification.message}
                        </p>
                        <p className="text-xs text-zinc-600 mt-1">
                          {formatDate(notification.created_at)}
                        </p>
                      </div>
                      <div className="flex items-center gap-1">
                        {!notification.is_read && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 w-8 p-0"
                            onClick={(e) => {
                              e.stopPropagation();
                              markAsRead(notification.id);
                            }}
                          >
                            <Check className="w-4 h-4" />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0 text-red-400 hover:text-red-300"
                          onClick={(e) => {
                            e.stopPropagation();
                            deleteNotification(notification.id);
                          }}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
};

export default AdminNotificationsPage;
