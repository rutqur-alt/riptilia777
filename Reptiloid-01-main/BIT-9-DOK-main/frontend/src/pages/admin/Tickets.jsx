import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import DashboardLayout from '@/components/DashboardLayout';
import { api, formatDate } from '@/lib/auth';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { 
  MessageCircle, Plus, Inbox, Search, Mail, RefreshCw,
  Users, Building2, UserCheck, Bell, Trash2
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const AdminTickets = () => {
  const navigate = useNavigate();
  const [tickets, setTickets] = useState([]);
  const [users, setUsers] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [showNewTicket, setShowNewTicket] = useState(false);
  const [newTicket, setNewTicket] = useState({ subject: '', message: '', user_id: '' });
  const [creating, setCreating] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState('all'); // all, trader, merchant, approval

  useEffect(() => {
    fetchData();
  }, [activeFilter]);

  const fetchData = async () => {
    setLoading(true);
    try {
      // Формируем параметры запроса
      const params = {};
      if (activeFilter === 'trader') params.filter_role = 'trader';
      if (activeFilter === 'merchant') params.filter_role = 'merchant';
      if (activeFilter === 'approval') params.filter_type = 'approval';  // trader_approval или merchant_approval
      
      const [ticketsRes, statsRes, usersRes] = await Promise.all([
        api.get('/tickets', { params }),
        api.get('/admin/tickets/stats'),
        api.get('/admin/users')
      ]);
      
      setTickets(ticketsRes.data.tickets || []);
      setStats(statsRes.data || {});
      setUsers(usersRes.data.users?.filter(u => u.role !== 'admin') || []);
    } catch (error) {
      toast.error('Ошибка загрузки');
    } finally {
      setLoading(false);
    }
  };

  const deleteTicket = async (ticketId) => {
    if (!window.confirm('Удалить этот тикет?')) return;
    
    try {
      await api.delete(`/tickets/${ticketId}`);
      toast.success('Тикет удалён');
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка удаления');
    }
  };

  // Сортируем тикеты: непрочитанные вверху, потом по дате
  const sortedTickets = [...tickets].sort((a, b) => {
    // Сначала непрочитанные
    if ((a.unread_by_admin > 0) !== (b.unread_by_admin > 0)) {
      return a.unread_by_admin > 0 ? -1 : 1;
    }
    // Потом по дате (новые вверху)
    return new Date(b.updated_at || b.created_at) - new Date(a.updated_at || a.created_at);
  });

  const createTicket = async (e) => {
    e.preventDefault();
    if (!newTicket.subject.trim() || !newTicket.message.trim() || !newTicket.user_id) {
      toast.error('Заполните все поля');
      return;
    }

    setCreating(true);
    try {
      const res = await api.post('/tickets', newTicket);
      toast.success('Сообщение отправлено пользователю');
      setShowNewTicket(false);
      setNewTicket({ subject: '', message: '', user_id: '' });
      navigate(`/support/${res.data.ticket_id}`);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка создания');
    } finally {
      setCreating(false);
    }
  };

  const getStatusBadge = (ticket) => {
    const hasUnread = ticket.unread_by_admin > 0;
    
    if (ticket.status === 'closed') {
      return (
        <Badge variant="outline" className="bg-zinc-800 text-zinc-400 border-zinc-700">
          Закрыт
        </Badge>
      );
    }
    
    return (
      <div className="flex items-center gap-2">
        {hasUnread && (
          <Badge className="bg-red-500 text-white">
            {ticket.unread_by_admin}
          </Badge>
        )}
        <Badge variant="outline" className="bg-emerald-500/20 text-emerald-400 border-emerald-500/50">
          Открыт
        </Badge>
      </div>
    );
  };

  const getRoleBadge = (role) => {
    const badges = {
      trader: { bg: 'bg-blue-500/20', text: 'text-blue-400', label: 'Трейдер' },
      merchant: { bg: 'bg-purple-500/20', text: 'text-purple-400', label: 'Мерчант' },
    };
    const b = badges[role] || { bg: 'bg-zinc-500/20', text: 'text-zinc-400', label: role };
    return (
      <span className={`px-2 py-0.5 rounded text-xs ${b.bg} ${b.text}`}>
        {b.label}
      </span>
    );
  };

  const filteredTickets = sortedTickets.filter(t => {
    if (!searchQuery) return true;
    return (
      t.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (t.user_login && t.user_login.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (t.user_nickname && t.user_nickname.toLowerCase().includes(searchQuery.toLowerCase()))
    );
  });

  const filterTabs = [
    { id: 'all', label: 'Все', icon: Inbox, count: tickets.length },
    { id: 'approval', label: 'Заявки', icon: UserCheck, count: stats.approval_tickets || 0 },
    { id: 'trader', label: 'Трейдеры', icon: Users, count: stats.trader_tickets || 0 },
    { id: 'merchant', label: 'Мерчанты', icon: Building2, count: stats.merchant_tickets || 0 },
  ];

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-[60vh]">
          <div className="animate-spin w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full" />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold font-['Chivo'] flex items-center gap-2">
              Тикеты
              {stats.unread_total > 0 && (
                <Badge className="bg-red-500 text-white">
                  <Bell className="w-3 h-3 mr-1" />
                  {stats.unread_total} новых
                </Badge>
              )}
            </h1>
            <p className="text-zinc-400 text-sm">Управление обращениями пользователей</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={fetchData} className="border-zinc-800">
              <RefreshCw className="w-4 h-4" />
            </Button>
            <Dialog open={showNewTicket} onOpenChange={setShowNewTicket}>
              <DialogTrigger asChild>
                <Button className="bg-emerald-500 hover:bg-emerald-600">
                  <Mail className="w-4 h-4 mr-2" />
                  Написать
                </Button>
              </DialogTrigger>
              <DialogContent className="bg-zinc-900 border-zinc-800">
                <DialogHeader>
                  <DialogTitle>Написать пользователю</DialogTitle>
                </DialogHeader>
                <form onSubmit={createTicket} className="space-y-4">
                  <div>
                    <Label>Пользователь</Label>
                    <Select 
                      value={newTicket.user_id} 
                      onValueChange={(value) => setNewTicket({ ...newTicket, user_id: value })}
                    >
                      <SelectTrigger className="bg-zinc-800 border-zinc-700">
                        <SelectValue placeholder="Выберите пользователя" />
                      </SelectTrigger>
                      <SelectContent className="bg-zinc-900 border-zinc-800 max-h-60">
                        {users.map((user) => (
                          <SelectItem key={user.id} value={user.id}>
                            {user.nickname || user.login} (@{user.login}) - {user.role}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>Тема</Label>
                    <Input
                      value={newTicket.subject}
                      onChange={(e) => setNewTicket({ ...newTicket, subject: e.target.value })}
                      placeholder="Тема сообщения"
                      className="bg-zinc-800 border-zinc-700"
                    />
                  </div>
                  <div>
                    <Label>Сообщение</Label>
                    <Textarea
                      value={newTicket.message}
                      onChange={(e) => setNewTicket({ ...newTicket, message: e.target.value })}
                      placeholder="Текст сообщения..."
                      className="bg-zinc-800 border-zinc-700 min-h-[120px]"
                    />
                  </div>
                  <div className="flex justify-end gap-2">
                    <Button type="button" variant="outline" onClick={() => setShowNewTicket(false)}>
                      Отмена
                    </Button>
                    <Button type="submit" disabled={creating} className="bg-emerald-500 hover:bg-emerald-600">
                      {creating ? 'Отправка...' : 'Отправить'}
                    </Button>
                  </div>
                </form>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* Filter Tabs */}
        <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
          {filterTabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeFilter === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveFilter(tab.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg whitespace-nowrap transition-colors ${
                  isActive 
                    ? 'bg-emerald-500 text-white' 
                    : 'bg-zinc-900 text-zinc-400 hover:bg-zinc-800'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
                {tab.count > 0 && (
                  <span className={`px-1.5 py-0.5 rounded text-xs ${
                    isActive ? 'bg-white/20' : 'bg-zinc-800'
                  }`}>
                    {tab.count}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Search */}
        <div className="relative mb-6">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Поиск по теме, ID или логину..."
            className="pl-10 bg-zinc-900 border-zinc-800"
          />
        </div>

        {/* Tickets List */}
        {filteredTickets.length === 0 ? (
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="p-12 text-center">
              <Inbox className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
              <h3 className="text-lg font-medium mb-2">Нет тикетов</h3>
              <p className="text-zinc-400 text-sm">
                {searchQuery ? 'По вашему запросу ничего не найдено' : 'Тикеты от пользователей появятся здесь'}
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {filteredTickets.map((ticket) => (
              <div key={ticket.id} className="relative group">
                <Link to={`/support/${ticket.id}`}>
                  <Card className={`bg-zinc-900 border-zinc-800 hover:border-zinc-700 transition-colors cursor-pointer ${
                    ticket.unread_by_admin > 0 ? 'border-l-4 border-l-red-500' : ''
                  }`}>
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                            (ticket.type === 'trader_approval' || ticket.type === 'merchant_approval')
                              ? 'bg-orange-500/20' 
                              : ticket.status === 'open' 
                                ? 'bg-emerald-500/20' 
                                : 'bg-zinc-800'
                          }`}>
                            {(ticket.type === 'trader_approval' || ticket.type === 'merchant_approval') ? (
                              <UserCheck className="w-5 h-5 text-orange-400" />
                            ) : (
                              <MessageCircle className={`w-5 h-5 ${
                                ticket.status === 'open' ? 'text-emerald-400' : 'text-zinc-500'
                              }`} />
                            )}
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <h3 className="font-medium">
                                {(ticket.type === 'trader_approval' || ticket.type === 'merchant_approval') 
                                  ? `Заявка: ${ticket.user_nickname || ticket.user_login}`
                                  : ticket.subject || 'Без темы'}
                              </h3>
                              {(ticket.type === 'trader_approval' || ticket.type === 'merchant_approval') && (
                                <Badge variant="outline" className="bg-orange-500/20 text-orange-400 border-orange-500/50 text-xs">
                                  {ticket.type === 'trader_approval' ? 'Трейдер' : 'Мерчант'}
                                </Badge>
                              )}
                            </div>
                            <div className="flex items-center gap-2 text-sm text-zinc-500">
                              <span>{ticket.user_nickname || ticket.user_login || 'Unknown'}</span>
                              {ticket.user_login && <span className="text-zinc-600">@{ticket.user_login}</span>}
                              {ticket.user_role && getRoleBadge(ticket.user_role)}
                              <span className="text-zinc-700">•</span>
                              <span className="font-['JetBrains_Mono'] text-xs">#{ticket.id.split('_').pop()}</span>
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-xs text-zinc-500">
                            {formatDate(ticket.updated_at)}
                          </span>
                          {getStatusBadge(ticket)}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
                {/* Delete button */}
                <button
                  onClick={(e) => { e.preventDefault(); deleteTicket(ticket.id); }}
                  className="absolute top-2 right-2 p-2 rounded-lg bg-red-500/10 text-red-400 opacity-0 group-hover:opacity-100 hover:bg-red-500/20 transition-all"
                  title="Удалить тикет"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
};

export default AdminTickets;
