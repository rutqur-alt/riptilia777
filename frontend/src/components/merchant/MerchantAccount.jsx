import { useAuth } from "@/App";
import { User } from "lucide-react";

export default function MerchantAccount() {
  const { user } = useAuth();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Профиль</h1>

      <div className="bg-[#121212] border border-white/5 rounded-2xl p-6">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-20 h-20 bg-[#F97316]/10 rounded-2xl flex items-center justify-center">
            <User className="w-10 h-10 text-[#F97316]" />
          </div>
          <div>
            <div className="text-xl font-bold text-white">{user?.nickname || user?.merchant_name || user?.login}</div>
            <div className="text-[#F97316]">Мерчант</div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex justify-between py-3 border-b border-white/5">
            <span className="text-[#71717A]">Логин</span>
            <span className="text-white">{user?.login}</span>
          </div>
          <div className="flex justify-between py-3 border-b border-white/5">
            <span className="text-[#71717A]">Комиссия на платежи</span>
            <span className="text-[#3B82F6] font-medium font-['JetBrains_Mono']">{user?.commission_rate || 0}%</span>
          </div>
          <div className="flex justify-between py-3 border-b border-white/5">
            <span className="text-[#71717A]">Комиссия на выплаты</span>
            <span className="text-[#10B981] font-medium font-['JetBrains_Mono']">{user?.withdrawal_commission || 3}%</span>
          </div>
          <div className="flex justify-between py-3">
            <span className="text-[#71717A]">Статус</span>
            <span className="text-[#10B981]">Активен</span>
          </div>
        </div>
      </div>
    </div>
  );
}
