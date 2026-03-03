import React from 'react';
import { Copy, Check } from 'lucide-react';
import { toast } from 'sonner';

/**
 * Компонент для отображения копируемого ID заказа
 * Единый формат для всех ролей: показывает ПОЛНЫЙ ID с возможностью копирования
 * 
 * ID заказа всегда одинаковый везде: у покупателя, трейдера, мерчанта и админа
 */
const CopyableOrderId = ({ 
  orderId, 
  className = '',
  showHash = false, // По умолчанию показываем ПОЛНЫЙ ID (для единообразия)
  prefix = '#',
  size = 'default' // 'small', 'default', 'large'
}) => {
  const [copied, setCopied] = React.useState(false);
  
  if (!orderId) return <span className="text-zinc-500">-</span>;
  
  // Показываем ПОЛНЫЙ Order ID для единообразия во всей системе
  // При showHash=true показываем сокращённую версию (для компактных списков)
  const getDisplayId = (id) => {
    if (!id) return '-';
    
    if (!showHash) {
      // Полный ID как есть
      return id;
    }
    
    // Сокращённая версия для компактного отображения
    const parts = id.split('_');
    if (parts.length >= 3) {
      return parts[parts.length - 1];
    }
    // Для формата ORD-0001
    const dashParts = id.split('-');
    if (dashParts.length >= 2) {
      return dashParts[dashParts.length - 1];
    }
    return id.slice(-6).toUpperCase();
  };
  
  const displayId = getDisplayId(orderId);
  
  const handleCopy = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    try {
      await navigator.clipboard.writeText(orderId);
      setCopied(true);
      toast.success(`ID скопирован: ${orderId}`);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      // Fallback для старых браузеров
      const textArea = document.createElement('textarea');
      textArea.value = orderId;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      setCopied(true);
      toast.success(`ID скопирован: ${orderId}`);
      setTimeout(() => setCopied(false), 2000);
    }
  };
  
  const sizeClasses = {
    small: 'text-xs px-1.5 py-0.5 gap-1',
    default: 'text-sm px-2 py-1 gap-1.5',
    large: 'text-base px-2.5 py-1.5 gap-2'
  };
  
  const iconSizes = {
    small: 'w-3 h-3',
    default: 'w-3.5 h-3.5',
    large: 'w-4 h-4'
  };
  
  return (
    <button
      onClick={handleCopy}
      className={`
        inline-flex items-center 
        font-['JetBrains_Mono'] 
        bg-zinc-800/50 hover:bg-zinc-700/50 
        border border-zinc-700 hover:border-zinc-600
        rounded transition-all duration-200
        cursor-pointer select-none
        ${sizeClasses[size]}
        ${className}
      `}
      title={`Нажмите чтобы скопировать: ${orderId}`}
      data-testid={`copy-order-id-${orderId}`}
    >
      <span className="text-zinc-300">{prefix}{displayId}</span>
      {copied ? (
        <Check className={`${iconSizes[size]} text-emerald-400`} />
      ) : (
        <Copy className={`${iconSizes[size]} text-zinc-500 hover:text-zinc-300`} />
      )}
    </button>
  );
};

export default CopyableOrderId;
