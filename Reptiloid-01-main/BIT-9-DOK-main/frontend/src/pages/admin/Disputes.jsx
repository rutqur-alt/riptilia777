import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import DashboardLayout from '@/components/DashboardLayout';
import { api, formatUSDT, formatRUB, formatDate, getStatusLabel, getStatusClass } from '@/lib/auth';
import CopyableOrderId from '@/components/CopyableOrderId';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
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
import { Textarea } from '@/components/ui/textarea';
import { toast } from 'sonner';
import { RefreshCw, AlertTriangle, CheckCircle, XCircle, User, CreditCard, MessageCircle, Trash2 } from 'lucide-react';

const AdminDisputes = () => {
  const [disputes, setDisputes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedDispute, setSelectedDispute] = useState(null);
  const [notes, setNotes] = useState('');
  const [processing, setProcessing] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    fetchDisputes();
  }, []);

  const fetchDisputes = async () => {
    try {
      const res = await api.get('/disputes');
      setDisputes(res.data.disputes || []);
    } catch (error) {
      toast.error('Ошибка загрузки споров');
    } finally {
      setLoading(false);
    }
  };

  const deleteDispute = async (disputeId) => {
    setDeleting(true);
    try {
      await api.delete(`/admin/disputes/${disputeId}`);
      toast.success('Спор удалён');
      setDeleteConfirm(null);
      fetchDisputes();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка удаления');
    } finally {
      setDeleting(false);
    }
  };

  const resolveDispute = async (decision) => {
    if (!selectedDispute) return;
    
    setProcessing(true);
    try {
      await api.post(`/disputes/${selectedDispute.id}/resolve`, {
        resolution: decision,
        comment: notes
      });
      toast.success('Спор разрешён');
      setSelectedDispute(null);
      setNotes('');
      fetchDisputes();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка');
    } finally {
      setProcessing(false);
    }
  };

  const openDisputes = disputes.filter(d => d.status === 'open');
  const resolvedDisputes = disputes.filter(d => d.status === 'resolved');

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
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold font-['Chivo']">Споры и арбитраж</h1>
            <p className="text-zinc-400 text-sm">Открытых: {openDisputes.length}</p>
          </div>
          <Button variant="outline" onClick={fetchDisputes} className="border-zinc-800">
            <RefreshCw className="w-4 h-4 mr-2" />
            Обновить
          </Button>
        </div>

        {/* Open Disputes */}
        <div>
          <h2 className="text-lg font-semibold mb-4">
            Открытые споры
            {openDisputes.length > 0 && (
              <span className="ml-2 px-2 py-1 rounded-full bg-red-500/20 text-red-400 text-sm">
                {openDisputes.length}
              </span>
            )}
          </h2>
          
          {openDisputes.length === 0 ? (
            <Card className="bg-zinc-900 border-zinc-800">
              <CardContent className="p-12 text-center">
                <CheckCircle className="w-12 h-12 text-emerald-500 mx-auto mb-4" />
                <h3 className="text-lg font-medium mb-2">Нет открытых споров</h3>
                <p className="text-zinc-400 text-sm">Все споры разрешены</p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {openDisputes.map((dispute) => (
                <Card key={dispute.id} className="bg-zinc-900 border-zinc-800 border-l-4 border-l-orange-500">
                  <CardContent className="p-5">
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="w-5 h-5 text-orange-400" />
                        <CopyableOrderId orderId={dispute.order?.id} size="small" />
                      </div>
                      <span className={`px-2 py-1 rounded text-xs border ${getStatusClass(dispute.status)}`}>
                        {getStatusLabel(dispute.status)}
                      </span>
                    </div>

                    {dispute.order && (
                      <div className="space-y-2 mb-4">
                        <div className="flex justify-between">
                          <span className="text-zinc-400">Сумма:</span>
                          <span className="font-['JetBrains_Mono']">{formatRUB(dispute.order.amount_rub)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-400">USDT:</span>
                          <span className="font-['JetBrains_Mono']">{formatUSDT(dispute.order.amount_usdt)}</span>
                        </div>
                      </div>
                    )}

                    <div className="text-sm text-zinc-400 mb-2">
                      <strong>Причина:</strong> {dispute.reason}
                    </div>
                    
                    <div className="text-sm text-zinc-500 mb-4">
                      Инициатор: {dispute.initiated_by === 'trader' ? 'Трейдер' : dispute.initiated_by === 'buyer' ? 'Покупатель' : 'Система'}
                      <br />
                      Создан: {formatDate(dispute.created_at)}
                    </div>

                    <div className="flex gap-2">
                      <Link to={`/admin/disputes/${dispute.id}`} className="flex-1">
                        <Button
                          variant="outline"
                          className="w-full border-zinc-700"
                        >
                          <MessageCircle className="w-4 h-4 mr-2" />
                          Чат
                        </Button>
                      </Link>
                      <Button
                        onClick={() => setSelectedDispute(dispute)}
                        className="flex-1 bg-orange-500 hover:bg-orange-600"
                        data-testid={`resolve-dispute-${dispute.id}`}
                      >
                        Решить
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setDeleteConfirm(dispute)}
                        className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>

        {/* Resolved Disputes */}
        {resolvedDisputes.length > 0 && (
          <div>
            <h2 className="text-lg font-semibold mb-4">Разрешённые споры</h2>
            <Card className="bg-zinc-900 border-zinc-800 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-zinc-800">
                      <th className="table-header px-4 py-3 text-left">Ордер</th>
                      <th className="table-header px-4 py-3 text-left">Сумма</th>
                      <th className="table-header px-4 py-3 text-left">Решение</th>
                      <th className="table-header px-4 py-3 text-left">Дата</th>
                      <th className="table-header px-4 py-3 text-right">Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resolvedDisputes.map((dispute) => (
                      <tr key={dispute.id} className="border-b border-zinc-800/50">
                        <td className="px-4 py-3">
                          <CopyableOrderId orderId={dispute.order?.id || dispute.order_id} size="small" />
                        </td>
                        <td className="px-4 py-3 font-['JetBrains_Mono']">
                          {formatRUB(dispute.order?.amount_rub)}
                        </td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-1 rounded text-xs ${
                            dispute.decision === 'pay_buyer' ? 'bg-emerald-500/20 text-emerald-400' :
                            dispute.decision === 'cancel' ? 'bg-orange-500/20 text-orange-400' :
                            'bg-blue-500/20 text-blue-400'
                          }`}>
                            {dispute.decision === 'pay_buyer' ? 'В пользу покупателя' :
                             dispute.decision === 'cancel' ? 'USDT возвращены трейдеру' :
                             dispute.decision}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm text-zinc-400">
                          {formatDate(dispute.resolved_at)}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-end gap-2">
                            <Link to={`/admin/disputes/${dispute.id}`}>
                              <Button
                                variant="outline"
                                size="sm"
                                className="border-zinc-700"
                              >
                                <MessageCircle className="w-4 h-4 mr-1" />
                                Чат
                              </Button>
                            </Link>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setDeleteConfirm(dispute)}
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
          </div>
        )}

        {/* Delete Confirmation Dialog */}
        <AlertDialog open={!!deleteConfirm} onOpenChange={() => setDeleteConfirm(null)}>
          <AlertDialogContent className="bg-zinc-900 border-zinc-800">
            <AlertDialogHeader>
              <AlertDialogTitle>Удалить спор?</AlertDialogTitle>
              <AlertDialogDescription>
                Спор по заказу будет удалён. Это действие нельзя отменить.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel className="bg-zinc-800 border-zinc-700 hover:bg-zinc-700">Отмена</AlertDialogCancel>
              <AlertDialogAction
                onClick={() => deleteDispute(deleteConfirm?.id)}
                disabled={deleting}
                className="bg-red-600 hover:bg-red-700"
              >
                {deleting ? 'Удаление...' : 'Удалить'}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Resolve Dialog */}
        <Dialog open={!!selectedDispute} onOpenChange={(open) => !open && setSelectedDispute(null)}>
          <DialogContent className="bg-zinc-900 border-zinc-800 max-w-2xl">
            <DialogHeader>
              <DialogTitle className="font-['Chivo'] flex items-center gap-3">
                Рассмотрение спора по заказу 
                <CopyableOrderId orderId={selectedDispute?.order?.id || selectedDispute?.order_id} size="default" />
              </DialogTitle>
            </DialogHeader>

            {(selectedDispute?.order || selectedDispute) && (
              <div className="space-y-6 mt-4">
                {/* Order Details */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-zinc-800 rounded-lg p-4">
                    <div className="text-sm text-zinc-400 mb-1">Сумма ордера</div>
                    <div className="font-['JetBrains_Mono'] text-xl">{formatRUB(selectedDispute.order?.amount_rub || selectedDispute.amount_rub)}</div>
                    <div className="font-['JetBrains_Mono'] text-sm text-zinc-400">{formatUSDT(selectedDispute.order?.amount_usdt || selectedDispute.amount_usdt)} USDT</div>
                  </div>
                  <div className="bg-zinc-800 rounded-lg p-4">
                    <div className="text-sm text-zinc-400 mb-1">Статус ордера</div>
                    <span className={`px-2 py-1 rounded text-xs border ${getStatusClass(selectedDispute.order?.status || selectedDispute.status)}`}>
                      {getStatusLabel(selectedDispute.order?.status || selectedDispute.status)}
                    </span>
                  </div>
                </div>

                {/* Contacts */}
                <div className="grid grid-cols-2 gap-4">
                  {(selectedDispute.order?.buyer_contact || selectedDispute.buyer_contact) && (
                    <div className="flex items-center gap-2 p-3 bg-zinc-800 rounded-lg">
                      <User className="w-5 h-5 text-blue-400" />
                      <div>
                        <div className="text-xs text-zinc-500">Контакт покупателя</div>
                        <div className="text-sm">{selectedDispute.order?.buyer_contact || selectedDispute.buyer_contact}</div>
                      </div>
                    </div>
                  )}
                  {(selectedDispute.order?.payment_details || selectedDispute.payment_details) && (
                    <div className="flex items-center gap-2 p-3 bg-zinc-800 rounded-lg">
                      <CreditCard className="w-5 h-5 text-emerald-400" />
                      <div>
                        <div className="text-xs text-zinc-500">Реквизиты трейдера</div>
                        <div className="text-sm font-['JetBrains_Mono']">
                          {(selectedDispute.order?.payment_details || selectedDispute.payment_details)?.card_number || 
                           (selectedDispute.order?.payment_details || selectedDispute.payment_details)?.phone_number}
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Notes */}
                <div className="space-y-2">
                  <label className="text-sm text-zinc-400">Заметки администратора</label>
                  <Textarea
                    placeholder="Комментарий к решению..."
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    className="bg-zinc-950 border-zinc-800 min-h-[100px]"
                    data-testid="moderator-notes"
                  />
                </div>

                {/* Actions */}
                <div className="grid grid-cols-2 gap-4">
                  <Button
                    onClick={() => resolveDispute('pay_buyer')}
                    disabled={processing}
                    className="bg-emerald-500 hover:bg-emerald-600"
                    data-testid="resolve-pay-buyer"
                  >
                    <CheckCircle className="w-4 h-4 mr-2" />
                    В пользу покупателя
                  </Button>
                  <Button
                    onClick={() => resolveDispute('cancel')}
                    disabled={processing}
                    variant="outline"
                    className="border-red-500/50 text-red-400 hover:bg-red-500/10"
                    data-testid="resolve-cancel"
                  >
                    <XCircle className="w-4 h-4 mr-2" />
                    Вернуть USDT трейдеру
                  </Button>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </DashboardLayout>
  );
};

export default AdminDisputes;
