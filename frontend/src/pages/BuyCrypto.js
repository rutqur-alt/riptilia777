import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import { useAuth, API } from "@/App";
import axios from "axios";
import { 
  DollarSign, ArrowLeft, CheckCircle, AlertTriangle, 
  User, ArrowRight, Info, FileText
} from "lucide-react";

export default function BuyCrypto() {
  const { isAuthenticated, user, token } = useAuth();
  const navigate = useNavigate();
  const [offers, setOffers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [userStats, setUserStats] = useState(null);
  const [selectedOffer, setSelectedOffer] = useState(null);
  const [showRequirementDialog, setShowRequirementDialog] = useState(false);
  const [showRulesDialog, setShowRulesDialog] = useState(false);
  const [rulesText, setRulesText] = useState("");
  const [buyingOfferId, setBuyingOfferId] = useState(null);

  const MIN_TRADES_REQUIRED = 20;
  
  // Check if user is blocked from buying (merchant or admin)
  const isBlockedFromBuying = () => {
    if (!user) return false;
    if (user.role === "merchant") return true;
    const adminRoles = ["admin", "owner", "mod_p2p", "mod_marketplace", "mod_support", "super_admin"];
    if (adminRoles.includes(user.admin_role) || adminRoles.includes(user.role)) return true;
    return false;
  };

  useEffect(() => {
    fetchOffers();
    fetchRules();
    if (isAuthenticated && user?.role === "trader") {
      fetchUserStats();
    }
  }, [isAuthenticated, user, token]);

  const fetchOffers = async () => {
    try {
      const response = await axios.get(`${API}/crypto/sell-offers`);
      setOffers(response.data || []);
    } catch (error) {
      console.error("Error fetching offers:", error);
    } finally {
      setLoading(false);
    }
  };

  const fetchRules = async () => {
    try {
      const response = await axios.get(`${API}/payout-settings/public`);
      setRulesText(response.data.rules || "");
    } catch (error) {
      console.error("Error fetching rules:", error);
    }
  };

  const fetchUserStats = async () => {
    try {
      const response = await axios.get(`${API}/traders/stats`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setUserStats(response.data);
    } catch (error) {
      console.error("Error fetching stats:", error);
    }
  };

  const canBuyCrypto = () => {
    if (!isAuthenticated) return false;
    if (isBlockedFromBuying()) return false;
    if (user?.role !== "trader") return false;
    if (!userStats) return false;
    return (userStats.successful_trades || 0) >= MIN_TRADES_REQUIRED;
  };

  // Покупка в один клик - показываем правила, потом сразу создаём сделку
  const handleBuyClick = (offer) => {
    if (!isAuthenticated) {
      navigate("/auth");
      return;
    }
    
    if (isBlockedFromBuying()) {
      toast.error("Покупка USDT недоступна для вашего типа аккаунта");
      return;
    }
    
    if (!canBuyCrypto()) {
      setShowRequirementDialog(true);
      return;
    }

    setSelectedOffer(offer);
    setShowRulesDialog(true);
  };

  // После принятия правил - сразу создаём сделку на всю сумму
  const handleRulesAcceptAndBuy = async () => {
    if (!selectedOffer) return;
    
    setBuyingOfferId(selectedOffer.id);
    setShowRulesDialog(false);

    try {
      const response = await axios.post(`${API}/crypto/buy`, {
        offer_id: selectedOffer.id,
        rules_accepted: true
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });

      toast.success("Заявка создана! Реквизиты в чате.");
      navigate("/trader/messages");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка создания заявки");
    } finally {
      setBuyingOfferId(null);
    }
  };

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white">
      {/* Header */}
      <header className="border-b border-white/5 bg-[#0A0A0A]/95 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link to="/" className="flex items-center gap-2">
              <ArrowLeft className="w-5 h-5 text-[#71717A]" />
              <span className="text-[#71717A] hover:text-white transition-colors">Назад</span>
            </Link>
            <div className="h-6 w-px bg-white/10" />
            <h1 className="text-xl font-bold flex items-center gap-2">
              <DollarSign className="w-6 h-6 text-[#10B981]" />
              Купить USDT
            </h1>
          </div>
          
          {isAuthenticated ? (
            <Link to="/trader">
              <Button variant="outline" className="border-white/10 text-white hover:bg-white/5" title="Перейти в личный кабинет">
                Личный кабинет
              </Button>
            </Link>
          ) : (
            <Link to="/auth">
              <Button className="bg-[#7C3AED] hover:bg-[#6D28D9] text-white" title="Войти в аккаунт">
                Войти
              </Button>
            </Link>
          )}
        </div>
      </header>

      {/* Info Banner */}
      <div className="bg-[#7C3AED]/10 border-b border-[#7C3AED]/20">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-3">
          <Info className="w-5 h-5 text-[#7C3AED] flex-shrink-0" />
          <p className="text-sm text-[#A1A1AA]">
            Покупка криптовалюты доступна только для пользователей с <span className="text-white font-medium">{MIN_TRADES_REQUIRED}+ успешными сделками</span>. 
            Все заявки обрабатываются модераторами платформы.
          </p>
        </div>
      </div>
      
      {/* Block Warning for merchants/admins */}
      {isAuthenticated && isBlockedFromBuying() && (
        <div className="bg-[#EF4444]/10 border-b border-[#EF4444]/20">
          <div className="max-w-7xl mx-auto px-4 py-4 flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-[#EF4444] flex-shrink-0" />
            <p className="text-sm text-[#EF4444]">
              <span className="font-medium">Покупка USDT недоступна</span> для {user?.role === "merchant" ? "мерчантов" : "администрации"}. 
              Эта функция доступна только для обычных трейдеров.
            </p>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 border-2 border-[#10B981] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : offers.length === 0 ? (
          <div className="text-center py-20">
            <DollarSign className="w-16 h-16 text-[#52525B] mx-auto mb-4" />
            <h2 className="text-xl font-bold text-white mb-2">Нет активных заявок</h2>
            <p className="text-[#71717A]">В данный момент нет доступных предложений на продажу USDT</p>
          </div>
        ) : (
          <div className="grid gap-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-white">Доступные предложения</h2>
              <span className="text-sm text-[#71717A]">{offers.length} предложений</span>
            </div>

            {offers.map((offer) => {
              // Рассчитываем USDT по курсу продажи (sell_rate)
              const sellRate = offer.sell_rate || offer.rate || 82.16;
              const usdtAmount = sellRate > 0 ? (offer.amount_rub / sellRate).toFixed(2) : '0.00';
              const isLoading = buyingOfferId === offer.id;
              
              return (
              <div 
                key={offer.id}
                className="bg-[#121212] border border-white/5 rounded-2xl p-6 hover:border-white/10 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-[#10B981]/10 rounded-xl flex items-center justify-center">
                      <User className="w-6 h-6 text-[#10B981]" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-white">{offer.merchant_name}</span>
                        {offer.merchant_verified && (
                          <CheckCircle className="w-4 h-4 text-[#10B981]" />
                        )}
                      </div>
                      <div className="text-sm text-[#71717A]">
                        {offer.merchant_trades || 0} сделок
                      </div>
                    </div>
                  </div>

                  <div className="text-right">
                    <div className="text-2xl font-bold text-[#10B981]">
                      {sellRate.toFixed(2)} ₽
                    </div>
                    <div className="text-sm text-[#71717A]">за 1 USDT</div>
                  </div>
                </div>

                {/* Сумма крупно */}
                <div className="mt-4 pt-4 border-t border-white/5">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-4xl font-bold text-white font-mono">
                        {(offer.amount_rub || 0).toLocaleString('ru-RU')} ₽
                      </div>
                      <div className="text-xl text-[#10B981] font-semibold mt-2">
                        = {usdtAmount} USDT
                      </div>
                    </div>

                    <Button 
                      onClick={() => handleBuyClick(offer)}
                      disabled={isLoading || isBlockedFromBuying()}
                      className={`px-8 py-3 text-lg h-14 ${
                        isBlockedFromBuying() 
                          ? "bg-[#3F3F46] text-[#71717A] cursor-not-allowed" 
                          : "bg-[#10B981] hover:bg-[#059669] text-white"
                      }`}
                      title={isBlockedFromBuying() ? "Покупка недоступна для вашего типа аккаунта" : "Купить всю сумму"}>
                      {isLoading ? (
                        <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      ) : (
                        <>
                          Купить
                          <ArrowRight className="w-5 h-5 ml-2" />
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              </div>
            )})}
          </div>
        )}
      </main>

      {/* Requirement Dialog */}
      <Dialog open={showRequirementDialog} onOpenChange={setShowRequirementDialog}>
        <DialogContent className="bg-[#121212] border-white/10 text-white max-w-md">
          <DialogHeader>
            <DialogTitle className="text-xl flex items-center gap-2">
              <AlertTriangle className="w-6 h-6 text-[#F59E0B]" />
              Недостаточно сделок
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            <p className="text-[#A1A1AA]">
              Для покупки криптовалюты необходимо иметь минимум <span className="text-white font-medium">{MIN_TRADES_REQUIRED} успешных сделок</span>.
            </p>

            <div className="bg-[#0A0A0A] rounded-xl p-4">
              <div className="flex items-center justify-between">
                <span className="text-[#71717A]">Ваши сделки</span>
                <span className="text-white font-medium">
                  {userStats?.successful_trades || 0} / {MIN_TRADES_REQUIRED}
                </span>
              </div>
              <div className="mt-2 h-2 bg-white/10 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-[#F59E0B] rounded-full transition-all"
                  style={{ width: `${Math.min(100, ((userStats?.successful_trades || 0) / MIN_TRADES_REQUIRED) * 100)}%` }}
                />
              </div>
            </div>

            <p className="text-sm text-[#71717A]">
              Совершайте P2P сделки на платформе, чтобы получить доступ к покупке криптовалюты.
            </p>

            <Button 
              onClick={() => setShowRequirementDialog(false)}
              className="w-full bg-[#7C3AED] hover:bg-[#6D28D9] text-white"
            >
              Понятно
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Rules Dialog - Принять правила и сразу купить */}
      <Dialog open={showRulesDialog} onOpenChange={setShowRulesDialog}>
        <DialogContent className="bg-[#121212] border-white/10 text-white max-w-lg max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="text-xl flex items-center gap-2">
              <FileText className="w-6 h-6 text-[#3B82F6]" />
              Подтверждение покупки
            </DialogTitle>
          </DialogHeader>

          <div className="flex-1 overflow-y-auto space-y-4 pr-2">
            {selectedOffer && (
              <div className="bg-[#10B981]/10 border border-[#10B981]/20 rounded-xl p-4">
                <h4 className="text-[#10B981] font-medium mb-3">Вы покупаете:</h4>
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-[#71717A]">Сумма:</span>
                    <span className="text-2xl font-bold text-white">
                      {(selectedOffer.amount_rub || 0).toLocaleString('ru-RU')} ₽
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-[#71717A]">Вы получите:</span>
                    <span className="text-xl font-bold text-[#10B981]">
                      {((selectedOffer.sell_rate || selectedOffer.rate) > 0 
                        ? (selectedOffer.amount_rub / (selectedOffer.sell_rate || selectedOffer.rate)).toFixed(2) 
                        : '0.00')} USDT
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-[#71717A]">Курс:</span>
                    <span className="text-white">
                      {(selectedOffer.sell_rate || selectedOffer.rate || 0).toFixed(2)} ₽/USDT
                    </span>
                  </div>
                </div>
              </div>
            )}

            <div className="bg-[#F59E0B]/10 border border-[#F59E0B]/20 rounded-xl p-4 flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-[#F59E0B] flex-shrink-0 mt-0.5" />
              <p className="text-sm text-[#F59E0B]">
                Нажимая "Купить", вы соглашаетесь с правилами платформы.
              </p>
            </div>

            <div className="bg-[#0A0A0A] border border-white/5 rounded-xl p-4">
              <pre className="text-white text-sm whitespace-pre-wrap font-sans leading-relaxed">
                {rulesText || "Правила загружаются..."}
              </pre>
            </div>
          </div>

          <div className="flex gap-3 mt-4 pt-4 border-t border-white/5">
            <Button 
              variant="outline" 
              onClick={() => setShowRulesDialog(false)}
              className="flex-1 border-white/10 text-white hover:bg-white/5"
              title="Отменить действие">
              Отмена
            </Button>
            <Button 
              onClick={handleRulesAcceptAndBuy}
              className="flex-1 bg-[#10B981] hover:bg-[#059669] text-white"
            >
              <CheckCircle className="w-4 h-4 mr-2" />
              Купить за {selectedOffer ? (selectedOffer.amount_rub || 0).toLocaleString('ru-RU') : 0} ₽
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
