import { XCircle } from "lucide-react";

export default function RejectedView() {
  return (
    <div className="flex items-center justify-center h-[60vh]">
      <div className="text-center">
        <XCircle className="w-16 h-16 text-[#EF4444] mx-auto mb-4" />
        <h2 className="text-xl font-bold text-white mb-2">Заявка отклонена</h2>
        <p className="text-[#71717A]">К сожалению, ваша заявка на мерчанта была отклонена.</p>
      </div>
    </div>
  );
}
