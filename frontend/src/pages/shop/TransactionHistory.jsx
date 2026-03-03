import React from 'react';
import { X, CheckCircle, Clock, AlertTriangle, ExternalLink } from 'lucide-react';

export default function TransactionHistory({ 
  transactions, 
  loadingHistory, 
  showHistory, 
  setShowHistory 
}) {
  if (!showHistory) return null;

  return (
    <div className="bg-[#121212] border border-white/10 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-white">История пополнений</h2>
        <button onClick={() => setShowHistory(false)} className="text-[#71717A] hover:text-white">
          <X className="w-5 h-5" />
        </button>
      </div>

      {loadingHistory ? (
        <div className="text-center py-8 text-[#71717A]">Загрузка...</div>
      ) : transactions.length === 0 ? (
        <div className="text-center py-8 text-[#71717A]">Нет операций</div>
      ) : (
        <div className="space-y-2 max-h-[400px] overflow-y-auto">
          {transactions.map((tx, i) => (
            <div key={i} className="bg-[#0A0A0A] rounded-xl p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                  tx.status === 'completed' ? 'bg-[#10B981]/20' :
                  tx.status === 'pending' ? 'bg-[#F59E0B]/20' :
                  tx.status === 'disputed' ? 'bg-[#EF4444]/20' :
                  'bg-[#71717A]/20'
                }`}>
                  {tx.status === 'completed' ? <CheckCircle className="w-5 h-5 text-[#10B981]" /> :
                   tx.status === 'pending' ? <Clock className="w-5 h-5 text-[#F59E0B]" /> :
                   tx.status === 'disputed' ? <AlertTriangle className="w-5 h-5 text-[#EF4444]" /> :
                   <Clock className="w-5 h-5 text-[#71717A]" />}
                </div>
                <div>
                  <p className="text-white font-medium">{tx.client_amount_rub || tx.amount_rub || 0} ₽</p>
                  <p className="text-[#71717A] text-xs">
                    {new Date(tx.created_at).toLocaleString('ru-RU')}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <span className={`text-xs px-2 py-1 rounded-full ${
                  tx.status === 'completed' ? 'bg-[#10B981]/20 text-[#10B981]' :
                  tx.status === 'pending' ? 'bg-[#F59E0B]/20 text-[#F59E0B]' :
                  tx.status === 'disputed' ? 'bg-[#EF4444]/20 text-[#EF4444]' :
                  'bg-[#71717A]/20 text-[#71717A]'
                }`}>
                  {tx.status === 'completed' ? 'Завершено' :
                   tx.status === 'pending' ? 'Ожидает' :
                   tx.status === 'disputed' ? 'Спор' :
                   tx.status === 'paid' ? 'Оплачено' :
                   tx.status === 'cancelled' ? 'Отменено' : tx.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
