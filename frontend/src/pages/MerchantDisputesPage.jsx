/**
 * MerchantDisputesPage - Dispute management for merchants
 * 
 * Features:
 * - View all disputed trades
 * - Open disputes on paid trades
 * - Read/write messages in dispute chats
 * - Track dispute resolution status
 */

import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { 
  AlertTriangle, MessageCircle, Send, ArrowLeft, RefreshCw,
  Clock, CheckCircle, XCircle, Loader, ChevronRight
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { useAuth, API } from '../App';

export default function MerchantDisputesPage() {
  const { token, user } = useAuth();
  const [disputes, setDisputes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [selectedTrade, setSelectedTrade] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [sendingMessage, setSendingMessage] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const messagesEndRef = useRef(null);
  const pollRef = useRef(null);

  useEffect(() => {
    fetchDisputes();
    const interval = setInterval(fetchDisputes, 15000);
    return () => clearInterval(interval);
  }, [filter]);

  useEffect(() => {
    if (selectedTrade) {
      fetchMessages(selectedTrade.id);
      pollRef.current = setInterval(() => fetchMessages(selectedTrade.id, true), 5000);
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [selectedTrade?.id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const fetchDisputes = async () => {
    try {
      const params = {};
      if (filter === 'active') params.status = 'disputed';
      if (filter === 'resolved') params.status = 'resolved';
      const response = await axios.get(`${API}/merchant/disputes`, {
        params,
        headers: { Authorization: `Bearer ${token}` }
      });
      setDisputes(response.data || []);
    } catch (error) {
      console.error('Error fetching disputes:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchMessages = async (tradeId, silent = false) => {
    if (!silent) setLoadingMessages(true);
    try {
      const response = await axios.get(`${API}/merchant/disputes/${tradeId}/messages`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setMessages(response.data || []);
    } catch (error) {
      console.error('Error fetching messages:', error);
    } finally {
      if (!silent) setLoadingMessages(false);
    }
  };

  const sendMessage = async () => {
    if (!newMessage.trim() || !selectedTrade) return;
    setSendingMessage(true);
    try {
      await axios.post(`${API}/merchant/disputes/${selectedTrade.id}/messages`, 
        { content: newMessage.trim() },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setNewMessage('');
      await fetchMessages(selectedTrade.id, true);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка отправки сообщения');
    } finally {
      setSendingMessage(false);
    }
  };

  const openDispute = async (tradeId) => {
    const reason = window.prompt('Укажите причину спора:');
    if (reason === null) return;
    
    try {
      await axios.post(`${API}/merchant/disputes/${tradeId}/open`, 
        { reason: reason || 'Спор открыт мерчантом' },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success('Спор открыт');
      fetchDisputes();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка открытия спора');
    }
  };

  const getStatusBadge = (status, trade) => {
    // Determine resolution label from dispute_resolution field, not trade status
    const isBuyerWins = trade?.dispute_resolution && ['refund_buyer', 'favor_buyer', 'favor_client'].includes(trade.dispute_resolution);
    const isSellerWins = trade?.dispute_resolution && ['favor_seller', 'favor_trader', 'cancel_dispute', 'release_seller'].includes(trade.dispute_resolution);
    
    const configs = {
      disputed: { bg: 'bg-[#EF4444]/10', text: 'text-[#EF4444]', label: 'Спор открыт', icon: AlertTriangle },
      dispute: { bg: 'bg-[#EF4444]/10', text: 'text-[#EF4444]', label: 'Спор открыт', icon: AlertTriangle },
      completed: { bg: 'bg-[#10B981]/10', text: 'text-[#10B981]', label: isSellerWins ? 'Решён (в пользу продавца)' : 'Решён (в пользу покупателя)', icon: CheckCircle },
      cancelled: { bg: 'bg-[#71717A]/10', text: 'text-[#71717A]', label: isBuyerWins ? 'Решён (в пользу покупателя)' : 'Решён (в пользу продавца)', icon: XCircle },
      refunded: { bg: 'bg-[#71717A]/10', text: 'text-[#71717A]', label: 'Решён (в пользу покупателя)', icon: XCircle },
      paid: { bg: 'bg-[#F59E0B]/10', text: 'text-[#F59E0B]', label: 'Оплачен', icon: Clock },
      pending: { bg: 'bg-[#3B82F6]/10', text: 'text-[#3B82F6]', label: 'Ожидает', icon: Clock }
    };
    const config = configs[status] || configs.pending;
    const Icon = config.icon;
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs ${config.bg} ${config.text}`}>
        {Icon && <Icon className="w-3 h-3" />}
        {config.label}
      </span>
    );
  };

  const getSenderLabel = (msg) => {
    if (msg.sender_type === 'system') return { name: 'Система', color: 'text-[#8B5CF6]' };
    if (msg.sender_type === 'admin') return { name: 'Администратор', color: 'text-[#EF4444]' };
    if (msg.sender_type === 'merchant') return { name: 'Вы (мерчант)', color: 'text-[#F97316]' };
    if (msg.sender_type === 'trader') return { name: msg.sender_nickname || 'Трейдер', color: 'text-[#10B981]' };
    if (msg.sender_type === 'client' || msg.sender_type === 'buyer') return { name: msg.sender_nickname || 'Клиент', color: 'text-[#3B82F6]' };
    return { name: msg.sender_nickname || 'Неизвестный', color: 'text-[#71717A]' };
  };

  // Chat view
  if (selectedTrade) {
    return (
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center gap-4">
          <button
            onClick={() => { setSelectedTrade(null); setMessages([]); }}
            className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center text-[#71717A] hover:text-white"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-[#EF4444]" />
              Спор #{selectedTrade.trade_id?.slice(4, 12) || selectedTrade.id?.slice(4, 12)}
            </h2>
            <div className="flex items-center gap-3 mt-1">
              {getStatusBadge(selectedTrade.status, selectedTrade)}
              <span className="text-xs text-[#52525B]">
                {selectedTrade.amount_usdt} USDT / {selectedTrade.amount_rub} RUB
              </span>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="bg-[#121212] border border-white/5 rounded-xl flex flex-col" style={{ height: 'calc(100vh - 280px)' }}>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {loadingMessages ? (
              <div className="flex items-center justify-center py-10">
                <Loader className="w-6 h-6 text-[#71717A] animate-spin" />
              </div>
            ) : messages.length === 0 ? (
              <div className="text-center py-10 text-[#52525B]">
                Нет сообщений
              </div>
            ) : (
              messages.map(msg => {
                const sender = getSenderLabel(msg);
                const isMerchant = msg.sender_type === 'merchant';
                const isSystem = msg.sender_type === 'system';
                
                if (isSystem) {
                  return (
                    <div key={msg.id} className="text-center">
                      <div className="inline-block px-4 py-2 bg-[#8B5CF6]/10 rounded-xl text-xs text-[#8B5CF6]">
                        {msg.content}
                      </div>
                      <div className="text-[10px] text-[#52525B] mt-1">
                        {new Date(msg.created_at).toLocaleString('ru-RU')}
                      </div>
                    </div>
                  );
                }

                return (
                  <div key={msg.id} className={`flex ${isMerchant ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[70%] rounded-xl px-4 py-2 ${
                      isMerchant 
                        ? 'bg-[#F97316]/10 border border-[#F97316]/20' 
                        : 'bg-white/5 border border-white/5'
                    }`}>
                      <div className={`text-[10px] font-medium mb-1 ${sender.color}`}>
                        {sender.name}
                      </div>
                      <div className="text-sm text-white whitespace-pre-wrap">{msg.content}</div>
                      <div className="text-[10px] text-[#52525B] mt-1 text-right">
                        {new Date(msg.created_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Message Input - only for active disputes */}
          {(selectedTrade.status === 'disputed' || selectedTrade.status === 'dispute') && (
            <div className="border-t border-white/5 p-3">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                  placeholder="Написать сообщение в спор..."
                  className="flex-1 px-4 py-2.5 bg-[#0A0A0A] border border-white/10 rounded-xl text-white text-sm placeholder-[#52525B] focus:outline-none focus:border-[#F97316]/50"
                />
                <button
                  onClick={sendMessage}
                  disabled={!newMessage.trim() || sendingMessage}
                  className="px-4 py-2.5 bg-[#F97316] hover:bg-[#EA580C] disabled:opacity-50 text-white rounded-xl transition-colors"
                >
                  {sendingMessage ? (
                    <Loader className="w-5 h-5 animate-spin" />
                  ) : (
                    <Send className="w-5 h-5" />
                  )}
                </button>
              </div>
            </div>
          )}

          {/* Resolved message */}
          {selectedTrade.status !== 'disputed' && selectedTrade.dispute_resolved_at && (
            <div className="border-t border-white/5 p-3 text-center">
              <span className={`text-xs ${
                ['refund_buyer', 'favor_buyer', 'favor_client'].includes(selectedTrade.dispute_resolution) ? 'text-[#10B981]' : 'text-[#71717A]'
              }`}>
                Спор решён {['refund_buyer', 'favor_buyer', 'favor_client'].includes(selectedTrade.dispute_resolution) ? 'в пользу покупателя' : 'в пользу продавца'}
              </span>
            </div>
          )}
        </div>
      </div>
    );
  }

  // List view
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <AlertTriangle className="w-6 h-6 text-[#EF4444]" />
            Споры
          </h1>
          <p className="text-[#71717A] text-sm mt-1">
            Управление спорами по сделкам
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchDisputes} className="text-[#71717A] border-white/10" title="Обновить данные">
          <RefreshCw className="w-4 h-4 mr-2" />
          Обновить
        </Button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2">
        {[
          { key: 'all', label: 'Все' },
          { key: 'active', label: `Активные (${disputes.filter(d => d.status === 'disputed').length})` },
          { key: 'resolved', label: 'Решённые' }
        ].map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
              filter === f.key 
                ? f.key === 'active' 
                  ? 'bg-[#EF4444]/20 text-[#EF4444]' 
                  : 'bg-white/10 text-white'
                : 'text-[#71717A] hover:text-white hover:bg-white/5'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* API Info */}
      <div className="bg-[#121212] border border-white/5 rounded-xl p-4">
        <div className="text-xs text-[#52525B] mb-2">API ДЛЯ УПРАВЛЕНИЯ СПОРАМИ:</div>
        <div className="space-y-1 text-xs font-mono">
          <div className="text-[#71717A]">
            <span className="text-[#10B981]">POST</span> /v1/invoice/dispute/open — Открыть спор
          </div>
          <div className="text-[#71717A]">
            <span className="text-[#3B82F6]">GET</span> /v1/invoice/disputes — Список споров
          </div>
          <div className="text-[#71717A]">
            <span className="text-[#3B82F6]">GET</span> /v1/invoice/dispute/messages — Чат спора
          </div>
          <div className="text-[#71717A]">
            <span className="text-[#10B981]">POST</span> /v1/invoice/dispute/message — Отправить сообщение
          </div>
        </div>
      </div>

      {/* Disputes List */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader className="w-8 h-8 text-[#71717A] animate-spin" />
        </div>
      ) : disputes.length === 0 ? (
        <div className="text-center py-20">
          <AlertTriangle className="w-16 h-16 text-[#52525B] mx-auto mb-4" />
          <h3 className="text-lg font-medium text-white mb-2">Нет споров</h3>
          <p className="text-[#71717A]">У вас пока нет споров по сделкам</p>
        </div>
      ) : (
        <div className="space-y-3">
          {disputes.map(dispute => (
            <div
              key={dispute.id || dispute.trade_id}
              onClick={() => setSelectedTrade(dispute)}
              className={`bg-[#121212] border rounded-xl p-4 cursor-pointer transition-all hover:bg-white/5 ${
                dispute.status === 'disputed' 
                  ? 'border-[#EF4444]/30 bg-[#EF4444]/5' 
                  : 'border-white/5'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                    dispute.status === 'disputed' 
                      ? 'bg-[#EF4444]/20' 
                      : 'bg-white/5'
                  }`}>
                    <AlertTriangle className={`w-6 h-6 ${
                      dispute.status === 'disputed' ? 'text-[#EF4444]' : 'text-[#71717A]'
                    }`} />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-white">
                        #{(dispute.trade_id || dispute.id)?.slice(4, 12)}
                      </span>
                      {getStatusBadge(dispute.status, dispute)}
                    </div>
                    <div className="text-sm text-[#71717A] mt-1">
                      {dispute.amount_usdt} USDT • {dispute.amount_rub} RUB
                      {dispute.trader_login && ` • @${dispute.trader_login}`}
                    </div>
                    {dispute.dispute_reason && (
                      <div className="text-xs text-[#52525B] mt-1">
                        Причина: {dispute.dispute_reason}
                      </div>
                    )}
                    <div className="text-xs text-[#52525B] mt-0.5">
                      {dispute.disputed_at 
                        ? `Спор: ${new Date(dispute.disputed_at).toLocaleString('ru-RU')}`
                        : new Date(dispute.created_at).toLocaleString('ru-RU')
                      }
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {dispute.status === 'disputed' && (
                    <MessageCircle className="w-5 h-5 text-[#EF4444]" />
                  )}
                  <ChevronRight className="w-5 h-5 text-[#71717A]" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
