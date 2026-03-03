import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Save, Eye, EyeOff } from 'lucide-react';

export default function SettingsDialog({
  open,
  onOpenChange,
  connected,
  merchantId,
  setMerchantId,
  apiKey,
  setApiKey,
  apiSecret,
  setApiSecret,
  showSecret,
  setShowSecret,
  merchantName,
  disconnectApi,
  connectApi
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[#121212] border-white/10 text-white max-w-md">
        <DialogHeader>
          <DialogTitle>Настройки API</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 mt-4">
          <div>
            <label className="text-sm text-[#71717A] mb-1.5 block">Merchant ID</label>
            <Input
              type="text"
              value={merchantId}
              onChange={(e) => setMerchantId(e.target.value)}
              className="bg-[#0A0A0A] border-white/10 text-white"
              disabled={connected}
            />
          </div>

          <div>
            <label className="text-sm text-[#71717A] mb-1.5 block">API Key</label>
            <Input
              type="text"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="bg-[#0A0A0A] border-white/10 text-white"
              disabled={connected}
            />
          </div>

          <div>
            <label className="text-sm text-[#71717A] mb-1.5 block">API Secret</label>
            <div className="relative">
              <Input
                type={showSecret ? 'text' : 'password'}
                value={apiSecret}
                onChange={(e) => setApiSecret(e.target.value)}
                className="bg-[#0A0A0A] border-white/10 text-white pr-10"
                disabled={connected}
              />
              <button
                onClick={() => setShowSecret(!showSecret)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#52525B] hover:text-white"
              >
                {showSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {connected ? (
            <div className="space-y-3">
              <div className="p-3 bg-[#10B981]/10 rounded-lg border border-[#10B981]/20">
                <p className="text-[#10B981] text-sm">Подключено к: {merchantName}</p>
              </div>
              <Button
                variant="destructive"
                onClick={disconnectApi}
                className="w-full"
              >
                Отключиться
              </Button>
            </div>
          ) : (
            <Button
              onClick={() => { connectApi(); onOpenChange(false); }}
              disabled={!merchantId || !apiKey || !apiSecret}
              className="w-full bg-gradient-to-r from-[#7C3AED] to-[#10B981]"
            >
              <Save className="w-4 h-4 mr-2" />
              Сохранить и подключиться
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
