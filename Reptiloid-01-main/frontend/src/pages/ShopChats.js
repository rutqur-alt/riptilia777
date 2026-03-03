import { useState, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Store, MessageCircle, Send, ArrowLeft } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { toast } from "sonner";

export default function ShopChats() {
  const { token, user } = useAuth();
  const [searchParams] = useSearchParams();
  const [conversations, setConversations] = useState([]);
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [newMessage, setNewMessage] = useState("");
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef(null);

  const preselectedShop = searchParams.get("shop");
  const preselectedSubject = searchParams.get("subject");

  useEffect(() => {
    fetchConversations();
    const interval = setInterval(refreshMessages, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (preselectedShop && conversations.length > 0 && !selectedConversation) {
      const conv = conversations.find(c => c.shop_id === preselectedShop);
      if (conv) {
        fetchConversation(conv.id);
      } else {
        handleNewConversation();
      }
    }
  }, [conversations, preselectedShop]);

  const handleNewConversation = async () => {
    if (!preselectedShop) return;
    const subject = preselectedSubject || "Здравствуйте!";
    try {
      const response = await axios.post(
        `${API}/shop/${preselectedShop}/messages`,
        { message: subject },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (response.data.conversation_id) {
        await fetchConversations();
        await fetchConversation(response.data.conversation_id);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка создания переписки");
    }
  };

  const fetchConversations = async () => {
    try {
      const response = await axios.get(`${API}/my/shop-conversations`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setConversations(response.data);
    } catch (error) {
      console.error("Error fetching conversations:", error);
    } finally {
      setLoading(false);
    }
  };

  const fetchConversation = async (convId) => {
    try {
      const response = await axios.get(`${API}/my/shop-conversations/${convId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSelectedConversation(response.data);
      setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
    } catch (error) {
      toast.error("Ошибка загрузки переписки");
    }
  };

  const refreshMessages = async () => {
    if (selectedConversation) {
      try {
        const response = await axios.get(`${API}/my/shop-conversations/${selectedConversation.id}`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setSelectedConversation(response.data);
      } catch (error) {}
    }
    try {
      const response = await axios.get(`${API}/my/shop-conversations`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setConversations(response.data);
    } catch (error) {}
  };

  const sendReply = async () => {
    if (!newMessage.trim() || !selectedConversation) return;
    setSending(true);
    try {
      await axios.post(
        `${API}/my/shop-conversations/${selectedConversation.id}/reply`,
        { message: newMessage },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setNewMessage("");
      await fetchConversation(selectedConversation.id);
      fetchConversations();
    } catch (error) {
      toast.error("Ошибка отправки");
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-8 h-8 border-2 border-[#10B981] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white font-['Unbounded']">Сообщения магазинов</h1>
        <p className="text-[#71717A]">Переписка с магазинами маркетплейса</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 h-[600px]">
        <div className="bg-[#121212] border border-white/5 rounded-xl overflow-hidden">
          <div className="p-4 border-b border-white/5">
            <h3 className="text-white font-semibold">Переписки</h3>
            <p className="text-xs text-[#71717A]">{conversations.length} магазинов</p>
          </div>
          <div className="overflow-y-auto max-h-[520px]">
            {conversations.length === 0 ? (
              <div className="p-6 text-center">
                <MessageCircle className="w-8 h-8 text-[#52525B] mx-auto mb-2" />
                <p className="text-[#71717A] text-sm">Нет переписок</p>
                <p className="text-[#52525B] text-xs mt-1">Напишите в любой магазин на маркетплейсе</p>
              </div>
            ) : conversations.map(conv => (
              <button
                key={conv.id}
                onClick={() => fetchConversation(conv.id)}
                className={`w-full p-4 text-left border-b border-white/5 hover:bg-white/5 transition-colors ${
                  selectedConversation?.id === conv.id ? 'bg-[#10B981]/10' : ''
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <Store className="w-4 h-4 text-[#10B981]" />
                    <span className="text-white font-medium text-sm">{conv.shop_name}</span>
                  </div>
                  {conv.unread_customer > 0 && (
                    <span className="bg-[#10B981] text-white text-xs px-2 py-0.5 rounded-full">
                      {conv.unread_customer}
                    </span>
                  )}
                </div>
                <p className="text-[#71717A] text-xs truncate pl-6">
                  {conv.messages?.[conv.messages.length - 1]?.message || "Нет сообщений"}
                </p>
                <p className="text-[#52525B] text-[10px] pl-6 mt-1">
                  {conv.updated_at ? new Date(conv.updated_at).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : ""}
                </p>
              </button>
            ))}
          </div>
        </div>

        <div className="lg:col-span-2 bg-[#121212] border border-white/5 rounded-xl overflow-hidden flex flex-col">
          {!selectedConversation ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <MessageCircle className="w-12 h-12 text-[#52525B] mx-auto mb-3" />
                <p className="text-[#71717A]">Выберите переписку</p>
                <p className="text-[#52525B] text-sm mt-1">или напишите магазину через маркетплейс</p>
              </div>
            </div>
          ) : (
            <>
              <div className="p-4 border-b border-white/5 flex items-center gap-3">
                <button onClick={() => setSelectedConversation(null)} className="lg:hidden text-[#71717A] hover:text-white">
                  <ArrowLeft className="w-5 h-5" />
                </button>
                <Store className="w-5 h-5 text-[#10B981]" />
                <div>
                  <h3 className="text-white font-semibold">{selectedConversation.shop_name}</h3>
                  <p className="text-xs text-[#71717A]">Магазин маркетплейса</p>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {selectedConversation.messages?.map((msg, idx) => (
                  <div
                    key={idx}
                    className={`flex ${msg.sender_type === 'customer' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div className={`max-w-[70%] rounded-xl px-4 py-2 ${
                      msg.sender_type === 'customer'
                        ? 'bg-[#10B981] text-white'
                        : 'bg-[#1A1A1A] text-white'
                    }`}>
                      <p className="text-xs opacity-70 mb-1">
                        {msg.sender_type === 'customer' ? 'Вы' : msg.sender_name || selectedConversation.shop_name}
                      </p>
                      <p className="text-sm whitespace-pre-wrap">{msg.message}</p>
                      <p className={`text-[10px] mt-1 ${msg.sender_type === 'customer' ? 'text-white/50' : 'text-[#52525B]'}`}>
                        {msg.created_at ? new Date(msg.created_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" }) : ""}
                      </p>
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>

              <div className="p-4 border-t border-white/5">
                <div className="flex gap-2">
                  <Input
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    placeholder="Написать сообщение..."
                    className="flex-1 bg-[#0A0A0A] border-white/10 text-white rounded-xl"
                    onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendReply()}
                  />
                  <Button
                    onClick={sendReply}
                    disabled={sending || !newMessage.trim()}
                    className="bg-[#10B981] hover:bg-[#059669] text-white rounded-xl px-4"
                  >
                    <Send className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
