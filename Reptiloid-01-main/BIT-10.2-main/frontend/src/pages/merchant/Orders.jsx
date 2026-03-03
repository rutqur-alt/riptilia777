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
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { toast } from 'sonner';
import { RefreshCw, Search, FileText, ExternalLink, AlertTriangle, Copy, CheckCircle } from 'lucide-react';

const MerchantOrders = () => {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [limit] = useState(50);
  
  // Dispute dialog
  const [disputeDialog, setDisputeDialog] = useState(false);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [disputeReason, setDisputeReason] = useState('');
  const [openingDispute, setOpeningDispute] = useState(false);
  
  // Dispute link dialog
  const [disputeLinkDialog, setDisputeLinkDialog] = useState(false);
  const [disputeLink, setDisputeLink] = useState('');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchOrders();
  }, [statusFilter, offset]);

  const fetchOrders = async () => {
    try {
      setLoading(true);
      const params = { limit, offset };
      if (statusFilter !== 'all') params.status = statusFilter;
      
      const res = await api.get('/merchant/transactions', { params });
      setOrders(res.data.transactions || []);
      setTotal(res.data.total || 0);
    } catch (error) {
      toast.error('Ошибка загрузки транзакций');
    } finally {
      setLoading(false);
    }
  };

  const filteredOrders = orders.filter(order => {
    if (!searchQuery) return true;
    return order.id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
           order.external_id?.toLowerCase().includes(searchQuery.toLowerCase());
  });

  const openDisputeDialog = (order) => {
    setSelectedOrder(order);
    setDisputeReason('');
    setDisputeDialog(true);
  };

  const handleOpenDispute = async () => {
    if (!selectedOrder) {
      return;
    }
    
    setOpeningDispute(true);
    try {
      const res = await api.post(`/merchant/transaction/${selectedOrder.id}/open-dispute`, null, {
        params: { reason: 'Спор открыт мерчантом' }
      });
      
      toast.success('Спор открыт');
      setDisputeDialog(false);
      
      fetchOrders();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка открытия спора');
    } finally {
      setOpeningDispute(false);
    }
  };

  const copyDisputeLink = async (link) => {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      toast.success('Ссылка скопирована');
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error('Не удалось скопировать');
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed':
      case 'paid':
        return 'text-emerald-400 bg-emerald-500/20 border-emerald-500/30';
      case 'pending':
      case 'waiting_buyer_confirmation':
      case 'waiting_trader_confirmation':
        return 'text-yellow-400 bg-yellow-500/20 border-yellow-500/30';
      case 'dispute':
      case 'disputed':
        return 'text-orange-400 bg-orange-500/20 border-orange-500/30';
      case 'cancelled':
      case 'expired':
      case 'failed':
        return 'text-red-400 bg-red-500/20 border-red-500/30';
      default:
        return 'text-zinc-400 bg-zinc-500/20 border-zinc-500/30';
    }
  };

  const canOpenDispute = (order) => {
    return ['pending', 'waiting_buyer_confirmation', 'waiting_trader_confirmation', 'paid'].includes(order.status);
  };

  if (loading && orders.length === 0) {
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
            <h1 className="text-2xl font-bold font-['Chivo']">Транзакции</h1>
            <p className="text-zinc-400 text-sm">Всего: {total} транзакций</p>
          </div>
          <Button variant="outline" onClick={fetchOrders} className="border-zinc-800" disabled={loading}>
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Обновить
          </Button>
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <Input
              placeholder="Поиск по ID заказа..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 bg-zinc-900 border-zinc-800"
              data-testid="order-search-input"
            />
          </div>
          <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setOffset(0); }}>
            <SelectTrigger className="w-full sm:w-48 bg-zinc-900 border-zinc-800" data-testid="status-filter">
              <SelectValue placeholder="Статус" />
            </SelectTrigger>
            <SelectContent className="bg-zinc-900 border-zinc-800">
              <SelectItem value="all">Все статусы</SelectItem>
              <SelectItem value="active">Активные</SelectItem>
              <SelectItem value="completed">Завершённые</SelectItem>
              <SelectItem value="dispute">Спорные</SelectItem>
              <SelectItem value="cancelled">Отменённые</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Orders Table */}
        {filteredOrders.length === 0 ? (
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="p-12 text-center">
              <FileText className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
              <h3 className="text-lg font-medium mb-2">Нет транзакций</h3>
              <p className="text-zinc-400 text-sm">
                {statusFilter !== 'all' ? 'Нет транзакций с выбранным статусом' : 'Транзакции появятся здесь после создания через API'}
              </p>
            </CardContent>
          </Card>
        ) : (
          <Card className="bg-zinc-900 border-zinc-800 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-zinc-800">
                    <th className="table-header px-4 py-3 text-left">ID / Внешний ID</th>
                    <th className="table-header px-4 py-3 text-left">Сумма</th>
                    <th className="table-header px-4 py-3 text-left">Статус</th>
                    <th className="table-header px-4 py-3 text-left">Дата</th>
                    <th className="table-header px-4 py-3 text-right">Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredOrders.map((order) => (
                    <tr key={order.id} className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
                      <td className="px-4 py-3">
                        <CopyableOrderId orderId={order.id} size="small" />
                        {order.external_id && (
                          <div className="text-xs text-zinc-500 mt-1">ext: {order.external_id}</div>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-['JetBrains_Mono']">{formatRUB(order.amount_rub)}</div>
                        <div className="font-['JetBrains_Mono'] text-sm text-zinc-500">{formatUSDT(order.amount_usdt)} USDT</div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-1 rounded text-xs border ${getStatusColor(order.status)}`}>
                          {getStatusLabel(order.status)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-zinc-400">
                        {formatDate(order.created_at)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-2">
                          {/* Ссылка на спор / Чат спора */}
                          {(order.status === 'disputed' || order.dispute_id) && (
                            <Link to={`/merchant/disputes/${order.dispute_id || order.id}`}>
                              <Button
                                variant="outline"
                                size="sm"
                                className="border-orange-500/50 text-orange-400 hover:bg-orange-500/10"
                                data-testid={`dispute-chat-${order.id}`}
                              >
                                <AlertTriangle className="w-4 h-4 mr-1" />
                                Чат спора
                              </Button>
                            </Link>
                          )}
                          
                          {/* Открыть спор */}
                          {canOpenDispute(order) && order.status !== 'disputed' && !order.dispute_id && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-orange-400 hover:text-orange-300 hover:bg-orange-500/10"
                              onClick={() => openDisputeDialog(order)}
                              data-testid={`open-dispute-${order.id}`}
                            >
                              <AlertTriangle className="w-4 h-4 mr-1" />
                              Открыть спор
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            
            {/* Pagination */}
            {total > limit && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-zinc-800">
                <div className="text-sm text-zinc-400">
                  Показано {offset + 1}-{Math.min(offset + limit, total)} из {total}
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={offset === 0}
                    onClick={() => setOffset(Math.max(0, offset - limit))}
                    className="border-zinc-800"
                  >
                    Назад
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={offset + limit >= total}
                    onClick={() => setOffset(offset + limit)}
                    className="border-zinc-800"
                  >
                    Далее
                  </Button>
                </div>
              </div>
            )}
          </Card>
        )}

        {/* Open Dispute Dialog */}
        <Dialog open={disputeDialog} onOpenChange={setDisputeDialog}>
          <DialogContent className="bg-zinc-900 border-zinc-800">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-orange-400" />
                Открыть спор
              </DialogTitle>
            </DialogHeader>
            
            {selectedOrder && (
              <div className="space-y-4 mt-4">
                <div className="bg-zinc-800 rounded-lg p-4">
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-zinc-400">ID заказа:</span>
                      <div className="font-['JetBrains_Mono']">{selectedOrder.id}</div>
                    </div>
                    <div>
                      <span className="text-zinc-400">Сумма:</span>
                      <div className="font-['JetBrains_Mono']">{formatRUB(selectedOrder.amount_rub)}</div>
                    </div>
                  </div>
                </div>
                
                <div className="bg-orange-500/10 border border-orange-500/20 rounded-lg p-3 text-sm text-orange-300">
                  После открытия спора вы сможете общаться с трейдером и администрацией в чате.
                </div>
              </div>
            )}
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setDisputeDialog(false)} className="border-zinc-700">
                Отмена
              </Button>
              <Button 
                onClick={handleOpenDispute} 
                disabled={openingDispute}
                className="bg-orange-500 hover:bg-orange-600"
                data-testid="confirm-open-dispute"
              >
                {openingDispute ? 'Открываем...' : 'Открыть спор'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Dispute Link Dialog */}
        <Dialog open={disputeLinkDialog} onOpenChange={setDisputeLinkDialog}>
          <DialogContent className="bg-zinc-900 border-zinc-800">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <CheckCircle className="w-5 h-5 text-emerald-400" />
                Ссылка на спор
              </DialogTitle>
            </DialogHeader>
            
            <div className="space-y-4 mt-4">
              <p className="text-sm text-zinc-400">
                Передайте эту ссылку клиенту для связи с поддержкой напрямую:
              </p>
              
              <div className="flex items-center gap-2">
                <Input
                  value={disputeLink}
                  readOnly
                  className="bg-zinc-950 border-zinc-800 font-['JetBrains_Mono'] text-sm"
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => copyDisputeLink(disputeLink)}
                  className="border-zinc-700 shrink-0"
                  data-testid="copy-dispute-link"
                >
                  {copied ? <CheckCircle className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                </Button>
              </div>
              
              <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3 text-sm text-blue-300">
                Ссылка активна до закрытия спора. После решения спора по ней будет показан результат.
              </div>
            </div>
            
            <DialogFooter>
              <Button onClick={() => setDisputeLinkDialog(false)} className="bg-emerald-500 hover:bg-emerald-600">
                Понятно
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </DashboardLayout>
  );
};

export default MerchantOrders;
