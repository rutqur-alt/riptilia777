// Constants for UnifiedMessagesHub
import {
  MessageCircle, Scale, ArrowDownRight, Briefcase, Shield, Store,
  HelpCircle, Users, UserPlus
} from "lucide-react";

// Shop categories mapping (English -> Russian)
export const SHOP_CATEGORIES = {
  accounts: "Аккаунты",
  software: "Софт",
  databases: "Базы данных",
  tools: "Инструменты",
  guides: "Гайды и схемы",
  keys: "Ключи",
  financial: "Финансовое",
  templates: "Шаблоны",
  other: "Другое"
};

export const getCategoryLabel = (cat) => SHOP_CATEGORIES[cat] || cat;

// Role colors per spec
export const ROLE_CONFIG = {
  user: { color: 'bg-white text-black border border-gray-300', name: 'Пользователь', marker: 'bg-white border border-gray-400' },
  buyer: { color: 'bg-white text-black border border-gray-300', name: 'Покупатель', marker: 'bg-white border border-gray-400' },
  p2p_seller: { color: 'bg-white text-black border border-gray-300', name: 'Продавец', marker: 'bg-white border border-gray-400' },
  shop_owner: { color: 'bg-white text-black border border-gray-300', name: 'Магазин', marker: 'bg-[#8B5CF6]' },
  merchant: { color: 'bg-white text-black border border-gray-300', name: 'Мерчант', marker: 'bg-[#F97316]' },
  mod_p2p: { color: 'bg-[#F59E0B] text-white', name: 'Модератор P2P', marker: 'bg-[#F59E0B]' },
  mod_market: { color: 'bg-[#F59E0B] text-white', name: 'Гарант', marker: 'bg-[#F59E0B]' },
  support: { color: 'bg-[#3B82F6] text-white', name: 'Поддержка', marker: 'bg-[#3B82F6]' },
  admin: { color: 'bg-[#EF4444] text-white', name: 'Администратор', marker: 'bg-[#EF4444]' },
  owner: { color: 'bg-[#EF4444] text-white', name: 'Владелец', marker: 'bg-[#EF4444]' },
  system: { color: 'bg-[#6B7280] text-white', name: 'Система', marker: 'bg-[#6B7280]' }
};

export const getRoleInfo = (role) => ROLE_CONFIG[role] || ROLE_CONFIG.user;

// Get categories based on admin role
export const getCategories = (adminRole) => {
  const baseCategories = [
    { key: "all", label: "Все", icon: MessageCircle, color: "text-white" }
  ];
  
  // P2P Moderator: disputes, crypto payouts, merchant apps
  if (adminRole === "mod_p2p" || adminRole === "owner" || adminRole === "admin") {
    baseCategories.push({ key: "p2p_dispute", label: "P2P Споры", icon: Scale, color: "text-[#EF4444]" });
    baseCategories.push({ key: "crypto_payout", label: "Выплаты", icon: ArrowDownRight, color: "text-[#10B981]" });
    baseCategories.push({ key: "merchant_app", label: "Заявки мерчантов", icon: Briefcase, color: "text-[#F97316]" });
  }
  
  // Marketplace Moderator (Guarantor): marketplace disputes, shop apps, guarantor orders
  if (adminRole === "mod_market" || adminRole === "owner" || adminRole === "admin") {
    baseCategories.push({ key: "guarantor", label: "Гарант-сделки", icon: Shield, color: "text-[#F59E0B]" });
    baseCategories.push({ key: "shop_app", label: "Заявки магазинов", icon: Store, color: "text-[#8B5CF6]" });
  }
  
  // Support: support tickets
  if (adminRole === "support" || adminRole === "owner" || adminRole === "admin") {
    baseCategories.push({ key: "support", label: "Поддержка", icon: HelpCircle, color: "text-[#3B82F6]" });
  }
  
  // Admin/Owner/Mods: write to users
  if (adminRole === "owner" || adminRole === "admin" || adminRole === "mod_p2p" || adminRole === "mod_market") {
    baseCategories.push({ key: "admin_to_user", label: "Пользователям", icon: Users, color: "text-[#71717A]" });
  }
  
  // All staff: show chats they were invited to
  baseCategories.push({ key: "invited", label: "Приглашённые", icon: UserPlus, color: "text-[#F59E0B]" });
  
  return baseCategories;
};

// Icon/Color helpers
export const getCategoryIcon = (category) => {
  switch (category) {
    case "p2p_dispute": return Scale;
    case "merchant_app": return Briefcase;
    case "shop_app": return Store;
    case "support": return HelpCircle;
    case "guarantor": return Shield;
    default: return MessageCircle;
  }
};

export const getCategoryColor = (category) => {
  switch (category) {
    case "p2p_dispute": return "text-[#EF4444]";
    case "merchant_app": return "text-[#F97316]";
    case "shop_app": return "text-[#8B5CF6]";
    case "support": return "text-[#3B82F6]";
    case "marketplace": return "text-[#8B5CF6]";
    case "crypto_payout": return "text-[#10B981]";
    case "guarantor": return "text-[#F59E0B]";
    default: return "text-[#71717A]";
  }
};
