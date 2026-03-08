/**
 * Shared NotificationDropdown component used by TraderDashboard and MerchantDashboard.
 * Renders a notification bell/button with a dropdown list of unread notifications.
 *
 * Props:
 *   badges       - object with notification counts (e.g. { trades: 3, messages: 1, total: 4, ... })
 *   token        - JWT token for API calls
 *   role         - "trader" | "merchant"
 *   buildItems   - (badges, prefix) => array of { key, label, path, count } — role-specific items builder
 */
import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import axios from "axios";
import { API } from "@/App";

export default function NotificationDropdown({ badges, token, role, buildItems }) {
  const [open, setOpen] = useState(false);
  const [localBadges, setLocalBadges] = useState(badges);
  const dropdownRef = useRef(null);
  const buttonRef = useRef(null);
  const prefix = role === "merchant" ? "/merchant" : "/trader";

  useEffect(() => { setLocalBadges(badges); }, [badges]);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target) && buttonRef.current && !buttonRef.current.contains(event.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const declension = (n) => {
    const abs = Math.abs(n) % 100;
    const n1 = abs % 10;
    if (abs > 10 && abs < 20) return "\u0441\u043E\u0431\u044B\u0442\u0438\u0439";
    if (n1 > 1 && n1 < 5) return "\u0441\u043E\u0431\u044B\u0442\u0438\u044F";
    if (n1 === 1) return "\u0441\u043E\u0431\u044B\u0442\u0438\u0435";
    return "\u0441\u043E\u0431\u044B\u0442\u0438\u0439";
  };

  const handleItemClick = async (item) => {
    const updated = { ...localBadges, [item.key]: 0 };
    updated.total = Object.entries(updated).filter(([k]) => !["total","trade_payments","trade_events","disputes","guarantor_unread","support","shop_customer_messages"].includes(k)).reduce((s, [, v]) => s + (v || 0), 0);
    setLocalBadges(updated);
    setOpen(false);
    try {
      await axios.post(`${API}/notifications/read`, { type: item.key }, { headers: { Authorization: `Bearer ${token}` } });
    } catch (e) { console.error(e); }
    window.location.href = item.path;
  };

  const handleReadAll = async () => {
    const zeroed = {};
    Object.keys(localBadges).forEach(k => zeroed[k] = 0);
    setLocalBadges(zeroed);
    setOpen(false);
    try {
      await axios.post(`${API}/notifications/read`, {}, { headers: { Authorization: `Bearer ${token}` } });
    } catch (e) { console.error(e); }
  };

  const total = localBadges.total || 0;
  const items = buildItems(localBadges, prefix);

  const getDropdownPos = () => {
    if (!buttonRef.current) return { top: 100, left: 60 };
    const r = buttonRef.current.getBoundingClientRect();
    return { top: r.bottom + 4, left: Math.max(r.left, 10) };
  };

  return (
    <>
      <button
        ref={buttonRef}
        onClick={() => setOpen(!open)}
        className={total > 0 ? "text-xs text-[#EF4444] bg-[#EF4444]/10 px-2 py-0.5 rounded-full hover:bg-[#EF4444]/20 transition-colors cursor-pointer whitespace-nowrap" : "text-xs text-[#52525B] bg-white/5 px-2 py-0.5 rounded-full hover:bg-white/10 transition-colors cursor-pointer whitespace-nowrap"}
      >
        {total > 0 ? `${total} ${declension(total)}` : "\u041D\u0435\u0442 \u0441\u043E\u0431\u044B\u0442\u0438\u0439"}
      </button>
      {open && createPortal(
        <div ref={dropdownRef} style={{position: "fixed", top: getDropdownPos().top, left: getDropdownPos().left, zIndex: 99999, minWidth: "300px", width: "320px"}} className="bg-[#1A1A1A] border border-white/10 rounded-xl shadow-2xl overflow-hidden">
          <div className="p-3 border-b border-white/5">
            <div className="text-xs font-medium text-white">{"\u041E\u043F\u043E\u0432\u0435\u0449\u0435\u043D\u0438\u044F"}</div>
          </div>
          <div className="max-h-80 overflow-y-auto">
            {items.length === 0 ? (
              <div className="p-4 text-center text-xs text-[#52525B]">{"\u041D\u0435\u0442 \u043E\u043F\u043E\u0432\u0435\u0449\u0435\u043D\u0438\u0439"}</div>
            ) : (
              items.map((item) => (
                <button
                  key={item.key}
                  onClick={() => handleItemClick(item)}
                  className="w-full text-left px-4 py-3 hover:bg-white/5 transition-colors border-b border-white/5 last:border-0 flex items-center justify-between gap-3"
                >
                  <span className="text-sm text-[#A1A1AA]">{item.label}</span>
                  <span className="text-[10px] bg-[#EF4444] text-white rounded-full px-1.5 py-0.5 min-w-[20px] text-center font-bold flex-shrink-0">
                    {item.count}
                  </span>
                </button>
              ))
            )}
          </div>
          <div className="p-2 border-t border-white/5">
            <button onClick={handleReadAll} className="w-full text-center py-2 text-xs text-[#7C3AED] hover:bg-[#7C3AED]/10 rounded-lg transition-colors">
              {"\u041F\u0440\u043E\u0447\u0438\u0442\u0430\u0442\u044C \u0432\u0441\u0451"}
            </button>
          </div>
        </div>,
        document.body
      )}
    </>
  );
}

/**
 * Default notification items builder for Trader role.
 */
export function buildTraderNotificationItems(b, prefix) {
  const items = [];
  if (b.trades > 0) items.push({ key: "trades", label: "\u0410\u043A\u0442\u0438\u0432\u043D\u044B\u0435 \u0441\u0434\u0435\u043B\u043A\u0438", path: `${prefix}/sales`, count: b.trades });
  if (b.purchases > 0) items.push({ key: "purchases", label: "\u041F\u043E\u043A\u0443\u043F\u043A\u0438 \u0432 \u043C\u0430\u0440\u043A\u0435\u0442\u0435", path: `${prefix}/my-purchases`, count: b.purchases });
  if (b.guarantor_deals > 0) items.push({ key: "guarantor", label: "\u0413\u0430\u0440\u0430\u043D\u0442-\u0441\u0434\u0435\u043B\u043A\u0438", path: `${prefix}/my-purchases`, count: b.guarantor_deals });
  if (b.shop_messages > 0) items.push({ key: "shop_messages", label: "\u0421\u043E\u043E\u0431\u0449\u0435\u043D\u0438\u044F \u043C\u0430\u0433\u0430\u0437\u0438\u043D\u0430", path: `${prefix}/shop-chats`, count: b.shop_messages });
  if (b.messages > 0) items.push({ key: "messages", label: "\u041B\u0438\u0447\u043D\u044B\u0435 \u0441\u043E\u043E\u0431\u0449\u0435\u043D\u0438\u044F", path: `${prefix}/messages`, count: b.messages });
  if (b.deposits > 0) items.push({ key: "deposits", label: "\u041F\u043E\u043F\u043E\u043B\u043D\u0435\u043D\u0438\u044F", path: `${prefix}/transactions`, count: b.deposits });
  if (b.withdrawals > 0) items.push({ key: "withdrawals", label: "\u0412\u044B\u0432\u043E\u0434 \u0441\u0440\u0435\u0434\u0441\u0442\u0432", path: `${prefix}/withdraw`, count: b.withdrawals });
  if (b.trade_payment > 0) items.push({ key: "trade_payment", label: "\u041E\u043F\u043B\u0430\u0442\u0430 \u0432 \u0441\u0434\u0435\u043B\u043A\u0435", path: `${prefix}/sales`, count: b.trade_payment });
  if (b.trade_message > 0) items.push({ key: "trade_message", label: "\u0421\u043E\u043E\u0431\u0449\u0435\u043D\u0438\u0435 \u0432 \u0441\u0434\u0435\u043B\u043A\u0435", path: `${prefix}/sales`, count: b.trade_message });
  if (b.trade_dispute > 0) items.push({ key: "trade_dispute", label: "\u0421\u043F\u043E\u0440 \u0432 \u0441\u0434\u0435\u043B\u043A\u0435", path: `${prefix}/sales`, count: b.trade_dispute });
  return items;
}

/**
 * Default notification items builder for Merchant role.
 */
export function buildMerchantNotificationItems(b, prefix) {
  const items = [];
  if (b.trades > 0) items.push({ key: "trades", label: "\u0410\u043A\u0442\u0438\u0432\u043D\u044B\u0435 \u0441\u0434\u0435\u043B\u043A\u0438", path: `${prefix}/payments`, count: b.trades });
  if (b.shop_messages > 0) items.push({ key: "shop_messages", label: "\u0421\u043E\u043E\u0431\u0449\u0435\u043D\u0438\u044F \u043C\u0430\u0433\u0430\u0437\u0438\u043D\u0430", path: `${prefix}/shop`, count: b.shop_messages });
  if (b.messages > 0) items.push({ key: "messages", label: "\u0421\u043E\u043E\u0431\u0449\u0435\u043D\u0438\u044F", path: `${prefix}/messages`, count: b.messages });
  if (b.deposits > 0) items.push({ key: "deposits", label: "\u041F\u043E\u043F\u043E\u043B\u043D\u0435\u043D\u0438\u044F", path: `${prefix}/transactions`, count: b.deposits });
  if (b.withdrawals > 0) items.push({ key: "withdrawals", label: "\u0412\u044B\u0432\u043E\u0434 \u0441\u0440\u0435\u0434\u0441\u0442\u0432", path: `${prefix}/withdraw`, count: b.withdrawals });
  if (b.trade_payment > 0) items.push({ key: "trade_payment", label: "\u041E\u043F\u043B\u0430\u0442\u0430 \u0432 \u0441\u0434\u0435\u043B\u043A\u0435", path: `${prefix}/payments`, count: b.trade_payment });
  if (b.trade_message > 0) items.push({ key: "trade_message", label: "\u0421\u043E\u043E\u0431\u0449\u0435\u043D\u0438\u0435 \u0432 \u0441\u0434\u0435\u043B\u043A\u0435", path: `${prefix}/payments`, count: b.trade_message });
  if (b.trade_dispute > 0) items.push({ key: "trade_dispute", label: "\u0421\u043F\u043E\u0440 \u0432 \u0441\u0434\u0435\u043B\u043A\u0435", path: `${prefix}/disputes`, count: b.trade_dispute });
  return items;
}
