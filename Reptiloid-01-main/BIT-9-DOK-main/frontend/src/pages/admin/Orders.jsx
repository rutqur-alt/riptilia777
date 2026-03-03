import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import DashboardLayout from '@/components/DashboardLayout';
import { api, formatUSDT, formatRUB, formatDate, getStatusLabel, getStatusClass } from '@/lib/auth';
import CopyableOrderId from '@/components/CopyableOrderId';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { toast } from 'sonner';
import { RefreshCw, Search, FileText, Trash2, MessageCircle, AlertTriangle } from 'lucide-react';

const AdminOrders = () => {
  const [orders, setOrders] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    fetchOrders();
  }, [statusFilter]);

  const fetchOrders = async () => {
    try {
      const params = { limit: 100 };
      if (statusFilter !== 'all') params.status = statusFilter;
      
      const res = await api.get('/admin/orders', { params });
      setOrders(res.data.orders || []);
      setTotal(res.data.total || 0);
    } catch (error) {
      toast.error('Ошибка загрузки ордеров');
    } finally {
      setLoading(false);
    }
  };

  const deleteOrder = async (orderId) => {
    setDeleting(true);
    try {
      await api.delete(`/admin/orders/${orderId}`);
      toast.success('Ордер удалён');
      setDeleteConfirm(null);
      fetchOrders();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка удаления');
    } finally {
      setDeleting(false);
    }
  };

  const filteredOrders = orders.filter(order => {
    if (!searchQuery) return true;
    return order.id.toLowerCase().includes(searchQuery.toLowerCase());
  });

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
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold font-['Chivo']">Все ордера</h1>
            <p className="text-zinc-400 text-sm">Всего: {total}</p>
          </div>
          <Button variant="outline" onClick={fetchOrders} className="border-zinc-800">
            <RefreshCw className="w-4 h-4 mr-2" />
            Обновить
          </Button>
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <Input
              placeholder="Поиск по ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 bg-zinc-900 border-zinc-800"
              data-testid="order-search-input"
            />
          </div>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-full sm:w-48 bg-zinc-900 border-zinc-800" data-testid="status-filter">
              <SelectValue placeholder="Статус" />
            </SelectTrigger>
            <SelectContent className="bg-zinc-900 border-zinc-800">
              <SelectItem value="all">Все статусы</SelectItem>
              <SelectItem value="waiting_buyer_confirmation">Ожидание оплаты</SelectItem>
              <SelectItem value="waiting_trader_confirmation">Ожидание подтверждения</SelectItem>
              <SelectItem value="completed">Завершён</SelectItem>
              <SelectItem value="cancelled">Отменён</SelectItem>
              <SelectItem value="dispute">Спор</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Orders Table */}
        {filteredOrders.length === 0 ? (
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="p-12 text-center">
              <FileText className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
              <h3 className="text-lg font-medium mb-2">Нет ордеров</h3>
            </CardContent>
          </Card>
        ) : (
          <Card className="bg-zinc-900 border-zinc-800 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-zinc-800">
                    <th className="table-header px-4 py-3 text-left">ID</th>
                    <th className="table-header px-4 py-3 text-left">Сумма</th>
                    <th className="table-header px-4 py-3 text-left">USDT</th>
                    <th className="table-header px-4 py-3 text-left">Статус</th>
                    <th className="table-header px-4 py-3 text-left">Трейдер</th>
                    <th className="table-header px-4 py-3 text-left">Мерчант</th>
                    <th className="table-header px-4 py-3 text-left">Создан</th>
                    <th className="table-header px-4 py-3 text-right">Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredOrders.map((order) => (
                    <tr key={order.id} className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
                      <td className="px-4 py-3">
                        <CopyableOrderId orderId={order.id} size="small" />
                      </td>
                      <td className="px-4 py-3 font-['JetBrains_Mono']">
                        {formatRUB(order.amount_rub)}
                      </td>
                      <td className="px-4 py-3 font-['JetBrains_Mono'] text-zinc-400">
                        {formatUSDT(order.amount_usdt)}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-1 rounded text-xs border ${getStatusClass(order.status)}`}>
                          {getStatusLabel(order.status)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-zinc-400">
                        {order.trader_id?.substring(0, 10) || '-'}...
                      </td>
                      <td className="px-4 py-3 text-sm text-zinc-400">
                        {order.merchant_id?.substring(0, 10) || '-'}...
                      </td>
                      <td className="px-4 py-3 text-sm text-zinc-400">
                        {formatDate(order.created_at)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-2">
                          {/* Кнопка чата спора */}
                          {(order.status === 'disputed' || order.dispute_id) && (
                            <Link to={`/admin/disputes/${order.dispute_id || order.id}`}>
                              <Button
                                variant="outline"
                                size="sm"
                                className="border-orange-500/50 text-orange-400 hover:bg-orange-500/10"
                              >
                                <AlertTriangle className="w-4 h-4 mr-1" />
                                Чат спора
                              </Button>
                            </Link>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setDeleteConfirm(order)}
                            className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        {/* Delete Confirmation */}
        <AlertDialog open={!!deleteConfirm} onOpenChange={() => setDeleteConfirm(null)}>
          <AlertDialogContent className="bg-zinc-900 border-zinc-800">
            <AlertDialogHeader>
              <AlertDialogTitle>Удалить ордер?</AlertDialogTitle>
              <AlertDialogDescription>
                Ордер #{deleteConfirm?.id} будет удалён. Это действие нельзя отменить.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel className="bg-zinc-800 border-zinc-700 hover:bg-zinc-700">Отмена</AlertDialogCancel>
              <AlertDialogAction
                onClick={() => deleteOrder(deleteConfirm?.id)}
                disabled={deleting}
                className="bg-red-600 hover:bg-red-700"
              >
                {deleting ? 'Удаление...' : 'Удалить'}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </DashboardLayout>
  );
};

export default AdminOrders;
