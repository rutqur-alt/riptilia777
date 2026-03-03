import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import DashboardLayout from '@/components/DashboardLayout';
import { api, formatDate, useAuth } from '@/lib/auth';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { 
  MessageCircle, Send, ArrowLeft, Plus, Inbox, Clock, 
  CheckCircle, User, Shield, X, UserPlus, Users, Trash2
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

// Список тикетов
const TicketsList = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showNewTicket, setShowNewTicket] = useState(false);
  const [newTicket, setNewTicket] = useState({ subject: '', message: '' });
  const [creating, setCreating] = useState(false);

  // Pending трейдер или мерчант не могут создавать новые тикеты
  const canCreateTicket = !((user?.role === 'trader' || user?.role === 'merchant') && user?.approval_status === 'pending');

  useEffect(() => {
    fetchTickets();
  }, []);

  const fetchTickets = async () => {
    try {
      const res = await api.get('/tickets');
      setTickets(res.data.tickets);
    } catch (error) {
      const message = error.response?.data?.detail || error.message || 'Ошибка загрузки тикетов';
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  const createTicket = async (e) => {
    e.preventDefault();
    if (!newTicket.subject.trim() || !newTicket.message.trim()) {
      toast.error('Заполните все поля');
      return;
    }

    setCreating(true);
    try {
      const res = await api.post('/tickets', newTicket);
      toast.success('Тикет создан');
      setShowNewTicket(false);
      setNewTicket({ subject: '', message: '' });
      // API возвращает ticket.id внутри объекта ticket
      const ticketId = res.data.ticket?.id || res.data.ticket_id;
      if (ticketId) {
        navigate(`/support/${ticketId}`);
      } else {
        fetchTickets();
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка создания');
    } finally {
      setCreating(false);
    }
  };

  const getStatusBadge = (ticket) => {
    const hasUnread = ticket.unread_by_user > 0;
    
    if (ticket.status === 'open') {
      return (
        <div className="flex items-center gap-2">
          {hasUnread && (
            <span className="px-2 py-1 bg-red-500 text-white rounded text-xs font-bold">
              {ticket.unread_by_user}
            </span>
          )}
          <span className="px-2 py-1 bg-emerald-500/20 text-emerald-400 rounded text-xs">
            Открыт
          </span>
        </div>
      );
    }
    return (
      <span className="px-2 py-1 bg-zinc-700 text-zinc-400 rounded text-xs">
        Закрыт
      </span>
    );
  };

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
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold font-['Chivo']">Поддержка</h1>
            <p className="text-zinc-400 text-sm">Связь с администрацией</p>
          </div>
          {canCreateTicket && (
            <Dialog open={showNewTicket} onOpenChange={setShowNewTicket}>
              <DialogTrigger asChild>
                <Button className="bg-emerald-500 hover:bg-emerald-600">
                  <Plus className="w-4 h-4 mr-2" />
                  Новый тикет
                </Button>
              </DialogTrigger>
              <DialogContent className="bg-zinc-900 border-zinc-800">
                <DialogHeader>
                  <DialogTitle>Создать тикет</DialogTitle>
                </DialogHeader>
                <form onSubmit={createTicket} className="space-y-4">
                  <div>
                    <Label>Тема</Label>
                    <Input
                      value={newTicket.subject}
                    onChange={(e) => setNewTicket({ ...newTicket, subject: e.target.value })}
                    placeholder="Кратко опишите проблему"
                    className="bg-zinc-800 border-zinc-700"
                  />
                </div>
                <div>
                  <Label>Сообщение</Label>
                  <Textarea
                    value={newTicket.message}
                    onChange={(e) => setNewTicket({ ...newTicket, message: e.target.value })}
                    placeholder="Опишите подробно..."
                    className="bg-zinc-800 border-zinc-700 min-h-[120px]"
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <Button type="button" variant="outline" onClick={() => setShowNewTicket(false)}>
                    Отмена
                  </Button>
                  <Button type="submit" disabled={creating} className="bg-emerald-500 hover:bg-emerald-600">
                    {creating ? 'Создание...' : 'Создать'}
                  </Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
          )}
        </div>

        {/* Pending trader info */}
        {!canCreateTicket && (
          <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-4 mb-6">
            <p className="text-orange-400 text-sm">
              Вы можете использовать только тикет заявки на регистрацию. После одобрения появится возможность создавать новые обращения.
            </p>
          </div>
        )}

        {/* Tickets List */}
        {tickets.length === 0 ? (
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="p-12 text-center">
              <Inbox className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
              <h3 className="text-lg font-medium mb-2">Нет тикетов</h3>
              <p className="text-zinc-400 text-sm mb-4">
                Создайте тикет чтобы связаться с поддержкой
              </p>
              <Button onClick={() => setShowNewTicket(true)} className="bg-emerald-500 hover:bg-emerald-600">
                <Plus className="w-4 h-4 mr-2" />
                Создать тикет
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {tickets.map((ticket) => (
              <Link key={ticket.id} to={`/support/${ticket.id}`}>
                <Card className="bg-zinc-900 border-zinc-800 hover:border-zinc-700 transition-colors cursor-pointer">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                          ticket.status === 'open' ? 'bg-emerald-500/20' : 'bg-zinc-800'
                        }`}>
                          <MessageCircle className={`w-5 h-5 ${
                            ticket.status === 'open' ? 'text-emerald-400' : 'text-zinc-500'
                          }`} />
                        </div>
                        <div>
                          <h3 className="font-medium">{ticket.subject}</h3>
                          <p className="text-sm text-zinc-500">
                            #{ticket.id.split('_').pop()} • {formatDate(ticket.created_at)}
                          </p>
                        </div>
                      </div>
                      {getStatusBadge(ticket)}
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
};

// Чат тикета
const TicketChat = () => {
  const { ticketId } = useParams();
  const { user } = useAuth();
  const [ticket, setTicket] = useState(null);
  const [ticketUser, setTicketUser] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef(null);
  
  // Новые состояния для назначения сотрудников
  const [assignedStaff, setAssignedStaff] = useState([]);
  const [allStaff, setAllStaff] = useState([]);
  const [showAssignDialog, setShowAssignDialog] = useState(false);
  const [selectedStaff, setSelectedStaff] = useState('');
  const [assigning, setAssigning] = useState(false);

  const isStaff = user?.role === 'admin' || user?.role === 'support';

  useEffect(() => {
    fetchTicket();
    markAsRead();
    if (isStaff) {
      fetchAllStaff();
    }
    const interval = setInterval(fetchTicket, 5000);
    return () => clearInterval(interval);
  }, [ticketId]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const fetchTicket = async () => {
    try {
      const res = await api.get(`/tickets/${ticketId}`);
      setTicket(res.data.ticket);
      setMessages(res.data.messages);
      setTicketUser(res.data.user);
      setAssignedStaff(res.data.assigned_staff || []);
    } catch (error) {
      const message = error.response?.data?.detail || error.message || 'Ошибка загрузки тикета';
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  const fetchAllStaff = async () => {
    try {
      const res = await api.get('/admin/staff');
      setAllStaff(res.data.staff || []);
    } catch (error) {
      console.error('Error fetching staff:', error);
    }
  };

  const markAsRead = async () => {
    try {
      await api.post(`/tickets/${ticketId}/mark-read`);
    } catch (error) {
      console.error('Error marking as read:', error);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!newMessage.trim()) return;

    setSending(true);
    try {
      await api.post(`/tickets/${ticketId}/reply`, { message: newMessage });
      setNewMessage('');
      fetchTicket();
    } catch (error) {
      const message = error.response?.data?.detail || error.message || 'Ошибка отправки';
      toast.error(message);
    } finally {
      setSending(false);
    }
  };

  const closeTicket = async () => {
    try {
      await api.post(`/tickets/${ticketId}/close`);
      toast.success('Тикет закрыт');
      fetchTicket();
    } catch (error) {
      const message = error.response?.data?.detail || error.message || 'Ошибка закрытия тикета';
      toast.error(message);
    }
  };

  const assignStaff = async () => {
    if (!selectedStaff) {
      toast.error('Выберите сотрудника');
      return;
    }
    
    setAssigning(true);
    try {
      await api.post(`/tickets/${ticketId}/assign`, { staff_id: selectedStaff });
      toast.success('Сотрудник добавлен к тикету');
      setShowAssignDialog(false);
      setSelectedStaff('');
      fetchTicket();
    } catch (error) {
      const message = error.response?.data?.detail || error.message || 'Ошибка назначения';
      toast.error(message);
    } finally {
      setAssigning(false);
    }
  };

  const unassignStaff = async (staffId) => {
    try {
      await api.delete(`/tickets/${ticketId}/assign/${staffId}`);
      toast.success('Сотрудник удалён из тикета');
      fetchTicket();
    } catch (error) {
      const message = error.response?.data?.detail || error.message || 'Ошибка удаления';
      toast.error(message);
    }
  };

  // Фильтруем сотрудников которые ещё не назначены
  const availableStaff = allStaff.filter(
    s => !assignedStaff.some(as => as.id === s.id)
  );

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-[60vh]">
          <div className="animate-spin w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full" />
        </div>
      </DashboardLayout>
    );
  }

  const backLink = isStaff ? '/admin/tickets' : '/support';

  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <Link to={backLink}>
              <Button variant="outline" size="icon" className="border-zinc-800">
                <ArrowLeft className="w-4 h-4" />
              </Button>
            </Link>
            <div>
              <h1 className="text-xl font-bold font-['Chivo']">{ticket?.subject}</h1>
              <p className="text-sm text-zinc-400">
                #{ticketId?.split('_').pop()} 
                {ticketUser && isStaff && ` • ${ticketUser.nickname || ticketUser.login}`}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Кнопка назначения сотрудника */}
            {isStaff && ticket?.status === 'open' && (
              <Dialog open={showAssignDialog} onOpenChange={setShowAssignDialog}>
                <DialogTrigger asChild>
                  <Button variant="outline" className="border-zinc-700">
                    <UserPlus className="w-4 h-4 mr-2" />
                    Добавить
                  </Button>
                </DialogTrigger>
                <DialogContent className="bg-zinc-900 border-zinc-800">
                  <DialogHeader>
                    <DialogTitle>Добавить сотрудника к тикету</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4">
                    <div>
                      <Label>Выберите сотрудника</Label>
                      <Select value={selectedStaff} onValueChange={setSelectedStaff}>
                        <SelectTrigger className="bg-zinc-800 border-zinc-700">
                          <SelectValue placeholder="Выберите сотрудника..." />
                        </SelectTrigger>
                        <SelectContent className="bg-zinc-900 border-zinc-800">
                          {availableStaff.map(s => (
                            <SelectItem key={s.id} value={s.id}>
                              {s.nickname || s.login} ({s.role === 'admin' ? 'Админ' : 'Поддержка'})
                            </SelectItem>
                          ))}
                          {availableStaff.length === 0 && (
                            <SelectItem value="_empty" disabled>
                              Все сотрудники уже назначены
                            </SelectItem>
                          )}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex justify-end gap-2">
                      <Button variant="outline" onClick={() => setShowAssignDialog(false)}>
                        Отмена
                      </Button>
                      <Button 
                        onClick={assignStaff} 
                        disabled={assigning || !selectedStaff}
                        className="bg-emerald-500 hover:bg-emerald-600"
                      >
                        {assigning ? 'Добавление...' : 'Добавить'}
                      </Button>
                    </div>
                  </div>
                </DialogContent>
              </Dialog>
            )}
            {isStaff && ticket?.status === 'open' && (
              <Button variant="outline" onClick={closeTicket} className="border-zinc-700">
                <X className="w-4 h-4 mr-2" />
                Закрыть
              </Button>
            )}
          </div>
        </div>

        {/* Назначенные сотрудники */}
        {isStaff && assignedStaff.length > 0 && (
          <Card className="bg-zinc-900/50 border-zinc-800 mb-4">
            <CardContent className="p-3">
              <div className="flex items-center gap-2 flex-wrap">
                <Users className="w-4 h-4 text-zinc-500" />
                <span className="text-sm text-zinc-400">Работают над тикетом:</span>
                {assignedStaff.map(s => (
                  <Badge 
                    key={s.id} 
                    variant="outline" 
                    className={`${s.role === 'admin' ? 'border-purple-500/50 text-purple-400' : 'border-blue-500/50 text-blue-400'} flex items-center gap-1`}
                  >
                    {s.nickname || s.login}
                    <button 
                      onClick={() => unassignStaff(s.id)}
                      className="ml-1 hover:text-red-400 transition-colors"
                      title="Удалить из тикета"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Chat */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-0">
            {/* Messages */}
            <div className="h-[400px] overflow-y-auto p-4 space-y-4">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.sender_id === user?.id ? 'justify-end' : 'justify-start'}`}
                >
                  <div className={`max-w-[70%] rounded-lg p-3 border ${
                    msg.sender_role === 'admin' || msg.sender_role === 'support'
                      ? 'bg-purple-500/20 border-purple-500/50' 
                      : 'bg-zinc-800 border-zinc-700'
                  }`}>
                    <div className="flex items-center gap-2 mb-1">
                      {(msg.sender_role === 'admin' || msg.sender_role === 'support') ? (
                        <Shield className="w-4 h-4 text-purple-400" />
                      ) : (
                        <User className="w-4 h-4 text-zinc-400" />
                      )}
                      <span className="text-xs font-medium">
                        {(msg.sender_role === 'admin' || msg.sender_role === 'support') 
                          ? (msg.sender_nickname || msg.sender_login || 'Администрация')
                          : (msg.sender_id === user?.id ? 'Вы' : (msg.sender_nickname || msg.sender_login))
                        }
                      </span>
                      {(msg.sender_role === 'admin' || msg.sender_role === 'support') && (
                        <span className="text-xs text-purple-400/60">
                          ({msg.sender_role === 'admin' ? 'админ' : 'поддержка'})
                        </span>
                      )}
                      <span className="text-xs text-zinc-500">
                        {new Date(msg.created_at).toLocaleTimeString('ru-RU', { 
                          hour: '2-digit', 
                          minute: '2-digit' 
                        })}
                      </span>
                    </div>
                    <p className="text-sm whitespace-pre-wrap">{msg.message || msg.text}</p>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            {ticket?.status === 'open' ? (
              <form onSubmit={sendMessage} className="p-4 border-t border-zinc-800">
                <div className="flex gap-2">
                  <Input
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    placeholder="Введите сообщение..."
                    className="flex-1 bg-zinc-800 border-zinc-700"
                    disabled={sending}
                  />
                  <Button 
                    type="submit" 
                    disabled={sending || !newMessage.trim()}
                    className="bg-emerald-500 hover:bg-emerald-600"
                  >
                    <Send className="w-4 h-4" />
                  </Button>
                </div>
              </form>
            ) : (
              <div className="p-4 border-t border-zinc-800 text-center text-zinc-500">
                <CheckCircle className="w-5 h-5 inline-block mr-2 text-emerald-400" />
                Тикет закрыт
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
};

export { TicketsList, TicketChat };
