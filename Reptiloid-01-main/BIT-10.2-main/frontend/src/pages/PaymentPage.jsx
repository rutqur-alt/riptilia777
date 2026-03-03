import React, { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { toast } from 'sonner';
import { DollarSign, Clock, CreditCard, CheckCircle, XCircle, AlertTriangle, Copy, RefreshCw, MessageCircle, Shield, ExternalLink } from 'lucide-react';
import CopyableOrderId from '@/components/CopyableOrderId';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import axios from 'axios';

// Standalone API instance for PaymentPage (no auth interceptors)
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const paymentApi = axios.create({
  baseURL: `${BACKEND_URL}/api`,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000
});

// Названия методов оплаты
const getPaymentMethodName = (method) => {
  const names = {
    'card': 'Банковская карта',
    'sbp': 'СБП',
    'sim': 'Мобильный счёт',
    'mono_bank': 'Monobank',
    'sng_sbp': 'СБП СНГ',
    'sng_card': 'Карта СНГ',
    'qr_code': 'QR-код'
  };
  return names[method] || method;
};

// Helper functions (standalone - no auth dependency)
const formatRUB = (amount) => {
  if (!amount && amount !== 0) return '0 ₽';
  return new Intl.NumberFormat('ru-RU').format(amount) + ' ₽';
};

const formatUSDT = (amount) => {
  if (!amount && amount !== 0) return '0';
  return Number(amount).toFixed(2);
};

const getStatusLabel = (status) => {
  const labels = {
    'new': 'Новый',
    'waiting_requisites': 'Ожидание реквизитов',
    'waiting_trader_confirmation': 'Ожидание подтверждения',
    'waiting_buyer_confirmation': 'Ожидание оплаты',
    'paid': 'Оплачен',
    'completed': 'Завершён',
    'cancelled': 'Отменён',
    'expired': 'Истёк',
    'dispute': 'Спор',
    'disputed': 'Спор'
  };
  return labels[status] || status;
};

const getStatusClass = (status) => {
  const classes = {
    'new': 'text-blue-400',
    'waiting_requisites': 'text-blue-400',
    'waiting_trader_confirmation': 'text-yellow-400',
    'waiting_buyer_confirmation': 'text-yellow-400',
    'paid': 'text-emerald-400',
    'completed': 'text-emerald-400',
    'cancelled': 'text-red-400',
    'expired': 'text-zinc-400',
    'dispute': 'text-orange-400',
    'disputed': 'text-orange-400'
  };
  return classes[status] || 'text-zinc-400';
};

const PaymentPage = () => {
  const { orderId } = useParams();
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [confirming, setConfirming] = useState(false);
  const [timeLeft, setTimeLeft] = useState(0);
  const [autoCancelTimeLeft, setAutoCancelTimeLeft] = useState(0);
  const [disputeTimeLeft, setDisputeTimeLeft] = useState(0);
  const [showDisputeDialog, setShowDisputeDialog] = useState(false);
  const [disputeReason, setDisputeReason] = useState('');
  const [openingDispute, setOpeningDispute] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  // Fetch order data
  const fetchOrder = useCallback(async () => {
    if (!orderId) {
      setError('ID заказа не указан');
      setLoading(false);
      return;
    }
    
    try {
      const res = await paymentApi.get(`/pay/${orderId}`);
      const orderData = res.data.order || res.data;
      if (res.data.payment_details) {
        orderData.payment_details = res.data.payment_details;
      }
      setOrder(orderData);
      setError(null);
    } catch (err) {
      console.error('Payment page error:', err);
      if (err.response?.status === 404) {
        setError('Заказ не найден');
      } else if (err.code === 'ECONNABORTED' || !err.response) {
        setError('Ошибка соединения. Проверьте интернет.');
      } else {
        setError('Ошибка загрузки заказа');
      }
    } finally {
      setLoading(false);
    }
  }, [orderId]);

  useEffect(() => {
    fetchOrder();
  }, [fetchOrder]);

  // Автообновление когда заказ ждёт трейдера или реквизиты
  useEffect(() => {
    if (!order || !['new', 'waiting_trader_confirmation', 'waiting_requisites'].includes(order.status)) return;
    
    const interval = setInterval(fetchOrder, 5000);
    return () => clearInterval(interval);
  }, [order]);

  // Таймер до автоотмены заказа (10 минут после принятия трейдером)
  useEffect(() => {
    if (!order || order.status !== 'waiting_buyer_confirmation') return;
    
    const updateAutoCancelTimer = () => {
      const takenAt = order.taken_at || order.accepted_at || order.trader_accepted_at;
      if (!takenAt) {
        setAutoCancelTimeLeft(1800); // Default 30 minutes
        return;
      }
      
      const takenTime = new Date(takenAt);
      const autoCancelAt = new Date(takenTime.getTime() + 30 * 60 * 1000); // +30 minutes
      const now = new Date();
      const diff = Math.max(0, Math.floor((autoCancelAt - now) / 1000));
      setAutoCancelTimeLeft(diff);
    };

    updateAutoCancelTimer();
    const interval = setInterval(updateAutoCancelTimer, 1000);
    return () => clearInterval(interval);
  }, [order]);

  useEffect(() => {
    if (!order || order.status !== 'waiting_buyer_confirmation') return;
    
    const updateTimer = () => {
      const expiresAt = new Date(order.expires_at);
      const now = new Date();
      const diff = Math.max(0, Math.floor((expiresAt - now) / 1000));
      setTimeLeft(diff);
    };

    updateTimer();
    const interval = setInterval(updateTimer, 1000);
    return () => clearInterval(interval);
  }, [order]);

  // Таймер до возможности открытия спора (10 минут после подтверждения оплаты)
  useEffect(() => {
    if (!order || order.status !== 'waiting_trader_confirmation') return;
    
    const updateDisputeTimer = () => {
      if (!order.buyer_confirmed_at) {
        setDisputeTimeLeft(600); // 10 минут
        return;
      }
      
      const confirmedAt = new Date(order.buyer_confirmed_at);
      const canDisputeAt = new Date(confirmedAt.getTime() + 10 * 60 * 1000); // +10 минут
      const now = new Date();
      const diff = Math.max(0, Math.floor((canDisputeAt - now) / 1000));
      setDisputeTimeLeft(diff);
    };

    updateDisputeTimer();
    const interval = setInterval(updateDisputeTimer, 1000);
    return () => clearInterval(interval);
  }, [order]);

  const handleConfirm = async () => {
    setConfirming(true);
    try {
      await paymentApi.post(`/pay/${orderId}/confirm`);
      toast.success('Оплата отправлена на проверку');
      fetchOrder();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Ошибка');
    } finally {
      setConfirming(false);
    }
  };

  const handleCancelOrder = async () => {
    if (!window.confirm('Вы уверены, что хотите отменить заказ?')) return;
    
    setCancelling(true);
    try {
      await paymentApi.post(`/pay/${orderId}/cancel`);
      toast.success('Заказ отменён');
      fetchOrder();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Ошибка отмены');
    } finally {
      setCancelling(false);
    }
  };

  const handleOpenDispute = async () => {
    setOpeningDispute(true);
    try {
      const res = await paymentApi.post(`/pay/${orderId}/dispute`, { 
        reason: 'Спор открыт покупателем'
      });
      
      // Показываем ссылку и предупреждение
      const disputeLink = `${window.location.origin}/dispute/${res.data.dispute_id}`;
      toast.success(
        <div>
          <p className="font-medium">Спор открыт!</p>
          <p className="text-sm mt-1">⚠️ Сохраните ссылку на спор!</p>
        </div>,
        { duration: 5000 }
      );
      
      // Копируем ссылку в буфер
      try {
        await navigator.clipboard.writeText(disputeLink);
        toast.info('Ссылка скопирована в буфер обмена', { duration: 3000 });
      } catch (clipboardError) {
        console.log('Clipboard error:', clipboardError);
      }
      
      setShowDisputeDialog(false);
      // Переходим в чат спора
      if (res.data.dispute_id) {
        window.location.href = `/dispute/${res.data.dispute_id}?buyer=true`;
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Ошибка открытия спора');
    } finally {
      setOpeningDispute(false);
    }
  };

  const goToDisputeChat = () => {
    if (order.dispute_id) {
      window.location.href = `/dispute/${order.dispute_id}?buyer=true`;
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('Скопировано');
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#09090B] flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-zinc-400">Загрузка заказа...</p>
        </div>
      </div>
    );
  }

  if (error || !order) {
    return (
      <div className="min-h-screen bg-[#09090B] flex items-center justify-center p-6">
        <div className="text-center max-w-md">
          <XCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold mb-2">{error || 'Заказ не найден'}</h1>
          <p className="text-zinc-400 mb-6">Проверьте правильность ссылки</p>
          <Button 
            onClick={() => { setLoading(true); setError(null); fetchOrder(); }}
            className="bg-emerald-500 hover:bg-emerald-600"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Повторить
          </Button>
        </div>
      </div>
    );
  }

  const renderStatusContent = () => {
    // Ссылка на спор для покупателя
    const disputeLink = order?.dispute_id ? `${window.location.origin}/dispute/${order.dispute_id}?buyer=true` : '';
    
    switch (order.status) {
      case 'new':
      case 'waiting_requisites':
        return (
          <div className="text-center py-8">
            <div className="w-16 h-16 rounded-full bg-blue-500/20 flex items-center justify-center mx-auto mb-4">
              <Clock className="w-8 h-8 text-blue-400 animate-pulse" />
            </div>
            <h2 className="text-xl font-bold mb-2">Ожидание реквизитов</h2>
            <p className="text-zinc-400 mb-4">
              Заявка создана. Ожидайте, трейдер скоро выдаст реквизиты для оплаты.
            </p>
            {order.requested_payment_method && (
              <div className="bg-zinc-800 rounded-lg px-4 py-2 inline-block text-sm text-zinc-300 mb-4">
                Способ оплаты: <span className="text-emerald-400">{getPaymentMethodName(order.requested_payment_method)}</span>
              </div>
            )}
            <div className="bg-zinc-800 rounded-lg p-4 text-sm text-zinc-400 mb-4">
              <p>💡 Не закрывайте эту страницу. Реквизиты появятся автоматически.</p>
            </div>
            
            {/* Рекламный баннер */}
            <a 
              href="https://bitarbitr.org" 
              target="_blank" 
              rel="noopener noreferrer"
              onClick={(e) => {
                e.preventDefault();
                window.open('https://bitarbitr.org', '_blank', 'noopener,noreferrer');
              }}
              className="block mb-6 group cursor-pointer"
            >
              <div className="bg-gradient-to-r from-emerald-500/20 via-teal-500/20 to-cyan-500/20 border border-emerald-500/30 rounded-xl p-4 hover:border-emerald-400/50 transition-all duration-300 hover:scale-[1.02]">
                <div className="flex items-center justify-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center">
                    <DollarSign className="w-5 h-5 text-white" />
                  </div>
                  <div className="text-left">
                    <div className="text-emerald-400 font-bold text-lg group-hover:text-emerald-300 transition-colors">
                      💰 Зарабатывай с нами!
                    </div>
                    <div className="text-zinc-400 text-sm">
                      Стань трейдером и получай доход с каждой сделки
                    </div>
                  </div>
                  <ExternalLink className="w-5 h-5 text-emerald-400/50 group-hover:text-emerald-400 transition-colors" />
                </div>
              </div>
            </a>
            
            <div className="flex gap-2 justify-center">
              <Button 
                onClick={fetchOrder}
                variant="outline"
                className="border-zinc-700"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Обновить
              </Button>
              <Button 
                onClick={handleCancelOrder}
                variant="outline"
                className="border-red-500/50 text-red-400 hover:bg-red-500/10"
              >
                <XCircle className="w-4 h-4 mr-2" />
                Отменить
              </Button>
            </div>
          </div>
        );

      case 'waiting_buyer_confirmation':
        return (
          <>
            {/* Timer and Warning Message */}
            <div className="mb-6">
              <div className="flex items-center justify-center gap-2 mb-3">
                <Clock className={`w-5 h-5 ${autoCancelTimeLeft < 180 ? 'text-red-400' : 'text-orange-400'}`} />
                <span className={`font-['JetBrains_Mono'] text-xl ${autoCancelTimeLeft < 180 ? 'text-red-400' : 'text-white'}`}>
                  {formatTime(autoCancelTimeLeft)}
                </span>
              </div>
              
              {/* Payment time warning */}
              <div className={`${autoCancelTimeLeft < 180 ? 'bg-red-500/10 border-red-500/30' : 'bg-orange-500/10 border-orange-500/30'} border rounded-lg p-3 text-center`}>
                <p className={`${autoCancelTimeLeft < 180 ? 'text-red-400' : 'text-orange-400'} text-sm font-medium`}>
                  ⏱️ {autoCancelTimeLeft < 180 ? 'Осталось менее 3 минут!' : 'У вас есть 10 минут на оплату'}
                </p>
                <p className="text-zinc-400 text-xs mt-1">
                  После этого времени заказ будет автоматически отменён
                </p>
              </div>
            </div>

            {/* Payment Details */}
            {order.payment_details && (
              <div className="bg-zinc-800 rounded-xl p-6 mb-6 text-center">
                <div className="text-sm text-zinc-400 mb-2">
                  {(order.payment_details.type === 'card' || order.payment_details.card_number) && 'Номер карты'}
                  {(order.payment_details.type === 'sbp' && !order.payment_details.card_number) && 'Телефон для СБП'}
                  {(order.payment_details.type === 'qr' || order.payment_details.type === 'qr_code') && 'QR-код для оплаты'}
                  {(order.payment_details.type === 'mobile' || order.payment_details.type === 'sim') && 'Номер для пополнения'}
                  {order.payment_details.type === 'text' && 'Реквизиты для оплаты'}
                  {(order.payment_details.type === 'mono_bank') && 'Monobank'}
                  {(order.payment_details.type === 'sng_sbp') && 'СБП СНГ'}
                  {(order.payment_details.type === 'sng_card') && 'Карта СНГ'}
                </div>
                
                {/* Ручные текстовые реквизиты */}
                {order.payment_details.manual_text && (
                  <div 
                    className="font-['JetBrains_Mono'] text-lg whitespace-pre-wrap cursor-pointer hover:text-emerald-400 transition-colors mb-3"
                    onClick={() => copyToClipboard(order.payment_details.manual_text)}
                  >
                    {order.payment_details.manual_text}
                    <Copy className="w-4 h-4 inline ml-2" />
                  </div>
                )}
                
                {/* Номер карты (для card, sng_card, mono_bank) */}
                {order.payment_details.card_number && (
                  <>
                    <div 
                      className="font-['JetBrains_Mono'] text-2xl mb-2 flex items-center justify-center gap-2 cursor-pointer hover:text-emerald-400 transition-colors"
                      onClick={() => copyToClipboard(order.payment_details.card_number)}
                    >
                      {order.payment_details.card_number}
                      <Copy className="w-4 h-4" />
                    </div>
                    {order.payment_details.bank_name && (
                      <div className="text-zinc-400">
                        {order.payment_details.bank_name}
                      </div>
                    )}
                    {order.payment_details.holder_name && (
                      <div className="text-zinc-500 text-sm mt-1">
                        {order.payment_details.holder_name}
                      </div>
                    )}
                  </>
                )}

                {/* Телефон (для sbp, sng_sbp, sim, mobile) */}
                {order.payment_details.phone_number && !order.payment_details.card_number && (
                  <>
                    <div 
                      className="font-['JetBrains_Mono'] text-2xl mb-2 flex items-center justify-center gap-2 cursor-pointer hover:text-emerald-400 transition-colors"
                      onClick={() => copyToClipboard(order.payment_details.phone_number)}
                    >
                      {order.payment_details.phone_number}
                      <Copy className="w-4 h-4" />
                    </div>
                    <div className="text-zinc-400">
                      {order.payment_details.type === 'sbp' && 'СБП'}
                      {order.payment_details.type === 'sng_sbp' && 'СБП СНГ'}
                      {(order.payment_details.type === 'sim' || order.payment_details.type === 'mobile') && 'Пополнение мобильной связи'}
                      {order.payment_details.bank_name && ` • ${order.payment_details.bank_name}`}
                      {order.payment_details.operator_name && ` • ${order.payment_details.operator_name}`}
                    </div>
                  </>
                )}

                {/* QR код */}
                {order.payment_details.qr_data && (
                  <>
                    <div className="flex justify-center mb-4">
                      <img 
                        src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(order.payment_details.qr_data)}`}
                        alt="QR код для оплаты"
                        className="rounded-lg bg-white p-2"
                      />
                    </div>
                    <div 
                      className="font-['JetBrains_Mono'] text-sm text-center cursor-pointer hover:text-emerald-400 transition-colors break-all"
                      onClick={() => copyToClipboard(order.payment_details.qr_data)}
                    >
                      {order.payment_details.qr_data.length > 50 
                        ? order.payment_details.qr_data.substring(0, 50) + '...' 
                        : order.payment_details.qr_data}
                      <Copy className="w-4 h-4 inline ml-2" />
                    </div>
                    {order.payment_details.bank_name && (
                      <div className="text-zinc-400 text-center mt-2">
                        {order.payment_details.bank_name}
                      </div>
                    )}
                  </>
                )}

                {/* Номер счёта (универсальный fallback) */}
                {order.payment_details.account_number && !order.payment_details.card_number && !order.payment_details.phone_number && (
                  <>
                    <div 
                      className="font-['JetBrains_Mono'] text-xl mb-2 flex items-center justify-center gap-2 cursor-pointer hover:text-emerald-400 transition-colors"
                      onClick={() => copyToClipboard(order.payment_details.account_number)}
                    >
                      {order.payment_details.account_number}
                      <Copy className="w-4 h-4" />
                    </div>
                    {order.payment_details.recipient_name && (
                      <div className="text-zinc-500 text-sm">
                        {order.payment_details.recipient_name}
                      </div>
                    )}
                  </>
                )}

                {/* Если вообще ничего нет - показываем тип */}
                {!order.payment_details.card_number && 
                 !order.payment_details.phone_number && 
                 !order.payment_details.qr_data && 
                 !order.payment_details.manual_text &&
                 !order.payment_details.account_number && (
                  <div className="text-orange-400">
                    Реквизиты ещё не назначены. Ожидайте...
                  </div>
                )}
              </div>
            )}

            {/* Instructions */}
            <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-4 mb-6">
              <h3 className="font-medium text-emerald-400 mb-2">Инструкция:</h3>
              <ol className="text-sm text-zinc-300 space-y-2">
                <li>1. Переведите <span className="text-orange-400 font-bold">ТОЧНУЮ сумму</span> <span className="font-['JetBrains_Mono'] text-white">{formatRUB(order.amount_rub)}</span></li>
                {order.marker && (
                  <li className="text-orange-400/80 text-xs pl-4">
                    (включая маркер +{order.marker}₽ для идентификации платежа)
                  </li>
                )}
                <li>2. Сохраните чек об оплате</li>
                <li>3. Нажмите «Я оплатил» после перевода</li>
              </ol>
            </div>

            {/* Confirm Button */}
            <Button
              onClick={handleConfirm}
              disabled={confirming || timeLeft === 0}
              className="w-full bg-emerald-500 hover:bg-emerald-600 h-14 text-lg glow-green mb-3"
            >
              {confirming ? 'Отправка...' : 'Я оплатил'}
            </Button>
            
            {/* Cancel Button */}
            <Button
              onClick={handleCancelOrder}
              disabled={cancelling}
              variant="outline"
              className="w-full border-zinc-700 text-zinc-400 hover:bg-zinc-800"
            >
              <XCircle className="w-4 h-4 mr-2" />
              {cancelling ? 'Отмена...' : 'Отменить заказ'}
            </Button>
          </>
        );

      case 'waiting_trader_confirmation':
        const canOpenDispute = disputeTimeLeft === 0;
        const disputeMinutes = Math.floor(disputeTimeLeft / 60);
        const disputeSeconds = disputeTimeLeft % 60;
        
        return (
          <div className="text-center py-8">
            <div className="w-16 h-16 rounded-full bg-orange-500/20 flex items-center justify-center mx-auto mb-4">
              <Clock className="w-8 h-8 text-orange-400 animate-pulse" />
            </div>
            <h2 className="text-xl font-bold mb-2">Ожидание подтверждения</h2>
            <p className="text-zinc-400 mb-4">
              Трейдер проверяет поступление средств. Обычно это занимает не более 15 минут.
            </p>
            
            {/* Кнопка открытия спора */}
            <div className="bg-orange-500/10 border border-orange-500/20 rounded-xl p-4 mb-4">
              {canOpenDispute ? (
                <>
                  <p className="text-sm text-zinc-400 mb-3">
                    Если у вас возникли проблемы с оплатой или трейдер долго не подтверждает - откройте спор.
                  </p>
                  <Button
                    onClick={() => setShowDisputeDialog(true)}
                    variant="outline"
                    className="border-orange-500/50 text-orange-400 hover:bg-orange-500/10"
                    data-testid="open-dispute-btn"
                  >
                    <AlertTriangle className="w-4 h-4 mr-2" />
                    Открыть спор
                  </Button>
                </>
              ) : (
                <>
                  <p className="text-sm text-zinc-400 mb-2">
                    Подождите, пока трейдер проверит платёж
                  </p>
                  <div className="flex items-center justify-center gap-2 text-orange-400">
                    <Clock className="w-4 h-4" />
                    <span className="font-['JetBrains_Mono']">
                      Спор можно открыть через {disputeMinutes}:{disputeSeconds.toString().padStart(2, '0')}
                    </span>
                  </div>
                  <p className="text-xs text-zinc-500 mt-2">
                    Возможность открыть спор появится через 10 минут после нажатия &quot;Я оплатил&quot;
                  </p>
                </>
              )}
            </div>
            
            {/* Кнопка отмены заказа - доступна всегда */}
            <Button
              onClick={handleCancelOrder}
              disabled={cancelling}
              variant="outline"
              className="w-full border-zinc-700 text-zinc-400 hover:bg-zinc-800 mt-4"
            >
              <XCircle className="w-4 h-4 mr-2" />
              {cancelling ? 'Отмена...' : 'Отменить заказ'}
            </Button>
          </div>
        );

      case 'disputed':
        const disputeLink = `${window.location.origin}/dispute/${order.dispute_id}`;
        return (
          <div className="text-center py-8">
            <div className="w-16 h-16 rounded-full bg-orange-500/20 flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="w-8 h-8 text-orange-400" />
            </div>
            <h2 className="text-xl font-bold mb-2">Спор открыт</h2>
            <p className="text-zinc-400 mb-4">
              Модератор рассматривает вашу ситуацию. Перейдите в чат для общения.
            </p>
            
            {/* Уникальная ссылка на спор */}
            <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-4 mb-4">
              <p className="text-sm text-orange-300 font-medium mb-2">
                ⚠️ ВАЖНО! Сохраните эту ссылку:
              </p>
              <div className="flex items-center gap-2 bg-zinc-800 rounded-lg p-2">
                <input 
                  type="text" 
                  readOnly 
                  value={disputeLink}
                  className="flex-1 bg-transparent text-sm text-zinc-300 outline-none font-mono"
                />
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    navigator.clipboard.writeText(disputeLink);
                    toast.success('Ссылка скопирована!');
                  }}
                  className="text-emerald-400 hover:text-emerald-300"
                >
                  <Copy className="w-4 h-4" />
                </Button>
              </div>
              <p className="text-xs text-zinc-500 mt-2">
                По этой ссылке вы сможете вернуться в чат спора до его разрешения
              </p>
            </div>
            
            <Button
              onClick={goToDisputeChat}
              className="bg-orange-500 hover:bg-orange-600"
            >
              <MessageCircle className="w-4 h-4 mr-2" />
              Перейти в чат спора
            </Button>
          </div>
        );

      case 'completed':
        return (
          <div className="text-center py-8">
            <div className="w-16 h-16 rounded-full bg-emerald-500/20 flex items-center justify-center mx-auto mb-4">
              <CheckCircle className="w-8 h-8 text-emerald-400" />
            </div>
            <h2 className="text-xl font-bold mb-2">Оплата подтверждена!</h2>
            <p className="text-zinc-400">
              Спасибо за использование BITARBITR
            </p>
          </div>
        );

      case 'cancelled':
        return (
          <div className="text-center py-8">
            <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center mx-auto mb-4">
              <XCircle className="w-8 h-8 text-red-400" />
            </div>
            <h2 className="text-xl font-bold mb-2">Заказ отменён</h2>
            <p className="text-zinc-400">
              Время на оплату истекло или заказ был отменён
            </p>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-[#09090B] flex items-center justify-center p-4 pt-20">
      <div className="w-full max-w-md">
        {/* Header - минимальный */}
        <div className="text-center mb-6">
          <h1 className="text-xl font-bold text-zinc-300">Оплата заказа</h1>
        </div>

        {/* Payment Card */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6">
          {/* Amount */}
          <div className="text-center mb-6">
            <div className="text-sm text-zinc-400 mb-1">К оплате:</div>
            <div className="font-['JetBrains_Mono'] text-4xl font-bold text-white mb-2">
              {formatRUB(order.amount_rub)}
            </div>
            {/* Маркер */}
            {order.marker && (
              <div className="flex items-center justify-center gap-2 text-orange-400 text-sm mb-2">
                <span className="inline-block px-2 py-0.5 bg-orange-500/20 rounded">📌 Маркер +{order.marker}₽</span>
              </div>
            )}
            <div className="flex items-center justify-center gap-2 text-zinc-500">
              <DollarSign className="w-4 h-4" />
              <span className="font-['JetBrains_Mono']">{formatUSDT(order.amount_usdt)} USDT</span>
            </div>
          </div>

          {/* Status indicator */}
          <div className="flex justify-center mb-6">
            <span className={`px-3 py-1 rounded-full text-sm border ${getStatusClass(order.status)}`}>
              {getStatusLabel(order.status)}
            </span>
          </div>

          {/* Dynamic Content */}
          {renderStatusContent()}
        </div>

        {/* Order ID */}
        <div className="text-center mt-4">
          <CopyableOrderId orderId={order.id || order.order_id} size="default" />
        </div>
      </div>

      {/* Dispute Dialog */}
      <Dialog open={showDisputeDialog} onOpenChange={setShowDisputeDialog}>
        <DialogContent className="bg-zinc-900 border-zinc-800">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-orange-400" />
              Открыть спор
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-4">
            <p className="text-sm text-zinc-400">
              После открытия спора вы сможете общаться с трейдером и администрацией в чате.
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={() => setShowDisputeDialog(false)}
                className="flex-1"
              >
                Отмена
              </Button>
              <Button
                onClick={handleOpenDispute}
                disabled={openingDispute}
                className="flex-1 bg-orange-500 hover:bg-orange-600"
              >
                {openingDispute ? 'Открытие...' : 'Открыть спор'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default PaymentPage;
