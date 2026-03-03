/**
 * Unified Chat Component for Reptiloid Platform
 * Based on messaging specification document
 * 
 * Role Colors:
 * - user/buyer: white
 * - p2p_seller: white + 💱
 * - shop_owner: purple (#8B5CF6)
 * - merchant: orange (#F97316)
 * - mod_p2p: yellow (#F59E0B)
 * - mod_market: yellow + ⚖️
 * - support: blue (#3B82F6)
 * - admin/owner: red (#EF4444)
 * - system: gray (#6B7280)
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import axios from 'axios';
import { toast } from 'sonner';
import { Send, Loader, AlertTriangle, CheckCircle, XCircle, MessageCircle, Shield, Users, Trash2 } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';

const API = process.env.REACT_APP_BACKEND_URL;

// Role configurations
const ROLE_CONFIG = {
  user: { color: 'bg-white text-black border border-gray-200', name: 'Пользователь', icon: '' },
  buyer: { color: 'bg-white text-black border border-gray-200', name: 'Покупатель', icon: '' },
  p2p_seller: { color: 'bg-white text-black border border-gray-200', name: 'Продавец', icon: '💱' },
  shop_owner: { color: 'bg-[#8B5CF6] text-white', name: 'Магазин', icon: '🏪' },
  merchant: { color: 'bg-[#F97316] text-white', name: 'Мерчант', icon: '🏢' },
  mod_p2p: { color: 'bg-[#F59E0B] text-white', name: 'Модератор P2P', icon: '' },
  mod_market: { color: 'bg-[#F59E0B] text-white', name: 'Гарант', icon: '⚖️' },
  support: { color: 'bg-[#3B82F6] text-white', name: 'Поддержка', icon: '' },
  admin: { color: 'bg-[#EF4444] text-white', name: 'Администратор', icon: '' },
  owner: { color: 'bg-[#EF4444] text-white', name: 'Владелец', icon: '' },
  system: { color: 'bg-[#6B7280] text-white', name: 'Система', icon: '' }
};

// Get role display info
const getRoleInfo = (role) => ROLE_CONFIG[role] || ROLE_CONFIG.user;

// Format date
const formatDate = (dateStr) => {
  const date = new Date(dateStr);
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
};

/**
 * UnifiedChat - Main chat component
 * 
 * Props:
 * - conversationId: string - ID of the conversation
 * - token: string - Auth token
 * - currentUserId: string - Current user's ID
 * - onClose: function - Called when chat is closed
 * - showHeader: boolean - Show conversation header
 * - height: string - Height of chat container
 */
export function UnifiedChat({ 
  conversationId, 
  token, 
  currentUserId,
  onClose,
  showHeader = true,
  height = "500px"
}) {
  const [conversation, setConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef(null);

  // Fetch conversation and messages
  const fetchConversation = async () => {
    try {
      const response = await axios.get(`${API}/msg/conversations/${conversationId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setConversation(response.data.conversation);
      setMessages(response.data.messages || []);
    } catch (error) {
      console.error('Error fetching conversation:', error);
      toast.error('Ошибка загрузки чата');
    } finally {
      setLoading(false);
    }
  };

  const onWsChatMessage = useCallback((data) => {
    if (data.type === "message") {
      setMessages(prev => {
        const exists = prev.some(m => m.id === data.id);
        if (exists) return prev;
        return [...prev, data];
      });
    }
  }, []);

  useWebSocket(
    conversationId ? `/ws/conversation/${conversationId}` : null,
    onWsChatMessage,
    { enabled: !!conversationId && !!token }
  );

  useEffect(() => {
    if (conversationId && token) {
      fetchConversation();
      const interval = setInterval(fetchConversation, 30000);
      return () => clearInterval(interval);
    }
  }, [conversationId, token]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Send message
  const handleSend = async () => {
    if (!newMessage.trim()) return;
    
    setSending(true);
    try {
      await axios.post(
        `${API}/msg/conversations/${conversationId}/send`,
        { content: newMessage },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setNewMessage('');
      fetchConversation();
    } catch (error) {
      toast.error('Ошибка отправки сообщения');
    } finally {
      setSending(false);
    }
  };

  // Delete message
  const handleDelete = async (msgId) => {
    try {
      await axios.delete(`${API}/msg/messages/${msgId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      fetchConversation();
      toast.success('Сообщение удалено');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Нельзя удалить сообщение');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center" style={{ height }}>
        <Loader className="w-6 h-6 text-[#7C3AED] animate-spin" />
      </div>
    );
  }

  if (!conversation) {
    return (
      <div className="flex items-center justify-center" style={{ height }}>
        <p className="text-[#71717A]">Чат не найден</p>
      </div>
    );
  }

  const isDispute = conversation.status === 'dispute';
  const isLocked = conversation.delete_locked;

  return (
    <div className="flex flex-col bg-[#121212] rounded-xl border border-white/5 overflow-hidden" style={{ height }}>
      {/* Header */}
      {showHeader && (
        <div className={`p-3 border-b border-white/5 ${isDispute ? 'bg-[#EF4444]/10' : ''}`}>
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-white font-semibold text-sm flex items-center gap-2">
                {isDispute && <AlertTriangle className="w-4 h-4 text-[#EF4444]" />}
                {conversation.title}
              </h3>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-[#71717A] text-xs">
                  {conversation.participants?.length || 0} участников
                </span>
                {isLocked && (
                  <span className="text-[#F59E0B] text-xs flex items-center gap-1">
                    <Shield className="w-3 h-3" /> Удаление запрещено
                  </span>
                )}
              </div>
            </div>
            {onClose && (
              <Button variant="ghost" size="sm" onClick={onClose} className="text-[#71717A] hover:text-white">
                <XCircle className="w-4 h-4" />
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Participants */}
      <div className="px-3 py-2 border-b border-white/5 bg-[#0A0A0A]">
        <div className="flex flex-wrap gap-2">
          {conversation.participants?.map((p, idx) => {
            const roleInfo = getRoleInfo(p.role);
            return (
              <span 
                key={idx} 
                className={`text-xs px-2 py-0.5 rounded ${roleInfo.color}`}
              >
                {roleInfo.icon} {p.name}
              </span>
            );
          })}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <MessageCircle className="w-10 h-10 text-[#52525B] mb-2" />
            <p className="text-[#71717A] text-sm">Нет сообщений</p>
            <p className="text-[#52525B] text-xs">Начните общение</p>
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
                <div className={`max-w-[75%] group`}>
                  {/* Sender info */}
                  {!isOwn && (
                    <div className="text-[10px] text-[#71717A] mb-0.5 ml-2">
                      {roleInfo.icon} {msg.sender_name} • {roleInfo.name}
                    </div>
                  )}
                  
                  {/* Message bubble */}
                  <div className={`px-3 py-2 rounded-xl ${isOwn ? 'bg-[#7C3AED] text-white' : roleInfo.color}`}>
                    {msg.is_deleted ? (
                      <span className="italic text-white/60">Сообщение удалено</span>
                    ) : (
                      <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    )}
                    
                    <div className="flex items-center justify-between mt-1">
                      <span className={`text-[9px] ${isOwn ? 'text-white/60' : 'opacity-60'}`}>
                        {formatDate(msg.created_at)}
                      </span>
                      
                      {/* Delete button (only for own messages, not deleted, not locked) */}
                      {isOwn && !msg.is_deleted && !isLocked && (
                        <button
                          onClick={() => handleDelete(msg.id)}
                          className="opacity-0 group-hover:opacity-100 transition-opacity ml-2"
                        >
                          <Trash2 className="w-3 h-3 text-white/40 hover:text-white/80" />
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-white/5 bg-[#0A0A0A]">
        <div className="flex gap-2">
          <Input
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            placeholder="Введите сообщение..."
            className="flex-1 bg-[#121212] border-white/10 text-white h-10"
            onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            disabled={conversation.status === 'completed'}
          />
          <Button
            onClick={handleSend}
            disabled={sending || !newMessage.trim() || conversation.status === 'completed'}
            className="bg-[#7C3AED] hover:bg-[#6D28D9] text-white h-10 px-4"
          >
            {sending ? <Loader className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </Button>
        </div>
        
        {conversation.status === 'completed' && (
          <p className="text-center text-[#71717A] text-xs mt-2">
            Чат завершён
          </p>
        )}
      </div>

      {/* Role legend */}
      <div className="px-3 py-2 border-t border-white/5 bg-[#0A0A0A]">
        <div className="flex flex-wrap gap-3 text-[10px]">
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

/**
 * ConversationsList - List of user's conversations
 */
export function ConversationsList({ token, currentUserId, onSelectConversation }) {
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(null);

  useEffect(() => {
    const fetchConversations = async () => {
      try {
        const response = await axios.get(`${API}/msg/conversations`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setConversations(response.data || []);
      } catch (error) {
        console.error('Error fetching conversations:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchConversations();
    const interval = setInterval(fetchConversations, 30000);
    return () => clearInterval(interval);
  }, [token]);

  const getTypeLabel = (type) => {
    const labels = {
      p2p_trade: 'P2P Сделка',
      p2p_merchant: 'Сделка мерчанта',
      marketplace: 'Заказ',
      support_ticket: 'Поддержка',
      internal_admin: 'Персонал',
      internal_discussion: 'Обсуждение'
    };
    return labels[type] || type;
  };

  const getStatusBadge = (status) => {
    if (status === 'dispute') {
      return <span className="bg-[#EF4444] text-white text-[9px] px-1.5 py-0.5 rounded">СПОР</span>;
    }
    if (status === 'completed') {
      return <span className="bg-[#10B981] text-white text-[9px] px-1.5 py-0.5 rounded">Завершён</span>;
    }
    return null;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-40">
        <Loader className="w-5 h-5 text-[#7C3AED] animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {conversations.length === 0 ? (
        <div className="text-center py-8">
          <MessageCircle className="w-10 h-10 text-[#52525B] mx-auto mb-2" />
          <p className="text-[#71717A] text-sm">Нет чатов</p>
        </div>
      ) : (
        conversations.map((conv) => (
          <div
            key={conv.id}
            onClick={() => {
              setSelectedId(conv.id);
              onSelectConversation(conv);
            }}
            className={`p-3 rounded-lg border cursor-pointer transition-colors ${
              selectedId === conv.id 
                ? 'bg-[#7C3AED]/10 border-[#7C3AED]' 
                : 'bg-[#121212] border-white/5 hover:bg-white/5'
            }`}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-white font-medium text-sm truncate">{conv.title}</span>
                  {getStatusBadge(conv.status)}
                </div>
                <p className="text-[#71717A] text-xs mt-0.5">{getTypeLabel(conv.type)}</p>
                {conv.last_message && (
                  <p className="text-[#52525B] text-xs mt-1 truncate">
                    {conv.last_message.sender_name}: {conv.last_message.content?.slice(0, 40)}...
                  </p>
                )}
              </div>
              {conv.unread_count > 0 && (
                <span className="bg-[#EF4444] text-white text-xs font-bold w-5 h-5 flex items-center justify-center rounded-full">
                  {conv.unread_count}
                </span>
              )}
            </div>
          </div>
        ))
      )}
    </div>
  );
}

/**
 * DisputeActions - Actions for resolving disputes (moderator only)
 */
export function DisputeActions({ tradeId, token, onResolved }) {
  const [resolving, setResolving] = useState(false);
  const [reason, setReason] = useState('');

  const handleResolve = async (decision) => {
    if (!reason.trim()) {
      toast.error('Укажите причину решения');
      return;
    }
    
    setResolving(true);
    try {
      await axios.post(
        `${API}/msg/trade/${tradeId}/resolve`,
        { decision, reason },
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

  return (
    <div className="p-3 border-t border-white/5 bg-[#0A0A0A] space-y-3">
      <Input
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="Причина решения..."
        className="bg-[#121212] border-white/10 text-white text-sm h-9"
      />
      <div className="flex gap-2">
        <Button
          onClick={() => handleResolve('refund_buyer')}
          disabled={resolving}
          size="sm"
          className="flex-1 bg-[#F59E0B] hover:bg-[#D97706] text-white text-xs h-9"
        >
          В пользу покупателя
        </Button>
        <Button
          onClick={() => handleResolve('release_seller')}
          disabled={resolving}
          size="sm"
          className="flex-1 bg-[#10B981] hover:bg-[#059669] text-white text-xs h-9"
        >
          В пользу продавца
        </Button>
      </div>
    </div>
  );
}

export default UnifiedChat;
