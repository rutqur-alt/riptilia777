import { Link } from "react-router-dom";
import { TrendingUp, DollarSign } from "lucide-react";

export default function TraderHistory() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white font-['Unbounded']">История сделок</h1>
      <p className="text-[#71717A]">Выберите раздел для просмотра завершённых сделок</p>
      
      <div className="grid sm:grid-cols-2 gap-4">
        <Link to="/trader/history/sales">
          <div className="bg-[#121212] border border-white/5 hover:border-[#10B981]/50 rounded-2xl p-6 transition-colors">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-[#10B981]/10 flex items-center justify-center">
                <TrendingUp className="w-6 h-6 text-[#10B981]" />
              </div>
              <div>
                <div className="text-white font-semibold text-lg">История продаж</div>
                <div className="text-sm text-[#71717A]">Завершённые продажи USDT</div>
              </div>
            </div>
          </div>
        </Link>
        
        <Link to="/trader/history/purchases">
          <div className="bg-[#121212] border border-white/5 hover:border-[#7C3AED]/50 rounded-2xl p-6 transition-colors">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-[#7C3AED]/10 flex items-center justify-center">
                <DollarSign className="w-6 h-6 text-[#7C3AED]" />
              </div>
              <div>
                <div className="text-white font-semibold text-lg">История покупок</div>
                <div className="text-sm text-[#71717A]">Завершённые покупки USDT</div>
              </div>
            </div>
          </div>
        </Link>
      </div>
    </div>
  );
}
