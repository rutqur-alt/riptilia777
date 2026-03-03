// ChatActions - Decision buttons for different conversation types
import React, { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { API } from "@/App";

export function ChatActions({
  selectedConv,
  adminRole,
  onDecision,
  onOpenTemplates,
  onOpenCommission,
  setNewMessage,
  token
}) {
  const [reasonMode, setReasonMode] = useState(null); // null | { action, label }
  const [reasonText, setReasonText] = useState("");

  const canShowActions = selectedConv.status === "pending" || 
    selectedConv.status === "pending_confirmation" || 
    selectedConv.status === "pending_payment" || 
    selectedConv.status === "disputed" || 
    selectedConv.status === "dispute" || 
    selectedConv.status === "open" || 
    selectedConv.status === "active" || 
    selectedConv.status === "paid" || 
    selectedConv.status === "funded" ||
    selectedConv.status === "pending_delivery";

  if (!canShowActions) return null;

  const askReason = (action, label) => {
    setReasonMode({ action, label });
    setReasonText("");
  };

  const submitReason = () => {
    if (!reasonText.trim()) {
      toast.error("Укажите причину");
      return;
    }
    onDecision(reasonMode.action, { reason: reasonText.trim() });
    setReasonMode(null);
    setReasonText("");
  };

  const cancelReason = () => {
    setReasonMode(null);
    setReasonText("");
  };

  const handlePartialRefund = () => {
    askReason("__partial_refund_amount__", "Сумма частичного возврата (USDT)");
  };

  const submitPartialRefund = () => {
    const amount = parseFloat(reasonText);
    if (!amount || isNaN(amount)) {
      toast.error("Укажите сумму");
      return;
    }
    // After getting amount, ask for reason
    setReasonMode({ action: "refund_partial", label: "Причина возврата", extra: { amount } });
    setReasonText("Частичный возврат по решению гаранта");
  };

  const handleReasonSubmit = () => {
    if (reasonMode.action === "__partial_refund_amount__") {
      submitPartialRefund();
      return;
    }
    if (reasonMode.extra) {
      onDecision(reasonMode.action, { ...reasonMode.extra, reason: reasonText.trim() || "По решению администратора" });
    } else {
      submitReason();
    }
    setReasonMode(null);
    setReasonText("");
  };

  // If asking for reason, show input
  if (reasonMode) {
    return (
      <div className="p-3 border-b border-white/5 bg-[#0A0A0A]">
        <div className="text-[10px] text-[#52525B] mb-2">{reasonMode.label}:</div>
        <div className="flex gap-2">
          <input
            type="text"
            value={reasonText}
            onChange={(e) => setReasonText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleReasonSubmit()}
            placeholder={reasonMode.label + "..."}
            className="flex-1 px-3 py-1.5 bg-[#121212] border border-white/10 rounded-lg text-white text-xs focus:outline-none focus:border-[#7C3AED]"
            autoFocus
          />
          <button
            onClick={handleReasonSubmit}
            className="px-3 py-1.5 bg-[#10B981]/20 text-[#10B981] rounded-lg text-xs hover:bg-[#10B981]/30"
          >
            Подтвердить
          </button>
          <button
            onClick={cancelReason}
            className="px-3 py-1.5 bg-[#EF4444]/20 text-[#EF4444] rounded-lg text-xs hover:bg-[#EF4444]/30"
          >
            Отмена
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-3 border-b border-white/5 bg-[#0A0A0A]">
      <div className="text-[10px] text-[#52525B] mb-2">ДЕЙСТВИЯ:</div>
      <div className="flex flex-wrap gap-2">
        {selectedConv.type === "p2p_dispute" && (
          <>
            <ActionButton 
              onClick={() => onOpenTemplates("dispute")} 
              color="#8B5CF6" 
              icon="⚡" 
              label="Авто-сообщение"
              testId="auto-message-dispute-btn"
            />
            <ActionButton 
              onClick={() => askReason("refund_buyer", "Причина возврата покупателю")} 
              color="#10B981" 
              icon="💰" 
              label="В пользу покупателя"
              testId="refund-buyer-btn"
            />
            <ActionButton 
              onClick={() => askReason("cancel_dispute", "Причина отмены спора")} 
              color="#EF4444" 
              icon="❌" 
              label="Отменить"
              testId="cancel-dispute-btn"
            />
          </>
        )}

        {selectedConv.type === "merchant_application" && (
          <>
            <ActionButton 
              onClick={() => onOpenTemplates("merchant_app")} 
              color="#8B5CF6" 
              icon="⚡" 
              label="Авто-сообщение"
              testId="auto-message-btn"
            />
            {(adminRole === "owner" || adminRole === "admin") && (
              <ActionButton 
                onClick={() => onOpenCommission("merchant")} 
                color="#10B981" 
                icon="✅" 
                label="Одобрить"
                testId="approve-merchant-btn"
              />
            )}
            <ActionButton 
              onClick={() => askReason("reject", "Причина отказа")} 
              color="#EF4444" 
              icon="❌" 
              label="Отклонить"
              testId="reject-merchant-btn"
            />
          </>
        )}

        {selectedConv.type === "shop_application" && (
          <>
            <ActionButton 
              onClick={() => onOpenTemplates("shop_app")} 
              color="#8B5CF6" 
              icon="⚡" 
              label="Авто-сообщение"
              testId="auto-message-shop-btn"
            />
            {(adminRole === "owner" || adminRole === "admin") && (
              <ActionButton 
                onClick={() => onOpenCommission("shop")} 
                color="#10B981" 
                icon="✅" 
                label="Одобрить"
                testId="approve-shop-btn"
              />
            )}
            <ActionButton 
              onClick={() => askReason("reject", "Причина отказа")} 
              color="#EF4444" 
              icon="❌" 
              label="Отклонить"
              testId="reject-shop-btn"
            />
          </>
        )}

        {selectedConv.type === "marketplace_guarantor" && (
          <>
            <ActionButton 
              onClick={() => askReason("complete", "Причина завершения сделки")} 
              color="#10B981" 
              icon="✅" 
              label="Завершить сделку"
              testId="release-to-seller-btn"
            />
            <ActionButton 
              onClick={() => askReason("refund", "Причина отмены сделки")} 
              color="#EF4444" 
              icon="❌" 
              label="Отменить сделку"
              testId="full-refund-btn"
            />
          </>
        )}

        {selectedConv.type === "crypto_order" && (
          <>
            <ActionButton 
              onClick={() => onOpenTemplates("crypto_order")} 
              color="#8B5CF6" 
              icon="⚡" 
              label="Авто-сообщение"
            />
            {selectedConv.status === "dispute" && (
              <>
                <ActionButton 
                  onClick={() => askReason("refund_buyer", "Причина возврата покупателю")} 
                  color="#10B981" 
                  icon="💰" 
                  label="Возврат покупателю"
                />
                <ActionButton 
                  onClick={() => askReason("complete_order", "Причина решения в пользу мерчанта")} 
                  color="#F97316" 
                  icon="✅" 
                  label="В пользу мерчанта"
                />
              </>
            )}
            {selectedConv.status !== "dispute" && selectedConv.status !== "completed" && (
              <ActionButton 
                onClick={() => onDecision("mark_completed", {})} 
                color="#10B981" 
                icon="✅" 
                label="Завершить"
              />
            )}
          </>
        )}

        {(selectedConv.type === "support_ticket" || selectedConv.type === "unified_support_ticket") && (
          <>
            <ActionButton 
              onClick={() => onOpenTemplates("support")} 
              color="#8B5CF6" 
              icon="⚡" 
              label="Авто-сообщение"
              testId="auto-message-support-btn"
            />
            <ActionButton 
              onClick={() => setNewMessage("📋 Предоставьте дополнительную информацию")} 
              color="#3B82F6" 
              icon="📋" 
              label="Запросить информацию"
            />
            <ActionButton 
              onClick={() => onDecision("resolved", {})} 
              color="#10B981" 
              icon="✅" 
              label="Решить"
            />
            <ActionButton 
              onClick={() => onDecision("closed", {})} 
              color="#52525B" 
              icon="🔒" 
              label="Закрыть"
            />
          </>
        )}
      </div>
    </div>
  );
}

function ActionButton({ onClick, color, icon, label, testId }) {
  return (
    <button 
      onClick={onClick} 
      className={`px-3 py-1.5 bg-[${color}]/10 text-[${color}] rounded-lg text-xs hover:bg-[${color}]/20`}
      style={{ 
        backgroundColor: `${color}1a`, 
        color: color 
      }}
      data-testid={testId}
    >
      {icon} {label}
    </button>
  );
}

export default ChatActions;
