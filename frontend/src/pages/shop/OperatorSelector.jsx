import React from 'react';
import { Button } from '@/components/ui/button';
import { 
  X, User, CheckCircle, AlertTriangle, Shield, ChevronDown, Check,
  CreditCard, Smartphone, Phone, QrCode
} from 'lucide-react';
import { getPaymentMethod } from '@/config/paymentMethods';

const getRequisiteIcon = (type) => {
  switch (type) {
    case "card": return CreditCard;
    case "sbp": return Smartphone;
    case "sim": return Phone;
    case "qr_code": return QrCode;
    default: return CreditCard;
  }
};

const getRequisiteLabel = (type) => {
  switch (type) {
    case "card": return "Банковская карта";
    case "sbp": return "СБП";
    case "sim": return "Мобильный";
    case "qr_code": return "QR-код";
    default: return type;
  }
};

export default function OperatorSelector({
  depositAmount,
  operators,
  filteredOperators,
  selectedFilter,
  setSelectedFilter,
  availableMethods,
  showMethodsDropdown,
  setShowMethodsDropdown,
  openOperatorDialog,
  resetFlow
}) {
  return (
    <div>
      {/* Back button + amount header */}
      <div className="flex items-center justify-between mb-4">
        <Button
          variant="ghost"
          onClick={resetFlow}
          className="text-[#71717A] hover:text-white"
        >
          <X className="w-4 h-4 mr-1" /> Отмена
        </Button>
        <div className="text-right">
          <div className="text-[#71717A] text-xs">Пополнение</div>
          <div className="text-xl font-bold text-white font-['JetBrains_Mono']">
            {depositAmount.toLocaleString()} RUB
          </div>
        </div>
      </div>

      {/* Payment method filter */}
      <div className="relative mb-4">
        <button
          onClick={() => setShowMethodsDropdown(!showMethodsDropdown)}
          className="flex items-center justify-between gap-3 px-4 py-3 bg-[#121212] border border-white/10 rounded-xl hover:border-white/20 transition-colors min-w-[200px]"
        >
          <span className="text-white">
            {selectedFilter === "all" ? "Все методы оплаты" : getPaymentMethod(selectedFilter).name}
          </span>
          <ChevronDown className={`w-4 h-4 text-[#71717A] transition-transform ${showMethodsDropdown ? 'rotate-180' : ''}`} />
        </button>
        {showMethodsDropdown && (
          <div className="absolute top-full left-0 mt-2 bg-[#1A1A1A] border border-white/10 rounded-xl overflow-hidden z-20 shadow-xl min-w-[200px]">
            <button
              onClick={() => { setSelectedFilter("all"); setShowMethodsDropdown(false); }}
              className={`w-full flex items-center justify-between gap-3 px-4 py-3 hover:bg-white/5 transition-colors ${selectedFilter === "all" ? "text-white" : "text-[#A1A1AA]"}`}
            >
              <span>Все методы</span>
              {selectedFilter === "all" && <Check className="w-4 h-4 text-white" />}
            </button>
            {availableMethods.map(methodType => {
              const info = getPaymentMethod(methodType);
              return (
                <button
                  key={methodType}
                  onClick={() => { setSelectedFilter(methodType); setShowMethodsDropdown(false); }}
                  className={`w-full flex items-center gap-3 px-4 py-3 transition-colors ${selectedFilter === methodType ? "bg-[#7C3AED] text-white" : "text-[#A1A1AA] hover:bg-white/5"}`}
                >
                  <span className="text-lg">{info.emoji}</span>
                  <span className="flex-1 text-left">{info.name}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Operators count */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-[#71717A] text-sm">
          {filteredOperators.length} {filteredOperators.length === 1 ? 'оператор' : 'операторов'}
        </span>
        <span className="text-xs text-[#52525B]">Лучшая цена сверху</span>
      </div>

      {/* Operators list */}
      {filteredOperators.length === 0 ? (
        <div className="bg-[#121212] rounded-2xl p-8 text-center border border-white/5">
          <AlertTriangle className="w-12 h-12 text-[#F59E0B] mx-auto mb-3" />
          <h2 className="text-lg font-semibold text-white mb-2">Нет доступных операторов</h2>
          <p className="text-[#71717A] text-sm">
            {selectedFilter !== "all" ? "Попробуйте другой способ оплаты" : "Попробуйте позже"}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {filteredOperators.map((op) => {
            const bestPrice = filteredOperators[0]?.toPayRub || depositAmount;
            const isBest = op.toPayRub === bestPrice;
            // Support both requisites (old) and payment_methods (new white-label API)
            const uniqueTypes = [...new Set(op.payment_methods || op.requisites?.map(r => r.type) || [])];

            return (
              <div
                key={op.offer_id}
                onClick={() => openOperatorDialog(op)}
                className={`bg-[#121212] border hover:bg-[#1A1A1A] rounded-xl p-4 cursor-pointer transition-all ${isBest ? "border-[#10B981]/30" : "border-white/5 hover:border-[#7C3AED]/30"}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="relative">
                      <div className="w-10 h-10 rounded-full bg-[#1A1A1A] flex items-center justify-center">
                        <User className="w-5 h-5 text-[#52525B]" />
                      </div>
                      <div className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-[#121212] ${op.is_online ? 'bg-[#10B981]' : 'bg-[#52525B]'}`} />
                    </div>
                    <div>
                      <div className="text-white font-medium text-sm flex items-center gap-2">
                        {op.nickname || op.trader_login}
                        {isBest && (
                          <span className="px-2 py-0.5 bg-[#10B981]/10 text-[#10B981] text-xs rounded-full">
                            Лучшая цена
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 text-xs text-[#52525B]">
                        <span className="flex items-center gap-1"><CheckCircle className="w-3 h-3 text-[#10B981]" />{op.success_rate || 100}%</span>
                        <span>{op.trades_count || 0} сделок</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    <div className="hidden sm:flex flex-wrap gap-1">
                      {uniqueTypes.map((type, idx) => {
                        const Icon = getRequisiteIcon(type);
                        return (
                          <span key={idx} className="inline-flex items-center gap-1 px-2 py-1 bg-[#1A1A1A] text-[#A1A1AA] text-xs rounded">
                            <Icon className="w-3 h-3" />
                            {getRequisiteLabel(type)}
                          </span>
                        );
                      })}
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-bold text-white font-['JetBrains_Mono']">
                        {Math.round(op.toPayRub).toLocaleString()} RUB
                      </div>
                      {op.commissionPercent > 0 && (
                        <div className="text-xs text-[#F59E0B]">+{op.commissionPercent}%</div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <p className="text-center text-[#52525B] text-xs mt-6 flex items-center justify-center gap-2">
        <Shield className="w-4 h-4" /> Безопасная оплата
      </p>
    </div>
  );
}
