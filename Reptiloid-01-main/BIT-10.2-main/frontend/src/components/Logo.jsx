import React, { useEffect, useRef, useState } from 'react';

// Символы крипты и денег для анимации
const CRYPTO_SYMBOLS = ['₿', '₽', '$', '€', '₮', '◈', '⟐', '₳', 'Ξ', '◉'];

// Круглый логотип с плавающими символами
export const Logo = ({ size = 'md', className = '', animated = true }) => {
  const sizes = {
    sm: { container: 'w-12 h-12', symbol: 'text-lg', ring: 44 },
    md: { container: 'w-16 h-16', symbol: 'text-2xl', ring: 58 },
    lg: { container: 'w-28 h-28', symbol: 'text-4xl', ring: 100 },
    xl: { container: 'w-40 h-40', symbol: 'text-6xl', ring: 140 }
  };

  const s = sizes[size];

  return (
    <div className={`relative ${s.container} ${className}`}>
      {/* Внешнее свечение */}
      <div className="absolute inset-0 rounded-full bg-gradient-to-tr from-orange-500/30 via-yellow-500/20 to-emerald-500/30 blur-xl animate-pulse" />
      
      {/* SVG с кругом и символами */}
      <svg className="absolute inset-0 w-full h-full" viewBox="0 0 100 100">
        <defs>
          {/* Градиент для основного круга */}
          <linearGradient id="circleGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#ff6b00" stopOpacity="0.8"/>
            <stop offset="50%" stopColor="#ffd700" stopOpacity="0.6"/>
            <stop offset="100%" stopColor="#00ff87" stopOpacity="0.8"/>
          </linearGradient>
          
          {/* Свечение */}
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="2" result="blur"/>
            <feMerge>
              <feMergeNode in="blur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
          
          {/* Градиент для внутреннего круга */}
          <radialGradient id="innerGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#1a1a2e" stopOpacity="1"/>
            <stop offset="70%" stopColor="#0d0d15" stopOpacity="1"/>
            <stop offset="100%" stopColor="#050508" stopOpacity="1"/>
          </radialGradient>
        </defs>
        
        {/* Внешнее кольцо с символами */}
        <circle cx="50" cy="50" r="46" fill="none" stroke="url(#circleGradient)" strokeWidth="2" filter="url(#glow)"/>
        
        {/* Вращающееся кольцо с пунктиром */}
        <circle cx="50" cy="50" r="43" fill="none" stroke="url(#circleGradient)" strokeWidth="0.5" strokeDasharray="8 4" opacity="0.5">
          <animateTransform attributeName="transform" type="rotate" from="0 50 50" to="360 50 50" dur="20s" repeatCount="indefinite"/>
        </circle>
        
        {/* Внутренний тёмный круг */}
        <circle cx="50" cy="50" r="38" fill="url(#innerGlow)"/>
        
        {/* Орбитальные символы крипты */}
        {animated && (
          <>
            {/* Биткоин на орбите */}
            <text fontSize="8" fill="#ffd700" filter="url(#glow)">
              <animateMotion dur="12s" repeatCount="indefinite">
                <mpath href="#orbit1"/>
              </animateMotion>
              ₿
            </text>
            <path id="orbit1" d="M 50 8 A 42 42 0 1 1 50 92 A 42 42 0 1 1 50 8" fill="none"/>
            
            {/* Доллар на орбите */}
            <text fontSize="6" fill="#00ff87" filter="url(#glow)">
              <animateMotion dur="10s" repeatCount="indefinite" begin="-3s">
                <mpath href="#orbit2"/>
              </animateMotion>
              $
            </text>
            <path id="orbit2" d="M 50 12 A 38 38 0 1 0 50 88 A 38 38 0 1 0 50 12" fill="none"/>
            
            {/* Евро на орбите */}
            <text fontSize="5" fill="#ff6b00" filter="url(#glow)">
              <animateMotion dur="15s" repeatCount="indefinite" begin="-7s">
                <mpath href="#orbit1"/>
              </animateMotion>
              €
            </text>
            
            {/* Эфир на орбите */}
            <text fontSize="6" fill="#627eea" filter="url(#glow)">
              <animateMotion dur="8s" repeatCount="indefinite" begin="-2s">
                <mpath href="#orbit2"/>
              </animateMotion>
              Ξ
            </text>
          </>
        )}
        
        {/* Звёздочки/искры */}
        <circle cx="20" cy="25" r="1" fill="#ffd700">
          <animate attributeName="opacity" values="0.3;1;0.3" dur="2s" repeatCount="indefinite"/>
          <animate attributeName="r" values="0.5;1.5;0.5" dur="2s" repeatCount="indefinite"/>
        </circle>
        <circle cx="80" cy="30" r="1" fill="#00ff87">
          <animate attributeName="opacity" values="0.3;1;0.3" dur="1.5s" repeatCount="indefinite" begin="0.5s"/>
          <animate attributeName="r" values="0.5;1.5;0.5" dur="1.5s" repeatCount="indefinite" begin="0.5s"/>
        </circle>
        <circle cx="75" cy="75" r="1" fill="#ff6b00">
          <animate attributeName="opacity" values="0.3;1;0.3" dur="2.5s" repeatCount="indefinite" begin="1s"/>
          <animate attributeName="r" values="0.5;1.5;0.5" dur="2.5s" repeatCount="indefinite" begin="1s"/>
        </circle>
        <circle cx="25" cy="70" r="1" fill="#627eea">
          <animate attributeName="opacity" values="0.3;1;0.3" dur="1.8s" repeatCount="indefinite" begin="0.3s"/>
          <animate attributeName="r" values="0.5;1.5;0.5" dur="1.8s" repeatCount="indefinite" begin="0.3s"/>
        </circle>
        
        {/* Маленькие точки-звёзды */}
        <circle cx="15" cy="50" r="0.5" fill="#fff" opacity="0.6">
          <animate attributeName="opacity" values="0.2;0.8;0.2" dur="3s" repeatCount="indefinite"/>
        </circle>
        <circle cx="85" cy="50" r="0.5" fill="#fff" opacity="0.6">
          <animate attributeName="opacity" values="0.2;0.8;0.2" dur="2.5s" repeatCount="indefinite" begin="1s"/>
        </circle>
        <circle cx="50" cy="15" r="0.5" fill="#fff" opacity="0.6">
          <animate attributeName="opacity" values="0.2;0.8;0.2" dur="2s" repeatCount="indefinite" begin="0.5s"/>
        </circle>
        <circle cx="50" cy="85" r="0.5" fill="#fff" opacity="0.6">
          <animate attributeName="opacity" values="0.2;0.8;0.2" dur="2.2s" repeatCount="indefinite" begin="1.5s"/>
        </circle>
      </svg>
      
      {/* Центральные символы ₿₽ */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="flex items-center">
          <span 
            className={`font-black ${s.symbol}`}
            style={{ 
              color: '#ff8c00',
              textShadow: '0 0 15px #ff6b00, 0 0 30px #ff6b0080'
            }}
          >
            ₿
          </span>
          <span 
            className={`font-black ${s.symbol}`}
            style={{ 
              color: '#00ff87',
              textShadow: '0 0 15px #00ff87, 0 0 30px #00ff8780'
            }}
          >
            ₽
          </span>
        </div>
      </div>
    </div>
  );
};

// Текстовый логотип
export const LogoText = ({ className = '' }) => {
  return (
    <span className={`font-black tracking-tight ${className}`}>
      <span 
        style={{ 
          background: 'linear-gradient(135deg, #ff6b00, #ffd700)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          filter: 'drop-shadow(0 0 8px rgba(255,107,0,0.5))'
        }}
      >
        BIT
      </span>
      <span 
        style={{ 
          background: 'linear-gradient(135deg, #00ff87, #00d4aa)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          filter: 'drop-shadow(0 0 8px rgba(0,255,135,0.5))'
        }}
      >
        ARBITR
      </span>
    </span>
  );
};

// Полный логотип с текстом
export const FullLogo = ({ size = 'md', className = '' }) => {
  const textSizes = {
    sm: 'text-xl',
    md: 'text-2xl', 
    lg: 'text-4xl',
    xl: 'text-5xl'
  };

  return (
    <div className={`flex items-center gap-4 ${className}`}>
      <Logo size={size} />
      <LogoText className={textSizes[size]} />
    </div>
  );
};

// Матричная анимация с символами крипты
export const MatrixRain = ({ className = '' }) => {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    const resizeCanvas = () => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
    
    const fontSize = 14;
    const columns = Math.floor(canvas.width / fontSize);
    const drops = Array(columns).fill(1);

    const draw = () => {
      ctx.fillStyle = 'rgba(5, 5, 8, 0.05)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      
      ctx.font = `${fontSize}px 'JetBrains Mono', monospace`;

      for (let i = 0; i < drops.length; i++) {
        const text = CRYPTO_SYMBOLS[Math.floor(Math.random() * CRYPTO_SYMBOLS.length)];
        const x = i * fontSize;
        const y = drops[i] * fontSize;

        // Градиент цвета
        const progress = (y / canvas.height);
        const r = Math.floor(255 * (1 - progress));
        const g = Math.floor(107 + 148 * progress);
        const b = Math.floor(0 + 135 * progress);
        
        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${0.4 + Math.random() * 0.4})`;
        ctx.fillText(text, x, y);

        if (y > canvas.height && Math.random() > 0.975) {
          drops[i] = 0;
        }
        drops[i]++;
      }
    };

    const interval = setInterval(draw, 50);
    return () => {
      clearInterval(interval);
      window.removeEventListener('resize', resizeCanvas);
    };
  }, []);

  return <canvas ref={canvasRef} className={`w-full h-full ${className}`} />;
};

// Полноэкранный лоадер
export const FullPageLoader = ({ text = 'Загрузка...' }) => {
  return (
    <div className="fixed inset-0 bg-[#050508] flex items-center justify-center z-50">
      <div className="absolute inset-0 opacity-30">
        <MatrixRain />
      </div>
      <div className="relative z-10 flex flex-col items-center gap-6">
        <Logo size="lg" />
        <div className="flex items-center gap-3 text-zinc-400">
          <div className="flex gap-1">
            <div className="w-2 h-2 bg-orange-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
            <div className="w-2 h-2 bg-yellow-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
            <div className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
          <span>{text}</span>
        </div>
      </div>
    </div>
  );
};

export default Logo;
