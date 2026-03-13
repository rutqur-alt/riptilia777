import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useAuth, API } from "@/App";
import axios from "axios";
import { ShoppingBag } from "lucide-react";
import PurchaseCard from "./PurchaseCard";

export default function MyMarketPurchases() {
  const { token } = useAuth();
  const [purchases, setPurchases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    fetchPurchases();
  }, []);

  const fetchPurchases = async () => {
    try {
      const response = await axios.get(`${API}/marketplace/my-purchases`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setPurchases(response.data || []);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const toggleExpand = async (id) => {
    const newId = expandedId === id ? null : id;
    setExpandedId(newId);
    // Mark purchase as viewed when expanding
    if (newId) {
      const purchase = purchases.find(p => p.id === id);
      if (purchase && !purchase.viewed) {
        try {
          await axios.post(`${API}/marketplace/purchases/${id}/mark-viewed`, {}, {
            headers: { Authorization: `Bearer ${token}` }
          });
          setPurchases(prev => prev.map(p => p.id === id ? { ...p, viewed: true } : p));
        } catch (e) { console.error(e); }
      }
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success("Скопировано!");
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
      <div>
        <h1 className="text-2xl font-bold text-white font-['Unbounded']">Мои покупки</h1>
        <p className="text-[#71717A]">История заказов с маркетплейса</p>
      </div>

      {purchases.length === 0 ? (
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-12 text-center">
          <ShoppingBag className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
          <p className="text-[#71717A]">Вы ещё ничего не покупали</p>
          <Link to="/marketplace">
            <Button className="mt-4 bg-[#7C3AED] hover:bg-[#6D28D9] rounded-full px-6">
              Перейти в каталог
            </Button>
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {purchases.map((purchase) => (
            <PurchaseCard 
              key={purchase.id} 
              purchase={purchase} 
              expandedId={expandedId}
              toggleExpand={toggleExpand}
              copyToClipboard={copyToClipboard}
              onRefresh={fetchPurchases}
              token={token}
            />
          ))}
        </div>
      )}
    </div>
  );
}
