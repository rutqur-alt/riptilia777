import React, { useState, useEffect } from 'react';
import { useAuth, API } from '@/App';
import axios from 'axios';
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
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from 'sonner';
import { 
  Plus, CreditCard, Smartphone, QrCode, Phone, Trash2, Edit, 
  CheckCircle, Banknote, Globe, ArrowLeft, Loader2, MoreVertical
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { PAYMENT_METHODS, PAYMENT_METHOD_OPTIONS } from '@/config/paymentMethods';

// Используем единый конфиг методов
const METHODS = Object.fromEntries(
  Object.entries(PAYMENT_METHODS).map(([key, val]) => [
    key, 
    { name: val.shortName, icon: val.emoji, color: val.textClass, bg: val.bgClass }
  ])
);


export default function TraderPaymentDetails() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [details, setDetails] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [saving, setSaving] = useState(false);
  
  const api = axios.create({ baseURL: API, headers: { Authorization: `Bearer ${token}` } });
  
  const emptyForm = {
    payment_type: 'sbp', card_number: '', phone_number: '', qr_link: '',
    bank_name: '', operator_name: '', holder_name: '', comment: '',
    priority: 10, is_active: true,
  };
  const [form, setForm] = useState(emptyForm);

  useEffect(() => { load(); }, []);

  const load = async () => {
    try {
      const res = await api.get('/trader/payment-details');
      setDetails(res.data);
    } catch { toast.error('Ошибка загрузки'); }
    finally { setLoading(false); }
  };

  const save = async (e) => {
    e.preventDefault();
    const t = form.payment_type;
    
    if ((t === 'sbp' || t === 'sng_sbp') && (!form.phone_number || !form.bank_name)) {
      toast.error('Заполните телефон и банк'); return;
    }
    if ((t === 'card' || t === 'sng_card') && (!form.card_number || !form.bank_name)) {
      toast.error('Заполните карту и банк'); return;
    }
    if (t === 'sim' && (!form.phone_number || !form.operator_name)) {
      toast.error('Заполните телефон и оператора'); return;
    }
    if (t === 'qr_code' && !form.qr_link) {
      toast.error('Вставьте ссылку QR'); return;
    }
    
    setSaving(true);
    try {
      if (editingId) {
        await api.put(`/trader/payment-details/${editingId}`, form);
        toast.success('Сохранено');
      } else {
        await api.post('/trader/payment-details', form);
        toast.success('Добавлено');
      }
      setDialogOpen(false);
      setForm(emptyForm);
      setEditingId(null);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || 'Ошибка'); }
    finally { setSaving(false); }
  };

  const del = async (id) => {
    if (!confirm('Удалить?')) return;
    try { await api.delete(`/trader/payment-details/${id}`); toast.success('Удалено'); load(); }
    catch { toast.error('Ошибка'); }
  };

  const edit = (d) => {
    setForm({
      payment_type: d.payment_type, card_number: d.card_number || '', phone_number: d.phone_number || '',
      qr_link: d.qr_link || d.qr_data || '', bank_name: d.bank_name || '', operator_name: d.operator_name || '',
      holder_name: d.holder_name || '', comment: d.comment || '',
      priority: d.priority, is_active: d.is_active,
    });
    setEditingId(d.id);
    setDialogOpen(true);
  };

  const getInfo = (d) => {
    const t = d.payment_type;
    if (t === 'sbp' || t === 'sng_sbp') return [d.phone_number, d.bank_name, d.holder_name].filter(Boolean).join(' • ');
    if (t === 'card' || t === 'sng_card') return [d.card_number?.replace(/(\d{4})/g, '$1 ').trim(), d.bank_name].filter(Boolean).join(' • ');
    if (t === 'sim') return [d.phone_number, d.operator_name].filter(Boolean).join(' • ');
    if (t === 'mono_bank') return [d.phone_number || d.card_number, d.bank_name].filter(Boolean).join(' • ');
    if (t === 'qr_code') return (d.qr_link || d.qr_data || '').slice(0, 40) + '...';
    return 'Реквизит';
  };

  if (loading) return (
    <div className="min-h-screen bg-gradient-to-b from-zinc-950 to-zinc-900 flex items-center justify-center">
      <Loader2 className="w-8 h-8 text-emerald-500 animate-spin" />
    </div>
  );

  return (
    <div className="min-h-screen bg-gradient-to-b from-zinc-950 to-zinc-900">
      {/* Header */}
      <div className="sticky top-0 z-10 bg-zinc-950/80 backdrop-blur-xl border-b border-white/5 px-4 py-4 safe-top">
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => navigate('/trader')} className="p-2 rounded-xl bg-white/5 hover:bg-white/10 transition-colors">
              <ArrowLeft className="w-5 h-5 text-zinc-400" />
            </button>
            <div>
              <h1 className="text-lg font-bold text-white">Реквизиты</h1>
              <p className="text-xs text-zinc-500">{details.length} реквизитов</p>
            </div>
          </div>
          <Button onClick={() => { setForm(emptyForm); setEditingId(null); setDialogOpen(true); }} className="bg-emerald-500 hover:bg-emerald-600 h-10 px-4">
            <Plus className="w-4 h-4 mr-2" /> Добавить
          </Button>
        </div>
      </div>

      <div className="px-4 py-4 max-w-2xl mx-auto space-y-3 pb-safe">
        {details.length === 0 ? (
          <div className="bg-zinc-900/50 rounded-2xl p-8 text-center border border-white/5">
            <CreditCard className="w-12 h-12 mx-auto mb-4 text-zinc-600" />
            <h3 className="text-lg font-medium text-white mb-2">Нет реквизитов</h3>
            <p className="text-zinc-500 text-sm mb-4">Добавьте реквизиты для приёма платежей</p>
            <Button onClick={() => setDialogOpen(true)} className="bg-emerald-500 hover:bg-emerald-600">
              <Plus className="w-4 h-4 mr-2" /> Добавить первый
            </Button>
          </div>
        ) : (
          details.map(d => {
            const m = METHODS[d.payment_type] || METHODS.card;
            return (
              <div key={d.id} className={`bg-zinc-900/50 rounded-2xl p-4 border border-white/5 ${!d.is_active ? 'opacity-50' : ''}`}>
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    <div className={`w-12 h-12 rounded-xl ${m.bg} flex items-center justify-center text-2xl shrink-0`}>
                      {m.icon}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`font-medium ${m.color}`}>{m.name}</span>
                        {d.is_active && <CheckCircle className="w-4 h-4 text-emerald-400" />}
                      </div>
                      <p className="text-sm text-zinc-400 font-mono truncate">{getInfo(d)}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 ml-2">
                    <button onClick={() => edit(d)} className="p-2 rounded-lg hover:bg-white/5 transition-colors">
                      <Edit className="w-4 h-4 text-zinc-400" />
                    </button>
                    <button onClick={() => del(d.id)} className="p-2 rounded-lg hover:bg-red-500/10 transition-colors">
                      <Trash2 className="w-4 h-4 text-red-400" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })
        )}

        {/* Tip */}
        <div className="bg-blue-500/10 border border-blue-500/20 rounded-2xl p-4">
          <p className="text-sm text-blue-300">
            <strong>💡 Совет:</strong> Реквизиты с высоким приоритетом используются первыми. 
            Пополните баланс USDT чтобы получать заказы.
          </p>
        </div>
      </div>

      {/* Dialog */}
      <Dialog open={dialogOpen} onOpenChange={(o) => { setDialogOpen(o); if (!o) { setForm(emptyForm); setEditingId(null); } }}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md mx-4 max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-white">{editingId ? 'Редактировать' : 'Добавить'} реквизит</DialogTitle>
          </DialogHeader>
          
          <form onSubmit={save} className="space-y-4 mt-4">
            <div>
              <Label className="text-zinc-400">Метод оплаты</Label>
              <Select value={form.payment_type} onValueChange={v => setForm({ ...form, payment_type: v })}>
                <SelectTrigger className="bg-zinc-800 border-zinc-700 mt-1"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-zinc-800 border-zinc-700">
                  {Object.entries(METHODS).map(([k, m]) => (
                    <SelectItem key={k} value={k}>
                      <span className="flex items-center gap-2">{m.icon} {m.name}</span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Dynamic Fields */}
            {(form.payment_type === 'sbp' || form.payment_type === 'sng_sbp') && (
              <>
                <div><Label className="text-zinc-400">Телефон *</Label><Input value={form.phone_number} onChange={e => setForm({ ...form, phone_number: e.target.value })} placeholder="+7 999 123 45 67" className="bg-zinc-800 border-zinc-700 mt-1 font-mono" /></div>
                <div><Label className="text-zinc-400">Банк *</Label><Input value={form.bank_name} onChange={e => setForm({ ...form, bank_name: e.target.value })} placeholder="Сбербанк, Тинькофф..." className="bg-zinc-800 border-zinc-700 mt-1" /></div>
                <div><Label className="text-zinc-400">ФИО (опц.)</Label><Input value={form.holder_name} onChange={e => setForm({ ...form, holder_name: e.target.value })} placeholder="Иван И." className="bg-zinc-800 border-zinc-700 mt-1" /></div>
              </>
            )}
            
            {(form.payment_type === 'card' || form.payment_type === 'sng_card') && (
              <>
                <div><Label className="text-zinc-400">Номер карты *</Label><Input value={form.card_number} onChange={e => setForm({ ...form, card_number: e.target.value.replace(/\s/g, '') })} placeholder="2200 0000 0000 0000" className="bg-zinc-800 border-zinc-700 mt-1 font-mono" /></div>
                <div><Label className="text-zinc-400">Банк *</Label><Input value={form.bank_name} onChange={e => setForm({ ...form, bank_name: e.target.value })} placeholder="Сбербанк..." className="bg-zinc-800 border-zinc-700 mt-1" /></div>
                <div><Label className="text-zinc-400">ФИО (опц.)</Label><Input value={form.holder_name} onChange={e => setForm({ ...form, holder_name: e.target.value })} placeholder="IVAN PETROV" className="bg-zinc-800 border-zinc-700 mt-1" /></div>
              </>
            )}
            
            {form.payment_type === 'sim' && (
              <>
                <div><Label className="text-zinc-400">Телефон *</Label><Input value={form.phone_number} onChange={e => setForm({ ...form, phone_number: e.target.value })} placeholder="+7 999 123 45 67" className="bg-zinc-800 border-zinc-700 mt-1 font-mono" /></div>
                <div><Label className="text-zinc-400">Оператор *</Label><Input value={form.operator_name} onChange={e => setForm({ ...form, operator_name: e.target.value })} placeholder="МТС, Билайн..." className="bg-zinc-800 border-zinc-700 mt-1" /></div>
              </>
            )}
            
            {form.payment_type === 'mono_bank' && (
              <>
                <div><Label className="text-zinc-400">Телефон</Label><Input value={form.phone_number} onChange={e => setForm({ ...form, phone_number: e.target.value })} placeholder="+7 999 123 45 67" className="bg-zinc-800 border-zinc-700 mt-1 font-mono" /></div>
                <div><Label className="text-zinc-400">Или карта</Label><Input value={form.card_number} onChange={e => setForm({ ...form, card_number: e.target.value })} placeholder="2200..." className="bg-zinc-800 border-zinc-700 mt-1 font-mono" /></div>
                <div><Label className="text-zinc-400">Банк (опц.)</Label><Input value={form.bank_name} onChange={e => setForm({ ...form, bank_name: e.target.value })} className="bg-zinc-800 border-zinc-700 mt-1" /></div>
              </>
            )}
            
            {form.payment_type === 'qr_code' && (
              <div><Label className="text-zinc-400">Ссылка QR *</Label><Input value={form.qr_link} onChange={e => setForm({ ...form, qr_link: e.target.value })} placeholder="https://qr.nspk.ru/..." className="bg-zinc-800 border-zinc-700 mt-1 font-mono text-xs" /></div>
            )}


            {/* Active & Priority */}
            <div className="flex items-center justify-between pt-2">
              <div className="flex items-center gap-2">
                <Switch checked={form.is_active} onCheckedChange={c => setForm({ ...form, is_active: c })} />
                <Label className="text-zinc-400">Активен</Label>
              </div>
              <div className="flex items-center gap-2">
                <Label className="text-zinc-500 text-xs">Приоритет:</Label>
                <Input type="number" value={form.priority} onChange={e => setForm({ ...form, priority: Number(e.target.value) })} className="bg-zinc-800 border-zinc-700 w-16 text-center" min="1" max="100" />
              </div>
            </div>

            <Button type="submit" disabled={saving} className="w-full bg-emerald-500 hover:bg-emerald-600 h-12">
              {saving ? <Loader2 className="w-5 h-5 animate-spin" /> : (editingId ? 'Сохранить' : 'Добавить')}
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
