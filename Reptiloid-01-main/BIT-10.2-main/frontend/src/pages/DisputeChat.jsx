import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, Link, useSearchParams, useNavigate } from 'react-router-dom';
import DashboardLayout from '@/components/DashboardLayout';
import { api, formatRUB, formatUSDT, formatDate, useAuth, BACKEND_URL } from '@/lib/auth';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import { 
  MessageCircle, Send, ArrowLeft, User, Shield, ShoppingCart,
  AlertTriangle, CheckCircle, Clock, DollarSign, XCircle, Wifi, WifiOff
} from 'lucide-react';

const DisputeChat = () => {
  const params = useParams();
  const disputeId = params.disputeId || params.id; // Поддержка обоих вариантов
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const buyerParam = searchParams.get('buyer') === 'true';
  const { user, loading: authLoading } = useAuth();
  
  // Проверяем наличие токена напрямую - это более надёжно чем ждать загрузки user
  const hasAuthToken = !!localStorage.getItem('token');
  
  // isBuyer только если:
  // 1. Параметр buyer=true в URL
  // 2. НЕТ токена авторизации
  // 3. Пользователь не залогинен
  const isBuyer = buyerParam && !hasAuthToken && !user;
  
  const [dispute, setDispute] = useState(null);
  const [order, setOrder] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [buyerContact, setBuyerContact] = useState('');
  const [wsConnected, setWsConnected] = useState(false);
  const messagesEndRef = useRef(null);
  const wsRef = useRef(null);

  // WebSocket connection for real-time messages
  useEffect(() => {
    if (!disputeId) return;
    
    const connectWebSocket = () => {
      const token = localStorage.getItem('token');
      const wsProtocol = BACKEND_URL?.startsWith('https') ? 'wss' : 'ws';
      const wsHost = BACKEND_URL?.replace(/^https?:\/\//, '') || '';
      
      let wsUrl;
      if (isBuyer) {
        // Buyers use a random token as identifier
        const buyerToken = sessionStorage.getItem('buyerToken') || Math.random().toString(36).substring(7);
        sessionStorage.setItem('buyerToken', buyerToken);
        wsUrl = `${wsProtocol}://${wsHost}/api/ws/dispute/${disputeId}?buyer_token=${buyerToken}`;
      } else if (token) {
        wsUrl = `${wsProtocol}://${wsHost}/api/ws/dispute/${disputeId}?token=${token}`;
      } else {
        return; // No auth, can't connect
      }
      
      try {
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;
        
        ws.onopen = () => {
          console.log('🔌 WebSocket connected to dispute chat');
          setWsConnected(true);
        };
        
        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'new_message' && data.message) {
              // Add new message to the list if not already present
              setMessages(prev => {
                const exists = prev.some(m => m.id === data.message.id);
                if (exists) return prev;
                // Remove any optimistic message with same text
                const filtered = prev.filter(m => !m._optimistic || m.text !== data.message.text);
                return [...filtered, data.message];
              });
            } else if (data.type === 'pong') {
              // Heartbeat response
            }
          } catch (e) {
            console.error('WS message parse error:', e);
          }
        };
        
        ws.onclose = () => {
          console.log('🔌 WebSocket disconnected');
          setWsConnected(false);
          // Reconnect after 3 seconds
          setTimeout(connectWebSocket, 3000);
        };
        
        ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          setWsConnected(false);
        };
        
        // Heartbeat every 30 seconds
        const heartbeat = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 30000);
        
        return () => {
          clearInterval(heartbeat);
          ws.close();
        };
      } catch (e) {
        console.error('WebSocket connection error:', e);
      }
    };
    
    const cleanup = connectWebSocket();
    return () => {
      if (cleanup) cleanup();
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [disputeId, isBuyer]);

  // Initial fetch and fallback polling (slower rate when WS is connected)
  useEffect(() => {
    fetchDispute();
    // Poll less frequently as WebSocket handles real-time updates
    const interval = setInterval(fetchDispute, wsConnected ? 30000 : 5000);
    return () => clearInterval(interval);
  }, [disputeId, wsConnected]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const fetchDispute = async () => {
    try {
      const endpoint = isBuyer 
        ? `/disputes/${disputeId}/public`
        : `/disputes/${disputeId}/messages`;
      const res = await api.get(endpoint);
      setDispute(res.data.dispute);
      setOrder(res.data.order);
      // Only update if we have more messages (avoid overwriting optimistic ones)
      setMessages(prev => {
        const newMsgs = res.data.messages || [];
        if (newMsgs.length >= prev.filter(m => !m._optimistic).length) {
          return newMsgs;
        }
        return prev;
      });
      if (res.data.dispute?.buyer_contact) {
        setBuyerContact(res.data.dispute.buyer_contact);
      }
    } catch (error) {
      console.error('Error fetching dispute:', error);
      const message = error.response?.data?.detail || error.message || 'Ошибка загрузки спора';
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!newMessage.trim()) return;

    const messageText = newMessage.trim();
    setSending(true);
    
    // Проверяем токен авторизации напрямую
    const authToken = localStorage.getItem('token');
    const isAuthenticated = !!authToken && !!user;
    
    // Определяем реальную роль отправителя
    const actualSenderRole = isAuthenticated ? (user.role || 'trader') : 'buyer';
    const actualSenderName = isAuthenticated 
      ? (user.nickname || user.login || 'Вы') 
      : (buyerContact || 'Покупатель');
    
    // Optimistic update - immediately show the message in UI
    const optimisticMessage = {
      id: `temp_${Date.now()}`,
      text: messageText,
      sender_role: actualSenderRole,
      sender_name: actualSenderName,
      created_at: new Date().toISOString(),
      _optimistic: true
    };
    setMessages(prev => [...prev, optimisticMessage]);
    setNewMessage('');
    
    try {
      // Используем публичный endpoint ТОЛЬКО если НЕТ авторизации
      const endpoint = isAuthenticated
        ? `/disputes/${disputeId}/messages`
        : `/disputes/${disputeId}/public/message`;
      
      const payload = isAuthenticated 
        ? { text: messageText }
        : { text: messageText, contact: buyerContact };
        
      await api.post(endpoint, payload);
      // WebSocket will deliver the real message, but fetch anyway as fallback
      if (!wsConnected) {
        await fetchDispute();
      }
    } catch (error) {
      // Remove optimistic message on error
      setMessages(prev => prev.filter(m => m.id !== optimisticMessage.id));
      const message = error.response?.data?.detail || error.message || 'Ошибка отправки';
      toast.error(message);
    } finally {
      setSending(false);
    }
  };

  // Трейдер подтверждает платеж (закрывает спор в пользу покупателя)
  const confirmPayment = async () => {
    if (!window.confirm('Подтвердить получение платежа? Спор будет закрыт, USDT переведены мерчанту.')) return;
    
    setProcessing(true);
    try {
      await api.post(`/disputes/${disputeId}/confirm-payment`);
      toast.success('Платёж подтверждён! Спор закрыт.');
      navigate('/trader/workspace');
    } catch (error) {
      const message = error.response?.data?.detail || error.message || 'Ошибка подтверждения';
      toast.error(message);
    } finally {
      setProcessing(false);
    }
  };

  // Трейдер отклоняет платеж (не получил деньги)
  const rejectPayment = async () => {
    if (!window.confirm('Вы уверены, что НЕ получили платёж? Модератор проверит ситуацию.')) return;
    
    setProcessing(true);
    try {
      await api.post(`/disputes/${disputeId}/reject-payment`);
      toast.success('Заявка отправлена модератору на проверку');
      fetchDispute();
    } catch (error) {
      const message = error.response?.data?.detail || error.message || 'Ошибка';
      toast.error(message);
    } finally {
      setProcessing(false);
    }
  };

  // Админ решает спор в пользу покупателя
  const adminResolveBuyer = async () => {
    if (!window.confirm('Решить спор в пользу покупателя? USDT будут списаны с трейдера и переведены мерчанту.')) return;
    
    setProcessing(true);
    try {
      await api.post(`/disputes/${disputeId}/resolve`, { 
        resolution: 'pay_buyer',
        comment: 'Решено администратором в пользу покупателя'
      });
      toast.success('Спор решён в пользу покупателя!');
      navigate('/admin/disputes');
    } catch (error) {
      const message = error.response?.data?.detail || error.message || 'Ошибка';
      toast.error(message);
    } finally {
      setProcessing(false);
    }
  };

  // Админ отменяет заказ
  const adminCancelOrder = async () => {
    if (!window.confirm('Отменить заказ? USDT будут возвращены трейдеру.')) return;
    
    setProcessing(true);
    try {
      await api.post(`/disputes/${disputeId}/resolve`, {
        resolution: 'cancel',
        comment: 'Заказ отменён администратором'
      });
      toast.success('Заказ отменён, USDT возвращены трейдеру.');
      navigate('/admin/disputes');
    } catch (error) {
      const message = error.response?.data?.detail || error.message || 'Ошибка';
      toast.error(message);
    } finally {
      setProcessing(false);
    }
  };

  const getRoleIcon = (role) => {
    switch (role) {
      case 'moderator': 
      case 'admin': 
        return <Shield className="w-4 h-4 text-red-400" />;
      case 'trader': return <User className="w-4 h-4 text-emerald-400" />;
      case 'merchant': return <ShoppingCart className="w-4 h-4 text-orange-400" />;
      case 'buyer': return <ShoppingCart className="w-4 h-4 text-blue-400" />;
      default: return <User className="w-4 h-4 text-zinc-400" />;
    }
  };

  const getRoleLabel = (role) => {
    switch (role) {
      case 'moderator': 
      case 'admin': 
        return 'Администрация';
      case 'trader': return 'Трейдер';
      case 'merchant': return 'Мерчант';
      case 'buyer': return 'Клиент';
      default: return role;
    }
  };

  const getRoleBgColor = (role) => {
    switch (role) {
      case 'moderator': 
      case 'admin': 
        return 'bg-red-500/20 border-red-500/50';
      case 'trader': return 'bg-emerald-500/20 border-emerald-500/50';
      case 'merchant': return 'bg-orange-500/20 border-orange-500/50';
      case 'buyer': return 'bg-blue-500/20 border-blue-500/50';
      default: return 'bg-zinc-800 border-zinc-700';
    }
  };

  const getRoleTextColor = (role) => {
    switch (role) {
      case 'moderator': 
      case 'admin': 
        return 'text-red-400';
      case 'trader': return 'text-emerald-400';
      case 'merchant': return 'text-orange-400';
      case 'buyer': return 'text-blue-400';
      default: return 'text-zinc-400';
    }
  };

  // Определяем роль текущего пользователя в споре
  const isTrader = user?.role === 'trader';
  const isMerchant = user?.role === 'merchant';
  const isAdmin = user?.role === 'admin';

  // Определяем куда возвращаться
  const getBackLink = () => {
    if (user?.role === 'admin') return '/admin/disputes';
    if (user?.role === 'merchant') return '/merchant/orders';
    return '/trader/workspace';
  };

  if (loading) {
    return isBuyer ? (
      <div className="min-h-screen bg-[#09090B] flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full" />
      </div>
    ) : (
      <DashboardLayout>
        <div className="flex items-center justify-center h-[60vh]">
          <div className="animate-spin w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full" />
        </div>
      </DashboardLayout>
    );
  }

  const chatContent = (
    <div className={isBuyer ? "max-w-2xl mx-auto p-4" : "max-w-4xl mx-auto"}>
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        {!isBuyer && (
          <Link to={getBackLink()}>
            <Button variant="outline" size="icon" className="border-zinc-800">
              <ArrowLeft className="w-4 h-4" />
            </Button>
          </Link>
        )}
        <div className="flex-1">
          <h1 className="text-xl font-bold font-['Chivo'] flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-orange-400" />
            Спор #{order?.id?.split('_').pop() || dispute?.order_id?.split('_').pop() || disputeId?.split('_').pop()}
            {/* WebSocket connection indicator */}
            {wsConnected ? (
              <span className="flex items-center gap-1 text-xs text-emerald-400 font-normal">
                <Wifi className="w-3 h-3" />
                Live
              </span>
            ) : (
              <span className="flex items-center gap-1 text-xs text-zinc-500 font-normal">
                <WifiOff className="w-3 h-3" />
              </span>
            )}
          </h1>
          <p className="text-sm text-zinc-400">
            {dispute?.status === 'open' ? (
              <span className="text-orange-400">Открыт</span>
            ) : dispute?.status === 'pending_review' ? (
              <span className="text-yellow-400">На проверке модератора</span>
            ) : (
              <span className="text-emerald-400">Решён</span>
            )}
          </p>
        </div>
        
        {/* Order info */}
        {order && (
          <div className="text-right">
            <div className="font-['JetBrains_Mono'] text-lg font-bold">{formatRUB(order.amount_rub)}</div>
            <div className="text-xs text-zinc-500">≈ {formatUSDT(order.amount_usdt)} USDT</div>
          </div>
        )}
      </div>

      {/* Уникальная ссылка на спор для покупателя */}
      {isBuyer && dispute?.status === 'open' && (
        <Card className="bg-orange-500/10 border-orange-500/30 mb-6">
          <CardContent className="p-4">
            <h3 className="font-medium mb-2 flex items-center gap-2 text-orange-400">
              <AlertTriangle className="w-4 h-4" />
              ⚠️ ВАЖНО! Сохраните эту ссылку
            </h3>
            <p className="text-sm text-zinc-400 mb-3">
              По этой ссылке вы сможете вернуться в чат спора в любое время до его разрешения.
            </p>
            <div className="flex items-center gap-2 bg-zinc-800 rounded-lg p-2">
              <input 
                type="text" 
                readOnly 
                value={window.location.href}
                className="flex-1 bg-transparent text-sm text-zinc-300 outline-none font-mono"
              />
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  navigator.clipboard.writeText(window.location.href);
                  toast.success('Ссылка скопирована!');
                }}
                className="text-emerald-400 hover:text-emerald-300"
              >
                Копировать
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Trader actions - только подтвердить платеж (НЕ для покупателя) */}
      {isTrader && !isBuyer && dispute?.status === 'open' && (
        <Card className="bg-gradient-to-r from-emerald-500/10 to-orange-500/10 border-emerald-500/30 mb-6">
          <CardContent className="p-4">
            <h3 className="font-medium mb-3 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-orange-400" />
              Действия по спору
            </h3>
            <p className="text-sm text-zinc-400 mb-4">
              Если вы получили платёж от покупателя - подтвердите его. Спор будет закрыт, а сделка завершена.
            </p>
            <Button
              onClick={confirmPayment}
              disabled={processing}
              className="w-full bg-emerald-500 hover:bg-emerald-600"
            >
              <CheckCircle className="w-4 h-4 mr-2" />
              {processing ? 'Обработка...' : 'Платёж получен - закрыть спор'}
            </Button>
          </CardContent>
        </Card>
      )}
      
      {/* Admin actions - resolve dispute */}
      {isAdmin && dispute?.status === 'open' && (
        <Card className="bg-gradient-to-r from-red-500/10 to-orange-500/10 border-red-500/30 mb-6">
          <CardContent className="p-4">
            <h3 className="font-medium mb-3 flex items-center gap-2 text-red-400">
              <Shield className="w-4 h-4 text-red-400" />
              Действия администратора
            </h3>
            <p className="text-sm text-zinc-400 mb-4">
              Рассмотрите ситуацию и примите решение по спору.
            </p>
            <div className="flex gap-3">
              <Button
                onClick={adminResolveBuyer}
                disabled={processing}
                className="flex-1 bg-emerald-500 hover:bg-emerald-600"
              >
                <CheckCircle className="w-4 h-4 mr-2" />
                В пользу покупателя
              </Button>
              <Button
                onClick={adminCancelOrder}
                disabled={processing}
                variant="outline"
                className="flex-1 border-red-500/50 text-red-400 hover:bg-red-500/10"
              >
                <XCircle className="w-4 h-4 mr-2" />
                Отменить заказ
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Chat */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader className="border-b border-zinc-800">
          <CardTitle className="text-base flex items-center gap-2">
            <MessageCircle className="w-4 h-4" />
            Чат спора
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {/* Messages */}
          <div className="h-[350px] overflow-y-auto p-4 space-y-4">
            {messages.length === 0 ? (
              <div className="text-center text-zinc-500 py-8">
                Сообщений пока нет. Начните диалог.
              </div>
            ) : (
              messages.map((msg) => {
                const isOwnMessage = isBuyer 
                  ? msg.sender_role === 'buyer'
                  : msg.sender_id === user?.id;
                  
                return (
                  <div
                    key={msg.id}
                    className={`flex ${isOwnMessage ? 'justify-end' : 'justify-start'}`}
                  >
                    <div className={`max-w-[70%] rounded-lg p-3 border ${getRoleBgColor(msg.sender_role)}`}>
                      <div className="flex items-center gap-2 mb-1">
                        {getRoleIcon(msg.sender_role)}
                        <span className={`text-xs font-medium ${getRoleTextColor(msg.sender_role)}`}>
                          {getRoleLabel(msg.sender_role)}
                        </span>
                        <span className="text-xs text-zinc-500">
                          {new Date(msg.created_at).toLocaleTimeString('ru-RU', { 
                            hour: '2-digit', 
                            minute: '2-digit' 
                          })}
                        </span>
                      </div>
                      <p className="text-sm whitespace-pre-wrap">{msg.text}</p>
                    </div>
                  </div>
                );
              })
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          {dispute?.status !== 'resolved' ? (
            <form onSubmit={sendMessage} className="p-4 border-t border-zinc-800">
              <div className="flex gap-2">
                <Input
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  placeholder="Введите сообщение..."
                  className="flex-1 bg-zinc-800 border-zinc-700"
                  disabled={sending}
                />
                <Button 
                  type="submit" 
                  disabled={sending || !newMessage.trim()}
                  className="bg-emerald-500 hover:bg-emerald-600"
                >
                  <Send className="w-4 h-4" />
                </Button>
              </div>
            </form>
          ) : (
            <div className="p-4 border-t border-zinc-800 text-center text-zinc-500">
              <CheckCircle className="w-5 h-5 inline-block mr-2 text-emerald-400" />
              Спор закрыт
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );

  // Для покупателя - без DashboardLayout
  if (isBuyer) {
    return (
      <div className="min-h-screen bg-[#09090B]">
        <div className="border-b border-zinc-800 bg-zinc-900/50 backdrop-blur-sm">
          <div className="max-w-2xl mx-auto px-4 py-3 flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-emerald-500 flex items-center justify-center">
              <DollarSign className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold font-['Chivo']">BITARBITR</span>
          </div>
        </div>
        {chatContent}
      </div>
    );
  }

  return (
    <DashboardLayout>
      {chatContent}
    </DashboardLayout>
  );
};

export default DisputeChat;
