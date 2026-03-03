/**
 * StaffMonitoring - Real-time staff activity monitoring
 */
import { useState, useEffect } from "react";
import { API, useAuth } from "@/App";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { RefreshCw, Users, Activity, Eye, UserCog } from "lucide-react";
import { PageHeader, LoadingSpinner, EmptyState } from "@/components/admin/SharedComponents";

export default function StaffMonitoring() {
  const { token } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      const res = await axios.get(`${API}/admin/activity-monitor`, { headers: { Authorization: `Bearer ${token}` } });
      setData(res.data);
    } catch (error) {
      console.error("Error fetching monitoring data:", error);
    } finally {
      setLoading(false);
    }
  };

  const roleLabels = {
    owner: { label: "👑 Владелец", color: "text-[#7C3AED]", bg: "bg-[#7C3AED]/20" },
    admin: { label: "🔴 Админ", color: "text-[#EF4444]", bg: "bg-[#EF4444]/20" },
    mod_p2p: { label: "🔵 P2P Мод", color: "text-[#3B82F6]", bg: "bg-[#3B82F6]/20" },
    mod_market: { label: "🟣 Маркет Мод", color: "text-[#A855F7]", bg: "bg-[#A855F7]/20" },
    support: { label: "🔵 Поддержка", color: "text-[#06B6D4]", bg: "bg-[#06B6D4]/20" }
  };

  return (
    <div className="space-y-4" data-testid="staff-monitoring">
      <PageHeader 
        title="Мониторинг персонала" 
        subtitle="Активность и статус сотрудников"
        action={
          <Button variant="ghost" size="sm" onClick={fetchData} className="h-8">
            <RefreshCw className="w-4 h-4 mr-1" />
            Обновить
          </Button>
        }
      />

      {loading ? <LoadingSpinner /> : !data ? (
        <EmptyState icon={Eye} text="Не удалось загрузить данные" />
      ) : (
        <>
          {/* Summary Stats */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-[#121212] border border-white/5 rounded-xl p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-[#10B981]/20 flex items-center justify-center">
                  <div className="w-3 h-3 rounded-full bg-[#10B981] animate-pulse" />
                </div>
                <div>
                  <div className="text-2xl font-bold text-white">{data.total_online || 0}</div>
                  <div className="text-[#71717A] text-xs">Онлайн сейчас</div>
                </div>
              </div>
            </div>
            <div className="bg-[#121212] border border-white/5 rounded-xl p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-[#3B82F6]/20 flex items-center justify-center">
                  <Users className="w-5 h-5 text-[#3B82F6]" />
                </div>
                <div>
                  <div className="text-2xl font-bold text-white">{data.total_staff || 0}</div>
                  <div className="text-[#71717A] text-xs">Всего персонала</div>
                </div>
              </div>
            </div>
            <div className="bg-[#121212] border border-white/5 rounded-xl p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-[#F59E0B]/20 flex items-center justify-center">
                  <Activity className="w-5 h-5 text-[#F59E0B]" />
                </div>
                <div>
                  <div className="text-2xl font-bold text-white">
                    {(data.staff || []).reduce((sum, s) => sum + (s.decisions_today || 0), 0)}
                  </div>
                  <div className="text-[#71717A] text-xs">Решений сегодня</div>
                </div>
              </div>
            </div>
          </div>

          {/* Staff Table */}
          <div className="bg-[#121212] border border-white/5 rounded-xl overflow-hidden">
            <div className="p-4 border-b border-white/5">
              <h3 className="text-white font-semibold flex items-center gap-2">
                <UserCog className="w-5 h-5 text-[#71717A]" />
                Активность сотрудников
              </h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/5 text-[#71717A] text-xs">
                    <th className="text-left p-3">Сотрудник</th>
                    <th className="text-left p-3">Роль</th>
                    <th className="text-center p-3">Статус</th>
                    <th className="text-center p-3">Решений</th>
                    <th className="text-center p-3">Сообщений</th>
                    <th className="text-left p-3">Последнее действие</th>
                  </tr>
                </thead>
                <tbody>
                  {(data.staff || []).map(staff => {
                    const roleInfo = roleLabels[staff.role] || roleLabels.support;
                    return (
                      <tr key={staff.id} className="border-b border-white/5 hover:bg-white/5">
                        <td className="p-3">
                          <div className="flex items-center gap-2">
                            <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${roleInfo.bg}`}>
                              <UserCog className={`w-4 h-4 ${roleInfo.color}`} />
                            </div>
                            <div>
                              <div className="text-white text-sm font-medium">{staff.nickname || staff.login}</div>
                              <div className="text-[#52525B] text-xs">@{staff.login}</div>
                            </div>
                          </div>
                        </td>
                        <td className="p-3">
                          <span className={`px-2 py-1 rounded text-xs ${roleInfo.bg} ${roleInfo.color}`}>
                            {roleInfo.label}
                          </span>
                        </td>
                        <td className="p-3 text-center">
                          <div className="flex items-center justify-center gap-2">
                            <div className={`w-2.5 h-2.5 rounded-full ${staff.is_online ? 'bg-[#10B981] animate-pulse' : 'bg-[#52525B]'}`} />
                            <span className={`text-xs ${staff.is_online ? 'text-[#10B981]' : 'text-[#52525B]'}`}>
                              {staff.is_online ? 'Онлайн' : 'Оффлайн'}
                            </span>
                          </div>
                        </td>
                        <td className="p-3 text-center">
                          <span className={`text-sm font-mono ${staff.decisions_today > 0 ? 'text-[#10B981]' : 'text-[#52525B]'}`}>
                            {staff.decisions_today || 0}
                          </span>
                        </td>
                        <td className="p-3 text-center">
                          <span className={`text-sm font-mono ${staff.messages_today > 0 ? 'text-[#3B82F6]' : 'text-[#52525B]'}`}>
                            {staff.messages_today || 0}
                          </span>
                        </td>
                        <td className="p-3">
                          {staff.last_decision ? (
                            <div className="text-xs">
                              <div className="text-[#A1A1AA]">{staff.last_decision.decision_type || 'N/A'}</div>
                              <div className="text-[#52525B]">
                                {new Date(staff.last_decision.created_at).toLocaleString("ru-RU", { 
                                  day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'
                                })}
                              </div>
                            </div>
                          ) : (
                            <span className="text-[#52525B] text-xs">—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
