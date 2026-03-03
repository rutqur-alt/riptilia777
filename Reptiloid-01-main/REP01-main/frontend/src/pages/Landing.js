import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Wallet, User, CheckCircle, MessageCircle, Store, Circle, DollarSign } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";

export default function Landing() {
  const { isAuthenticated, user } = useAuth();
  const [offers, setOffers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [paymentFilter, setPaymentFilter] = useState("all");
  const [sortBy, setSortBy] = useState("price");
  const [amountMin, setAmountMin] = useState("");
  const [amountMax, setAmountMax] = useState("");

  useEffect(() => {
    fetchOffers();
  }, [paymentFilter, sortBy]);

  const fetchOffers = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (paymentFilter !== "all") params.append("payment_method", paymentFilter);
      params.append("sort_by", sortBy);
      
      const response = await axios.get(`${API}/public/offers?${params.toString()}`);
      let data = response.data;
      
      // Client-side amount filtering
      if (amountMin) {
        data = data.filter(o => o.available_usdt >= parseFloat(amountMin));
      }
      if (amountMax) {
        data = data.filter(o => o.available_usdt <= parseFloat(amountMax));
      }
      
      setOffers(data);
    } catch (error) {
      console.error("Failed to fetch offers:", error);
    } finally {
      setLoading(false);
    }
  };

  const applyAmountFilter = () => {
    fetchOffers();
  };

  const getDashboardLink = () => {
    if (!user) return "/auth";
    switch (user.role) {
      case "trader": return "/trader";
      case "merchant": return "/merchant";
      case "admin": return "/admin";
      default: return "/auth";
    }
  };

  const getRequisiteIcon = (type) => {
    switch (type) {
      case "card": return "💳";
      case "sbp": return "⚡";
      case "qr": return "📱";
      case "sim": return "📞";
      case "cis": return "🌍";
      default: return "💰";
    }
  };

  const getRequisiteDisplayName = (req) => {
    // Показываем ТИП оплаты, а не банк
    if (req.type === "card") return "Банковская карта";
    if (req.type === "sbp") return "СБП";
    if (req.type === "sim") return "Сотовая связь";
    if (req.type === "qr") return "QR-код";
    if (req.type === "cis") return "Перевод СНГ";
    return req.type;
  };

  // Format number with spaces
  const formatNumber = (num) => {
    return num?.toLocaleString("ru-RU") || "0";
  };

  return (
    <div className="min-h-screen bg-[#0A0A0A]">
      {/* Header */}
      <header className="border-b border-white/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4">
          <div className="flex items-center justify-between">
            <Link to="/" className="flex items-center gap-2">
              <img src="/logo.jpg" alt="Reptiloid" className="w-10 h-10 rounded-lg" />
              <span className="text-lg font-semibold text-white font-['Unbounded']">Reptiloid</span>
            </Link>
            
            {/* Navigation */}
            <nav className="hidden md:flex items-center gap-1">
              <Link to="/forum">
                <Button 
                  data-testid="nav-forum-btn"
                  variant="ghost" 
                  className="text-[#A1A1AA] hover:text-white hover:bg-white/5 rounded-lg h-9 px-4 gap-2"
                >
                  <MessageCircle className="w-4 h-4" />
                  Форум
                </Button>
              </Link>
              <Link to="/buy-crypto">
                <Button 
                  data-testid="nav-buy-crypto-btn"
                  variant="ghost" 
                  className="text-[#A1A1AA] hover:text-white hover:bg-white/5 rounded-lg h-9 px-4 gap-2"
                >
                  <DollarSign className="w-4 h-4" />
                  Купить USDT
                </Button>
              </Link>
              <Link to="/marketplace">
                <Button 
                  data-testid="nav-market-btn"
                  variant="ghost" 
                  className="text-[#A1A1AA] hover:text-white hover:bg-white/5 rounded-lg h-9 px-4 gap-2"
                >
                  <Store className="w-4 h-4" />
                  Маркет
                </Button>
              </Link>
            </nav>
            
            <div className="flex items-center gap-3">
              {isAuthenticated ? (
                <Link to={getDashboardLink()}>
                  <Button variant="ghost" className="text-white hover:bg-white/5 rounded-lg h-9 px-4">
                    Личный кабинет
                  </Button>
                </Link>
              ) : (
                <>
                  <Link to="/auth">
                    <Button variant="ghost" className="text-[#A1A1AA] hover:text-white hover:bg-white/5 rounded-lg h-9">
                      Войти
                    </Button>
                  </Link>
                  <Link to="/auth">
                    <Button className="bg-[#7C3AED] hover:bg-[#6D28D9] text-white rounded-lg h-9 px-4">
                      Регистрация
                    </Button>
                  </Link>
                </>
              )}
            </div>
          </div>
          
          {/* Mobile nav */}
          <div className="flex md:hidden items-center gap-2 mt-3 pt-3 border-t border-white/5">
            <Link to="/forum" className="flex-1">
              <Button 
                data-testid="nav-forum-btn-mobile"
                variant="outline" 
                size="sm"
                className="w-full bg-transparent border-white/10 text-[#A1A1AA] hover:text-white hover:bg-white/5 rounded-lg gap-1.5"
              >
                <MessageCircle className="w-3.5 h-3.5" />
                Форум
              </Button>
            </Link>
            <Link to="/buy-crypto" className="flex-1">
              <Button 
                data-testid="nav-buy-crypto-btn-mobile"
                variant="outline" 
                size="sm"
                className="w-full bg-transparent border-white/10 text-[#A1A1AA] hover:text-white hover:bg-white/5 rounded-lg gap-1.5"
              >
                <DollarSign className="w-3.5 h-3.5" />
                Купить USDT
              </Button>
            </Link>
            <Link to="/marketplace" className="flex-1">
              <Button 
                data-testid="nav-market-btn-mobile"
                variant="outline" 
                size="sm"
                className="w-full bg-transparent border-white/10 text-[#A1A1AA] hover:text-white hover:bg-white/5 rounded-lg gap-1.5"
              >
                <Store className="w-3.5 h-3.5" />
                Маркет
              </Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3 mb-6">
          <Select value={paymentFilter} onValueChange={setPaymentFilter}>
            <SelectTrigger className="w-[180px] bg-[#121212] border-white/10 text-white rounded-lg h-9">
              <SelectValue placeholder="Все методы" />
            </SelectTrigger>
            <SelectContent className="bg-[#121212] border-white/10">
              <SelectItem value="all" className="text-white">Все методы</SelectItem>
              <SelectItem value="card" className="text-white">💳 Банковская карта</SelectItem>
              <SelectItem value="sbp" className="text-white">⚡ СБП</SelectItem>
              <SelectItem value="qr" className="text-white">📱 QR-код</SelectItem>
              <SelectItem value="sim" className="text-white">📞 Сотовая связь</SelectItem>
              <SelectItem value="cis" className="text-white">🌍 Перевод СНГ</SelectItem>
            </SelectContent>
          </Select>
          
          <Select value={sortBy} onValueChange={setSortBy}>
            <SelectTrigger className="w-[140px] bg-[#121212] border-white/10 text-white rounded-lg h-9">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-[#121212] border-white/10">
              <SelectItem value="price" className="text-white">По курсу</SelectItem>
              <SelectItem value="amount" className="text-white">По сумме</SelectItem>
            </SelectContent>
          </Select>

          {/* Amount Filter */}
          <div className="flex items-center gap-2">
            <Input
              type="number"
              placeholder="От"
              value={amountMin}
              onChange={(e) => setAmountMin(e.target.value)}
              onBlur={applyAmountFilter}
              className="w-20 bg-[#121212] border-white/10 text-white rounded-lg h-9 text-sm"
            />
            <span className="text-[#52525B]">—</span>
            <Input
              type="number"
              placeholder="До"
              value={amountMax}
              onChange={(e) => setAmountMax(e.target.value)}
              onBlur={applyAmountFilter}
              className="w-20 bg-[#121212] border-white/10 text-white rounded-lg h-9 text-sm"
            />
            <span className="text-xs text-[#52525B]">USDT</span>
          </div>

          <span className="text-sm text-[#52525B] ml-auto">
            {offers.length} объявлений
          </span>
        </div>

        {/* Table Header */}
        <div className="hidden md:grid grid-cols-12 gap-4 px-4 py-2 text-xs text-[#52525B] uppercase tracking-wider">
          <div className="col-span-2">Продавец</div>
          <div className="col-span-2">Курс</div>
          <div className="col-span-2">Доступно</div>
          <div className="col-span-2">Лимиты</div>
          <div className="col-span-2">Оплата</div>
          <div className="col-span-1">Сделок</div>
          <div className="col-span-1"></div>
        </div>

        {/* Offers */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-6 h-6 border-2 border-[#7C3AED] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : offers.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-[#52525B]">Нет объявлений</p>
          </div>
        ) : (
          <div className="space-y-2">
            {offers.map((offer) => {
              const availableRub = (offer.available_usdt || 0) * (offer.price_rub || 0);
              return (
              <div 
                key={offer.id} 
                data-testid={`offer-card-${offer.id}`}
                className="bg-[#121212] border border-white/5 hover:border-white/10 rounded-xl p-4 transition-colors"
              >
                <div className="grid md:grid-cols-12 gap-4 items-center">
                  {/* Trader */}
                  <div className="md:col-span-2 flex items-center gap-3">
                    <div className="relative">
                      <div className="w-9 h-9 rounded-full bg-[#1A1A1A] flex items-center justify-center">
                        <User className="w-4 h-4 text-[#52525B]" />
                      </div>
                      {/* Online indicator */}
                      <div className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-[#121212] ${
                        offer.is_online ? 'bg-[#10B981]' : 'bg-[#52525B]'
                      }`} />
                    </div>
                    <div>
                      <div className="text-white font-medium text-sm" data-testid="trader-display-name">
                        {offer.trader_display_name || offer.trader_login}
                      </div>
                      <div className="flex items-center gap-1 text-xs text-[#52525B]">
                        <CheckCircle className="w-3 h-3 text-[#10B981]" />
                        {offer.success_rate || 100}%
                      </div>
                    </div>
                  </div>

                  {/* Price */}
                  <div className="md:col-span-2">
                    <div className="text-xl font-semibold text-white font-mono">
                      {formatNumber(offer.price_rub)}
                    </div>
                    <div className="text-xs text-[#52525B]">RUB/USDT</div>
                  </div>

                  {/* Available - USDT + RUB */}
                  <div className="md:col-span-2">
                    <div className="text-white font-medium">
                      {offer.available_usdt || offer.amount_usdt} USDT
                    </div>
                    <div className="text-xs text-[#10B981]">
                      ≈ {formatNumber(Math.round(availableRub))} ₽
                    </div>
                  </div>

                  {/* Limits - NEW COLUMN */}
                  <div className="md:col-span-2">
                    <div className="text-[#A1A1AA] text-sm">
                      {offer.min_amount || 1} – {offer.max_amount || offer.amount_usdt}
                    </div>
                    <div className="text-xs text-[#52525B]">USDT</div>
                  </div>

                  {/* Payment - show ALL unique payment types */}
                  <div className="md:col-span-2">
                    <div className="flex flex-wrap gap-1">
                      {(() => {
                        // Get unique payment types from requisites
                        const types = [...new Set(offer.requisites?.map(r => r.type) || [])];
                        return types.map((type, idx) => (
                          <span 
                            key={idx} 
                            className="inline-flex items-center gap-1 px-2 py-1 bg-[#1A1A1A] text-[#A1A1AA] text-xs rounded"
                          >
                            {getRequisiteIcon(type)} {getRequisiteDisplayName({ type })}
                          </span>
                        ));
                      })()}
                    </div>
                  </div>

                  {/* Trades */}
                  <div className="md:col-span-1">
                    <div className="text-white text-sm">{offer.trades_count || 0}</div>
                  </div>

                  {/* Action - hide button for own offers */}
                  <div className="md:col-span-1 flex justify-end">
                    {isAuthenticated && user?.role === "trader" && offer.trader_id === user?.id ? (
                      <span className="text-xs text-[#52525B]">Ваше</span>
                    ) : isAuthenticated && user?.role === "trader" ? (
                      <Link to={`/buy/${offer.id}`}>
                        <Button size="sm" className="bg-[#10B981] hover:bg-[#059669] text-white rounded-lg h-8 px-4">
                          Купить
                        </Button>
                      </Link>
                    ) : (
                      <Link to={`/shop?offer=${offer.id}`}>
                        <Button size="sm" className="bg-[#10B981] hover:bg-[#059669] text-white rounded-lg h-8 px-4">
                          Купить
                        </Button>
                      </Link>
                    )}
                  </div>
                </div>
              </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
