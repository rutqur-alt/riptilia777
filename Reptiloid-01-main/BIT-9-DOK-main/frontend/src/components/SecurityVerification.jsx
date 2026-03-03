import React, { useState } from 'react';
import { api } from '@/lib/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Shield, Lock, Smartphone, AlertTriangle, Eye, EyeOff } from 'lucide-react';
import { toast } from 'sonner';

/**
 * Security Verification Modal
 * Requires password and 2FA (if enabled) for sensitive operations
 */
const SecurityVerification = ({ 
  open, 
  onOpenChange, 
  onVerified, 
  title = "Подтверждение безопасности",
  description = "Для выполнения этой операции требуется подтверждение",
  actionLabel = "Подтвердить"
}) => {
  const [password, setPassword] = useState('');
  const [twoFactorCode, setTwoFactorCode] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [requires2FA, setRequires2FA] = useState(null);
  const [checking, setChecking] = useState(false);

  // Check if user has 2FA enabled
  const check2FAStatus = async () => {
    if (requires2FA !== null) return;
    setChecking(true);
    try {
      const res = await api.get('/auth/2fa/status');
      setRequires2FA(res.data.enabled);
    } catch (error) {
      setRequires2FA(false);
    } finally {
      setChecking(false);
    }
  };

  React.useEffect(() => {
    if (open) {
      check2FAStatus();
      setPassword('');
      setTwoFactorCode('');
    }
  }, [open]);

  const handleVerify = async () => {
    if (!password) {
      toast.error('Введите пароль');
      return;
    }

    if (requires2FA && (!twoFactorCode || twoFactorCode.length !== 6)) {
      toast.error('Введите 6-значный код 2FA');
      return;
    }

    setLoading(true);
    try {
      // Verify credentials on server
      const res = await api.post('/auth/verify-credentials', {
        password,
        two_factor_code: requires2FA ? twoFactorCode : null
      });

      // API returns success: true
      if (res.data.success) {
        onVerified({
          password,
          twoFactorCode: requires2FA ? twoFactorCode : null,
          verificationToken: res.data.verification_token
        });
        onOpenChange(false);
        setPassword('');
        setTwoFactorCode('');
      } else {
        toast.error('Неверные учётные данные');
      }
    } catch (error) {
      const msg = error.response?.data?.detail || 'Неверные учётные данные';
      toast.error(msg);
      // Clear inputs but keep modal open for retry
      setPassword('');
      setTwoFactorCode('');
      // Focus password input for retry
      setTimeout(() => {
        const pwdInput = document.querySelector('[data-testid="security-password"]');
        if (pwdInput) pwdInput.focus();
      }, 100);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-zinc-900 border-zinc-800 sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg">
            <Shield className="w-5 h-5 text-emerald-400" />
            {title}
          </DialogTitle>
          <DialogDescription className="text-zinc-400">
            {description}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="bg-orange-500/10 border border-orange-500/20 rounded-lg p-3 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-orange-400 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-orange-300">
              Это защищённая операция. Подтвердите свою личность для продолжения.
            </div>
          </div>

          <div className="space-y-2">
            <Label className="flex items-center gap-2">
              <Lock className="w-4 h-4 text-zinc-400" />
              Пароль
            </Label>
            <div className="relative">
              <Input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Введите ваш пароль"
                className="bg-zinc-950 border-zinc-800 pr-10"
                autoFocus
                data-testid="security-password"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {checking && (
            <div className="flex items-center gap-2 text-sm text-zinc-400">
              <div className="w-4 h-4 border-2 border-zinc-600 border-t-emerald-500 rounded-full animate-spin" />
              Проверка 2FA...
            </div>
          )}

          {requires2FA && (
            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <Smartphone className="w-4 h-4 text-zinc-400" />
                Код 2FA (Google Authenticator)
              </Label>
              <Input
                type="text"
                inputMode="numeric"
                value={twoFactorCode}
                onChange={(e) => setTwoFactorCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="000000"
                maxLength={6}
                className="bg-zinc-950 border-zinc-800 font-mono text-center text-xl tracking-widest"
                data-testid="security-2fa"
              />
            </div>
          )}
        </div>

        <DialogFooter className="flex gap-2">
          <Button 
            variant="outline" 
            onClick={() => onOpenChange(false)}
            className="border-zinc-700"
          >
            Отмена
          </Button>
          <Button
            onClick={handleVerify}
            disabled={loading || checking || !password || (requires2FA && twoFactorCode.length !== 6)}
            className="bg-emerald-500 hover:bg-emerald-600"
            data-testid="security-submit"
          >
            {loading ? (
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
            ) : (
              <Shield className="w-4 h-4 mr-2" />
            )}
            {actionLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default SecurityVerification;
