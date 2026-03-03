import React from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { CreditCard, Loader2 } from 'lucide-react';

export default function TopUpForm({ 
  amount, 
  setAmount, 
  topUpLoading, 
  startTopUp 
}) {
  const presetAmounts = [500, 1000, 2000, 5000];

  return (
    <div className="bg-[#121212] rounded-2xl p-6 border border-white/5">
      <div className="flex items-center gap-2 mb-4">
        <CreditCard className="w-5 h-5 text-[#7C3AED]" />
        <h2 className="text-white font-semibold">Пополнить баланс</h2>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        {presetAmounts.map((val) => (
          <Button
            key={val}
            variant="outline"
            size="sm"
            onClick={() => setAmount(val.toString())}
            className={`border-white/10 ${amount === val.toString() ? 'bg-[#7C3AED] text-white border-[#7C3AED]' : 'text-white hover:bg-white/5'}`}
          >
            {val.toLocaleString()} ₽
          </Button>
        ))}
      </div>

      <div className="flex gap-2">
        <Input
          type="number"
          placeholder="Сумма в RUB"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          min={100}
          className="bg-[#0A0A0A] border-white/10 text-white placeholder:text-[#52525B] font-['JetBrains_Mono']"
          data-testid="amount-input"
        />
        <Button
          onClick={startTopUp}
          disabled={topUpLoading || !amount || parseInt(amount) < 100}
          className="bg-[#7C3AED] hover:bg-[#6D28D9] px-6"
          data-testid="topup-btn"
        >
          {topUpLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Пополнить'}
        </Button>
      </div>
    </div>
  );
}
