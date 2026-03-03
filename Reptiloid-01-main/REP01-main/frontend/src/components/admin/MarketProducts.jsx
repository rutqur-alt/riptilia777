import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Package, RefreshCw, Eye, Trash2 } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { Badge, LoadingSpinner, EmptyState, PageHeader } from "@/components/admin/SharedComponents";

export function MarketProducts() {
  const { token } = useAuth();
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => { fetchProducts(); }, []);

  const fetchProducts = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/admin/products`, { headers: { Authorization: `Bearer ${token}` } });
      setProducts(response.data || []);
    } catch (error) {
      console.error("Error fetching products:", error);
      toast.error("Ошибка загрузки товаров");
    } finally {
      setLoading(false);
    }
  };

  const handleToggleProduct = async (productId, isActive) => {
    try {
      await axios.post(`${API}/admin/products/${productId}/toggle`, { is_active: !isActive },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(isActive ? "Товар скрыт" : "Товар активирован");
      fetchProducts();
    } catch (error) {
      toast.error("Ошибка");
    }
  };

  const handleDeleteProduct = async (productId, productName) => {
    if (!window.confirm(`Удалить товар "${productName}"?`)) return;
    try {
      await axios.delete(`${API}/admin/products/${productId}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success("Товар удалён");
      fetchProducts();
    } catch (error) {
      toast.error("Ошибка");
    }
  };

  const filteredProducts = products.filter(p => 
    (p.title?.toLowerCase() || "").includes(search.toLowerCase()) ||
    (p.shop_name?.toLowerCase() || "").includes(search.toLowerCase())
  );

  return (
    <div className="space-y-4" data-testid="market-products">
      <PageHeader title="Товары" subtitle="Все товары маркетплейса" />
      
      <div className="flex gap-2">
        <Input
          placeholder="Поиск товаров..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs bg-[#121212] border-white/10 text-white h-8"
        />
        <Button variant="ghost" size="sm" onClick={fetchProducts} className="h-8">
          <RefreshCw className="w-4 h-4" />
        </Button>
      </div>

      {loading ? <LoadingSpinner /> : filteredProducts.length === 0 ? (
        <EmptyState icon={Package} text="Нет товаров" />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {filteredProducts.map(product => (
            <div key={product.id} className={`bg-[#121212] border rounded-xl p-3 ${!product.is_active ? 'border-[#EF4444]/30 opacity-60' : 'border-white/5'}`}>
              <div className="flex items-start gap-3">
                {product.image_url ? (
                  <img src={product.image_url} alt="" className="w-16 h-16 object-cover rounded-lg" />
                ) : (
                  <div className="w-16 h-16 bg-[#0A0A0A] rounded-lg flex items-center justify-center">
                    <Package className="w-6 h-6 text-[#52525B]" />
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-white font-medium text-sm truncate">{product.title}</span>
                    {!product.is_active && <Badge color="red">Скрыт</Badge>}
                  </div>
                  <div className="text-[#71717A] text-xs truncate">{product.shop_name || "Магазин"}</div>
                  <div className="text-[#10B981] font-semibold text-sm mt-1">{product.price} USDT</div>
                </div>
              </div>
              <div className="flex justify-end gap-2 mt-2">
                <Button size="sm" variant="ghost" onClick={() => handleToggleProduct(product.id, product.is_active)}
                  className={`h-7 text-xs ${product.is_active ? 'text-[#F59E0B]' : 'text-[#10B981]'}`}>
                  {product.is_active ? <Eye className="w-3 h-3 mr-1" /> : <Eye className="w-3 h-3 mr-1" />}
                  {product.is_active ? "Скрыть" : "Показать"}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => handleDeleteProduct(product.id, product.title)}
                  className="text-[#EF4444] h-7 text-xs">
                  <Trash2 className="w-3 h-3 mr-1" /> Удалить
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default MarketProducts;
