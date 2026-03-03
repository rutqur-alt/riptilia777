/**
 * My Messages Page - Messages from administration only
 * Simple unified messaging with support/admin
 */

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import axios from 'axios';
import { toast } from 'sonner';
import { 
  Send, Loader, MessageCircle, Shield, AlertTriangle, 
  CheckCircle, XCircle, HelpCircle, ShoppingBag, 
  ArrowRightLeft, Users, Plus, Filter, RefreshCw, LogOut
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { useAuth, API } from '../App';

// Role configurations per СООБЩЕНИЯ.txt spec
const ROLE_CONFIG = {
  user: { color: 'bg-white text-black border border-gray-300', name: 'Пользователь', icon: '' },
  buyer: { color: 'bg-white text-black border border-gray-300', name: 'Покупатель', icon: '' },
  p2p_seller: { color: 'bg-white text-black border border-gray-300', name: 'Продавец', icon: '💱' },
  shop_owner: { color: 'bg-[#8B5CF6] text-white', name: 'Магазин', icon: '🏪' },
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
  crypto_order: { icon: ArrowRightLeft, label: 'Покупка USDT', color: 'text-[#10B981]' }
};

export default function MyMessagesPage() {
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
  const [leavingChat, setLeavingChat] = useState(false);
  const [markingPaid, setMarkingPaid] = useState(false);
  const messagesEndRef = useRef(null);

  // WebSocket for real-time messages in selected conversation
  const onWsMessage = useCallback((data) => {
    if (data.type === "message") {
      setMessages(prev => {
        const exists = prev.some(m => m.id === data.id);
        if (exists) return prev;
        return [...prev, data];
      });
    } else if (data.type === "status_update") {
      setSelectedConv(prev => prev ? { ...prev, status: data.status || prev.status } : prev);
    }
  }, []);

  useWebSocket(
    selectedConv ? `/ws/conversation/${selectedConv.id}` : null,
    onWsMessage,
    { enabled: !!selectedConv }
  );

  // Fetch conversations
  useEffect(() => {
    fetchConversations();
    const interval = setInterval(fetchConversations, 30000);
    return () => clearInterval(interval);
  }, []);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Poll for messages when conversation selected
  useEffect(() => {
    if (selectedConv) {
      const interval = setInterval(() => fetchMessages(selectedConv.id), 30000);
      return () => clearInterval(interval);
    }
  }, [selectedConv?.id]);

  const fetchConversations = async () => {
    try {
      // Fetch both in parallel
      const [convsResponse, broadcastsResponse] = await Promise.all([
        axios.get(`${API}/msg/conversations`, {
          headers: { Authorization: `Bearer ${token}` }
        }),
        axios.get(`${API}/notifications/broadcasts`, {
          headers: { Authorization: `Bearer ${token}` }
        }).catch(() => ({ data: [] }))
      ]);
      
      // Filter conversations
      const allConvs = convsResponse.data || [];
      const filtered = allConvs.filter(c => 
        ['support_ticket', 'admin_message', 'admin_user_chat', 'crypto_order'].includes(c.type)
      );
      setConversations(filtered);
      
      // Set broadcasts
      setBroadcasts(broadcastsResponse.data || []);
    } catch (error) {
      console.error('Error fetching conversations:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchBroadcasts = async () => {
    try {
      const response = await axios.get(`${API}/notifications/broadcasts`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      console.log('Broadcasts loaded:', response.data);
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
      const response = await axios.get(`${API}/msg/conversations/${convId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSelectedConv(response.data.conversation);
      setMessages(response.data.messages || []);
    } catch (error) {
      toast.error('Ошибка загрузки сообщений');
    }
  };

  const selectConversation = async (conv) => {
    setSelectedConv(conv);
    setSelectedBroadcast(null);
    fetchMessages(conv.id);
    
    // Mark conversation as read
    if (conv.unread_count > 0) {
      try {
        await axios.post(`${API}/msg/conversations/${conv.id}/read`, {}, {
          headers: { Authorization: `Bearer ${token}` }
        });
        // Update local state to remove "NEW" badge
        setConversations(prev => prev.map(c => 
          c.id === conv.id ? { ...c, unread_count: 0 } : c
        ));
      } catch (error) {
        console.error('Error marking conversation as read:', error);
      }
    }
  };

  const sendMessage = async () => {
    if (!newMessage.trim() || !selectedConv) return;
    
    setSending(true);
    try {
      await axios.post(
        `${API}/msg/conversations/${selectedConv.id}/send`,
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
      fetchMessages(response.data.conversation_id);
    } catch (error) {
      toast.error('Ошибка создания обращения');
    }
  };

  const handleLeaveChat = async () => {
    if (!selectedConv) return;
    setLeavingChat(true);
    try {
      await axios.post(`${API}/msg/user/conversation/${selectedConv.id}/leave`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Вы покинули чат");
      setSelectedConv(null);
      fetchConversations();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Не удалось покинуть чат");
    } finally {
      setLeavingChat(false);
    }
  };

  // Mark crypto order as paid (for traders buying USDT)
  const handleMarkPaid = async () => {
    if (!selectedConv || !selectedConv.related_id) return;
    setMarkingPaid(true);
    try {
      await axios.post(`${API}/crypto/orders/${selectedConv.related_id}/mark-paid`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Оплата отмечена! Ожидайте подтверждения модератора.");
      fetchMessages(selectedConv.id);
      fetchConversations();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Не удалось отметить оплату");
    } finally {
      setMarkingPaid(false);
    }
  };

  // Check if user can mark order as paid
  const canMarkPaid = () => {
    if (!selectedConv) return false;
    return selectedConv.type === 'crypto_order' && selectedConv.status === 'active';
  };

  const canLeaveChat = () => {
    if (!selectedConv) return false;
    // Can leave if conversation is resolved/archived/completed/cancelled
    return ['completed', 'cancelled', 'resolved', 'approved', 'rejected', 'closed'].includes(selectedConv.status);
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  };

  // Combine broadcasts and conversations into unified list, sort by date (newest first)
  const allItems = useMemo(() => {
    // Convert broadcasts to unified format
    const broadcastItems = broadcasts.map(b => ({
      id: b.id,
      type: 'broadcast',
      title: b.title || 'Рассылка',
      last_message: { content: b.message },
      unread_count: b.is_read ? 0 : 1,
      is_read: b.is_read,
      updated_at: b.created_at,
      created_at: b.created_at,
      original: b
    }));
    
    // Convert conversations to unified format
    const convItems = conversations.map(c => ({
      ...c,
      type: c.type,
      original: c
    }));
    
    // Combine and sort ONLY by date (newest first)
    const combined = [...broadcastItems, ...convItems];
    
    return combined.sort((a, b) => {
      // Sort by date only - newest messages first
      const aDate = new Date(a.updated_at || a.last_message_at || a.created_at || 0).getTime();
      const bDate = new Date(b.updated_at || b.last_message_at || b.created_at || 0).getTime();
      return bDate - aDate;
    });
  }, [conversations, broadcasts]);

  return (
    <div className="space-y-4" data-testid="my-messages-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Сообщения</h1>
          <p className="text-[#71717A] text-sm">Сообщения от администрации</p>
        </div>
        <Button
          onClick={() => setShowNewTicket(true)}
          className="bg-[#7C3AED] hover:bg-[#6D28D9] text-white"
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
              Чаты ({allItems.length})
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
                <Loader className="w-5 h-5 text-[#7C3AED] animate-spin" />
              </div>
            ) : allItems.length === 0 ? (
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
              {/* Unified list: broadcasts + conversations sorted together */}
              {allItems.map((item) => {
                // Broadcast item
                if (item.type === 'broadcast') {
                  const b = item.original;
                  return (
                    <div
                      key={`broadcast-${b.id}`}
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
                  );
                }
                
                // Conversation item
                const conv = item;
                const typeConfig = TYPE_CONFIG[conv.type] || TYPE_CONFIG.support_ticket;
                const TypeIcon = typeConfig.icon;
                const isDispute = conv.status === 'dispute' || conv.status === 'disputed' || conv.type === 'p2p_dispute' || typeConfig.isDispute;
                const isSelected = selectedConv?.id === conv.id;
                
                // Show "NEW" badge only for unread messages
                const hasUnread = (conv.unread_count || 0) > 0;
                
                return (
                  <div
                    key={conv.id}
                    onClick={() => selectConversation(conv)}
                    className={`p-3 border-b border-white/5 cursor-pointer transition-colors ${
                      isSelected 
                        ? 'bg-[#7C3AED]/10 border-l-2 border-l-[#7C3AED]' 
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
                          {hasUnread && (
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
                        {conv.last_message && (
                          <p className="text-[#52525B] text-xs mt-1 truncate">
                            {conv.last_message.sender_name}: {conv.last_message.content?.slice(0, 30)}...
                          </p>
                        )}
                      </div>
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
                    <div className="flex items-center gap-2 mt-1">
                      {selectedConv.delete_locked && (
                        <span className="text-[#F59E0B] text-xs flex items-center gap-1">
                          <Shield className="w-3 h-3" /> Удаление запрещено
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {canLeaveChat() && (
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        onClick={handleLeaveChat}
                        disabled={leavingChat}
                        className="text-[#EF4444] hover:text-white hover:bg-[#EF4444]/20"
                        data-testid="leave-chat-btn"
                      >
                        {leavingChat ? <Loader className="w-4 h-4 animate-spin" /> : <LogOut className="w-4 h-4" />}
                        <span className="ml-1 text-xs">Покинуть</span>
                      </Button>
                    )}
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
                
                {/* Participants */}
                <div className="flex flex-wrap gap-2 mt-2">
                  {selectedConv.participants?.map((p, idx) => {
                    const roleInfo = getRoleInfo(p.role);
                    return (
                      <span key={idx} className={`text-[10px] px-2 py-0.5 rounded ${roleInfo.color}`}>
                        {roleInfo.icon} {p.name}
                      </span>
                    );
                  })}
                </div>
              </div>

              {/* Action buttons for crypto orders */}
              {selectedConv.type === 'crypto_order' && (
                <div className="p-3 border-b border-white/5 bg-[#0A0A0A]">
                  <div className="text-[10px] text-[#52525B] mb-2">ДЕЙСТВИЯ:</div>
                  <div className="flex flex-wrap gap-2">
                    {canMarkPaid() && (
                      <Button 
                        onClick={handleMarkPaid}
                        disabled={markingPaid}
                        className="bg-[#10B981] hover:bg-[#059669] text-white text-xs h-8 px-4"
                        data-testid="mark-paid-btn"
                      >
                        {markingPaid ? <Loader className="w-4 h-4 animate-spin mr-2" /> : <CheckCircle className="w-4 h-4 mr-2" />}
                        Я оплатил
                      </Button>
                    )}
                    {selectedConv.status === 'paid' && (
                      <div className="flex items-center gap-2 text-[#3B82F6] text-xs">
                        <Loader className="w-4 h-4 animate-spin" />
                        Ожидайте подтверждения модератора
                      </div>
                    )}
                    {selectedConv.status === 'completed' && (
                      <div className="flex items-center gap-2 text-[#10B981] text-xs">
                        <CheckCircle className="w-4 h-4" />
                        Сделка завершена! USDT зачислены на ваш баланс
                      </div>
                    )}
                  </div>
                </div>
              )}

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
                    const isSystem = msg.is_system;
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
                              {roleInfo.icon} {msg.sender_name} • {roleInfo.name}
                            </div>
                          )}
                          <div className={`px-3 py-2 rounded-xl ${isOwn ? 'bg-[#7C3AED] text-white' : roleInfo.color}`}>
                            {msg.is_deleted ? (
                              <span className="italic opacity-60">Сообщение удалено</span>
                            ) : (
                              <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                            )}
                            <p className={`text-[9px] mt-1 ${isOwn ? 'text-white/60' : 'opacity-60'}`}>
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
                      className="bg-[#7C3AED] hover:bg-[#6D28D9] text-white h-10 px-4"
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
                  <span className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-[#8B5CF6]" /> Магазин</span>
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
                <p className="text-[#71717A]">Выберите чат или рассылку</p>
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
