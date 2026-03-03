import { useState, useEffect } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Store, Package, ShoppingCart, AlertCircle, Shield, Zap, CheckCircle, Clock, Info } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { toast } from "sonner";

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

export default function ProductPage() {
  const { productId } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated, token } = useAuth();
  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(true);
  const [buying, setBuying] = useState(false);
  const [selectedVariant, setSelectedVariant] = useState(null);
  const [purchaseType, setPurchaseType] = useState("instant");

  useEffect(() => {
    fetchProduct();
  }, [productId]);

  const fetchProduct = async () => {
    try {
      const response = await axios.get(`${API}/marketplace/products/${productId}`);
      setProduct(response.data);
      // Select default variant (1 unit at base price)
      setSelectedVariant({ quantity: 1, price: response.data.price });
    } catch (error) {
      toast.error("Товар не найден");
    } finally {
      setLoading(false);
    }
  };

  // Calculate guarantor fee
  const guarantorPercent = product?.guarantor_commission_percent || 3;
  const basePrice = selectedVariant?.price || product?.price || 0;
  const guarantorFee = purchaseType === "guarantor" ? basePrice * (guarantorPercent / 100) : 0;
  const totalPrice = basePrice + guarantorFee;

  const handleBuy = async () => {
    if (!isAuthenticated) {
      toast.error("Войдите, чтобы купить товар");
      navigate("/auth");
      return;
    }
    
    setBuying(true);
    try {
      const params = new URLSearchParams();
      params.append("quantity", selectedVariant.quantity);
      if (selectedVariant.quantity > 1) {
        params.append("variant_quantity", selectedVariant.quantity);
      }
      params.append("purchase_type", purchaseType);
      
      const response = await axios.post(
        `${API}/marketplace/products/${productId}/buy?${params}`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      if (purchaseType === "instant" && response.data.delivered_content) {
        // Handle complex stock items (objects with text, file_url, photo_url)
        const contentItems = Array.isArray(response.data.delivered_content) 
          ? response.data.delivered_content 
          : [response.data.delivered_content];
        
        const contentDisplay = contentItems.map((item, idx) => {
          if (typeof item === 'string') return item;
          if (typeof item === 'object' && item !== null) {
            return item.text || JSON.stringify(item);
          }
          return String(item);
        }).join('\n---\n');
        
        toast.success(
          <div>
            <div className="font-semibold">Товар куплен! ({response.data.quantity} шт.)</div>
            <div className="text-sm mt-2 font-mono bg-black/20 p-3 rounded break-all whitespace-pre-wrap max-h-40 overflow-y-auto">
              {contentDisplay}
            </div>
            <div className="text-xs mt-2 text-blue-300">
              Переход в "Мои покупки"...
            </div>
          </div>,
          { duration: 30000 }
        );
        // Redirect to My Purchases after short delay
        setTimeout(() => {
          navigate("/trader/my-purchases");
        }, 2000);
      } else if (purchaseType === "guarantor") {
        toast.success(
          <div>
            <div className="font-semibold flex items-center gap-2">
              <Shield className="w-4 h-4" />
              Заказ оформлен через гаранта!
            </div>
            <div className="text-sm mt-2 text-gray-300">
              {response.data.message}
            </div>
            <div className="text-xs mt-2 text-gray-400">
              Автозавершение: {new Date(response.data.auto_complete_at).toLocaleDateString("ru-RU")}
            </div>
          </div>,
          { duration: 15000 }
        );
        navigate("/trader/my-purchases");
      } else {
        toast.success("Покупка оформлена!");
        setTimeout(() => {
          navigate("/trader/my-purchases");
        }, 2000);
      }
      
      fetchProduct();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка покупки");
    } finally {
      setBuying(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-[#10B981] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!product) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
        <div className="text-center">
          <Package className="w-16 h-16 text-[#52525B] mx-auto mb-4" />
          <p className="text-[#71717A]">Товар не найден</p>
          <Link to="/marketplace">
            <Button className="mt-4 bg-[#10B981] hover:bg-[#059669]" title="Вернуться назад">Назад</Button>
          </Link>
        </div>
      </div>
    );
  }

  // Build price options
  const priceOptions = [
    { quantity: 1, price: product.price, label: "1 шт." }
  ];
  
  if (product.price_variants && product.price_variants.length > 0) {
    product.price_variants.forEach(v => {
      if (v.quantity !== 1) {
        const discount = Math.round((1 - v.price / (product.price * v.quantity)) * 100);
        priceOptions.push({
          quantity: v.quantity,
          price: v.price,
          label: v.label || `${v.quantity} шт.`,
          discount: discount > 0 ? discount : null
        });
      }
    });
  }

  // Stock info
  const stockCount = product.stock_count || 0;
  const available = stockCount - (product.reserved_count || 0);

  return (
    <div className="min-h-screen bg-[#0A0A0A]">
      {/* Header */}
      <header className="border-b border-white/5">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-4">
          <div className="flex items-center gap-4">
            <Link to="/marketplace">
              <Button variant="ghost" size="icon" className="text-[#A1A1AA] hover:text-white hover:bg-white/5">
                <ArrowLeft className="w-5 h-5" />
              </Button>
            </Link>
            <span className="text-lg font-semibold text-white truncate">{product.name}</span>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8">
        <div className="grid md:grid-cols-2 gap-8">
          {/* Image */}
          <div className="aspect-square bg-[#121212] rounded-2xl border border-white/5 overflow-hidden">
            {product.image_url ? (
              <img src={product.image_url} alt="" className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <Package className="w-24 h-24 text-[#52525B]" />
              </div>
            )}
          </div>
          
          {/* Info */}
          <div>
            {/* Shop */}
            {product.shop && (
              <Link 
                to={`/marketplace/shop/${product.shop.id}`}
                className="inline-flex items-center gap-2 mb-4 hover:opacity-80 transition-opacity"
              >
                <div className="w-8 h-8 rounded-lg bg-[#121212] flex items-center justify-center overflow-hidden">
                  {product.shop.logo ? (
                    <img src={product.shop.logo} alt="" className="w-full h-full object-cover" />
                  ) : (
                    <Store className="w-4 h-4 text-[#10B981]" />
                  )}
                </div>
                <div>
                  <div className="text-sm text-white font-medium">{product.shop.name}</div>
                  <div className="text-xs text-[#52525B]">@{product.shop.nickname}</div>
                </div>
              </Link>
            )}
            
            {/* Title & Category */}
            <h1 className="text-2xl font-bold text-white mb-2">{product.name}</h1>
            <div className="flex items-center gap-3 mb-4">
              <span className="px-3 py-1 bg-[#121212] border border-white/10 rounded-lg text-sm text-[#A1A1AA]">
                {getCategoryLabel(product.category)}
              </span>
              <span className={`text-sm ${available > 0 ? "text-[#10B981]" : "text-[#EF4444]"}`}>
                {available > 0 ? `В наличии: ${available} шт.` : "Нет в наличии"}
              </span>
            </div>
            
            {/* Price Options */}
            <div className="bg-[#121212] border border-white/5 rounded-xl p-4 mb-4">
              <div className="text-sm text-[#71717A] mb-3">Выберите вариант</div>
              <div className="space-y-2">
                {priceOptions.map((option, index) => (
                  <button
                    key={index}
                    onClick={() => setSelectedVariant(option)}
                    disabled={available < option.quantity}
                    className={`w-full flex items-center justify-between p-3 rounded-lg border transition-colors ${
                      selectedVariant?.quantity === option.quantity
                        ? "border-[#10B981] bg-[#10B981]/10"
                        : available < option.quantity
                        ? "border-white/5 opacity-50 cursor-not-allowed"
                        : "border-white/10 hover:border-white/20"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                        selectedVariant?.quantity === option.quantity
                          ? "border-[#10B981]"
                          : "border-white/30"
                      }`}>
                        {selectedVariant?.quantity === option.quantity && (
                          <div className="w-2 h-2 rounded-full bg-[#10B981]" />
                        )}
                      </div>
                      <span className="text-white">{option.label}</span>
                      {option.discount && (
                        <span className="px-2 py-0.5 bg-[#F59E0B]/10 text-[#F59E0B] text-xs rounded">
                          -{option.discount}%
                        </span>
                      )}
                    </div>
                    <div className="text-right">
                      <span className="text-[#10B981] font-semibold">{option.price} {product.currency}</span>
                      {option.quantity > 1 && (
                        <div className="text-xs text-[#52525B]">
                          {(option.price / option.quantity).toFixed(2)} за шт.
                        </div>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            </div>
            
            {/* Purchase Type */}
            <div className="bg-[#121212] border border-white/5 rounded-xl p-4 mb-4">
              <div className="text-sm text-[#71717A] mb-3">Способ покупки</div>
              <div className="space-y-2">
                <button
                  onClick={() => setPurchaseType("instant")}
                  className={`w-full flex items-center gap-3 p-3 rounded-lg border transition-colors ${
                    purchaseType === "instant"
                      ? "border-[#10B981] bg-[#10B981]/10"
                      : "border-white/10 hover:border-white/20"
                  }`}
                 title="Купить USDT">
                  <Zap className={`w-5 h-5 ${purchaseType === "instant" ? "text-[#10B981]" : "text-[#71717A]"}`} />
                  <div className="text-left flex-1">
                    <div className="text-white font-medium">Купить напрямую</div>
                    <div className="text-xs text-[#52525B]">Мгновенная выдача после оплаты</div>
                  </div>
                  <div className="text-right">
                    <div className="text-[#10B981] font-semibold">{basePrice.toFixed(2)} USDT</div>
                  </div>
                  {purchaseType === "instant" && <CheckCircle className="w-5 h-5 text-[#10B981]" />}
                </button>
                
                <button
                  onClick={() => setPurchaseType("guarantor")}
                  className={`w-full flex items-center gap-3 p-3 rounded-lg border transition-colors ${
                    purchaseType === "guarantor"
                      ? "border-[#7C3AED] bg-[#7C3AED]/10"
                      : "border-white/10 hover:border-white/20"
                  }`}
                 title="Купить USDT">
                  <Shield className={`w-5 h-5 ${purchaseType === "guarantor" ? "text-[#7C3AED]" : "text-[#71717A]"}`} />
                  <div className="text-left flex-1">
                    <div className="text-white font-medium">Купить с защитой гаранта</div>
                    <div className="text-xs text-[#52525B]">Безопасная сделка · Комиссия {guarantorPercent}%</div>
                  </div>
                  <div className="text-right">
                    <div className="text-[#7C3AED] font-semibold">{(basePrice + basePrice * guarantorPercent / 100).toFixed(2)} USDT</div>
                    <div className="text-xs text-[#52525B]">+{guarantorFee.toFixed(2)} гарант</div>
                  </div>
                  {purchaseType === "guarantor" && <CheckCircle className="w-5 h-5 text-[#7C3AED]" />}
                </button>
              </div>
              
              {/* Guarantor info */}
              {purchaseType === "guarantor" && (
                <div className="mt-3 p-3 bg-[#7C3AED]/5 border border-[#7C3AED]/20 rounded-lg">
                  <div className="flex items-start gap-2 text-xs text-[#A78BFA]">
                    <Info className="w-4 h-4 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium mb-1">Как работает защита гаранта:</p>
                      <ul className="space-y-1 text-[#8B5CF6]">
                        <li>• Деньги блокируются до подтверждения получения</li>
                        <li>• У вас 3 дня на проверку товара</li>
                        <li>• При проблеме — откройте спор</li>
                        <li>• Администратор решит спор справедливо</li>
                      </ul>
                    </div>
                  </div>
                </div>
              )}
            </div>
            
            {/* Description */}
            {product.description && (
              <div className="mb-6">
                <div className="text-sm text-[#71717A] mb-2">Описание</div>
                <p className="text-[#E4E4E7] whitespace-pre-wrap text-sm">{product.description}</p>
              </div>
            )}
            
            {/* Price Summary */}
            {purchaseType === "guarantor" && (
              <div className="bg-[#0A0A0A] border border-white/5 rounded-xl p-4 mb-4">
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-[#71717A]">Цена товара</span>
                  <span className="text-white">{basePrice.toFixed(2)} USDT</span>
                </div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-[#71717A]">Комиссия гаранта ({guarantorPercent}%)</span>
                  <span className="text-[#7C3AED]">+{guarantorFee.toFixed(2)} USDT</span>
                </div>
                <div className="border-t border-white/5 pt-2 mt-2 flex justify-between">
                  <span className="text-white font-medium">Итого к оплате</span>
                  <span className="text-[#10B981] font-bold">{totalPrice.toFixed(2)} USDT</span>
                </div>
              </div>
            )}
            
            {/* Buy button */}
            <Button
              onClick={handleBuy}
              disabled={buying || available < (selectedVariant?.quantity || 1)}
              className={`w-full rounded-xl h-12 text-lg ${
                purchaseType === "guarantor"
                  ? "bg-[#7C3AED] hover:bg-[#6D28D9]"
                  : "bg-[#10B981] hover:bg-[#059669]"
              } text-white`}
             title="Купить USDT">
              {buying ? (
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  {purchaseType === "guarantor" ? (
                    <Shield className="w-5 h-5 mr-2" />
                  ) : (
                    <ShoppingCart className="w-5 h-5 mr-2" />
                  )}
                  Купить за {totalPrice.toFixed(2)} {product.currency}
                </>
              )}
            </Button>
            
            {/* Info */}
            <div className="mt-4 flex items-start gap-2 text-xs text-[#52525B]">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <p>
                {purchaseType === "instant" 
                  ? "После покупки товар будет выдан автоматически. Отмена невозможна."
                  : "Товар будет зарезервирован. Выдача после вашего подтверждения получения."
                }
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
