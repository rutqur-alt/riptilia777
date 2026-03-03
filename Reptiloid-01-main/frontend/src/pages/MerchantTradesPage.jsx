/**
 * Merchant Trades Page - P2P trades management for merchants
 * 
 * Shows trades with filters:
 * - Active (активные)
 * - Completed (завершённые)
 * - Disputes (споры) - highlighted in red
 * 
 * Types:
 * - sell: Мерчант продаёт крипту
 * - buy: Мерчант покупает крипту
 */

import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { 
  ArrowUpRight, ArrowDownRight, Clock, CheckCircle, AlertTriangle,
  RefreshCw, ChevronRight, User, Loader, MessageCircle
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { useAuth, API } from '../App';

export default function MerchantTradesPage() {
  const { type = 'sell' } = useParams(); // 'sell' or 'buy'
  const navigate = useNavigate();
  const { token, user } = useAuth();
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all'); // all, active, completed, dispute

  useEffect(() => {
    fetchTrades();
    const interval = setInterval(fetchTrades, 15000);
    return () => clearInterval(interval);
  }, [type, filter]);

  const fetchTrades = async () => {
    try {
      const response = await axios.get(`${API}/merchant/trades`, {
        params: { type, status: filter !== 'all' ? filter : undefined },
        headers: { Authorization: `Bearer ${token}` }
      });
      setTrades(response.data || []);
    } catch (error) {
      console.error('Error fetching trades:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    const configs = {
      pending: { bg: 'bg-[#F59E0B]/10', text: 'text-[#F59E0B]', label: 'Ожидает', icon: Clock },
      active: { bg: 'bg-[#3B82F6]/10', text: 'text-[#3B82F6]', label: 'В процессе', icon: Clock },
      paid: { bg: 'bg-[#10B981]/10', text: 'text-[#10B981]', label: 'Оплачен', icon: CheckCircle },
      completed: { bg: 'bg-[#10B981]/10', text: 'text-[#10B981]', label: 'Завершён', icon: CheckCircle },
      dispute: { bg: 'bg-[#EF4444]/10', text: 'text-[#EF4444]', label: 'Спор', icon: AlertTriangle },
      cancelled: { bg: 'bg-[#71717A]/10', text: 'text-[#71717A]', label: 'Отменён', icon: null }
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

  const handleTradeClick = (trade) => {
    // Navigate to messages with this trade's conversation
    if (trade.conversation_id) {
      navigate('/merchant/messages', { state: { conversationId: trade.conversation_id } });
    } else {
      toast.info('Чат для этой сделки не найден');
    }
  };

  const disputeCount = trades.filter(t => t.status === 'dispute').length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            {type === 'sell' ? (
              <>
                <ArrowUpRight className="w-6 h-6 text-[#10B981]" />
                Продажа
              </>
            ) : (
              <>
                <ArrowDownRight className="w-6 h-6 text-[#F59E0B]" />
                Покупка
              </>
            )}
          </h1>
          <p className="text-[#71717A] text-sm mt-1">
            {type === 'sell' ? 'Сделки, где вы продаёте криптовалюту' : 'Сделки, где вы покупаете криптовалюту'}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchTrades} className="text-[#71717A] border-white/10" title="Обновить данные">
          <RefreshCw className="w-4 h-4 mr-2" />
          Обновить
        </Button>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-4 border-b border-white/5 pb-4">
        <button
          onClick={() => navigate('/merchant/trades/sell')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
            type === 'sell' 
              ? 'bg-[#10B981]/10 text-[#10B981]' 
              : 'text-[#71717A] hover:text-white hover:bg-white/5'
          }`}
        >
          <ArrowUpRight className="w-4 h-4" />
          Продажа
        </button>
        <button
          onClick={() => navigate('/merchant/trades/buy')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
            type === 'buy' 
              ? 'bg-[#F59E0B]/10 text-[#F59E0B]' 
              : 'text-[#71717A] hover:text-white hover:bg-white/5'
          }`}
        >
          <ArrowDownRight className="w-4 h-4" />
          Покупка
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2">
        {[
          { key: 'all', label: 'Все' },
          { key: 'active', label: 'Активные' },
          { key: 'completed', label: 'Завершённые' },
          { key: 'dispute', label: `Споры${disputeCount > 0 ? ` (${disputeCount})` : ''}`, danger: true }
        ].map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
              filter === f.key 
                ? f.danger 
                  ? 'bg-[#EF4444]/20 text-[#EF4444]' 
                  : 'bg-white/10 text-white'
                : f.danger && disputeCount > 0
                ? 'text-[#EF4444] hover:bg-[#EF4444]/10'
                : 'text-[#71717A] hover:text-white hover:bg-white/5'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Trades List */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader className="w-8 h-8 text-[#71717A] animate-spin" />
        </div>
      ) : trades.length === 0 ? (
        <div className="text-center py-20">
          <MessageCircle className="w-16 h-16 text-[#52525B] mx-auto mb-4" />
          <h3 className="text-lg font-medium text-white mb-2">Нет сделок</h3>
          <p className="text-[#71717A]">
            {filter === 'dispute' 
              ? 'Нет открытых споров' 
              : type === 'sell' 
              ? 'У вас пока нет сделок продажи' 
              : 'У вас пока нет сделок покупки'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {trades.map(trade => (
            <div
              key={trade.id}
              onClick={() => handleTradeClick(trade)}
              className={`bg-[#121212] border rounded-xl p-4 cursor-pointer transition-all hover:bg-white/5 ${
                trade.status === 'dispute' 
                  ? 'border-[#EF4444]/30 bg-[#EF4444]/5' 
                  : 'border-white/5'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                    trade.status === 'dispute' 
                      ? 'bg-[#EF4444]/20' 
                      : type === 'sell' 
                      ? 'bg-[#10B981]/10' 
                      : 'bg-[#F59E0B]/10'
                  }`}>
                    {trade.status === 'dispute' ? (
                      <AlertTriangle className="w-6 h-6 text-[#EF4444]" />
                    ) : (
                      <User className="w-6 h-6 text-white/50" />
                    )}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className={`font-medium ${
                        trade.status === 'dispute' ? 'text-[#EF4444]' : 'text-white'
                      }`}>
                        {trade.client_nickname || trade.buyer_nickname || trade.seller_nickname || 'Клиент'}
                      </span>
                      {getStatusBadge(trade.status)}
                    </div>
                    <div className="text-sm text-[#71717A] mt-1">
                      {trade.amount} {trade.currency || 'USDT'} • {trade.fiat_amount?.toFixed(2) || '—'} ₽
                    </div>
                    <div className="text-xs text-[#52525B] mt-0.5">
                      {new Date(trade.created_at).toLocaleString('ru-RU')}
                    </div>
                  </div>
                </div>
                <ChevronRight className={`w-5 h-5 ${
                  trade.status === 'dispute' ? 'text-[#EF4444]' : 'text-[#71717A]'
                }`} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
