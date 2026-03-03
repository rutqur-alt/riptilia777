import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { API } from "@/App";
import axios from "axios";
import { 
  ShoppingCart, CreditCard, Wallet, Gift, Star, Zap, 
  ChevronRight, Check, ArrowRight
} from "lucide-react";

// Test merchant credentials - this would normally be stored securely
const TEST_MERCHANT = {
  id: null, // Will be fetched
  api_key: null,
  name: "Тестовый Магазин",
  type: "shop"
};

const depositOptions = [
  { amount: 500, bonus: null },
  { amount: 1000, bonus: null },
  { amount: 2500, bonus: "5%" },
  { amount: 5000, bonus: "10%" },
  { amount: 10000, bonus: "15%" },
  { amount: 25000, bonus: "20%" }
];

export default function TestShop() {
  const navigate = useNavigate();
  const [step, setStep] = useState("shop"); // shop, deposit, processing
  const [selectedAmount, setSelectedAmount] = useState(null);
  const [customAmount, setCustomAmount] = useState("");
  const [balance, setBalance] = useState(0);
  const [creating, setCreating] = useState(false);
  const [paymentLink, setPaymentLink] = useState(null);
  const [merchantData, setMerchantData] = useState(null);

  useEffect(() => {
    // Create or get test merchant on load
    initTestMerchant();
  }, []);

  const initTestMerchant = async () => {
    try {
      // Try to login as existing test merchant
      const loginRes = await axios.post(`${API}/auth/login`, {
        login: "test_shop_merchant",
        password: "testshop123"
      });
      setMerchantData(loginRes.data.user);
    } catch (error) {
      // If doesn't exist, create it
      try {
        const registerRes = await axios.post(`${API}/auth/merchant/register`, {
          login: "test_shop_merchant",
          password: "testshop123",
          merchant_name: "Тестовый Магазин",
          merchant_type: "shop",
          telegram: "@test_shop"
        });
        setMerchantData(registerRes.data.user);
        
        // Auto-approve for testing (normally would need admin)
        // This is just for demo purposes
      } catch (regError) {
        console.error("Could not create test merchant", regError);
      }
    }
  };

  const handleSelectAmount = (amount) => {
    setSelectedAmount(amount);
    setCustomAmount("");
  };

  const handleCustomAmount = (value) => {
    setCustomAmount(value);
    setSelectedAmount(null);
  };

  const getFinalAmount = () => {
    return selectedAmount || parseInt(customAmount) || 0;
  };

  const handleDeposit = async () => {
    const amount = getFinalAmount();
    if (amount < 100) {
      toast.error("Минимальная сумма 100 ₽");
      return;
    }

    setCreating(true);
    try {
      // Login to get token
      const loginRes = await axios.post(`${API}/auth/login`, {
        login: "test_shop_merchant",
        password: "testshop123"
      });
      
      const token = loginRes.data.token;
      
      // Create payment link
      const linkRes = await axios.post(`${API}/payment-links`, {
        amount_rub: amount,
        price_rub: 92.5 // Default rate
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });

      setPaymentLink(linkRes.data);
      setStep("processing");
      toast.success("Платежная ссылка создана!");
    } catch (error) {
      console.error(error);
      if (error.response?.status === 403) {
        toast.error("Мерчант не активирован. Обратитесь к администратору.");
      } else {
        toast.error(error.response?.data?.detail || "Ошибка создания платежа");
      }
    } finally {
      setCreating(false);
    }
  };

  const handleGoToPayment = () => {
    if (paymentLink) {
      navigate(`/pay/${paymentLink.id}`);
    }
  };

  // Shop Main Page
  if (step === "shop") {
    return (
      <div className="min-h-screen bg-gradient-to-b from-[#1a1a2e] to-[#16213e]">
        {/* Header */}
        <header className="border-b border-white/10 bg-black/20 backdrop-blur-sm">
          <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#FF6B6B] to-[#FF8E53] flex items-center justify-center">
                <ShoppingCart className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-bold text-white">TestShop</span>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <div className="text-xs text-white/50">Баланс</div>
                <div className="text-white font-bold font-['JetBrains_Mono']">{balance.toLocaleString()} ₽</div>
              </div>
              <Button 
                onClick={() => setStep("deposit")}
                className="bg-gradient-to-r from-[#FF6B6B] to-[#FF8E53] hover:opacity-90 rounded-full px-6"
              >
                <Wallet className="w-4 h-4 mr-2" />
                Пополнить
              </Button>
            </div>
          </div>
        </header>

        {/* Hero */}
        <div className="max-w-6xl mx-auto px-4 py-16 text-center">
          <h1 className="text-5xl font-bold text-white mb-4">
            Тестовый Магазин
          </h1>
          <p className="text-xl text-white/70 mb-8">
            Демонстрация P2P оплаты для клиентов мерчантов
          </p>
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[#10B981]/10 border border-[#10B981]/20">
            <Check className="w-4 h-4 text-[#10B981]" />
            <span className="text-[#10B981] text-sm">Тестовый режим — деньги не списываются</span>
          </div>
        </div>

        {/* Products Grid */}
        <div className="max-w-6xl mx-auto px-4 pb-16">
          <h2 className="text-2xl font-bold text-white mb-6">Тестовые товары</h2>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              { name: "Премиум подписка", price: 999, icon: Star, color: "from-[#FFD700] to-[#FFA500]" },
              { name: "Игровая валюта", price: 500, icon: Zap, color: "from-[#00D9FF] to-[#00A3FF]" },
              { name: "Подарочная карта", price: 2500, icon: Gift, color: "from-[#FF6B6B] to-[#FF8E53]" }
            ].map((product, idx) => (
              <div key={idx} className="bg-white/5 backdrop-blur-sm rounded-2xl p-6 border border-white/10 hover:border-white/20 transition-colors">
                <div className={`w-16 h-16 rounded-2xl bg-gradient-to-br ${product.color} flex items-center justify-center mb-4`}>
                  <product.icon className="w-8 h-8 text-white" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">{product.name}</h3>
                <div className="text-2xl font-bold text-white font-['JetBrains_Mono'] mb-4">
                  {product.price.toLocaleString()} ₽
                </div>
                <Button 
                  onClick={() => {
                    setSelectedAmount(product.price);
                    setStep("deposit");
                  }}
                  className="w-full bg-white/10 hover:bg-white/20 rounded-xl"
                >
                  Купить
                </Button>
              </div>
            ))}
          </div>
        </div>

        {/* How it works */}
        <div className="max-w-6xl mx-auto px-4 pb-16">
          <h2 className="text-2xl font-bold text-white mb-6">Как это работает</h2>
          <div className="grid md:grid-cols-4 gap-4">
            {[
              { step: "1", title: "Выберите сумму", desc: "Укажите сумму пополнения" },
              { step: "2", title: "Выберите трейдера", desc: "Выберите продавца USDT" },
              { step: "3", title: "Оплатите", desc: "Переведите рубли на карту" },
              { step: "4", title: "Получите", desc: "Деньги зачислятся автоматически" }
            ].map((item, idx) => (
              <div key={idx} className="bg-white/5 rounded-xl p-4 text-center">
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#FF6B6B] to-[#FF8E53] flex items-center justify-center mx-auto mb-3 text-white font-bold">
                  {item.step}
                </div>
                <div className="text-white font-medium mb-1">{item.title}</div>
                <div className="text-sm text-white/50">{item.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // Deposit Page
  if (step === "deposit") {
    return (
      <div className="min-h-screen bg-gradient-to-b from-[#1a1a2e] to-[#16213e] px-4 py-8">
        <div className="max-w-lg mx-auto">
          {/* Back button */}
          <button 
            onClick={() => setStep("shop")} 
            className="flex items-center gap-2 text-white/70 hover:text-white mb-8 transition-colors"
          >
            <ChevronRight className="w-4 h-4 rotate-180" />
            Вернуться в магазин
          </button>

          <div className="bg-white/5 backdrop-blur-sm rounded-3xl p-8 border border-white/10">
            <div className="text-center mb-8">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#FF6B6B] to-[#FF8E53] flex items-center justify-center mx-auto mb-4">
                <CreditCard className="w-8 h-8 text-white" />
              </div>
              <h1 className="text-2xl font-bold text-white">Пополнение баланса</h1>
              <p className="text-white/50 mt-2">Оплата через P2P обмен USDT</p>
            </div>

            {/* Amount Options */}
            <div className="grid grid-cols-2 gap-3 mb-6">
              {depositOptions.map((option) => (
                <button
                  key={option.amount}
                  onClick={() => handleSelectAmount(option.amount)}
                  className={`p-4 rounded-xl border-2 transition-all ${
                    selectedAmount === option.amount
                      ? "border-[#FF6B6B] bg-[#FF6B6B]/10"
                      : "border-white/10 hover:border-white/20"
                  }`}
                >
                  <div className="text-xl font-bold text-white font-['JetBrains_Mono']">
                    {option.amount.toLocaleString()} ₽
                  </div>
                  {option.bonus && (
                    <div className="text-xs text-[#10B981] mt-1">+{option.bonus} бонус</div>
                  )}
                </button>
              ))}
            </div>

            {/* Custom Amount */}
            <div className="mb-6">
              <label className="text-white/70 text-sm mb-2 block">Или введите свою сумму</label>
              <Input
                type="number"
                placeholder="Сумма в рублях"
                value={customAmount}
                onChange={(e) => handleCustomAmount(e.target.value)}
                className="bg-white/5 border-white/10 text-white h-14 rounded-xl text-lg font-['JetBrains_Mono'] placeholder:text-white/30"
              />
            </div>

            {/* Summary */}
            {getFinalAmount() > 0 && (
              <div className="bg-white/5 rounded-xl p-4 mb-6">
                <div className="flex justify-between items-center">
                  <span className="text-white/70">К оплате</span>
                  <span className="text-2xl font-bold text-white font-['JetBrains_Mono']">
                    {getFinalAmount().toLocaleString()} ₽
                  </span>
                </div>
                <div className="flex justify-between items-center mt-2 text-sm">
                  <span className="text-white/50">Примерно в USDT</span>
                  <span className="text-white/70 font-['JetBrains_Mono']">
                    ≈ {(getFinalAmount() / 92.5).toFixed(2)} USDT
                  </span>
                </div>
              </div>
            )}

            {/* Submit Button */}
            <Button
              onClick={handleDeposit}
              disabled={getFinalAmount() < 100 || creating}
              className="w-full h-14 bg-gradient-to-r from-[#FF6B6B] to-[#FF8E53] hover:opacity-90 rounded-xl font-semibold text-lg disabled:opacity-50"
            >
              {creating ? (
                <div className="spinner" />
              ) : (
                <>
                  Оплатить через P2P
                  <ArrowRight className="w-5 h-5 ml-2" />
                </>
              )}
            </Button>

            <p className="text-center text-white/30 text-xs mt-4">
              Вы будете перенаправлены на платформу Reptiloid
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Processing/Redirect Page
  if (step === "processing" && paymentLink) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-[#1a1a2e] to-[#16213e] flex items-center justify-center px-4">
        <div className="max-w-md w-full bg-white/5 backdrop-blur-sm rounded-3xl p-8 border border-white/10 text-center">
          <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-[#10B981] to-[#059669] flex items-center justify-center mx-auto mb-6">
            <Check className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white mb-2">Платеж создан!</h1>
          <p className="text-white/50 mb-6">
            Сумма: {paymentLink.amount_rub.toLocaleString()} ₽ ({paymentLink.amount_usdt.toFixed(2)} USDT)
          </p>
          
          <div className="bg-white/5 rounded-xl p-4 mb-6 text-left">
            <div className="text-white/50 text-sm mb-1">ID платежа</div>
            <div className="text-white font-['JetBrains_Mono'] text-sm break-all">{paymentLink.id}</div>
          </div>

          <Button
            onClick={handleGoToPayment}
            className="w-full h-14 bg-gradient-to-r from-[#FF6B6B] to-[#FF8E53] hover:opacity-90 rounded-xl font-semibold text-lg"
          >
            Перейти к оплате
            <ArrowRight className="w-5 h-5 ml-2" />
          </Button>

          <button 
            onClick={() => setStep("shop")} 
            className="text-white/50 hover:text-white text-sm mt-4 transition-colors"
          >
            Вернуться в магазин
          </button>
        </div>
      </div>
    );
  }

  return null;
}
