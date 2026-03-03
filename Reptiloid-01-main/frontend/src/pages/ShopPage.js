import { useState, useEffect } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Wallet, ArrowLeft, Store, Package, ShoppingCart, MessageCircle, Send, X } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { toast } from "sonner";

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
  games: "Игры",
  subscriptions: "Подписки",
  services: "Услуги",
  other: "Другое"
};
const getCategoryLabel = (cat) => CATEGORIES[cat] || cat;

export default function ShopPage() {
  const { shopId } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated, token, user } = useAuth();
  const [shop, setShop] = useState(null);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showMessageModal, setShowMessageModal] = useState(false);
  const [message, setMessage] = useState("");
  const [sendingMessage, setSendingMessage] = useState(false);

  useEffect(() => {
    fetchShopData();
  }, [shopId]);

  const fetchShopData = async () => {
    try {
      const response = await axios.get(`${API}/marketplace/shops/${shopId}`);
      setShop(response.data.shop);
      setProducts(response.data.products);
    } catch (error) {
      toast.error("Магазин не найден");
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async () => {
    if (!isAuthenticated) {
      toast.error("Войдите, чтобы написать в магазин");
      return;
    }
    if (!message.trim()) return;
    
    setSendingMessage(true);
    try {
      await axios.post(
        `${API}/shop/${shopId}/messages`,
        { message },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success("Сообщение отправлено! Ответ появится в разделе Сообщения магазинов");
      setMessage("");
      setShowMessageModal(false);
      // Redirect to ShopChats - trader dashboard has this route
      if (user?.role === "trader") {
        navigate("/trader/shop-chats");
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка отправки");
    } finally {
      setSendingMessage(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-[#10B981] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!shop) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
        <div className="text-center">
          <Store className="w-16 h-16 text-[#52525B] mx-auto mb-4" />
          <p className="text-[#71717A]">Магазин не найден</p>
          <Link to="/marketplace">
            <Button className="mt-4 bg-[#10B981] hover:bg-[#059669]" title="Вернуться назад">Назад</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0A0A0A]">
      {/* Header */}
      <header className="border-b border-white/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4">
          <div className="flex items-center gap-4">
            <Link to="/marketplace">
              <Button variant="ghost" size="icon" className="text-[#A1A1AA] hover:text-white hover:bg-white/5">
                <ArrowLeft className="w-5 h-5" />
              </Button>
            </Link>
            <span className="text-lg font-semibold text-white">Магазин</span>
          </div>
        </div>
      </header>

      {/* Shop Banner & Info */}
      <div className="bg-gradient-to-r from-[#10B981]/20 to-[#059669]/10 h-32 relative">
        {shop.banner && (
          <img src={shop.banner} alt="" className="w-full h-full object-cover" />
        )}
      </div>
      
      <div className="max-w-7xl mx-auto px-4 sm:px-6 -mt-12 relative z-10">
        <div className="flex items-end justify-between gap-4 mb-6">
          <div className="flex items-end gap-4">
            <div className="w-24 h-24 rounded-2xl bg-[#121212] border-4 border-[#0A0A0A] flex items-center justify-center overflow-hidden">
              {shop.logo ? (
                <img src={shop.logo} alt="" className="w-full h-full object-cover" />
              ) : (
                <Store className="w-10 h-10 text-[#10B981]" />
              )}
            </div>
            <div className="pb-2">
              <h1 className="text-2xl font-bold text-white">{shop.name}</h1>
              <p className="text-[#71717A] text-sm">{products.length} товаров</p>
            </div>
          </div>
          
          {/* Contact Button */}
          <Button
            onClick={() => setShowMessageModal(true)}
            className="bg-[#7C3AED] hover:bg-[#6D28D9] text-white rounded-xl gap-2 mb-2"
           title="Написать сообщение">
            <MessageCircle className="w-4 h-4" />
            Написать
          </Button>
        </div>
        
        {shop.description && (
          <p className="text-[#A1A1AA] mb-6 max-w-2xl">{shop.description}</p>
        )}

        {/* Categories */}
        {shop.categories && shop.categories.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-8">
            {shop.categories.map(cat => (
              <span key={cat} className="px-3 py-1 bg-[#121212] border border-white/10 rounded-lg text-sm text-[#A1A1AA]">
                {getCategoryLabel(cat)}
              </span>
            ))}
          </div>
        )}

        {/* Products */}
        <h2 className="text-lg font-semibold text-white mb-4">Товары ({products.length})</h2>
        
        {products.length === 0 ? (
          <div className="text-center py-20 bg-[#121212] rounded-2xl border border-white/5">
            <Package className="w-12 h-12 text-[#52525B] mx-auto mb-4" />
            <p className="text-[#71717A]">В магазине пока нет товаров</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 pb-8">
            {products.map(product => (
              <Link 
                key={product.id}
                to={`/marketplace/product/${product.id}`}
                className="bg-[#121212] border border-white/5 rounded-xl overflow-hidden group hover:border-[#10B981]/30 transition-colors"
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
                  <h3 className="text-white text-sm font-medium line-clamp-2 group-hover:text-[#10B981] transition-colors">{product.name}</h3>
                  <p className="text-[#52525B] text-xs mt-1 line-clamp-2">{product.description}</p>
                  
                  <div className="flex items-center justify-between mt-3">
                    <span className="text-[10px] text-[#52525B]">{getCategoryLabel(product.category)}</span>
                    <span className="text-xs text-[#71717A]">
                      {(product.stock_count || product.available || 0) > 0 ? `${product.stock_count || product.available} шт.` : 'Нет в наличии'}
                    </span>
                  </div>
                  
                  <div className="mt-3 bg-[#10B981]/10 text-[#10B981] rounded-lg h-9 text-sm flex items-center justify-center font-medium group-hover:bg-[#10B981] group-hover:text-white transition-colors">
                    <ShoppingCart className="w-4 h-4 mr-1" />
                    Подробнее
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Message Modal */}
      {showMessageModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-[#121212] border border-white/10 rounded-2xl p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">Написать в магазин</h3>
              <button
                onClick={() => setShowMessageModal(false)}
                className="text-[#71717A] hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <p className="text-[#71717A] text-sm mb-4">
              Сообщение для <span className="text-white">{shop.name}</span>
            </p>
            
            <Textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Напишите ваше сообщение..."
              rows={4}
              className="bg-[#0A0A0A] border-white/10 text-white rounded-xl resize-none mb-4"
            />
            
            <div className="flex gap-3">
              <Button
                variant="outline"
                onClick={() => setShowMessageModal(false)}
                className="flex-1 bg-transparent border-white/10 text-white rounded-xl"
               title="Отменить действие">
                Отмена
              </Button>
              <Button
                onClick={handleSendMessage}
                disabled={sendingMessage || !message.trim()}
                className="flex-1 bg-[#7C3AED] hover:bg-[#6D28D9] text-white rounded-xl gap-2"
               title="Отправить сообщение">
                {sendingMessage ? (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    Отправить
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
