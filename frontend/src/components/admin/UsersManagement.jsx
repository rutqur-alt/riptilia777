import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { 
  Users, Search, Filter, Ban, Lock, Unlock, DollarSign, Eye, Trash2,
  Key, UserCheck, UserX, XCircle, Briefcase, TrendingUp, Activity, Copy
} from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { Badge, LoadingSpinner, PageHeader } from "@/components/admin/SharedComponents";

// User Stats Modal Component
function UserStatsModal({ user, onClose }) {
  const { token } = useAuth();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
  }, [user.id]);

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API}/super-admin/users/${user.id}/stats`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setStats(response.data);
    } catch (error) {
      toast.error("Ошибка загрузки статистики");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
      <div className="bg-[#121212] border border-white/10 rounded-2xl w-full max-w-2xl max-h-[80vh] overflow-y-auto">
        <div className="p-4 border-b border-white/5 flex items-center justify-between sticky top-0 bg-[#121212]">
          <div>
            <h2 className="text-lg font-bold text-white">{stats?.user?.nickname || user.login}</h2>
            <div className="text-xs text-[#52525B]">@{stats?.user?.login} • {stats?.user_type === "trader" ? "Пользователь" : "Мерчант"}</div>
          </div>
          <button onClick={onClose} className="text-[#71717A] hover:text-white" title="Закрыть">
            <XCircle className="w-5 h-5" />
          </button>
        </div>

        {loading ? (
          <div className="p-8 text-center"><LoadingSpinner /></div>
        ) : stats && (
          <div className="p-4 space-y-4">
            {/* Balance */}
            <div className="bg-[#0A0A0A] rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[#71717A] text-sm">Баланс</span>
                {stats.user?.balance_locked && <Badge color="red">Заблокирован</Badge>}
              </div>
              <div className="text-2xl font-bold text-[#10B981] font-mono">{(stats.user?.balance_usdt || 0).toFixed(4)} USDT</div>
            </div>

            {/* Trading Stats */}
            {stats.trader && (
              <div className="bg-[#0A0A0A] rounded-xl p-4">
                <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-[#10B981]" /> Трейдинг
                </h3>
                <div className="grid grid-cols-4 gap-3">
                  <div className="text-center">
                    <div className="text-lg font-bold text-white">{stats.trader.total_trades}</div>
                    <div className="text-[10px] text-[#52525B]">Всего сделок</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-bold text-[#10B981]">{stats.trader.completed_trades}</div>
                    <div className="text-[10px] text-[#52525B]">Завершено</div>
                  </div>
                  <div className="text-center">
                    <div className="text-sm font-bold text-white font-mono">{stats.trader.volume_usdt}</div>
                    <div className="text-[10px] text-[#52525B]">Оборот USDT</div>
                  </div>
                  <div className="text-center">
                    <div className="text-sm font-bold text-white font-mono">{stats.trader.volume_rub?.toLocaleString()}</div>
                    <div className="text-[10px] text-[#52525B]">Оборот ₽</div>
                  </div>
                </div>
              </div>
            )}

            {/* Merchant Stats */}
            {stats.merchant && (
              <div className="bg-[#0A0A0A] rounded-xl p-4">
                <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                  <Briefcase className="w-4 h-4 text-[#3B82F6]" /> Мерчант
                </h3>
                <div className="grid grid-cols-3 gap-3">
                  <div className="text-center">
                    <div className="text-lg font-bold text-white">{stats.merchant.completed_payments}</div>
                    <div className="text-[10px] text-[#52525B]">Платежей</div>
                  </div>
                  <div className="text-center">
                    <div className="text-sm font-bold text-[#10B981] font-mono">{stats.merchant.volume_usdt}</div>
                    <div className="text-[10px] text-[#52525B]">Оборот USDT</div>
                  </div>
                  <div className="text-center">
                    <div className="text-sm font-bold text-white font-mono">{stats.merchant.volume_rub?.toLocaleString()}</div>
                    <div className="text-[10px] text-[#52525B]">Оборот ₽</div>
                  </div>
                </div>
              </div>
            )}

            {/* Referrals */}
            {stats.referrals && (
              <div className="bg-[#0A0A0A] rounded-xl p-4">
                <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                  <Users className="w-4 h-4 text-[#F59E0B]" /> Рефералы
                </h3>
                <div className="grid grid-cols-2 gap-3">
                  <div className="text-center">
                    <div className="text-lg font-bold text-white">{stats.referrals.total_referrals}</div>
                    <div className="text-[10px] text-[#52525B]">Приглашённых</div>
                  </div>
                  <div className="text-center">
                    <div className="text-sm font-bold text-[#10B981] font-mono">{(stats.referrals.referral_earnings || 0).toFixed(4)}</div>
                    <div className="text-[10px] text-[#52525B]">Заработано USDT</div>
                  </div>
                </div>
              </div>
            )}

            {/* Recent Trades */}
            {stats.recent_trades?.length > 0 && (
              <div className="bg-[#0A0A0A] rounded-xl p-4">
                <h3 className="text-sm font-semibold text-white mb-3">Последние сделки</h3>
                <div className="space-y-2 max-h-40 overflow-y-auto">
                  {stats.recent_trades.map(trade => (
                    <div key={trade.id} className="flex items-center justify-between text-xs p-2 bg-white/5 rounded-lg">
                      <div>
                        <span className="text-[#10B981] font-mono">{trade.amount_usdt} USDT</span>
                        <span className="text-[#52525B] mx-2">→</span>
                        <span className="text-white font-mono">{trade.amount_rub} ₽</span>
                      </div>
                      <Badge color={trade.status === "completed" ? "green" : trade.status === "cancelled" ? "gray" : "yellow"}>
                        {trade.status}
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function UsersManagement() {
  const { token, user } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [selectedUser, setSelectedUser] = useState(null);
  
  const isFullAdmin = user?.admin_role === "owner" || user?.admin_role === "admin";

  useEffect(() => { fetchUsers(); }, [filter]);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/super-admin/users?user_type=${filter}&limit=200`, 
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setUsers(response.data || []);
    } catch (error) {
      toast.error("Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  };

  const handleBan = async (userId, isBanned) => {
    const reason = isBanned ? "" : prompt("Причина блокировки:");
    if (!isBanned && !reason) return;
    
    try {
      await axios.post(`${API}/super-admin/users/${userId}/ban`,
        { banned: !isBanned, reason },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(isBanned ? "Разблокирован" : "Заблокирован");
      fetchUsers();
    } catch (error) {
      toast.error("Ошибка");
    }
  };

  const handleAdjustBalance = async (userId) => {
    const amount = prompt("Сумма (+/-):");
    if (!amount) return;
    const reason = prompt("Причина:");
    if (!reason) return;
    
    try {
      await axios.post(`${API}/super-admin/users/${userId}/balance`,
        { amount: parseFloat(amount), reason },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success("Баланс изменён");
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка");
    }
  };

  const handleResetPassword = async (userId) => {
    const newPassword = prompt("Новый пароль (минимум 6 символов):");
    if (!newPassword || newPassword.length < 6) {
      if (newPassword) toast.error("Пароль должен быть минимум 6 символов");
      return;
    }
    
    try {
      await axios.post(`${API}/super-admin/users/${userId}/reset-password`,
        { new_password: newPassword },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success("Пароль сброшен");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка");
    }
  };

  const handleToggleBalanceLock = async (userId, isLocked) => {
    try {
      await axios.post(`${API}/super-admin/users/${userId}/toggle-balance-lock`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(isLocked ? "Баланс разблокирован" : "Баланс заблокирован");
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка");
    }
  };

  const handleDeleteUser = async (userId, login) => {
    if (!window.confirm(`Удалить пользователя ${login} НАВСЕГДА? Это действие нельзя отменить!`)) return;
    if (!window.confirm("Вы уверены? Все данные пользователя будут удалены!")) return;
    
    try {
      await axios.delete(`${API}/super-admin/users/${userId}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success("Пользователь удалён");
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка удаления");
    }
  };

  const filteredUsers = users.filter(u => 
    !search || 
    u.login?.toLowerCase().includes(search.toLowerCase()) ||
    u.nickname?.toLowerCase().includes(search.toLowerCase()) ||
    u.merchant_name?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-4" data-testid="users-management">
      <PageHeader title="Пользователи" subtitle={`${users.length} пользователей`} icon={Users} />

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-[#52525B]" />
          <Input
            type="text"
            placeholder="Поиск..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 bg-[#0A0A0A] border-white/10 text-white text-sm h-9"
          />
        </div>
        <div className="flex gap-1.5">
          {[
            { value: "all", label: "Все" },
            { value: "traders", label: "Трейдеры" },
            { value: "merchants", label: "Мерчанты" },
            { value: "staff", label: "Персонал" }
          ].map(f => (
            <Button
              key={f.value}
              size="sm"
              onClick={() => setFilter(f.value)}
              className={`h-8 text-xs ${filter === f.value ? 'bg-[#A78BFA] hover:bg-[#8B5CF6] text-white' : 'bg-white/5 hover:bg-white/10 text-[#A1A1AA]'}`}
            >
              {f.label}
            </Button>
          ))}
        </div>
      </div>

      {/* Users Table */}
      {loading ? (
        <LoadingSpinner />
      ) : (
        <div className="bg-[#121212] border border-white/5 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[#0A0A0A] border-b border-white/5">
              <tr>
                <th className="text-left p-3 text-[#71717A] font-medium text-xs">ID</th>
                <th className="text-left p-3 text-[#71717A] font-medium text-xs">Пользователь</th>
                <th className="text-left p-3 text-[#71717A] font-medium text-xs">Тип</th>
                <th className="text-left p-3 text-[#71717A] font-medium text-xs">Баланс</th>
                <th className="text-left p-3 text-[#71717A] font-medium text-xs">Статус</th>
                <th className="text-right p-3 text-[#71717A] font-medium text-xs">Действия</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map((u) => (
                <tr key={u.id} className="border-b border-white/5 hover:bg-white/5">
                  <td className="p-3">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[10px] text-[#52525B]">{u.id?.slice(0, 8)}...</span>
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(u.id);
                          toast.success('ID скопирован');
                        }}
                        className="text-[#52525B] hover:text-[#10B981] transition-colors"
                        title="Скопировать полный ID"
                      >
                        <Copy className="w-3 h-3" />
                      </button>
                    </div>
                  </td>
                  <td className="p-3">
                    <div className="font-medium text-white">{u.nickname || u.merchant_name || u.login}</div>
                    <div className="text-[10px] text-[#52525B]">@{u.login}</div>
                  </td>
                  <td className="p-3">
                    <Badge color={u.user_type === "trader" ? "blue" : u.user_type === "merchant" ? "purple" : "yellow"}>
                      {u.user_type === "trader" ? "Трейдер" : u.user_type === "merchant" ? "Мерчант" : "Персонал"}
                    </Badge>
                  </td>
                  <td className="p-3">
                    <span className="text-[#10B981] font-mono text-xs">{(u.balance_usdt || 0).toFixed(2)}</span>
                    {u.balance_locked && <Lock className="w-3 h-3 text-[#EF4444] ml-1 inline" />}
                  </td>
                  <td className="p-3">
                    <Badge color={u.is_blocked || u.status === "blocked" ? "red" : "green"}>
                      {u.is_blocked || u.status === "blocked" ? "Заблокирован" : "Активен"}
                    </Badge>
                  </td>
                  <td className="p-3">
                    <div className="flex gap-1 justify-end">
                      <Button
                        size="sm"
                        onClick={() => setSelectedUser(u)}
                        className="h-7 w-7 p-0 bg-white/5 hover:bg-white/10 text-[#A1A1AA]"
                        title="Статистика"
                      >
                        <Eye className="w-3.5 h-3.5" />
                      </Button>
                      {isFullAdmin && (
                        <>
                          <Button
                            size="sm"
                            onClick={() => handleBan(u.id, u.is_blocked || u.status === "blocked")}
                            className={`h-7 w-7 p-0 ${u.is_blocked || u.status === "blocked" ? 'bg-[#10B981]/20 hover:bg-[#10B981]/30 text-[#10B981]' : 'bg-[#EF4444]/20 hover:bg-[#EF4444]/30 text-[#EF4444]'}`}
                            title={u.is_blocked || u.status === "blocked" ? "Разблокировать" : "Заблокировать"}
                          >
                            {u.is_blocked || u.status === "blocked" ? <UserCheck className="w-3.5 h-3.5" /> : <UserX className="w-3.5 h-3.5" />}
                          </Button>
                          <Button
                            size="sm"
                            onClick={() => handleAdjustBalance(u.id)}
                            className="h-7 w-7 p-0 bg-[#10B981]/20 hover:bg-[#10B981]/30 text-[#10B981]"
                            title="Изменить баланс"
                          >
                            <DollarSign className="w-3.5 h-3.5" />
                          </Button>
                          <Button
                            size="sm"
                            onClick={() => handleToggleBalanceLock(u.id, u.balance_locked)}
                            className={`h-7 w-7 p-0 ${u.balance_locked ? 'bg-[#F59E0B]/20 hover:bg-[#F59E0B]/30 text-[#F59E0B]' : 'bg-white/5 hover:bg-white/10 text-[#71717A]'}`}
                            title={u.balance_locked ? "Разблокировать баланс" : "Заблокировать баланс"}
                          >
                            {u.balance_locked ? <Unlock className="w-3.5 h-3.5" /> : <Lock className="w-3.5 h-3.5" />}
                          </Button>
                          <Button
                            size="sm"
                            onClick={() => handleResetPassword(u.id)}
                            className="h-7 w-7 p-0 bg-white/5 hover:bg-white/10 text-[#71717A]"
                            title="Сбросить пароль"
                          >
                            <Key className="w-3.5 h-3.5" />
                          </Button>
                          <Button
                            size="sm"
                            onClick={() => handleDeleteUser(u.id, u.login)}
                            className="h-7 w-7 p-0 bg-[#EF4444]/10 hover:bg-[#EF4444]/20 text-[#52525B] hover:text-[#EF4444]"
                            title="Удалить">
                            <Trash2 className="w-3.5 h-3.5" />
                          </Button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedUser && (
        <UserStatsModal user={selectedUser} onClose={() => setSelectedUser(null)} />
      )}
    </div>
  );
}
