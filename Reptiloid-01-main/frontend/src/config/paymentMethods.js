// Единый конфиг методов оплаты для всей платформы
// Используется: трейдер (реквизиты), покупатель (выбор оператора), главная (стакан)

import { CreditCard, Smartphone, QrCode, Phone, Globe, Banknote } from 'lucide-react';

export const PAYMENT_METHODS = {
  sbp: { 
    name: 'СБП', 
    shortName: 'СБП',
    icon: Smartphone,
    emoji: '⚡', 
    color: '#3B82F6',
    bgClass: 'bg-blue-500/10',
    textClass: 'text-blue-400',
    description: 'Система быстрых платежей'
  },
  card: { 
    name: 'Банковская карта', 
    shortName: 'Карта',
    icon: CreditCard,
    emoji: '💳', 
    color: '#10B981',
    bgClass: 'bg-emerald-500/10',
    textClass: 'text-emerald-400',
    description: 'Перевод на карту'
  },
  sim: { 
    name: 'Баланс телефона', 
    shortName: 'SIM',
    icon: Phone,
    emoji: '📱', 
    color: '#F59E0B',
    bgClass: 'bg-orange-500/10',
    textClass: 'text-orange-400',
    description: 'Пополнение баланса'
  },
  qr_code: { 
    name: 'QR-код', 
    shortName: 'QR',
    icon: QrCode,
    emoji: '📷', 
    color: '#EC4899',
    bgClass: 'bg-pink-500/10',
    textClass: 'text-pink-400',
    description: 'Оплата по QR'
  },
  mono_bank: { 
    name: 'Monobank', 
    shortName: 'Mono',
    icon: Banknote,
    emoji: '🏦', 
    color: '#A855F7',
    bgClass: 'bg-purple-500/10',
    textClass: 'text-purple-400',
    description: 'Monobank (Украина)'
  },
  sng_sbp: { 
    name: 'СБП (СНГ)', 
    shortName: 'СНГ СБП',
    icon: Globe,
    emoji: '🌍', 
    color: '#06B6D4',
    bgClass: 'bg-cyan-500/10',
    textClass: 'text-cyan-400',
    description: 'СБП для стран СНГ'
  },
  sng_card: { 
    name: 'Карта (СНГ)', 
    shortName: 'СНГ Карта',
    icon: Globe,
    emoji: '🌏', 
    color: '#14B8A6',
    bgClass: 'bg-teal-500/10',
    textClass: 'text-teal-400',
    description: 'Карта для стран СНГ'
  }
};

// Получить информацию о методе (с fallback)
export const getPaymentMethod = (type) => {
  return PAYMENT_METHODS[type] || {
    name: type,
    shortName: type,
    icon: CreditCard,
    emoji: '💰',
    color: '#71717A',
    bgClass: 'bg-zinc-500/10',
    textClass: 'text-zinc-400',
    description: ''
  };
};

// Список всех методов для селекта
export const PAYMENT_METHOD_OPTIONS = Object.entries(PAYMENT_METHODS).map(([key, value]) => ({
  value: key,
  label: value.name,
  shortLabel: value.shortName,
  emoji: value.emoji
}));

// Фильтр активных методов
export const getActiveMethodTypes = (operators) => {
  const types = new Set();
  operators.forEach(op => {
    (op.requisites || op.payment_methods || []).forEach(r => {
      const type = typeof r === 'string' ? r : r.type;
      if (PAYMENT_METHODS[type]) types.add(type);
    });
  });
  return Array.from(types);
};
