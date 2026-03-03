// Shared utilities and constants for trader components
import { CreditCard, Phone, QrCode, Smartphone, Globe } from "lucide-react";

export const merchantTypeLabels = {
  casino: "Казино",
  shop: "Магазин",
  stream: "Стрим",
  other: "Другое"
};

export const requisiteTypeLabels = {
  card: { name: "Банковская карта", emoji: "💳", color: "#7C3AED", icon: CreditCard },
  sbp: { name: "СБП", emoji: "⚡", color: "#10B981", icon: Phone },
  qr: { name: "QR-код", emoji: "📱", color: "#3B82F6", icon: QrCode },
  sim: { name: "SIM баланс", emoji: "📞", color: "#F59E0B", icon: Smartphone },
  cis: { name: "Перевод СНГ", emoji: "🌍", color: "#EC4899", icon: Globe }
};

export const getRequisiteDisplayName = (req) => {
  const typeInfo = requisiteTypeLabels[req.type];
  if (!typeInfo) return req.type;
  if (req.type === "card") {
    return `${typeInfo.emoji} ${req.data.bank_name} •••• ${req.data.card_number?.slice(-4) || ""}`;
  }
  if (req.type === "sbp") {
    return `${typeInfo.emoji} СБП ${req.data.phone}`;
  }
  if (req.type === "qr") {
    return `${typeInfo.emoji} QR-код ${req.data.bank_name}`;
  }
  if (req.type === "sim") {
    return `${typeInfo.emoji} ${req.data.operator} ${req.data.phone}`;
  }
  if (req.type === "cis") {
    return `${typeInfo.emoji} ${req.data.country} ${req.data.bank_name}`;
  }
  return `${typeInfo.emoji} ${typeInfo.name}`;
};

export const tradeStatusStyles = {
  pending: "bg-[#F59E0B]/10 text-[#F59E0B]",
  paid: "bg-[#3B82F6]/10 text-[#3B82F6]",
  completed: "bg-[#10B981]/10 text-[#10B981]",
  cancelled: "bg-[#EF4444]/10 text-[#EF4444]",
  disputed: "bg-[#EF4444]/10 text-[#EF4444]"
};

export const tradeStatusLabels = {
  seller: {
    pending: "Ожидает оплаты",
    paid: "Покупатель оплатил!",
    completed: "Завершена",
    cancelled: "Отменена",
    disputed: "Спор"
  },
  buyer: {
    pending: "Ожидает вашей оплаты",
    paid: "Ожидает подтверждения",
    completed: "Завершена",
    cancelled: "Отменена",
    disputed: "Спор"
  }
};

export const getStatusBadge = (status, role = "seller") => {
  const labels = tradeStatusLabels[role] || tradeStatusLabels.seller;
  return {
    className: `px-2 py-1 text-xs rounded-full font-medium ${tradeStatusStyles[status] || tradeStatusStyles.pending}`,
    label: labels[status] || status
  };
};
