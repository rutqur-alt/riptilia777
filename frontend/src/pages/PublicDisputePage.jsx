import React, { useState, useEffect, useRef } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import axios from 'axios';
import { 
  MessageCircle, Send, AlertTriangle, CheckCircle, XCircle,
  Clock, User, Shield, Copy, ExternalLink, RefreshCw
} from 'lucide-react';
import { API } from '@/App';

// Публичная страница спора - доступна без авторизации по ссылке
const PublicDisputePage = () => {
  const { tradeId } = useParams();
  const [searchParams] = useSearchParams();
  const isBuyer = searchParams.get('buyer') === 'true';
  
  const [trade, setTrade] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [newMessage, setNewMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [buyerName, setBuyerName] = useState('');
  
  const messagesEndRef = useRef(null);

  useEffect(() => {
    fetchDispute();
    const interval = setInterval(fetchDispute, 5000);
    return () => clearInterval(interval);
  }, [tradeId]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const fetchDispute = async () => {
    try {
      const res = await axios.get(`${API}/trades/${tradeId}/dispute-public`);
      setTrade(res.data.trade);
      setMessages(res.data.messages || []);
      setError(null);
    } catch (err) {
      if (err.response?.status === 404) {
        setError('Спор не найден');
      } else {
        setError('Ошибка загрузки данных');
      }
    } finally {
      setLoading(false);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!newMessage.trim()) return;
    
    setSending(true);
    try {
      await axios.post(`${API}/trades/${tradeId}/messages-public`, {
        content: newMessage,
        sender_name: buyerName || 'Клиент'
      });
      setNewMessage('');
      fetchDispute();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Ошибка отправки');
    } finally {
      setSending(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('Скопировано!');
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleString('ru-RU', {
      day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'
    });
  };

  const getRoleIcon = (role, senderType) => {
    if (senderType === 'admin' || role === 'admin' || role === 'mod_p2p') {
      return <Shield className="w-4 h-4 text-red-400" />;
    }
    if (role === 'trader' || senderType === 'trader') {
      return <User className="w-4 h-4 text-emerald-400" />;
    }
    return <User className="w-4 h-4 text-blue-400" />;
  };

  const getRoleLabel = (role, senderType) => {
    if (senderType === 'admin' || role === 'admin') return 'Администрация';
    if (role === 'mod_p2p') return 'Модератор P2P';
    if (role === 'trader' || senderType === 'trader') return 'Трейдер';
    return 'Клиент';
  };

  const getRoleBgColor = (role, senderType) => {
    if (senderType === 'admin' || role === 'admin' || role === 'mod_p2p') {
      return 'bg-red-500/20 border-red-500/30';
    }
    if (role === 'trader' || senderType === 'trader') {
      return 'bg-emerald-500/20 border-emerald-500/30';
    }
    return 'bg-blue-500/20 border-blue-500/30';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#09090B] flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-[#09090B] flex items-center justify-center p-4">
        <div className="text-center max-w-md">
          <XCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-white mb-2">{error}</h2>
          <p className="text-zinc-400 mb-4">Проверьте правильность ссылки</p>
          <Button onClick={fetchDispute} className="bg-emerald-500 hover:bg-emerald-600">
            <RefreshCw className="w-4 h-4 mr-2" />
            Повторить
          </Button>
        </div>
      </div>
    );
  }

  const disputeLink = window.location.href;

  return (
    <div className="min-h-screen bg-[#09090B] text-white">
      {/* Header */}
      <header className="bg-zinc-900 border-b border-zinc-800 py-4">
        <div className="container mx-auto px-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center">
              <Shield className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-lg">Reptiloid • Спор</h1>
              <p className="text-zinc-400 text-sm">Служба поддержки</p>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6 max-w-2xl">
        {/* Trade Info */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 mb-6">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-2">
              {trade?.status === 'disputed' ? (
                <AlertTriangle className="w-5 h-5 text-orange-400" />
              ) : trade?.status === 'completed' ? (
                <CheckCircle className="w-5 h-5 text-emerald-400" />
              ) : (
                <Clock className="w-5 h-5 text-yellow-400" />
              )}
              <span className="font-medium">
                {trade?.status === 'disputed' ? 'Спор открыт' : 
                 trade?.status === 'completed' ? 'Решён' : 'Рассматривается'}
              </span>
            </div>
            <div className="text-right">
              <div className="font-mono text-lg font-bold">
                {trade?.amount_rub?.toLocaleString('ru-RU')} ₽
              </div>
              <div className="text-xs text-zinc-500">
                ≈ {trade?.amount_usdt?.toFixed(2)} USDT
              </div>
            </div>
          </div>

          {/* Order ID */}
          <div className="bg-zinc-800 rounded-lg p-3 mb-4">
            <div className="text-xs text-zinc-500 mb-1">ID сделки</div>
            <div className="flex items-center gap-2">
              <code className="text-sm text-zinc-300 font-mono flex-1 truncate">
                {tradeId}
              </code>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => copyToClipboard(tradeId)}
                className="text-zinc-400 hover:text-white h-7"
              >
                <Copy className="w-4 h-4" />
              </Button>
            </div>
          </div>

          {/* Dispute Link Warning */}
          {trade?.status === 'disputed' && (
            <div className="bg-orange-500/10 border border-orange-500/30 rounded-lg p-4">
              <div className="flex items-center gap-2 text-orange-400 font-medium mb-2">
                <AlertTriangle className="w-4 h-4" />
                ⚠️ Сохраните эту ссылку!
              </div>
              <p className="text-sm text-zinc-400 mb-3">
                По этой ссылке вы сможете вернуться в чат спора
              </p>
              <div className="flex items-center gap-2 bg-zinc-800 rounded-lg p-2">
                <input
                  type="text"
                  readOnly
                  value={disputeLink}
                  className="flex-1 bg-transparent text-sm text-zinc-300 outline-none font-mono truncate"
                />
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => copyToClipboard(disputeLink)}
                  className="text-emerald-400 hover:text-emerald-300"
                 title="Скопировать в буфер обмена">
                  <Copy className="w-4 h-4 mr-1" />
                  Копировать
                </Button>
              </div>
            </div>
          )}

          {/* Dispute reason */}
          {trade?.dispute_reason && (
            <div className="mt-4 p-3 bg-zinc-800 rounded-lg">
              <div className="text-xs text-zinc-500 mb-1">Причина спора</div>
              <div className="text-sm">{trade.dispute_reason}</div>
            </div>
          )}
        </div>

        {/* Chat */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
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
                <p className="text-sm mt-1">Напишите нам, и мы поможем решить вопрос</p>
              </div>
            ) : (
              messages.map((msg) => {
                const isClient = msg.sender_type === 'client' || (!msg.sender_type && !msg.sender_role);
                const isOwnMessage = isClient && isBuyer;
                
                return (
                  <div
                    key={msg.id}
                    className={`flex ${isOwnMessage ? 'justify-end' : 'justify-start'}`}
                  >
                    <div className={`max-w-[80%] rounded-lg p-3 border ${getRoleBgColor(msg.sender_role, msg.sender_type)}`}>
                      <div className="flex items-center gap-2 mb-1">
                        {getRoleIcon(msg.sender_role, msg.sender_type)}
                        <span className="text-xs font-medium">
                          {getRoleLabel(msg.sender_role, msg.sender_type)}
                        </span>
                        <span className="text-xs text-zinc-500">
                          {formatDate(msg.created_at)}
                        </span>
                      </div>
                      <p className="text-sm whitespace-pre-wrap">
                        {msg.message || msg.content}
                      </p>
                    </div>
                  </div>
                );
              })
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          {trade?.status !== 'completed' && trade?.status !== 'cancelled' ? (
            <form onSubmit={handleSendMessage} className="border-t border-zinc-800 p-4">
              {/* Name input for first message */}
              {messages.filter(m => m.sender_type === 'client').length === 0 && (
                <div className="mb-3">
                  <Input
                    placeholder="Ваше имя (необязательно)"
                    value={buyerName}
                    onChange={(e) => setBuyerName(e.target.value)}
                    className="bg-zinc-800 border-zinc-700"
                  />
                </div>
              )}
              <div className="flex gap-2">
                <Input
                  placeholder="Введите сообщение..."
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  className="flex-1 bg-zinc-800 border-zinc-700"
                  disabled={sending}
                  data-testid="dispute-message-input"
                />
                <Button
                  type="submit"
                  disabled={sending || !newMessage.trim()}
                  className="bg-emerald-500 hover:bg-emerald-600"
                  data-testid="dispute-send-btn"
                >
                  {sending ? (
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <Send className="w-5 h-5" />
                  )}
                </Button>
              </div>
            </form>
          ) : (
            <div className="border-t border-zinc-800 p-4 text-center text-zinc-500">
              <CheckCircle className="w-5 h-5 inline-block mr-2 text-emerald-400" />
              Спор закрыт
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="mt-6 text-center text-sm text-zinc-500">
          <p>Служба поддержки работает круглосуточно</p>
        </div>
      </main>
    </div>
  );
};

export default PublicDisputePage;
