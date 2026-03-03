import { useState, useEffect } from "react";
import { Wrench, RefreshCw, Settings, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function MaintenancePage({ message = "Ведутся технические работы" }) {
  const [rotation, setRotation] = useState(0);
  const [dots, setDots] = useState("");
  const [pulse, setPulse] = useState(false);

  // Rotating gear animation
  useEffect(() => {
    const interval = setInterval(() => {
      setRotation(prev => (prev + 2) % 360);
    }, 50);
    return () => clearInterval(interval);
  }, []);

  // Loading dots animation
  useEffect(() => {
    const interval = setInterval(() => {
      setDots(prev => prev.length >= 3 ? "" : prev + ".");
    }, 500);
    return () => clearInterval(interval);
  }, []);

  // Pulse animation
  useEffect(() => {
    const interval = setInterval(() => {
      setPulse(prev => !prev);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  const handleRefresh = () => {
    window.location.reload();
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#0A0A0A] via-[#0F0F0F] to-[#0A0A0A] flex flex-col items-center justify-center p-4 overflow-hidden relative">
      {/* Animated background elements */}
      <div className="absolute inset-0 overflow-hidden">
        {/* Floating particles */}
        {[...Array(20)].map((_, i) => (
          <div
            key={i}
            className="absolute w-1 h-1 bg-[#7C3AED]/30 rounded-full animate-float"
            style={{
              left: `${Math.random() * 100}%`,
              top: `${Math.random() * 100}%`,
              animationDelay: `${Math.random() * 5}s`,
              animationDuration: `${5 + Math.random() * 10}s`
            }}
          />
        ))}
        
        {/* Gradient orbs */}
        <div className={`absolute -top-40 -left-40 w-80 h-80 bg-[#7C3AED]/10 rounded-full blur-3xl transition-opacity duration-2000 ${pulse ? 'opacity-60' : 'opacity-30'}`} />
        <div className={`absolute -bottom-40 -right-40 w-80 h-80 bg-[#10B981]/10 rounded-full blur-3xl transition-opacity duration-2000 ${pulse ? 'opacity-30' : 'opacity-60'}`} />
      </div>

      {/* Main content */}
      <div className="relative z-10 text-center max-w-md">
        {/* Animated icon container */}
        <div className="relative w-32 h-32 mx-auto mb-8">
          {/* Outer ring */}
          <div className="absolute inset-0 border-4 border-[#7C3AED]/20 rounded-full animate-pulse" />
          
          {/* Middle ring with rotation */}
          <div 
            className="absolute inset-2 border-2 border-dashed border-[#10B981]/40 rounded-full"
            style={{ transform: `rotate(${rotation}deg)` }}
          />
          
          {/* Inner circle with icon */}
          <div className="absolute inset-4 bg-gradient-to-br from-[#7C3AED]/20 to-[#10B981]/20 rounded-full flex items-center justify-center backdrop-blur-sm border border-white/5">
            <div className="relative">
              <Settings 
                className="w-12 h-12 text-[#7C3AED]"
                style={{ transform: `rotate(${-rotation}deg)` }}
              />
              <Wrench 
                className="w-6 h-6 text-[#10B981] absolute -bottom-1 -right-1"
                style={{ transform: `rotate(${rotation * 0.5}deg)` }}
              />
            </div>
          </div>
          
          {/* Orbiting dot */}
          <div 
            className="absolute w-3 h-3 bg-[#7C3AED] rounded-full shadow-lg shadow-[#7C3AED]/50"
            style={{
              left: `${50 + 45 * Math.cos(rotation * Math.PI / 180)}%`,
              top: `${50 + 45 * Math.sin(rotation * Math.PI / 180)}%`,
              transform: 'translate(-50%, -50%)'
            }}
          />
        </div>

        {/* Title */}
        <h1 className="text-3xl md:text-4xl font-bold text-white mb-4 font-['Unbounded']">
          Технические работы
        </h1>

        {/* Message */}
        <p className="text-[#A1A1AA] text-lg mb-2">
          {message}
        </p>

        {/* Loading indicator */}
        <div className="flex items-center justify-center gap-2 text-[#71717A] mb-8">
          <Clock className="w-4 h-4 animate-pulse" />
          <span className="text-sm">
            Скоро вернёмся{dots}
          </span>
        </div>

        {/* Status indicators */}
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-6 mb-6">
          <div className="grid grid-cols-3 gap-4">
            <div className="text-center">
              <div className="w-3 h-3 rounded-full bg-[#F59E0B] mx-auto mb-2 animate-pulse" />
              <span className="text-xs text-[#71717A]">Серверы</span>
            </div>
            <div className="text-center">
              <div className="w-3 h-3 rounded-full bg-[#F59E0B] mx-auto mb-2 animate-pulse" />
              <span className="text-xs text-[#71717A]">База данных</span>
            </div>
            <div className="text-center">
              <div className="w-3 h-3 rounded-full bg-[#10B981] mx-auto mb-2" />
              <span className="text-xs text-[#71717A]">Сеть</span>
            </div>
          </div>
        </div>

        {/* Refresh button */}
        <Button 
          onClick={handleRefresh}
          className="bg-gradient-to-r from-[#7C3AED] to-[#A855F7] hover:from-[#6D28D9] hover:to-[#9333EA] text-white rounded-full px-8 py-3 text-sm font-medium shadow-lg shadow-[#7C3AED]/20 group"
          data-testid="maintenance-refresh-btn"
        >
          <RefreshCw className="w-4 h-4 mr-2 group-hover:animate-spin" />
          Проверить доступность
        </Button>

        {/* Contact info */}
        <p className="mt-8 text-xs text-[#52525B]">
          Если проблема сохраняется, свяжитесь с поддержкой
        </p>
      </div>

      {/* CSS for custom animations */}
      <style jsx global>{`
        @keyframes float {
          0%, 100% {
            transform: translateY(0) translateX(0);
            opacity: 0.3;
          }
          25% {
            transform: translateY(-20px) translateX(10px);
            opacity: 0.6;
          }
          50% {
            transform: translateY(-10px) translateX(-5px);
            opacity: 0.4;
          }
          75% {
            transform: translateY(-30px) translateX(5px);
            opacity: 0.5;
          }
        }
        
        .animate-float {
          animation: float 8s ease-in-out infinite;
        }
        
        .transition-opacity {
          transition: opacity 2s ease-in-out;
        }
      `}</style>
    </div>
  );
}
