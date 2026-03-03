import React, { useState, useEffect, useRef } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { MessageCircle, UserCog, Users, Send, XCircle, PlusCircle, CheckCircle, LogOut, Loader } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { LoadingSpinner, PageHeader } from "@/components/admin/SharedComponents";

export function AdminMessagesToStaff() {
  const { token, user } = useAuth();
  const [activeTab, setActiveTab] = useState("general");
  const [staff, setStaff] = useState([]);
  const [onlineStaff, setOnlineStaff] = useState([]);
  const [selectedStaff, setSelectedStaff] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [groupChats, setGroupChats] = useState([]);
  const [selectedGroupChat, setSelectedGroupChat] = useState(null);
  const [showCreateGroupChat, setShowCreateGroupChat] = useState(false);
  const [newGroupChatName, setNewGroupChatName] = useState("");
  const [selectedParticipants, setSelectedParticipants] = useState([]);
  const messagesEndRef = useRef(null);

  const ROLE_CONFIG = {
    owner: { color: 'bg-[#EF4444]', text: 'text-[#EF4444]', name: 'Владелец', icon: '👑' },
    admin: { color: 'bg-[#EF4444]', text: 'text-[#EF4444]', name: 'Администратор', icon: '' },
    mod_p2p: { color: 'bg-[#F59E0B]', text: 'text-[#F59E0B]', name: 'Модератор P2P', icon: '' },
    mod_market: { color: 'bg-[#F59E0B]', text: 'text-[#F59E0B]', name: 'Гарант', icon: '⚖️' },
    support: { color: 'bg-[#3B82F6]', text: 'text-[#3B82F6]', name: 'Поддержка', icon: '' },
    system: { color: 'bg-[#6B7280]', text: 'text-[#6B7280]', name: 'Система', icon: '' }
  };

  const getRoleInfo = (role) => ROLE_CONFIG[role] || ROLE_CONFIG.support;

  useEffect(() => {
    fetchStaff();
    fetchOnlineStaff();
    if (activeTab === "general") fetchGeneralChat();
    const interval = setInterval(() => {
      fetchOnlineStaff();
      if (activeTab === "general") fetchGeneralChat();
    }, 5000);
    return () => clearInterval(interval);
  }, [activeTab]);

  useEffect(() => {
    if (activeTab === "direct" && selectedStaff) {
      fetchDirectMessages(selectedStaff.id);
      const interval = setInterval(() => fetchDirectMessages(selectedStaff.id), 15000);
      return () => clearInterval(interval);
    }
  }, [selectedStaff, activeTab]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (activeTab === "group_chats") fetchGroupChats();
  }, [activeTab]);

  useEffect(() => {
    if (activeTab === "group_chats" && selectedGroupChat) {
      fetchGroupChatMessages(selectedGroupChat.id);
      const interval = setInterval(() => fetchGroupChatMessages(selectedGroupChat.id), 15000);
      return () => clearInterval(interval);
    }
  }, [selectedGroupChat, activeTab]);

  const fetchStaff = async () => {
    try {
      const response = await axios.get(`${API}/super-admin/staff`, { headers: { Authorization: `Bearer ${token}` } });
      setStaff((response.data || []).filter(s => s.id !== user?.id));
    } catch (error) { console.error("Error fetching staff:", error); }
    finally { setLoading(false); }
  };

  const fetchOnlineStaff = async () => {
    try {
      const response = await axios.get(`${API}/admin/staff-chat/online`, { headers: { Authorization: `Bearer ${token}` } });
      setOnlineStaff(response.data || []);
    } catch (error) { console.error("Error fetching online staff:", error); }
  };

  const fetchGeneralChat = async () => {
    try {
      const response = await axios.get(`${API}/msg/staff/general`, { headers: { Authorization: `Bearer ${token}` } });
      setMessages(response.data?.messages || []);
    } catch (error) {
      try {
        const oldResponse = await axios.get(`${API}/admin/staff-chat`, { headers: { Authorization: `Bearer ${token}` } });
        setMessages(oldResponse.data || []);
      } catch (e) { console.error("Error fetching general chat:", e); }
    } finally { setLoading(false); }
  };

  const fetchDirectMessages = async (staffId) => {
    try {
      const response = await axios.get(`${API}/admin/staff-messages/${staffId}`, { headers: { Authorization: `Bearer ${token}` } });
      setMessages(response.data || []);
    } catch (error) { console.error("Error fetching direct messages:", error); }
  };

  const fetchGroupChats = async () => {
    try {
      const res = await axios.get(`${API}/admin/staff-chats`, { headers: { Authorization: `Bearer ${token}` } });
      setGroupChats(res.data || []);
    } catch (error) { console.error("Error fetching group chats:", error); }
  };

  const fetchGroupChatMessages = async (chatId) => {
    try {
      const res = await axios.get(`${API}/msg/conversations/${chatId}`, { headers: { Authorization: `Bearer ${token}` } });
      setMessages(res.data?.messages || []);
    } catch (error) { console.error("Error fetching messages:", error); }
  };

  const sendGeneralMessage = async () => {
    if (!newMessage.trim()) return;
    setSending(true);
    try {
      await axios.post(`${API}/msg/staff/general`, { content: newMessage }, { headers: { Authorization: `Bearer ${token}` } });
      setNewMessage("");
      fetchGeneralChat();
    } catch (error) {
      try {
        await axios.post(`${API}/admin/staff-chat`, { message: newMessage }, { headers: { Authorization: `Bearer ${token}` } });
        setNewMessage("");
        fetchGeneralChat();
      } catch (e) { toast.error("Не удалось отправить"); }
    } finally { setSending(false); }
  };

  const sendDirectMessage = async () => {
    if (!newMessage.trim() || !selectedStaff) return;
    setSending(true);
    try {
      await axios.post(`${API}/admin/staff-messages/${selectedStaff.id}`, { message: newMessage }, { headers: { Authorization: `Bearer ${token}` } });
      setNewMessage("");
      fetchDirectMessages(selectedStaff.id);
    } catch (error) { toast.error("Ошибка отправки"); }
    finally { setSending(false); }
  };

  const sendGroupChatMessage = async () => {
    if (!newMessage.trim() || !selectedGroupChat) return;
    setSending(true);
    try {
      await axios.post(`${API}/msg/conversations/${selectedGroupChat.id}/send`, { content: newMessage }, { headers: { Authorization: `Bearer ${token}` } });
      setNewMessage("");
      fetchGroupChatMessages(selectedGroupChat.id);
    } catch (error) { toast.error("Ошибка отправки"); }
    finally { setSending(false); }
  };

  const createGroupChat = async () => {
    if (!newGroupChatName.trim()) { toast.error("Введите название чата"); return; }
    try {
      await axios.post(`${API}/admin/staff-chats`, { name: newGroupChatName, participants: selectedParticipants.map(p => p.id) }, { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Чат создан");
      setShowCreateGroupChat(false);
      setNewGroupChatName("");
      setSelectedParticipants([]);
      fetchGroupChats();
    } catch (error) { toast.error(error.response?.data?.detail || "Ошибка создания чата"); }
  };

  const toggleParticipant = (staffMember) => {
    if (selectedParticipants.find(p => p.id === staffMember.id)) {
      setSelectedParticipants(selectedParticipants.filter(p => p.id !== staffMember.id));
    } else {
      setSelectedParticipants([...selectedParticipants, staffMember]);
    }
  };

  const leaveGroupChat = async (chatId) => {
    if (!window.confirm("Вы уверены, что хотите выйти из чата?")) return;
    try {
      await axios.post(`${API}/msg/conversations/${chatId}/leave`, {}, { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Вы вышли из чата");
      setSelectedGroupChat(null);
      fetchGroupChats();
    } catch (error) { toast.error(error.response?.data?.detail || "Ошибка"); }
  };

  const handleSend = () => {
    if (activeTab === "general") sendGeneralMessage();
    else if (activeTab === "direct") sendDirectMessage();
    else if (activeTab === "group_chats") sendGroupChatMessage();
  };

  const isOnline = (staffId) => onlineStaff.some(s => s.id === staffId);

  return (
    <div className="space-y-4" data-testid="staff-messages-page">
      <PageHeader title="Коммуникации персонала" subtitle="Общий чат персонала и личные сообщения" />
      
      {/* Tab Navigation */}
      <div className="flex gap-2 bg-[#121212] p-2 rounded-xl w-fit">
        <button onClick={() => { setActiveTab("general"); setSelectedStaff(null); }} className={`px-4 py-2 rounded-lg text-sm transition-all ${activeTab === "general" ? "bg-[#7C3AED] text-white" : "text-[#71717A] hover:bg-white/5"}`} data-testid="tab-general">
          <MessageCircle className="w-4 h-4 inline mr-2" />Общий чат
        </button>
        <button onClick={() => { setActiveTab("group_chats"); setSelectedGroupChat(null); }} className={`px-4 py-2 rounded-lg text-sm transition-all ${activeTab === "group_chats" ? "bg-[#7C3AED] text-white" : "text-[#71717A] hover:bg-white/5"}`} data-testid="tab-group-chats">
          <UserCog className="w-4 h-4 inline mr-2" />Групповые чаты
          {groupChats.length > 0 && <span className="ml-1 px-1.5 py-0.5 text-[10px] rounded-full bg-white/20">{groupChats.length}</span>}
        </button>
        <button onClick={() => setActiveTab("direct")} className={`px-4 py-2 rounded-lg text-sm transition-all ${activeTab === "direct" ? "bg-[#7C3AED] text-white" : "text-[#71717A] hover:bg-white/5"}`} data-testid="tab-direct">
          <Users className="w-4 h-4 inline mr-2" />Личные сообщения
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 h-[calc(100vh-280px)]">
        {/* Left Panel */}
        <div className="bg-[#121212] border border-white/5 rounded-xl overflow-hidden flex flex-col">
          {activeTab === "group_chats" ? (
            <>
              <div className="p-3 border-b border-white/5 flex items-center justify-between">
                <h3 className="text-white font-semibold text-sm">Групповые чаты</h3>
                <button onClick={() => setShowCreateGroupChat(true)} className="text-[#10B981] hover:text-[#059669]"><PlusCircle className="w-5 h-5" /></button>
              </div>
              <div className="flex-1 overflow-y-auto">
                {groupChats.length === 0 ? (
                  <div className="p-4 text-center">
                    <UserCog className="w-10 h-10 text-[#52525B] mx-auto mb-2" />
                    <p className="text-[#71717A] text-sm">Нет чатов</p>
                    <button onClick={() => setShowCreateGroupChat(true)} className="mt-2 text-[#10B981] text-xs hover:underline">Создать чат</button>
                  </div>
                ) : groupChats.map(chat => (
                  <div key={chat.id} onClick={() => setSelectedGroupChat(chat)} className={`p-3 border-b border-white/5 cursor-pointer transition-colors ${selectedGroupChat?.id === chat.id ? "bg-[#7C3AED]/10 border-l-2 border-l-[#7C3AED]" : "hover:bg-white/5"}`}>
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="text-white text-sm font-medium">{chat.name}</div>
                        <div className="text-[#52525B] text-xs">{chat.participants_count || 1} участников</div>
                      </div>
                      <button onClick={(e) => { e.stopPropagation(); leaveGroupChat(chat.id); }} className="text-[#EF4444]/50 hover:text-[#EF4444] p-1" title="Выйти"><LogOut className="w-4 h-4" /></button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : activeTab === "general" ? (
            <>
              <div className="p-3 border-b border-white/5"><h3 className="text-white font-semibold text-sm">Онлайн ({onlineStaff.length})</h3></div>
              <div className="flex-1 overflow-y-auto p-2">
                {onlineStaff.length === 0 ? (
                  <div className="p-4 text-center text-[#52525B] text-xs">Нет онлайн</div>
                ) : onlineStaff.map(s => {
                  const roleInfo = getRoleInfo(s.admin_role);
                  return (
                    <div key={s.id} className="flex items-center gap-2 p-2 rounded-lg hover:bg-white/5">
                      <div className="relative">
                        <div className={`w-8 h-8 rounded-lg ${roleInfo.color} flex items-center justify-center text-white text-xs font-bold`}>{s.login[0].toUpperCase()}</div>
                        <div className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-[#10B981] rounded-full border-2 border-[#121212]" />
                      </div>
                      <div>
                        <div className="text-white text-xs font-medium">{s.login}</div>
                        <div className={`text-[10px] ${roleInfo.text}`}>{roleInfo.icon} {roleInfo.name}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          ) : activeTab === "direct" ? (
            <>
              <div className="p-3 border-b border-white/5"><h3 className="text-white font-semibold text-sm">Персонал</h3></div>
              <div className="flex-1 overflow-y-auto">
                {loading ? <LoadingSpinner /> : staff.length === 0 ? (
                  <div className="p-4 text-center text-[#52525B] text-xs">Нет персонала</div>
                ) : staff.map(s => {
                  const roleInfo = getRoleInfo(s.admin_role);
                  const online = isOnline(s.id);
                  return (
                    <button key={s.id} onClick={() => setSelectedStaff(s)} className={`w-full p-3 text-left border-b border-white/5 hover:bg-white/5 transition-colors ${selectedStaff?.id === s.id ? 'bg-[#7C3AED]/10 border-l-2 border-l-[#7C3AED]' : ''}`}>
                      <div className="flex items-center gap-2">
                        <div className="relative">
                          <div className={`w-8 h-8 rounded-lg ${roleInfo.color} flex items-center justify-center text-white text-xs font-bold`}>{s.login[0].toUpperCase()}</div>
                          {online && <div className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-[#10B981] rounded-full border-2 border-[#121212]" />}
                        </div>
                        <div>
                          <div className="text-white text-sm font-medium">{s.login}</div>
                          <div className={`text-[10px] ${roleInfo.text}`}>{roleInfo.icon} {roleInfo.name}</div>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </>
          ) : null}
        </div>

        {/* Chat Area */}
        <div className="lg:col-span-3 bg-[#121212] border border-white/5 rounded-xl flex flex-col overflow-hidden">
          {/* Header */}
          <div className="p-3 border-b border-white/5 bg-[#0A0A0A]">
            {activeTab === "general" ? (
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#7C3AED] to-[#A855F7] flex items-center justify-center"><MessageCircle className="w-4 h-4 text-white" /></div>
                <div><h3 className="text-white font-semibold text-sm">Общий чат персонала</h3><p className="text-[10px] text-[#71717A]">Все сотрудники видят эти сообщения</p></div>
              </div>
            ) : activeTab === "direct" && selectedStaff ? (
              <div className="flex items-center gap-2">
                <div className={`w-8 h-8 rounded-lg ${getRoleInfo(selectedStaff.admin_role).color} flex items-center justify-center text-white text-xs font-bold`}>{selectedStaff.login[0].toUpperCase()}</div>
                <div><h3 className="text-white font-semibold text-sm">{selectedStaff.login}</h3><p className={`text-[10px] ${getRoleInfo(selectedStaff.admin_role).text}`}>{getRoleInfo(selectedStaff.admin_role).icon} {getRoleInfo(selectedStaff.admin_role).name}</p></div>
              </div>
            ) : activeTab === "group_chats" && selectedGroupChat ? (
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-[#10B981] flex items-center justify-center"><UserCog className="w-4 h-4 text-white" /></div>
                <div><h3 className="text-white font-semibold text-sm">{selectedGroupChat.name}</h3><p className="text-[10px] text-[#10B981]">{selectedGroupChat.participants_count || 1} участников</p></div>
              </div>
            ) : (
              <div className="text-[#71717A] text-sm">{activeTab === "direct" ? "Выберите сотрудника" : activeTab === "group_chats" ? "Выберите групповой чат" : ""}</div>
            )}
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {(activeTab === "general" || (activeTab === "direct" && selectedStaff) || (activeTab === "group_chats" && selectedGroupChat)) ? (
              messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full"><MessageCircle className="w-12 h-12 text-[#52525B] mb-3" /><p className="text-[#71717A] text-sm">Нет сообщений</p></div>
              ) : messages.map((msg, idx) => {
                const isMe = msg.sender_id === user?.id;
                const roleInfo = getRoleInfo(msg.sender_role);
                const isSystem = msg.is_system || msg.sender_role === "system";
                
                if (isSystem) return <div key={idx} className="flex justify-center"><div className="bg-[#6B7280]/20 text-[#A1A1AA] text-xs px-3 py-1 rounded-full">{msg.content || msg.message}</div></div>;

                return (
                  <div key={idx} className={`flex ${isMe ? 'justify-end' : 'justify-start'}`}>
                    <div className="max-w-[70%]">
                      {!isMe && <div className={`text-[10px] mb-0.5 ml-2 ${roleInfo.text}`}>{roleInfo.icon} {msg.sender_name || msg.sender_nickname || msg.sender_login} • {roleInfo.name}</div>}
                      <div className={`p-3 rounded-xl ${isMe ? 'bg-[#7C3AED]' : roleInfo.color} text-white`}>
                        <p className="text-sm whitespace-pre-wrap">{msg.content || msg.message}</p>
                        <p className="text-[10px] text-white/50 mt-1">{new Date(msg.created_at).toLocaleString("ru-RU", { hour: "2-digit", minute: "2-digit" })}</p>
                      </div>
                    </div>
                  </div>
                );
              })
            ) : activeTab === "group_chats" && !selectedGroupChat ? (
              <div className="flex flex-col items-center justify-center h-full"><UserCog className="w-12 h-12 text-[#52525B] mb-3" /><p className="text-[#71717A] text-sm">Выберите групповой чат</p></div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full"><UserCog className="w-12 h-12 text-[#52525B] mb-3" /><p className="text-[#71717A] text-sm">Выберите сотрудника</p></div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          {(activeTab === "general" || (activeTab === "direct" && selectedStaff) || (activeTab === "group_chats" && selectedGroupChat)) && (
            <div className="p-3 border-t border-white/5 bg-[#0A0A0A]">
              <div className="flex gap-2">
                <Input value={newMessage} onChange={(e) => setNewMessage(e.target.value)} placeholder={activeTab === "general" ? "Сообщение всему персоналу..." : activeTab === "group_chats" ? `Сообщение в «${selectedGroupChat?.name}»...` : `Сообщение для ${selectedStaff?.login}...`} className="flex-1 bg-[#121212] border-white/10 text-white h-10" onKeyPress={(e) => e.key === 'Enter' && handleSend()} data-testid="staff-message-input" />
                <Button onClick={handleSend} disabled={sending || !newMessage.trim()} className="bg-[#7C3AED] hover:bg-[#6D28D9] h-10 px-4" data-testid="staff-send-btn" title="Отправить сообщение">
                  {sending ? <Loader className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                </Button>
              </div>
            </div>
          )}

          {/* Role Legend */}
          <div className="px-3 py-2 border-t border-white/5 bg-[#0A0A0A]">
            <div className="flex flex-wrap gap-3 text-[10px] text-[#71717A]">
              <span className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-[#EF4444]" /> Админ/Владелец</span>
              <span className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-[#F59E0B]" /> Модератор</span>
              <span className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-[#3B82F6]" /> Поддержка</span>
            </div>
          </div>
        </div>
      </div>

      {/* Create Group Chat Modal */}
      {showCreateGroupChat && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-[#121212] border border-white/10 rounded-2xl w-full max-w-lg">
            <div className="p-4 border-b border-white/5 flex items-center justify-between">
              <h3 className="text-white font-semibold">💬 Новый групповой чат</h3>
              <button onClick={() => { setShowCreateGroupChat(false); setSelectedParticipants([]); setNewGroupChatName(""); }} className="text-[#71717A] hover:text-white"><XCircle className="w-5 h-5" /></button>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="text-[#71717A] text-xs mb-1 block">Название чата *</label>
                <Input value={newGroupChatName} onChange={e => setNewGroupChatName(e.target.value)} placeholder="Например: Обсуждение спора #123" className="bg-white/5 border-white/10" />
              </div>
              
              <div>
                <label className="text-[#71717A] text-xs mb-2 block">Участники чата</label>
                {selectedParticipants.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-3">
                    {selectedParticipants.map(p => (
                      <span key={p.id} className="flex items-center gap-1 px-2 py-1 rounded-lg bg-[#10B981]/20 text-[#10B981] text-xs">
                        {p.login}
                        <button onClick={() => toggleParticipant(p)} className="hover:text-white"><XCircle className="w-3 h-3" /></button>
                      </span>
                    ))}
                  </div>
                )}
                <div className="bg-white/5 rounded-xl max-h-48 overflow-y-auto">
                  {staff.filter(s => s.id !== user?.id).map(s => {
                    const isSelected = selectedParticipants.find(p => p.id === s.id);
                    const roleInfo = getRoleInfo(s.admin_role);
                    return (
                      <div key={s.id} onClick={() => toggleParticipant(s)} className={`p-3 border-b border-white/5 cursor-pointer transition-colors flex items-center justify-between ${isSelected ? "bg-[#10B981]/10" : "hover:bg-white/5"}`}>
                        <div className="flex items-center gap-2">
                          <div className={`w-8 h-8 rounded-lg ${roleInfo.color} flex items-center justify-center text-white text-xs font-bold`}>{s.login?.charAt(0).toUpperCase()}</div>
                          <div>
                            <div className="text-white text-sm">{s.nickname || s.login}</div>
                            <div className={`text-[10px] ${roleInfo.text}`}>{roleInfo.icon} {roleInfo.name}</div>
                          </div>
                        </div>
                        {isSelected ? <CheckCircle className="w-5 h-5 text-[#10B981]" /> : <div className="w-5 h-5 rounded-full border border-white/20" />}
                      </div>
                    );
                  })}
                </div>
                <p className="text-[#52525B] text-[10px] mt-1">Вы будете добавлены автоматически как создатель</p>
              </div>

              <Button onClick={createGroupChat} disabled={!newGroupChatName.trim()} className="w-full bg-[#10B981] hover:bg-[#059669] disabled:opacity-50" title="Создать новое объявление">
                <PlusCircle className="w-4 h-4 mr-2" /> Создать чат {selectedParticipants.length > 0 && `(${selectedParticipants.length + 1} участников)`}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default AdminMessagesToStaff;
