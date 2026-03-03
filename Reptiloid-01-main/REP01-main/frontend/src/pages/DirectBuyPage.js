import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { useAuth, API } from "@/App";
import axios from "axios";
import { 
  ArrowLeft, Wallet, Shield, Clock, CheckCircle, AlertTriangle, 
  Send, Copy, Star, Info, User, MessageCircle, XCircle
} from "lucide-react";

export default function DirectBuyPage() {
  const { offerId } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated, user, token } = useAuth();
  const messagesEndRef = useRef(null);
  
  const [step, setStep] = useState("amount"); // amount, requisite, paying, chat
  const [offer, setOffer] = useState(null);
  const [loading, setLoading] = useState(true);
  const [amount, setAmount] = useState("");
  const [selectedRequisite, setSelectedRequisite] = useState(null);
  const [trade, setTrade] = useState(null);
  const [creating, setCreating] = useState(false);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState("");
  const [timeLeft, setTimeLeft] = useState(1800);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate("/auth");
      return;
    }
    fetchOffer();
  }, [offerId, isAuthenticated]);

  useEffect(() => {
    if (trade && (trade.status === "pending" || trade.status === "paid")) {
      const interval = setInterval(fetchMessages, 3000);
      return () => clearInterval(interval);
    }
  }, [trade]);

  useEffect(() => {
    if (trade && trade.status === "pending") {
      const timer = setInterval(() => {
        setTimeLeft(prev => Math.max(0, prev - 1));
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [trade]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const fetchOffer = async () => {
    try {
      const response = await axios.get(`${API}/public/offers`);
      const found = response.data.find(o => o.id === offerId);
      if (found) {
        // Can't buy from yourself
        if (found.trader_id === user?.id) {
          toast.error("Нельзя покупать у самого себя");
          navigate("/");
          return;
        }
        setOffer(found);
      } else {
        toast.error("Объявление не найдено");
        navigate("/");
      }
    } catch (error) {
      toast.error("Ошибка загрузки");
      navigate("/");
    } finally {
      setLoading(false);
    }
  };

  const fetchMessages = async () => {
    if (!trade) return;
    try {
      const response = await axios.get(`${API}/trades/${trade.id}/messages`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setMessages(response.data);
    } catch (error) {
      console.error("Failed to fetch messages");
    }
  };

  const handleCreateTrade = async () => {
    if (!amount || parseFloat(amount) <= 0) {
      toast.error("Укажите сумму");
      return;
    }
    if (!selectedRequisite) {
      toast.error("Выберите способ оплаты");
      return;
    }

    const amountUsdt = parseFloat(amount);
    if (amountUsdt < (offer.min_amount || 1)) {
      toast.error(`Минимальная сумма: ${offer.min_amount || 1} USDT`);
      return;
    }
    if (amountUsdt > (offer.max_amount || offer.available_usdt)) {
      toast.error(`Максимальная сумма: ${offer.max_amount || offer.available_usdt} USDT`);
      return;
    }
    if (amountUsdt > offer.available_usdt) {
      toast.error(`Доступно только ${offer.available_usdt} USDT`);
      return;
    }

    setCreating(true);
    try {
      const response = await axios.post(`${API}/trades/direct`, {
        offer_id: offer.id,
        amount_usdt: amountUsdt,
        requisite_id: selectedRequisite.id
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setTrade(response.data);
      setStep("paying");
      fetchMessages();
      toast.success("Сделка создана!");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка создания сделки");
    } finally {
      setCreating(false);
    }
  };

  const handleMarkPaid = async () => {
    if (!trade) return;
    try {
      await axios.post(`${API}/trades/${trade.id}/mark-paid`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTrade({ ...trade, status: "paid" });
      toast.success("Отмечено как оплачено");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка");
    }
  };

  const handleOpenDispute = async () => {
    if (!trade) return;
    const reason = prompt("Укажите причину спора:");
    if (!reason) return;
    
    try {
      await axios.post(`${API}/trades/${trade.id}/dispute`, { reason }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTrade({ ...trade, status: "disputed" });
      toast.success("Спор открыт");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка");
    }
  };

  const handleCancelTrade = async () => {
    if (!trade) return;
    if (!confirm("Отменить сделку?")) return;
    
    try {
      await axios.post(`${API}/trades/${trade.id}/cancel`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTrade({ ...trade, status: "cancelled" });
      toast.success("Сделка отменена");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка");
    }
  };

  const handleSendMessage = async () => {
    if (!newMessage.trim() || !trade) return;
    
    try {
      await axios.post(`${API}/trades/${trade.id}/messages`, {
        content: newMessage
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setNewMessage("");
      fetchMessages();
    } catch (error) {
      toast.error("Ошибка отправки");
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success("Скопировано");
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-[#7C3AED] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!offer) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center px-4">
        <div className="text-center">
          <AlertTriangle className="w-16 h-16 text-[#F59E0B] mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-white">Объявление не найдено</h1>
        </div>
      </div>
    );
  }

  // Step 1: Enter amount and select requisite
  if (step === "amount") {
    const amountRub = amount ? (parseFloat(amount) * offer.price_rub).toFixed(0) : 0;
    
    return (
      <div className="min-h-screen bg-[#0A0A0A] px-4 py-8">
        <div className="max-w-lg mx-auto">
          {/* Header */}
          <div className="flex items-center gap-4 mb-8">
            <Link to="/" className="p-2 rounded-xl bg-white/5 hover:bg-white/10">
              <ArrowLeft className="w-5 h-5 text-white" />
            </Link>
            <div>
              <h1 className="text-xl font-bold text-white font-['Unbounded']">Купить USDT</h1>
              <p className="text-sm text-[#71717A]">Прямая покупка у трейдера</p>
            </div>
          </div>

          {/* Offer Info */}
          <div className="bg-[#121212] border border-white/5 rounded-2xl p-6 mb-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-full bg-gradient-to-br from-[#7C3AED] to-[#A855F7] flex items-center justify-center">
                <User className="w-6 h-6 text-white" />
              </div>
              <div>
                <div className="text-white font-semibold">{offer.trader_login}</div>
                <div className="flex items-center gap-2 text-sm">
                  <Star className="w-3 h-3 text-[#F59E0B] fill-[#F59E0B]" />
                  <span className="text-[#F59E0B]">{offer.success_rate || 100}%</span>
                  <span className="text-[#52525B]">•</span>
                  <span className="text-[#71717A]">{offer.trades_count || 0} сделок</span>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="bg-[#0A0A0A] rounded-xl p-3">
                <div className="text-[#71717A]">Курс</div>
                <div className="text-white font-bold font-['JetBrains_Mono']">{offer.price_rub} ₽/USDT</div>
              </div>
              <div className="bg-[#0A0A0A] rounded-xl p-3">
                <div className="text-[#71717A]">Доступно</div>
                <div className="text-white font-bold font-['JetBrains_Mono']">{offer.available_usdt} USDT</div>
              </div>
            </div>

            <div className="mt-3 text-xs text-[#71717A]">
              Лимит: {offer.min_amount || 1} - {offer.max_amount || offer.available_usdt} USDT
            </div>

            {offer.conditions && (
              <div className="mt-4 p-3 bg-[#F59E0B]/10 rounded-xl">
                <div className="flex items-start gap-2">
                  <Info className="w-4 h-4 text-[#F59E0B] flex-shrink-0 mt-0.5" />
                  <div className="text-sm text-[#F59E0B]">{offer.conditions}</div>
                </div>
              </div>
            )}
          </div>

          {/* Amount Input */}
          <div className="bg-[#121212] border border-white/5 rounded-2xl p-6 mb-6">
            <label className="text-[#A1A1AA] text-sm mb-2 block">Сумма покупки (USDT)</label>
            <Input
              type="number"
              placeholder={`${offer.min_amount || 1} - ${offer.max_amount || offer.available_usdt}`}
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="bg-[#0A0A0A] border-white/10 text-white h-14 rounded-xl text-lg font-['JetBrains_Mono']"
              data-testid="amount-input"
            />
            {amount && (
              <div className="mt-3 text-sm text-[#71717A]">
                К оплате: <span className="text-white font-semibold">{parseInt(amountRub).toLocaleString()} ₽</span>
              </div>
            )}
          </div>

          {/* Requisite Selection */}
          <div className="bg-[#121212] border border-white/5 rounded-2xl p-4 mb-6">
            <label className="text-[#A1A1AA] text-sm mb-2 block">Способ оплаты ({(offer.requisites || []).length})</label>
            <div className="space-y-1.5 max-h-[240px] overflow-y-auto pr-1">
              {(offer.requisites || []).map((req) => (
                <button
                  key={req.id}
                  onClick={() => setSelectedRequisite(req)}
                  className={`w-full flex items-center gap-2 p-2.5 rounded-lg transition-all ${
                    selectedRequisite?.id === req.id
                      ? "bg-[#7C3AED]/20 border border-[#7C3AED]"
                      : "bg-[#0A0A0A] border border-transparent hover:border-white/10"
                  }`}
                >
                  <span className="text-base flex-shrink-0">
                    {req.type === "card" && "💳"}
                    {req.type === "sbp" && "⚡"}
                    {req.type === "qr" && "📱"}
                    {req.type === "sim" && "📞"}
                  </span>
                  <div className="text-left flex-1 min-w-0">
                    <div className="text-white text-sm font-medium truncate">
                      {req.type === "card" && `${req.data?.bank_name} •••• ${req.data?.card_number?.slice(-4) || ""}`}
                      {req.type === "sbp" && `СБП ${req.data?.bank_name}`}
                      {req.type === "qr" && `QR ${req.data?.bank_name}`}
                      {req.type === "sim" && req.data?.operator}
                    </div>
                  </div>
                  {selectedRequisite?.id === req.id && (
                    <CheckCircle className="w-4 h-4 text-[#7C3AED] flex-shrink-0" />
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Create Button */}
          <Button
            onClick={handleCreateTrade}
            disabled={!amount || !selectedRequisite || creating}
            className="w-full h-14 bg-[#10B981] hover:bg-[#059669] rounded-xl font-semibold text-lg disabled:opacity-50"
            data-testid="create-trade-btn"
          >
            {creating ? <div className="spinner" /> : "Создать сделку"}
          </Button>
        </div>
      </div>
    );
  }

  // Step 2: Paying - show requisites and chat
  if (step === "paying" && trade) {
    const requisite = trade.requisite || selectedRequisite;
    const amountRub = (trade.amount_usdt * offer.price_rub).toFixed(0);
    
    return (
      <div className="min-h-screen bg-[#0A0A0A] px-4 py-8">
        <div className="max-w-4xl mx-auto">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-xl font-bold text-white font-['Unbounded']">Сделка #{trade.id.slice(0, 8)}</h1>
              <p className="text-sm text-[#71717A]">Покупка {trade.amount_usdt} USDT у @{offer.trader_login}</p>
            </div>
            <div className={`px-3 py-1.5 rounded-full text-sm font-medium ${
              trade.status === "pending" ? "bg-[#F59E0B]/10 text-[#F59E0B]" :
              trade.status === "paid" ? "bg-[#3B82F6]/10 text-[#3B82F6]" :
              trade.status === "completed" ? "bg-[#10B981]/10 text-[#10B981]" :
              trade.status === "disputed" ? "bg-[#EF4444]/10 text-[#EF4444]" :
              "bg-[#52525B]/10 text-[#52525B]"
            }`}>
              {trade.status === "pending" && "Ожидает оплаты"}
              {trade.status === "paid" && "Оплачено"}
              {trade.status === "completed" && "Завершено"}
              {trade.status === "disputed" && "Спор"}
              {trade.status === "cancelled" && "Отменено"}
            </div>
          </div>

          <div className="grid lg:grid-cols-3 gap-6">
            {/* Left: Payment Info */}
            <div className="space-y-4">
              {/* Timer */}
              {trade.status === "pending" && (
                <div className="bg-[#F59E0B]/10 border border-[#F59E0B]/20 rounded-2xl p-4 text-center">
                  <Clock className="w-6 h-6 text-[#F59E0B] mx-auto mb-2" />
                  <div className="text-2xl font-bold text-[#F59E0B] font-['JetBrains_Mono']">
                    {formatTime(timeLeft)}
                  </div>
                  <div className="text-sm text-[#F59E0B]/70">Время на оплату</div>
                </div>
              )}

              {/* Amount */}
              <div className="bg-[#121212] border border-white/5 rounded-2xl p-4">
                <div className="text-[#71717A] text-sm mb-1">К оплате</div>
                <div className="text-3xl font-bold text-white font-['JetBrains_Mono']">
                  {parseInt(amountRub).toLocaleString()} ₽
                </div>
                <div className="text-sm text-[#71717A]">{trade.amount_usdt} USDT</div>
              </div>

              {/* Requisite */}
              {requisite && (
                <div className="bg-[#121212] border border-white/5 rounded-2xl p-4">
                  <div className="text-[#71717A] text-sm mb-3">Реквизиты для оплаты</div>
                  
                  {requisite.type === "card" && (
                    <div className="space-y-3">
                      <div>
                        <div className="text-xs text-[#52525B]">Банк</div>
                        <div className="text-white font-medium">{requisite.data?.bank_name}</div>
                      </div>
                      <div>
                        <div className="text-xs text-[#52525B]">Номер карты</div>
                        <div className="flex items-center gap-2">
                          <div className="text-white font-['JetBrains_Mono'] text-lg">{requisite.data?.card_number}</div>
                          <button onClick={() => copyToClipboard(requisite.data?.card_number)} className="p-1 hover:bg-white/10 rounded">
                            <Copy className="w-4 h-4 text-[#7C3AED]" />
                          </button>
                        </div>
                      </div>
                      {requisite.data?.holder_name && (
                        <div>
                          <div className="text-xs text-[#52525B]">Получатель</div>
                          <div className="text-white">{requisite.data.holder_name}</div>
                        </div>
                      )}
                    </div>
                  )}

                  {requisite.type === "sbp" && (
                    <div className="space-y-3">
                      <div>
                        <div className="text-xs text-[#52525B]">Банк</div>
                        <div className="text-white font-medium">{requisite.data?.bank_name}</div>
                      </div>
                      <div>
                        <div className="text-xs text-[#52525B]">Телефон</div>
                        <div className="flex items-center gap-2">
                          <div className="text-white font-['JetBrains_Mono'] text-lg">{requisite.data?.phone}</div>
                          <button onClick={() => copyToClipboard(requisite.data?.phone)} className="p-1 hover:bg-white/10 rounded">
                            <Copy className="w-4 h-4 text-[#7C3AED]" />
                          </button>
                        </div>
                      </div>
                    </div>
                  )}

                  {requisite.type === "qr" && (
                    <div className="space-y-3">
                      <div>
                        <div className="text-xs text-[#52525B]">Банк</div>
                        <div className="text-white font-medium">{requisite.data?.bank_name}</div>
                      </div>
                      {requisite.data?.qr_data && (
                        <div className="flex justify-center">
                          <img 
                            src={requisite.data.qr_data} 
                            alt="QR код" 
                            className="w-40 h-40 rounded-lg bg-white p-2"
                          />
                        </div>
                      )}
                      <div className="text-[#71717A] text-xs text-center">
                        {requisite.data?.description || "Отсканируйте QR-код"}
                      </div>
                    </div>
                  )}

                  {requisite.type === "sim" && (
                    <div className="space-y-3">
                      <div>
                        <div className="text-xs text-[#52525B]">Оператор</div>
                        <div className="text-white font-medium">{requisite.data?.operator}</div>
                      </div>
                      <div>
                        <div className="text-xs text-[#52525B]">Телефон</div>
                        <div className="flex items-center gap-2">
                          <div className="text-white font-['JetBrains_Mono'] text-lg">{requisite.data?.phone}</div>
                          <button onClick={() => copyToClipboard(requisite.data?.phone)} className="p-1 hover:bg-white/10 rounded">
                            <Copy className="w-4 h-4 text-[#7C3AED]" />
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Actions */}
              {trade.status === "pending" && (
                <div className="space-y-2">
                  <Button onClick={handleMarkPaid} className="w-full h-12 bg-[#10B981] hover:bg-[#059669] rounded-xl" data-testid="mark-paid-btn">
                    <CheckCircle className="w-4 h-4 mr-2" />
                    Я оплатил
                  </Button>
                  <Button onClick={handleCancelTrade} variant="outline" className="w-full h-10 border-white/10 text-[#A1A1AA] rounded-xl">
                    Отменить
                  </Button>
                </div>
              )}

              {trade.status === "paid" && (
                <div className="space-y-2">
                  <div className="bg-[#3B82F6]/10 border border-[#3B82F6]/20 rounded-xl p-4 text-center">
                    <div className="text-[#3B82F6]">Ожидайте подтверждения от трейдера</div>
                  </div>
                  <Button onClick={handleOpenDispute} variant="outline" className="w-full h-10 border-[#EF4444]/50 text-[#EF4444] rounded-xl">
                    <AlertTriangle className="w-4 h-4 mr-2" />
                    Открыть спор
                  </Button>
                </div>
              )}

              {trade.status === "completed" && (
                <div className="bg-[#10B981]/10 border border-[#10B981]/20 rounded-xl p-4 text-center">
                  <CheckCircle className="w-8 h-8 text-[#10B981] mx-auto mb-2" />
                  <div className="text-[#10B981] font-semibold">Сделка завершена!</div>
                  <div className="text-sm text-[#10B981]/70">{trade.amount_usdt} USDT зачислены на ваш баланс</div>
                </div>
              )}

              {trade.status === "disputed" && (
                <div className="bg-[#EF4444]/10 border border-[#EF4444]/20 rounded-xl p-4 text-center">
                  <AlertTriangle className="w-8 h-8 text-[#EF4444] mx-auto mb-2" />
                  <div className="text-[#EF4444] font-semibold">Спор открыт</div>
                  <div className="text-sm text-[#EF4444]/70">Администратор рассмотрит ваше обращение</div>
                </div>
              )}

              <Link to="/">
                <Button variant="ghost" className="w-full text-[#71717A]">
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Вернуться на главную
                </Button>
              </Link>
            </div>

            {/* Right: Chat */}
            <div className="lg:col-span-2 bg-[#121212] border border-white/5 rounded-2xl flex flex-col h-[500px]">
              <div className="p-4 border-b border-white/5">
                <div className="flex items-center gap-2">
                  <MessageCircle className="w-5 h-5 text-[#7C3AED]" />
                  <span className="text-white font-medium">Чат с трейдером</span>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {messages.map((msg) => {
                  const isMe = msg.sender_type === "buyer";
                  const isSystem = msg.sender_type === "system" || msg.is_system;
                  const isAdmin = msg.sender_role === "owner" || msg.sender_role === "admin";
                  const isModerator = msg.sender_role?.startsWith("mod_") || msg.sender_role === "support";
                  const isStaff = isAdmin || isModerator;
                  
                  return (
                    <div
                      key={msg.id}
                      className={`flex ${isMe ? "justify-end" : "justify-start"}`}
                    >
                      <div className="max-w-[80%]">
                        {/* Staff label */}
                        {isStaff && !isSystem && (
                          <div className={`text-[10px] mb-1 ml-2 ${
                            isAdmin ? "text-[#EF4444]" : "text-[#3B82F6]"
                          }`}>
                            {isAdmin ? "👑 Администратор" : "🛡️ Модератор"} • {msg.sender_nickname || msg.sender_name}
                          </div>
                        )}
                        <div className={`rounded-2xl px-4 py-2 ${
                          isSystem
                            ? "bg-[#F59E0B]/10 text-[#F59E0B] text-sm"
                            : isMe
                            ? "bg-[#7C3AED] text-white"
                            : isAdmin
                            ? "bg-[#EF4444] text-white"
                            : isModerator
                            ? "bg-[#3B82F6] text-white"
                            : "bg-white/10 text-white"
                        }`}>
                          {msg.content}
                        </div>
                      </div>
                    </div>
                  );
                })}
                <div ref={messagesEndRef} />
              </div>

              {(trade.status === "pending" || trade.status === "paid" || trade.status === "disputed") && (
                <div className="p-4 border-t border-white/5">
                  <div className="flex gap-2">
                    <Input
                      value={newMessage}
                      onChange={(e) => setNewMessage(e.target.value)}
                      onKeyPress={(e) => e.key === "Enter" && handleSendMessage()}
                      placeholder="Написать сообщение..."
                      className="bg-[#0A0A0A] border-white/10 text-white rounded-xl"
                    />
                    <Button onClick={handleSendMessage} className="bg-[#7C3AED] hover:bg-[#6D28D9] rounded-xl px-4">
                      <Send className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return null;
}
