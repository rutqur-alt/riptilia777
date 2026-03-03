import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import { Wallet, ExternalLink, Store, Sparkles } from 'lucide-react';
import axios from 'axios';
import { API } from '@/App';

/**
 * Demo Shop - единственный тестовый магазин для проверки платёжного потока
 * URL: /demo
 */
const DemoShop = () => {
  const [amount, setAmount] = useState('');
  const [loading, setLoading] = useState(false);

  const createPaymentAndOpen = async () => {
    const numAmount = parseInt(amount);
    if (!numAmount || numAmount < 100) {
      toast.error('Минимальная сумма 100₽');
      return;
    }

    setLoading(true);
    
    try {
      const response = await axios.post(`${API}/shop/quick-payment`, {
        amount_rub: numAmount,
        description: `Пополнение на ${numAmount.toLocaleString()} ₽`
      });
      
      if (response.data.invoice_id) {
        toast.success('Платёж создан! Открываю...');
        const paymentUrl = `/select-operator/${response.data.invoice_id}`;
        window.open(paymentUrl, '_blank');
        setAmount('');
      }
    } catch (error) {
      console.error('Error:', error);
      toast.error('Ошибка создания платежа');
    } finally {
      setLoading(false);
    }
  };

  const quickAmounts = [500, 1000, 2000, 5000, 10000];

  return (
    <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="bg-[#121212] border border-white/10 rounded-2xl p-6 space-y-6">
          {/* Лого */}
          <div className="text-center">
            <div className="w-16 h-16 mx-auto bg-gradient-to-br from-[#7C3AED] to-[#10B981] rounded-2xl flex items-center justify-center mb-4">
              <Store className="w-8 h-8 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-white mb-1">Demo Shop</h1>
            <p className="text-[#71717A] text-sm">Тестовый магазин для проверки платежей</p>
          </div>

          {/* Ввод суммы */}
          <div className="space-y-4">
            <div>
              <label className="text-sm text-[#71717A] mb-2 block">Сумма пополнения</label>
              <div className="relative">
                <Input
                  type="number"
                  placeholder="Введите сумму"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="bg-[#0A0A0A] border-white/10 h-14 text-xl text-center pr-12 text-white placeholder:text-[#52525B]"
                  min="100"
                  data-testid="demo-amount-input"
                />
                <span className="absolute right-4 top-1/2 -translate-y-1/2 text-[#52525B] text-lg">₽</span>
              </div>
            </div>

            {/* Быстрые суммы */}
            <div className="grid grid-cols-5 gap-2">
              {quickAmounts.map((val) => (
                <Button
                  key={val}
                  variant="outline"
                  onClick={() => setAmount(String(val))}
                  className={`border-white/10 text-white hover:bg-white/5 h-10 px-2 text-sm ${
                    amount === String(val) ? 'bg-[#7C3AED]/20 border-[#7C3AED]' : ''
                  }`}
                  data-testid={`quick-amount-${val}`}
                >
                  {val >= 1000 ? `${val/1000}k` : val}
                </Button>
              ))}
            </div>
          </div>

          {/* Инфо */}
          <div className="bg-[#7C3AED]/10 border border-[#7C3AED]/20 rounded-xl p-3">
            <div className="flex items-start gap-2">
              <Sparkles className="w-4 h-4 text-[#7C3AED] mt-0.5 flex-shrink-0" />
              <div className="text-sm text-[#A1A1AA]">
                Страница оплаты откроется в <strong className="text-white">новой вкладке</strong>
              </div>
            </div>
          </div>

          {/* Кнопка */}
          <Button
            onClick={createPaymentAndOpen}
            disabled={!amount || loading}
            className="w-full h-14 bg-[#10B981] hover:bg-[#059669] text-white text-lg rounded-xl"
            data-testid="create-payment-btn"
           title="Пополнить баланс USDT">
            {loading ? (
              <span className="flex items-center gap-2">
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Создание...
              </span>
            ) : (
              <>
                <Wallet className="w-5 h-5 mr-2" />
                Пополнить
                <ExternalLink className="w-4 h-4 ml-2" />
              </>
            )}
          </Button>
        </div>

        <p className="text-center text-[#52525B] text-xs mt-4">
          Используйте /demo для тестирования платёжного потока
        </p>
      </div>
    </div>
  );
};

export default DemoShop;
