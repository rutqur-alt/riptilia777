import React from 'react';
import { Button } from '@/components/ui/button';
import { Wallet, RefreshCw, Loader2 } from 'lucide-react';

export default function BalanceCard({ balance, loadingBalance, fetchBalance }) {
  return (
    <div className="bg-gradient-to-br from-[#7C3AED]/20 to-[#10B981]/20 rounded-2xl p-6 border border-white/10">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2 text-[#A78BFA]">
          <Wallet className="w-5 h-5" />
          <span className="font-medium">Ваш баланс</span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={fetchBalance}
          disabled={loadingBalance}
          className="text-[#71717A] hover:text-white"
          data-testid="refresh-balance-btn"
        >
          {loadingBalance ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
        </Button>
      </div>
      <div className="text-4xl font-bold text-white mb-1">
        {balance !== null ? `${balance.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ₽` : '—'}
      </div>
      <p className="text-[#71717A] text-sm">Доступно для использования</p>
    </div>
  );
}
