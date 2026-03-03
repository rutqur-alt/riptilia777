import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { TrendingUp, Pause } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { Badge, LoadingSpinner, EmptyState, PageHeader } from "@/components/admin/SharedComponents";

export function P2POffers() {
  const { token } = useAuth();
  const [offers, setOffers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { fetchOffers(); }, []);

  const fetchOffers = async () => {
    try {
      const response = await axios.get(`${API}/admin/offers`, { headers: { Authorization: `Bearer ${token}` } });
      setOffers(response.data || []);
    } catch (error) {
      toast.error("Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  };

  const handleDeactivate = async (offerId) => {
    try {
      await axios.put(`${API}/admin/offers/${offerId}/deactivate`, {}, { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Деактивировано");
      fetchOffers();
    } catch (error) {
      toast.error("Ошибка");
    }
  };

  return (
    <div className="space-y-4" data-testid="p2p-offers">
      <PageHeader title="Объявления P2P" subtitle={`Всего: ${offers.length}`} />

      {loading ? <LoadingSpinner /> : offers.length === 0 ? (
        <EmptyState icon={TrendingUp} text="Нет объявлений" />
      ) : (
        <div className="bg-[#121212] border border-white/5 rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/5 bg-[#0A0A0A]">
                <th className="text-left py-2 px-3 text-[10px] text-[#71717A]">Продавец</th>
                <th className="text-left py-2 px-3 text-[10px] text-[#71717A]">Сумма</th>
                <th className="text-left py-2 px-3 text-[10px] text-[#71717A]">Курс</th>
                <th className="text-left py-2 px-3 text-[10px] text-[#71717A]">Статус</th>
                <th className="text-right py-2 px-3 text-[10px] text-[#71717A]">Действия</th>
              </tr>
            </thead>
            <tbody>
              {offers.map(offer => (
                <tr key={offer.id} className="border-b border-white/5 hover:bg-white/[0.02]">
                  <td className="py-2 px-3 text-white text-xs">{offer.trader_login || offer.trader_nickname}</td>
                  <td className="py-2 px-3">
                    <div className="text-[#10B981] text-xs font-mono">{offer.available_usdt?.toFixed(2)} / {offer.amount_usdt} USDT</div>
                  </td>
                  <td className="py-2 px-3 text-white text-xs">{offer.price_rub} ₽</td>
                  <td className="py-2 px-3">
                    <Badge color={offer.is_active ? "green" : "gray"}>{offer.is_active ? "Активно" : "Неакт."}</Badge>
                  </td>
                  <td className="py-2 px-3 text-right">
                    {offer.is_active && (
                      <Button size="sm" variant="ghost" onClick={() => handleDeactivate(offer.id)} className="text-[#EF4444] h-7 w-7 p-0">
                        <Pause className="w-3.5 h-3.5" />
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default P2POffers;
