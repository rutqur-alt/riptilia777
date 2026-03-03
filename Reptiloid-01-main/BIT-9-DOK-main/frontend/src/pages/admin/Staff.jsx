import React, { useState, useEffect } from 'react';
import DashboardLayout from '@/components/DashboardLayout';
import { api, formatDate } from '@/lib/auth';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { 
  RefreshCw, Shield, UserPlus, Settings, CheckCircle, XCircle,
  Users, FileText, Scale, DollarSign, MessageSquare, Trash2, Ban, UserCheck
} from 'lucide-react';

// Список всех возможных прав
const ALL_PERMISSIONS = [
  { key: 'approve_traders', label: 'Одобрение трейдеров', icon: UserCheck, description: 'Подтверждение заявок на регистрацию трейдеров' },
  { key: 'block_users', label: 'Блокировка пользователей', icon: Ban, description: 'Блокировка/разблокировка пользователей' },
  { key: 'delete_users', label: 'Удаление пользователей', icon: Trash2, description: 'Полное удаление пользователей из системы' },
  { key: 'view_orders', label: 'Просмотр ордеров', icon: FileText, description: 'Доступ к списку всех ордеров' },
  { key: 'manage_disputes', label: 'Управление спорами', icon: Scale, description: 'Разрешение споров между трейдерами и покупателями' },
  { key: 'view_accounting', label: 'Просмотр бухгалтерии', icon: DollarSign, description: 'Доступ к финансовой статистике и отчётам' },
  { key: 'manage_rates', label: 'Управление курсами', icon: DollarSign, description: 'Изменение курсов валют' },
  { key: 'create_admins', label: 'Создание администраторов', icon: Shield, description: 'Добавление новых админов и саппортов' },
  { key: 'manage_tickets', label: 'Управление тикетами', icon: MessageSquare, description: 'Работа с обращениями пользователей' },
];

// Права по умолчанию для ролей
const DEFAULT_PERMISSIONS = {
  admin: {
    approve_traders: true,
    block_users: true,
    delete_users: true,
    view_orders: true,
    manage_disputes: true,
    view_accounting: true,
    manage_rates: true,
    create_admins: true,
    manage_tickets: true
  },
  support: {
    approve_traders: true,
    block_users: true,
    delete_users: false,
    view_orders: true,
    manage_disputes: true,
    view_accounting: false,
    manage_rates: false,
    create_admins: false,
    manage_tickets: true
  }
};

const AdminStaff = () => {
  const [staff, setStaff] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editDialog, setEditDialog] = useState(null);
  const [processing, setProcessing] = useState(false);

  // Form state for new user
  const [newEmail, setNewEmail] = useState('');
  const [newNickname, setNewNickname] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState('support');
  const [newPermissions, setNewPermissions] = useState(DEFAULT_PERMISSIONS.support);

  // Edit permissions state
  const [editPermissions, setEditPermissions] = useState({});

  useEffect(() => {
    fetchStaff();
  }, []);

  const fetchStaff = async () => {
    try {
      const res = await api.get('/admin/staff');
      setStaff(res.data.staff || []);
    } catch (error) {
      toast.error('Ошибка загрузки');
    } finally {
      setLoading(false);
    }
  };

  const handleRoleChange = (role) => {
    setNewRole(role);
    setNewPermissions(DEFAULT_PERMISSIONS[role] || {});
  };

  const toggleNewPermission = (key) => {
    setNewPermissions(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const toggleEditPermission = (key) => {
    setEditPermissions(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const createStaff = async () => {
    if (!newEmail || !newPassword || !newNickname) {
      toast.error('Заполните все поля');
      return;
    }

    setProcessing(true);
    try {
      await api.post('/admin/staff', {
        login: newEmail,
        nickname: newNickname,
        password: newPassword,
        role: newRole,
        permissions: newPermissions
      });
      toast.success(`${newRole === 'admin' ? 'Администратор' : 'Саппорт'} создан`);
      setCreateDialogOpen(false);
      resetForm();
      fetchStaff();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка создания');
    } finally {
      setProcessing(false);
    }
  };

  const updatePermissions = async () => {
    setProcessing(true);
    try {
      await api.put(`/admin/users/${editDialog.id}/permissions`, editPermissions);
      toast.success('Права обновлены');
      setEditDialog(null);
      fetchStaff();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка обновления');
    } finally {
      setProcessing(false);
    }
  };

  const openEditDialog = (user) => {
    setEditDialog(user);
    setEditPermissions(user.permissions || DEFAULT_PERMISSIONS[user.role] || {});
  };

  const resetForm = () => {
    setNewEmail('');
    setNewNickname('');
    setNewPassword('');
    setNewRole('support');
    setNewPermissions(DEFAULT_PERMISSIONS.support);
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
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold font-['Chivo'] flex items-center gap-2">
              <Shield className="w-6 h-6 text-emerald-400" />
              Управление персоналом
            </h1>
            <p className="text-zinc-400 text-sm">Администраторы и саппорты: {staff.length}</p>
          </div>
          <div className="flex gap-2">
            <Button onClick={() => setCreateDialogOpen(true)} className="bg-emerald-500 hover:bg-emerald-600">
              <UserPlus className="w-4 h-4 mr-2" />
              Добавить
            </Button>
            <Button variant="outline" onClick={fetchStaff} className="border-zinc-800">
              <RefreshCw className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Staff List */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {staff.map((user) => (
            <Card key={user.id} className="bg-zinc-900 border-zinc-800">
              <CardContent className="p-5">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium">{user.nickname || user.login}</span>
                      <Badge className={user.role === 'admin' ? 'bg-red-500/20 text-red-400' : 'bg-orange-500/20 text-orange-400'}>
                        {user.role === 'admin' ? 'Админ' : 'Саппорт'}
                      </Badge>
                    </div>
                    <div className="text-sm text-zinc-400">@{user.login}</div>
                    <div className="text-xs text-zinc-500 font-['JetBrains_Mono'] mt-1">
                      ID: {user.id}
                    </div>
                    <div className="text-sm text-zinc-400 mt-1">
                      Создан: {formatDate(user.created_at)}
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => openEditDialog(user)}
                    className="border-zinc-700"
                  >
                    <Settings className="w-4 h-4 mr-1" />
                    Права
                  </Button>
                </div>

                {/* Permissions Summary */}
                <div className="flex flex-wrap gap-2">
                  {ALL_PERMISSIONS.map(perm => {
                    const hasPermission = user.permissions?.[perm.key] ?? DEFAULT_PERMISSIONS[user.role]?.[perm.key];
                    return (
                      <span
                        key={perm.key}
                        className={`text-xs px-2 py-1 rounded-full ${
                          hasPermission 
                            ? 'bg-emerald-500/20 text-emerald-400' 
                            : 'bg-zinc-800 text-zinc-600'
                        }`}
                        title={perm.description}
                      >
                        {hasPermission ? <CheckCircle className="w-3 h-3 inline mr-1" /> : <XCircle className="w-3 h-3 inline mr-1" />}
                        {perm.label}
                      </span>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {staff.length === 0 && (
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="p-12 text-center">
              <Shield className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
              <p className="text-zinc-400">Нет администраторов или саппортов</p>
              <Button onClick={() => setCreateDialogOpen(true)} className="mt-4 bg-emerald-500 hover:bg-emerald-600">
                <UserPlus className="w-4 h-4 mr-2" />
                Добавить первого
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Create Dialog */}
        <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
          <DialogContent className="bg-zinc-900 border-zinc-800 max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <UserPlus className="w-5 h-5 text-emerald-400" />
                Добавить сотрудника
              </DialogTitle>
            </DialogHeader>

            <div className="space-y-6 py-4">
              {/* Basic Info */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Логин</Label>
                  <Input
                    type="text"
                    value={newEmail}
                    onChange={(e) => setNewEmail(e.target.value.toLowerCase())}
                    placeholder="admin123"
                    className="bg-zinc-950 border-zinc-800"
                  />
                  <p className="text-xs text-zinc-500">Только буквы и цифры</p>
                </div>
                <div className="space-y-2">
                  <Label>Никнейм</Label>
                  <Input
                    type="text"
                    value={newNickname}
                    onChange={(e) => setNewNickname(e.target.value)}
                    placeholder="Иван Админов"
                    className="bg-zinc-950 border-zinc-800"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Пароль</Label>
                <Input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="••••••••"
                  className="bg-zinc-950 border-zinc-800"
                />
              </div>

              {/* Role Selection */}
              <div className="space-y-2">
                <Label>Роль</Label>
                <Select value={newRole} onValueChange={handleRoleChange}>
                  <SelectTrigger className="bg-zinc-950 border-zinc-800">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="support">Саппорт</SelectItem>
                    <SelectItem value="admin">Администратор</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Permissions */}
              <div className="space-y-3">
                <Label className="text-base">Права доступа</Label>
                <div className="bg-zinc-950 rounded-lg border border-zinc-800 divide-y divide-zinc-800">
                  {ALL_PERMISSIONS.map(perm => {
                    const Icon = perm.icon;
                    return (
                      <div key={perm.key} className="flex items-center justify-between p-4">
                        <div className="flex items-center gap-3">
                          <Icon className="w-5 h-5 text-zinc-400" />
                          <div>
                            <div className="font-medium text-sm">{perm.label}</div>
                            <div className="text-xs text-zinc-500">{perm.description}</div>
                          </div>
                        </div>
                        <Switch
                          checked={newPermissions[perm.key] || false}
                          onCheckedChange={() => toggleNewPermission(perm.key)}
                        />
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => { setCreateDialogOpen(false); resetForm(); }} className="border-zinc-700">
                Отмена
              </Button>
              <Button onClick={createStaff} disabled={processing} className="bg-emerald-500 hover:bg-emerald-600">
                {processing ? 'Создание...' : 'Создать'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Edit Permissions Dialog */}
        <Dialog open={!!editDialog} onOpenChange={() => setEditDialog(null)}>
          <DialogContent className="bg-zinc-900 border-zinc-800 max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Settings className="w-5 h-5 text-blue-400" />
                Настройка прав: {editDialog?.nickname || editDialog?.login}
              </DialogTitle>
            </DialogHeader>

            <div className="space-y-3 py-4">
              <div className="bg-zinc-950 rounded-lg border border-zinc-800 divide-y divide-zinc-800">
                {ALL_PERMISSIONS.map(perm => {
                  const Icon = perm.icon;
                  return (
                    <div key={perm.key} className="flex items-center justify-between p-4">
                      <div className="flex items-center gap-3">
                        <Icon className="w-5 h-5 text-zinc-400" />
                        <div>
                          <div className="font-medium text-sm">{perm.label}</div>
                          <div className="text-xs text-zinc-500">{perm.description}</div>
                        </div>
                      </div>
                      <Switch
                        checked={editPermissions[perm.key] || false}
                        onCheckedChange={() => toggleEditPermission(perm.key)}
                      />
                    </div>
                  );
                })}
              </div>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => setEditDialog(null)} className="border-zinc-700">
                Отмена
              </Button>
              <Button onClick={updatePermissions} disabled={processing} className="bg-blue-500 hover:bg-blue-600">
                {processing ? 'Сохранение...' : 'Сохранить'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </DashboardLayout>
  );
};

export default AdminStaff;
