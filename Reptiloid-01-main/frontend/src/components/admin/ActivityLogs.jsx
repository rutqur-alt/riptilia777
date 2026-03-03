import React, { useState, useEffect } from "react";
import { toast } from "sonner";
import { History, Activity } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { Badge, LoadingSpinner, EmptyState, PageHeader } from "@/components/admin/SharedComponents";

export function ActivityLogs() {
  const { token } = useAuth();
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { fetchLogs(); }, []);

  const fetchLogs = async () => {
    try {
      const response = await axios.get(`${API}/super-admin/activity-log?limit=100`, { headers: { Authorization: `Bearer ${token}` } });
      setLogs(response.data || []);
    } catch (error) {
      toast.error("Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  };

  const actionColors = {
    ban_user: "red",
    unban_user: "green",
    adjust_balance: "yellow",
    toggle_maintenance: "purple",
    create_staff: "blue",
    delete_staff: "red",
    update_commissions: "yellow",
    delete_message: "gray",
    delete_conversation: "gray"
  };

  return (
    <div className="space-y-4" data-testid="activity-logs">
      <PageHeader title="Логи действий" subtitle="История действий администраторов" />

      {loading ? <LoadingSpinner /> : logs.length === 0 ? (
        <EmptyState icon={History} text="Нет записей" />
      ) : (
        <div className="space-y-1">
          {logs.map((log, i) => (
            <div key={i} className="bg-[#121212] border border-white/5 rounded-lg p-2 flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center">
                <Activity className={`w-3.5 h-3.5 text-${actionColors[log.action] || 'gray'}-500`} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-white text-xs font-medium">{log.admin_login}</span>
                  <Badge color={actionColors[log.action] || "gray"}>{log.action}</Badge>
                </div>
                <div className="text-[#52525B] text-[10px] truncate">
                  {log.target_type}: {log.target_id?.slice(0, 8)}...
                  {log.details && Object.keys(log.details).length > 0 && (
                    <span> • {JSON.stringify(log.details).slice(0, 50)}</span>
                  )}
                </div>
              </div>
              <div className="text-[#3F3F46] text-[10px] whitespace-nowrap">
                {new Date(log.created_at).toLocaleString("ru-RU")}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default ActivityLogs;
