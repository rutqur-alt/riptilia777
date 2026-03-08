import React, { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { API } from "@/App";
import {
  BarChart3, Wallet, FileText, RefreshCw, LogOut, Settings,
  ArrowDownCircle, ArrowUpCircle, Copy, DollarSign, TrendingUp,
  Activity, CreditCard, AlertTriangle, MessageSquare, X, Send, Loader, MessageCircle
} from "lucide-react";


// Auth context for QR Provider
function useAuth() {
  const token = localStorage.getItem("token");
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  const logout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    window.location.href = "/login";
  };
  return { token, user, logout };
}

// ==================== Main Dashboard ====================


// Role display config for dispute chat
const ROLE_DISPLAY = {
  user:        { label: "Пользователь", color: "#3B82F6", bg: "bg-white/10 text-white" },
  buyer:       { label: "Покупатель",   color: "#3B82F6", bg: "bg-white/10 text-white" },
  p2p_seller:  { label: "Продавец",     color: "#3B82F6", bg: "bg-white/10 text-white" },
  trader:      { label: "Трейдер",      color: "#10B981", bg: "bg-white/10 text-white" },
  merchant:    { label: "Мерчант",      color: "#F97316", bg: "bg-[#F97316]/20 text-white" },
  shop_owner:  { label: "Магазин",      color: "#8B5CF6", bg: "bg-[#8B5CF6]/20 text-white" },
  qr_provider: { label: "Провайдер",    color: "#A855F7", bg: "bg-[#A855F7]/20 text-white" },
  mod_p2p:     { label: "Модератор",    color: "#F59E0B", bg: "bg-[#F59E0B]/20 text-white" },
  moderator:   { label: "Модератор",    color: "#F59E0B", bg: "bg-[#F59E0B]/20 text-white" },
  mod_market:  { label: "Гарант",       color: "#F59E0B", bg: "bg-[#F59E0B]/20 text-white" },
  support:     { label: "Поддержка",    color: "#3B82F6", bg: "bg-[#3B82F6]/20 text-white" },
  admin:       { label: "Админ",        color: "#EF4444", bg: "bg-[#EF4444]/20 text-white" },
  owner:       { label: "Супер Админ",  color: "#EF4444", bg: "bg-[#EF4444]/20 text-white" },
  system:      { label: "Система",      color: "#6B7280", bg: "bg-[#6B7280]/20 text-white" },
};
const getRoleDisplay = (role) => ROLE_DISPLAY[role] || ROLE_DISPLAY.user;

// ==================== Dispute Chat Modal ====================
function DisputeChatModal({ open, onClose, tradeId, token }) {
  const [messages, setMessages] = useState([]);
  const [trade, setTrade] = useState(null);
  const [loading, setLoading] = useState(true);
  const [newMessage, setNewMessage] = useState('');
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef(null);

  const fetchChat = useCallback(async (silent = false) => {
    if (!tradeId) return;
    if (!silent) setLoading(true);
    try {
      const res = await axios.get(`${API}/qr-aggregator/provider/disputes/${tradeId}/chat`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setMessages(res.data.messages || []);
      setTrade(res.data.trade || null);
    } catch (e) {
      if (!silent) toast.error("Ошибка загрузки чата");
    } finally {
      if (!silent) setLoading(false);
    }
  }, [tradeId, token]);

  useEffect(() => {
    if (open && tradeId) {
      fetchChat();
      const interval = setInterval(() => fetchChat(true), 5000);
      return () => clearInterval(interval);
    }
  }, [open, tradeId, fetchChat]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async () => {
    if (!newMessage.trim() || !tradeId) return;
    setSending(true);
    try {
      await axios.post(`${API}/qr-aggregator/provider/disputes/${tradeId}/chat`,
        { content: newMessage.trim() },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setNewMessage('');
      await fetchChat(true);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Ошибка отправки');
    } finally {
      setSending(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-[#18181B] border border-white/10 rounded-xl w-full max-w-lg max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-white/5">
          <div className="flex items-center gap-2">
            <MessageCircle className="w-5 h-5 text-[#3B82F6]" />
            <span className="text-white font-medium">Чат спора</span>
            {trade && <span className="text-xs text-[#71717A] font-mono ml-2">#{tradeId?.slice(0, 10)}</span>}
          </div>
          <button onClick={onClose} className="p-1 rounded hover:bg-white/10 text-[#71717A]">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Trade Info */}
        {trade && (
          <div className="px-4 py-2 bg-[#0D0D1A] border-b border-white/5 text-xs flex items-center justify-between">
            <div>
              <span className="text-[#71717A]">Сумма: </span>
              <span className="text-white">{(trade.amount_usdt || 0).toFixed(2)} USDT</span>
              <span className="text-[#71717A] ml-3">Статус: </span>
              <span className={trade.status === 'disputed' ? 'text-[#EF4444]' : 'text-[#71717A]'}>{trade.status}</span>
            </div>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2 min-h-[200px] max-h-[400px]" style={{scrollbarWidth: "thin", scrollbarColor: "#333 transparent"}}>
          {loading ? (
            <div className="flex justify-center py-10">
              <Loader className="w-6 h-6 animate-spin text-[#71717A]" />
            </div>
          ) : messages.length === 0 ? (
            <div className="text-center py-10">
              <MessageCircle className="w-12 h-12 text-[#52525B] mx-auto mb-3" />
              <p className="text-[#71717A] text-sm">Сообщений нет</p>
            </div>
          ) : (
            messages.map((msg, i) => {
              const ri = getRoleDisplay(msg.sender_role);
              return (
              <div key={msg.id || i} className={`flex ${msg.sender_role === "qr_provider" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[80%] rounded-xl px-3 py-2 ${ri.bg}`}>
                  <div className="text-xs font-medium mb-1" style={{color: ri.color}}>
                    <span className="opacity-60">[{ri.label}]</span>{" "}
                    {msg.sender_nickname || msg.sender_name || ri.label}
                  </div>
                  <div className="text-sm whitespace-pre-wrap break-words">{msg.content || msg.text || msg.message}</div>
                  <div className="text-[10px] text-[#52525B] mt-1 text-right">
                    {msg.created_at ? new Date(msg.created_at).toLocaleString("ru-RU") : ""}
                  </div>
                </div>
              </div>
            );})
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Message Input */}
        {trade && ['disputed', 'paid', 'pending', 'cancelled'].includes(trade.status) && (
          <div className="p-3 border-t border-white/5">
            <div className="flex gap-2">
              <input
                type="text"
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                placeholder="Написать сообщение..."
                className="flex-1 px-4 py-2.5 bg-[#0D0D1A] border border-white/10 rounded-xl text-white text-sm placeholder-[#52525B] focus:outline-none focus:border-[#A855F7]/50"
              />
              <button
                onClick={sendMessage}
                disabled={!newMessage.trim() || sending}
                className="px-4 py-2.5 bg-[#A855F7] hover:bg-[#9333EA] disabled:opacity-50 text-white rounded-xl transition-colors"
              >
                {sending ? <Loader className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ==================== Disputes Page ====================
function DisputesPage() {
  const { token } = useAuth();
  const [disputes, setDisputes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [chatTradeId, setChatTradeId] = useState(null);
  const [showChat, setShowChat] = useState(false);

  const fetchDisputes = useCallback(async () => {
    try {
      setLoading(true);
      const res = await axios.get(`${API}/qr-aggregator/provider/disputes`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setDisputes(res.data.disputes || []);
    } catch (e) {
      toast.error("Ошибка загрузки споров");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchDisputes(); }, [fetchDisputes]);

  const getStatusBadge = (status) => {
    switch(status) {
      case "disputed": return <span className="px-2 py-0.5 bg-[#EF4444]/20 text-[#EF4444] rounded text-xs">Открыт</span>;
      case "completed": return <span className="px-2 py-0.5 bg-[#10B981]/20 text-[#10B981] rounded text-xs">Решён</span>;
      case "cancelled": return <span className="px-2 py-0.5 bg-[#71717A]/20 text-[#71717A] rounded text-xs">Отменён</span>;
      case "pending_completion": return <span className="px-2 py-0.5 bg-[#F59E0B]/20 text-[#F59E0B] rounded text-xs inline-flex items-center gap-1" title="Ожидайте, скоро сделка завершится">⏳ Завершается</span>;
      default: return <span className="px-2 py-0.5 bg-[#F59E0B]/20 text-[#F59E0B] rounded text-xs">{status}</span>;
    }
  };

  const formatDate = (d) => {
    if (!d) return "-";
    try { return new Date(d).toLocaleString("ru-RU"); } catch { return d; }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white flex items-center gap-2">
          <AlertTriangle className="w-6 h-6 text-[#EF4444]" /> Споры
        </h2>
        <button onClick={fetchDisputes} className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-[#A1A1AA]">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {loading ? (
        <div className="text-center text-[#71717A] py-8">Загрузка...</div>
      ) : disputes.length === 0 ? (
        <div className="bg-[#18181B] border border-white/5 rounded-xl p-8 text-center">
          <AlertTriangle className="w-12 h-12 text-[#71717A] mx-auto mb-3" />
          <p className="text-[#71717A]">Нет активных споров</p>
        </div>
      ) : (
        <div className="space-y-3">
          {disputes.map((d) => (
            <div key={d.trade_id} className="bg-[#18181B] border border-white/5 rounded-xl p-4 hover:border-white/10 transition-colors">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <span className="text-xs text-[#71717A] font-mono">{d.trade_id?.slice(0, 12)}...</span>
                  {getStatusBadge(d.status)}
                  {d.unread_count > 0 && (
                    <span className="px-2 py-0.5 bg-[#EF4444] text-white rounded-full text-[10px] font-bold animate-pulse">
                      {d.unread_count} новых
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => { setChatTradeId(d.trade_id); setShowChat(true); }}
                    className="flex items-center gap-1 px-3 py-1.5 bg-[#A855F7]/20 hover:bg-[#A855F7]/30 text-[#A855F7] rounded-lg text-xs transition-colors"
                  >
                    <MessageCircle className="w-3.5 h-3.5" /> Чат
                    {d.unread_count > 0 && (
                      <span className="ml-1 px-1.5 py-0.5 bg-[#EF4444] text-white rounded-full text-[9px] font-bold">
                        {d.unread_count}
                      </span>
                    )}
                  </button>
                  <span className="text-xs text-[#71717A]">{formatDate(d.disputed_at)}</span>
                </div>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                <div>
                  <span className="text-[#71717A]">Мерчант: </span>
                  <span className="text-[#F97316]">{d.merchant_name}</span>
                </div>
                <div>
                  <span className="text-[#71717A]">Сумма: </span>
                  <span className="text-white">{(d.amount_usdt || 0).toFixed(2)} USDT</span>
                </div>
                <div>
                  <span className="text-[#71717A]">Причина: </span>
                  <span className="text-[#EF4444]">{d.dispute_reason || "-"}</span>
                </div>
                <div>
                  <span className="text-[#71717A]">Открыт: </span>
                  <span className="text-white">{d.disputed_by_role || "-"}</span>
                </div>
              </div>
              {d.dispute_resolved && (
                <div className="mt-2 text-xs text-[#10B981]">
                  Решение: {d.dispute_resolution || "Решён"}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Chat Modal */}
      <DisputeChatModal
        open={showChat}
        onClose={() => { setShowChat(false); fetchDisputes(); }}
        tradeId={chatTradeId}
        token={token}
      />
    </div>
  );
}

export default function QRProviderDashboard() {
  const { token, user, logout } = useAuth();
  const [currentPage, setCurrentPage] = useState("dashboard");

  if (!token || user?.role !== "qr_provider") {
    window.location.href = "/login";
    return null;
  }

  const pages = {
    dashboard: <DashboardPage />,
    operations: <OperationsPage />,
    finances: <FinancesPage />,
    deposit: <DepositPage />,
    withdraw: <WithdrawPage />,
    disputes: <DisputesPage />,
  };

  const navItems = [
    { key: "dashboard", label: "Обзор", icon: BarChart3 },
    { key: "operations", label: "Операции", icon: FileText },
    { key: "finances", label: "Финансы", icon: Wallet },
    { key: "deposit", label: "Пополнение", icon: ArrowDownCircle },
    { key: "withdraw", label: "Вывод", icon: ArrowUpCircle },
    { key: "disputes", label: "Споры", icon: AlertTriangle },
  ];

  return (
    <div className="min-h-screen bg-[#0D0D1A]">
      {/* Top Navigation */}
      <div className="bg-[#1A1A2E] border-b border-gray-700 px-6 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-6">
            <h1 className="text-lg font-bold text-white">QR Провайдер</h1>
            <nav className="flex gap-1">
              {navItems.map(item => (
                <button key={item.key} onClick={() => setCurrentPage(item.key)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-sm transition-colors ${
                    currentPage === item.key ? 'bg-[#A855F7] text-white' : 'text-gray-400 hover:text-white hover:bg-gray-700'
                  }`}>
                  <item.icon className="w-4 h-4" />
                  {item.label}
                </button>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-400">{user.display_name || user.login}</span>
            <Button variant="ghost" size="sm" onClick={logout} className="text-gray-400 hover:text-red-400">
              <LogOut className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-6 py-6">
        {pages[currentPage] || pages.dashboard}
      </div>
    </div>
  );
}

// ==================== Dashboard Page ====================
function DashboardPage() {
  const { token } = useAuth();
  const [stats, setStats] = useState(null);
  const [wallet, setWallet] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [statsRes, walletRes] = await Promise.all([
        axios.get(`${API}/qr-provider/stats`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/qr-provider/wallet`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      setStats(statsRes.data);
      setWallet(walletRes.data);
    } catch (e) { toast.error("Ошибка загрузки данных"); }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) return <Spinner />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white">Обзор</h2>
        <Button variant="ghost" size="sm" onClick={fetchData}><RefreshCw className="w-4 h-4 text-gray-400" /></Button>
      </div>

      {/* Balance Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Баланс USDT" value={`${(wallet?.balance_usdt || 0).toFixed(2)}`} sub="USDT" color="purple" icon={DollarSign} />
        <StatCard label="Доступно" value={`${(wallet?.available_usdt || 0).toFixed(2)}`} sub="USDT" color="green" icon={Wallet} />
        <StatCard label="Заморожено" value={`${(wallet?.frozen_usdt || 0).toFixed(2)}`} sub="USDT" color="yellow" icon={Activity} />
        <StatCard label="Всего заработано" value={`${(wallet?.total_earnings_usdt || 0).toFixed(4)}`} sub="USDT" color="blue" icon={TrendingUp} />
      </div>

      {/* Separate Integration Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* NSPK Stats */}
        <div className="bg-[#1A1A2E] border border-blue-500/30 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <CreditCard className="w-5 h-5 text-blue-400" />
            <h3 className="text-white font-medium">NSPK (QR)</h3>
            <span className={`text-xs px-2 py-0.5 rounded ml-auto ${stats?.nspk_api_available ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'}`}>
              {stats?.nspk_api_available ? 'API OK' : 'API X'}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <p className="text-gray-400">Сегодня</p>
              <p className="text-white font-medium">{stats?.nspk?.today?.operations || 0} оп. / {stats?.nspk?.today?.completed || 0} зав.</p>
              <p className="text-xs text-gray-500">{(stats?.nspk?.today?.volume_rub || 0).toLocaleString()} P</p>
            </div>
            <div>
              <p className="text-gray-400">Всего</p>
              <p className="text-white font-medium">{stats?.nspk?.total?.operations || 0} оп. / {stats?.nspk?.total?.completed || 0} зав.</p>
              <p className="text-xs text-gray-500">{(stats?.nspk?.total?.volume_rub || 0).toLocaleString()} P</p>
            </div>
          </div>
          <div className="mt-2 pt-2 border-t border-gray-700">
            <p className="text-xs text-gray-400">Успешность: <span className="text-white">{stats?.nspk?.success_rate || 100}%</span></p>
          </div>
        </div>

        {/* TransGrant Stats */}
        <div className="bg-[#1A1A2E] border border-orange-500/30 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <CreditCard className="w-5 h-5 text-orange-400" />
            <h3 className="text-white font-medium">TransGrant (СНГ)</h3>
            <span className={`text-xs px-2 py-0.5 rounded ml-auto ${stats?.transgrant_api_available ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'}`}>
              {stats?.transgrant_api_available ? 'API OK' : 'API X'}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <p className="text-gray-400">Сегодня</p>
              <p className="text-white font-medium">{stats?.transgrant?.today?.operations || 0} оп. / {stats?.transgrant?.today?.completed || 0} зав.</p>
              <p className="text-xs text-gray-500">{(stats?.transgrant?.today?.volume_rub || 0).toLocaleString()} P</p>
            </div>
            <div>
              <p className="text-gray-400">Всего</p>
              <p className="text-white font-medium">{stats?.transgrant?.total?.operations || 0} оп. / {stats?.transgrant?.total?.completed || 0} зав.</p>
              <p className="text-xs text-gray-500">{(stats?.transgrant?.total?.volume_rub || 0).toLocaleString()} P</p>
            </div>
          </div>
          <div className="mt-2 pt-2 border-t border-gray-700">
            <p className="text-xs text-gray-400">Успешность: <span className="text-white">{stats?.transgrant?.success_rate || 100}%</span></p>
          </div>
        </div>
      </div>

      {/* Active Operations */}
      <div className="bg-[#1A1A2E] border border-gray-700 rounded-lg p-4">
        <p className="text-sm text-gray-400">Активных операций: <span className="text-white font-medium">{stats?.active_operations || 0}</span></p>
      </div>
    </div>
  );
}

// ==================== Operations Page ====================
function OperationsPage() {
  const { token } = useAuth();
  const [operations, setOperations] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [methodFilter, setMethodFilter] = useState("");
  const [loading, setLoading] = useState(true);

  const fetchOps = useCallback(async () => {
    try {
      const params = new URLSearchParams({ page, limit: 20 });
      if (statusFilter) params.set("status", statusFilter);
      if (methodFilter) params.set("method", methodFilter);
      const res = await axios.get(`${API}/qr-provider/operations?${params}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setOperations(res.data.operations || []);
      setTotal(res.data.total || 0);
    } catch (e) { toast.error("Ошибка загрузки операций"); }
    finally { setLoading(false); }
  }, [token, page, statusFilter, methodFilter]);

  useEffect(() => { fetchOps(); }, [fetchOps]);

  const statusColors = {
    pending: "bg-yellow-500/20 text-yellow-400",
    processing: "bg-blue-500/20 text-blue-400",
    paid: "bg-cyan-500/20 text-cyan-400",
    completed: "bg-green-500/20 text-green-400",
    rejected: "bg-red-500/20 text-red-400",
    expired: "bg-gray-500/20 text-gray-400",
    cancelled: "bg-red-500/20 text-red-400",
  };

  const statusLabels = {
    pending: "Ожидание", processing: "В процессе", paid: "Оплачена",
    completed: "Завершена", rejected: "Отклонена", expired: "Истекла", cancelled: "Отменена",
  };

  const copyToClipboard = async (text, label = "") => {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(String(text));
      toast.success(label ? `${label} скопирован` : "Скопировано");
    } catch {
      toast.error("Не удалось скопировать");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white">Операции</h2>
        <div className="flex items-center gap-2">
          <select value={methodFilter} onChange={(e) => { setMethodFilter(e.target.value); setPage(1); }}
            className="bg-[#1A1A2E] border border-gray-600 rounded px-3 py-1.5 text-sm text-white">
            <option value="">Все методы</option>
            <option value="nspk">NSPK (QR)</option>
            <option value="transgrant">TransGrant (СНГ)</option>
          </select>
          <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="bg-[#1A1A2E] border border-gray-600 rounded px-3 py-1.5 text-sm text-white">
            <option value="">Все статусы</option>
            <option value="pending">Ожидание</option>
            <option value="completed">Завершённые</option>
            <option value="rejected">Отклонённые</option>
          </select>
          <Button variant="ghost" size="sm" onClick={fetchOps}><RefreshCw className="w-4 h-4 text-gray-400" /></Button>
        </div>
      </div>

      {loading ? <Spinner /> : operations.length === 0 ? (
        <div className="bg-[#1A1A2E] border border-gray-700 rounded-lg p-8 text-center text-gray-400">Нет операций</div>
      ) : (
        <div className="space-y-2">
          {operations.map((op) => (
            <div key={op.id} className="bg-[#1A1A2E] border border-gray-700 rounded-lg p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-sm text-white font-medium flex flex-wrap items-center gap-x-2 gap-y-1">
                    <span className={op.payment_method === 'nspk' ? 'text-blue-400' : 'text-orange-400'}>
                      {op.payment_method === 'nspk' ? 'NSPK' : 'TransGrant'}
                    </span>
                    <span className="text-gray-500">•</span>
                    <span>{(op.amount_rub || 0).toLocaleString()} ₽</span>
                    {op.trade_amount_usdt != null && (
                      <>
                        <span className="text-gray-500">•</span>
                        <span className="text-gray-300">{Number(op.trade_amount_usdt).toFixed(4)} USDT</span>
                      </>
                    )}
                    {op.trade_number && (
                      <>
                        <span className="text-gray-500">•</span>
                        <button
                          type="button"
                          onClick={() => copyToClipboard(op.trade_number, "Номер сделки")}
                          className="inline-flex items-center gap-1 text-[#A855F7] hover:underline"
                          title="Скопировать номер сделки"
                        >
                          №{op.trade_number} <Copy className="w-3.5 h-3.5" />
                        </button>
                      </>
                    )}
                  </p>

                  <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-gray-400">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-gray-500">Trade ID:</span>
                      <span className="font-mono text-gray-300 truncate">{op.trade_id || "-"}</span>
                      {op.trade_id && (
                        <button
                          type="button"
                          onClick={() => copyToClipboard(op.trade_id, "Trade ID")}
                          className="p-1 rounded hover:bg-white/10"
                          title="Скопировать Trade ID"
                        >
                          <Copy className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>

                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-gray-500">TrustGain:</span>
                      <span className="font-mono text-gray-300 truncate">{op.trustgain_operation_id || "-"}</span>
                      {op.trustgain_operation_id && (
                        <button
                          type="button"
                          onClick={() => copyToClipboard(op.trustgain_operation_id, "TrustGain ID")}
                          className="p-1 rounded hover:bg-white/10"
                          title="Скопировать TrustGain ID"
                        >
                          <Copy className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>

                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-gray-500">Op ID:</span>
                      <span className="font-mono text-gray-300 truncate">{op.id}</span>
                      <button
                        type="button"
                        onClick={() => copyToClipboard(op.id, "ID операции")}
                        className="p-1 rounded hover:bg-white/10"
                        title="Скопировать ID операции"
                      >
                        <Copy className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-gray-500">Создано:</span>
                      <span className="text-gray-300">{op.created_at ? new Date(op.created_at).toLocaleString("ru-RU") : "-"}</span>
                      {op.status === "pending" && op.trade_expires_at && (
                        <span className="ml-2 text-[#F59E0B]" title="Авто-отмена через 30 минут, если оплата не пройдёт">
                          истекает: {new Date(op.trade_expires_at).toLocaleTimeString("ru-RU")}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="text-right shrink-0">
                  {op.provider_earning_usdt > 0 && (
                    <p className="text-sm text-green-400">+{op.provider_earning_usdt.toFixed(4)} USDT</p>
                  )}
                  <span className={`text-xs px-2 py-1 rounded ${statusColors[op.status] || 'bg-gray-500/20 text-gray-400'}`}>
                    {statusLabels[op.status] || op.status}
                  </span>
                  {op.trade_status && op.trade_status !== op.status && (
                    <div className="mt-1 text-[10px] text-gray-500">
                      статус сделки: <span className="font-mono">{op.trade_status}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}

          {total > 20 && (
            <div className="flex justify-center gap-2 pt-4">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)} className="border-gray-600 text-gray-300">Назад</Button>
              <span className="text-sm text-gray-400 py-1">Стр. {page} из {Math.ceil(total / 20)}</span>
              <Button variant="outline" size="sm" disabled={operations.length < 20} onClick={() => setPage(page + 1)} className="border-gray-600 text-gray-300">Далее</Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ==================== Finances Page ====================
function FinancesPage() {
  const { token } = useAuth();
  const [finances, setFinances] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchFinances = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/qr-provider/finances`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setFinances(res.data);
    } catch (e) { toast.error("Ошибка загрузки финансов"); }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => { fetchFinances(); }, [fetchFinances]);

  if (loading) return <Spinner />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white">Финансы</h2>
        <Button variant="ghost" size="sm" onClick={fetchFinances}><RefreshCw className="w-4 h-4 text-gray-400" /></Button>
      </div>

      {/* USDT Balance */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-[#1A1A2E] border border-purple-500/30 rounded-lg p-6 text-center">
          <p className="text-sm text-gray-400 mb-2">Баланс</p>
          <p className="text-3xl font-bold text-white">{(finances?.balance_usdt || 0).toFixed(2)}</p>
          <p className="text-sm text-gray-500">USDT</p>
        </div>
        <div className="bg-[#1A1A2E] border border-green-500/30 rounded-lg p-6 text-center">
          <p className="text-sm text-gray-400 mb-2">Доступно</p>
          <p className="text-3xl font-bold text-green-400">{(finances?.available_usdt || 0).toFixed(2)}</p>
          <p className="text-sm text-gray-500">USDT</p>
        </div>
        <div className="bg-[#1A1A2E] border border-yellow-500/30 rounded-lg p-6 text-center">
          <p className="text-sm text-gray-400 mb-2">Заморожено</p>
          <p className="text-3xl font-bold text-yellow-400">{(finances?.frozen_usdt || 0).toFixed(2)}</p>
          <p className="text-sm text-gray-500">USDT</p>
        </div>
      </div>

      {/* Per-Integration Earnings */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-[#1A1A2E] border border-blue-500/30 rounded-lg p-4">
          <h3 className="text-blue-400 font-medium mb-3">NSPK (QR) - Статистика</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-gray-400">Операций:</span><span className="text-white">{finances?.nspk?.total_operations || 0}</span></div>
            <div className="flex justify-between"><span className="text-gray-400">Завершённых:</span><span className="text-green-400">{finances?.nspk?.completed_operations || 0}</span></div>
            <div className="flex justify-between"><span className="text-gray-400">Оборот:</span><span className="text-white">{(finances?.nspk?.turnover_rub || 0).toLocaleString()} P</span></div>
            <div className="flex justify-between"><span className="text-gray-400">Заработано:</span><span className="text-green-400">{(finances?.nspk?.earnings_usdt || 0).toFixed(4)} USDT</span></div>
            <div className="flex justify-between"><span className="text-gray-400">Успешность:</span><span className="text-white">{finances?.nspk?.success_rate || 100}%</span></div>
          </div>
        </div>
        <div className="bg-[#1A1A2E] border border-orange-500/30 rounded-lg p-4">
          <h3 className="text-orange-400 font-medium mb-3">TransGrant (СНГ) - Статистика</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-gray-400">Операций:</span><span className="text-white">{finances?.transgrant?.total_operations || 0}</span></div>
            <div className="flex justify-between"><span className="text-gray-400">Завершённых:</span><span className="text-green-400">{finances?.transgrant?.completed_operations || 0}</span></div>
            <div className="flex justify-between"><span className="text-gray-400">Оборот:</span><span className="text-white">{(finances?.transgrant?.turnover_rub || 0).toLocaleString()} P</span></div>
            <div className="flex justify-between"><span className="text-gray-400">Заработано:</span><span className="text-green-400">{(finances?.transgrant?.earnings_usdt || 0).toFixed(4)} USDT</span></div>
            <div className="flex justify-between"><span className="text-gray-400">Успешность:</span><span className="text-white">{finances?.transgrant?.success_rate || 100}%</span></div>
          </div>
        </div>
      </div>

      {/* Withdrawal History */}
      {finances?.withdrawal_history?.length > 0 && (
        <div className="bg-[#1A1A2E] border border-gray-700 rounded-lg p-4">
          <h3 className="text-white font-medium mb-3">История выводов</h3>
          <div className="space-y-2">
            {finances.withdrawal_history.map((wd) => (
              <div key={wd.id} className="flex items-center justify-between p-3 bg-[#0D0D1A] rounded-lg">
                <div>
                  <p className="text-sm text-white">{wd.amount} USDT</p>
                  <p className="text-xs text-gray-400">{wd.to_address?.slice(0, 15)}... | {wd.created_at ? new Date(wd.created_at).toLocaleString() : ''}</p>
                </div>
                <span className={`text-xs px-2 py-1 rounded ${
                  wd.status === 'completed' ? 'bg-green-500/20 text-green-400' :
                  wd.status === 'pending' ? 'bg-yellow-500/20 text-yellow-400' :
                  'bg-red-500/20 text-red-400'
                }`}>{wd.status === 'completed' ? 'Выполнен' : wd.status === 'pending' ? 'Ожидание' : wd.status}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Transactions */}
      {finances?.recent_transactions?.length > 0 && (
        <div className="bg-[#1A1A2E] border border-gray-700 rounded-lg p-4">
          <h3 className="text-white font-medium mb-3">Последние транзакции</h3>
          <div className="space-y-2">
            {finances.recent_transactions.slice(0, 15).map((tx) => (
              <div key={tx.id} className="flex items-center justify-between p-3 bg-[#0D0D1A] rounded-lg">
                <div>
                  <p className="text-sm text-white">{tx.description || tx.type}</p>
                  <p className="text-xs text-gray-400">{tx.created_at ? new Date(tx.created_at).toLocaleString() : ''}</p>
                </div>
                <p className={`text-sm font-medium ${tx.amount >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {tx.amount >= 0 ? '+' : ''}{tx.amount?.toFixed(2)} USDT
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ==================== Deposit Page ====================
function DepositPage() {
  const { token } = useAuth();
  const [depositInfo, setDepositInfo] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchDeposit = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/qr-provider/deposit-address`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setDepositInfo(res.data.deposit_info);
    } catch (e) { toast.error("Ошибка загрузки адреса"); }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => { fetchDeposit(); }, [fetchDeposit]);

  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text);
    toast.success(`${label} скопировано`);
  };

  if (loading) return <Spinner />;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-white">Пополнение баланса</h2>

      <div className="bg-[#1A1A2E] border border-purple-500/30 rounded-lg p-6 space-y-4">
        <h3 className="text-lg font-semibold text-white">Отправьте USDT на адрес ниже</h3>

        {/* Address */}
        <div>
          <label className="text-sm text-gray-400 mb-1 block">Адрес кошелька:</label>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-[#0D0D1A] border border-gray-600 rounded px-4 py-3 text-white font-mono text-sm break-all">
              {depositInfo?.address || 'Загрузка...'}
            </code>
            {depositInfo?.address && (
              <Button variant="outline" size="sm" onClick={() => copyToClipboard(depositInfo.address, "Адрес")}
                className="border-purple-500/50 text-purple-400 hover:bg-purple-500/10 shrink-0">
                <Copy className="w-4 h-4" />
              </Button>
            )}
          </div>
        </div>

        {/* Comment/Memo */}
        <div>
          <label className="text-sm text-gray-400 mb-1 block">Комментарий (ОБЯЗАТЕЛЬНО):</label>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-[#0D0D1A] border border-yellow-500/30 rounded px-4 py-3 text-yellow-400 font-mono text-2xl font-bold text-center">
              {depositInfo?.comment || '...'}
            </code>
            {depositInfo?.comment && (
              <Button variant="outline" size="sm" onClick={() => copyToClipboard(depositInfo.comment, "Комментарий")}
                className="border-yellow-500/50 text-yellow-400 hover:bg-yellow-500/10 shrink-0">
                <Copy className="w-4 h-4" />
              </Button>
            )}
          </div>
        </div>

        {/* Instructions */}
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
          <h4 className="text-sm font-medium text-yellow-400 mb-2">Инструкция:</h4>
          <ol className="space-y-1 text-sm text-gray-300">
            {depositInfo?.instructions?.map((inst, i) => (
              <li key={i}>{inst}</li>
            ))}
          </ol>
        </div>

        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
          <p className="text-sm text-red-400">
            Без указания комментария депозит НЕ будет зачислен автоматически!
          </p>
        </div>
      </div>
    </div>
  );
}

// ==================== Withdraw Page ====================
function WithdrawPage() {
  const { token } = useAuth();
  const [wallet, setWallet] = useState(null);
  const [amount, setAmount] = useState("");
  const [address, setAddress] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);

  const WITHDRAWAL_FEE = 1.0;

  const fetchWallet = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/qr-provider/wallet`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setWallet(res.data);
    } catch (e) { toast.error("Ошибка загрузки баланса"); }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => { fetchWallet(); }, [fetchWallet]);

  const handleWithdraw = async () => {
    if (!amount || parseFloat(amount) <= 0) {
      toast.error("Укажите сумму");
      return;
    }
    if (!address || address.length < 48) {
      toast.error("Укажите корректный адрес кошелька");
      return;
    }

    setSubmitting(true);
    try {
      const res = await axios.post(`${API}/qr-provider/withdraw`, {
        amount: parseFloat(amount),
        to_address: address,
      }, { headers: { Authorization: `Bearer ${token}` } });

      toast.success(`Заявка создана! ID: ${res.data.request_id}`);
      setAmount("");
      setAddress("");
      fetchWallet();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Ошибка вывода");
    } finally { setSubmitting(false); }
  };

  if (loading) return <Spinner />;

  const available = wallet?.available_usdt || 0;
  const parsedAmount = parseFloat(amount) || 0;
  const total = parsedAmount + WITHDRAWAL_FEE;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-white">Вывод USDT</h2>

      <div className="bg-[#1A1A2E] border border-gray-700 rounded-lg p-6 space-y-4">
        {/* Balance info */}
        <div className="grid grid-cols-3 gap-4 text-center">
          <div className="p-3 bg-[#0D0D1A] rounded">
            <p className="text-xs text-gray-400">Баланс</p>
            <p className="text-lg font-bold text-white">{(wallet?.balance_usdt || 0).toFixed(2)} USDT</p>
          </div>
          <div className="p-3 bg-[#0D0D1A] rounded">
            <p className="text-xs text-gray-400">Доступно</p>
            <p className="text-lg font-bold text-green-400">{available.toFixed(2)} USDT</p>
          </div>
          <div className="p-3 bg-[#0D0D1A] rounded">
            <p className="text-xs text-gray-400">Заморожено</p>
            <p className="text-lg font-bold text-yellow-400">{(wallet?.frozen_usdt || 0).toFixed(2)} USDT</p>
          </div>
        </div>

        {/* Form */}
        <div>
          <label className="text-sm text-gray-400 mb-1 block">Сумма вывода (USDT):</label>
          <input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} step="0.01" min="1"
            placeholder="Например: 10.00"
            className="w-full bg-[#0D0D1A] border border-gray-600 rounded px-4 py-3 text-white text-lg" />
          {parsedAmount > 0 && (
            <p className="text-xs text-gray-400 mt-1">
              Комиссия: {WITHDRAWAL_FEE} USDT | Итого: {total.toFixed(2)} USDT
              {total > available && <span className="text-red-400 ml-2">(недостаточно средств)</span>}
            </p>
          )}
        </div>

        <div>
          <label className="text-sm text-gray-400 mb-1 block">Адрес кошелька (TON):</label>
          <input type="text" value={address} onChange={(e) => setAddress(e.target.value)}
            placeholder="UQ..."
            className="w-full bg-[#0D0D1A] border border-gray-600 rounded px-4 py-3 text-white font-mono text-sm" />
        </div>

        <Button onClick={handleWithdraw} disabled={submitting || total > available || parsedAmount <= 0}
          className="w-full bg-[#A855F7] hover:bg-[#9333EA] text-white py-3 text-lg disabled:opacity-50">
          {submitting ? <RefreshCw className="animate-spin w-5 h-5 mr-2" /> : <ArrowUpCircle className="w-5 h-5 mr-2" />}
          {submitting ? 'Отправка...' : `Вывести ${parsedAmount > 0 ? parsedAmount.toFixed(2) + ' USDT' : ''}`}
        </Button>

        <p className="text-xs text-gray-500 text-center">
          Вывод обрабатывается администрацией. Обычно до 24 часов.
        </p>
      </div>
    </div>
  );
}

// ==================== Shared Components ====================
function Spinner() {
  return <div className="flex justify-center p-8"><RefreshCw className="animate-spin w-6 h-6 text-gray-400" /></div>;
}

function StatCard({ label, value, sub, color, icon: Icon }) {
  const colors = {
    purple: "border-purple-500/30 bg-purple-500/10",
    green: "border-green-500/30 bg-green-500/10",
    blue: "border-blue-500/30 bg-blue-500/10",
    yellow: "border-yellow-500/30 bg-yellow-500/10",
    orange: "border-orange-500/30 bg-orange-500/10",
  };
  return (
    <div className={`rounded-lg border p-4 ${colors[color] || colors.purple}`}>
      <div className="flex items-center justify-between mb-1">
        <p className="text-xs text-gray-400 uppercase">{label}</p>
        {Icon && <Icon className="w-4 h-4 text-gray-500" />}
      </div>
      <p className="text-xl font-bold text-white">{value}</p>
      {sub && <p className="text-xs text-gray-500">{sub}</p>}
    </div>
  );
}
