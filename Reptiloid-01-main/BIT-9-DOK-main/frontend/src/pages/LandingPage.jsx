import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Coins } from 'lucide-react';

const LandingPage = () => {
  return (
    <div className="min-h-screen bg-[#09090B] text-white flex flex-col">
      {/* Navigation */}
      <nav className="bg-[#09090B] border-b border-zinc-800">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-10 h-10 rounded-lg bg-emerald-500 flex items-center justify-center">
              <Coins className="w-6 h-6 text-white" />
            </div>
            <span className="font-bold text-xl tracking-tight font-['Chivo']">BITARBITR</span>
          </div>
          
          <div className="flex items-center gap-3">
            <Link to="/login">
              <Button variant="ghost" className="text-zinc-400 hover:text-white" data-testid="login-btn">
                Войти
              </Button>
            </Link>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="max-w-md w-full text-center">
          <div className="w-20 h-20 rounded-2xl bg-emerald-500 flex items-center justify-center mx-auto mb-8">
            <Coins className="w-10 h-10 text-white" />
          </div>
          
          <h1 className="text-3xl font-bold font-['Chivo'] mb-4">
            BITARBITR
          </h1>
          
          <p className="text-zinc-400 mb-8">
            P2P платформа для обмена USDT
          </p>
          
          <div className="space-y-3">
            <Link to="/login" className="block">
              <Button className="w-full bg-emerald-500 hover:bg-emerald-600 text-white h-12 text-base" data-testid="login-main-btn">
                Войти
              </Button>
            </Link>
            
            <Link to="/register?role=trader" className="block">
              <Button variant="outline" className="w-full border-zinc-700 hover:bg-zinc-800 h-12 text-base" data-testid="start-trader-btn">
                Стать трейдером
              </Button>
            </Link>
            
            <Link to="/register?role=merchant" className="block">
              <Button variant="outline" className="w-full border-zinc-700 hover:bg-zinc-800 h-12 text-base" data-testid="start-merchant-btn">
                Стать мерчантом
              </Button>
            </Link>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-800 py-4 text-center text-zinc-500 text-sm">
        © {new Date().getFullYear()} BITARBITR
      </footer>
    </div>
  );
};

export default LandingPage;
