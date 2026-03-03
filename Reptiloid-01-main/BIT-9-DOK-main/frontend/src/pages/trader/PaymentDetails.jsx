import React, { useState, useEffect } from 'react';
import DashboardLayout from '@/components/DashboardLayout';
import { api, formatRUB } from '@/lib/auth';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from 'sonner';
import { Plus, CreditCard, Smartphone, QrCode, Phone, Trash2, Edit, CheckCircle, Banknote, Globe } from 'lucide-react';

// 7 методов оплаты
const PAYMENT_METHODS = {
  sbp: {
    name: 'SBP',
    icon: Phone,
    description: 'Система быстрых платежей',
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10'
  },
  card: {
    name: 'Card',
    icon: CreditCard,
    description: 'Банковская карта',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10'
  },
  sim: {
    name: 'SIM',
    icon: Smartphone,
    description: 'Пополнение мобильного',
    color: 'text-orange-400',
    bgColor: 'bg-orange-500/10'
  },
  mono_bank: {
    name: 'Mono Bank',
    icon: Banknote,
    description: 'Mono Bank (телефон или карта)',
    color: 'text-purple-400',
    bgColor: 'bg-purple-500/10'
  },
  sng_sbp: {
    name: 'SNG-SBP',
    icon: Globe,
    description: 'СНГ - СБП',
    color: 'text-cyan-400',
    bgColor: 'bg-cyan-500/10'
  },
  sng_card: {
    name: 'SNG-Card',
    icon: Globe,
    description: 'СНГ - Карта',
    color: 'text-teal-400',
    bgColor: 'bg-teal-500/10'
  },
  qr_code: {
    name: 'QR-code',
    icon: QrCode,
    description: 'QR-код (ссылка)',
    color: 'text-pink-400',
    bgColor: 'bg-pink-500/10'
  }
};

const TraderPaymentDetails = () => {
  const [details, setDetails] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  
  const [formData, setFormData] = useState({
    payment_type: 'sbp',
    card_number: '',
    phone_number: '',
    qr_link: '',
    bank_name: '',
    operator_name: '',
    holder_name: '',
    comment: '',
    min_amount_rub: 100,
    max_amount_rub: 500000,
    daily_limit_rub: 1500000,
    priority: 10,
    is_active: true,
  });

  useEffect(() => {
    fetchDetails();
  }, []);

  const fetchDetails = async () => {
    try {
      const res = await api.get('/trader/payment-details');
      setDetails(res.data);
    } catch (error) {
      toast.error('Ошибка загрузки реквизитов');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Валидация обязательных полей
    const type = formData.payment_type;
    
    if (type === 'sbp' || type === 'sng_sbp') {
      if (!formData.phone_number || !formData.bank_name) {
        toast.error('Заполните номер телефона и название банка');
        return;
      }
    } else if (type === 'card' || type === 'sng_card') {
      if (!formData.card_number || !formData.bank_name) {
        toast.error('Заполните номер карты и название банка');
        return;
      }
    } else if (type === 'sim') {
      if (!formData.phone_number || !formData.operator_name) {
        toast.error('Заполните номер телефона и название оператора');
        return;
      }
    } else if (type === 'mono_bank') {
      if (!formData.phone_number && !formData.card_number) {
        toast.error('Заполните номер телефона или номер карты');
        return;
      }
    } else if (type === 'qr_code') {
      if (!formData.qr_link) {
        toast.error('Вставьте ссылку на QR-код');
        return;
      }
    }
    
    try {
      if (editingId) {
        await api.put(`/trader/payment-details/${editingId}`, formData);
        toast.success('Реквизит обновлён');
      } else {
        await api.post('/trader/payment-details', formData);
        toast.success('Реквизит добавлен');
      }
      
      setDialogOpen(false);
      resetForm();
      fetchDetails();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка сохранения');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Удалить реквизит?')) return;
    
    try {
      await api.delete(`/trader/payment-details/${id}`);
      toast.success('Реквизит удалён');
      fetchDetails();
    } catch (error) {
      toast.error('Ошибка удаления');
    }
  };

  const resetForm = () => {
    setFormData({
      payment_type: 'sbp',
      card_number: '',
      phone_number: '',
      qr_link: '',
      bank_name: '',
      operator_name: '',
      holder_name: '',
      comment: '',
      min_amount_rub: 100,
      max_amount_rub: 500000,
      daily_limit_rub: 1500000,
      priority: 10,
      is_active: true,
    });
    setEditingId(null);
  };

  const handleEdit = (detail) => {
    setFormData({
      payment_type: detail.payment_type,
      card_number: detail.card_number || '',
      phone_number: detail.phone_number || '',
      qr_link: detail.qr_link || detail.qr_data || '',
      bank_name: detail.bank_name || '',
      operator_name: detail.operator_name || '',
      holder_name: detail.holder_name || '',
      comment: detail.comment || '',
      min_amount_rub: detail.min_amount_rub,
      max_amount_rub: detail.max_amount_rub,
      daily_limit_rub: detail.daily_limit_rub,
      priority: detail.priority,
      is_active: detail.is_active,
    });
    setEditingId(detail.id);
    setDialogOpen(true);
  };

  const getMethodIcon = (type) => {
    const method = PAYMENT_METHODS[type];
    if (!method) return CreditCard;
    return method.icon;
  };

  const formatDetailInfo = (detail) => {
    const type = detail.payment_type;
    
    if (type === 'sbp' || type === 'sng_sbp') {
      const parts = [detail.phone_number, detail.bank_name, detail.holder_name].filter(Boolean);
      return parts.join(' • ') || 'Не заполнено';
    } else if (type === 'card' || type === 'sng_card') {
      const cardDisplay = detail.card_number?.replace(/(\d{4})/g, '$1 ').trim();
      const parts = [cardDisplay, detail.bank_name, detail.holder_name].filter(Boolean);
      return parts.join(' • ') || 'Не заполнено';
    } else if (type === 'sim') {
      const parts = [detail.phone_number, detail.operator_name].filter(Boolean);
      return parts.join(' • ') || 'Не заполнено';
    } else if (type === 'mono_bank') {
      const main = detail.phone_number || detail.card_number?.replace(/(\d{4})/g, '$1 ').trim();
      const parts = [main, detail.comment, detail.bank_name].filter(Boolean);
      return parts.join(' • ') || 'Не заполнено';
    } else if (type === 'qr_code') {
      const link = detail.qr_link || detail.qr_data;
      if (!link) return 'Не заполнено';
      return link.length > 50 ? link.slice(0, 50) + '...' : link;
    }
    
    return 'Реквизит';
  };

  const renderFormFields = () => {
    const type = formData.payment_type;
    
    return (
      <>
        {/* SBP & SNG-SBP: телефон + банк + ФИО(опц) */}
        {(type === 'sbp' || type === 'sng_sbp') && (
          <>
            <div className="space-y-2">
              <Label>Номер телефона <span className="text-red-400">*</span></Label>
              <Input
                placeholder="+7 999 123 45 67"
                value={formData.phone_number}
                onChange={(e) => setFormData({ ...formData, phone_number: e.target.value })}
                className="bg-zinc-950 border-zinc-800 font-['JetBrains_Mono']"
                required
              />
            </div>
            <div className="space-y-2">
              <Label>Название банка <span className="text-red-400">*</span></Label>
              <Input
                placeholder="Сбербанк, Тинькофф, Альфа-Банк..."
                value={formData.bank_name}
                onChange={(e) => setFormData({ ...formData, bank_name: e.target.value })}
                className="bg-zinc-950 border-zinc-800"
                required
              />
            </div>
            <div className="space-y-2">
              <Label>ФИО получателя (опционально)</Label>
              <Input
                placeholder="Иван Иванов И."
                value={formData.holder_name}
                onChange={(e) => setFormData({ ...formData, holder_name: e.target.value })}
                className="bg-zinc-950 border-zinc-800"
              />
            </div>
          </>
        )}

        {/* Card & SNG-Card: карта + банк + ФИО(опц) */}
        {(type === 'card' || type === 'sng_card') && (
          <>
            <div className="space-y-2">
              <Label>Номер карты <span className="text-red-400">*</span></Label>
              <Input
                placeholder="2200 0000 0000 0000"
                value={formData.card_number}
                onChange={(e) => setFormData({ ...formData, card_number: e.target.value.replace(/\s/g, '') })}
                className="bg-zinc-950 border-zinc-800 font-['JetBrains_Mono']"
                required
              />
            </div>
            <div className="space-y-2">
              <Label>Название банка <span className="text-red-400">*</span></Label>
              <Input
                placeholder="Сбербанк, Тинькофф, Альфа-Банк..."
                value={formData.bank_name}
                onChange={(e) => setFormData({ ...formData, bank_name: e.target.value })}
                className="bg-zinc-950 border-zinc-800"
                required
              />
            </div>
            <div className="space-y-2">
              <Label>ФИО получателя (опционально)</Label>
              <Input
                placeholder="Иван Иванов И."
                value={formData.holder_name}
                onChange={(e) => setFormData({ ...formData, holder_name: e.target.value })}
                className="bg-zinc-950 border-zinc-800"
              />
            </div>
          </>
        )}

        {/* SIM: телефон + оператор */}
        {type === 'sim' && (
          <>
            <div className="space-y-2">
              <Label>Номер телефона <span className="text-red-400">*</span></Label>
              <Input
                placeholder="+7 999 123 45 67"
                value={formData.phone_number}
                onChange={(e) => setFormData({ ...formData, phone_number: e.target.value })}
                className="bg-zinc-950 border-zinc-800 font-['JetBrains_Mono']"
                required
              />
            </div>
            <div className="space-y-2">
              <Label>Название оператора <span className="text-red-400">*</span></Label>
              <Input
                placeholder="МТС, Билайн, Мегафон, Теле2..."
                value={formData.operator_name}
                onChange={(e) => setFormData({ ...formData, operator_name: e.target.value })}
                className="bg-zinc-950 border-zinc-800"
                required
              />
            </div>
          </>
        )}

        {/* Mono Bank: телефон ИЛИ карта + комментарий + банк(опц) + ФИО(опц) */}
        {type === 'mono_bank' && (
          <>
            <div className="space-y-2">
              <Label>Номер телефона</Label>
              <Input
                placeholder="+7 999 123 45 67"
                value={formData.phone_number}
                onChange={(e) => setFormData({ ...formData, phone_number: e.target.value })}
                className="bg-zinc-950 border-zinc-800 font-['JetBrains_Mono']"
              />
              <p className="text-xs text-zinc-500">Заполните телефон ИЛИ номер карты</p>
            </div>
            <div className="space-y-2">
              <Label>Номер карты</Label>
              <Input
                placeholder="2200 0000 0000 0000"
                value={formData.card_number}
                onChange={(e) => setFormData({ ...formData, card_number: e.target.value.replace(/\s/g, '') })}
                className="bg-zinc-950 border-zinc-800 font-['JetBrains_Mono']"
              />
            </div>
            <div className="space-y-2">
              <Label>Комментарий</Label>
              <Input
                placeholder="Альфа-альфа, примечание..."
                value={formData.comment}
                onChange={(e) => setFormData({ ...formData, comment: e.target.value })}
                className="bg-zinc-950 border-zinc-800"
              />
            </div>
            <div className="space-y-2">
              <Label>Название банка (опционально)</Label>
              <Input
                placeholder="Mono Bank, Приват..."
                value={formData.bank_name}
                onChange={(e) => setFormData({ ...formData, bank_name: e.target.value })}
                className="bg-zinc-950 border-zinc-800"
              />
            </div>
            <div className="space-y-2">
              <Label>ФИО получателя (опционально)</Label>
              <Input
                placeholder="Иван Иванов И."
                value={formData.holder_name}
                onChange={(e) => setFormData({ ...formData, holder_name: e.target.value })}
                className="bg-zinc-950 border-zinc-800"
              />
            </div>
          </>
        )}

        {/* QR-code: ссылка */}
        {type === 'qr_code' && (
          <div className="space-y-2">
            <Label>Ссылка на QR-код <span className="text-red-400">*</span></Label>
            <Input
              placeholder="https://qr.nspk.ru/..."
              value={formData.qr_link}
              onChange={(e) => setFormData({ ...formData, qr_link: e.target.value })}
              className="bg-zinc-950 border-zinc-800 font-['JetBrains_Mono'] text-sm"
              required
            />
            <p className="text-xs text-zinc-500">Вставьте полную ссылку на QR-код</p>
          </div>
        )}
      </>
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
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold font-['Chivo']">Платёжные реквизиты</h1>
            <p className="text-zinc-400 text-sm">Добавьте реквизиты для получения платежей от покупателей</p>
          </div>
          
          <Dialog open={dialogOpen} onOpenChange={(open) => {
            setDialogOpen(open);
            if (!open) resetForm();
          }}>
            <DialogTrigger asChild>
              <Button className="bg-emerald-500 hover:bg-emerald-600" data-testid="add-payment-detail-btn">
                <Plus className="w-4 h-4 mr-2" />
                Добавить
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle className="font-['Chivo']">
                  {editingId ? 'Редактировать реквизит' : 'Добавить реквизит'}
                </DialogTitle>
              </DialogHeader>
              
              <form onSubmit={handleSubmit} className="space-y-4 mt-4">
                <div className="space-y-2">
                  <Label>Метод оплаты</Label>
                  <Select
                    value={formData.payment_type}
                    onValueChange={(v) => setFormData({ ...formData, payment_type: v })}
                  >
                    <SelectTrigger className="bg-zinc-950 border-zinc-800">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-zinc-900 border-zinc-800">
                      {Object.entries(PAYMENT_METHODS).map(([key, method]) => {
                        const Icon = method.icon;
                        return (
                          <SelectItem key={key} value={key}>
                            <div className="flex items-center gap-2">
                              <Icon className={`w-4 h-4 ${method.color}`} />
                              <span>{method.name}</span>
                            </div>
                          </SelectItem>
                        );
                      })}
                    </SelectContent>
                  </Select>
                </div>

                {/* Динамические поля в зависимости от типа */}
                {renderFormFields()}

                {/* Лимиты */}
                <div className="border-t border-zinc-800 pt-4 mt-4">
                  <Label className="text-zinc-400 text-sm">Лимиты</Label>
                  <div className="grid grid-cols-2 gap-4 mt-2">
                    <div className="space-y-2">
                      <Label className="text-xs">Мин. сумма (₽)</Label>
                      <Input
                        type="number"
                        value={formData.min_amount_rub}
                        onChange={(e) => setFormData({ ...formData, min_amount_rub: Number(e.target.value) })}
                        className="bg-zinc-950 border-zinc-800"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-xs">Макс. сумма (₽)</Label>
                      <Input
                        type="number"
                        value={formData.max_amount_rub}
                        onChange={(e) => setFormData({ ...formData, max_amount_rub: Number(e.target.value) })}
                        className="bg-zinc-950 border-zinc-800"
                      />
                    </div>
                  </div>
                  <div className="mt-2 space-y-2">
                    <Label className="text-xs">Дневной лимит (₽)</Label>
                    <Input
                      type="number"
                      value={formData.daily_limit_rub}
                      onChange={(e) => setFormData({ ...formData, daily_limit_rub: Number(e.target.value) })}
                      className="bg-zinc-950 border-zinc-800"
                    />
                  </div>
                </div>

                {/* Приоритет и активность */}
                <div className="flex items-center justify-between pt-2">
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={formData.is_active}
                      onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
                    />
                    <Label>Активен</Label>
                  </div>
                  <div className="flex items-center gap-2">
                    <Label className="text-xs text-zinc-400">Приоритет:</Label>
                    <Input
                      type="number"
                      value={formData.priority}
                      onChange={(e) => setFormData({ ...formData, priority: Number(e.target.value) })}
                      className="bg-zinc-950 border-zinc-800 w-16 text-center"
                      min="1"
                      max="100"
                    />
                  </div>
                </div>

                <Button type="submit" className="w-full bg-emerald-500 hover:bg-emerald-600">
                  {editingId ? 'Сохранить изменения' : 'Добавить реквизит'}
                </Button>
              </form>
            </DialogContent>
          </Dialog>
        </div>

        {/* Список реквизитов */}
        {details.length === 0 ? (
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="p-8 text-center">
              <CreditCard className="w-12 h-12 mx-auto mb-4 text-zinc-600" />
              <h3 className="text-lg font-medium mb-2">Нет реквизитов</h3>
              <p className="text-zinc-400 mb-4">
                Добавьте платёжные реквизиты, чтобы принимать заказы
              </p>
              <Button onClick={() => setDialogOpen(true)} className="bg-emerald-500 hover:bg-emerald-600">
                <Plus className="w-4 h-4 mr-2" />
                Добавить первый реквизит
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {details.map((detail) => {
              const method = PAYMENT_METHODS[detail.payment_type] || PAYMENT_METHODS.card;
              const Icon = method.icon;
              
              return (
                <Card key={detail.id} className={`bg-zinc-900 border-zinc-800 ${!detail.is_active ? 'opacity-50' : ''}`}>
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className={`w-12 h-12 rounded-xl ${method.bgColor} flex items-center justify-center`}>
                          <Icon className={`w-6 h-6 ${method.color}`} />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className={`font-medium ${method.color}`}>{method.name}</span>
                            {detail.is_active && (
                              <CheckCircle className="w-4 h-4 text-emerald-400" />
                            )}
                          </div>
                          <div className="text-sm text-zinc-400 font-['JetBrains_Mono']">
                            {formatDetailInfo(detail)}
                          </div>
                          <div className="text-xs text-zinc-500 mt-1">
                            {formatRUB(detail.min_amount_rub)} – {formatRUB(detail.max_amount_rub)}
                            {' • '}
                            Использовано: {formatRUB(detail.used_today_rub || 0)} / {formatRUB(detail.daily_limit_rub)}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleEdit(detail)}
                          className="text-zinc-400 hover:text-white"
                        >
                          <Edit className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(detail.id)}
                          className="text-red-400 hover:text-red-300"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}

        {/* Подсказка */}
        <Card className="bg-blue-500/10 border-blue-500/30">
          <CardContent className="p-4">
            <p className="text-sm text-blue-300">
              <strong>Важно:</strong> Добавьте хотя бы один реквизит и пополните баланс USDT, чтобы получать заказы. 
              Реквизиты с высоким приоритетом будут использоваться первыми.
            </p>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
};

export default TraderPaymentDetails;
