import React from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Plug, Eye, EyeOff, Loader2 } from 'lucide-react';

export default function ApiConnectionForm({
  merchantId,
  setMerchantId,
  apiKey,
  setApiKey,
  apiSecret,
  setApiSecret,
  showSecret,
  setShowSecret,
  connecting,
  connectApi
}) {
  return (
    <div className="bg-[#121212] border border-white/10 rounded-2xl p-6 max-w-md mx-auto">
      <div className="text-center mb-6">
        <div className="w-16 h-16 mx-auto bg-gradient-to-br from-[#7C3AED] to-[#10B981] rounded-2xl flex items-center justify-center mb-4">
          <Plug className="w-8 h-8 text-white" />
        </div>
        <h2 className="text-xl font-bold text-white mb-1">Подключение к магазину</h2>
        <p className="text-[#71717A] text-sm">Введите данные API для начала работы</p>
      </div>

      <div className="space-y-4">
        <div>
          <label className="text-sm text-[#71717A] mb-1.5 block">Merchant ID</label>
          <Input
            type="text"
            placeholder="Введите Merchant ID"
            value={merchantId}
            onChange={(e) => setMerchantId(e.target.value)}
            className="bg-[#0A0A0A] border-white/10 text-white placeholder:text-[#52525B]"
            data-testid="merchant-id-input"
          />
        </div>
        <div>
          <label className="text-sm text-[#71717A] mb-1.5 block">API Key</label>
          <Input
            type="text"
            placeholder="Введите API ключ"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            className="bg-[#0A0A0A] border-white/10 text-white placeholder:text-[#52525B]"
            data-testid="api-key-input"
          />
        </div>
        <div>
          <label className="text-sm text-[#71717A] mb-1.5 block">API Secret</label>
          <div className="relative">
            <Input
              type={showSecret ? 'text' : 'password'}
              placeholder="Введите API Secret"
              value={apiSecret}
              onChange={(e) => setApiSecret(e.target.value)}
              className="bg-[#0A0A0A] border-white/10 text-white placeholder:text-[#52525B] pr-10"
              data-testid="api-secret-input"
            />
            <button
              onClick={() => setShowSecret(!showSecret)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[#52525B] hover:text-white"
            >
              {showSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>

        <Button
          onClick={() => connectApi()}
          disabled={connecting || !merchantId || !apiKey || !apiSecret}
          className="w-full bg-gradient-to-r from-[#7C3AED] to-[#10B981] hover:opacity-90"
          data-testid="connect-btn"
        >
          {connecting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Plug className="w-4 h-4 mr-2" />}
          Подключиться
        </Button>
      </div>
    </div>
  );
}
