import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Store, Lock, Unlock, CheckCircle, XCircle, Trash2 } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { Badge, LoadingSpinner, EmptyState, PageHeader } from "@/components/admin/SharedComponents";

export function MarketShops() {
  const { token } = useAuth();
  const [shops, setShops] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { fetchShops(); }, []);

  const fetchShops = async () => {
    try {
      const response = await axios.get(`${API}/admin/shops`, { headers: { Authorization: `Bearer ${token}` } });
      setShops(response.data || []);
    } catch (error) {
      toast.error("Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateCommission = async (shopId, rate) => {
    try {
      await axios.put(`${API}/admin/shops/${shopId}/commission?commission_rate=${rate}`, {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success("Комиссия обновлена");
      fetchShops();
    } catch (error) {
      toast.error("Ошибка");
    }
  };

  const handleToggleBlock = async (shopId) => {
    try {
      const result = await axios.post(`${API}/admin/shops/${shopId}/block`, {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(result.data.is_blocked ? "Магазин заблокирован" : "Магазин разблокирован");
      fetchShops();
    } catch (error) {
      toast.error("Ошибка");
    }
  };

  const handleToggleBalanceLock = async (shopId) => {
    try {
      const result = await axios.post(`${API}/admin/shops/${shopId}/toggle-balance`,  {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(result.data.is_balance_locked ? "Счёт заблокирован" : "Счёт разблокирован");
      fetchShops();
    } catch (error) {
      toast.error("Ошибка");
    }
  };

  const handleDeleteShop = async (shopId, shopName) => {
    if (!window.confirm(`Удалить магазин "${shopName}"? Это действие необратимо!`)) return;
    try {
      await axios.delete(`${API}/admin/shops/${shopId}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success("Магазин удалён");
      fetchShops();
    } catch (error) {
      toast.error("Ошибка");
    }
  };

  return (
    <div className="space-y-4" data-testid="market-shops">
      <PageHeader title="Магазины" subtitle="Маркетплейс" />

      {loading ? <LoadingSpinner /> : shops.length === 0 ? (
        <EmptyState icon={Store} text="Нет магазинов" />
      ) : (
        <div className="space-y-2">
          {shops.map(shop => (
            <div key={shop.id} className={`bg-[#121212] border rounded-xl p-4 ${shop.is_blocked ? 'border-[#EF4444]/30' : 'border-white/5'}`}>
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-white font-medium">{shop.shop_name || "Магазин"}</span>
                    {shop.is_blocked && <Badge color="red">Заблокирован</Badge>}
                    {shop.is_balance_locked && <Badge color="yellow">Счёт заморожен</Badge>}
                  </div>
                  <div className="text-[#71717A] text-xs mt-1">
                    Владелец: @{shop.owner_nickname || shop.owner_login} • ID: {shop.id?.slice(0, 8)}...
                  </div>
                  <div className="flex items-center gap-4 mt-2 text-xs">
                    <span className="text-[#10B981]">Баланс: {(shop.shop_balance || 0).toFixed(2)} USDT</span>
                    <span className="text-[#A1A1AA]">Продаж: {shop.total_sales || 0}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {/* Commission */}
                  <div className="flex items-center gap-1 bg-[#0A0A0A] rounded-lg px-2 py-1">
                    <span className="text-[#71717A] text-xs">Комиссия:</span>
                    <Input 
                      type="number"
                      step="0.5"
                      min="0"
                      max="50"
                      defaultValue={shop.commission_rate || 5}
                      onBlur={(e) => {
                        const newRate = parseFloat(e.target.value);
                        if (newRate !== shop.commission_rate) handleUpdateCommission(shop.id, newRate);
                      }}
                      className="w-16 h-6 text-xs bg-transparent border-0 text-white text-center p-0"
                    />
                    <span className="text-[#71717A] text-xs">%</span>
                  </div>
                  
                  {/* Actions */}
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleToggleBalanceLock(shop.id)}
                    className={`h-7 w-7 p-0 ${shop.is_balance_locked ? 'text-[#10B981]' : 'text-[#F59E0B]'}`}
                    title={shop.is_balance_locked ? "Разморозить счёт" : "Заморозить счёт"}
                  >
                    {shop.is_balance_locked ? <Unlock className="w-3.5 h-3.5" /> : <Lock className="w-3.5 h-3.5" />}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleToggleBlock(shop.id)}
                    className={`h-7 w-7 p-0 ${shop.is_blocked ? 'text-[#10B981]' : 'text-[#EF4444]'}`}
                    title={shop.is_blocked ? "Разблокировать" : "Заблокировать"}
                  >
                    {shop.is_blocked ? <CheckCircle className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleDeleteShop(shop.id, shop.shop_name)}
                    className="text-[#EF4444] hover:text-[#F87171] h-7 w-7 p-0"
                    title="Удалить магазин"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default MarketShops;
