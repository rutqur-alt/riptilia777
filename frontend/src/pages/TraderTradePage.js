import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { API, useAuth } from "@/App";
import axios from "axios";
import { useWebSocket } from "@/hooks/useWebSocket";
import { 
  ArrowLeft, CheckCircle, XCircle, Clock, Copy, Send, 
  CreditCard, Phone, User, AlertTriangle, MessageCircle,
  Shield, Loader
} from "lucide-react";

// Role colors per specification СООБЩЕНИЯ 2.txt
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

export default function TraderTradePage() {
  const { tradeId } = useParams();
  const navigate = useNavigate();
  const { token, user } = useAuth();
  const [trade, setTrade] = useState(null);
  const [loading, setLoading] = useState(true);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState("");
  const [sendingMessage, setSendingMessage] = useState(false);
  const [timeLeft, setTimeLeft] = useState(0);
  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const isFirstLoad = useRef(true);

  // WebSocket for real-time trade messages
  const handleWsMessage = useCallback((data) => {
    if (data.type === "message") {
      setMessages(prev => {
        const exists = prev.some(m => m.id === data.id);
        if (exists) return prev;
        return [...prev, data];
      });
    } else if (data.type === "status_update") {
      fetchTrade();
    }
  }, []);

  useWebSocket(
    tradeId ? `/ws/trade/${tradeId}` : null,
    handleWsMessage,
    { enabled: !!tradeId }
  );

  // Initialize conversation and fetch trade
  useEffect(() => {
    fetchTrade();
    fetchMessages();
    // Polling as fallback (5s for faster updates if WS fails)
    const interval = setInterval(() => {
      fetchTrade();
      if (tradeId) fetchMessages();
    }, 5000);
    return () => clearInterval(interval);
  }, [tradeId]);



  // Timer for pending trades
  useEffect(() => {
    if (trade?.status === "pending" && trade?.expires_at) {
      const updateTimer = () => {
        const now = new Date();
        const expires = new Date(trade.expires_at);
        const diff = Math.max(0, Math.floor((expires - now) / 1000));
        setTimeLeft(diff);
      };
      updateTimer();
      const timer = setInterval(updateTimer, 1000);
      return () => clearInterval(timer);
    }
  }, [trade]);

  // Auto-scroll only on new messages (not on refetch)
  useEffect(() => {
    if (isFirstLoad.current && messages.length > 0) {
      messagesEndRef.current?.scrollIntoView({ behavior: "auto" });
      isFirstLoad.current = false;
    } else if (messages.length > 0) {
      const container = messagesContainerRef.current;
      if (container) {
        const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
        if (isNearBottom) {
          messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
        }
      }
    }
  }, [messages]);


  const fetchTrade = async () => {
    try {
      const response = await axios.get(`${API}/trades/${tradeId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTrade(response.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const fetchMessages = async () => {
    if (!tradeId) return;
    try {
      const response = await axios.get(`${API}/trades/${tradeId}/messages`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setMessages(response.data || []);
    } catch (error) {
      console.error("Failed to fetch messages:", error);
    }
  };

  const handleSendMessage = async () => {
    if (!newMessage.trim() || !tradeId) return;
    
    setSendingMessage(true);
    try {
      await axios.post(`${API}/trades/${tradeId}/messages`, {
        content: newMessage
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setNewMessage("");
      setTimeout(fetchMessages, 500);
    } catch (error) {
      toast.error("Ошибка отправки");
    } finally {
      setSendingMessage(false);
    }
  };

  const handleConfirm = async () => {
    try {
      await axios.post(`${API}/trades/${tradeId}/confirm`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Сделка подтверждена! USDT переведены.");
      fetchTrade();
      fetchMessages();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка подтверждения");
    }
  };

  const handleCancel = async () => {
    if (!confirm("Отменить сделку? USDT вернутся на ваш баланс.")) return;
    
    try {
      await axios.post(`${API}/trades/${tradeId}/cancel`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Сделка отменена");
      fetchTrade();
      fetchMessages();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка отмены");
    }
  };

  const handleDispute = async () => {
    const reason = prompt("Укажите причину спора:");
    if (!reason) return;
    
    try {
      // Use new unified messaging API for dispute
      await axios.post(`${API}/trades/${tradeId}/dispute`, { reason }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Спор открыт. Модератор рассмотрит сделку.");
      fetchTrade();
      fetchMessages();
    } catch (error) {
      // Fallback to old API
      try {
        await axios.post(`${API}/trades/${tradeId}/dispute`, {}, {
          headers: { Authorization: `Bearer ${token}` },
          params: { reason }
        });
        toast.success("Спор открыт. Администратор рассмотрит сделку.");
        fetchTrade();
      } catch (e) {
        toast.error(e.response?.data?.detail || "Ошибка открытия спора");
      }
    }
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success("Скопировано");
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-[#7C3AED] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!trade) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
        <div className="text-center">
          <AlertTriangle className="w-16 h-16 text-[#F59E0B] mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-white mb-2">Сделка не найдена</h1>
          <Link to="/trader/sales">
            <Button className="mt-4 bg-[#7C3AED] hover:bg-[#6D28D9]" title="Вернуться к списку сделок">
              К списку сделок
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  const statusConfig = {
    pending: { color: "#F59E0B", bg: "#F59E0B", label: "Ожидает оплаты", icon: Clock },
    paid: { color: "#3B82F6", bg: "#3B82F6", label: "Клиент оплатил", icon: CreditCard },
    disputed: { color: "#EF4444", bg: "#EF4444", label: "Спор", icon: AlertTriangle },
    completed: { color: "#10B981", bg: "#10B981", label: "Завершена", icon: CheckCircle },
    cancelled: { color: "#EF4444", bg: "#EF4444", label: "Отменена", icon: XCircle }
  };

  const status = statusConfig[trade.status] || statusConfig.pending;
  const StatusIcon = status.icon;
  const isDispute = trade.status === "disputed";

  return (
    <div className="min-h-screen bg-[#0A0A0A]">
      {/* Header */}
      <header className="bg-[#121212] border-b border-white/5 px-4 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button onClick={() => navigate("/trader/sales")} className="p-2 rounded-lg hover:bg-white/5">
              <ArrowLeft className="w-5 h-5 text-white" />
            </button>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-bold text-white">Сделка #{trade.id}</h1>
                <button onClick={() => { navigator.clipboard.writeText(trade.id); toast.success("Номер сделки скопирован"); }} className="p-1 rounded hover:bg-white/10 transition-colors" title="Скопировать номер сделки">
                  <Copy className="w-4 h-4 text-[#71717A] hover:text-white" />
                </button>
              </div>
              <div className="flex items-center gap-2 mt-1">
                <span className={`px-2 py-0.5 rounded text-xs font-medium`} style={{ backgroundColor: `${status.bg}20`, color: status.color }}>
                  {status.label}
                </span>
                {isDispute && (
                  <span className="bg-[#EF4444]/10 text-[#EF4444] px-2 py-0.5 rounded text-xs flex items-center gap-1">
                    <Shield className="w-3 h-3" /> Удаление сообщений запрещено
                  </span>
                )}
                {(trade.status === "pending" || trade.status === "paid") && (
                  <span className="text-[#F59E0B] font-['JetBrains_Mono'] text-sm">
                    ⏱️ {formatTime(timeLeft)}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto p-4 grid lg:grid-cols-2 gap-6">
        {/* Left: Trade Details */}
        <div className="space-y-6">
          {/* Amount Card */}
          <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
            <div className="flex items-center justify-between mb-6">
              <div>
                <div className="text-[#71717A] text-sm">Продаёте</div>
                <div className="text-3xl font-bold text-white font-['JetBrains_Mono']">
                  {trade.amount_usdt} USDT
                </div>
              </div>
              <div className="text-right">
                <div className="text-[#71717A] text-sm">Получите</div>
                <div className="text-2xl font-bold text-[#10B981] font-['JetBrains_Mono']">
                  {Math.round(trade.amount_rub || 0).toLocaleString()} ₽
                </div>
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4 pt-4 border-t border-white/5">
              <div>
                <div className="text-[#52525B] text-xs">Курс</div>
                <div className="text-white">{trade.price_rub} ₽/USDT</div>
              </div>
              <div>
                <div className="text-[#52525B] text-xs">Комиссия</div>
                <div className="text-[#F59E0B]">{trade.trader_commission || 0} USDT</div>
              </div>
            </div>
          </div>

          {/* Выбранный клиентом реквизит */}
          {trade.requisites && trade.requisites.length > 0 && (
            <div className="bg-[#121212] border border-white/5 rounded-2xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <CreditCard className="w-4 h-4 text-[#7C3AED]" />
                <span className="text-white text-sm font-medium">Реквизит для клиента</span>
              </div>
              {trade.requisites.slice(0, 1).map((req, idx) => (
                <div key={idx} className="flex items-center justify-between bg-[#0A0A0A] rounded-xl p-3">
                  <div className="flex items-center gap-3">
                    <span className="text-lg">
                      {req.type === "card" && "💳"}
                      {req.type === "sbp" && "⚡"}
                      {req.type === "qr" && "📱"}
                      {req.type === "sim" && "📞"}
                    </span>
                    <div>
                      <div className="text-white font-['JetBrains_Mono'] text-sm">
                        {req.type === "card" && req.data?.card_number}
                        {req.type === "sbp" && req.data?.phone}
                        {req.type === "sim" && req.data?.phone}
                      </div>
                      <div className="text-[#52525B] text-xs">
                        {req.type === "card" && req.data?.bank_name}
                        {req.type === "sbp" && `СБП ${req.data?.bank_name || ""}`}
                        {req.type === "sim" && req.data?.operator}
                      </div>
                    </div>
                  </div>
                  <button 
                    onClick={() => copyToClipboard(req.data?.card_number || req.data?.phone || "")} 
                    className="text-[#7C3AED] text-xs hover:underline"
                   title="Скопировать в буфер обмена">
                    Копировать
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Actions */}
          {(trade.status === "pending" || trade.status === "paid" || trade.status === "disputed") && (
            <div className="bg-[#121212] border border-white/5 rounded-2xl p-4">
              {trade.status === "pending" && (
                <div className="bg-[#F59E0B]/10 rounded-xl p-3 mb-3">
                  <div className="flex items-center gap-2 text-[#F59E0B] text-sm">
                    <Clock className="w-4 h-4" />
                    <span>Ожидание оплаты. Отмена через 30 мин.</span>
                  </div>
                </div>
              )}
              
              {trade.status === "paid" && (
                <div className="bg-[#3B82F6]/10 rounded-xl p-3 mb-3">
                  <div className="flex items-center gap-2 text-[#3B82F6] text-sm">
                    <CreditCard className="w-4 h-4" />
                    <span>Клиент оплатил! Проверьте {Math.round(trade.amount_rub || 0).toLocaleString()} ₽</span>
                  </div>
                </div>
              )}
              
              {trade.status === "disputed" && (
                <div className="bg-[#EF4444]/10 rounded-xl p-3 mb-3">
                  <div className="flex items-center gap-2 text-[#EF4444] text-sm">
                    <AlertTriangle className="w-4 h-4" />
                    <span>Модератор рассмотрит сделку.</span>
                  </div>
                  {trade.disputed_by_role && (
                    <div className="text-[#EF4444] text-sm font-bold mt-2">
                      Спор открыт {trade.disputed_by_role}
                    </div>
                  )}
                </div>
              )}
              
              <div className="flex gap-2">
                {(trade.status === "paid" || trade.status === "disputed") && (
                  <Button 
                    onClick={handleConfirm}
                    className="flex-1 bg-[#10B981] hover:bg-[#059669] h-10 rounded-xl"
                    data-testid="confirm-trade-btn"
                   title="Подтвердить получение оплаты">
                    <CheckCircle className="w-4 h-4 mr-2" />
                    Подтвердить
                  </Button>
                )}
                {trade.status === "paid" && (
                  <Button 
                    onClick={handleDispute}
                    variant="outline"
                    className="border-[#F59E0B]/50 text-[#F59E0B] hover:bg-[#F59E0B]/10 h-10 rounded-xl"
                    data-testid="dispute-trade-btn"
                  >
                    <AlertTriangle className="w-4 h-4 mr-2" />
                    Спор
                  </Button>
                )}
                {trade.status === "pending" && (
                  <Button 
                    onClick={handleCancel}
                    variant="outline"
                    className="flex-1 border-[#EF4444]/50 text-[#EF4444] hover:bg-[#EF4444]/10 h-10 rounded-xl"
                    data-testid="cancel-trade-btn"
                   title="Отменить сделку">
                    <XCircle className="w-4 h-4 mr-2" />
                    Отменить
                  </Button>
                )}
              </div>
              
              {(trade.status === "paid" || trade.status === "disputed") && (
                <p className="text-xs text-[#52525B] text-center mt-3">
                  Подтверждайте только после проверки поступления денег!
                </p>
              )}
            </div>
          )}

          {trade.status === "completed" && (
            <div className="bg-[#10B981]/10 border border-[#10B981]/20 rounded-2xl p-6 text-center">
              <CheckCircle className="w-12 h-12 text-[#10B981] mx-auto mb-3" />
              <h3 className="text-[#10B981] font-semibold text-lg">Сделка завершена!</h3>
              <p className="text-[#71717A] mt-2">USDT переведены мерчанту.</p>
            </div>
          )}

          {trade.status === "cancelled" && (
            <div className="bg-[#EF4444]/10 border border-[#EF4444]/20 rounded-2xl p-6 text-center">
              <XCircle className="w-12 h-12 text-[#EF4444] mx-auto mb-3" />
              <h3 className="text-[#EF4444] font-semibold text-lg">Сделка отменена</h3>
              <p className="text-[#71717A] mt-2">USDT возвращены на ваш баланс.</p>
            </div>
          )}
        </div>

        {/* Right: Chat - Using Unified Messaging */}
        <div className={`bg-[#121212] border rounded-2xl flex flex-col h-[600px] ${isDispute ? 'border-[#EF4444]/30' : 'border-white/5'}`}>
          <div className={`p-4 border-b ${isDispute ? 'border-[#EF4444]/20 bg-[#EF4444]/5' : 'border-white/5'}`}>
            <h3 className="text-white font-semibold flex items-center gap-2">
              <MessageCircle className={`w-5 h-5 ${isDispute ? 'text-[#EF4444]' : 'text-[#7C3AED]'}`} />
              Чат сделки
              {isDispute && (
                <span className="text-[#EF4444] text-xs bg-[#EF4444]/10 px-2 py-0.5 rounded">СПОР</span>
              )}
            </h3>
            {isDispute && (
              <p className="text-[#EF4444] text-xs mt-1">⚠️ Модератор присоединился к чату. Удаление сообщений запрещено.</p>
            )}
          </div>
          
          {/* Messages with role colors */}
          <div ref={messagesContainerRef} className="flex-1 overflow-y-auto p-4 space-y-3">
            {messages.length === 0 ? (
              <div className="text-center py-8">
                <MessageCircle className="w-10 h-10 text-[#52525B] mx-auto mb-3" />
                <p className="text-[#71717A] text-sm">Нет сообщений</p>
                <p className="text-[#52525B] text-xs mt-1">Напишите клиенту если нужно уточнить детали</p>
              </div>
            ) : (
              messages.map((msg) => {
                const isOwn = msg.sender_id === user?.id;
                const isSystem = msg.is_system || msg.sender_role === "system";
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
                  <div key={msg.id} className={`flex ${isOwn ? "justify-end" : "justify-start"}`}>
                    <div className="max-w-[80%]">
                      {!isOwn && (
                        <div className="text-[10px] text-[#71717A] mb-0.5 ml-2">
                          {roleInfo.icon} {msg.sender_name} • {roleInfo.name}
                        </div>
                      )}
                      <div className={`rounded-2xl px-4 py-2 ${
                        isOwn 
                          ? "bg-[#7C3AED] text-white" 
                          : roleInfo.color
                      }`}>
                        <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                        <div className={`text-[10px] mt-1 ${isOwn ? "text-white/60" : "opacity-60"}`}>
                          {formatDate(msg.created_at)}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
            <div ref={messagesEndRef} />
          </div>
          
          {/* Input - disabled if trade is completed/cancelled */}
          {trade.status !== "completed" && trade.status !== "cancelled" && (
            <div className="p-4 border-t border-white/5">
              <div className="flex gap-2">
                <Input
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  onKeyPress={(e) => e.key === "Enter" && handleSendMessage()}
                  placeholder={isDispute ? "Сообщение модератору и другим участникам..." : "Написать сообщение..."}
                  className="flex-1 bg-[#0A0A0A] border-white/10 text-white h-10 rounded-xl"
                  data-testid="trade-message-input"
                />
                <Button 
                  onClick={handleSendMessage}
                  disabled={!newMessage.trim() || sendingMessage || !tradeId}
                  className="bg-[#7C3AED] hover:bg-[#6D28D9] h-10 px-4 rounded-xl"
                  data-testid="trade-send-message-btn"
                title="Отправить сообщение"
                >
                  {sendingMessage ? <Loader className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                </Button>
              </div>
            </div>
          )}

          {/* Role legend */}
          <div className="px-4 py-2 border-t border-white/5 bg-[#0A0A0A]">
            <div className="flex flex-wrap gap-3 text-[10px] text-[#71717A]">
              <span className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-white border border-gray-400" /> Пользователь</span>
              <span className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-[#F97316]" /> Мерчант</span>
              <span className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-[#F59E0B]" /> Модератор</span>
              <span className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-[#EF4444]" /> Админ</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
