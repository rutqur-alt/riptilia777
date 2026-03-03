import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { toast } from 'sonner';
import CopyableOrderId from '@/components/CopyableOrderId';
import { 
  MessageCircle, 
  Send, 
  AlertTriangle, 
  CheckCircle, 
  XCircle,
  Clock,
  User,
  Shield,
  Loader2,
  Copy
} from 'lucide-react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const PublicDispute = () => {
  const params = useParams();
  const token = params.token || params.id; // Поддержка обоих вариантов
  const searchParams = new URLSearchParams(window.location.search);
  const isBuyer = searchParams.get('buyer') === 'true';
  
  const [dispute, setDispute] = useState(null);
  const [order, setOrder] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const [newMessage, setNewMessage] = useState('');
  const [senderName, setSenderName] = useState('');
  const [sending, setSending] = useState(false);
  const [showCancelDialog, setShowCancelDialog] = useState(false);
  
  const messagesEndRef = useRef(null);

  useEffect(() => {
    fetchDispute();
    // Автообновление каждые 10 секунд
    const interval = setInterval(fetchDispute, 10000);
    return () => clearInterval(interval);
  }, [token]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const fetchDispute = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/public/dispute/${token}`);
      setDispute(res.data.dispute);
      setOrder(res.data.order);
      setMessages(res.data.messages || []);
      setError(null);
    } catch (err) {
      if (err.response?.status === 404) {
        setError('Спор не найден или ссылка недействительна');
      } else {
        setError('Ошибка загрузки данных');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!newMessage.trim()) return;
    
    setSending(true);
    try {
      await axios.post(`${API_URL}/api/public/dispute/${token}/message`, {
        text: newMessage,
        contact: senderName || 'Клиент'
      });
      
      setNewMessage('');
      fetchDispute();
      toast.success('Сообщение отправлено');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Ошибка отправки');
    } finally {
      setSending(false);
    }
  };

  const handleCancelDispute = async () => {
    if (!order?.id) return;
    
    try {
      await axios.post(`${API_URL}/api/pay/${order.id}/cancel-dispute`);
      toast.success('Спор отменён');
      setShowCancelDialog(false);
      fetchDispute();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Ошибка отмены спора');
    }
  };
  
  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('Ссылка скопирована!');
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'open':
        return <Clock className="w-5 h-5 text-yellow-400" />;
      case 'resolved':
        return <CheckCircle className="w-5 h-5 text-emerald-400" />;
      default:
        return <AlertTriangle className="w-5 h-5 text-orange-400" />;
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'open':
        return 'Рассматривается';
      case 'resolved':
        return 'Решён';
      default:
        return status;
    }
  };

  const getResolutionText = (resolution) => {
    switch (resolution) {
      case 'pay_buyer':
        return 'В пользу покупателя';
      case 'refund':
        return 'Возврат средств';
      case 'complete':
        return 'Сделка завершена';
      case 'cancel':
        return 'Отменён';
      default:
        return resolution;
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-4">
        <Card className="bg-zinc-900 border-zinc-800 max-w-md w-full">
          <CardContent className="p-8 text-center">
            <XCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
            <h2 className="text-xl font-bold mb-2">Ошибка</h2>
            <p className="text-zinc-400">{error}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      {/* Header */}
      <header className="bg-zinc-900 border-b border-zinc-800 py-4">
        <div className="container mx-auto px-4">
          <div className="flex items-center gap-3">
            <Shield className="w-8 h-8 text-emerald-500" />
            <div>
              <h1 className="font-bold text-lg">Служба поддержки</h1>
              <p className="text-zinc-400 text-sm">Рассмотрение спора по платежу</p>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6 max-w-3xl">
        {/* Dispute Info */}
        <Card className="bg-zinc-900 border-zinc-800 mb-6">
          <CardContent className="p-6">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-2">
                {getStatusIcon(dispute?.status)}
                <span className="font-medium">
                  Статус: {getStatusText(dispute?.status)}
                </span>
              </div>
              <CopyableOrderId orderId={order?.id || dispute?.order_id} size="small" />
            </div>

            {/* Order Details */}
            {order && (
              <div className="grid grid-cols-2 gap-4 p-4 bg-zinc-800 rounded-lg mb-4">
                <div>
                  <div className="text-xs text-zinc-500 mb-1">ID заказа</div>
                  <CopyableOrderId orderId={order.id} showHash={false} size="small" prefix="" />
                </div>
                <div>
                  <div className="text-xs text-zinc-500 mb-1">Сумма</div>
                  <div className="font-['JetBrains_Mono'] text-lg">
                    {order.amount_rub?.toLocaleString('ru-RU')} ₽
                  </div>
                </div>
                <div>
                  <div className="text-xs text-zinc-500 mb-1">Дата создания</div>
                  <div className="text-sm">{formatDate(order.created_at)}</div>
                </div>
                <div>
                  <div className="text-xs text-zinc-500 mb-1">Дата спора</div>
                  <div className="text-sm">{formatDate(dispute?.created_at)}</div>
                </div>
              </div>
            )}

            {/* Reason */}
            {dispute?.reason && dispute.reason !== 'Payment dispute' && (
              <div className="bg-orange-500/10 border border-orange-500/20 rounded-lg p-4">
                <div className="text-xs text-orange-400 mb-1">Причина спора:</div>
                <div className="text-sm">{dispute.reason}</div>
              </div>
            )}

            {/* Cancel Dispute Button for buyer */}
            {isBuyer && dispute?.status === 'open' && (
              <div className="mt-4 p-4 bg-zinc-800 rounded-lg border border-zinc-700">
                <p className="text-sm text-zinc-400 mb-3">
                  Если вопрос решён, вы можете отменить спор
                </p>
                <Button
                  onClick={() => setShowCancelDialog(true)}
                  variant="outline"
                  className="w-full border-red-500/50 text-red-400 hover:bg-red-500/10"
                  data-testid="cancel-dispute-btn"
                >
                  <XCircle className="w-4 h-4 mr-2" />
                  Отменить спор
                </Button>
              </div>
            )}

            {/* Resolution */}
            {dispute?.status === 'resolved' && dispute?.resolution && (
              <div className="mt-4 bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle className="w-5 h-5 text-emerald-400" />
                  <span className="font-medium text-emerald-400">Спор решён</span>
                </div>
                <div className="text-sm">
                  <strong>Решение:</strong> {getResolutionText(dispute.resolution)}
                </div>
                {dispute.resolution_comment && (
                  <div className="text-sm mt-2 text-zinc-400">
                    <strong>Комментарий:</strong> {dispute.resolution_comment}
                  </div>
                )}
                <div className="text-xs text-zinc-500 mt-2">
                  Решено: {formatDate(dispute.resolved_at)}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Chat */}
        <Card className="bg-zinc-900 border-zinc-800">
          <div className="border-b border-zinc-800 p-4">
            <div className="flex items-center gap-2">
              <MessageCircle className="w-5 h-5 text-emerald-500" />
              <span className="font-medium">Чат с поддержкой</span>
            </div>
          </div>

          {/* Messages */}
          <div className="h-[400px] overflow-y-auto p-4 space-y-4">
            {messages.length === 0 ? (
              <div className="text-center text-zinc-500 py-8">
                <MessageCircle className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>Пока нет сообщений</p>
                <p className="text-sm">Напишите нам, и мы поможем решить вопрос</p>
              </div>
            ) : (
              messages.map((msg) => {
                // Определяем роль и стили
                const isAdmin = msg.sender_role === 'admin' || msg.sender_role === 'moderator';
                const isTrader = msg.sender_role === 'trader';
                const isMerchant = msg.sender_role === 'merchant';
                const isBuyerMsg = msg.sender_role === 'buyer';
                
                const getSenderName = () => {
                  if (isAdmin) return 'Администрация';
                  if (isTrader) return 'Трейдер';
                  if (isMerchant) return 'Мерчант';
                  return 'Клиент';
                };
                
                const getSenderColor = () => {
                  if (isAdmin) return 'text-red-400';
                  if (isTrader) return 'text-emerald-400';
                  if (isMerchant) return 'text-orange-400';
                  return 'text-blue-400';
                };
                
                const getBgColor = () => {
                  if (isAdmin) return 'bg-red-500/20 border border-red-500/30';
                  if (isTrader) return 'bg-emerald-500/20 border border-emerald-500/30';
                  if (isMerchant) return 'bg-orange-500/20 border border-orange-500/30';
                  if (isBuyerMsg) return 'bg-blue-500/20 border border-blue-500/30';
                  return 'bg-zinc-800 border border-zinc-700';
                };
                
                const getIcon = () => {
                  if (isAdmin) return <Shield className="w-4 h-4 text-red-400" />;
                  if (isTrader) return <User className="w-4 h-4 text-emerald-400" />;
                  if (isMerchant) return <User className="w-4 h-4 text-orange-400" />;
                  return <User className="w-4 h-4 text-blue-400" />;
                };
                
                // Проверяем есть ли URL в тексте
                const urlRegex = /(https?:\/\/[^\s]+)/g;
                const hasUrl = urlRegex.test(msg.text);
                
                // Функция рендера текста с кликабельными ссылками
                const renderTextWithLinks = (text) => {
                  const parts = text.split(urlRegex);
                  return parts.map((part, i) => {
                    if (part.match(urlRegex)) {
                      return (
                        <span key={i} className="block mt-2">
                          <a 
                            href={part} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="text-emerald-400 hover:text-emerald-300 underline break-all"
                          >
                            {part}
                          </a>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => copyToClipboard(part)}
                            className="ml-2 h-6 px-2 text-xs text-zinc-400 hover:text-white"
                          >
                            <Copy className="w-3 h-3 mr-1" />
                            Копировать
                          </Button>
                        </span>
                      );
                    }
                    return <span key={i}>{part}</span>;
                  });
                };
                
                return (
                  <div
                    key={msg.id}
                    className={`flex ${isBuyerMsg ? 'justify-end' : 'justify-start'}`}
                  >
                    <div className={`max-w-[80%] rounded-lg p-3 ${getBgColor()}`}>
                      <div className="flex items-center gap-2 mb-1">
                        {getIcon()}
                        <span className={`text-xs font-medium ${getSenderColor()}`}>
                          {getSenderName()}
                        </span>
                        <span className="text-xs text-zinc-500">
                          {formatDate(msg.created_at).split(' ')[1]}
                        </span>
                      </div>
                      <div className="text-sm whitespace-pre-wrap">
                        {hasUrl ? renderTextWithLinks(msg.text) : msg.text}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          {dispute?.status === 'open' ? (
            <form onSubmit={handleSendMessage} className="border-t border-zinc-800 p-4">
              <div className="flex gap-2">
                <Textarea
                  placeholder="Напишите сообщение..."
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  className="bg-zinc-800 border-zinc-700 min-h-[60px] resize-none"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage(e);
                    }
                  }}
                  data-testid="message-input"
                />
                <Button
                  type="submit"
                  disabled={sending || !newMessage.trim()}
                  className="bg-emerald-500 hover:bg-emerald-600 px-4"
                  data-testid="send-message-btn"
                >
                  {sending ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <Send className="w-5 h-5" />
                  )}
                </Button>
              </div>
              <p className="text-xs text-zinc-500 mt-2">
                Shift + Enter для новой строки
              </p>
            </form>
          ) : (
            <div className="border-t border-zinc-800 p-4 text-center text-zinc-500">
              <p>Спор закрыт, отправка сообщений недоступна</p>
            </div>
          )}
        </Card>

        {/* Footer */}
        <div className="mt-6 text-center text-sm text-zinc-500">
          <p>Если у вас остались вопросы, напишите нам в чат</p>
          <p>Время работы поддержки: круглосуточно</p>
        </div>
      </main>
      
      {/* Cancel Dispute Confirmation Dialog */}
      <AlertDialog open={showCancelDialog} onOpenChange={setShowCancelDialog}>
        <AlertDialogContent className="bg-zinc-900 border-zinc-800">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-xl">⚠️ Отменить спор?</AlertDialogTitle>
            <AlertDialogDescription className="text-zinc-400">
              <p className="mb-4">Вы уверены, что хотите отменить спор?</p>
              <ul className="list-disc list-inside space-y-2 text-sm">
                <li>Средства будут возвращены трейдеру</li>
                <li>Заказ будет отменён</li>
                <li className="text-red-400 font-medium">Вы НЕ сможете открыть спор по этому заказу снова</li>
              </ul>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="bg-zinc-800 border-zinc-700 hover:bg-zinc-700">
              Отмена
            </AlertDialogCancel>
            <AlertDialogAction 
              onClick={handleCancelDispute}
              className="bg-red-500 hover:bg-red-600"
            >
              Да, отменить спор
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default PublicDispute;
