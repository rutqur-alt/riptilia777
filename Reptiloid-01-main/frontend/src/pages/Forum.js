import { useState, useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Wallet, ArrowLeft, Send, User, Shield, Store, Search, X } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { toast } from "sonner";

export default function Forum() {
  const { isAuthenticated, user, token } = useAuth();
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [showSearch, setShowSearch] = useState(false);
  const messagesEndRef = useRef(null);
  const wsRef = useRef(null);

  useEffect(() => {
    fetchMessages();
    connectWebSocket();
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const fetchMessages = async () => {
    try {
      const response = await axios.get(`${API}/forum/messages?limit=100`);
      setMessages(response.data);
    } catch (error) {
      console.error("Failed to fetch messages:", error);
    } finally {
      setLoading(false);
    }
  };

  const connectWebSocket = () => {
    const wsUrl = API.replace("https://", "wss://").replace("http://", "ws://").replace("/api", "");
    const ws = new WebSocket(`${wsUrl}/ws/forum`);
    
    ws.onopen = () => {
      console.log("Forum WebSocket connected");
    };
    
    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        setMessages(prev => {
          // Avoid duplicates
          if (prev.some(m => m.id === message.id)) {
            return prev;
          }
          return [...prev, message];
        });
      } catch (e) {
        console.error("Failed to parse message:", e);
      }
    };
    
    ws.onclose = () => {
      console.log("Forum WebSocket disconnected");
      // Reconnect after 3 seconds
      setTimeout(connectWebSocket, 3000);
    };
    
    ws.onerror = (error) => {
      console.error("Forum WebSocket error:", error);
    };
    
    wsRef.current = ws;
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!newMessage.trim() || sending) return;
    
    if (!isAuthenticated) {
      toast.error("Войдите, чтобы отправлять сообщения");
      return;
    }
    
    const messageContent = newMessage.trim();
    setSending(true);
    setNewMessage("");
    
    try {
      const response = await axios.post(
        `${API}/forum/messages`,
        { content: messageContent },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      // Add message immediately from response (WebSocket may not work in all environments)
      const newMsg = response.data;
      setMessages(prev => {
        // Avoid duplicates if WebSocket already added it
        if (prev.some(m => m.id === newMsg.id)) {
          return prev;
        }
        return [...prev, newMsg];
      });
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка отправки");
      setNewMessage(messageContent); // Restore message on error
    } finally {
      setSending(false);
    }
  };

  const getRoleIcon = (role) => {
    switch (role) {
      case "admin": return <Shield className="w-3 h-3 text-red-400" />;
      case "merchant": return <Store className="w-3 h-3 text-blue-400" />;
      default: return <User className="w-3 h-3 text-gray-400" />;
    }
  };

  const getRoleBadge = (role) => {
    switch (role) {
      case "admin": return "bg-red-500/20 text-red-400";
      case "merchant": return "bg-blue-500/20 text-blue-400";
      case "trader": return "bg-green-500/20 text-green-400";
      default: return "bg-gray-500/20 text-gray-400";
    }
  };

  const formatTime = (dateStr) => {
    const date = new Date(dateStr);
    return date.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  };

  const formatDate = (dateStr) => {
    const date = new Date(dateStr);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    
    if (date.toDateString() === today.toDateString()) return "Сегодня";
    if (date.toDateString() === yesterday.toDateString()) return "Вчера";
    return date.toLocaleDateString("ru-RU", { day: "numeric", month: "long" });
  };

  // Group messages by date (filtered by search)
  const filteredMessages = searchQuery.trim() 
    ? messages.filter(m => 
        m.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
        m.sender_login.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : messages;

  const groupedMessages = filteredMessages.reduce((groups, message) => {
    const date = formatDate(message.created_at);
    if (!groups[date]) groups[date] = [];
    groups[date].push(message);
    return groups;
  }, {});

  return (
    <div className="min-h-screen bg-[#0A0A0A] flex flex-col">
      {/* Header */}
      <header className="border-b border-white/5 flex-shrink-0">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link to="/">
                <Button variant="ghost" size="icon" className="text-[#A1A1AA] hover:text-white hover:bg-white/5">
                  <ArrowLeft className="w-5 h-5" />
                </Button>
              </Link>
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-[#7C3AED] flex items-center justify-center">
                  <Wallet className="w-4 h-4 text-white" />
                </div>
                <span className="text-lg font-semibold text-white">Форум</span>
              </div>
            </div>
            
            <div className="flex items-center gap-4">
              <span className="text-sm text-[#52525B]">
                {filteredMessages.length}{searchQuery ? ` из ${messages.length}` : ""} сообщений
              </span>
              
              {/* Search Toggle */}
              <Button
                variant="ghost"
                size="icon"
                onClick={() => {
                  setShowSearch(!showSearch);
                  if (showSearch) setSearchQuery("");
                }}
                className={`text-[#A1A1AA] hover:text-white hover:bg-white/5 ${showSearch ? 'text-[#7C3AED]' : ''}`}
                data-testid="forum-search-toggle"
              >
                {showSearch ? <X className="w-5 h-5" /> : <Search className="w-5 h-5" />}
              </Button>
              
              {isAuthenticated && (
                <Link to={user?.role === "admin" ? "/admin" : user?.role === "merchant" ? "/merchant" : "/trader"}>
                  <Button variant="outline" size="sm" className="border-[#7C3AED]/50 text-[#A78BFA] hover:bg-[#7C3AED]/10" title="Перейти в личный кабинет">
                    <User className="w-4 h-4 mr-2" />
                    Личный кабинет
                  </Button>
                </Link>
              )}
            </div>
          </div>
          
          {/* Search Input */}
          {showSearch && (
            <div className="mt-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#52525B]" />
                <Input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Поиск по сообщениям..."
                  className="bg-[#121212] border-white/10 text-white pl-10 rounded-xl h-10"
                  data-testid="forum-search-input"
                  autoFocus
                />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery("")}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[#52525B] hover:text-white"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </header>

      {/* Messages */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-4 py-4">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <div className="w-6 h-6 border-2 border-[#7C3AED] border-t-transparent rounded-full animate-spin" />
            </div>
          ) : messages.length === 0 ? (
            <div className="text-center py-20">
              <p className="text-[#52525B]">Чат пуст. Будьте первым!</p>
            </div>
          ) : filteredMessages.length === 0 ? (
            <div className="text-center py-20">
              <Search className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
              <p className="text-[#52525B]">Ничего не найдено по запросу "{searchQuery}"</p>
              <button 
                onClick={() => setSearchQuery("")}
                className="text-[#7C3AED] hover:underline mt-2 text-sm"
               title="Очистить данные">
                Очистить поиск
              </button>
            </div>
          ) : (
            <div className="space-y-6">
              {Object.entries(groupedMessages).map(([date, msgs]) => (
                <div key={date}>
                  {/* Date separator */}
                  <div className="flex items-center gap-4 my-6">
                    <div className="flex-1 h-px bg-white/5" />
                    <span className="text-xs text-[#52525B]">{date}</span>
                    <div className="flex-1 h-px bg-white/5" />
                  </div>
                  
                  {/* Messages for this date */}
                  <div className="space-y-3">
                    {msgs.map((message) => (
                      <div
                        key={message.id}
                        data-testid={`forum-message-${message.id}`}
                        className={`flex gap-3 ${
                          user?.id === message.sender_id ? "flex-row-reverse" : ""
                        }`}
                      >
                        {/* Avatar */}
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                          message.sender_role === "admin" ? "bg-red-500/20" :
                          message.sender_role === "merchant" ? "bg-blue-500/20" :
                          "bg-[#1A1A1A]"
                        }`}>
                          {getRoleIcon(message.sender_role)}
                        </div>
                        
                        {/* Message bubble */}
                        <div className={`max-w-[70%] ${
                          user?.id === message.sender_id 
                            ? "bg-[#7C3AED]/20 border-[#7C3AED]/30" 
                            : "bg-[#121212] border-white/5"
                        } border rounded-xl px-4 py-2`}>
                          {/* Header */}
                          <div className="flex items-center gap-2 mb-1">
                            <span className={`text-sm font-medium ${
                              user?.id === message.sender_id ? "text-[#A78BFA]" : "text-white"
                            }`}>
                              {message.sender_login}
                            </span>
                            <span className={`text-[10px] px-1.5 py-0.5 rounded ${getRoleBadge(message.sender_role)}`}>
                              {message.sender_role === "admin" ? "Админ" :
                               message.sender_role === "merchant" ? "Мерчант" : "Пользователь"}
                            </span>
                            <span className="text-xs text-[#52525B]">
                              {formatTime(message.created_at)}
                            </span>
                          </div>
                          
                          {/* Content */}
                          <p className="text-[#E4E4E7] text-sm whitespace-pre-wrap break-words">
                            {message.content}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>
      </main>

      {/* Input */}
      <div className="border-t border-white/5 flex-shrink-0">
        <div className="max-w-4xl mx-auto px-4 py-4">
          {isAuthenticated ? (
            <form onSubmit={handleSendMessage} className="flex gap-3">
              <Input
                data-testid="forum-input"
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                placeholder="Написать сообщение..."
                maxLength={1000}
                className="flex-1 bg-[#121212] border-white/10 text-white placeholder:text-[#52525B] rounded-xl h-11"
              />
              <Button
                data-testid="forum-send-btn"
                type="submit"
                disabled={!newMessage.trim() || sending}
                className="bg-[#7C3AED] hover:bg-[#6D28D9] text-white rounded-xl h-11 px-6"
              >
                <Send className="w-4 h-4" />
              </Button>
            </form>
          ) : (
            <div className="text-center py-2">
              <Link to="/auth">
                <Button className="bg-[#7C3AED] hover:bg-[#6D28D9] text-white rounded-xl" title="Войти в аккаунт">
                  Войти, чтобы писать
                </Button>
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
