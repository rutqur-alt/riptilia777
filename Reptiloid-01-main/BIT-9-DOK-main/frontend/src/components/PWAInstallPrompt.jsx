import React, { useState } from 'react';
import { usePWA } from '@/hooks/usePWA';
import { Button } from '@/components/ui/button';
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogDescription,
  DialogFooter 
} from '@/components/ui/dialog';
import { Download, Bell, BellRing, Smartphone, X, Check } from 'lucide-react';
import { toast } from 'sonner';

const PWAInstallPrompt = () => {
  const { 
    isInstallable, 
    isInstalled, 
    installApp, 
    notificationPermission, 
    requestNotificationPermission 
  } = usePWA();
  
  const [showDialog, setShowDialog] = useState(false);
  const [installing, setInstalling] = useState(false);

  const handleInstall = async () => {
    setInstalling(true);
    const success = await installApp();
    setInstalling(false);
    
    if (success) {
      toast.success('Приложение установлено!');
      setShowDialog(false);
    }
  };

  const handleEnableNotifications = async () => {
    const granted = await requestNotificationPermission();
    if (granted) {
      toast.success('Уведомления включены!');
    } else {
      toast.error('Уведомления отклонены');
    }
  };

  // Don't show if already installed or not installable on desktop
  if (isInstalled) return null;

  return (
    <>
      {/* Floating install button for mobile */}
      {isInstallable && (
        <Button
          onClick={() => setShowDialog(true)}
          className="fixed bottom-20 left-4 z-50 h-9 w-9 rounded-full bg-emerald-600 hover:bg-emerald-700 shadow-lg md:hidden"
        >
          <Download className="w-4 h-4" />
        </Button>
      )}

      {/* Desktop banner */}
      {isInstallable && (
        <div className="hidden md:flex fixed bottom-4 left-4 right-4 z-50 bg-zinc-900 border border-zinc-700 rounded-lg p-4 items-center justify-between shadow-xl max-w-md">
          <div className="flex items-center gap-3">
            <div className="bg-emerald-500/20 p-2 rounded-lg">
              <Smartphone className="w-6 h-6 text-emerald-400" />
            </div>
            <div>
              <p className="font-medium text-white text-sm">Установить приложение</p>
              <p className="text-xs text-zinc-400">Быстрый доступ с рабочего стола</p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowDialog(false)}
            >
              <X className="w-4 h-4" />
            </Button>
            <Button
              size="sm"
              onClick={handleInstall}
              disabled={installing}
              className="bg-emerald-600 hover:bg-emerald-700"
            >
              {installing ? 'Установка...' : 'Установить'}
            </Button>
          </div>
        </div>
      )}

      {/* Installation dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Smartphone className="w-5 h-5 text-emerald-400" />
              Установить BITARBITR
            </DialogTitle>
            <DialogDescription>
              Установите приложение для быстрого доступа и получения уведомлений
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            {/* Feature list */}
            <div className="space-y-3">
              <div className="flex items-center gap-3 text-sm">
                <div className="bg-emerald-500/20 p-1.5 rounded">
                  <Check className="w-4 h-4 text-emerald-400" />
                </div>
                <span>Работает без интернета</span>
              </div>
              <div className="flex items-center gap-3 text-sm">
                <div className="bg-emerald-500/20 p-1.5 rounded">
                  <Check className="w-4 h-4 text-emerald-400" />
                </div>
                <span>Push-уведомления</span>
              </div>
              <div className="flex items-center gap-3 text-sm">
                <div className="bg-emerald-500/20 p-1.5 rounded">
                  <Check className="w-4 h-4 text-emerald-400" />
                </div>
                <span>Иконка на рабочем столе</span>
              </div>
            </div>

            {/* Notification permission */}
            {notificationPermission !== 'granted' && (
              <div className="p-3 bg-zinc-800 rounded-lg">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Bell className="w-4 h-4 text-yellow-400" />
                    <span className="text-sm">Уведомления</span>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleEnableNotifications}
                  >
                    <BellRing className="w-4 h-4 mr-1" />
                    Включить
                  </Button>
                </div>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="ghost" onClick={() => setShowDialog(false)}>
              Позже
            </Button>
            <Button 
              onClick={handleInstall}
              disabled={installing}
              className="bg-emerald-600 hover:bg-emerald-700"
            >
              <Download className="w-4 h-4 mr-2" />
              {installing ? 'Установка...' : 'Установить'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default PWAInstallPrompt;
