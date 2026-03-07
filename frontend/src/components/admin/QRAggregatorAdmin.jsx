import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Button } from "../ui/button";
import { API } from "@/App";
import {
  RefreshCw, Plus, Trash2, Edit, Save, ChevronDown, ChevronRight,
  Power, Activity, Shield, Key, Settings, BarChart3, Users
, DollarSign, AlertTriangle} from "lucide-react";


function FormField({ label, value, onChange, type = "text", placeholder = "" }) {
  return (
    <div>
      <label className="block text-xs text-gray-400 mb-1">{label}</label>
      <input type={type} value={value || ""} onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-[#0D0D1A] border border-gray-600 rounded px-3 py-1.5 text-sm text-white" />
    </div>
  );
}

export default function QRAggregatorAdmin() {
  const [providers, setProviders] = useState([]);
  const [settings, setSettings] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [expandedId, setExpandedId] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [activeTab, setActiveTab] = useState("providers");

  const token = localStorage.getItem("token");
  const headers = { Authorization: `Bearer ${token}` };

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [provRes, setRes, statRes] = await Promise.all([
        axios.get(`${API}/admin/qr-providers`, { headers }),
        axios.get(`${API}/admin/qr-aggregator/settings`, { headers }),
        axios.get(`${API}/admin/qr-aggregator/stats`, { headers }),
      ]);
      setProviders(provRes.data.providers || []);
      setSettings(setRes.data);
      setStats(statRes.data);
    } catch (e) { toast.error("Ошибка загрузки данных"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const updateSettings = async (newSettings) => {
    try {
      await axios.put(`${API}/admin/qr-aggregator/settings`, newSettings, { headers });
      toast.success("Настройки сохранены");
      fetchAll();
    } catch (e) { toast.error("Ошибка сохранения"); }
  };

  const createProvider = async (data) => {
    try {
      await axios.post(`${API}/admin/qr-providers`, data, { headers });
      toast.success("Провайдер создан");
      setShowCreateForm(false);
      fetchAll();
    } catch (e) { toast.error(e.response?.data?.detail || "Ошибка создания"); }
  };

  const updateProvider = async (id, data) => {
    try {
      await axios.put(`${API}/admin/qr-providers/${id}`, data, { headers });
      toast.success("Провайдер обновлён");
      setEditingId(null);
      fetchAll();
    } catch (e) { toast.error("Ошибка обновления"); }
  };

  const toggleProvider = async (id) => {
    try {
      await axios.post(`${API}/admin/qr-providers/${id}/toggle`, {}, { headers });
      toast.success("Статус изменён");
      fetchAll();
    } catch (e) { toast.error("Ошибка"); }
  };

  const deleteProvider = async (id) => {
    if (!confirm("Удалить провайдера?")) return;
    try {
      await axios.delete(`${API}/admin/qr-providers/${id}`, { headers });
      toast.success("Провайдер удалён");
      fetchAll();
    } catch (e) { toast.error(e.response?.data?.detail || "Ошибка удаления"); }
  };

  const healthCheck = async (id) => {
    try {
      const res = await axios.post(`${API}/admin/qr-providers/${id}/health-check`, {}, { headers });
      const d = res.data;
      toast.success(`NSPK: ${d.nspk_available ? 'OK' : 'X'} | TransGrant: ${d.transgrant_available ? 'OK' : 'X'}`);
      fetchAll();
    } catch (e) { toast.error("Ошибка проверки"); }
  };

  if (loading) return <div className="flex justify-center p-8"><RefreshCw className="animate-spin w-6 h-6 text-gray-400" /></div>;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">QR Агрегатор</h1>
          <p className="text-sm text-gray-400">Две интеграции: NSPK (QR) и TransGrant (СНГ)</p>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={fetchAll}><RefreshCw className="w-4 h-4 text-gray-400" /></Button>
          <Button size="sm" onClick={() => setShowCreateForm(!showCreateForm)} className="bg-[#A855F7] hover:bg-[#9333EA] text-white">
            <Plus className="w-4 h-4 mr-1" /> Провайдер
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-700 pb-2">
        {[
          { key: "providers", label: "Провайдеры", icon: Users },
          { key: "settings", label: "Настройки", icon: Settings },
          { key: "stats", label: "Статистика", icon: BarChart3 },
        ].map(t => (
          <button key={t.key} onClick={() => setActiveTab(t.key)}
            className={`flex items-center gap-1 px-3 py-1.5 rounded text-sm ${activeTab === t.key ? 'bg-[#A855F7] text-white' : 'text-gray-400 hover:text-white'}`}>
            <t.icon className="w-4 h-4" /> {t.label}
          </button>
        ))}
      </div>

      {/* Stats Tab */}
      {activeTab === "stats" && stats && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard label="Провайдеры" value={`${stats.providers?.active || 0} / ${stats.providers?.total || 0}`} sub="активных / всего" color="purple" />
            <StatCard label="Общий депозит" value={`${(stats.total_deposit_usdt || 0).toFixed(2)} USDT`} color="green" />
          </div>

          {/* NSPK Stats */}
          <div className="bg-[#1A1A2E] border border-gray-700 rounded-lg p-4">
            <h3 className="text-white font-medium mb-3">NSPK (QR) - Статистика</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
              <div><span className="text-gray-400">Всего операций:</span> <span className="text-white ml-1">{stats.nspk?.total_operations || 0}</span></div>
              <div><span className="text-gray-400">Завершённых:</span> <span className="text-green-400 ml-1">{stats.nspk?.completed || 0}</span></div>
              <div><span className="text-gray-400">Сегодня:</span> <span className="text-white ml-1">{stats.nspk?.today_operations || 0} ({stats.nspk?.today_completed || 0} завершённых)</span></div>
              <div><span className="text-gray-400">Объём:</span> <span className="text-white ml-1">{(stats.nspk?.total_volume_rub || 0).toLocaleString()} P</span></div>
              <div><span className="text-gray-400">Объём сегодня:</span> <span className="text-white ml-1">{(stats.nspk?.today_volume_rub || 0).toLocaleString()} P</span></div>
            </div>
          </div>

          {/* TransGrant Stats */}
          <div className="bg-[#1A1A2E] border border-gray-700 rounded-lg p-4">
            <h3 className="text-white font-medium mb-3">TransGrant (СНГ) - Статистика</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
              <div><span className="text-gray-400">Всего операций:</span> <span className="text-white ml-1">{stats.transgrant?.total_operations || 0}</span></div>
              <div><span className="text-gray-400">Завершённых:</span> <span className="text-green-400 ml-1">{stats.transgrant?.completed || 0}</span></div>
              <div><span className="text-gray-400">Сегодня:</span> <span className="text-white ml-1">{stats.transgrant?.today_operations || 0} ({stats.transgrant?.today_completed || 0} завершённых)</span></div>
              <div><span className="text-gray-400">Объём:</span> <span className="text-white ml-1">{(stats.transgrant?.total_volume_rub || 0).toLocaleString()} P</span></div>
              <div><span className="text-gray-400">Объём сегодня:</span> <span className="text-white ml-1">{(stats.transgrant?.today_volume_rub || 0).toLocaleString()} P</span></div>
            </div>
          </div>
        </div>
      )}

      {/* Settings Tab */}
      {activeTab === "settings" && settings && <SettingsPanel settings={settings} onSave={updateSettings} />}

      {/* Providers Tab */}
      {activeTab === "providers" && (
        <div className="space-y-4">
          {showCreateForm && <CreateProviderForm onCreate={createProvider} onCancel={() => setShowCreateForm(false)} />}

          {providers.length === 0 ? (
            <div className="bg-[#1A1A2E] border border-gray-700 rounded-lg p-8 text-center text-gray-400">
              Нет провайдеров. Нажмите "+ Провайдер" чтобы создать.
            </div>
          ) : (
            providers.map(p => (
              <ProviderCard key={p.id} provider={p}
                expanded={expandedId === p.id}
                editing={editingId === p.id}
                onToggleExpand={() => setExpandedId(expandedId === p.id ? null : p.id)}
                onEdit={() => setEditingId(editingId === p.id ? null : p.id)}
                onUpdate={(data) => updateProvider(p.id, data)}
                onToggle={() => toggleProvider(p.id)}
                onDelete={() => deleteProvider(p.id)}
                onHealthCheck={() => healthCheck(p.id)}
                onRefresh={fetchAll}
                headers={headers}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}

// ==================== Settings Panel ====================
function SettingsPanel({ settings, onSave }) {
  const [form, setForm] = useState({
    is_enabled: settings.is_enabled ?? true,
    health_check_interval: settings.health_check_interval || 45,
    nspk_min_amount: settings.nspk_min_amount || 100,
    nspk_max_amount: settings.nspk_max_amount || 500000,
    nspk_commission_percent: settings.nspk_commission_percent || 5.0,
    transgrant_min_amount: settings.transgrant_min_amount || 100,
    transgrant_max_amount: settings.transgrant_max_amount || 300000,
    transgrant_commission_percent: settings.transgrant_commission_percent || 7.0,
  });

  return (
    <div className="space-y-6">
      {/* General */}
      <div className="bg-[#1A1A2E] border border-gray-700 rounded-lg p-4">
        <h3 className="text-white font-medium mb-3">Общие настройки</h3>
        <div className="grid grid-cols-2 gap-4">
          <div className="flex items-center gap-3">
            <label className="text-sm text-gray-400">Агрегатор включён:</label>
            <input type="checkbox" checked={form.is_enabled} onChange={(e) => setForm({...form, is_enabled: e.target.checked})} className="accent-purple-500" />
          </div>
          <FormField label="Интервал проверки API (сек)" value={form.health_check_interval} type="number"
            onChange={(v) => setForm({...form, health_check_interval: parseInt(v) || 45})} />
        </div>
      </div>

      {/* NSPK Settings */}
      <div className="bg-[#1A1A2E] border border-blue-500/30 rounded-lg p-4">
        <h3 className="text-blue-400 font-medium mb-3">NSPK (QR) - Настройки</h3>
        <div className="grid grid-cols-3 gap-4">
          <FormField label="Мин. сумма (P)" value={form.nspk_min_amount} type="number"
            onChange={(v) => setForm({...form, nspk_min_amount: parseFloat(v) || 0})} />
          <FormField label="Макс. сумма (P)" value={form.nspk_max_amount} type="number"
            onChange={(v) => setForm({...form, nspk_max_amount: parseFloat(v) || 0})} />
          <FormField label="Комиссия (%)" value={form.nspk_commission_percent} type="number"
            onChange={(v) => setForm({...form, nspk_commission_percent: parseFloat(v) || 0})} />
        </div>
      </div>

      {/* TransGrant Settings */}
      <div className="bg-[#1A1A2E] border border-orange-500/30 rounded-lg p-4">
        <h3 className="text-orange-400 font-medium mb-3">TransGrant (СНГ) - Настройки</h3>
        <div className="grid grid-cols-3 gap-4">
          <FormField label="Мин. сумма (P)" value={form.transgrant_min_amount} type="number"
            onChange={(v) => setForm({...form, transgrant_min_amount: parseFloat(v) || 0})} />
          <FormField label="Макс. сумма (P)" value={form.transgrant_max_amount} type="number"
            onChange={(v) => setForm({...form, transgrant_max_amount: parseFloat(v) || 0})} />
          <FormField label="Комиссия (%)" value={form.transgrant_commission_percent} type="number"
            onChange={(v) => setForm({...form, transgrant_commission_percent: parseFloat(v) || 0})} />
        </div>
      </div>

      <Button onClick={() => onSave(form)} className="bg-[#A855F7] hover:bg-[#9333EA] text-white">
        <Save className="w-4 h-4 mr-1" /> Сохранить настройки
      </Button>
    </div>
  );
}

// ==================== Create Provider Form ====================
function CreateProviderForm({ onCreate, onCancel }) {
  const [form, setForm] = useState({
    login: "", password: "", display_name: "",
    nspk_enabled: true, transgrant_enabled: false,
    nspk_commission_percent: 5.0, transgrant_commission_percent: 7.0,
    weight: 100, max_concurrent_operations: 10,
  });

  return (
    <div className="bg-[#1A1A2E] border border-purple-500/30 rounded-lg p-6 space-y-4">
      <h3 className="text-lg font-semibold text-white">Новый провайдер</h3>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <FormField label="Логин" value={form.login} onChange={(v) => setForm({...form, login: v})} />
        <FormField label="Пароль" value={form.password} onChange={(v) => setForm({...form, password: v})} type="password" />
        <FormField label="Имя" value={form.display_name} onChange={(v) => setForm({...form, display_name: v})} />
        <FormField label="Вес" value={form.weight} type="number" onChange={(v) => setForm({...form, weight: parseInt(v) || 100})} />
        <FormField label="Макс. операций" value={form.max_concurrent_operations} type="number" onChange={(v) => setForm({...form, max_concurrent_operations: parseInt(v) || 10})} />
      </div>

      {/* Integrations */}
      <div className="grid grid-cols-2 gap-4">
        <div className="p-3 rounded border border-blue-500/30 bg-blue-500/5">
          <div className="flex items-center gap-2 mb-2">
            <input type="checkbox" checked={form.nspk_enabled} onChange={(e) => setForm({...form, nspk_enabled: e.target.checked})} className="accent-blue-500" />
            <span className="text-sm text-blue-400 font-medium">NSPK (QR)</span>
          </div>
          <FormField label="Комиссия NSPK (%)" value={form.nspk_commission_percent} type="number"
            onChange={(v) => setForm({...form, nspk_commission_percent: parseFloat(v) || 0})} />
        </div>
        <div className="p-3 rounded border border-orange-500/30 bg-orange-500/5">
          <div className="flex items-center gap-2 mb-2">
            <input type="checkbox" checked={form.transgrant_enabled} onChange={(e) => setForm({...form, transgrant_enabled: e.target.checked})} className="accent-orange-500" />
            <span className="text-sm text-orange-400 font-medium">TransGrant (СНГ)</span>
          </div>
          <FormField label="Комиссия TransGrant (%)" value={form.transgrant_commission_percent} type="number"
            onChange={(v) => setForm({...form, transgrant_commission_percent: parseFloat(v) || 0})} />
        </div>
      </div>

      <div className="flex gap-2">
        <Button onClick={() => onCreate(form)} className="bg-[#A855F7] hover:bg-[#9333EA] text-white">
          <Plus className="w-4 h-4 mr-1" /> Создать
        </Button>
        <Button variant="outline" onClick={onCancel} className="border-gray-600 text-gray-300">Отмена</Button>
      </div>
    </div>
  );
}

// ==================== Provider Card ====================
function ProviderCard({ provider, expanded, editing, onToggleExpand, onEdit, onUpdate, onToggle, onDelete, onHealthCheck, onRefresh, headers }) {
  const [editData, setEditData] = useState({
    display_name: provider.display_name,
    weight: provider.weight,
    max_concurrent_operations: provider.max_concurrent_operations,
    nspk_enabled: provider.nspk_enabled,
    nspk_commission_percent: provider.nspk_commission_percent,
    transgrant_enabled: provider.transgrant_enabled,
    transgrant_commission_percent: provider.transgrant_commission_percent,
  });

  const [showApiKeys, setShowApiKeys] = useState(false);
  const [apiKeys, setApiKeys] = useState(null);
  const [editingKeys, setEditingKeys] = useState(false);
  const [keyForm, setKeyForm] = useState({});
  const [newPassword, setNewPassword] = useState(null);
  const [showBalanceAdjust, setShowBalanceAdjust] = useState(false);
  const [balanceAmount, setBalanceAmount] = useState("");
  const [balanceReason, setBalanceReason] = useState("admin_adjustment");
  const [reconciling, setReconciling] = useState(false);

  const isActive = provider.is_active;
  const nspkOk = provider.nspk_api_available;
  const transgrantOk = provider.transgrant_api_available;

  const adjustBalance = async (amount) => {
    if (!amount || isNaN(parseFloat(amount))) { toast.error("Введите сумму"); return; }
    try {
      const res = await axios.post(`${API}/admin/qr-providers/${provider.id}/adjust-balance`, {
        amount: parseFloat(amount),
        reason: balanceReason || "admin_adjustment"
      }, { headers });
      toast.success(`Баланс изменён: ${res.data.old_balance} → ${res.data.new_balance} USDT`);
      setBalanceAmount("");
      setShowBalanceAdjust(false);
      // Trigger parent refresh
      if (onRefresh) onRefresh();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Ошибка изменения баланса");
    }
  };

  const reconcileFrozen = async () => {
    setReconciling(true);
    try {
      const res = await axios.post(`${API}/admin/qr-providers/${provider.id}/reconcile-frozen`, {}, { headers });
      toast.success(`Заморозка пересчитана: ${res.data.old_frozen} → ${res.data.new_frozen} USDT. Исправлено операций: ${res.data.fixed_operations}`);
      if (onRefresh) onRefresh();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Ошибка пересчёта");
    } finally { setReconciling(false); }
  };

  const loadApiKeys = async () => {
    try {
      const res = await axios.get(`${API}/admin/qr-providers/${provider.id}/api-keys`, { headers });
      setApiKeys(res.data);
      setKeyForm({
        nspk_api_key: res.data.nspk?.api_key || "",
        nspk_secret_key: "",
        nspk_api_url: res.data.nspk?.api_url || "https://api.trustgain.io",
        nspk_merchant_id: res.data.nspk?.merchant_id || "",
        nspk_gateway_id: res.data.nspk?.gateway_id || "",
        transgrant_api_key: res.data.transgrant?.api_key || "",
        transgrant_secret_key: "",
        transgrant_api_url: res.data.transgrant?.api_url || "https://api.trustgain.io",
        transgrant_merchant_id: res.data.transgrant?.merchant_id || "",
        transgrant_gateway_id: res.data.transgrant?.gateway_id || "",
      });
      setShowApiKeys(true);
    } catch (e) { toast.error("Ошибка загрузки API ключей"); }
  };

  const saveApiKeys = async () => {
    try {
      // Only send non-empty fields
      const payload = {};
      Object.entries(keyForm).forEach(([k, v]) => { if (v) payload[k] = v; });
      await axios.put(`${API}/admin/qr-providers/${provider.id}/api-keys`, payload, { headers });
      toast.success("API ключи обновлены");
      setEditingKeys(false);
      loadApiKeys();
    } catch (e) { toast.error("Ошибка сохранения API ключей"); }
  };

  const resetPassword = async () => {
    if (!confirm("Сбросить пароль провайдера?")) return;
    try {
      const res = await axios.post(`${API}/admin/qr-providers/${provider.id}/reset-password`, {}, { headers });
      setNewPassword(res.data.new_password);
      toast.success("Пароль сброшен");
    } catch (e) { toast.error("Ошибка сброса пароля"); }
  };

  return (
    <div className="bg-[#1A1A2E] border border-gray-700 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-4 cursor-pointer hover:bg-[#1E1E36]" onClick={onToggleExpand}>
        <div className="flex items-center gap-3">
          <div className={`w-3 h-3 rounded-full ${isActive ? 'bg-green-500' : 'bg-red-500'}`} />
          <div>
            <p className="text-white font-medium">{provider.display_name}</p>
            <p className="text-xs text-gray-400">
              Логин: <span className="font-mono text-gray-300">{provider.login}</span> | ID: {provider.id?.slice(0,8)}...
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="text-sm font-medium text-white">{(provider.balance_usdt || 0).toFixed(2)} USDT</p>
            <p className="text-xs text-gray-400">баланс</p>
          </div>
          <div className="flex flex-col gap-1">
            <span className={`text-xs px-2 py-0.5 rounded ${nspkOk ? 'bg-blue-500/20 text-blue-400' : 'bg-gray-500/20 text-gray-500'}`}>
              NSPK {nspkOk ? 'OK' : 'X'}
            </span>
            <span className={`text-xs px-2 py-0.5 rounded ${transgrantOk ? 'bg-orange-500/20 text-orange-400' : 'bg-gray-500/20 text-gray-500'}`}>
              TG {transgrantOk ? 'OK' : 'X'}
            </span>
          </div>
          <span className={`text-xs px-2 py-0.5 rounded ${isActive ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
            {isActive ? 'Активен' : 'Выкл'}
          </span>
          {expanded ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
        </div>
      </div>

      {/* Expanded */}
      {expanded && (
        <div className="border-t border-gray-700 p-4 space-y-4">
          {/* Info */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
            <div><span className="text-gray-400">Баланс:</span> <span className="text-white ml-1">{(provider.balance_usdt || 0).toFixed(2)} USDT</span></div>
            <div><span className="text-yellow-400">Заморожено:</span> <span className="text-yellow-300 ml-1">{(provider.frozen_usdt || 0).toFixed(2)} USDT</span></div>
            <div><span className="text-green-400">Доступно:</span> <span className="text-green-300 ml-1">{((provider.balance_usdt || 0) - (provider.frozen_usdt || 0)).toFixed(2)} USDT</span></div>
            <div><span className="text-gray-400">Вес:</span> <span className="text-white ml-1">{provider.weight}</span></div>
            <div><span className="text-gray-400">Успешность:</span> <span className="text-white ml-1">{provider.success_rate || 100}%</span></div>
          </div>

          {/* Balance Adjustment */}
          {showBalanceAdjust && (
            <div className="bg-[#0D0D1A] border border-purple-500/30 rounded-lg p-4 space-y-3">
              <h4 className="text-sm font-medium text-purple-400">Управление балансом</h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="text-xs text-gray-400 block mb-1">Сумма USDT (+ пополнение, - списание)</label>
                  <input type="number" step="0.01" value={balanceAmount}
                    onChange={(e) => setBalanceAmount(e.target.value)}
                    className="w-full bg-[#1A1A2E] border border-gray-600 rounded px-3 py-2 text-white text-sm"
                    placeholder="Например: 100 или -50" />
                </div>
                <div>
                  <label className="text-xs text-gray-400 block mb-1">Причина</label>
                  <select value={balanceReason} onChange={(e) => setBalanceReason(e.target.value)}
                    className="w-full bg-[#1A1A2E] border border-gray-600 rounded px-3 py-2 text-white text-sm">
                    <option value="admin_adjustment">Корректировка админом</option>
                    <option value="deposit">Пополнение</option>
                    <option value="withdrawal">Вывод</option>
                    <option value="correction">Исправление ошибки</option>
                  </select>
                </div>
                <div className="flex items-end gap-2">
                  <Button size="sm" onClick={() => adjustBalance(balanceAmount)}
                    className="bg-[#A855F7] hover:bg-[#9333EA] text-white">
                    Применить
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => setShowBalanceAdjust(false)}
                    className="border-gray-600 text-gray-400">Отмена</Button>
                </div>
              </div>
              <div className="flex gap-2 pt-2 border-t border-gray-700">
                <Button variant="outline" size="sm" onClick={reconcileFrozen} disabled={reconciling}
                  className="border-yellow-500/50 text-yellow-400 hover:bg-yellow-500/10">
                  {reconciling ? "Пересчёт..." : "Пересчитать заморозку"}
                </Button>
              </div>
            </div>
          )}

          {/* Integrations Status */}
          <div className="grid grid-cols-2 gap-4">
            <div className={`p-3 rounded border ${provider.nspk_enabled ? 'border-blue-500/30 bg-blue-500/5' : 'border-gray-600 bg-gray-800/50'}`}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-blue-400">NSPK (QR)</span>
                <span className={`text-xs px-2 py-0.5 rounded ${provider.nspk_enabled ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'}`}>
                  {provider.nspk_enabled ? 'Вкл' : 'Выкл'}
                </span>
              </div>
              <p className="text-xs text-gray-400">Комиссия: {provider.nspk_commission_percent || 5}%</p>
            </div>
            <div className={`p-3 rounded border ${provider.transgrant_enabled ? 'border-orange-500/30 bg-orange-500/5' : 'border-gray-600 bg-gray-800/50'}`}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-orange-400">TransGrant (СНГ)</span>
                <span className={`text-xs px-2 py-0.5 rounded ${provider.transgrant_enabled ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'}`}>
                  {provider.transgrant_enabled ? 'Вкл' : 'Выкл'}
                </span>
              </div>
              <p className="text-xs text-gray-400">Комиссия: {provider.transgrant_commission_percent || 7}%</p>
            </div>
          </div>

          {/* New Password */}
          {newPassword && (
            <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3">
              <p className="text-sm text-green-400 mb-1">Новый пароль:</p>
              <div className="flex items-center gap-2">
                <code className="text-white bg-[#0D0D1A] px-3 py-1 rounded font-mono text-lg">{newPassword}</code>
                <Button variant="outline" size="sm" onClick={() => { navigator.clipboard.writeText(newPassword); toast.success("Скопировано"); }}
                  className="border-green-500/50 text-green-400 hover:bg-green-500/10">Копировать</Button>
                <Button variant="outline" size="sm" onClick={() => setNewPassword(null)} className="border-gray-600 text-gray-400">Скрыть</Button>
              </div>
            </div>
          )}

          {/* API Keys Section - TWO SEPARATE INTEGRATIONS */}
          {showApiKeys && apiKeys && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-medium text-white">API Ключи TrustGain</h4>
                <div className="flex gap-2">
                  {!editingKeys ? (
                    <Button variant="outline" size="sm" onClick={() => setEditingKeys(true)} className="border-gray-600 text-gray-300 hover:bg-gray-700">
                      <Edit className="w-3 h-3 mr-1" /> Изменить
                    </Button>
                  ) : (
                    <>
                      <Button size="sm" onClick={saveApiKeys} className="bg-[#A855F7] hover:bg-[#9333EA] text-white">
                        <Save className="w-3 h-3 mr-1" /> Сохранить
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => setEditingKeys(false)} className="border-gray-600 text-gray-300">Отмена</Button>
                    </>
                  )}
                  <Button variant="outline" size="sm" onClick={() => setShowApiKeys(false)} className="border-gray-600 text-gray-400">Скрыть</Button>
                </div>
              </div>

              {/* NSPK Keys */}
              <div className="bg-[#0D0D1A] border border-blue-500/30 rounded-lg p-3">
                <h5 className="text-xs text-blue-400 font-medium mb-2">NSPK (QR) - API</h5>
                {editingKeys ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    <FormField label="API Key" value={keyForm.nspk_api_key} onChange={(v) => setKeyForm({...keyForm, nspk_api_key: v})} />
                    <FormField label="Secret Key" value={keyForm.nspk_secret_key} onChange={(v) => setKeyForm({...keyForm, nspk_secret_key: v})} type="password" placeholder="Оставьте пустым чтобы не менять" />
                    <FormField label="API URL" value={keyForm.nspk_api_url} onChange={(v) => setKeyForm({...keyForm, nspk_api_url: v})} />
                    <FormField label="Merchant ID (TrustGain)" value={keyForm.nspk_merchant_id} onChange={(v) => setKeyForm({...keyForm, nspk_merchant_id: v})} />
                    <FormField label="Gateway ID" value={keyForm.nspk_gateway_id} onChange={(v) => setKeyForm({...keyForm, nspk_gateway_id: v})} />
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div><span className="text-xs text-gray-400">API Key:</span> <span className="text-white font-mono">{apiKeys.nspk?.api_key || '-'}</span></div>
                    <div><span className="text-xs text-gray-400">Secret:</span> <span className="text-white font-mono">{apiKeys.nspk?.secret_key || '-'}</span></div>
                    <div><span className="text-xs text-gray-400">URL:</span> <span className="text-white font-mono">{apiKeys.nspk?.api_url || '-'}</span></div>
                    <div><span className="text-xs text-gray-400">Merchant ID:</span> <span className="text-white font-mono">{apiKeys.nspk?.merchant_id || '-'}</span></div>
                    <div><span className="text-xs text-gray-400">Gateway ID:</span> <span className="text-white font-mono">{apiKeys.nspk?.gateway_id || '-'}</span></div>
                  </div>
                )}
              </div>

              {/* TransGrant Keys */}
              <div className="bg-[#0D0D1A] border border-orange-500/30 rounded-lg p-3">
                <h5 className="text-xs text-orange-400 font-medium mb-2">TransGrant (СНГ) - API</h5>
                {editingKeys ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    <FormField label="API Key" value={keyForm.transgrant_api_key} onChange={(v) => setKeyForm({...keyForm, transgrant_api_key: v})} />
                    <FormField label="Secret Key" value={keyForm.transgrant_secret_key} onChange={(v) => setKeyForm({...keyForm, transgrant_secret_key: v})} type="password" placeholder="Оставьте пустым чтобы не менять" />
                    <FormField label="API URL" value={keyForm.transgrant_api_url} onChange={(v) => setKeyForm({...keyForm, transgrant_api_url: v})} />
                    <FormField label="Merchant ID (TrustGain)" value={keyForm.transgrant_merchant_id} onChange={(v) => setKeyForm({...keyForm, transgrant_merchant_id: v})} />
                    <FormField label="Gateway ID" value={keyForm.transgrant_gateway_id} onChange={(v) => setKeyForm({...keyForm, transgrant_gateway_id: v})} />
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div><span className="text-xs text-gray-400">API Key:</span> <span className="text-white font-mono">{apiKeys.transgrant?.api_key || '-'}</span></div>
                    <div><span className="text-xs text-gray-400">Secret:</span> <span className="text-white font-mono">{apiKeys.transgrant?.secret_key || '-'}</span></div>
                    <div><span className="text-xs text-gray-400">URL:</span> <span className="text-white font-mono">{apiKeys.transgrant?.api_url || '-'}</span></div>
                    <div><span className="text-xs text-gray-400">Merchant ID:</span> <span className="text-white font-mono">{apiKeys.transgrant?.merchant_id || '-'}</span></div>
                    <div><span className="text-xs text-gray-400">Gateway ID:</span> <span className="text-white font-mono">{apiKeys.transgrant?.gateway_id || '-'}</span></div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Edit Form */}
          {editing && (
            <div className="border-t border-gray-700 pt-4 space-y-3">
              <h4 className="text-sm font-medium text-white">Редактирование</h4>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                <FormField label="Имя" value={editData.display_name} onChange={(v) => setEditData({...editData, display_name: v})} />
                <FormField label="Вес" value={editData.weight} type="number" onChange={(v) => setEditData({...editData, weight: parseInt(v) || 100})} />
                <FormField label="Макс. операций" value={editData.max_concurrent_operations} type="number" onChange={(v) => setEditData({...editData, max_concurrent_operations: parseInt(v) || 10})} />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="flex items-center gap-2">
                  <input type="checkbox" checked={editData.nspk_enabled} onChange={(e) => setEditData({...editData, nspk_enabled: e.target.checked})} className="accent-blue-500" />
                  <span className="text-sm text-gray-300">NSPK включён</span>
                  <input type="number" value={editData.nspk_commission_percent} onChange={(e) => setEditData({...editData, nspk_commission_percent: parseFloat(e.target.value) || 0})}
                    className="w-20 bg-[#0D0D1A] border border-gray-600 rounded px-2 py-1 text-sm text-white ml-2" />
                  <span className="text-xs text-gray-400">%</span>
                </div>
                <div className="flex items-center gap-2">
                  <input type="checkbox" checked={editData.transgrant_enabled} onChange={(e) => setEditData({...editData, transgrant_enabled: e.target.checked})} className="accent-orange-500" />
                  <span className="text-sm text-gray-300">TransGrant включён</span>
                  <input type="number" value={editData.transgrant_commission_percent} onChange={(e) => setEditData({...editData, transgrant_commission_percent: parseFloat(e.target.value) || 0})}
                    className="w-20 bg-[#0D0D1A] border border-gray-600 rounded px-2 py-1 text-sm text-white ml-2" />
                  <span className="text-xs text-gray-400">%</span>
                </div>
              </div>
              <Button size="sm" onClick={() => onUpdate(editData)} className="bg-[#A855F7] hover:bg-[#9333EA] text-white">
                <Save className="w-4 h-4 mr-1" /> Сохранить
              </Button>
            </div>
          )}

          {/* Actions */}
          <div className="flex flex-wrap gap-2 pt-2 border-t border-gray-700">
            <Button variant="outline" size="sm" onClick={onEdit} className="border-gray-600 text-gray-300 hover:bg-gray-700">
              <Edit className="w-3 h-3 mr-1" /> {editing ? 'Отмена' : 'Редактировать'}
            </Button>
            <Button variant="outline" size="sm" onClick={() => setShowBalanceAdjust(!showBalanceAdjust)}
              className="border-green-500/50 text-green-400 hover:bg-green-500/10">
              <DollarSign className="w-3 h-3 mr-1" /> Баланс
            </Button>
            <Button variant="outline" size="sm" onClick={loadApiKeys} className="border-purple-500/50 text-purple-400 hover:bg-purple-500/10">
              <Shield className="w-3 h-3 mr-1" /> API ключи
            </Button>
            <Button variant="outline" size="sm" onClick={resetPassword} className="border-orange-500/50 text-orange-400 hover:bg-orange-500/10">
              <Key className="w-3 h-3 mr-1" /> Сброс пароля
            </Button>
            <Button variant="outline" size="sm" onClick={onHealthCheck} className="border-gray-600 text-gray-300 hover:bg-gray-700">
              <Activity className="w-3 h-3 mr-1" /> Проверить API
            </Button>
            <Button variant="outline" size="sm" onClick={onToggle}
              className={isActive ? "border-yellow-500/50 text-yellow-400 hover:bg-yellow-500/10" : "border-green-500/50 text-green-400 hover:bg-green-500/10"}>
              <Power className="w-3 h-3 mr-1" /> {isActive ? 'Деактивировать' : 'Активировать'}
            </Button>
            <Button size="sm" variant="outline"
              className="text-[#EF4444] border-[#EF4444]/30 hover:bg-[#EF4444]/10"
              onClick={() => {
                if (onShowDisputes) onShowDisputes(provider.id);
                else window.location.href = "/admin/messages?category=p2p_dispute";
              }}
            >
              <AlertTriangle className="w-3 h-3 mr-1" /> Споры
            </Button>
            <Button variant="outline" size="sm" onClick={onDelete} className="border-red-500/50 text-red-400 hover:bg-red-500/10 ml-auto">
              <Trash2 className="w-3 h-3 mr-1" /> Удалить
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

// ==================== Stat Card ====================
function StatCard({ label, value, sub, color }) {
  const colors = {
    purple: "border-purple-500/30 bg-purple-500/10",
    green: "border-green-500/30 bg-green-500/10",
    blue: "border-blue-500/30 bg-blue-500/10",
    yellow: "border-yellow-500/30 bg-yellow-500/10",
  };
  return (
    <div className={`rounded-lg border p-4 ${colors[color] || colors.purple}`}>
      <p className="text-xs text-gray-400 uppercase">{label}</p>
      <p className="text-xl font-bold text-white mt-1">{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
    </div>
  );
}
