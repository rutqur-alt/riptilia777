import React from 'react';
import { Button } from '@/components/ui/button';
import { Store, Settings, History } from 'lucide-react';

export default function ShopHeader({ 
  connected, 
  merchantName, 
  showHistory, 
  setShowHistory, 
  showSettings, 
  setShowSettings,
  loadTransactions 
}) {
  return (
    <header className="sticky top-0 z-50 bg-[#0A0A0A]/95 backdrop-blur-xl border-b border-white/5">
      <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#7C3AED] to-[#10B981] flex items-center justify-center">
            <Store className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-white font-bold text-lg">{connected ? merchantName : 'Магазин'}</h1>
            <div className="flex items-center gap-1.5">
              <div className={`w-2 h-2 rounded-full ${connected ? 'bg-[#10B981]' : 'bg-[#EF4444]'}`} />
              <span className="text-xs text-[#71717A]">{connected ? 'Подключено' : 'Не подключено'}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {connected && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setShowHistory(!showHistory);
                if (!showHistory) loadTransactions();
              }}
              className="text-[#71717A] hover:text-white"
              data-testid="history-btn"
              title="История транзакций"
            >
              <History className="w-4 h-4" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowSettings(!showSettings)}
            className="text-[#71717A] hover:text-white"
            data-testid="settings-btn"
            title="Настройки"
          >
            <Settings className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </header>
  );
}
