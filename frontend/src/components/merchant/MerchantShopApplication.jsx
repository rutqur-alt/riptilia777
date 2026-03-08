import { useState, useEffect, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import { useAuth, API } from "@/App";
import { Loader, MessageCircle, Send, Store, XCircle } from "lucide-react";

const SHOP_CATEGORIES = {
  accounts: "Аккаунты",
  software: "Софт",
  databases: "Базы данных",
  tools: "Инструменты",
  guides: "Гайды и схемы",
  keys: "Ключи",
  financial: "Финансовое",
  templates: "Шаблоны",
  games: "Игры",
  subscriptions: "Подписки",
  services: "Услуги",
  other: "Другое"
};

export default function MerchantShopApplication({ onSuccess }) {
  const { token, user } = useAuth();
  const [application, setApplication] = useState(null);
  const [conversation, setConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    shop_name: "",
    shop_description: "",
    categories: [],
    telegram: "",
    experience: ""
  });
  const messagesEndRef = useRef(null);

  useEffect(() => {
    checkExistingApplication();
    const interval = setInterval(fetchMessages, 5000);
    return () => clearInterval(interval);
  }, [token]);

  const checkExistingApplication = async () => {
    try {
      const response = await axios.get(`${API}/shop/my-application`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (response.data?.application) {
        setApplication(response.data.application);
        await fetchConversation(response.data.application.id);
      }
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const fetchConversation = async (applicationId) => {
    try {
      const response = await axios.get(`${API}/msg/user/conversations`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const conv = response.data.find(c => c.type === "shop_application" && c.related_id === applicationId);
      if (conv) {
        setConversation(conv);
        await fetchMessages(conv.id);
      }
    } catch (error) {
      console.error(error);
    }
  };

  const fetchMessages = async (convId) => {
    const id = convId || conversation?.id;
    if (!id) return;
    try {
      const response = await axios.get(`${API}/msg/user/conversations/${id}/messages`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setMessages(response.data || []);
      const appRes = await axios.get(`${API}/shop/my-application`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (appRes.data?.has_shop) {
        onSuccess?.();
      }
    } catch (error) {
      console.error(error);
    }
  };

  const createApplication = async () => {
    if (!formData.shop_name || !formData.shop_description || formData.categories.length === 0) {
      toast.error("Заполните все обязательные поля");
      return;
    }
    try {
      await axios.post(`${API}/shop/apply`, formData, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Заявка создана!");
      setShowForm(false);
      await checkExistingApplication();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка создания заявки");
    }
  };

  const handleSend = async () => {
    if (!newMessage.trim() || !conversation) return;
    setSending(true);
    try {
      await axios.post(`${API}/msg/user/conversations/${conversation.id}/messages`,
        { content: newMessage },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setNewMessage("");
      await fetchMessages();
    } catch (error) {
      toast.error("Ошибка отправки");
    } finally {
      setSending(false);
    }
  };

  const toggleCategory = (cat) => {
    setFormData(prev => ({
      ...prev,
      categories: prev.categories.includes(cat)
        ? prev.categories.filter(c => c !== cat)
        : [...prev.categories, cat]
    }));
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (loading) {
    return <div className="flex justify-center py-20"><Loader className="w-8 h-8 animate-spin text-[#71717A]" /></div>;
  }

  if (!application) {
    if (!showForm) {
      return (
        <div className="max-w-2xl mx-auto text-center py-12">
          <div className="w-20 h-20 bg-gradient-to-br from-[#10B981]/20 to-[#34D399]/10 rounded-3xl flex items-center justify-center mx-auto mb-6">
            <Store className="w-10 h-10 text-[#10B981]" />
          </div>
          <h2 className="text-2xl font-bold text-white mb-3">Открыть магазин</h2>
          <p className="text-[#71717A] mb-6 max-w-md mx-auto">
            Чтобы открыть магазин на маркетплейсе, заполните заявку. Администратор рассмотрит её и свяжется с вами.
          </p>
          <button onClick={() => setShowForm(true)} className="bg-[#10B981] hover:bg-[#059669] text-white rounded-xl h-12 px-8 inline-flex items-center gap-2">
            <MessageCircle className="w-5 h-5" />
            Подать заявку
          </button>
        </div>
      );
    }

    return (
      <div className="max-w-2xl mx-auto">
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
          <h2 className="text-xl font-bold text-white mb-6">Заявка на открытие магазина</h2>
          <div className="space-y-4">
            <div>
              <label className="text-sm text-[#A1A1AA] mb-2 block">Название магазина *</label>
              <input value={formData.shop_name} onChange={(e) => setFormData({...formData, shop_name: e.target.value})} placeholder="Мой магазин" className="w-full h-10 px-3 bg-[#0A0A0A] border border-white/10 text-white rounded-xl" />
            </div>
            <div>
              <label className="text-sm text-[#A1A1AA] mb-2 block">Категории товаров *</label>
              <div className="flex flex-wrap gap-2">
                {Object.entries(SHOP_CATEGORIES).map(([key, label]) => (
                  <button key={key} onClick={() => toggleCategory(key)} className={`px-3 py-1.5 rounded-lg text-xs transition-colors ${formData.categories.includes(key) ? "bg-[#10B981] text-white" : "bg-[#1A1A1A] text-[#71717A] hover:bg-white/10"}`}>{label}</button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-sm text-[#A1A1AA] mb-2 block">Описание магазина *</label>
              <textarea value={formData.shop_description} onChange={(e) => setFormData({...formData, shop_description: e.target.value})} placeholder="Расскажите о товарах..." className="w-full px-3 py-2 bg-[#0A0A0A] border border-white/10 text-white rounded-xl min-h-[100px] resize-none" />
            </div>
            <div>
              <label className="text-sm text-[#A1A1AA] mb-2 block">Telegram для связи</label>
              <input value={formData.telegram} onChange={(e) => setFormData({...formData, telegram: e.target.value})} placeholder="@username" className="w-full h-10 px-3 bg-[#0A0A0A] border border-white/10 text-white rounded-xl" />
            </div>
            <div>
              <label className="text-sm text-[#A1A1AA] mb-2 block">Опыт в продажах</label>
              <textarea value={formData.experience} onChange={(e) => setFormData({...formData, experience: e.target.value})} placeholder="Опишите ваш опыт (необязательно)" className="w-full px-3 py-2 bg-[#0A0A0A] border border-white/10 text-white rounded-xl resize-none" />
            </div>
          </div>
          <div className="flex gap-3 mt-6">
            <button onClick={() => setShowForm(false)} className="flex-1 bg-transparent border border-white/10 text-white rounded-xl h-10">Отмена</button>
            <button onClick={createApplication} className="flex-1 bg-[#10B981] hover:bg-[#059669] text-white rounded-xl h-10">Отправить заявку</button>
          </div>
        </div>
      </div>
    );
  }

  if (application.status === "rejected") {
    return (
      <div className="max-w-2xl mx-auto">
        <div className="bg-[#EF4444]/10 border border-[#EF4444]/20 rounded-2xl p-6 text-center">
          <XCircle className="w-12 h-12 text-[#EF4444] mx-auto mb-4" />
          <h3 className="text-xl font-bold text-white mb-2">Заявка отклонена</h3>
          <p className="text-[#A1A1AA] mb-4">{application.admin_comment || "Администратор отклонил вашу заявку"}</p>
          <button onClick={() => { setApplication(null); setShowForm(true); }} className="bg-[#10B981] hover:bg-[#059669] text-white rounded-xl h-10 px-6">Подать новую заявку</button>
        </div>
      </div>
    );
  }

  const statusColors = { pending: "bg-[#F59E0B]/10 text-[#F59E0B] border-[#F59E0B]/30", reviewing: "bg-[#3B82F6]/10 text-[#3B82F6] border-[#3B82F6]/30", approved: "bg-[#10B981]/10 text-[#10B981] border-[#10B981]/30" };
  const statusNames = { pending: "На рассмотрении", reviewing: "В обработке", approved: "Одобрено" };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="bg-[#121212] border border-white/5 rounded-2xl p-4 mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-[#10B981]/10 rounded-xl flex items-center justify-center"><Store className="w-5 h-5 text-[#10B981]" /></div>
          <div>
            <div className="text-white font-medium">{application.shop_name}</div>
            <div className="text-xs text-[#52525B]">Заявка на открытие магазина</div>
          </div>
        </div>
        <span className={`px-3 py-1.5 rounded-lg text-xs border ${statusColors[application.status] || statusColors.pending}`}>{statusNames[application.status] || "На рассмотрении"}</span>
      </div>
      <div className="bg-[#121212] border border-white/5 rounded-2xl overflow-hidden flex flex-col" style={{ height: "500px" }}>
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg) => (
            <div key={msg.id} className={`flex ${msg.sender_id === user?.id ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[75%] p-3 rounded-2xl ${msg.sender_id === user?.id ? "bg-[#10B981] text-white" : msg.sender_role === "system" || msg.is_system ? "bg-[#7C3AED]/20 text-[#A78BFA] border border-[#7C3AED]/30" : "bg-[#1A1A1A] text-white"}`}>
                {msg.sender_role && msg.sender_role !== "system" && msg.sender_id !== user?.id && (<div className="text-xs text-[#10B981] mb-1 font-medium">{msg.sender_nickname || "Модератор"}</div>)}
                <p className="whitespace-pre-wrap">{msg.content}</p>
                <div className={`text-xs mt-1 ${msg.sender_id === user?.id ? "text-white/70" : "text-[#52525B]"}`}>{new Date(msg.created_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}</div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
        <div className="border-t border-white/5 p-4">
          <div className="flex gap-2">
            <input value={newMessage} onChange={(e) => setNewMessage(e.target.value)} onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()} placeholder="Написать сообщение..." className="flex-1 h-10 px-3 bg-[#0A0A0A] border border-white/10 text-white rounded-xl" disabled={sending} />
            <button onClick={handleSend} disabled={sending || !newMessage.trim()} className="bg-[#10B981] hover:bg-[#059669] text-white rounded-xl h-10 w-10 flex items-center justify-center"><Send className="w-4 h-4" /></button>
          </div>
        </div>
      </div>
    </div>
  );
}

