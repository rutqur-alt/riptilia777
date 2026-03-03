import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import { useAuth, API } from "@/App";
import axios from "axios";
import { 
  DollarSign, ArrowLeft, Clock, CheckCircle, AlertTriangle, 
  User, Search, ArrowRight, Wallet, Shield, Info, FileText
} from "lucide-react";

export default function BuyCrypto() {
  const { isAuthenticated, user, token } = useAuth();
  const navigate = useNavigate();
  const [offers, setOffers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [userStats, setUserStats] = useState(null);
  const [selectedOffer, setSelectedOffer] = useState(null);
  const [buyAmount, setBuyAmount] = useState("");
  const [showDialog, setShowDialog] = useState(false);
  const [showRequirementDialog, setShowRequirementDialog] = useState(false);
  const [showRulesDialog, setShowRulesDialog] = useState(false);
  const [rulesText, setRulesText] = useState("");
  const [rulesAccepted, setRulesAccepted] = useState(false);

  const MIN_TRADES_REQUIRED = 20;

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
    if (user?.role !== "trader") return false;
    if (!userStats) return false;
    return (userStats.successful_trades || 0) >= MIN_TRADES_REQUIRED;
  };

  const handleBuyClick = (offer) => {
    if (!isAuthenticated) {
      navigate("/auth");
      return;
    }
    
    if (!canBuyCrypto()) {
      setShowRequirementDialog(true);
      return;
    }

    setSelectedOffer(offer);
    setBuyAmount("");
    setRulesAccepted(false);
    setShowRulesDialog(true);  // Show rules first
  };

  const handleRulesAccept = () => {
    setRulesAccepted(true);
    setShowRulesDialog(false);
    setShowDialog(true);
  };

  const handleBuySubmit = async () => {
    if (!selectedOffer || !buyAmount) return;

    const amount = parseFloat(buyAmount);
    if (isNaN(amount) || amount <= 0) {
      toast.error("Введите корректную сумму");
      return;
    }

    if (amount < selectedOffer.min_amount) {
      toast.error(`Минимальная сумма: ${selectedOffer.min_amount} USDT`);
      return;
    }

    if (amount > selectedOffer.max_amount) {
      toast.error(`Максимальная сумма: ${selectedOffer.max_amount} USDT`);
      return;
    }

    try {
      const response = await axios.post(`${API}/crypto/buy`, {
        offer_id: selectedOffer.id,
        amount: amount,
        rules_accepted: true
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });

      toast.success("Заявка создана! Реквизиты в чате.");
      setShowDialog(false);
      navigate("/trader/messages");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка создания заявки");
    }
  };

  const getRubAmount = (usdtAmount) => {
    if (!selectedOffer || !usdtAmount) return 0;
    return (parseFloat(usdtAmount) * selectedOffer.rate).toFixed(2);
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

            {offers.map((offer) => (
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
                      {offer.rate?.toFixed(2)} ₽
                    </div>
                    <div className="text-sm text-[#71717A]">за 1 USDT</div>
                  </div>
                </div>

                <div className="mt-4 pt-4 border-t border-white/5 flex items-center justify-between">
                  <div className="flex items-center gap-6 text-sm">
                    <div>
                      <span className="text-[#71717A]">Сумма: </span>
                      <span className="text-white">{(offer.amount_rub || 0).toLocaleString()} ₽</span>
                      <span className="text-[#71717A] ml-1">({(offer.available_amount || 0).toFixed(2)} USDT)</span>
                    </div>
                  </div>

                  <Button 
                    onClick={() => handleBuyClick(offer)}
                    className="bg-[#10B981] hover:bg-[#059669] text-white px-6"
                   title="Купить USDT">
                    Купить
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* Buy Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="bg-[#121212] border-white/10 text-white max-w-md">
          <DialogHeader>
            <DialogTitle className="text-xl">Купить USDT</DialogTitle>
          </DialogHeader>

          {selectedOffer && (
            <div className="space-y-4">
              <div className="bg-[#0A0A0A] rounded-xl p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[#71717A]">Продавец</span>
                  <span className="text-white">{selectedOffer.merchant_name}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[#71717A]">Курс</span>
                  <span className="text-[#10B981] font-medium">{selectedOffer.rate?.toFixed(2)} ₽/USDT</span>
                </div>
              </div>

              <div>
                <label className="text-sm text-[#A1A1AA] mb-2 block">Сумма USDT</label>
                <Input
                  type="number"
                  value={buyAmount}
                  onChange={(e) => setBuyAmount(e.target.value)}
                  placeholder={`${selectedOffer.min_amount} - ${selectedOffer.max_amount}`}
                  className="bg-[#0A0A0A] border-white/10 text-white h-12"
                />
                <div className="text-xs text-[#71717A] mt-1">
                  Лимиты: {(selectedOffer.min_amount || 0).toFixed(2)} - {(selectedOffer.max_amount || 0).toFixed(2)} USDT
                </div>
              </div>

              {buyAmount && (
                <div className="bg-[#10B981]/10 border border-[#10B981]/20 rounded-xl p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-[#A1A1AA]">К оплате</span>
                    <span className="text-xl font-bold text-[#10B981]">{getRubAmount(buyAmount)} ₽</span>
                  </div>
                </div>
              )}

              <div className="flex gap-3">
                <Button 
                  variant="outline" 
                  onClick={() => setShowDialog(false)}
                  className="flex-1 border-white/10 text-white hover:bg-white/5"
                 title="Отменить действие">
                  Отмена
                </Button>
                <Button 
                  onClick={handleBuySubmit}
                  disabled={!buyAmount}
                  className="flex-1 bg-[#10B981] hover:bg-[#059669] text-white"
                 title="Создать новое объявление">
                  Создать заявку
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

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

      {/* Rules Dialog - MUST ACCEPT BEFORE BUYING */}
      <Dialog open={showRulesDialog} onOpenChange={setShowRulesDialog}>
        <DialogContent className="bg-[#121212] border-white/10 text-white max-w-lg max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="text-xl flex items-center gap-2">
              <FileText className="w-6 h-6 text-[#3B82F6]" />
              Правила покупки криптовалюты
            </DialogTitle>
          </DialogHeader>

          <div className="flex-1 overflow-y-auto space-y-4 pr-2">
            <div className="bg-[#F59E0B]/10 border border-[#F59E0B]/20 rounded-xl p-4 flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-[#F59E0B] flex-shrink-0 mt-0.5" />
              <p className="text-sm text-[#F59E0B]">
                Внимательно прочитайте правила перед совершением покупки. 
                Нажимая "Принять и продолжить", вы соглашаетесь с правилами.
              </p>
            </div>

            <div className="bg-[#0A0A0A] border border-white/5 rounded-xl p-4">
              <pre className="text-white text-sm whitespace-pre-wrap font-sans leading-relaxed">
                {rulesText || "Правила загружаются..."}
              </pre>
            </div>

            {selectedOffer && (
              <div className="bg-[#10B981]/10 border border-[#10B981]/20 rounded-xl p-4">
                <h4 className="text-[#10B981] font-medium mb-2">Выбранное предложение:</h4>
                <div className="text-sm space-y-1">
                  <div className="flex justify-between">
                    <span className="text-[#71717A]">Курс:</span>
                    <span className="text-white">{selectedOffer.rate?.toFixed(2)} ₽/USDT</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#71717A]">Доступно:</span>
                    <span className="text-white">{(selectedOffer.available_amount || 0).toFixed(2)} USDT</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#71717A]">Лимиты:</span>
                    <span className="text-white">{(selectedOffer.min_amount || 0).toFixed(2)} - {(selectedOffer.max_amount || 0).toFixed(2)} USDT</span>
                  </div>
                </div>
              </div>
            )}
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
              onClick={handleRulesAccept}
              className="flex-1 bg-[#10B981] hover:bg-[#059669] text-white"
            >
              <CheckCircle className="w-4 h-4 mr-2" />
              Принять и продолжить
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
