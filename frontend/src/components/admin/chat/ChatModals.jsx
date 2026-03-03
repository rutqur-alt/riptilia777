// ChatModals - All modal components for UnifiedMessagesHub
import React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  XCircle, UserCog, PlusCircle, CheckCircle, MessageCircle,
  Edit, Trash2, Loader
} from "lucide-react";

// Commission Modal
export function CommissionModal({
  show,
  onClose,
  commissionType,
  commissionValue,
  setCommissionValue,
  withdrawalCommissionValue,
  setWithdrawalCommissionValue,
  commissionSettings,
  onApprove
}) {
  if (!show) return null;

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4" data-testid="commission-modal">
      <div className="bg-[#121212] border border-white/10 rounded-2xl w-full max-w-sm">
        <div className="p-4 border-b border-white/5 flex items-center justify-between">
          <h3 className="text-white font-semibold">
            {commissionType === "merchant" ? "Комиссии мерчанта" : "Комиссия магазина"}
          </h3>
          <button onClick={onClose} className="text-[#71717A] hover:text-white" title="Закрыть">
            <XCircle className="w-5 h-5" />
          </button>
        </div>
        <div className="p-4 space-y-4">
          {/* Payment Commission */}
          <div>
            <label className="text-[#A1A1AA] text-sm mb-2 block font-medium">
              Комиссия на платежи (%)
            </label>
            <p className="text-[#52525B] text-xs mb-2">
              Вычитается из каждого входящего платежа мерчанта
            </p>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                step="0.1"
                min="0"
                max="100"
                value={commissionValue}
                onChange={(e) => setCommissionValue(e.target.value)}
                placeholder="Например: 3"
                className="flex-1 bg-white/5 border-white/10 text-white text-center text-lg"
                data-testid="commission-input"
              />
              <span className="text-white text-lg font-bold">%</span>
            </div>
          </div>

          {/* Withdrawal Commission - only for merchants */}
          {commissionType === "merchant" && (
            <div>
              <label className="text-[#A1A1AA] text-sm mb-2 block font-medium">
                Комиссия на выплаты (%)
              </label>
              <p className="text-[#52525B] text-xs mb-2">
                Вычитается при продаже USDT через раздел выплат
              </p>
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  step="0.1"
                  min="0"
                  max="100"
                  value={withdrawalCommissionValue || ""}
                  onChange={(e) => setWithdrawalCommissionValue(e.target.value)}
                  placeholder="Например: 3"
                  className="flex-1 bg-white/5 border-white/10 text-white text-center text-lg"
                  data-testid="withdrawal-commission-input"
                />
                <span className="text-white text-lg font-bold">%</span>
              </div>
            </div>
          )}

          <div className="flex gap-2 pt-2">
            <Button 
              variant="ghost" 
              onClick={onClose}
              className="flex-1 text-[#71717A]"
              title="Отменить"
            >
              Отмена
            </Button>
            <Button 
              onClick={onApprove}
              className="flex-1 bg-[#10B981] hover:bg-[#059669] text-white"
              data-testid="confirm-commission-btn"
              title="Одобрить мерчанта с указанными комиссиями"
            >
              Одобрить
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// Staff Selection Modal
export function StaffModal({
  show,
  onClose,
  staffList,
  onAddStaff
}) {
  if (!show) return null;

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
      <div className="bg-[#121212] border border-white/10 rounded-2xl w-full max-w-md">
        <div className="p-4 border-b border-white/5 flex items-center justify-between">
          <h3 className="text-white font-semibold">Добавить персонал в чат</h3>
          <button onClick={onClose} className="text-[#71717A] hover:text-white">
            <XCircle className="w-5 h-5" />
          </button>
        </div>
        <div className="p-4 max-h-[60vh] overflow-y-auto">
          {staffList.length === 0 ? (
            <p className="text-[#71717A] text-sm text-center py-4">Нет доступных сотрудников</p>
          ) : (
            <div className="space-y-2">
              {staffList.map(staff => (
                <button
                  key={staff.id}
                  onClick={() => onAddStaff(staff.id)}
                  className="w-full flex items-center gap-3 p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors"
                >
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    staff.admin_role === "owner" || staff.admin_role === "admin" ? "bg-[#EF4444]/20" :
                    staff.admin_role === "mod_p2p" || staff.admin_role === "mod_market" ? "bg-[#F59E0B]/20" :
                    "bg-[#3B82F6]/20"
                  }`}>
                    <UserCog className={`w-5 h-5 ${
                      staff.admin_role === "owner" || staff.admin_role === "admin" ? "text-[#EF4444]" :
                      staff.admin_role === "mod_p2p" || staff.admin_role === "mod_market" ? "text-[#F59E0B]" :
                      "text-[#3B82F6]"
                    }`} />
                  </div>
                  <div className="flex-1 text-left">
                    <div className="text-white text-sm font-medium">{staff.nickname || staff.login}</div>
                    <div className="text-[#71717A] text-xs">{staff.role_label || staff.admin_role}</div>
                  </div>
                  <PlusCircle className="w-5 h-5 text-[#10B981]" />
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Create User Chat Modal
export function CreateUserChatModal({
  show,
  onClose,
  userSearchQuery,
  setUserSearchQuery,
  userSearchResults,
  userChatTarget,
  setUserChatTarget,
  userChatSubject,
  setUserChatSubject,
  onSearchUsers,
  onCreateChat
}) {
  if (!show) return null;

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
      <div className="bg-[#121212] border border-white/10 rounded-2xl w-full max-w-md">
        <div className="p-4 border-b border-white/5 flex items-center justify-between">
          <h3 className="text-white font-semibold">👤 Новый чат с пользователем</h3>
          <button onClick={onClose} className="text-[#71717A] hover:text-white">
            <XCircle className="w-5 h-5" />
          </button>
        </div>
        <div className="p-4 space-y-4">
          <div>
            <label className="text-[#71717A] text-xs mb-1 block">Поиск пользователя *</label>
            <Input 
              value={userSearchQuery} 
              onChange={e => onSearchUsers(e.target.value)} 
              placeholder="Введите никнейм..." 
              className="bg-white/5 border-white/10" 
            />
            {userSearchResults.length > 0 && (
              <div className="mt-2 bg-white/5 rounded-lg max-h-40 overflow-y-auto">
                {userSearchResults.map(u => (
                  <button 
                    key={u.id} 
                    onClick={() => { 
                      setUserChatTarget(u); 
                      setUserSearchQuery(u.name); 
                    }}
                    className={`w-full p-2 text-left hover:bg-white/10 flex items-center gap-2 ${userChatTarget?.id === u.id ? "bg-[#7C3AED]/20" : ""}`}
                  >
                    <span className={`w-2 h-2 rounded-full ${u.type === "merchant" ? "bg-[#F97316]" : "bg-white"}`}></span>
                    <span className="text-white text-sm">@{u.name}</span>
                    <span className="text-[#52525B] text-xs">{u.type === "merchant" ? "мерчант" : "пользователь"}</span>
                  </button>
                ))}
              </div>
            )}
            {userChatTarget && (
              <div className="mt-2 p-2 bg-[#7C3AED]/10 rounded-lg flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-[#7C3AED]" />
                <span className="text-white text-sm">@{userChatTarget.name}</span>
                <span className="text-[#71717A] text-xs">({userChatTarget.type})</span>
              </div>
            )}
          </div>
          <div>
            <label className="text-[#71717A] text-xs mb-1 block">Тема (опционально)</label>
            <Input 
              value={userChatSubject} 
              onChange={e => setUserChatSubject(e.target.value)} 
              placeholder="Тема сообщения..." 
              className="bg-white/5 border-white/10" 
            />
          </div>
          <Button 
            onClick={onCreateChat} 
            disabled={!userChatTarget} 
            className="w-full bg-[#7C3AED] hover:bg-[#6D28D9] disabled:opacity-50"
          >
            <MessageCircle className="w-4 h-4 mr-2" /> Создать чат
          </Button>
        </div>
      </div>
    </div>
  );
}

// Message Templates Modal
export function TemplatesModal({
  show,
  onClose,
  templates,
  templatesLoading,
  editingTemplate,
  newTemplateTitle,
  setNewTemplateTitle,
  newTemplateContent,
  setNewTemplateContent,
  onCreateTemplate,
  onUpdateTemplate,
  onDeleteTemplate,
  onSelectTemplate,
  onStartEdit,
  onCancelEdit
}) {
  if (!show) return null;

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-[#18181B] rounded-xl p-6 w-[600px] max-h-[80vh] overflow-y-auto border border-white/10" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-white">⚡ Авто-сообщения</h3>
          <button onClick={onClose} className="text-[#71717A] hover:text-white">
            <XCircle className="w-5 h-5" />
          </button>
        </div>
        
        {/* Template form */}
        <div className="bg-white/5 rounded-lg p-4 mb-4">
          <h4 className="text-sm font-medium text-white mb-3">
            {editingTemplate ? "✏️ Редактировать шаблон" : "➕ Новый шаблон"}
          </h4>
          <div className="space-y-3">
            <Input 
              value={newTemplateTitle} 
              onChange={e => setNewTemplateTitle(e.target.value)} 
              placeholder="Название шаблона" 
              className="bg-white/5 border-white/10 text-white"
            />
            <Textarea 
              value={newTemplateContent} 
              onChange={e => setNewTemplateContent(e.target.value)} 
              placeholder="Текст сообщения..." 
              className="bg-white/5 border-white/10 text-white min-h-[100px]"
            />
            <div className="flex gap-2">
              {editingTemplate ? (
                <>
                  <Button onClick={onUpdateTemplate} className="bg-[#7C3AED] hover:bg-[#6D28D9] text-white">
                    <CheckCircle className="w-4 h-4 mr-2" /> Сохранить
                  </Button>
                  <Button onClick={onCancelEdit} variant="outline" className="border-white/20 text-white hover:bg-white/10">
                    Отмена
                  </Button>
                </>
              ) : (
                <Button onClick={onCreateTemplate} className="bg-[#10B981] hover:bg-[#059669] text-white">
                  <PlusCircle className="w-4 h-4 mr-2" /> Добавить
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Templates list */}
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-[#71717A]">Ваши шаблоны</h4>
          {templatesLoading ? (
            <div className="text-center py-4 text-[#71717A]">
              <Loader className="w-5 h-5 animate-spin mx-auto" />
            </div>
          ) : templates.length === 0 ? (
            <div className="text-center py-4 text-[#71717A] text-sm">
              Нет сохранённых шаблонов
            </div>
          ) : (
            templates.map(t => (
              <div key={t.id} className="bg-white/5 rounded-lg p-3 hover:bg-white/10 transition-colors group">
                <div className="flex items-start justify-between">
                  <div className="flex-1 cursor-pointer" onClick={() => onSelectTemplate(t)}>
                    <div className="font-medium text-white text-sm">{t.title}</div>
                    <div className="text-[#71717A] text-xs mt-1 line-clamp-2">{t.content}</div>
                  </div>
                  <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity ml-2">
                    <button 
                      onClick={() => onStartEdit(t)} 
                      className="p-1.5 text-[#3B82F6] hover:bg-[#3B82F6]/20 rounded"
                      title="Редактировать"
                    >
                      <Edit className="w-4 h-4" />
                    </button>
                    <button 
                      onClick={() => onDeleteTemplate(t.id)} 
                      className="p-1.5 text-[#EF4444] hover:bg-[#EF4444]/20 rounded"
                      title="Удалить"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
        
        <div className="mt-4 text-xs text-[#71717A] text-center">
          Нажмите на шаблон, чтобы вставить текст в поле сообщения
        </div>
      </div>
    </div>
  );
}

export default {
  CommissionModal,
  StaffModal,
  CreateUserChatModal,
  TemplatesModal
};
