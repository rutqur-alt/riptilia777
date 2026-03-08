import { useState, useEffect } from "react";
import axios from "axios";
import { useAuth, API } from "@/App";
import MerchantShopApplication from "./MerchantShopApplication";
import MerchantShopManagement from "./MerchantShopManagement";
import { Loader } from "lucide-react";

export default function MerchantShop() {
  const { token, user } = useAuth();
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStatus();
  }, []);

  const fetchStatus = async () => {
    try {
      const response = await axios.get(`${API}/shop/my-application`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setStatus(response.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="flex justify-center py-20"><Loader className="w-8 h-8 animate-spin text-[#71717A]" /></div>;
  }

  if (status?.has_shop) {
    return <MerchantShopManagement />;
  }

  return <MerchantShopApplication onSuccess={fetchStatus} />;
}

