/**
 * Merchant Messages Page - Messages from administration only
 */

import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { 
  Send, Loader, MessageCircle, Shield, AlertTriangle, 
  CheckCircle, XCircle, HelpCircle, ShoppingBag, 
  ArrowRightLeft, Users, Plus, RefreshCw
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { useAuth, API } from '../App';

// Role configurations
const ROLE_CONFIG = {
  user: { color: 'bg-white text-black border border-gray-300', name: 'Пользователь', icon: '' },
  buyer: { color: 'bg-white text-black border border-gray-300', name: 'Покупатель', icon: '' },
  trader: { color: 'bg-white text-black border border-gray-300', name: 'Трейдер', icon: '' },
  merchant: { color: 'bg-[#F97316] text-white', name: 'Мерчант', icon: '🏢' },
  mod_p2p: { color: 'bg-[#F59E0B] text-white', name: 'Модератор P2P', icon: '' },
  mod_market: { color: 'bg-[#F59E0B] text-white', name: 'Гарант', icon: '⚖️' },
  support: { color: 'bg-[#3B82F6] text-white', name: 'Поддержка', icon: '' },
  admin: { color: 'bg-[#EF4444] text-white', name: 'Администратор', icon: '' },
  owner: { color: 'bg-[#EF4444] text-white', name: 'Владелец', icon: '' },
  system: { color: 'bg-[#6B7280] text-white', name: 'Система', icon: '' }
};

const getRoleInfo = (role) => ROLE_CONFIG[role] || ROLE_CONFIG.user;

const TYPE_CONFIG = {
  support_ticket: { icon: HelpCircle, label: 'Обращение в поддержку', color: 'text-[#3B82F6]' },
  admin_message: { icon: Shield, label: 'Сообщение от администрации', color: 'text-[#EF4444]' },
  admin_user_chat: { icon: Shield, label: 'Сообщение от администрации', color: 'text-[#EF4444]' },
  merchant_application: { icon: MessageCircle, label: 'Заявка мерчанта', color: 'text-[#F97316]' }
};

export default function MerchantMessagesPage() {
  const { token, user } = useAuth();
  const [conversations, setConversations] = useState([]);
  const [broadcasts, setBroadcasts] = useState([]);
  const [selectedConv, setSelectedConv] = useState(null);
  const [selectedBroadcast, setSelectedBroadcast] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [showNewTicket, setShowNewTicket] = useState(false);
  const [ticketForm, setTicketForm] = useState({ category: 'other', subject: '', message: '' });
  const messagesEndRef = useRef(null);

  // Fetch conversations
  useEffect(() => {
    fetchConversations();
    const interval = setInterval(fetchConversations, 10000);
    return () => clearInterval(interval);
  }, []);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Poll for messages when conversation selected
  useEffect(() => {
    if (selectedConv) {
      const interval = setInterval(() => fetchMessages(selectedConv.id), 5000);
      return () => clearInterval(interval);
    }
  }, [selectedConv?.id]);

  const fetchConversations = async () => {
    try {
      const response = await axios.get(`${API}/msg/merchant/conversations`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      // Only show support/admin messages
      const allConvs = response.data || [];
      const filtered = allConvs.filter(c => ['support_ticket', 'admin_message', 'admin_user_chat', 'merchant_application'].includes(c.type));
      setConversations(filtered);
    } catch (error) {
      console.error('Error fetching conversations:', error);
    } finally {
      setLoading(false);
    }
    
    // Fetch broadcasts
    fetchBroadcasts();
  };

  const fetchBroadcasts = async () => {
    try {
      const response = await axios.get(`${API}/notifications/broadcasts`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setBroadcasts(response.data || []);
    } catch (error) {
      console.error('Error fetching broadcasts:', error);
    }
  };

  const markBroadcastRead = async (notificationId) => {
    try {
      await axios.post(`${API}/notifications/${notificationId}/read`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setBroadcasts(prev => prev.map(b => 
        b.id === notificationId ? { ...b, is_read: true } : b
      ));
    } catch (error) {
      console.error('Error marking broadcast read:', error);
    }
  };

  const fetchMessages = async (convId) => {
    try {
      const response = await axios.get(`${API}/msg/merchant/conversations/${convId}/messages`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setMessages(response.data || []);
      
      // Mark as read
      try {
        await axios.post(`${API}/msg/merchant/conversations/${convId}/read`, {}, {
          headers: { Authorization: `Bearer ${token}` }
        });
      } catch (e) {}
    } catch (error) {
      console.error('Error fetching messages:', error);
    }
  };

  const selectConversation = (conv) => {
    setSelectedConv(conv);
    fetchMessages(conv.id);
  };

  const sendMessage = async () => {
    if (!newMessage.trim() || !selectedConv) return;
    
    setSending(true);
    try {
      await axios.post(
        `${API}/msg/merchant/conversations/${selectedConv.id}/messages`,
        { content: newMessage },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setNewMessage('');
      fetchMessages(selectedConv.id);
    } catch (error) {
      toast.error('Ошибка отправки');
    } finally {
      setSending(false);
    }
  };

  const createSupportTicket = async () => {
    if (!ticketForm.subject.trim() || !ticketForm.message.trim()) {
      toast.error('Заполните все поля');
      return;
    }
    
    try {
      const response = await axios.post(
        `${API}/msg/support/create`,
        ticketForm,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success('Обращение создано');
      setShowNewTicket(false);
      setTicketForm({ category: 'other', subject: '', message: '' });
      fetchConversations();
      if (response.data.conversation_id) {
        fetchMessages(response.data.conversation_id);
      }
    } catch (error) {
      toast.error('Ошибка создания обращения');
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  };

  // Sort conversations: unread first, then by updated_at
  const filteredConversations = [...conversations].sort((a, b) => {
    // Unread messages first
    const aUnread = (a.unread_count || 0) > 0 ? 1 : 0;
    const bUnread = (b.unread_count || 0) > 0 ? 1 : 0;
    if (bUnread !== aUnread) return bUnread - aUnread;
    // Then by updated_at (newest first)
    return new Date(b.updated_at || 0) - new Date(a.updated_at || 0);
  });

  return (
    <div className="space-y-4" data-testid="merchant-messages-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Сообщения</h1>
          <p className="text-[#71717A] text-sm">Сообщения от администрации</p>
        </div>
        <Button
          onClick={() => setShowNewTicket(true)}
          className="bg-[#F97316] hover:bg-[#EA580C] text-white"
          data-testid="new-support-ticket-btn"
         title="Написать сообщение">
          <Plus className="w-4 h-4 mr-2" /> Написать в поддержку
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 h-[calc(100vh-280px)]">
        {/* Conversations List */}
        <div className="bg-[#121212] border border-white/5 rounded-xl overflow-hidden flex flex-col">
          <div className="p-3 border-b border-white/5 flex items-center justify-between">
            <h3 className="text-white font-semibold text-sm">
              Чаты ({filteredConversations.length})
            </h3>
            <Button
              variant="ghost"
              size="sm"
              onClick={fetchConversations}
              className="text-[#71717A] hover:text-white h-8 w-8 p-0"
            >
              <RefreshCw className="w-4 h-4" />
            </Button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center h-40">
                <Loader className="w-5 h-5 text-[#F97316] animate-spin" />
              </div>
            ) : filteredConversations.length === 0 && broadcasts.length === 0 ? (
              <div className="p-6 text-center">
                <MessageCircle className="w-10 h-10 text-[#52525B] mx-auto mb-3" />
                <p className="text-[#71717A] text-sm">Нет сообщений</p>
                  <Button 
                    onClick={() => setShowNewTicket(true)}
                    className="mt-3 bg-[#3B82F6] hover:bg-[#2563EB] text-white text-xs"
                   title="Создать новое обращение">
                    Написать в поддержку
                  </Button>
              </div>
            ) : (
              <>
              {/* Broadcasts first - unread on top */}
              {broadcasts.length > 0 && (
                <>
                  <div className="px-3 py-2 bg-[#F59E0B]/10 border-b border-[#F59E0B]/20">
                    <span className="text-[#F59E0B] text-xs font-medium flex items-center gap-1">
                      <Shield className="w-3 h-3" />
                      Рассылки от администрации ({broadcasts.length})
                    </span>
                  </div>
                  {[...broadcasts].sort((a, b) => (b.is_read ? 0 : 1) - (a.is_read ? 0 : 1)).map((b) => (
                    <div
                      key={b.id}
                      onClick={() => {
                        setSelectedConv(null);
                        setSelectedBroadcast(b);
                        if (!b.is_read) markBroadcastRead(b.id);
                      }}
                      className={`p-3 border-b border-white/5 cursor-pointer transition-colors ${
                        selectedBroadcast?.id === b.id 
                          ? 'bg-[#F59E0B]/10 border-l-2 border-l-[#F59E0B]' 
                          : 'hover:bg-white/5'
                      }`}
                    >
                      <div className="flex items-start gap-2">
                        <Shield className="w-4 h-4 mt-0.5 text-[#F59E0B]" />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-white text-sm font-medium truncate">
                              {b.title || 'Рассылка'}
                            </span>
                            {!b.is_read && (
                              <span className="bg-[#F59E0B] text-white text-[9px] px-1.5 py-0.5 rounded">
                                НОВОЕ
                              </span>
                            )}
                          </div>
                          <p className="text-[#52525B] text-xs mt-1 truncate">
                            {b.message?.slice(0, 50)}...
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </>
              )}
              
              {/* Chats */}
              {filteredConversations.map((conv) => {
                const typeConfig = TYPE_CONFIG[conv.type] || TYPE_CONFIG.support_ticket;
                const TypeIcon = typeConfig.icon;
                const isDispute = conv.status === 'dispute' || conv.status === 'disputed' || conv.type === 'p2p_dispute' || typeConfig.isDispute;
                const isSelected = selectedConv?.id === conv.id;
                
                return (
                  <div
                    key={conv.id}
                    onClick={() => selectConversation(conv)}
                    className={`p-3 border-b border-white/5 cursor-pointer transition-colors ${
                      isSelected 
                        ? 'bg-[#F97316]/10 border-l-2 border-l-[#F97316]' 
                        : isDispute
                        ? 'bg-[#EF4444]/5 hover:bg-[#EF4444]/10 border-l-2 border-l-[#EF4444]'
                        : 'hover:bg-white/5'
                    }`}
                    data-testid={`conversation-${conv.id}`}
                  >
                    <div className="flex items-start gap-2">
                      <TypeIcon className={`w-4 h-4 mt-0.5 ${typeConfig.color}`} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-white text-sm font-medium truncate">{conv.title}</span>
                          {conv.unread_count > 0 && (
                            <span className="bg-[#10B981] text-white text-[9px] px-1.5 py-0.5 rounded flex-shrink-0">
                              НОВОЕ
                            </span>
                          )}
                          {isDispute && (
                            <span className="bg-[#EF4444] text-white text-[9px] px-1.5 py-0.5 rounded flex-shrink-0">
                              СПОР
                            </span>
                          )}
                        </div>
                        <p className="text-[#71717A] text-xs">{typeConfig.label}</p>
                        {conv.subtitle && (
                          <p className="text-[#52525B] text-xs mt-1 truncate">{conv.subtitle}</p>
                        )}
                      </div>
                      {conv.unread_count > 0 && (
                        <span className="bg-[#EF4444] text-white text-xs font-bold w-5 h-5 flex items-center justify-center rounded-full flex-shrink-0">
                          {conv.unread_count}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
              </>
            )}
          </div>
        </div>

        {/* Chat Area */}
        <div className="lg:col-span-2 bg-[#121212] border border-white/5 rounded-xl overflow-hidden flex flex-col">
          {selectedBroadcast ? (
            // Show broadcast content
            <div className="flex-1 flex flex-col">
              <div className="p-4 border-b border-white/5 bg-[#F59E0B]/10">
                <div className="flex items-center gap-2">
                  <Shield className="w-5 h-5 text-[#F59E0B]" />
                  <h3 className="text-white font-semibold">
                    {selectedBroadcast.title || 'Рассылка от администрации'}
                  </h3>
                </div>
                <p className="text-[#71717A] text-xs mt-1">
                  {new Date(selectedBroadcast.created_at).toLocaleString('ru-RU')}
                </p>
              </div>
              <div className="flex-1 overflow-y-auto p-4">
                <div className="bg-[#0A0A0A] border border-white/5 rounded-xl p-4">
                  <p className="text-white whitespace-pre-wrap">{selectedBroadcast.message}</p>
                </div>
              </div>
              <div className="p-3 border-t border-white/5">
                <Button 
                  onClick={() => setSelectedBroadcast(null)}
                  variant="outline"
                  className="w-full border-white/10 text-white hover:bg-white/5"
                >
                  Закрыть
                </Button>
              </div>
            </div>
          ) : selectedConv ? (
            <>
              {/* Header */}
              <div className={`p-3 border-b border-white/5 ${selectedConv.status === 'dispute' ? 'bg-[#EF4444]/10' : ''}`}>
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-white font-semibold text-sm flex items-center gap-2">
                      {selectedConv.status === 'dispute' && <AlertTriangle className="w-4 h-4 text-[#EF4444]" />}
                      {selectedConv.title}
                    </h3>
                    {selectedConv.subtitle && (
                      <p className="text-[#71717A] text-xs mt-1">{selectedConv.subtitle}</p>
                    )}
                  </div>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={() => setSelectedConv(null)}
                    className="text-[#71717A] hover:text-white"
                  >
                    <XCircle className="w-4 h-4" />
                  </Button>
                </div>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-3 space-y-3">
                {messages.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full">
                    <MessageCircle className="w-10 h-10 text-[#52525B] mb-2" />
                    <p className="text-[#71717A] text-sm">Нет сообщений</p>
                  </div>
                ) : (
                  messages.map((msg) => {
                    const isOwn = msg.sender_id === user?.id;
                    const isSystem = msg.is_system || msg.sender_role === 'system';
                    const roleInfo = getRoleInfo(msg.sender_role);
                    
                    if (isSystem) {
                      return (
                        <div key={msg.id} className="flex justify-center">
                          <div className="bg-[#6B7280]/20 text-[#A1A1AA] text-xs px-3 py-1.5 rounded-full max-w-[80%] text-center">
                            {msg.content}
                          </div>
                        </div>
                      );
                    }

                    return (
                      <div key={msg.id} className={`flex ${isOwn ? 'justify-end' : 'justify-start'}`}>
                        <div className="max-w-[75%]">
                          {!isOwn && (
                            <div className="text-[10px] text-[#71717A] mb-0.5 ml-2">
                              {roleInfo.icon} {msg.sender_nickname || roleInfo.name} • {roleInfo.name}
                            </div>
                          )}
                          <div className={`px-3 py-2 rounded-xl ${isOwn ? 'bg-[#F97316] text-white' : 'bg-[#1A1A1A] text-white'}`}>
                            <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                            <p className={`text-[9px] mt-1 ${isOwn ? 'text-white/60' : 'text-[#52525B]'}`}>
                              {formatDate(msg.created_at)}
                            </p>
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Input */}
              {selectedConv.status !== 'completed' && (
                <div className="p-3 border-t border-white/5">
                  <div className="flex gap-2">
                    <Input
                      value={newMessage}
                      onChange={(e) => setNewMessage(e.target.value)}
                      placeholder="Введите сообщение..."
                      className="flex-1 bg-[#0A0A0A] border-white/10 text-white h-10"
                      onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                      data-testid="message-input"
                    />
                    <Button
                      onClick={sendMessage}
                      disabled={sending || !newMessage.trim()}
                      className="bg-[#F97316] hover:bg-[#EA580C] text-white h-10 px-4"
                      data-testid="send-message-btn"
                    >
                      {sending ? <Loader className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                    </Button>
                  </div>
                </div>
              )}

              {/* Role legend */}
              <div className="px-3 py-2 border-t border-white/5 bg-[#0A0A0A]">
                <div className="flex flex-wrap gap-3 text-[10px] text-[#71717A]">
                  <span className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-white border border-gray-400" /> Пользователь</span>
                  <span className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-[#F97316]" /> Мерчант</span>
                  <span className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-[#F59E0B]" /> Модератор</span>
                  <span className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-[#3B82F6]" /> Поддержка</span>
                  <span className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-[#EF4444]" /> Админ</span>
                </div>
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <MessageCircle className="w-12 h-12 text-[#52525B] mx-auto mb-3" />
                <p className="text-[#71717A]">Выберите чат</p>
                <p className="text-[#52525B] text-sm mt-1">или создайте обращение в поддержку</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* New Support Ticket Modal */}
      {showNewTicket && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50" onClick={() => setShowNewTicket(false)}>
          <div className="bg-[#121212] border border-white/10 rounded-xl w-full max-w-md p-6" onClick={e => e.stopPropagation()}>
            <h2 className="text-white font-bold text-lg mb-4">Новое обращение в поддержку</h2>
            
            <div className="space-y-4">
              <div>
                <label className="text-[#71717A] text-xs mb-1 block">Категория</label>
                <select
                  value={ticketForm.category}
                  onChange={(e) => setTicketForm({...ticketForm, category: e.target.value})}
                  className="w-full bg-[#0A0A0A] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  data-testid="ticket-category"
                >
                  <option value="technical">Техническая проблема</option>
                  <option value="payment">Вопрос по оплате</option>
                  <option value="trade">Проблема со сделкой</option>
                  <option value="account">Вопрос по аккаунту</option>
                  <option value="complaint_user">Жалоба на пользователя</option>
                  <option value="complaint_staff">Жалоба на сотрудника</option>
                  <option value="other">Другое</option>
                </select>
              </div>
              
              <div>
                <label className="text-[#71717A] text-xs mb-1 block">Тема</label>
                <Input
                  value={ticketForm.subject}
                  onChange={(e) => setTicketForm({...ticketForm, subject: e.target.value})}
                  placeholder="Кратко опишите проблему"
                  className="bg-[#0A0A0A] border-white/10 text-white"
                  data-testid="ticket-subject"
                />
              </div>
              
              <div>
                <label className="text-[#71717A] text-xs mb-1 block">Сообщение</label>
                <textarea
                  value={ticketForm.message}
                  onChange={(e) => setTicketForm({...ticketForm, message: e.target.value})}
                  placeholder="Подробно опишите вашу проблему..."
                  rows={4}
                  className="w-full bg-[#0A0A0A] border border-white/10 rounded-lg px-3 py-2 text-white text-sm resize-none"
                  data-testid="ticket-message"
                />
              </div>
            </div>
            
            <div className="flex gap-2 mt-6">
              <Button
                variant="ghost"
                onClick={() => setShowNewTicket(false)}
                className="flex-1 text-[#71717A]"
               title="Отменить действие">
                Отмена
              </Button>
              <Button
                onClick={createSupportTicket}
                className="flex-1 bg-[#3B82F6] hover:bg-[#2563EB] text-white"
                data-testid="submit-ticket-btn"
               title="Отправить сообщение">
                Отправить
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
