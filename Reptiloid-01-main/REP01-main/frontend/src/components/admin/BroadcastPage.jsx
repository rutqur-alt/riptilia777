/**
 * BroadcastPage - Admin broadcast notifications management
 */
import { useState, useEffect } from "react";
import { API, useAuth } from "@/App";
import axios from "axios";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Send, RefreshCw, History } from "lucide-react";
import { PageHeader, LoadingSpinner } from "@/components/admin/SharedComponents";

export default function BroadcastPage() {
  const { token } = useAuth();
  const [broadcastTarget, setBroadcastTarget] = useState("all");
  const [broadcastTitle, setBroadcastTitle] = useState("");
  const [broadcastContent, setBroadcastContent] = useState("");
  const [broadcastHistory, setBroadcastHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    fetchBroadcastHistory();
  }, []);

  const fetchBroadcastHistory = async () => {
    try {
      const res = await axios.get(`${API}/admin/broadcasts`, { headers: { Authorization: `Bearer ${token}` } });
      setBroadcastHistory(res.data || []);
    } catch (error) { 
      console.error("Error fetching broadcasts:", error); 
    } finally {
      setLoading(false);
    }
  };

  const sendBroadcast = async () => {
    if (!broadcastContent.trim()) {
      toast.error("Введите текст рассылки");
      return;
    }
    setSending(true);
    try {
      const res = await axios.post(`${API}/admin/broadcast`, {
        target: broadcastTarget,
        title: broadcastTitle,
        content: broadcastContent
      }, { headers: { Authorization: `Bearer ${token}` } });
      toast.success(`Рассылка отправлена ${res.data.recipients_count} получателям`);
      setBroadcastTitle("");
      setBroadcastContent("");
      fetchBroadcastHistory();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка отправки");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="space-y-6" data-testid="broadcast-page">
      <PageHeader 
        title="Рассылка" 
        subtitle="Отправка массовых уведомлений пользователям" 
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Create Broadcast */}
        <div className="bg-[#121212] border border-white/5 rounded-xl p-6">
          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
            <Send className="w-5 h-5 text-[#EC4899]" />
            Новая рассылка
          </h3>
          
          <div className="space-y-4">
            <div>
              <label className="text-[#71717A] text-sm mb-2 block">Получатели</label>
              <div className="flex gap-2">
                {[
                  { v: "all", l: "📢 Всем", desc: "Все пользователи и мерчанты" },
                  { v: "traders", l: "👤 Пользователям", desc: "Только трейдеры" },
                  { v: "merchants", l: "🟠 Мерчантам", desc: "Только мерчанты" }
                ].map(t => (
                  <button 
                    key={t.v} 
                    onClick={() => setBroadcastTarget(t.v)}
                    className={`flex-1 p-3 rounded-xl text-sm text-center transition-all ${
                      broadcastTarget === t.v 
                        ? "bg-[#EC4899] text-white" 
                        : "bg-white/5 text-[#71717A] hover:bg-white/10"
                    }`}
                  >
                    <div className="font-medium">{t.l}</div>
                    <div className="text-xs opacity-70 mt-0.5">{t.desc}</div>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="text-[#71717A] text-sm mb-2 block">Заголовок (опционально)</label>
              <Input 
                value={broadcastTitle} 
                onChange={e => setBroadcastTitle(e.target.value)} 
                placeholder="Заголовок рассылки" 
                className="bg-white/5 border-white/10" 
              />
            </div>

            <div>
              <label className="text-[#71717A] text-sm mb-2 block">Сообщение *</label>
              <Textarea 
                value={broadcastContent} 
                onChange={e => setBroadcastContent(e.target.value)} 
                placeholder="Текст рассылки..." 
                rows={6} 
                className="bg-white/5 border-white/10" 
              />
            </div>

            <Button 
              onClick={sendBroadcast} 
              disabled={sending || !broadcastContent.trim()}
              className="w-full bg-[#EC4899] hover:bg-[#DB2777] disabled:opacity-50"
            >
              {sending ? (
                <><RefreshCw className="w-4 h-4 mr-2 animate-spin" /> Отправка...</>
              ) : (
                <><Send className="w-4 h-4 mr-2" /> Отправить рассылку</>
              )}
            </Button>
          </div>
        </div>

        {/* History */}
        <div className="bg-[#121212] border border-white/5 rounded-xl overflow-hidden">
          <div className="p-4 border-b border-white/5 flex items-center justify-between">
            <h3 className="text-white font-semibold flex items-center gap-2">
              <History className="w-5 h-5 text-[#71717A]" />
              История рассылок
            </h3>
            <Button variant="ghost" size="sm" onClick={fetchBroadcastHistory} className="h-7 w-7 p-0">
              <RefreshCw className="w-4 h-4 text-[#71717A]" />
            </Button>
          </div>
          <div className="p-4 overflow-y-auto max-h-[500px]">
            {loading ? <LoadingSpinner /> : broadcastHistory.length === 0 ? (
              <div className="text-center py-10">
                <Send className="w-12 h-12 text-[#52525B] mx-auto mb-3" />
                <p className="text-[#71717A]">Рассылок пока нет</p>
                <p className="text-[#52525B] text-xs mt-1">Создайте первую рассылку слева</p>
              </div>
            ) : (
              <div className="space-y-3">
                {broadcastHistory.map(b => (
                  <div key={b.id} className="bg-white/5 rounded-xl p-4">
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-0.5 rounded text-xs ${
                          b.target === "all" ? "bg-[#EC4899]/20 text-[#EC4899]" :
                          b.target === "merchants" ? "bg-[#F97316]/20 text-[#F97316]" :
                          "bg-white/10 text-white"
                        }`}>
                          {b.target === "all" ? "📢 Всем" : b.target === "merchants" ? "🟠 Мерчантам" : "👤 Пользователям"}
                        </span>
                        <span className="text-[#71717A] text-xs">{b.recipients_count} получателей</span>
                      </div>
                      <span className="text-[#52525B] text-xs">{new Date(b.created_at).toLocaleString("ru-RU")}</span>
                    </div>
                    {b.title && <h4 className="text-white font-medium mb-1">{b.title}</h4>}
                    <p className="text-[#A1A1AA] text-sm whitespace-pre-wrap">{b.content}</p>
                    <div className="mt-2 text-[#52525B] text-xs">От: @{b.sender_name}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
