/**
 * Unified Admin Chat Components
 * Based on messaging specification from СООБЩЕНИЯ.txt
 * 
 * Role Colors per spec:
 * - User/Buyer: white
 * - P2P Seller: white + 💱
 * - Shop Owner: purple (#8B5CF6)
 * - Merchant: orange (#F97316)  
 * - P2P Moderator: yellow (#F59E0B)
 * - Marketplace Moderator/Guarantor: yellow + ⚖️
 * - Support: blue (#3B82F6)
 * - Administrator: red (#EF4444)
 * - System: gray (#6B7280)
 */

import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { 
  Send, Loader, MessageCircle, Shield, AlertTriangle, 
  CheckCircle, XCircle, Trash2, Users, Scale, RefreshCw
} from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';

// API base from App
const API = process.env.REACT_APP_BACKEND_URL || '';

// ==================== ROLE CONFIGURATION ====================
// Per spec: exact colors for each role
const ROLE_CONFIG = {
  user: { bg: 'bg-white text-black border border-gray-300', name: 'Пользователь', icon: '' },
  buyer: { bg: 'bg-white text-black border border-gray-300', name: 'Покупатель', icon: '' },
  p2p_seller: { bg: 'bg-white text-black border border-gray-300', name: 'Продавец P2P', icon: '💱' },
  shop_owner: { bg: 'bg-[#8B5CF6] text-white', name: 'Владелец магазина', icon: '🏪' },
  merchant: { bg: 'bg-[#F97316] text-white', name: 'Мерчант', icon: '🏢' },
  mod_p2p: { bg: 'bg-[#F59E0B] text-white', name: 'Модератор P2P', icon: '' },
  mod_market: { bg: 'bg-[#F59E0B] text-white', name: 'Гарант', icon: '⚖️' },
  support: { bg: 'bg-[#3B82F6] text-white', name: 'Поддержка', icon: '' },
  admin: { bg: 'bg-[#EF4444] text-white', name: 'Администратор', icon: '' },
  owner: { bg: 'bg-[#EF4444] text-white', name: 'Владелец', icon: '' },
  system: { bg: 'bg-[#6B7280] text-white', name: 'Система', icon: '' }
};

const getRoleInfo = (role) => ROLE_CONFIG[role] || ROLE_CONFIG.user;

const formatDate = (dateStr) => {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  return date.toLocaleString('ru-RU', { 
    day: '2-digit', 
    month: '2-digit', 
    hour: '2-digit', 
    minute: '2-digit' 
  });
};

// ==================== DISPUTE CHAT COMPONENT ====================
/**
 * Component for P2P dispute moderation
 * Uses unified messaging API
 */
export function DisputeChat({ 
  tradeId, 
  token, 
  currentUserId, 
  currentUserRole,
  onResolved,
  showActions = true
}) {
  const [conversation, setConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [resolutionReason, setResolutionReason] = useState('');
  const messagesEndRef = useRef(null);

  // Initialize or get conversation for this trade
  const initConversation = async () => {
    try {
      // First try to init (will return existing if exists)
      const initRes = await axios.post(`${API}/api/msg/trade/${tradeId}/init`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      const convId = initRes.data.conversation_id;
      
      // Now fetch the conversation with messages
      const convRes = await axios.get(`${API}/api/msg/conversations/${convId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setConversation(convRes.data.conversation);
      setMessages(convRes.data.messages || []);
    } catch (error) {
      console.error('Error loading dispute chat:', error);
      toast.error('Ошибка загрузки чата');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (tradeId && token) {
      initConversation();
      const interval = setInterval(initConversation, 5000);
      return () => clearInterval(interval);
    }
  }, [tradeId, token]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async () => {
    if (!newMessage.trim() || !conversation) return;
    
    setSending(true);
    try {
      await axios.post(
        `${API}/api/msg/conversations/${conversation.id}/send`,
        { content: newMessage },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setNewMessage('');
      initConversation();
    } catch (error) {
      toast.error('Ошибка отправки');
    } finally {
      setSending(false);
    }
  };

  const handleResolve = async (decision) => {
    if (!resolutionReason.trim()) {
      toast.error('Укажите причину решения');
      return;
    }
    
    setResolving(true);
    try {
      await axios.post(
        `${API}/api/msg/trade/${tradeId}/resolve`,
        { decision, reason: resolutionReason },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success('Решение принято');
      onResolved?.();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка');
    } finally {
      setResolving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader className="w-6 h-6 text-[#7C3AED] animate-spin" />
      </div>
    );
  }

  if (!conversation) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-[#71717A]">Чат не найден</p>
      </div>
    );
  }

  const isDispute = conversation.status === 'dispute';
  const isLocked = conversation.delete_locked;

  return (
    <div className="flex flex-col h-full bg-[#121212] rounded-xl border border-white/5 overflow-hidden">
      {/* Header */}
      <div className={`p-3 border-b border-white/5 ${isDispute ? 'bg-[#EF4444]/10' : ''}`}>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-white font-semibold text-sm flex items-center gap-2">
              {isDispute && <AlertTriangle className="w-4 h-4 text-[#EF4444]" />}
              {conversation.title}
            </h3>
            {isLocked && (
              <span className="text-[#F59E0B] text-xs flex items-center gap-1 mt-1">
                <Shield className="w-3 h-3" /> Удаление сообщений заблокировано
              </span>
            )}
          </div>
        </div>
        
        {/* Participants */}
        <div className="flex flex-wrap gap-2 mt-2">
          {conversation.participants?.map((p, idx) => {
            const roleInfo = getRoleInfo(p.role);
            return (
              <span key={idx} className={`text-[10px] px-2 py-0.5 rounded ${roleInfo.bg}`}>
                {roleInfo.icon} {p.name}
              </span>
            );
          })}
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
            const isOwn = msg.sender_id === currentUserId;
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
                  <div className={`px-3 py-2 rounded-xl ${isOwn ? 'bg-[#7C3AED] text-white' : roleInfo.bg}`}>
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
      <div className="p-3 border-t border-white/5">
        <div className="flex gap-2">
          <Input
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            placeholder="Введите сообщение..."
            className="flex-1 bg-[#0A0A0A] border-white/10 text-white h-10"
            onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
            disabled={conversation.status === 'completed'}
          />
          <Button
            onClick={sendMessage}
            disabled={sending || !newMessage.trim()}
            className="bg-[#7C3AED] hover:bg-[#6D28D9] text-white h-10 px-4"
          >
            {sending ? <Loader className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </Button>
        </div>
      </div>

      {/* Resolution Actions (for moderators in disputes) */}
      {showActions && isDispute && ['admin', 'owner', 'mod_p2p'].includes(currentUserRole) && (
        <div className="p-3 border-t border-white/5 bg-[#0A0A0A] space-y-3">
          <Input
            value={resolutionReason}
            onChange={(e) => setResolutionReason(e.target.value)}
            placeholder="Причина решения..."
            className="bg-[#121212] border-white/10 text-white text-sm h-9"
          />
          <div className="flex gap-2">
            <Button
              onClick={() => handleResolve('refund_buyer')}
              disabled={resolving}
              size="sm"
              className="flex-1 bg-[#3B82F6] hover:bg-[#2563EB] text-white text-xs h-9"
            >
              <CheckCircle className="w-4 h-4 mr-1" /> В пользу покупателя
            </Button>
            <Button
              onClick={() => handleResolve('release_seller')}
              disabled={resolving}
              size="sm"
              className="flex-1 bg-[#10B981] hover:bg-[#059669] text-white text-xs h-9"
            >
              <CheckCircle className="w-4 h-4 mr-1" /> В пользу продавца
            </Button>
          </div>
        </div>
      )}

      {/* Role Legend */}
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
    </div>
  );
}

// ==================== SUPPORT TICKET CHAT COMPONENT ====================
export function SupportTicketChat({ 
  conversationId, 
  token, 
  currentUserId,
  currentUserRole,
  onStatusChange
}) {
  const [conversation, setConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef(null);

  const fetchConversation = async () => {
    try {
      const response = await axios.get(`${API}/api/msg/conversations/${conversationId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setConversation(response.data.conversation);
      setMessages(response.data.messages || []);
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (conversationId && token) {
      fetchConversation();
      const interval = setInterval(fetchConversation, 5000);
      return () => clearInterval(interval);
    }
  }, [conversationId, token]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async () => {
    if (!newMessage.trim() || !conversation) return;
    
    setSending(true);
    try {
      await axios.post(
        `${API}/api/msg/conversations/${conversationId}/send`,
        { content: newMessage },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setNewMessage('');
      fetchConversation();
    } catch (error) {
      toast.error('Ошибка отправки');
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader className="w-6 h-6 text-[#7C3AED] animate-spin" />
      </div>
    );
  }

  if (!conversation) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-[#71717A]">Чат не найден</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full">
            <MessageCircle className="w-10 h-10 text-[#52525B] mb-2" />
            <p className="text-[#71717A] text-sm">Нет сообщений</p>
          </div>
        ) : (
          messages.map((msg) => {
            const isOwn = msg.sender_id === currentUserId;
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
                  <div className={`px-3 py-2 rounded-xl ${isOwn ? 'bg-[#3B82F6] text-white' : roleInfo.bg}`}>
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
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
      <div className="p-3 border-t border-white/5">
        <div className="flex gap-2">
          <Input
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            placeholder="Ответить..."
            className="flex-1 bg-[#0A0A0A] border-white/10 text-white h-10"
            onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
            disabled={conversation.status === 'completed'}
          />
          <Button
            onClick={sendMessage}
            disabled={sending || !newMessage.trim()}
            className="bg-[#3B82F6] hover:bg-[#2563EB] text-white h-10 px-4"
          >
            {sending ? <Loader className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ==================== STAFF CHAT COMPONENT ====================
export function StaffChatComponent({ token, currentUserId, currentUserRole }) {
  const [conversations, setConversations] = useState([]);
  const [selectedConv, setSelectedConv] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef(null);

  const fetchStaffChats = async () => {
    try {
      const response = await axios.get(`${API}/api/msg/staff/chats`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setConversations(response.data || []);
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchGeneralChat = async () => {
    try {
      const response = await axios.get(`${API}/api/msg/staff/general`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (response.data?.messages) {
        setMessages(response.data.messages);
        setSelectedConv({ id: 'general', title: 'Общий чат персонала' });
      }
    } catch (error) {
      console.error('Error:', error);
    }
  };

  const fetchConversationMessages = async (convId) => {
    try {
      const response = await axios.get(`${API}/api/msg/conversations/${convId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setMessages(response.data.messages || []);
      setSelectedConv(response.data.conversation);
    } catch (error) {
      console.error('Error:', error);
    }
  };

  useEffect(() => {
    fetchStaffChats();
    fetchGeneralChat();
    const interval = setInterval(() => {
      fetchStaffChats();
      if (selectedConv?.id === 'general') {
        fetchGeneralChat();
      } else if (selectedConv?.id) {
        fetchConversationMessages(selectedConv.id);
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [token]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async () => {
    if (!newMessage.trim()) return;
    
    setSending(true);
    try {
      if (selectedConv?.id === 'general') {
        await axios.post(
          `${API}/api/msg/staff/general`,
          { content: newMessage },
          { headers: { Authorization: `Bearer ${token}` } }
        );
      } else if (selectedConv?.id) {
        await axios.post(
          `${API}/api/msg/conversations/${selectedConv.id}/send`,
          { content: newMessage },
          { headers: { Authorization: `Bearer ${token}` } }
        );
      }
      setNewMessage('');
      
      if (selectedConv?.id === 'general') {
        fetchGeneralChat();
      } else {
        fetchConversationMessages(selectedConv.id);
      }
    } catch (error) {
      toast.error('Ошибка отправки');
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="flex h-full gap-4">
      {/* Conversations List */}
      <div className="w-64 bg-[#121212] border border-white/5 rounded-xl overflow-hidden flex flex-col">
        <div className="p-3 border-b border-white/5">
          <h3 className="text-white font-semibold text-sm">Чаты персонала</h3>
        </div>
        <div className="flex-1 overflow-y-auto">
          {/* General chat always first */}
          <div
            onClick={() => fetchGeneralChat()}
            className={`p-3 border-b border-white/5 cursor-pointer hover:bg-white/5 ${
              selectedConv?.id === 'general' ? 'bg-[#7C3AED]/10' : ''
            }`}
          >
            <div className="flex items-center gap-2">
              <Users className="w-4 h-4 text-[#7C3AED]" />
              <span className="text-white text-sm font-medium">Общий чат</span>
            </div>
            <p className="text-[#52525B] text-xs mt-1">Все сотрудники</p>
          </div>
          
          {/* Other conversations */}
          {conversations.map((conv) => (
            <div
              key={conv.id}
              onClick={() => fetchConversationMessages(conv.id)}
              className={`p-3 border-b border-white/5 cursor-pointer hover:bg-white/5 ${
                selectedConv?.id === conv.id ? 'bg-[#7C3AED]/10' : ''
              }`}
            >
              <span className="text-white text-sm">{conv.title}</span>
              {conv.unread_count > 0 && (
                <span className="ml-2 bg-[#EF4444] text-white text-[10px] px-1.5 rounded-full">
                  {conv.unread_count}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 bg-[#121212] border border-white/5 rounded-xl overflow-hidden flex flex-col">
        {selectedConv ? (
          <>
            <div className="p-3 border-b border-white/5">
              <h3 className="text-white font-semibold text-sm">{selectedConv.title}</h3>
            </div>
            
            <div className="flex-1 overflow-y-auto p-3 space-y-3">
              {messages.map((msg, idx) => {
                const isOwn = msg.sender_id === currentUserId;
                const roleInfo = getRoleInfo(msg.sender_role);
                
                return (
                  <div key={idx} className={`flex ${isOwn ? 'justify-end' : 'justify-start'}`}>
                    <div className="max-w-[75%]">
                      {!isOwn && (
                        <div className="text-[10px] text-[#71717A] mb-0.5 ml-2">
                          {roleInfo.icon} {msg.sender_name || msg.sender_login} • {roleInfo.name}
                        </div>
                      )}
                      <div className={`px-3 py-2 rounded-xl ${isOwn ? 'bg-[#7C3AED] text-white' : roleInfo.bg}`}>
                        <p className="text-sm whitespace-pre-wrap">{msg.content || msg.message}</p>
                        <p className={`text-[9px] mt-1 ${isOwn ? 'text-white/60' : 'opacity-60'}`}>
                          {formatDate(msg.created_at)}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })}
              <div ref={messagesEndRef} />
            </div>
            
            <div className="p-3 border-t border-white/5">
              <div className="flex gap-2">
                <Input
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  placeholder="Написать сообщение..."
                  className="flex-1 bg-[#0A0A0A] border-white/10 text-white h-10"
                  onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                />
                <Button
                  onClick={sendMessage}
                  disabled={sending || !newMessage.trim()}
                  className="bg-[#7C3AED] hover:bg-[#6D28D9] text-white h-10 px-4"
                >
                  {sending ? <Loader className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                </Button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <MessageCircle className="w-12 h-12 text-[#52525B] mx-auto mb-3" />
              <p className="text-[#71717A]">Выберите чат</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ==================== APPLICATION CHAT COMPONENT ====================
/**
 * Chat for merchant/shop applications
 */
export function ApplicationChat({
  applicationType, // 'merchant' or 'shop'
  userId,
  token,
  currentUserId,
  currentUserRole,
  onApprove,
  onReject
}) {
  const [conversation, setConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef(null);

  const fetchChat = async () => {
    try {
      const response = await axios.get(
        `${API}/api/msg/application/${applicationType}/${userId}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setConversation(response.data.conversation);
      setMessages(response.data.messages || []);
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (userId && token) {
      fetchChat();
      const interval = setInterval(fetchChat, 5000);
      return () => clearInterval(interval);
    }
  }, [userId, token, applicationType]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async () => {
    if (!newMessage.trim() || !conversation) return;
    
    setSending(true);
    try {
      await axios.post(
        `${API}/api/msg/conversations/${conversation.id}/send`,
        { content: newMessage },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setNewMessage('');
      fetchChat();
    } catch (error) {
      toast.error('Ошибка отправки');
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader className="w-6 h-6 text-[#7C3AED] animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full">
            <MessageCircle className="w-10 h-10 text-[#52525B] mb-2" />
            <p className="text-[#71717A] text-sm">Начните переписку</p>
          </div>
        ) : (
          messages.map((msg, idx) => {
            const isOwn = msg.sender_id === currentUserId;
            const isSystem = msg.is_system;
            const roleInfo = getRoleInfo(msg.sender_role);
            
            if (isSystem) {
              return (
                <div key={idx} className="flex justify-center">
                  <div className="bg-[#6B7280]/20 text-[#A1A1AA] text-xs px-3 py-1.5 rounded-full max-w-[80%] text-center">
                    {msg.content}
                  </div>
                </div>
              );
            }

            return (
              <div key={idx} className={`flex ${isOwn ? 'justify-end' : 'justify-start'}`}>
                <div className="max-w-[75%]">
                  {!isOwn && (
                    <div className="text-[10px] text-[#71717A] mb-0.5 ml-2">
                      {roleInfo.icon} {msg.sender_name} • {roleInfo.name}
                    </div>
                  )}
                  <div className={`px-3 py-2 rounded-xl ${isOwn ? 'bg-[#7C3AED] text-white' : roleInfo.bg}`}>
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
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
      <div className="p-3 border-t border-white/5">
        <div className="flex gap-2">
          <Input
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            placeholder={`Сообщение ${applicationType === 'merchant' ? 'мерчанту' : 'заявителю'}...`}
            className="flex-1 bg-[#0A0A0A] border-white/10 text-white h-10"
            onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
          />
          <Button
            onClick={sendMessage}
            disabled={sending || !newMessage.trim()}
            className="bg-[#7C3AED] hover:bg-[#6D28D9] text-white h-10 px-4"
          >
            {sending ? <Loader className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </Button>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="p-3 border-t border-white/5 bg-[#0A0A0A] flex gap-2">
        <Button 
          onClick={onApprove}
          className="flex-1 bg-[#10B981] hover:bg-[#059669] text-white text-xs h-9"
        >
          <CheckCircle className="w-4 h-4 mr-1" /> Одобрить
        </Button>
        <Button 
          onClick={onReject}
          variant="ghost"
          className="flex-1 text-[#EF4444] hover:bg-[#EF4444]/10 text-xs h-9"
        >
          <XCircle className="w-4 h-4 mr-1" /> Отклонить
        </Button>
      </div>
    </div>
  );
}

// Export role config for use elsewhere
export { ROLE_CONFIG, getRoleInfo, formatDate };
