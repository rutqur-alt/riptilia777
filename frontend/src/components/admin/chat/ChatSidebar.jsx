// ChatSidebar - Conversations list component
import React from "react";
import { Button } from "@/components/ui/button";
import {
  MessageCircle, Search, XCircle, RefreshCw, History, Trash2, PlusCircle
} from "lucide-react";
import { LoadingSpinner } from "@/components/admin/SharedComponents";
import { getCategoryIcon, getCategoryColor } from "./chatConstants";

export function ChatSidebar({
  loading,
  conversations,
  filteredConvs,
  selectedConv,
  setSelectedConv,
  searchQuery,
  setSearchQuery,
  searchResults,
  isSearching,
  handleSearch,
  clearSearch,
  showArchive,
  archivedConvs,
  onRefresh,
  onDeleteConversation
}) {
  const displayList = isSearching && searchQuery 
    ? searchResults 
    : showArchive 
      ? archivedConvs 
      : filteredConvs;

  return (
    <div className="bg-[#121212] border border-white/5 rounded-xl overflow-hidden flex flex-col">
      <div className="p-3 border-b border-white/5">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-white font-semibold text-sm">
            {isSearching && searchQuery 
              ? `Поиск (${searchResults.length})` 
              : showArchive 
                ? `Архив (${archivedConvs.length})` 
                : `Чаты (${filteredConvs.length})`}
          </h3>
          <Button variant="ghost" size="sm" onClick={onRefresh} className="h-7 w-7 p-0">
            <RefreshCw className="w-4 h-4 text-[#71717A]" />
          </Button>
        </div>
        {/* Search Input */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-[#52525B]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder="Поиск по никнейму, магазину..."
            className="w-full bg-white/5 border border-white/10 rounded-lg pl-9 pr-3 py-1.5 text-sm text-white placeholder-[#52525B] focus:outline-none focus:border-[#7C3AED]"
            data-testid="chat-search-input"
          />
          {searchQuery && (
            <button onClick={clearSearch} className="absolute right-2 top-1/2 transform -translate-y-1/2 text-[#52525B] hover:text-white">
              <XCircle className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        {loading ? <LoadingSpinner /> : displayList.length === 0 ? (
          <div className="p-6 text-center">
            {isSearching && searchQuery ? (
              <>
                <Search className="w-10 h-10 text-[#52525B] mx-auto mb-3" />
                <p className="text-[#71717A] text-sm">Ничего не найдено</p>
              </>
            ) : showArchive ? (
              <>
                <History className="w-10 h-10 text-[#52525B] mx-auto mb-3" />
                <p className="text-[#71717A] text-sm">Архив пуст</p>
              </>
            ) : (
              <>
                <MessageCircle className="w-10 h-10 text-[#52525B] mx-auto mb-3" />
                <p className="text-[#71717A] text-sm">Нет чатов</p>
              </>
            )}
          </div>
        ) : (
          displayList.map(conv => (
            <ConversationItem
              key={conv.id}
              conv={conv}
              isSelected={selectedConv?.id === conv.id}
              onClick={() => setSelectedConv(conv)}
              showArchive={showArchive}
              onDelete={onDeleteConversation}
            />
          ))
        )}
      </div>
    </div>
  );
}

function ConversationItem({ conv, isSelected, onClick, showArchive, onDelete }) {
  const iconColor = getCategoryColor(conv.category || conv.type);
  const isResolved = conv.resolved || conv.archived;
  const isLeftByMe = conv.is_left_by_me;
  const isCryptoDispute = conv.type === "crypto_order" && conv.status === "dispute";
  
  // Get icon component and render it properly
  const IconComponent = getCategoryIcon(conv.category || conv.type);

  return (
    <div
      onClick={onClick}
      className={`p-3 border-b border-white/5 cursor-pointer transition-colors ${
        isSelected ? "bg-[#7C3AED]/10 border-l-2 border-l-[#7C3AED]" : 
        isCryptoDispute ? "bg-[#EF4444]/10 border-l-2 border-l-[#EF4444] hover:bg-[#EF4444]/20" :
        "hover:bg-white/5"
      } ${isResolved || isLeftByMe ? "opacity-70" : ""}`}
      data-testid={`conv-${conv.id}`}
    >
      <div className="flex items-start gap-2">
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
          isCryptoDispute ? "bg-[#EF4444]/20" : `${iconColor.replace("text-", "bg-")}/20`
        }`}>
          <IconComponent className={`w-4 h-4 ${isCryptoDispute ? "text-[#EF4444]" : iconColor}`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`text-sm font-medium truncate ${isCryptoDispute ? "text-[#EF4444]" : "text-white"}`}>
              {conv.title}
            </span>
            {conv.is_qr_aggregator_dispute && (
              <span className="bg-[#F97316] text-white text-[9px] px-1.5 py-0.5 rounded">QR</span>
            )}
            {(conv.status === "disputed" || conv.status === "dispute") && (
              <span className="bg-[#EF4444] text-white text-[9px] px-1.5 py-0.5 rounded animate-pulse">СПОР</span>
            )}
            {isResolved && (
              <span className="bg-[#10B981] text-white text-[9px] px-1.5 py-0.5 rounded">РЕШЁН</span>
            )}
            {isLeftByMe && !isResolved && (
              <span className="bg-[#52525B] text-white text-[9px] px-1.5 py-0.5 rounded">ВЫШЛИ</span>
            )}
          </div>
          <p className={`text-xs truncate ${isCryptoDispute ? "text-[#EF4444]/70" : "text-[#71717A]"}`}>
            {conv.is_qr_aggregator_dispute ? "Спор QR-агрегатора" : conv.subtitle}
          </p>
          {showArchive && conv.category_label && (
            <p className="text-[#F59E0B]/70 text-[10px] mt-0.5">{conv.category_label}</p>
          )}
          {conv.resolved_at && (
            <p className="text-[#10B981]/70 text-[10px] mt-0.5">
              Решён: {new Date(conv.resolved_at).toLocaleDateString("ru-RU")}
            </p>
          )}
        </div>
        <div className="flex flex-col items-end gap-1">
          {conv.unread_count > 0 && (
            <span className="bg-[#EF4444] text-white text-[10px] px-1.5 py-0.5 rounded-full">
              {conv.unread_count}
            </span>
          )}
          {showArchive && (isResolved || isLeftByMe) && (
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(conv.id); }}
              className="text-[#EF4444]/60 hover:text-[#EF4444] p-1"
              title="Удалить чат"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default ChatSidebar;
