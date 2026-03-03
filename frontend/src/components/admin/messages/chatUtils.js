/**
 * Утилиты и константы для чата администратора
 */

// Категории магазина (English -> Russian)
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

// Конфигурация ролей
export const ROLE_CONFIG = {
  user: { color: 'bg-white text-black border border-gray-300', name: 'Пользователь', marker: 'bg-white border border-gray-400' },
  buyer: { color: 'bg-white text-black border border-gray-300', name: 'Покупатель', marker: 'bg-white border border-gray-400' },
  client: { color: 'bg-white text-black border border-gray-300', name: 'Клиент', marker: 'bg-white border border-gray-400' },
  p2p_seller: { color: 'bg-white text-black border border-gray-300', name: 'Продавец 💱', marker: 'bg-white border border-gray-400' },
  trader: { color: 'bg-white text-black border border-gray-300', name: 'Оператор 💱', marker: 'bg-[#10B981]' },
  shop_owner: { color: 'bg-white text-black border border-gray-300', name: '🏪 Магазин', marker: 'bg-[#8B5CF6]' },
  merchant: { color: 'bg-white text-black border border-gray-300', name: '🟠 Мерчант', marker: 'bg-[#F97316]' },
  mod_p2p: { color: 'bg-[#F59E0B] text-white', name: 'Модератор P2P', marker: 'bg-[#F59E0B]' },
  mod_market: { color: 'bg-[#F59E0B] text-white', name: '⚖️ Гарант', marker: 'bg-[#F59E0B]' },
  support: { color: 'bg-[#3B82F6] text-white', name: 'Поддержка', marker: 'bg-[#3B82F6]' },
  admin: { color: 'bg-[#EF4444] text-white', name: 'Администратор', marker: 'bg-[#EF4444]' },
  owner: { color: 'bg-[#EF4444] text-white', name: '👑 Владелец', marker: 'bg-[#EF4444]' },
  system: { color: 'bg-[#6B7280] text-white', name: 'Система', marker: 'bg-[#6B7280]' }
};

export const getRoleInfo = (role) => ROLE_CONFIG[role] || ROLE_CONFIG.user;

// Статусы чатов
export const STATUS_CONFIG = {
  pending: { color: 'bg-[#F59E0B]/10 text-[#F59E0B]', label: 'Ожидание' },
  active: { color: 'bg-[#3B82F6]/10 text-[#3B82F6]', label: 'Активный' },
  completed: { color: 'bg-[#10B981]/10 text-[#10B981]', label: 'Завершён' },
  cancelled: { color: 'bg-[#71717A]/10 text-[#71717A]', label: 'Отменён' },
  disputed: { color: 'bg-[#EF4444]/10 text-[#EF4444]', label: 'Спор' },
  paid: { color: 'bg-[#3B82F6]/10 text-[#3B82F6]', label: 'Оплачено' }
};

export const getStatusInfo = (status) => STATUS_CONFIG[status] || STATUS_CONFIG.pending;

// Типы чатов
export const CONVERSATION_TYPES = {
  p2p_dispute: { label: 'P2P Спор', icon: 'Scale', color: 'text-[#EF4444]' },
  crypto_order: { label: 'Вывод крипты', icon: 'ArrowDownRight', color: 'text-[#F59E0B]' },
  merchant_app: { label: 'Заявка мерчанта', icon: 'Briefcase', color: 'text-[#8B5CF6]' },
  shop_app: { label: 'Заявка магазина', icon: 'Store', color: 'text-[#10B981]' },
  support: { label: 'Поддержка', icon: 'HelpCircle', color: 'text-[#3B82F6]' },
  marketplace: { label: 'Маркетплейс', icon: 'Store', color: 'text-[#8B5CF6]' },
  user_chat: { label: 'Личный чат', icon: 'MessageCircle', color: 'text-white' }
};

export const getConversationType = (type) => CONVERSATION_TYPES[type] || { label: type, icon: 'MessageCircle', color: 'text-white' };

// Форматирование даты
export const formatDate = (dateStr) => {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now - date;
  
  // Меньше минуты
  if (diff < 60000) return 'только что';
  // Меньше часа
  if (diff < 3600000) return `${Math.floor(diff / 60000)} мин`;
  // Сегодня
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  }
  // Вчера
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) {
    return 'вчера ' + date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  }
  // Другое
  return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
};

// Форматирование полной даты
export const formatFullDate = (dateStr) => {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
};

// Обрезка текста
export const truncate = (text, maxLength = 50) => {
  if (!text) return '';
  return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
};
