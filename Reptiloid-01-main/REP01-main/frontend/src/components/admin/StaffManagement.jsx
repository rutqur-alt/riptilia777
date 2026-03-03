import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { UserCog, PlusCircle, Trash2 } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { Badge, LoadingSpinner, PageHeader } from "@/components/admin/SharedComponents";

export function StaffManagement() {
  const { token } = useAuth();
  const [staff, setStaff] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newStaff, setNewStaff] = useState({ login: "", password: "", role: "support" });

  useEffect(() => { fetchStaff(); }, []);

  const fetchStaff = async () => {
    try {
      const response = await axios.get(`${API}/super-admin/staff`, { headers: { Authorization: `Bearer ${token}` } });
      setStaff(response.data || []);
    } catch (error) {
      toast.error("Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!newStaff.login || !newStaff.password) {
      toast.error("Заполните все поля");
      return;
    }
    try {
      await axios.post(
        `${API}/super-admin/staff/create?login=${newStaff.login}&password=${newStaff.password}&role=${newStaff.role}`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success("Сотрудник создан");
      setShowCreate(false);
      setNewStaff({ login: "", password: "", role: "support" });
      fetchStaff();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка");
    }
  };

  const handleDelete = async (staffId) => {
    if (!confirm("Удалить сотрудника?")) return;
    try {
      await axios.delete(`${API}/super-admin/staff/${staffId}`, { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Удалён");
      fetchStaff();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка");
    }
  };

  const roleColors = {
    owner: "purple",
    admin: "blue",
    mod_p2p: "green",
    mod_market: "yellow",
    support: "gray"
  };

  const roleLabels = {
    owner: "Владелец",
    admin: "Админ",
    mod_p2p: "Мод P2P",
    mod_market: "Мод Маркет",
    support: "Поддержка"
  };

  return (
    <div className="space-y-4" data-testid="staff-management">
      <PageHeader 
        title="Персонал" 
        subtitle="Управление командой"
        action={
          <Button onClick={() => setShowCreate(true)} size="sm" className="bg-[#10B981] hover:bg-[#059669] text-white text-xs h-8">
            <PlusCircle className="w-3.5 h-3.5 mr-1.5" />
            Добавить
          </Button>
        }
      />

      {/* Create Modal */}
      {showCreate && (
        <div className="bg-[#121212] border border-white/10 rounded-xl p-4 space-y-3">
          <h3 className="text-sm font-semibold text-white">Новый сотрудник</h3>
          <div className="grid grid-cols-3 gap-3">
            <Input
              placeholder="Логин"
              value={newStaff.login}
              onChange={(e) => setNewStaff({ ...newStaff, login: e.target.value })}
              className="bg-[#0A0A0A] border-white/10 text-white text-xs h-8"
            />
            <Input
              placeholder="Пароль"
              type="password"
              value={newStaff.password}
              onChange={(e) => setNewStaff({ ...newStaff, password: e.target.value })}
              className="bg-[#0A0A0A] border-white/10 text-white text-xs h-8"
            />
            <select
              value={newStaff.role}
              onChange={(e) => setNewStaff({ ...newStaff, role: e.target.value })}
              className="bg-[#0A0A0A] border border-white/10 text-white text-xs h-8 rounded-lg px-2"
            >
              <option value="support">Поддержка</option>
              <option value="mod_p2p">Модератор P2P</option>
              <option value="mod_market">Модератор Маркет</option>
              <option value="admin">Админ</option>
            </select>
          </div>
          <div className="flex gap-2">
            <Button onClick={handleCreate} size="sm" className="bg-[#10B981] hover:bg-[#059669] text-white text-xs h-7">
              Создать
            </Button>
            <Button onClick={() => setShowCreate(false)} size="sm" variant="ghost" className="text-[#71717A] text-xs h-7">
              Отмена
            </Button>
          </div>
        </div>
      )}

      {loading ? <LoadingSpinner /> : (
        <div className="space-y-2">
          {staff.map(s => (
            <div key={s.id} className="bg-[#121212] border border-white/5 rounded-xl p-3 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[#7C3AED]/20 to-[#7C3AED]/5 flex items-center justify-center">
                  <UserCog className="w-4 h-4 text-[#A78BFA]" />
                </div>
                <div>
                  <div className="text-white text-sm font-medium">{s.login}</div>
                  <div className="text-[#52525B] text-[10px]">{s.actions_count || 0} действий</div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Badge color={roleColors[s.admin_role || "admin"]}>
                  {roleLabels[s.admin_role || "admin"]}
                </Badge>
                {s.admin_role !== "owner" && (
                  <Button 
                    size="sm" 
                    variant="ghost" 
                    onClick={() => handleDelete(s.id)}
                    className="text-[#EF4444] h-7 w-7 p-0"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default StaffManagement;
