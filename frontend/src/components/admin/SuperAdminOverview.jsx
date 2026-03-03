import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { 
  Users, DollarSign, Activity, AlertTriangle, Store, 
  ArrowDownRight, AlertCircle, Percent, History, Scale,
  Briefcase, Power, PowerOff
} from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { StatCard, Badge, LoadingSpinner } from "@/components/admin/SharedComponents";

export default function SuperAdminOverview() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [maintenance, setMaintenance] = useState(false);

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    try {
      const [overview, maintenanceRes] = await Promise.all([
        axios.get(`${API}/super-admin/overview`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/super-admin/maintenance`, { headers: { Authorization: `Bearer ${token}` } })
      ]);
      setData(overview.data);
      setMaintenance(maintenanceRes.data?.enabled || false);
    } catch (error) {
      console.error(error);
      toast.error("Ошибка загрузки данных");
    } finally {
      setLoading(false);
    }
  };

  const toggleMaintenance = async () => {
    try {
      await axios.post(`${API}/super-admin/maintenance`, 
        { enabled: !maintenance, message: "Ведутся технические работы" },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setMaintenance(!maintenance);
      toast.success(maintenance ? "Сайт включён" : "Режим обслуживания активирован");
    } catch (error) {
      toast.error("Ошибка");
    }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-4" data-testid="admin-overview">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Панель управления</h1>
          <p className="text-[#71717A] text-xs">Обзор платформы в реальном времени</p>
        </div>
        <Button
          onClick={toggleMaintenance}
          size="sm"
          className={`${maintenance ? 'bg-[#EF4444] hover:bg-[#DC2626]' : 'bg-[#52525B] hover:bg-[#71717A]'} text-white text-xs h-8`}
        >
          {maintenance ? <PowerOff className="w-3.5 h-3.5 mr-1.5" /> : <Power className="w-3.5 h-3.5 mr-1.5" />}
          {maintenance ? 'Выключить Maintenance' : 'Maintenance Mode'}
        </Button>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <StatCard 
          title="Пользователи" 
          value={data?.users?.total_traders || 0} 
          sub={`+${data?.users?.today_registrations || 0} сегодня`}
          icon={Users} 
          color="blue"
          onClick={() => navigate('/admin/users')}
        />
        <StatCard 
          title="Мерчанты" 
          value={data?.users?.total_merchants || 0} 
          icon={Briefcase} 
          color="purple"
          onClick={() => navigate('/admin/merchants')}
        />
        <StatCard 
          title="Активных сделок" 
          value={data?.trades?.active || 0} 
          sub={`${data?.trades?.today || 0} сегодня`}
          icon={Activity} 
          color="green"
          onClick={() => navigate('/admin/p2p/trades')}
        />
        <StatCard 
          title="Споры" 
          value={data?.trades?.disputed || 0} 
          icon={AlertTriangle} 
          color="red"
          onClick={() => navigate('/admin/p2p/disputes')}
        />
        <StatCard 
          title="Магазины" 
          value={data?.marketplace?.shops || 0} 
          icon={Store} 
          color="yellow"
          onClick={() => navigate('/admin/market/shops')}
        />
        <StatCard 
          title="Ожидают вывода" 
          value={data?.marketplace?.pending_withdrawals || 0} 
          icon={ArrowDownRight} 
          color="red"
          onClick={() => navigate('/admin/market/withdrawals')}
        />
      </div>

      {/* Financial Overview */}
      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-[#121212] border border-white/5 rounded-xl p-4">
          <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
            <DollarSign className="w-4 h-4 text-[#10B981]" />
            Финансовая сводка
          </h3>
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-[#0A0A0A] rounded-lg p-3">
              <div className="text-[#71717A] text-xs">Оборот P2P</div>
              <div className="text-white font-bold text-lg">{data?.volumes?.total_usdt?.toLocaleString() || 0} USDT</div>
              <div className="text-[#52525B] text-[10px]">≈ {data?.volumes?.total_rub?.toLocaleString() || 0} ₽</div>
            </div>
            <div className="bg-[#0A0A0A] rounded-lg p-3">
              <div className="text-[#71717A] text-xs">Комиссия заработана</div>
              <div className="text-[#10B981] font-bold text-lg">{data?.volumes?.total_commission?.toLocaleString() || 0} ₽</div>
            </div>
            <div className="bg-[#0A0A0A] rounded-lg p-3">
              <div className="text-[#71717A] text-xs">Всего сделок</div>
              <div className="text-white font-bold text-lg">{data?.trades?.completed || 0}</div>
              <div className="text-[#52525B] text-[10px]">завершено</div>
            </div>
          </div>
        </div>

        <div className="bg-[#121212] border border-white/5 rounded-xl p-4">
          <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-[#F59E0B]" />
            Требует внимания
          </h3>
          <div className="space-y-2">
            {data?.trades?.disputed > 0 && (
              <Link to="/admin/p2p/disputes" title="Просмотр и разрешение споров P2P" className="flex items-center justify-between p-2 bg-[#EF4444]/10 rounded-lg hover:bg-[#EF4444]/20 transition-colors">
                <span className="text-[#EF4444] text-xs">Споры P2P</span>
                <Badge color="red">{data.trades.disputed}</Badge>
              </Link>
            )}
            {data?.marketplace?.pending_withdrawals > 0 && (
              <Link to="/admin/market/withdrawals" className="flex items-center justify-between p-2 bg-[#F59E0B]/10 rounded-lg hover:bg-[#F59E0B]/20 transition-colors">
                <span className="text-[#F59E0B] text-xs">Заявки на вывод</span>
                <Badge color="yellow">{data.marketplace.pending_withdrawals}</Badge>
              </Link>
            )}
            {data?.users?.blocked_traders > 0 && (
              <div className="flex items-center justify-between p-2 bg-white/5 rounded-lg">
                <span className="text-[#A1A1AA] text-xs">Заблокировано</span>
                <Badge color="gray">{data.users.blocked_traders}</Badge>
              </div>
            )}
            {!data?.trades?.disputed && !data?.marketplace?.pending_withdrawals && (
              <div className="text-[#52525B] text-xs text-center py-4">Всё в порядке ✓</div>
            )}
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-[#121212] border border-white/5 rounded-xl p-4">
        <h3 className="text-sm font-semibold text-white mb-3">Быстрые действия</h3>
        <div className="flex flex-wrap gap-2">
          <Link to="/admin/users" title="Управление пользователями платформы" title="Управление пользователями платформы" className="px-3 py-1.5 bg-white/5 hover:bg-white/10 rounded-lg text-xs text-[#A1A1AA] hover:text-white transition-colors flex items-center gap-1.5">
            <Users className="w-3.5 h-3.5" /> Пользователи
          </Link>
          <Link to="/admin/p2p/disputes" title="Просмотр и разрешение споров P2P" title="Просмотр и разрешение споров P2P" className="px-3 py-1.5 bg-white/5 hover:bg-white/10 rounded-lg text-xs text-[#A1A1AA] hover:text-white transition-colors flex items-center gap-1.5">
            <Scale className="w-3.5 h-3.5" /> Споры
          </Link>
          <Link to="/admin/market/withdrawals" title="Заявки на вывод средств" className="px-3 py-1.5 bg-white/5 hover:bg-white/10 rounded-lg text-xs text-[#A1A1AA] hover:text-white transition-colors flex items-center gap-1.5">
            <ArrowDownRight className="w-3.5 h-3.5" /> Выводы
          </Link>
          <Link to="/admin/settings/commissions" title="Настройка комиссий платформы" className="px-3 py-1.5 bg-white/5 hover:bg-white/10 rounded-lg text-xs text-[#A1A1AA] hover:text-white transition-colors flex items-center gap-1.5">
            <Percent className="w-3.5 h-3.5" /> Комиссии
          </Link>
          <Link to="/admin/logs" title="Журнал действий на платформе" className="px-3 py-1.5 bg-white/5 hover:bg-white/10 rounded-lg text-xs text-[#A1A1AA] hover:text-white transition-colors flex items-center gap-1.5">
            <History className="w-3.5 h-3.5" /> Логи
          </Link>
        </div>
      </div>
    </div>
  );
}
