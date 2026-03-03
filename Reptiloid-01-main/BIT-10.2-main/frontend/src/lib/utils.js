import { clsx } from "clsx";
import { twMerge } from "tailwind-merge"

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

/**
 * Форматирует ID заказа/спора для отображения
 * Показывает полный ID для единообразия между ролями
 * @param {string} id - ID заказа или спора
 * @param {string} externalId - Внешний ID (опционально)
 * @returns {string} Отформатированный ID
 */
export function formatOrderId(id, externalId = null) {
  if (externalId) {
    return `${id} (${externalId})`;
  }
  return id || '-';
}

/**
 * Форматирует короткий ID для отображения в карточках
 * @param {string} id - ID заказа или спора
 * @returns {string} Короткий ID
 */
export function formatShortId(id) {
  if (!id) return '-';
  // Если ID содержит дату (формат xxx_YYYYMMDD_HASH), показываем HASH
  const parts = id.split('_');
  if (parts.length >= 3) {
    return parts[parts.length - 1];
  }
  // Иначе показываем полный ID
  return id;
}
