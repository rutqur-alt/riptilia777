import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { toast } from "sonner";
import { API } from "@/App";
import { useAuth } from "@/App";
import axios from "axios";
import { 
  CreditCard, Phone, QrCode, Smartphone, Plus, Trash2, Star, 
  Edit2, Check, X, Building2
} from "lucide-react";

const REQUISITE_TYPES = [
  { 
    id: "card", 
    name: "Банковская карта", 
    icon: CreditCard, 
    color: "#7C3AED",
    emoji: "💳",
    description: "Номер карты, банк и имя держателя"
  },
  { 
    id: "sbp", 
    name: "СБП по номеру", 
    icon: Phone, 
    color: "#10B981",
    emoji: "⚡",
    description: "Номер телефона для СБП перевода"
  },
  { 
    id: "qr", 
    name: "СБП QR-код", 
    icon: QrCode, 
    color: "#3B82F6",
    emoji: "📱",
    description: "QR-код для сканирования"
  },
  { 
    id: "sim", 
    name: "SIM (баланс)", 
    icon: Smartphone, 
    color: "#F59E0B",
    emoji: "📞",
    description: "Пополнение баланса телефона"
  },
  { 
    id: "cis", 
    name: "Перевод СНГ", 
    icon: Building2, 
    color: "#EC4899",
    emoji: "🌍",
    description: "Банковский перевод в страны СНГ"
  }
];

const BANKS = [
  "Сбербанк", "Тинькофф", "Альфа-Банк", "ВТБ", "Райффайзен", 
  "Газпромбанк", "Открытие", "МКБ", "Совкомбанк", "Промсвязьбанк"
];

const OPERATORS = ["МТС", "Мегафон", "Билайн", "Теле2", "Yota"];

const CIS_COUNTRIES = [
  { code: "KZ", name: "Казахстан", banks: ["Kaspi Bank", "Halyk Bank", "Сбербанк Казахстан", "Forte Bank", "Jusan Bank"] },
  { code: "BY", name: "Беларусь", banks: ["Беларусбанк", "Приорбанк", "БПС-Сбербанк", "Альфа-Банк Беларусь", "БелВЭБ"] },
  { code: "UZ", name: "Узбекистан", banks: ["Uzcard", "Humo", "NBU", "Kapitalbank", "Ipak Yoli Bank"] },
  { code: "AM", name: "Армения", banks: ["Ameriabank", "Ardshinbank", "ACBA Bank", "VTB Armenia", "Converse Bank"] },
  { code: "KG", name: "Кыргызстан", banks: ["KICB", "Optima Bank", "Бакай Банк", "RSK Bank", "Демир Банк"] },
  { code: "TJ", name: "Таджикистан", banks: ["Амонатбанк", "Ориёнбанк", "Эсхата", "Спитамен Банк", "Тоджиксодиротбонк"] },
  { code: "AZ", name: "Азербайджан", banks: ["Kapital Bank", "PASHA Bank", "ABB", "Unibank", "Bank Respublika"] }
];

export default function RequisitesPage() {
  const { token } = useAuth();
  const [requisites, setRequisites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [selectedType, setSelectedType] = useState(null);
  const [editingRequisite, setEditingRequisite] = useState(null);
  const [formData, setFormData] = useState({});

  useEffect(() => {
    fetchRequisites();
  }, []);

  const fetchRequisites = async () => {
    try {
      const response = await axios.get(`${API}/requisites`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setRequisites(response.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const getRequisitesByType = (type) => {
    return requisites.filter(r => r.type === type);
  };

  const handleCreate = async () => {
    if (!selectedType) return;
    
    try {
      await axios.post(`${API}/requisites`, {
        type: selectedType,
        data: formData
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Реквизит добавлен");
      setCreateDialogOpen(false);
      setSelectedType(null);
      setFormData({});
      fetchRequisites();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка добавления");
    }
  };

  const handleUpdate = async (requisiteId) => {
    try {
      await axios.put(`${API}/requisites/${requisiteId}`, {
        type: editingRequisite.type,
        data: formData
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Реквизит обновлён");
      setEditingRequisite(null);
      setFormData({});
      fetchRequisites();
    } catch (error) {
      toast.error("Ошибка обновления");
    }
  };

  const handleDelete = async (requisiteId) => {
    if (!confirm("Удалить реквизит?")) return;
    
    try {
      await axios.delete(`${API}/requisites/${requisiteId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Реквизит удалён");
      fetchRequisites();
    } catch (error) {
      toast.error("Ошибка удаления");
    }
  };

  const handleSetPrimary = async (requisiteId) => {
    try {
      await axios.post(`${API}/requisites/${requisiteId}/set-primary`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Основной реквизит обновлён");
      fetchRequisites();
    } catch (error) {
      toast.error("Ошибка");
    }
  };

  const startEdit = (requisite) => {
    setEditingRequisite(requisite);
    setFormData(requisite.data);
  };

  const renderForm = (type) => {
    switch (type) {
      case "card":
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="text-[#A1A1AA]">Банк</Label>
              <select
                value={formData.bank_name || ""}
                onChange={(e) => setFormData({ ...formData, bank_name: e.target.value })}
                className="w-full bg-[#1A1A1A] border border-white/10 text-white h-12 rounded-xl px-3"
              >
                <option value="">Выберите банк</option>
                {BANKS.map(bank => (
                  <option key={bank} value={bank}>{bank}</option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label className="text-[#A1A1AA]">Номер карты</Label>
              <Input
                placeholder="0000 0000 0000 0000"
                value={formData.card_number || ""}
                onChange={(e) => setFormData({ ...formData, card_number: e.target.value })}
                className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl font-['JetBrains_Mono']"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-[#A1A1AA]">Имя держателя</Label>
              <Input
                placeholder="IVAN PETROV"
                value={formData.card_holder || ""}
                onChange={(e) => setFormData({ ...formData, card_holder: e.target.value.toUpperCase() })}
                className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl"
              />
            </div>
          </div>
        );
      
      case "sbp":
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="text-[#A1A1AA]">Номер телефона</Label>
              <Input
                placeholder="+7 900 000 00 00"
                value={formData.phone || ""}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl font-['JetBrains_Mono']"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-[#A1A1AA]">Имя получателя</Label>
              <Input
                placeholder="Иван И."
                value={formData.recipient_name || ""}
                onChange={(e) => setFormData({ ...formData, recipient_name: e.target.value })}
                className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-[#A1A1AA]">Банк получателя</Label>
              <select
                value={formData.bank_name || ""}
                onChange={(e) => setFormData({ ...formData, bank_name: e.target.value })}
                className="w-full bg-[#1A1A1A] border border-white/10 text-white h-12 rounded-xl px-3"
              >
                <option value="">Выберите банк</option>
                {BANKS.map(bank => (
                  <option key={bank} value={bank}>{bank}</option>
                ))}
              </select>
            </div>
          </div>
        );
      
      case "qr":
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="text-[#A1A1AA]">Банк</Label>
              <select
                value={formData.bank_name || ""}
                onChange={(e) => setFormData({ ...formData, bank_name: e.target.value })}
                className="w-full bg-[#1A1A1A] border border-white/10 text-white h-12 rounded-xl px-3"
              >
                <option value="">Выберите банк</option>
                {BANKS.map(bank => (
                  <option key={bank} value={bank}>{bank}</option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label className="text-[#A1A1AA]">QR-код (вставьте данные или ссылку)</Label>
              <textarea
                placeholder="https://qr.nspk.ru/... или base64 данные"
                value={formData.qr_data || ""}
                onChange={(e) => setFormData({ ...formData, qr_data: e.target.value })}
                className="w-full bg-[#1A1A1A] border border-white/10 text-white rounded-xl p-3 min-h-[100px] resize-none font-['JetBrains_Mono'] text-sm"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-[#A1A1AA]">Описание (необязательно)</Label>
              <Input
                placeholder="Сканируйте QR в приложении банка"
                value={formData.description || ""}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl"
              />
            </div>
          </div>
        );
      
      case "sim":
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="text-[#A1A1AA]">Оператор</Label>
              <select
                value={formData.operator || ""}
                onChange={(e) => setFormData({ ...formData, operator: e.target.value })}
                className="w-full bg-[#1A1A1A] border border-white/10 text-white h-12 rounded-xl px-3"
              >
                <option value="">Выберите оператора</option>
                {OPERATORS.map(op => (
                  <option key={op} value={op}>{op}</option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label className="text-[#A1A1AA]">Номер телефона</Label>
              <Input
                placeholder="+7 900 000 00 00"
                value={formData.phone || ""}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl font-['JetBrains_Mono']"
              />
            </div>
          </div>
        );
      
      case "cis":
        const selectedCountry = CIS_COUNTRIES.find(c => c.name === formData.country);
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="text-[#A1A1AA]">Страна</Label>
              <select
                value={formData.country || ""}
                onChange={(e) => setFormData({ ...formData, country: e.target.value, bank_name: "" })}
                className="w-full bg-[#1A1A1A] border border-white/10 text-white h-12 rounded-xl px-3"
              >
                <option value="">Выберите страну</option>
                {CIS_COUNTRIES.map(country => (
                  <option key={country.code} value={country.name}>{country.name}</option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label className="text-[#A1A1AA]">Банк</Label>
              <select
                value={formData.bank_name || ""}
                onChange={(e) => setFormData({ ...formData, bank_name: e.target.value })}
                className="w-full bg-[#1A1A1A] border border-white/10 text-white h-12 rounded-xl px-3"
                disabled={!selectedCountry}
              >
                <option value="">Выберите банк</option>
                {selectedCountry?.banks.map(bank => (
                  <option key={bank} value={bank}>{bank}</option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label className="text-[#A1A1AA]">Номер счёта / IBAN</Label>
              <Input
                placeholder="KZ00BANK0000000000"
                value={formData.account_number || ""}
                onChange={(e) => setFormData({ ...formData, account_number: e.target.value })}
                className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl font-['JetBrains_Mono']"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-[#A1A1AA]">ФИО получателя</Label>
              <Input
                placeholder="Иван Иванов"
                value={formData.recipient_name || ""}
                onChange={(e) => setFormData({ ...formData, recipient_name: e.target.value })}
                className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-[#A1A1AA]">SWIFT/BIC (необязательно)</Label>
              <Input
                placeholder="HABORUA"
                value={formData.swift_bic || ""}
                onChange={(e) => setFormData({ ...formData, swift_bic: e.target.value })}
                className="bg-[#1A1A1A] border-white/10 text-white h-12 rounded-xl font-['JetBrains_Mono']"
              />
            </div>
          </div>
        );
      
      default:
        return null;
    }
  };

  const renderRequisiteCard = (requisite) => {
    const typeConfig = REQUISITE_TYPES.find(t => t.id === requisite.type);
    const Icon = typeConfig?.icon || CreditCard;
    const isEditing = editingRequisite?.id === requisite.id;
    
    return (
      <div 
        key={requisite.id}
        className={`bg-[#121212] border rounded-xl p-4 ${
          requisite.is_primary ? "border-[#10B981]" : "border-white/5"
        }`}
      >
        {isEditing ? (
          <div className="space-y-4">
            {renderForm(requisite.type)}
            <div className="flex gap-2 pt-2">
              <Button 
                onClick={() => handleUpdate(requisite.id)}
                className="bg-[#10B981] hover:bg-[#059669] rounded-xl flex-1"
              >
                <Check className="w-4 h-4 mr-2" />
                Сохранить
              </Button>
              <Button 
                variant="outline"
                onClick={() => { setEditingRequisite(null); setFormData({}); }}
                className="border-white/10 rounded-xl"
              >
                <X className="w-4 h-4" />
              </Button>
            </div>
          </div>
        ) : (
          <>
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-3">
                <div 
                  className="w-10 h-10 rounded-xl flex items-center justify-center"
                  style={{ backgroundColor: `${typeConfig?.color}20` }}
                >
                  <Icon className="w-5 h-5" style={{ color: typeConfig?.color }} />
                </div>
                <div>
                  <div className="text-white font-medium flex items-center gap-2">
                    {typeConfig?.emoji} {typeConfig?.name}
                    {requisite.is_primary && (
                      <span className="text-xs bg-[#10B981]/20 text-[#10B981] px-2 py-0.5 rounded-full">
                        Основной
                      </span>
                    )}
                  </div>
                  {requisite.data.bank_name && (
                    <div className="text-sm text-[#71717A]">{requisite.data.bank_name}</div>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-1">
                {!requisite.is_primary && (
                  <button
                    onClick={() => handleSetPrimary(requisite.id)}
                    className="p-2 rounded-lg hover:bg-white/5 transition-colors"
                    title="Сделать основным"
                  >
                    <Star className="w-4 h-4 text-[#52525B] hover:text-[#F59E0B]" />
                  </button>
                )}
                <button
                  onClick={() => startEdit(requisite)}
                  className="p-2 rounded-lg hover:bg-white/5 transition-colors"
                >
                  <Edit2 className="w-4 h-4 text-[#52525B]" />
                </button>
                <button
                  onClick={() => handleDelete(requisite.id)}
                  className="p-2 rounded-lg hover:bg-white/5 transition-colors"
                >
                  <Trash2 className="w-4 h-4 text-[#52525B] hover:text-[#EF4444]" />
                </button>
              </div>
            </div>
            
            <div className="bg-[#0A0A0A] rounded-lg p-3 space-y-1">
              {requisite.type === "card" && (
                <>
                  <div className="flex justify-between">
                    <span className="text-[#52525B] text-sm">Карта</span>
                    <span className="text-white font-['JetBrains_Mono']">{requisite.data.card_number}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#52525B] text-sm">Держатель</span>
                    <span className="text-[#A1A1AA]">{requisite.data.card_holder}</span>
                  </div>
                </>
              )}
              {requisite.type === "sbp" && (
                <>
                  <div className="flex justify-between">
                    <span className="text-[#52525B] text-sm">Телефон</span>
                    <span className="text-white font-['JetBrains_Mono']">{requisite.data.phone}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#52525B] text-sm">Получатель</span>
                    <span className="text-[#A1A1AA]">{requisite.data.recipient_name}</span>
                  </div>
                </>
              )}
              {requisite.type === "qr" && (
                <>
                  <div className="text-[#52525B] text-sm">QR-код настроен</div>
                  {requisite.data.description && (
                    <div className="text-[#A1A1AA] text-sm">{requisite.data.description}</div>
                  )}
                </>
              )}
              {requisite.type === "sim" && (
                <>
                  <div className="flex justify-between">
                    <span className="text-[#52525B] text-sm">Оператор</span>
                    <span className="text-[#A1A1AA]">{requisite.data.operator}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#52525B] text-sm">Номер</span>
                    <span className="text-white font-['JetBrains_Mono']">{requisite.data.phone}</span>
                  </div>
                </>
              )}
              {requisite.type === "cis" && (
                <>
                  <div className="flex justify-between">
                    <span className="text-[#52525B] text-sm">Страна</span>
                    <span className="text-[#A1A1AA]">{requisite.data.country}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#52525B] text-sm">Счёт</span>
                    <span className="text-white font-['JetBrains_Mono'] text-xs">{requisite.data.account_number}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#52525B] text-sm">Получатель</span>
                    <span className="text-[#A1A1AA]">{requisite.data.recipient_name}</span>
                  </div>
                </>
              )}
            </div>
          </>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white font-['Unbounded']">Мои реквизиты</h1>
          <p className="text-[#71717A] mt-1">Добавьте реквизиты для приёма платежей (до 5 каждого типа)</p>
        </div>
      </div>

      {/* Type sections */}
      {REQUISITE_TYPES.map((type) => {
        const typeRequisites = getRequisitesByType(type.id);
        const canAdd = typeRequisites.length < 5;
        
        return (
          <div key={type.id} className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div 
                  className="w-10 h-10 rounded-xl flex items-center justify-center"
                  style={{ backgroundColor: `${type.color}20` }}
                >
                  <type.icon className="w-5 h-5" style={{ color: type.color }} />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                    {type.emoji} {type.name}
                    <span className="text-sm font-normal text-[#52525B]">
                      ({typeRequisites.length}/5)
                    </span>
                  </h2>
                  <p className="text-sm text-[#52525B]">{type.description}</p>
                </div>
              </div>
              
              {canAdd && (
                <Dialog open={createDialogOpen && selectedType === type.id} onOpenChange={(open) => {
                  setCreateDialogOpen(open);
                  if (!open) {
                    setSelectedType(null);
                    setFormData({});
                  }
                }}>
                  <DialogTrigger asChild>
                    <Button 
                      onClick={() => setSelectedType(type.id)}
                      variant="outline" 
                      className="border-white/10 hover:bg-white/5 rounded-xl"
                    >
                      <Plus className="w-4 h-4 mr-2" />
                      Добавить
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="bg-[#121212] border-white/10 text-white max-w-md">
                    <DialogHeader>
                      <DialogTitle className="flex items-center gap-2">
                        {type.emoji} Добавить {type.name.toLowerCase()}
                      </DialogTitle>
                    </DialogHeader>
                    <div className="py-4">
                      {renderForm(type.id)}
                    </div>
                    <div className="flex gap-3">
                      <Button 
                        onClick={handleCreate}
                        className="flex-1 bg-[#7C3AED] hover:bg-[#6D28D9] rounded-xl"
                      >
                        Добавить
                      </Button>
                      <Button 
                        variant="outline"
                        onClick={() => { setCreateDialogOpen(false); setSelectedType(null); setFormData({}); }}
                        className="border-white/10 rounded-xl"
                      >
                        Отмена
                      </Button>
                    </div>
                  </DialogContent>
                </Dialog>
              )}
            </div>
            
            {typeRequisites.length === 0 ? (
              <div className="bg-[#121212] border border-white/5 border-dashed rounded-xl p-8 text-center">
                <type.icon className="w-12 h-12 text-[#52525B] mx-auto mb-3" />
                <p className="text-[#71717A]">Нет добавленных реквизитов</p>
                <p className="text-sm text-[#52525B]">Нажмите &quot;Добавить&quot; чтобы создать</p>
              </div>
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {typeRequisites.map(renderRequisiteCard)}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
