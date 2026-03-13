// Role display config for dispute chat (extracted from MerchantDashboard.js)

export const MERCHANT_ROLE_DISPLAY = {
  user:        { label: "Пользователь", color: "#3B82F6", bg: "bg-white/10 text-white" },
  buyer:       { label: "Покупатель",   color: "#3B82F6", bg: "bg-white/10 text-white" },
  p2p_seller:  { label: "Продавец",     color: "#3B82F6", bg: "bg-white/10 text-white" },
  trader:      { label: "Трейдер",      color: "#10B981", bg: "bg-[#10B981]/20 text-white" },
  merchant:    { label: "Мерчант",      color: "#F97316", bg: "bg-[#F97316]/20 text-white" },
  shop_owner:  { label: "Магазин",      color: "#8B5CF6", bg: "bg-[#8B5CF6]/20 text-white" },
  qr_provider: { label: "QR Провайдер", color: "#A855F7", bg: "bg-[#A855F7]/20 text-white" },
  mod_p2p:     { label: "Модератор",    color: "#F59E0B", bg: "bg-[#F59E0B]/20 text-white" },
  moderator:   { label: "Модератор",    color: "#F59E0B", bg: "bg-[#F59E0B]/20 text-white" },
  mod_market:  { label: "Гарант",       color: "#F59E0B", bg: "bg-[#F59E0B]/20 text-white" },
  support:     { label: "Поддержка",    color: "#3B82F6", bg: "bg-[#3B82F6]/20 text-white" },
  admin:       { label: "Админ",        color: "#EF4444", bg: "bg-[#EF4444]/20 text-white" },
  owner:       { label: "Супер Админ",  color: "#EF4444", bg: "bg-[#EF4444]/20 text-white" },
  system:      { label: "Система",      color: "#6B7280", bg: "bg-[#6B7280]/20 text-white" },
};

export const getMerchantRoleDisplay = (role) => MERCHANT_ROLE_DISPLAY[role] || MERCHANT_ROLE_DISPLAY.user;
