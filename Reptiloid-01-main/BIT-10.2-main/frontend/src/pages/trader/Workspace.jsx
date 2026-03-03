import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import DashboardLayout from '@/components/DashboardLayout';
import { api, formatUSDT, formatRUB, formatDate, getStatusLabel, getStatusClass } from '@/lib/auth';
import { useBalance } from '@/contexts/BalanceContext';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { toast } from 'sonner';
import CopyableOrderId from '@/components/CopyableOrderId';
import {
  Clock, CheckCircle, AlertTriangle, RefreshCw, User, Zap, ArrowRight, MessageCircle, XCircle, Edit3, Power, Settings, ChevronDown, Check
} from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const TraderWorkspace = () => {
  const { refreshBalance } = useBalance();
  const [orders, setOrders] = useState([]);
  const [availableOrders, setAvailableOrders] = useState([]);
  const [disputes, setDisputes] = useState([]);
  const [paymentDetails, setPaymentDetails] = useState([]);
  const [loading, setLoading] = useState(true);
  const [processingId, setProcessingId] = useState(null);
  const [hasDeposit, setHasDeposit] = useState(true);
  const [hasPaymentDetails, setHasPaymentDetails] = useState(true);
  const [traderBalance, setTraderBalance] = useState(0);
  
  // Режим работы трейдера
  const [isAvailable, setIsAvailable] = useState(true);
  const [togglingAvailable, setTogglingAvailable] = useState(false);
  
  // Фильтры по сумме и методам оплаты (мультиселект)
  const [minAmount, setMinAmount] = useState('');
  const [maxAmount, setMaxAmount] = useState('');
  const [selectedPaymentMethods, setSelectedPaymentMethods] = useState([]); // Массив выбранных методов
  const [showMethodsDropdown, setShowMethodsDropdown] = useState(false);
  const [filtersApplied, setFiltersApplied] = useState(false);
  const [traderLimits, setTraderLimits] = useState({ min_amount_rub: 100, max_amount_rub: 500000 });
  const methodsDropdownRef = useRef(null);
  
  // Все доступные методы оплаты
  const allPaymentMethods = [
    { value: 'card', label: 'Карта' },
    { value: 'sbp', label: 'СБП' },
    { value: 'sim', label: 'SIM' },
    { value: 'mono_bank', label: 'Mono' },
    { value: 'sng_sbp', label: 'СНГ-СБП' },
    { value: 'sng_card', label: 'СНГ-Карта' },
    { value: 'qr_code', label: 'QR' },
  ];
  
  // Модальное окно настройки лимитов
  const [showLimitsModal, setShowLimitsModal] = useState(false);
  const [editMinLimit, setEditMinLimit] = useState('');
  const [editMaxLimit, setEditMaxLimit] = useState('');
  const [savingLimits, setSavingLimits] = useState(false);
  
  // Модальное окно для принятия заказа
  const [showAcceptModal, setShowAcceptModal] = useState(false);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [acceptMode, setAcceptMode] = useState('auto'); // 'auto' или 'manual'
  const [selectedDetailId, setSelectedDetailId] = useState(null);
  const [manualText, setManualText] = useState('');

  // Загрузка профиля трейдера для получения is_available и лимитов
  const fetchTraderProfile = async () => {
    try {
      const res = await api.get('/trader/profile');
      setIsAvailable(res.data.is_available !== false);
      setTraderLimits({
        min_amount_rub: res.data.min_deal_amount_rub || 100,
        max_amount_rub: res.data.max_deal_amount_rub || 500000
      });
    } catch (error) {
      console.error('Error fetching trader profile:', error);
    }
  };

  // Переключение режима работы
  const toggleAvailable = async () => {
    setTogglingAvailable(true);
    try {
      const newValue = !isAvailable;
      await api.put('/trader/profile', null, { params: { is_available: newValue } });
      setIsAvailable(newValue);
      toast.success(newValue ? 'Режим работы включён' : 'Режим работы выключен');
    } catch (error) {
      toast.error('Ошибка переключения режима');
      console.error('Error toggling available:', error);
    } finally {
      setTogglingAvailable(false);
    }
  };

  // Открытие модального окна настройки лимитов
  const openLimitsModal = () => {
    setEditMinLimit(traderLimits.min_amount_rub.toString());
    setEditMaxLimit(traderLimits.max_amount_rub.toString());
    setShowLimitsModal(true);
  };

  // Сохранение лимитов
  const saveLimits = async () => {
    const minVal = parseFloat(editMinLimit) || 100;
    const maxVal = parseFloat(editMaxLimit) || 500000;
    
    if (minVal >= maxVal) {
      toast.error('Минимальный лимит должен быть меньше максимального');
      return;
    }
    
    if (minVal < 100) {
      toast.error('Минимальный лимит не может быть меньше 100₽');
      return;
    }
    
    setSavingLimits(true);
    try {
      await api.put('/trader/profile', null, { 
        params: { 
          min_deal_amount_rub: minVal,
          max_deal_amount_rub: maxVal
        } 
      });
      setTraderLimits({ min_amount_rub: minVal, max_amount_rub: maxVal });
      setShowLimitsModal(false);
      toast.success('Лимиты сохранены');
      // Обновляем список заявок с новыми лимитами
      fetchAvailableOrders();
    } catch (error) {
      toast.error('Ошибка сохранения лимитов');
      console.error('Error saving limits:', error);
    } finally {
      setSavingLimits(false);
    }
  };

  useEffect(() => {
    fetchOrders();
    fetchAvailableOrders();
    fetchDisputes();
    fetchPaymentDetails();
    fetchTraderProfile();
    
    const interval = setInterval(() => {
      fetchOrders();
      fetchAvailableOrders();
      fetchDisputes();
    }, 5000);
    
    return () => clearInterval(interval);
  }, [minAmount, maxAmount, selectedPaymentMethods]);

  // Закрытие дропдауна методов оплаты при клике вне
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (methodsDropdownRef.current && !methodsDropdownRef.current.contains(event.target)) {
        setShowMethodsDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const fetchOrders = async () => {
    try {
      const res = await api.get('/trader/orders');
      setOrders(res.data.orders || []);
    } catch (error) {
      console.error('Error fetching orders:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchAvailableOrders = async () => {
    try {
      const params = {};
      if (minAmount && parseFloat(minAmount) > 0) {
        params.min_amount = parseFloat(minAmount);
      }
      if (maxAmount && parseFloat(maxAmount) > 0) {
        params.max_amount = parseFloat(maxAmount);
      }
      // Передаём массив методов как строку через запятую
      if (selectedPaymentMethods.length > 0) {
        params.payment_methods = selectedPaymentMethods.join(',');
      }
      const res = await api.get('/trader/available-orders', { params });
      const orders = res.data.orders || [];
      const balance = res.data.available_balance || res.data.balance || 0;
      const traderTypes = res.data.trader_payment_types || [];
      
      // Заказы уже приходят с can_accept и reason из бэкенда
      setAvailableOrders(orders);
      setHasDeposit(res.data.has_deposit !== false);
      setHasPaymentDetails(res.data.has_payment_details !== false || traderTypes.length > 0);
      setTraderBalance(balance);
      setFiltersApplied(!!(params.min_amount || params.max_amount || selectedPaymentMethods.length > 0));
      
      // Обновляем лимиты если пришли
      if (res.data.trader_limits) {
        setTraderLimits(res.data.trader_limits);
      }
    } catch (error) {
      console.error('Error fetching available orders:', error);
    }
  };

  const clearFilters = () => {
    setMinAmount('');
    setMaxAmount('');
    setSelectedPaymentMethods([]);
  };

  // Toggle метода оплаты
  const togglePaymentMethod = (method) => {
    setSelectedPaymentMethods(prev => {
      if (prev.includes(method)) {
        return prev.filter(m => m !== method);
      } else {
        return [...prev, method];
      }
    });
  };

  const fetchDisputes = async () => {
    try {
      const res = await api.get('/trader/disputes');
      setDisputes(res.data.disputes || []);
    } catch (error) {
      console.error('Error fetching disputes:', error);
    }
  };

  const fetchPaymentDetails = async () => {
    try {
      const res = await api.get('/trader/payment-details');
      setPaymentDetails(res.data || []);
    } catch (error) {
      console.error('Error fetching payment details:', error);
    }
  };

  // Открыть модальное окно принятия заказа
  const openAcceptModal = (order) => {
    setSelectedOrder(order);
    // Фильтруем реквизиты по типу метода оплаты заказа (учитываем requested_payment_method)
    const requestedMethod = order.requested_payment_method || order.payment_method;
    const matchingDetails = paymentDetails.filter(
      pd => pd.is_active && (!requestedMethod || pd.payment_type === requestedMethod)
    );
    setAcceptMode(matchingDetails.length > 0 ? 'auto' : 'manual');
    setSelectedDetailId(matchingDetails.length > 0 ? matchingDetails[0].id : null);
    setManualText('');
    setShowAcceptModal(true);
  };

  // Получить реквизиты подходящего типа для заказа
  const getMatchingDetails = () => {
    if (!selectedOrder) return [];
    const requestedMethod = selectedOrder.requested_payment_method || selectedOrder.payment_method;
    return paymentDetails.filter(
      pd => pd.is_active && (!requestedMethod || pd.payment_type === requestedMethod)
    );
  };

  // Принять заказ (взять в работу)
  const acceptOrder = async () => {
    if (!selectedOrder) return;
    
    // Для новых заявок (waiting_requisites) используем новый endpoint
    if (selectedOrder.status === 'waiting_requisites') {
      // Проверяем режим - автоматический или ручной
      if (acceptMode === 'auto' && !selectedDetailId) {
        toast.error('Выберите реквизиты для оплаты');
        return;
      }
      if (acceptMode === 'manual' && !manualText.trim()) {
        toast.error('Введите реквизиты для оплаты');
        return;
      }
      if (acceptMode === 'manual' && manualText.length > 500) {
        toast.error('Максимум 500 символов');
        return;
      }
      
      setProcessingId(selectedOrder.id);
      try {
        if (acceptMode === 'manual') {
          // Ручной ввод реквизитов
          await api.post(`/trader/take-order/${selectedOrder.id}`, { manual_text: manualText.trim() });
        } else {
          // Выбор из сохранённых реквизитов
          await api.post(`/trader/take-order/${selectedOrder.id}?payment_detail_id=${selectedDetailId}`);
        }
        toast.success('Заявка взята! Реквизиты отправлены покупателю.');
        setShowAcceptModal(false);
        setManualText('');
        fetchOrders();
        fetchAvailableOrders();
        refreshBalance();
      } catch (error) {
        const message = error.response?.data?.detail || error.message || 'Ошибка';
        toast.error(message);
      } finally {
        setProcessingId(null);
      }
      return;
    }
    
    // Старая логика для других статусов
    if (acceptMode === 'manual' && !manualText.trim()) {
      toast.error('Введите реквизиты для оплаты');
      return;
    }
    
    if (acceptMode === 'manual' && manualText.length > 200) {
      toast.error('Максимум 200 символов');
      return;
    }

    setProcessingId(selectedOrder.id);
    try {
      const payload = acceptMode === 'manual' 
        ? { manual_text: manualText.trim() }
        : { payment_detail_id: selectedDetailId };
      
      await api.post(`/trader/orders/${selectedOrder.id}/accept`, payload);
      toast.success('Заявка принята! Ваши реквизиты отправлены покупателю.');
      setShowAcceptModal(false);
      fetchOrders();
      fetchAvailableOrders();
      refreshBalance(); // Обновляем баланс (USDT заблокированы)
    } catch (error) {
      const message = error.response?.data?.detail || error.message || 'Ошибка принятия заявки';
      toast.error(message);
    } finally {
      setProcessingId(null);
    }
  };

  const confirmPayment = async (orderId) => {
    setProcessingId(orderId);
    try {
      const res = await api.post(`/trader/orders/${orderId}/confirm`);
      toast.success('Сделка подтверждена! Комиссия зачислена на баланс.');
      // Обновляем список заказов и баланс
      await fetchOrders();
      refreshBalance(); // Обновляем баланс в хедере
      setProcessingId(null);
    } catch (error) {
      const message = error.response?.data?.detail || error.message || 'Ошибка подтверждения';
      toast.error(message);
      setProcessingId(null);
    }
  };

  const openDispute = async (orderId) => {
    setProcessingId(orderId);
    try {
      await api.post(`/trader/orders/${orderId}/dispute`, {
        order_id: orderId,
        reason: 'Оплата не поступила'
      });
      toast.success('Спор открыт. Перейдите в чат для общения с модератором.');
      fetchOrders();
      fetchDisputes();
    } catch (error) {
      const message = error.response?.data?.detail || error.message || 'Ошибка открытия спора';
      toast.error(message);
    } finally {
      setProcessingId(null);
    }
  };

  const cancelOrder = async (orderId) => {
    if (!window.confirm('Вы уверены, что хотите отменить заказ? Покупатель не оплатил.')) return;
    
    setProcessingId(orderId);
    try {
      await api.post(`/trader/orders/${orderId}/cancel`);
      toast.success('Заказ отменён');
      fetchOrders();
      fetchAvailableOrders();
      refreshBalance(); // Обновляем баланс (USDT разблокированы)
    } catch (error) {
      const message = error.response?.data?.detail || error.message || 'Ошибка отмены';
      toast.error(message);
    } finally {
      setProcessingId(null);
    }
  };

  // Завершить спор в пользу покупателя (подтвердить оплату из спора)
  const handleConfirmForBuyer = async (orderId) => {
    if (!window.confirm('Подтвердить получение оплаты? Спор будет закрыт, USDT переведены мерчанту.')) return;
    
    setProcessingId(orderId);
    try {
      // Находим спор по order_id
      const disputeForOrder = disputes.find(d => d.order_id === orderId);
      
      if (disputeForOrder) {
        // Закрываем спор через endpoint confirm-payment
        await api.post(`/disputes/${disputeForOrder.id}/confirm-payment`);
        toast.success('Платёж подтверждён! Спор закрыт.');
      } else {
        // Если спора нет в локальном state - пробуем найти спор на сервере
        const disputesRes = await api.get('/trader/disputes');
        const allDisputes = disputesRes.data.disputes || [];
        const serverDispute = allDisputes.find(d => d.order_id === orderId);
        
        if (serverDispute) {
          await api.post(`/disputes/${serverDispute.id}/confirm-payment`);
          toast.success('Платёж подтверждён! Спор закрыт.');
        } else {
          // Если спора нет - просто подтверждаем заказ
          await api.post(`/trader/orders/${orderId}/confirm`);
          toast.success('Сделка подтверждена! Комиссия зачислена на баланс.');
        }
      }
      
      await fetchOrders();
      await fetchDisputes();
      refreshBalance();
    } catch (error) {
      const message = error.response?.data?.detail || error.message || 'Ошибка подтверждения';
      toast.error(message);
    } finally {
      setProcessingId(null);
    }
  };

  const resolveDisputeForBuyer = async (orderId) => {
    if (!window.confirm('Вы уверены, что хотите закрыть спор в пользу покупателя? Комиссия будет начислена.')) return;
    
    setProcessingId(orderId);
    try {
      await api.post(`/trader/orders/${orderId}/resolve-for-buyer`);
      toast.success('Спор закрыт в пользу покупателя. Комиссия начислена.');
      fetchOrders();
      fetchDisputes();
      refreshBalance();
    } catch (error) {
      const message = error.response?.data?.detail || error.message || 'Ошибка закрытия спора';
      toast.error(message);
    } finally {
      setProcessingId(null);
    }
  };

  const canCancelOrder = (order) => {
    if (!order.cancel_available_at) return false;
    const cancelAt = new Date(order.cancel_available_at);
    return new Date() >= cancelAt;
  };

  const getTimeUntilCancel = (order) => {
    if (!order.cancel_available_at) return null;
    const cancelAt = new Date(order.cancel_available_at);
    const now = new Date();
    const diff = Math.max(0, Math.floor((cancelAt - now) / 1000));
    if (diff === 0) return null;
    const mins = Math.floor(diff / 60);
    const secs = diff % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const activeOrders = orders.filter(o => 
    ['waiting_buyer_confirmation', 'waiting_trader_confirmation', 'paid'].includes(o.status)
  );
  const disputedOrders = orders.filter(o => o.status === 'disputed');
  const completedOrders = orders.filter(o => o.status === 'completed').slice(0, 10);
  const openDisputes = disputes.filter(d => d.status === 'open');

  // Получить название метода оплаты
  const getPaymentMethodName = (method) => {
    const names = {
      'card': 'Карта',
      'sbp': 'СБП',
      'sim': 'SIM',
      'mono_bank': 'Mono',
      'sng_sbp': 'СНГ-СБП',
      'sng_card': 'СНГ-Карта',
      'qr_code': 'QR'
    };
    return names[method] || method || 'Любой';
  };

  // Форматирование реквизитов для отображения в селекте
  const formatPaymentDetail = (pd) => {
    const type = pd.payment_type;
    if (type === 'card') return `Карта: ${pd.card_number?.slice(-4) || '****'} (${pd.bank_name || 'банк'})`;
    if (type === 'sbp') return `СБП: ${pd.phone_number || '***'} (${pd.bank_name || 'банк'})`;
    if (type === 'sim') return `SIM: ${pd.phone_number || '***'} (${pd.operator_name || 'оператор'})`;
    if (type === 'mono_bank') return `Mono Bank: ${pd.card_number || pd.phone_number || '***'}`;
    if (type === 'sng_sbp') return `СНГ-СБП: ${pd.phone_number || '***'} (${pd.bank_name || 'банк'})`;
    if (type === 'sng_card') return `СНГ-Карта: ${pd.card_number?.slice(-4) || '****'} (${pd.bank_name || 'банк'})`;
    if (type === 'qr_code') return `QR-код: ${pd.qr_link?.substring(0, 20) || 'ссылка'}...`;
    return type;
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
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold font-['Chivo']">Рабочий стол</h1>
            <p className="text-zinc-400 text-sm">Управление активными сделками</p>
          </div>
          <div className="flex items-center gap-3">
            {/* Toggle режима работы */}
            <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors ${
              isAvailable 
                ? 'bg-emerald-500/10 border-emerald-500/30' 
                : 'bg-red-500/10 border-red-500/30'
            }`}>
              <Power className={`w-4 h-4 ${isAvailable ? 'text-emerald-400' : 'text-red-400'}`} />
              <span className={`text-sm font-medium ${isAvailable ? 'text-emerald-400' : 'text-red-400'}`}>
                {isAvailable ? 'На линии' : 'Офлайн'}
              </span>
              <Switch
                checked={isAvailable}
                onCheckedChange={toggleAvailable}
                disabled={togglingAvailable}
                data-testid="toggle-available-switch"
                className="data-[state=checked]:bg-emerald-500"
              />
            </div>
            <Button variant="outline" onClick={() => { fetchOrders(); fetchAvailableOrders(); fetchDisputes(); }} className="border-zinc-800">
              <RefreshCw className="w-4 h-4 mr-2" />
              Обновить
            </Button>
          </div>
        </div>

        {/* Предупреждение если режим работы выключен */}
        {!isAvailable && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-red-400 shrink-0" />
            <div className="flex-1">
              <p className="text-red-400 font-medium">Режим работы выключен</p>
              <p className="text-zinc-400 text-sm">Вы не будете получать новые заявки пока режим выключен</p>
            </div>
            <Button 
              onClick={toggleAvailable}
              disabled={togglingAvailable}
              className="bg-emerald-500 hover:bg-emerald-600"
              data-testid="enable-work-mode-btn"
            >
              <Power className="w-4 h-4 mr-2" />
              Включить
            </Button>
          </div>
        )}

        {/* Открытые споры - отдельный блок сверху */}
        {disputedOrders.length > 0 && (
          <div className="bg-gradient-to-r from-orange-500/10 to-red-500/10 border border-orange-500/30 rounded-xl p-6">
            <div className="flex items-center gap-2 mb-4">
              <AlertTriangle className="w-5 h-5 text-orange-400" />
              <h2 className="text-lg font-semibold">
                Открытые споры
                <span className="ml-2 px-2 py-0.5 bg-orange-500 text-white text-sm rounded-full">
                  {disputedOrders.length}
                </span>
              </h2>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {disputedOrders.map((order) => (
                <Card key={order.id} className="bg-zinc-900 border-orange-500/50">
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between mb-3">
                      <CopyableOrderId orderId={order.id} size="small" />
                      <span className="px-2 py-1 bg-orange-500/20 text-orange-400 rounded text-xs">
                        Спор
                      </span>
                    </div>

                    <div className="font-['JetBrains_Mono'] text-xl font-bold mb-1">
                      {formatRUB(order.amount_rub || 0)}
                    </div>
                    <div className="text-xs text-zinc-500 mb-2">
                      ≈ {formatUSDT(order.amount_usdt || 0)} USDT
                    </div>
                    
                    <div className="text-xs text-zinc-500 mb-4">
                      Создан: {formatDate(order.created_at)}
                    </div>

                    <div className="space-y-2">
                      <Link to={`/trader/disputes/${order.dispute_id}`}>
                        <Button variant="outline" className="w-full border-orange-500/50 text-orange-400 hover:bg-orange-500/10">
                          <MessageCircle className="w-4 h-4 mr-2" />
                          Чат спора
                        </Button>
                      </Link>
                      <Button 
                        onClick={() => handleConfirmForBuyer(order.id)}
                        disabled={processingId === order.id}
                        className="w-full bg-emerald-500 hover:bg-emerald-600"
                      >
                        <CheckCircle className="w-4 h-4 mr-2" />
                        Завершить в пользу покупателя
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* Двухколоночный layout: Активные сделки слева, Новые заявки справа */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* ЛЕВАЯ КОЛОНКА: Мои активные сделки */}
          <div>
            <h2 className="text-lg font-semibold mb-4">
              Мои активные сделки 
              <span className="text-zinc-500 font-normal ml-2">({activeOrders.length})</span>
            </h2>
            
            {activeOrders.length === 0 ? (
              <Card className="bg-zinc-900 border-zinc-800">
                <CardContent className="p-12 text-center">
                  <Clock className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
                  <h3 className="text-lg font-medium mb-2">Нет активных сделок</h3>
                  <p className="text-zinc-400 text-sm">
                    {availableOrders.length > 0 
                      ? 'Примите заявку справа, чтобы начать сделку'
                      : 'Новые заявки появятся автоматически'}
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-4">
                {activeOrders.map((order) => (
                  <Card 
                    key={order.id} 
                    className={`bg-zinc-900 border-zinc-800 ${
                      order.status === 'waiting_trader_confirmation' ? 'border-orange-500/50 animate-pulse-slow' : 
                      order.status === 'disputed' ? 'border-red-500/50' : ''
                    }`}
                  >
                    <CardContent className="p-5">
                      <div className="flex items-center justify-between mb-4">
                        <CopyableOrderId orderId={order.id} size="small" />
                        <span className={`px-2 py-1 rounded text-xs border ${getStatusClass(order.status)}`}>
                          {getStatusLabel(order.status)}
                        </span>
                      </div>

                      <div className="mb-4">
                        <div className="font-['JetBrains_Mono'] text-2xl font-bold mb-1">
                          {formatRUB(order.amount_rub)}
                        </div>
                        <div className="text-sm text-zinc-400">
                          ≈ {formatUSDT(order.amount_usdt)} USDT
                        </div>
                      </div>

                      {order.buyer_contact && (
                        <div className="flex items-center gap-2 text-sm text-zinc-400 mb-4 p-3 bg-zinc-800 rounded-lg">
                          <User className="w-4 h-4" />
                          <span>{order.buyer_contact}</span>
                        </div>
                      )}

                      <div className="text-xs text-zinc-500 mb-4">
                        Создано: {formatDate(order.created_at)}
                      </div>

                      {order.status === 'waiting_trader_confirmation' && (
                        <div className="space-y-2">
                          <div className="flex gap-2">
                            <Button
                              onClick={() => confirmPayment(order.id)}
                              disabled={processingId === order.id}
                              className="flex-1 bg-emerald-500 hover:bg-emerald-600"
                            >
                              <CheckCircle className="w-4 h-4 mr-2" />
                              {processingId === order.id ? 'Обработка...' : 'Подтвердить'}
                            </Button>
                            <Button
                              onClick={() => openDispute(order.id)}
                              disabled={processingId === order.id}
                              variant="outline"
                              className="border-orange-500/50 text-orange-400 hover:bg-orange-500/10"
                            >
                              <AlertTriangle className="w-4 h-4" />
                            </Button>
                          </div>
                          
                          <Button
                            onClick={() => cancelOrder(order.id)}
                            disabled={processingId === order.id || !canCancelOrder(order)}
                            variant="outline"
                            className={`w-full ${
                              canCancelOrder(order)
                                ? 'border-red-500/50 text-red-400 hover:bg-red-500/10'
                                : 'border-zinc-700 text-zinc-500 cursor-not-allowed'
                            }`}
                          >
                            <XCircle className="w-4 h-4 mr-2" />
                            {canCancelOrder(order) 
                              ? 'Отменить (не получил оплату)'
                              : `Отмена через ${getTimeUntilCancel(order) || '...'}`
                            }
                          </Button>
                        </div>
                      )}

                      {order.status === 'waiting_buyer_confirmation' && (
                        <div className="space-y-3">
                          <div className="text-center text-sm text-zinc-400 p-3 bg-zinc-800 rounded-lg">
                            <Clock className="w-4 h-4 inline-block mr-2" />
                            Ожидание оплаты покупателем
                          </div>
                          
                          <Button
                            onClick={() => cancelOrder(order.id)}
                            disabled={processingId === order.id || !canCancelOrder(order)}
                            variant="outline"
                            className={`w-full ${
                              canCancelOrder(order)
                                ? 'border-red-500/50 text-red-400 hover:bg-red-500/10'
                                : 'border-zinc-700 text-zinc-500 cursor-not-allowed'
                            }`}
                          >
                            <XCircle className="w-4 h-4 mr-2" />
                            {canCancelOrder(order) 
                              ? 'Отменить заявку (покупатель не оплатил)'
                              : `Отмена через ${getTimeUntilCancel(order) || '...'}`
                            }
                          </Button>
                        </div>
                      )}

                      {order.status === 'disputed' && (
                        <div className="space-y-3">
                          <div className="text-center text-sm text-orange-400 p-3 bg-orange-500/10 border border-orange-500/30 rounded-lg">
                            <AlertTriangle className="w-4 h-4 inline-block mr-2" />
                            Открыт спор - ожидает решения
                          </div>
                          
                          <div className="flex gap-2">
                            <Link to={`/trader/disputes/${order.dispute_id}`} className="flex-1">
                              <Button
                                variant="outline"
                                className="w-full border-zinc-700"
                              >
                                <MessageCircle className="w-4 h-4 mr-2" />
                                Чат спора
                              </Button>
                            </Link>
                            <Button
                              onClick={() => resolveDisputeForBuyer(order.id)}
                              disabled={processingId === order.id}
                              className="flex-1 bg-emerald-500 hover:bg-emerald-600"
                            >
                              <CheckCircle className="w-4 h-4 mr-2" />
                              Завершить в пользу покупателя
                            </Button>
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>

          {/* ПРАВАЯ КОЛОНКА: Новые заявки */}
          <div className="bg-gradient-to-r from-emerald-500/10 to-blue-500/10 border border-emerald-500/30 rounded-xl p-6">
            <div className="flex flex-col gap-4 mb-4">
              <div className="flex items-center gap-2">
                <Zap className="w-5 h-5 text-emerald-400" />
                <h2 className="text-lg font-semibold">
                  Новые заявки 
                  <span className="ml-2 px-2 py-0.5 bg-emerald-500 text-white text-sm rounded-full">
                    {availableOrders.length}
                  </span>
                </h2>
              </div>
              
              {/* Фильтры по сумме и методу оплаты */}
              <div className="flex flex-wrap items-center gap-2">
                <div className="flex items-center gap-2 bg-zinc-800/50 rounded-lg px-3 py-2">
                  <span className="text-xs text-zinc-400 whitespace-nowrap">от</span>
                  <Input
                    type="number"
                    placeholder="мин"
                    value={minAmount}
                    onChange={(e) => setMinAmount(e.target.value)}
                    className="w-20 h-7 text-sm bg-zinc-900 border-zinc-700 px-2"
                    data-testid="filter-min-amount"
                  />
                  <span className="text-xs text-zinc-400 whitespace-nowrap">до</span>
                  <Input
                    type="number"
                    placeholder="макс"
                    value={maxAmount}
                    onChange={(e) => setMaxAmount(e.target.value)}
                    className="w-20 h-7 text-sm bg-zinc-900 border-zinc-700 px-2"
                    data-testid="filter-max-amount"
                  />
                  <span className="text-xs text-zinc-500">₽</span>
                </div>
                
                {/* Мультиселект фильтр по методам оплаты */}
                <div className="relative" ref={methodsDropdownRef}>
                  <button
                    onClick={() => setShowMethodsDropdown(!showMethodsDropdown)}
                    className="flex items-center gap-2 h-9 px-3 text-sm bg-zinc-800/50 border border-zinc-700 rounded-lg text-white hover:border-emerald-500/50 transition-colors"
                    data-testid="filter-payment-methods-btn"
                  >
                    {selectedPaymentMethods.length === 0 ? (
                      <span className="text-zinc-400">Все методы</span>
                    ) : (
                      <span className="text-emerald-400">{selectedPaymentMethods.length} выбрано</span>
                    )}
                    <ChevronDown className={`w-4 h-4 transition-transform ${showMethodsDropdown ? 'rotate-180' : ''}`} />
                  </button>
                  
                  {/* Dropdown с чекбоксами */}
                  {showMethodsDropdown && (
                    <div className="absolute top-full left-0 mt-1 w-48 bg-zinc-800 border border-zinc-700 rounded-lg shadow-xl z-50 py-1">
                      {allPaymentMethods.map((method) => (
                        <button
                          key={method.value}
                          onClick={() => togglePaymentMethod(method.value)}
                          className="flex items-center gap-2 w-full px-3 py-2 text-sm text-left hover:bg-zinc-700/50 transition-colors"
                        >
                          <div className={`w-4 h-4 rounded border flex items-center justify-center ${
                            selectedPaymentMethods.includes(method.value)
                              ? 'bg-emerald-500 border-emerald-500'
                              : 'border-zinc-600'
                          }`}>
                            {selectedPaymentMethods.includes(method.value) && (
                              <Check className="w-3 h-3 text-white" />
                            )}
                          </div>
                          <span className={selectedPaymentMethods.includes(method.value) ? 'text-white' : 'text-zinc-400'}>
                            {method.label}
                          </span>
                        </button>
                      ))}
                      {selectedPaymentMethods.length > 0 && (
                        <button
                          onClick={() => setSelectedPaymentMethods([])}
                          className="flex items-center gap-2 w-full px-3 py-2 text-sm text-orange-400 hover:bg-zinc-700/50 border-t border-zinc-700 mt-1"
                        >
                          <XCircle className="w-4 h-4" />
                          Сбросить выбор
                        </button>
                      )}
                    </div>
                  )}
                </div>
                
                {filtersApplied && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={clearFilters}
                    className="h-7 text-xs text-zinc-400 hover:text-white"
                    data-testid="clear-filters-btn"
                  >
                    <XCircle className="w-3 h-3 mr-1" />
                    Сбросить
                  </Button>
                )}
              </div>
              
              {/* Выбранные методы в виде тегов */}
              {selectedPaymentMethods.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {selectedPaymentMethods.map(method => {
                    const methodInfo = allPaymentMethods.find(m => m.value === method);
                    return (
                      <span
                        key={method}
                        className="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-500/20 text-emerald-400 text-xs rounded-full"
                      >
                        {methodInfo?.label || method}
                        <button
                          onClick={() => togglePaymentMethod(method)}
                          className="hover:text-white"
                        >
                          <XCircle className="w-3 h-3" />
                        </button>
                      </span>
                    );
                  })}
                </div>
              )}
              
              {/* Показываем текущие лимиты трейдера с кнопкой настройки */}
              <div className="flex items-center gap-2">
                <span className="text-xs text-zinc-500">
                  Ваши лимиты: {formatRUB(traderLimits.min_amount_rub)} — {formatRUB(traderLimits.max_amount_rub)}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={openLimitsModal}
                  className="h-6 w-6 p-0 text-zinc-400 hover:text-white"
                  data-testid="settings-limits-btn"
                >
                  <Settings className="w-3.5 h-3.5" />
                </Button>
              </div>
            </div>
            
            {/* Предупреждения о требованиях */}
            {(!hasDeposit || !hasPaymentDetails) && availableOrders.length > 0 && (
              <div className="mb-4 p-4 bg-orange-500/10 border border-orange-500/30 rounded-lg">
                <div className="flex items-center gap-2 text-orange-400 font-medium mb-2">
                  <AlertTriangle className="w-4 h-4" />
                  Для принятия заявок необходимо:
                </div>
                <ul className="text-sm text-zinc-400 space-y-1 ml-6">
                  {!hasDeposit && (
                    <li className="flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-red-400"></span>
                      <Link to="/trader/finances" className="text-orange-400 hover:underline">
                        Пополнить депозит USDT
                      </Link>
                      <span className="text-zinc-500">(текущий: {formatUSDT(traderBalance)})</span>
                    </li>
                  )}
                  {!hasPaymentDetails && (
                    <li className="flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-red-400"></span>
                      <Link to="/trader/payment-details" className="text-orange-400 hover:underline">
                        Добавить реквизиты для оплаты
                      </Link>
                    </li>
                  )}
                </ul>
              </div>
            )}
            
            <div className="space-y-4 max-h-[600px] overflow-y-auto pr-2">
              {availableOrders.length > 0 ? (
                availableOrders.map((order) => (
                  <Card key={order.id} className={`bg-zinc-900 transition-colors ${
                    order.can_accept 
                      ? 'border-emerald-500/50 hover:border-emerald-500' 
                      : 'border-orange-500/30'
                  }`}>
                    <CardContent className="p-5">
                      <div className="flex items-center justify-between mb-3">
                        <CopyableOrderId orderId={order.id} size="small" />
                        <div className="flex items-center gap-2">
                          {/* Метод оплаты */}
                          <span className="px-2 py-1 rounded text-xs bg-blue-500/20 text-blue-400">
                            {getPaymentMethodName(order.requested_payment_method || order.payment_method)}
                          </span>
                          {/* Статус */}
                          <span className={`px-2 py-1 rounded text-xs ${
                            order.can_accept 
                              ? 'bg-emerald-500/20 text-emerald-400'
                              : 'bg-orange-500/20 text-orange-400'
                          }`}>
                            {order.can_accept ? 'Новая' : 
                              order.reason === 'no_deposit' ? 'Нет депозита' : 
                              order.reason === 'no_matching_details' ? 'Нет реквизитов' :
                              order.reason === 'out_of_limits' ? 'Вне лимитов' :
                              order.reason === 'low_balance' ? 'Мало баланса' :
                              'Недоступно'}
                          </span>
                        </div>
                      </div>

                      <div className="font-['JetBrains_Mono'] text-2xl font-bold mb-1">
                        {formatRUB(order.amount_rub)}
                      </div>
                      {order.marker_amount_rub > 0 && order.original_amount_rub && (
                        <div className="text-xs text-amber-400 bg-amber-500/10 rounded px-2 py-1 mb-1">
                          Цена: {formatRUB(order.original_amount_rub)} + маркер {order.marker_amount_rub}₽
                        </div>
                      )}
                      <div className="text-sm text-zinc-400 mb-2">
                        ≈ {formatUSDT(order.amount_usdt)} USDT
                      </div>

                      {!order.can_accept && (
                        <div className="text-xs text-orange-400 mb-2 p-2 bg-orange-500/10 rounded">
                          {order.reason === 'no_deposit' ? (
                            <>Пополните депозит USDT в разделе &quot;Финансы&quot;</>
                          ) : order.reason === 'no_matching_details' ? (
                            <>
                              Нет реквизитов типа <strong>{getPaymentMethodName(order.requested_payment_method || order.payment_method)}</strong><br/>
                              <Link to="/trader/payment-details" className="text-emerald-400 hover:underline">
                                Добавить реквизиты →
                              </Link>
                            </>
                          ) : order.reason === 'out_of_limits' ? (
                            <>
                              Сумма {formatRUB(order.amount_rub)} вне ваших лимитов<br/>
                              Ваши лимиты: {formatRUB(traderLimits.min_amount_rub)} — {formatRUB(traderLimits.max_amount_rub)}
                            </>
                          ) : (
                            <>
                              Нужно: {formatUSDT(order.required_usdt)} USDT<br/>
                              Ваш баланс: {formatUSDT(order.your_balance)} USDT
                            </>
                          )}
                        </div>
                      )}

                      <div className="text-xs text-zinc-500 mb-4">
                        Создано: {formatDate(order.created_at)}
                      </div>

                      <Button
                        onClick={() => openAcceptModal(order)}
                        disabled={processingId === order.id || !order.can_accept}
                        data-testid={`accept-order-${order.id}`}
                        className={`w-full ${
                          order.can_accept
                            ? 'bg-emerald-500 hover:bg-emerald-600'
                            : 'bg-zinc-700 cursor-not-allowed'
                        }`}
                      >
                        {processingId === order.id ? (
                          <span className="flex items-center gap-2">
                            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            Принимаю...
                          </span>
                        ) : !hasDeposit ? (
                          <span>Пополните депозит</span>
                        ) : order.reason === 'no_matching_details' ? (
                          <span>Нет реквизитов {getPaymentMethodName(order.requested_payment_method || order.payment_method)}</span>
                        ) : order.can_accept ? (
                          <span className="flex items-center gap-2">
                            <ArrowRight className="w-4 h-4" />
                            Принять заявку
                          </span>
                        ) : (
                          <span>Пополните баланс</span>
                        )}
                      </Button>
                    </CardContent>
                  </Card>
                ))
              ) : (
                <div className="text-center py-8 text-zinc-400">
                  {filtersApplied ? (
                    <div>
                      <p className="mb-2">Нет заявок по вашим фильтрам</p>
                      <Button variant="outline" size="sm" onClick={clearFilters} className="border-zinc-700">
                        Сбросить фильтры
                      </Button>
                    </div>
                  ) : (
                    <p>Новые заявки появятся здесь автоматически</p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Завершённые заказы */}
        <div>
          <h2 className="text-lg font-semibold mb-4">Последние завершённые</h2>
          
          {completedOrders.length === 0 ? (
            <Card className="bg-zinc-900 border-zinc-800">
              <CardContent className="p-8 text-center text-zinc-400">
                Завершённых сделок пока нет
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
                      <th className="table-header px-4 py-3 text-left">Комиссия</th>
                      <th className="table-header px-4 py-3 text-left">Дата</th>
                    </tr>
                  </thead>
                  <tbody>
                    {completedOrders.map((order) => (
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
                        <td className="px-4 py-3 font-['JetBrains_Mono'] text-emerald-400">
                          +{formatUSDT(order.trader_commission_usdt || 0)}
                        </td>
                        <td className="px-4 py-3 text-sm text-zinc-400">
                          {formatDate(order.completed_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* Модальное окно принятия заказа */}
      <Dialog open={showAcceptModal} onOpenChange={setShowAcceptModal}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md">
          <DialogHeader>
            <DialogTitle className="text-xl font-bold">Принять заявку</DialogTitle>
          </DialogHeader>
          
          {selectedOrder && (
            <div className="space-y-4">
              {/* Сумма и метод оплаты */}
              <div className="bg-zinc-800 rounded-lg p-4 text-center">
                <div className="text-sm text-zinc-400 mb-1">Сумма к оплате</div>
                <div className="font-['JetBrains_Mono'] text-2xl font-bold">
                  {formatRUB(selectedOrder.amount_rub)}
                </div>
                <div className="text-sm text-zinc-400 mb-2">
                  ≈ {formatUSDT(selectedOrder.amount_usdt)} USDT
                </div>
                <div className="inline-block px-3 py-1 rounded-full text-sm bg-blue-500/20 text-blue-400 border border-blue-500/30">
                  Метод: {getPaymentMethodName(selectedOrder?.requested_payment_method || selectedOrder?.payment_method)}
                </div>
              </div>

              {/* Выбор режима */}
              <div className="flex gap-2">
                <Button
                  variant={acceptMode === 'auto' ? 'default' : 'outline'}
                  onClick={() => setAcceptMode('auto')}
                  disabled={getMatchingDetails().length === 0}
                  className={`flex-1 ${acceptMode === 'auto' ? 'bg-emerald-500 hover:bg-emerald-600' : 'border-zinc-700'}`}
                >
                  Из сохранённых
                </Button>
                <Button
                  variant={acceptMode === 'manual' ? 'default' : 'outline'}
                  onClick={() => setAcceptMode('manual')}
                  className={`flex-1 ${acceptMode === 'manual' ? 'bg-emerald-500 hover:bg-emerald-600' : 'border-zinc-700'}`}
                >
                  <Edit3 className="w-4 h-4 mr-2" />
                  Ввести вручную
                </Button>
              </div>

              {/* Автоматический режим - выбор реквизитов */}
              {acceptMode === 'auto' && (
                <div>
                  <label className="block text-sm text-zinc-400 mb-2">
                    Выберите реквизиты ({getPaymentMethodName(selectedOrder?.requested_payment_method || selectedOrder?.payment_method)})
                  </label>
                  {getMatchingDetails().length === 0 ? (
                    <div className="text-center py-4 text-zinc-500 bg-zinc-800 rounded-lg">
                      <p className="mb-2">У вас нет сохранённых реквизитов типа <strong className="text-blue-400">{getPaymentMethodName(selectedOrder?.requested_payment_method || selectedOrder?.payment_method)}</strong></p>
                      <Link to="/trader/payment-details" className="text-emerald-400 hover:underline text-sm">
                        Добавить реквизиты →
                      </Link>
                    </div>
                  ) : (
                    <select
                      value={selectedDetailId || ''}
                      onChange={(e) => setSelectedDetailId(e.target.value)}
                      className="w-full px-4 py-3 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:outline-none focus:border-emerald-500"
                    >
                      {getMatchingDetails().map((pd) => (
                        <option key={pd.id} value={pd.id}>
                          {formatPaymentDetail(pd)}
                        </option>
                      ))}
                    </select>
                  )}
                </div>
              )}

              {/* Ручной режим - ввод текста */}
              {acceptMode === 'manual' && (
                <div>
                  <label className="block text-sm text-zinc-400 mb-2">
                    Реквизиты {getPaymentMethodName(selectedOrder?.requested_payment_method || selectedOrder?.payment_method)} (до 200 символов)
                  </label>
                  <Textarea
                    value={manualText}
                    onChange={(e) => setManualText(e.target.value)}
                    placeholder="Введите реквизиты для покупателя, например:&#10;Карта Сбербанк: 1234 5678 9012 3456&#10;Получатель: Иван И."
                    className="bg-zinc-800 border-zinc-700 min-h-[120px]"
                    maxLength={200}
                  />
                  <div className="text-xs text-zinc-500 mt-1 text-right">
                    {manualText.length}/200
                  </div>
                </div>
              )}

              {/* Кнопка подтверждения */}
              <Button
                onClick={acceptOrder}
                disabled={
                  processingId === selectedOrder.id ||
                  (acceptMode === 'auto' && !selectedDetailId) ||
                  (acceptMode === 'manual' && !manualText.trim())
                }
                data-testid="confirm-accept-order-btn"
                className="w-full bg-emerald-500 hover:bg-emerald-600 h-12"
              >
                {processingId === selectedOrder.id ? (
                  <span className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Принимаю...
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4" />
                    Принять и отправить реквизиты
                  </span>
                )}
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Модальное окно настройки лимитов */}
      <Dialog open={showLimitsModal} onOpenChange={setShowLimitsModal}>
        <DialogContent className="bg-zinc-900 border-zinc-800 text-white max-w-md">
          <DialogHeader>
            <DialogTitle className="text-xl font-semibold flex items-center gap-2">
              <Settings className="w-5 h-5 text-emerald-400" />
              Настройка лимитов
            </DialogTitle>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <p className="text-sm text-zinc-400">
              Установите минимальную и максимальную сумму заявок, которые вы готовы принимать
            </p>
            
            <div className="space-y-3">
              <div>
                <label className="block text-sm text-zinc-400 mb-1">Минимальная сумма (₽)</label>
                <Input
                  type="number"
                  value={editMinLimit}
                  onChange={(e) => setEditMinLimit(e.target.value)}
                  placeholder="100"
                  className="bg-zinc-800 border-zinc-700"
                  data-testid="edit-min-limit"
                />
              </div>
              
              <div>
                <label className="block text-sm text-zinc-400 mb-1">Максимальная сумма (₽)</label>
                <Input
                  type="number"
                  value={editMaxLimit}
                  onChange={(e) => setEditMaxLimit(e.target.value)}
                  placeholder="500000"
                  className="bg-zinc-800 border-zinc-700"
                  data-testid="edit-max-limit"
                />
              </div>
            </div>
            
            <div className="bg-zinc-800/50 rounded-lg p-3 text-sm text-zinc-400">
              <p>💡 Заявки вне ваших лимитов будут отображаться, но вы не сможете их принять</p>
            </div>
          </div>
          
          <div className="flex gap-3">
            <Button
              variant="outline"
              onClick={() => setShowLimitsModal(false)}
              className="flex-1 border-zinc-700"
            >
              Отмена
            </Button>
            <Button
              onClick={saveLimits}
              disabled={savingLimits}
              className="flex-1 bg-emerald-500 hover:bg-emerald-600"
              data-testid="save-limits-btn"
            >
              {savingLimits ? 'Сохранение...' : 'Сохранить'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </DashboardLayout>
  );
};

export default TraderWorkspace;
