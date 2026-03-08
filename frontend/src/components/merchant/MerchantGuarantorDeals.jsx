import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import axios from "axios";
import { Shield } from "lucide-react";
import { useAuth, API } from "@/App";

export default function MyGuarantorDeals() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [deals, setDeals] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDeals();
  }, []);

  const fetchDeals = async () => {
    try {
      const response = await axios.get(`${API}/guarantor/deals`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setDeals(response.data || []);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    const styles = {
      pending_counterparty: "bg-[#F59E0B]/10 text-[#F59E0B]",
      pending_payment: "bg-[#3B82F6]/10 text-[#3B82F6]",
      funded: "bg-[#10B981]/10 text-[#10B981]",
      completed: "bg-[#10B981]/10 text-[#10B981]",
      disputed: "bg-[#EF4444]/10 text-[#EF4444]",
      cancelled: "bg-[#71717A]/10 text-[#71717A]"
    };
    const labels = {
      pending_counterparty: "Ожидает участника",
      pending_payment: "Ожидает оплаты",
      funded: "Средства внесены",
      completed: "Завершена",
      disputed: "Спор",
      cancelled: "Отменена"
    };
    return (
      <span className={`px-2 py-1 text-xs rounded-full font-medium ${styles[status] || styles.pending_counterparty}`}>
        {labels[status] || status}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-[#7C3AED] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white font-['Unbounded']">Мои гарант-сделки</h1>
          <p className="text-[#71717A]">Сделки с гарантом как покупатель или продавец</p>
        </div>
      </div>

      {deals.length === 0 ? (
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-12 text-center">
          <Shield className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
          <p className="text-[#71717A]">У вас пока нет гарант-сделок</p>
          <p className="text-sm text-[#52525B] mt-1">Создайте новую сделку или присоединитесь по ссылке</p>
        </div>
      ) : (
        <div className="space-y-3">
          {deals.map((deal) => (
            <Link key={deal.id} to={`/merchant/guarantor-chat/${deal.id}`}>
              <div className="bg-[#121212] border border-white/5 hover:border-[#7C3AED]/30 rounded-xl p-5 transition-colors">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="text-white font-semibold">{deal.title}</div>
                    <div className="text-sm text-[#71717A]">
                      {deal.creator_role === 'buyer' ? 'Вы покупатель' : 'Вы продавец'}
                      {deal.counterparty_nickname && ` • с @${deal.counterparty_nickname}`}
                    </div>
                  </div>
                  {getStatusBadge(deal.status)}
                </div>
                <div className="flex items-center justify-between">
                  <div className="text-sm text-[#52525B]">
                    {new Date(deal.created_at).toLocaleDateString("ru-RU")}
                  </div>
                  <div className="text-lg font-bold text-[#10B981] font-['JetBrains_Mono']">
                    {deal.amount} {deal.currency}
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

