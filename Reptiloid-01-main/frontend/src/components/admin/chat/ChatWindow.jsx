// ChatWindow - Main chat area component
import React, { useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  MessageCircle, Send, XCircle, UserCog, LogOut, Trash2,
  CheckCircle, Scale, Briefcase, Store, HelpCircle, Shield, Loader
} from "lucide-react";
import { getRoleInfo, getCategoryIcon, getCategoryColor, getCategoryLabel } from "./chatConstants";
import ChatActions from "./ChatActions";

export function ChatWindow({
  selectedConv,
  setSelectedConv,
  messages,
  newMessage,
  setNewMessage,
  sending,
  onSendMessage,
  onLeaveConversation,
  onDeleteConversation,
  onAddStaff,
  onDecision,
  onOpenTemplates,
  onOpenCommission,
  adminRole,
  token
}) {
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (!selectedConv) {
    return <EmptyState />;
  }

  const iconColor = getCategoryColor(selectedConv.category || selectedConv.type);
  const Icon = getCategoryIcon(selectedConv.category || selectedConv.type);

  return (
    <>
      {/* Header */}
      <ChatHeader
        selectedConv={selectedConv}
        setSelectedConv={setSelectedConv}
        onAddStaff={onAddStaff}
        onLeaveConversation={onLeaveConversation}
        onDeleteConversation={onDeleteConversation}
        iconColor={iconColor}
        Icon={Icon}
      />

      {/* Resolved indicator */}
      {selectedConv.resolved && (
        <div className="p-2 border-b border-white/5 bg-[#10B981]/10">
          <div className="flex items-center gap-2 text-xs text-[#10B981]">
            <CheckCircle className="w-4 h-4" />
            <span>Вопрос решён</span>
            {selectedConv.resolved_at && (
              <span>• {new Date(selectedConv.resolved_at).toLocaleDateString("ru-RU")}</span>
            )}
          </div>
        </div>
      )}

      {/* Assigned moderator indicator */}
      {selectedConv.assigned_to && (
        <div className="p-2 border-b border-white/5 bg-[#8B5CF6]/5">
          <div className="flex items-center gap-2 text-xs text-[#8B5CF6]">
            <UserCog className="w-4 h-4" />
            <span>Взято в работу: {selectedConv.assigned_to_name || "Модератор"}</span>
            {selectedConv.assigned_at && (
              <span className="text-[#71717A]">• {new Date(selectedConv.assigned_at).toLocaleString("ru-RU", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" })}</span>
            )}
          </div>
        </div>
      )}

      {/* Decision Buttons */}
      <ChatActions
        selectedConv={selectedConv}
        adminRole={adminRole}
        onDecision={onDecision}
        onOpenTemplates={onOpenTemplates}
        onOpenCommission={onOpenCommission}
        setNewMessage={setNewMessage}
        token={token}
      />

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full">
            <MessageCircle className="w-10 h-10 text-[#52525B] mb-3" />
            <p className="text-[#71717A] text-sm">Нет сообщений</p>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <MessageBubble key={idx} msg={msg} />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-white/5">
        <div className="flex gap-2">
          <Input
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onKeyPress={(e) => e.key === "Enter" && onSendMessage()}
            placeholder="Написать сообщение..."
            className="flex-1 bg-[#0A0A0A] border-white/10 text-white h-9 rounded-lg"
            data-testid="message-input"
          />
          <Button 
            onClick={onSendMessage} 
            disabled={sending || !newMessage.trim()} 
            className="bg-[#7C3AED] hover:bg-[#6D28D9] h-9 px-4" 
            data-testid="send-btn"
          >
            {sending ? <Loader className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </Button>
        </div>
      </div>

      {/* Role legend */}
      <div className="px-3 py-2 border-t border-white/5 bg-[#0A0A0A]">
        <div className="flex flex-wrap gap-3 text-[10px] text-[#52525B]">
          <span className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-white border border-gray-400" /> Пользователь</span>
          <span className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-[#F97316]" /> Мерчант</span>
          <span className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-[#8B5CF6]" /> Магазин</span>
          <span className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-[#F59E0B]" /> Модератор</span>
          <span className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-[#3B82F6]" /> Поддержка</span>
          <span className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-[#EF4444]" /> Админ</span>
        </div>
      </div>
    </>
  );
}

function ChatHeader({ selectedConv, setSelectedConv, onAddStaff, onLeaveConversation, onDeleteConversation, iconColor, Icon }) {
  return (
    <div className={`p-3 border-b border-white/5 ${selectedConv.status === "disputed" ? "bg-[#EF4444]/5" : selectedConv.status === "closed" ? "bg-[#52525B]/5" : ""}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${iconColor.replace("text-", "bg-")}/20`}>
            <Icon className={`w-5 h-5 ${iconColor}`} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-white font-semibold text-sm">{selectedConv.title}</h3>
              {selectedConv.status === "closed" && (
                <span className="bg-[#52525B] text-white text-[9px] px-1.5 py-0.5 rounded">ЗАКРЫТ</span>
              )}
              {selectedConv.status === "dispute" && selectedConv.type === "crypto_order" && (
                <span className="bg-[#EF4444] text-white text-[9px] px-1.5 py-0.5 rounded animate-pulse">СПОР</span>
              )}
            </div>
            <p className="text-[#71717A] text-xs">{selectedConv.subtitle}</p>
            {selectedConv.type === "crypto_order" && (
              <div className="flex items-center gap-3 mt-1 text-[10px]">
                <span className="text-[#F97316]">Мерчант: @{selectedConv.order?.merchant_nickname || "неизвестен"}</span>
                <span className="text-[#10B981]">Покупатель: @{selectedConv.order?.buyer_nickname || "неизвестен"}</span>
              </div>
            )}
            {selectedConv.type === "marketplace_guarantor" && selectedConv.data && (
              <div className="flex flex-wrap items-center gap-3 mt-1 text-[10px]">
                <span className="text-[#3B82F6]">Покупатель: {selectedConv.data.buyer_nickname || "—"}</span>
                <span className="text-[#F97316]">Продавец: {selectedConv.data.seller_nickname || "—"}</span>
                <span className="text-[#10B981]">Сумма: {selectedConv.data.total_price || 0} USDT</span>
                {selectedConv.data.product_name && <span className="text-[#A1A1AA]">Товар: {selectedConv.data.product_name}</span>}
                {selectedConv.status && <span className={`px-1.5 py-0.5 rounded text-[9px] font-medium ${
                  selectedConv.status === "disputed" ? "bg-[#EF4444]/20 text-[#EF4444]" :
                  selectedConv.status === "completed" ? "bg-[#10B981]/20 text-[#10B981]" :
                  selectedConv.status === "refunded" ? "bg-[#F59E0B]/20 text-[#F59E0B]" :
                  "bg-[#3B82F6]/20 text-[#3B82F6]"
                }`}>{
                  selectedConv.status === "disputed" ? "СПОР" :
                  selectedConv.status === "completed" ? "ЗАВЕРШЕНА" :
                  selectedConv.status === "refunded" ? "ВОЗВРАТ" :
                  selectedConv.status === "pending_confirmation" ? "ОЖИДАЕТ" :
                  selectedConv.status.toUpperCase()
                }</span>}
              </div>
            )}
            {selectedConv.type === "shop_application" && selectedConv.data?.categories && selectedConv.data.categories.length > 0 && (
              <p className="text-[#8B5CF6] text-xs mt-0.5">
                {selectedConv.data.categories.map(c => getCategoryLabel(c)).join(", ")}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1">
          {selectedConv.status !== "closed" && (
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={onAddStaff}
              className="h-7 px-2 text-[#8B5CF6] hover:bg-[#8B5CF6]/10"
              title="Добавить персонал"
            >
              <UserCog className="w-4 h-4 mr-1" />
              <span className="text-xs">+</span>
            </Button>
          )}
          {!selectedConv.resolved && (
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={onLeaveConversation}
              className="h-7 px-2 text-[#52525B] hover:bg-[#52525B]/10 hover:text-white"
              title="Выйти из чата"
            >
              <LogOut className="w-4 h-4" />
            </Button>
          )}
          {(selectedConv.resolved || selectedConv.archived) && (
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => onDeleteConversation(selectedConv.id)}
              className="h-7 px-2 text-[#EF4444] hover:bg-[#EF4444]/10"
              title="Удалить чат"
            >
              <Trash2 className="w-4 h-4" />
            </Button>
          )}
          <Button variant="ghost" size="sm" onClick={() => setSelectedConv(null)} className="h-7 w-7 p-0">
            <XCircle className="w-4 h-4 text-[#71717A]" />
          </Button>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ msg }) {
  const isAdmin = msg.sender_type === "admin" || ["admin", "owner", "mod_p2p", "mod_market", "support"].includes(msg.sender_role);
  const isSystem = msg.is_system || msg.sender_role === "system";
  const roleInfo = getRoleInfo(msg.sender_role);
  
  if (isSystem) {
    return (
      <div className="flex justify-center">
        <div className="bg-[#6B7280]/20 text-[#A1A1AA] text-xs px-3 py-1 rounded-full max-w-[80%] text-center">
          {msg.content}
        </div>
      </div>
    );
  }

  return (
    <div className={`flex ${isAdmin ? "justify-end" : "justify-start"}`}>
      <div className="max-w-[75%]">
        {!isAdmin && (
          <div className="flex items-center gap-1.5 text-[10px] text-[#71717A] mb-0.5 ml-2">
            <div className={`w-2 h-2 rounded-full ${roleInfo.marker}`}></div>
            <span>{msg.sender_nickname ? `${roleInfo.name} (${msg.sender_nickname})` : roleInfo.name}</span>
          </div>
        )}
        {isAdmin && (
          <div className="flex items-center gap-1.5 text-[10px] text-white/60 mb-0.5 mr-2 justify-end">
            <span>{msg.sender_nickname ? `${roleInfo.name} (${msg.sender_nickname})` : roleInfo.name}</span>
            <div className={`w-2 h-2 rounded-full ${roleInfo.marker}`}></div>
          </div>
        )}
        <div className={`p-2.5 rounded-xl ${isAdmin ? roleInfo.color : "bg-white text-black border border-gray-300"}`}>
          <p className="text-xs whitespace-pre-wrap">{msg.content}</p>
          <div className={`text-[10px] mt-1 ${isAdmin ? "text-white/60" : "text-gray-500"}`}>
            {new Date(msg.created_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}
          </div>
        </div>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="text-center max-w-md">
        <div className="w-20 h-20 rounded-2xl bg-[#7C3AED]/10 flex items-center justify-center mx-auto mb-6">
          <MessageCircle className="w-10 h-10 text-[#7C3AED]" />
        </div>
        <h3 className="text-xl font-semibold text-white mb-2">Центр сообщений</h3>
        <p className="text-[#71717A] mb-6">
          Выберите чат из списка слева для просмотра переписки и управления
        </p>
        <div className="grid grid-cols-2 gap-3 text-left">
          <div className="p-3 bg-white/5 rounded-xl">
            <div className="flex items-center gap-2 mb-1">
              <Scale className="w-4 h-4 text-[#EF4444]" />
              <span className="text-white text-sm font-medium">P2P Споры</span>
            </div>
            <p className="text-xs text-[#71717A]">Арбитраж торговых сделок</p>
          </div>
          <div className="p-3 bg-white/5 rounded-xl">
            <div className="flex items-center gap-2 mb-1">
              <Briefcase className="w-4 h-4 text-[#F59E0B]" />
              <span className="text-white text-sm font-medium">Мерчанты</span>
            </div>
            <p className="text-xs text-[#71717A]">Поддержка бизнес-клиентов</p>
          </div>
          <div className="p-3 bg-white/5 rounded-xl">
            <div className="flex items-center gap-2 mb-1">
              <Store className="w-4 h-4 text-[#10B981]" />
              <span className="text-white text-sm font-medium">Магазин</span>
            </div>
            <p className="text-xs text-[#71717A]">Споры по покупкам</p>
          </div>
          <div className="p-3 bg-white/5 rounded-xl">
            <div className="flex items-center gap-2 mb-1">
              <HelpCircle className="w-4 h-4 text-[#3B82F6]" />
              <span className="text-white text-sm font-medium">Тех. поддержка</span>
            </div>
            <p className="text-xs text-[#71717A]">Вопросы пользователей</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ChatWindow;
