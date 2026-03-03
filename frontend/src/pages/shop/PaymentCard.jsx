import React from 'react';
import { Button } from '@/components/ui/button';
import { 
  X, Timer, Check, Copy, AlertTriangle,
  CreditCard, Smartphone, Phone, QrCode
} from 'lucide-react';

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

const fmtTime = (s) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`;

export default function PaymentCard({
  trade,
  depositAmount,
  timeLeft,
  requisite,
  cancelTrade,
  markPaid,
  copy
}) {
  const ReqIcon = requisite ? getRequisiteIcon(requisite.type) : CreditCard;

  return (
    <div className="bg-[#121212] rounded-2xl p-6 border border-white/5">
      <Button variant="ghost" onClick={cancelTrade} className="text-[#71717A] hover:text-white mb-4">
        <X className="w-4 h-4 mr-1" /> Отменить сделку
      </Button>

      <div className="text-center mb-4">
        <div className="w-14 h-14 rounded-2xl bg-[#F59E0B]/10 flex items-center justify-center mx-auto mb-3">
          <Timer className="w-7 h-7 text-[#F59E0B]" />
        </div>
        <h2 className="text-lg font-bold text-white">Переведите точную сумму</h2>
        {timeLeft != null && (
          <div className="text-sm text-[#F59E0B] mt-1">
            Осталось: {fmtTime(timeLeft)}
          </div>
        )}
      </div>

      {!requisite ? (
        <div className="text-center py-4 text-[#71717A]">
          <AlertTriangle className="w-8 h-8 mx-auto mb-2 text-[#F59E0B]" />
          <p>Реквизиты загружаются...</p>
        </div>
      ) : (
        <div className="space-y-3">
          {/* Amount */}
          <div className="bg-[#0A0A0A] rounded-xl p-4 text-center">
            <div className="text-[#71717A] text-xs mb-1">Сумма к оплате</div>
            <div className="text-3xl font-bold text-white font-['JetBrains_Mono']">
              {Math.round(trade.amount_rub || depositAmount).toLocaleString()} RUB
            </div>
          </div>

          {/* Requisite details */}
          <div className="bg-[#0A0A0A] rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <ReqIcon className="w-4 h-4 text-[#7C3AED]" />
              <span className="text-[#71717A] text-sm">{getRequisiteLabel(requisite.type)}</span>
            </div>

            {requisite.data?.card_number && (
              <div className="flex items-center justify-between py-2">
                <span className="text-white font-mono text-lg tracking-wider">{requisite.data.card_number}</span>
                <button onClick={() => copy(requisite.data.card_number)} className="text-[#7C3AED] hover:text-white p-1">
                  <Copy className="w-4 h-4" />
                </button>
              </div>
            )}
            {requisite.data?.phone && (
              <div className="flex items-center justify-between py-2">
                <span className="text-white font-mono text-lg">{requisite.data.phone}</span>
                <button onClick={() => copy(requisite.data.phone)} className="text-[#7C3AED] hover:text-white p-1">
                  <Copy className="w-4 h-4" />
                </button>
              </div>
            )}
            {requisite.data?.bank_name && (
              <div className="text-[#52525B] text-sm">{requisite.data.bank_name}</div>
            )}
            {requisite.data?.card_holder && (
              <div className="text-[#71717A] text-sm mt-1">{requisite.data.card_holder}</div>
            )}
          </div>
        </div>
      )}

      <Button onClick={markPaid} className="w-full h-14 bg-[#10B981] hover:bg-[#059669] text-white text-lg rounded-xl mt-4">
        <Check className="w-6 h-6 mr-2" /> Я оплатил
      </Button>
    </div>
  );
}
