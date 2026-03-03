import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';
import { toast } from 'sonner';
import { Plus, Trash2, Save, Percent, CreditCard, Phone, Smartphone, QrCode, Globe, Banknote } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// 7 методов оплаты
const PAYMENT_METHODS = {
  sbp: { name: 'SBP', icon: Phone, color: 'text-blue-400' },
  card: { name: 'Card', icon: CreditCard, color: 'text-emerald-400' },
  sim: { name: 'SIM', icon: Smartphone, color: 'text-orange-400' },
  mono_bank: { name: 'Mono Bank', icon: Banknote, color: 'text-purple-400' },
  sng_sbp: { name: 'SNG-SBP', icon: Globe, color: 'text-cyan-400' },
  sng_card: { name: 'SNG-Card', icon: Globe, color: 'text-teal-400' },
  qr_code: { name: 'QR-code', icon: QrCode, color: 'text-pink-400' },
};

const MerchantMethodCommissions = ({ open, onOpenChange, merchantId, merchantName }) => {
  const [methods, setMethods] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [selectedMethod, setSelectedMethod] = useState('sbp');

  useEffect(() => {
    if (open && merchantId) {
      fetchCommissions();
    }
  }, [open, merchantId]);

  const fetchCommissions = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/admin/merchants/${merchantId}/method-commissions`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setMethods(data.methods || []);
      }
    } catch (error) {
      toast.error('Ошибка загрузки настроек');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/admin/merchants/${merchantId}/method-commissions`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          merchant_id: merchantId,
          methods: methods
        })
      });
      if (res.ok) {
        toast.success('Настройки комиссий сохранены');
        onOpenChange(false);
      } else {
        const data = await res.json();
        toast.error(data.detail || 'Ошибка сохранения');
      }
    } catch (error) {
      toast.error('Ошибка сохранения');
    } finally {
      setSaving(false);
    }
  };

  const addMethod = () => {
    if (methods.find(m => m.payment_method === selectedMethod)) {
      toast.error('Этот метод уже добавлен');
      return;
    }
    
    setMethods([...methods, {
      payment_method: selectedMethod,
      intervals: [{ min_amount: 100, max_amount: 999, percent: 15 }]
    }]);
  };

  const removeMethod = (index) => {
    setMethods(methods.filter((_, i) => i !== index));
  };

  const addInterval = (methodIndex) => {
    const newMethods = [...methods];
    const lastInterval = newMethods[methodIndex].intervals.slice(-1)[0];
    const newMin = lastInterval ? lastInterval.max_amount + 1 : 100;
    
    newMethods[methodIndex].intervals.push({
      min_amount: newMin,
      max_amount: newMin + 4999,
      percent: lastInterval ? Math.max(lastInterval.percent - 0.5, 1) : 10
    });
    setMethods(newMethods);
  };

  const removeInterval = (methodIndex, intervalIndex) => {
    const newMethods = [...methods];
    newMethods[methodIndex].intervals = newMethods[methodIndex].intervals.filter((_, i) => i !== intervalIndex);
    setMethods(newMethods);
  };

  const updateInterval = (methodIndex, intervalIndex, field, value) => {
    const newMethods = [...methods];
    newMethods[methodIndex].intervals[intervalIndex][field] = parseFloat(value) || 0;
    setMethods(newMethods);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-zinc-900 border-zinc-800 max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Percent className="w-5 h-5 text-purple-400" />
            Комиссии по методам оплаты
          </DialogTitle>
          <p className="text-sm text-zinc-400">Мерчант: {merchantName}</p>
        </DialogHeader>

        {loading ? (
          <div className="flex justify-center py-8">
            <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <div className="space-y-4 mt-4">
            {/* Добавить метод */}
            <div className="flex gap-2">
              <Select value={selectedMethod} onValueChange={setSelectedMethod}>
                <SelectTrigger className="bg-zinc-950 border-zinc-800 flex-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-zinc-900 border-zinc-800">
                  {Object.entries(PAYMENT_METHODS).map(([key, method]) => {
                    const Icon = method.icon;
                    const isAdded = methods.some(m => m.payment_method === key);
                    return (
                      <SelectItem 
                        key={key} 
                        value={key}
                        disabled={isAdded}
                        className={isAdded ? 'opacity-50' : ''}
                      >
                        <div className="flex items-center gap-2">
                          <Icon className={`w-4 h-4 ${method.color}`} />
                          {method.name}
                          {isAdded && <span className="text-xs text-zinc-500">(добавлен)</span>}
                        </div>
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
              <Button onClick={addMethod} className="bg-purple-500 hover:bg-purple-600" title="Добавить новый элемент">
                <Plus className="w-4 h-4 mr-2" />
                Добавить
              </Button>
            </div>

            {/* Методы */}
            {methods.length === 0 ? (
              <div className="text-center py-8 text-zinc-500">
                <Percent className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>Методы оплаты не настроены</p>
                <p className="text-sm mt-1">Добавьте методы и настройте интервалы комиссий</p>
              </div>
            ) : (
              methods.map((method, methodIndex) => {
                const methodInfo = PAYMENT_METHODS[method.payment_method];
                const Icon = methodInfo?.icon || CreditCard;
                
                return (
                  <Card key={methodIndex} className="bg-zinc-950 border-zinc-800">
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <CardTitle className="flex items-center gap-2 text-base">
                          <Icon className={`w-5 h-5 ${methodInfo?.color || 'text-zinc-400'}`} />
                          {methodInfo?.name || method.payment_method}
                        </CardTitle>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeMethod(methodIndex)}
                          className="text-red-400 hover:text-red-300"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {/* Заголовки */}
                      <div className="grid grid-cols-4 gap-2 text-xs text-zinc-400 font-medium">
                        <span>От (₽)</span>
                        <span>До (₽)</span>
                        <span>Процент (%)</span>
                        <span></span>
                      </div>
                      
                      {/* Интервалы */}
                      {method.intervals.map((interval, intervalIndex) => (
                        <div key={intervalIndex} className="grid grid-cols-4 gap-2 items-center">
                          <Input
                            type="number"
                            value={interval.min_amount}
                            onChange={(e) => updateInterval(methodIndex, intervalIndex, 'min_amount', e.target.value)}
                            className="bg-zinc-950 border-zinc-700 h-9"
                            min="0"
                          />
                          <Input
                            type="number"
                            value={interval.max_amount}
                            onChange={(e) => updateInterval(methodIndex, intervalIndex, 'max_amount', e.target.value)}
                            className="bg-zinc-950 border-zinc-700 h-9"
                            min="0"
                          />
                          <Input
                            type="number"
                            step="0.1"
                            value={interval.percent}
                            onChange={(e) => updateInterval(methodIndex, intervalIndex, 'percent', e.target.value)}
                            className="bg-zinc-950 border-zinc-700 h-9"
                            min="0"
                            max="100"
                          />
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => removeInterval(methodIndex, intervalIndex)}
                            className="text-red-400 hover:text-red-300 h-9"
                            disabled={method.intervals.length === 1}
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      ))}
                      
                      {/* Кнопка добавить интервал */}
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => addInterval(methodIndex)}
                        className="w-full border-dashed border-zinc-600 text-zinc-400 hover:text-white"
                       title="Добавить новый элемент">
                        <Plus className="w-4 h-4 mr-2" />
                        Добавить интервал
                      </Button>
                    </CardContent>
                  </Card>
                );
              })
            )}

            {/* Пример расчёта */}
            {methods.length > 0 && (
              <Card className="bg-blue-500/10 border-blue-500/30">
                <CardContent className="p-4">
                  <p className="text-sm text-blue-300">
                    <strong>Пример:</strong> Если выбран метод SBP и сумма заявки 3000₽, 
                    система найдёт интервал 1000-5000₽ и применит соответствующий процент 
                    при расчёте комиссии (Тип 1 - мерчант платит).
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        <DialogFooter className="mt-6">
          <Button variant="outline" onClick={() => onOpenChange(false)} className="border-zinc-700">
            Отмена
          </Button>
          <Button onClick={handleSave} disabled={saving} className="bg-purple-500 hover:bg-purple-600" title="Сохранить изменения">
            {saving ? (
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
            ) : (
              <Save className="w-4 h-4 mr-2" />
            )}
            Сохранить
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default MerchantMethodCommissions;
