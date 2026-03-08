import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { Clock, Loader, Send } from "lucide-react";
import { toast } from "sonner";

import { API, useAuth } from "@/App";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function PendingMerchantChat() {
  const { user, token } = useAuth();
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [conversation, setConversation] = useState(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    fetchConversation();
    const interval = setInterval(fetchMessages, 15000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const fetchConversation = async () => {
    try {
      const response = await axios.get(`${API}/msg/merchant/conversations`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const conv = response.data?.find((c) => c.type === "merchant_application");
      if (conv) {
        setConversation(conv);
        await fetchMessages(conv.id);
      }
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const fetchMessages = async (convId) => {
    const id = convId || conversation?.id;
    if (!id) return;
    try {
      const response = await axios.get(`${API}/msg/merchant/conversations/${id}/messages`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setMessages(response.data || []);
    } catch (error) {
      console.error(error);
    }
  };

  const handleSend = async () => {
    if (!newMessage.trim() || !conversation) return;
    setSending(true);
    try {
      await axios.post(
        `${API}/msg/merchant/conversations/${conversation.id}/messages`,
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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader className="w-8 h-8 text-[#F97316] animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto">
      <div className="bg-[#F97316]/10 border border-[#F97316]/20 rounded-2xl p-4 mb-6">
        <div className="flex items-center gap-3">
          <Clock className="w-6 h-6 text-[#F97316]" />
          <div>
            <div className="text-white font-medium">Заявка на рассмотрении</div>
            <div className="text-sm text-[#A1A1AA]">Администратор рассмотрит вашу заявку в ближайшее время</div>
          </div>
        </div>
      </div>

      <div className="bg-[#121212] border border-white/5 rounded-2xl overflow-hidden" style={{ height: "500px" }}>
        <div className="p-4 border-b border-white/5">
          <h3 className="text-white font-medium">Чат с администратором</h3>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3" style={{ height: "380px" }}>
          {messages.map((msg) => (
            <div key={msg.id} className={`flex ${msg.sender_id === user?.id ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[70%] rounded-2xl px-4 py-2 ${
                  msg.sender_id === user?.id ? "bg-[#F97316] text-white" : "bg-white/5 text-white"
                }`}
              >
                <p className="text-sm">{msg.content}</p>
                <p className="text-[10px] opacity-60 mt-1">
                  {new Date(msg.created_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}
                </p>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        <div className="p-4 border-t border-white/5 flex gap-2">
          <Input
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Написать сообщение..."
            className="bg-[#1A1A1A] border-white/10 text-white h-10 rounded-xl"
          />
          <Button onClick={handleSend} disabled={sending} className="bg-[#F97316] hover:bg-[#EA580C] h-10 px-4 rounded-xl">
            {sending ? <Loader className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </Button>
        </div>
      </div>
    </div>
  );
}
