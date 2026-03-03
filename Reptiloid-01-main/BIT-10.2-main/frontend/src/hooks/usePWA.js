import { useState, useEffect, useCallback } from 'react';

export const usePWA = () => {
  // Check if already installed
  const isAlreadyInstalled = typeof window !== 'undefined' && 
    (window.matchMedia('(display-mode: standalone)').matches ||
     window.navigator.standalone === true);
  
  const [isInstallable, setIsInstallable] = useState(false);
  const [isInstalled, setIsInstalled] = useState(isAlreadyInstalled);
  const [isIOS, setIsIOS] = useState(false);
  const [notificationPermission, setNotificationPermission] = useState(
    typeof window !== 'undefined' && 'Notification' in window 
      ? Notification.permission 
      : 'default'
  );

  useEffect(() => {
    // Detect iOS
    const iOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    setIsIOS(iOS);
    
    // On iOS, we can't programmatically install, but we can show instructions
    if (iOS && !isAlreadyInstalled) {
      setIsInstallable(true);
    }

    // Check if we already captured the prompt globally
    if (window.deferredInstallPrompt) {
      console.log('PWA: Found existing deferredInstallPrompt');
      setIsInstallable(true);
    }

    // Listen for install prompt (Chrome/Android/Desktop)
    const handleBeforeInstallPrompt = (e) => {
      console.log('PWA: beforeinstallprompt event in hook!');
      e.preventDefault();
      window.deferredInstallPrompt = e;
      setIsInstallable(true);
    };

    // Listen for app installed event
    const handleAppInstalled = () => {
      console.log('PWA: App was installed successfully!');
      setIsInstalled(true);
      setIsInstallable(false);
      window.deferredInstallPrompt = null;
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    window.addEventListener('appinstalled', handleAppInstalled);

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
      window.removeEventListener('appinstalled', handleAppInstalled);
    };
  }, [isAlreadyInstalled]);

  const installApp = useCallback(async () => {
    console.log('PWA: installApp called');
    console.log('PWA: isIOS =', isIOS);
    console.log('PWA: deferredInstallPrompt =', !!window.deferredInstallPrompt);

    // For iOS - show instructions
    if (isIOS) {
      console.log('PWA: iOS detected, returning ios');
      return 'ios';
    }

    // For Chrome/Android/Desktop - use native prompt
    if (window.deferredInstallPrompt) {
      try {
        console.log('PWA: Showing native install prompt...');
        window.deferredInstallPrompt.prompt();
        const { outcome } = await window.deferredInstallPrompt.userChoice;
        
        console.log(`PWA: User choice = ${outcome}`);
        
        if (outcome === 'accepted') {
          setIsInstalled(true);
          setIsInstallable(false);
          window.deferredInstallPrompt = null;
          return true;
        } else {
          // User dismissed
          return false;
        }
      } catch (error) {
        console.error('PWA: Install error:', error);
        window.deferredInstallPrompt = null;
        return 'manual';
      }
    }

    // No prompt available - show manual instructions
    console.log('PWA: No native prompt available, returning manual');
    return 'manual';
  }, [isIOS]);

  const requestNotificationPermission = async () => {
    if (!('Notification' in window)) {
      console.log('This browser does not support notifications');
      return false;
    }

    try {
      const permission = await Notification.requestPermission();
      setNotificationPermission(permission);
      return permission === 'granted';
    } catch (error) {
      console.error('Error requesting notification permission:', error);
      return false;
    }
  };

  const sendLocalNotification = (title, options = {}) => {
    if (notificationPermission !== 'granted') {
      console.log('Notification permission not granted');
      return;
    }

    const defaultOptions = {
      icon: '/icons/icon-192x192.png',
      badge: '/icons/icon-72x72.png',
      vibrate: [100, 50, 100],
      ...options
    };

    new Notification(title, defaultOptions);
  };

  return {
    isInstallable,
    isInstalled,
    isIOS,
    installApp,
    notificationPermission,
    requestNotificationPermission,
    sendLocalNotification
  };
};
