import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '@/lib/auth';
import { Clock, Wrench, RefreshCw } from 'lucide-react';

const MaintenancePage = () => {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [timeLeft, setTimeLeft] = useState(0);

  const checkMaintenance = async () => {
    const role = localStorage.getItem('userRole');
    if (!role) {
      navigate('/login');
      return;
    }
    
    try {
      const res = await api.get(`/public/maintenance?role=${role}`);
      if (!res.data.active) {
        navigate(`/${role}/dashboard`);
      } else {
        setData(res.data);
        setTimeLeft(res.data.remaining_seconds || 0);
      }
    } catch (error) {
      console.error('Error checking maintenance:', error);
    }
  };

  useEffect(() => {
    checkMaintenance();
    const interval = setInterval(checkMaintenance, 30000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (timeLeft <= 0) return;
    
    const timer = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) {
          checkMaintenance();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeLeft]);

  const formatTime = (seconds) => {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (hrs > 0) {
      return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-4">
      <div className="max-w-md w-full text-center">
        {/* Animated Icon */}
        <div className="relative mb-8">
          <div className="w-32 h-32 mx-auto bg-amber-500/10 rounded-full flex items-center justify-center">
            <Wrench className="w-16 h-16 text-amber-400 animate-pulse" />
          </div>
          <div className="absolute inset-0 w-32 h-32 mx-auto border-4 border-amber-500/30 rounded-full animate-spin-slow" 
            style={{ animationDuration: '8s' }} />
        </div>

        {/* Title */}
        <h1 className="text-3xl font-bold mb-4">
          Техническое обслуживание
        </h1>

        {/* Message */}
        <p className="text-zinc-400 text-lg mb-8">
          {data?.message || 'Платформа временно недоступна. Мы работаем над улучшениями.'}
        </p>

        {/* Timer */}
        {timeLeft > 0 && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 mb-6">
            <div className="flex items-center justify-center gap-2 text-zinc-400 mb-2">
              <Clock className="w-5 h-5" />
              <span>Осталось примерно</span>
            </div>
            <div className="text-5xl font-mono font-bold text-amber-400">
              {formatTime(timeLeft)}
            </div>
          </div>
        )}

        {/* Refresh Button */}
        <button
          onClick={checkMaintenance}
          className="inline-flex items-center gap-2 px-6 py-3 bg-zinc-800 hover:bg-zinc-700 rounded-lg transition-colors"
        >
          <RefreshCw className="w-5 h-5" />
          Проверить снова
        </button>

        {/* Info */}
        <p className="text-zinc-600 text-sm mt-8">
          Страница автоматически обновится когда работы будут завершены
        </p>
      </div>

      <style>{`
        @keyframes spin-slow {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        .animate-spin-slow {
          animation: spin-slow 8s linear infinite;
        }
      `}</style>
    </div>
  );
};

export default MaintenancePage;
