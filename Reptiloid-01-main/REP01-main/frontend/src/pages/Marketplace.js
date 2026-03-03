import { useState, useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Wallet, ArrowLeft, Search, Store, Package, Filter, ShoppingCart, Star, ChevronRight } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";

// Category mapping
const CATEGORIES = {
  accounts: "Аккаунты",
  software: "Софт",
  databases: "Базы данных",
  tools: "Инструменты",
  guides: "Гайды и схемы",
  keys: "Ключи",
  financial: "Финансовое",
  templates: "Шаблоны",
  other: "Другое"
};

const getCategoryLabel = (category) => CATEGORIES[category] || category;

export default function Marketplace() {
  const { isAuthenticated } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [view, setView] = useState(searchParams.get("view") || "shops"); // shops or products
  const [shops, setShops] = useState([]);
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  
  const [filters, setFilters] = useState({
    search: searchParams.get("q") || "",
    category: searchParams.get("category") || "",
    sort: searchParams.get("sort") || "newest"
  });

  useEffect(() => {
    fetchCategories();
    if (view === "shops") {
      fetchShops();
    } else {
      fetchProducts();
    }
  }, [view, filters]);

  const fetchCategories = async () => {
    try {
      const response = await axios.get(`${API}/marketplace/categories`);
      setCategories(response.data);
    } catch (error) {
      console.error("Failed to fetch categories:", error);
    }
  };

  const fetchShops = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.search) params.append("search", filters.search);
      if (filters.category) params.append("category", filters.category);
      
      const response = await axios.get(`${API}/marketplace/shops?${params}`);
      setShops(response.data);
    } catch (error) {
      console.error("Failed to fetch shops:", error);
    } finally {
      setLoading(false);
    }
  };

  const fetchProducts = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.search) params.append("search", filters.search);
      if (filters.category) params.append("category", filters.category);
      if (filters.sort) params.append("sort", filters.sort);
      
      const response = await axios.get(`${API}/marketplace/products?${params}`);
      setProducts(response.data);
    } catch (error) {
      console.error("Failed to fetch products:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e) => {
    e.preventDefault();
    const newParams = new URLSearchParams(searchParams);
    if (filters.search) {
      newParams.set("q", filters.search);
    } else {
      newParams.delete("q");
    }
    setSearchParams(newParams);
  };

  return (
    <div className="min-h-screen bg-[#0A0A0A]">
      {/* Header */}
      <header className="border-b border-white/5 sticky top-0 bg-[#0A0A0A]/95 backdrop-blur z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link to="/">
                <Button variant="ghost" size="icon" className="text-[#A1A1AA] hover:text-white hover:bg-white/5">
                  <ArrowLeft className="w-5 h-5" />
                </Button>
              </Link>
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-[#10B981] flex items-center justify-center">
                  <Store className="w-4 h-4 text-white" />
                </div>
                <span className="text-lg font-semibold text-white">Маркетплейс</span>
              </div>
            </div>
            
            {isAuthenticated && (
              <Link to="/trader/my-purchases">
                <Button variant="ghost" className="text-[#A1A1AA] hover:text-white hover:bg-white/5 gap-2">
                  <ShoppingCart className="w-4 h-4" />
                  Мои покупки
                </Button>
              </Link>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
        {/* Filters */}
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-4 mb-6">
          <form onSubmit={handleSearch} className="flex flex-col md:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#52525B]" />
              <Input
                value={filters.search}
                onChange={(e) => setFilters({ ...filters, search: e.target.value })}
                placeholder="Поиск магазинов и товаров..."
                className="bg-[#0A0A0A] border-white/10 text-white pl-10 h-11 rounded-xl"
              />
            </div>
            
            <div className="flex gap-3">
              <Select 
                value={filters.category} 
                onValueChange={(v) => setFilters({ ...filters, category: v === "all" ? "" : v })}
              >
                <SelectTrigger className="w-[180px] bg-[#0A0A0A] border-white/10 text-white h-11 rounded-xl">
                  <SelectValue placeholder="Категория" />
                </SelectTrigger>
                <SelectContent className="bg-[#121212] border-white/10">
                  <SelectItem value="all" className="text-white">Все категории</SelectItem>
                  <SelectItem value="accounts" className="text-white">Аккаунты</SelectItem>
                  <SelectItem value="software" className="text-white">Софт</SelectItem>
                  <SelectItem value="databases" className="text-white">Базы данных</SelectItem>
                  <SelectItem value="tools" className="text-white">Инструменты</SelectItem>
                  <SelectItem value="guides" className="text-white">Гайды и схемы</SelectItem>
                  <SelectItem value="keys" className="text-white">Ключи</SelectItem>
                  <SelectItem value="financial" className="text-white">Финансовое</SelectItem>
                  <SelectItem value="templates" className="text-white">Шаблоны</SelectItem>
                  <SelectItem value="other" className="text-white">Другое</SelectItem>
                </SelectContent>
              </Select>
              
              {view === "products" && (
                <Select 
                  value={filters.sort} 
                  onValueChange={(v) => setFilters({ ...filters, sort: v })}
                >
                  <SelectTrigger className="w-[140px] bg-[#0A0A0A] border-white/10 text-white h-11 rounded-xl">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-[#121212] border-white/10">
                    <SelectItem value="newest" className="text-white">Новые</SelectItem>
                    <SelectItem value="price_asc" className="text-white">Дешевле</SelectItem>
                    <SelectItem value="price_desc" className="text-white">Дороже</SelectItem>
                  </SelectContent>
                </Select>
              )}
              
              <Button type="submit" className="bg-[#10B981] hover:bg-[#059669] text-white rounded-xl h-11 px-6">
                <Search className="w-4 h-4" />
              </Button>
            </div>
          </form>
        </div>

        {/* View Toggle */}
        <div className="flex gap-2 mb-6">
          <Button
            variant={view === "shops" ? "default" : "outline"}
            onClick={() => setView("shops")}
            className={view === "shops" 
              ? "bg-[#10B981] hover:bg-[#059669] text-white rounded-xl" 
              : "bg-transparent border-white/10 text-[#A1A1AA] hover:text-white rounded-xl"
            }
          >
            <Store className="w-4 h-4 mr-2" />
            Магазины
          </Button>
          <Button
            variant={view === "products" ? "default" : "outline"}
            onClick={() => setView("products")}
            className={view === "products" 
              ? "bg-[#10B981] hover:bg-[#059669] text-white rounded-xl" 
              : "bg-transparent border-white/10 text-[#A1A1AA] hover:text-white rounded-xl"
            }
          >
            <Package className="w-4 h-4 mr-2" />
            Товары
          </Button>
        </div>

        {/* Content */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 border-2 border-[#10B981] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : view === "shops" ? (
          /* Shops Grid */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {shops.length === 0 ? (
              <div className="col-span-full text-center py-20">
                <Store className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
                <p className="text-[#71717A]">Магазины не найдены</p>
              </div>
            ) : shops.map(shop => (
              <Link 
                key={shop.id} 
                to={`/marketplace/shop/${shop.id}`}
                className="bg-[#121212] border border-white/5 rounded-2xl overflow-hidden hover:border-[#10B981]/30 transition-colors group"
              >
                {/* Banner */}
                <div className="h-24 bg-gradient-to-r from-[#10B981]/20 to-[#059669]/10 relative">
                  {shop.banner && (
                    <img src={shop.banner} alt="" className="w-full h-full object-cover" />
                  )}
                </div>
                
                {/* Info */}
                <div className="p-4 -mt-8 relative">
                  <div className="w-16 h-16 rounded-xl bg-[#1A1A1A] border-4 border-[#121212] flex items-center justify-center mb-3 overflow-hidden">
                    {shop.logo ? (
                      <img src={shop.logo} alt="" className="w-full h-full object-cover" />
                    ) : (
                      <Store className="w-8 h-8 text-[#10B981]" />
                    )}
                  </div>
                  
                  <h3 className="text-white font-semibold group-hover:text-[#10B981] transition-colors">{shop.name}</h3>
                  
                  {shop.description && (
                    <p className="text-[#71717A] text-sm mt-2 line-clamp-2">{shop.description}</p>
                  )}
                  
                  <div className="flex items-center justify-between mt-4">
                    <span className="text-xs text-[#52525B]">
                      {shop.product_count} товаров
                    </span>
                    <ChevronRight className="w-4 h-4 text-[#52525B] group-hover:text-[#10B981] transition-colors" />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          /* Products Grid */
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {products.length === 0 ? (
              <div className="col-span-full text-center py-20">
                <Package className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
                <p className="text-[#71717A]">Товары не найдены</p>
              </div>
            ) : products.map(product => (
              <Link 
                key={product.id} 
                to={`/marketplace/product/${product.id}`}
                className="bg-[#121212] border border-white/5 rounded-xl overflow-hidden hover:border-[#10B981]/30 transition-colors group"
              >
                {/* Image */}
                <div className="aspect-square bg-[#1A1A1A] relative">
                  {product.image_url ? (
                    <img src={product.image_url} alt="" className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Package className="w-12 h-12 text-[#52525B]" />
                    </div>
                  )}
                  <div className="absolute top-2 right-2 bg-[#10B981] text-white text-xs font-medium px-2 py-1 rounded">
                    {product.price} {product.currency}
                  </div>
                </div>
                
                {/* Info */}
                <div className="p-3">
                  <h3 className="text-white text-sm font-medium line-clamp-2 group-hover:text-[#10B981] transition-colors">
                    {product.name}
                  </h3>
                  <p className="text-[#52525B] text-xs mt-1">{product.shop_name}</p>
                  
                  <div className="flex items-center justify-between mt-2">
                    <span className="text-[10px] text-[#52525B] bg-[#0A0A0A] px-2 py-0.5 rounded">
                      {getCategoryLabel(product.category)}
                    </span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
