import { useState, useEffect } from "react";
import { Link, useParams, useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { 
  Wallet, ArrowLeft, Shield, Users, AlertCircle, CheckCircle, 
  Clock, Copy, XCircle, AlertTriangle, Lock, Unlock, DollarSign
} from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { toast } from "sonner";

export default function GuarantDealPage() {
  const { dealId } = useParams();
  const [searchParams] = useSearchParams();
  const inviteCode = searchParams.get("code");
  const { isAuthenticated, user, token, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  
  const [deal, setDeal] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [disputeReason, setDisputeReason] = useState("");
  const [showDisputeForm, setShowDisputeForm] = useState(false);

  useEffect(() => {
    if (!authLoading && isAuthenticated) {
      fetchDeal();
    }
  }, [dealId, authLoading, isAuthenticated]);

  // Handle invite link
  useEffect(() => {
    if (inviteCode && isAuthenticated && deal?.status === "pending_counterparty") {
      handleJoin();
    }
  }, [inviteCode, isAuthenticated, deal]);

  const fetchDeal = async () => {
    try {
      const response = await axios.get(`${API}/guarantor/deals/${dealId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setDeal(response.data);
    } catch (error) {
      if (error.response?.status === 403 && inviteCode) {
        // User doesn't have access yet but has invite code - try to join
        setDeal({ status: "pending_counterparty" }); 
      } else {
        toast.error(error.response?.data?.detail || "Ошибка загрузки сделки");
        navigate("/trader/guarantor");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleJoin = async () => {
    if (!inviteCode) return;
    setActionLoading(true);
    try {
      await axios.post(
        `${API}/guarantor/deals/${dealId}/join?invite_code=${inviteCode}`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success("Вы присоединились к сделке!");
      fetchDeal();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка присоединения");
    } finally {
      setActionLoading(false);
    }
  };

  const handleFund = async () => {
    setActionLoading(true);
    try {
      await axios.post(
        `${API}/guarantor/deals/${dealId}/fund`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success("Сделка оплачена! Средства заморожены.");
      fetchDeal();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка оплаты");
    } finally {
      setActionLoading(false);
    }
  };

  const handleConfirm = async () => {
    setActionLoading(true);
    try {
      const response = await axios.post(
        `${API}/guarantor/deals/${dealId}/confirm`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(`Сделка завершена! Продавец получил ${response.data.seller_received} ${deal.currency}`);
      fetchDeal();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка подтверждения");
    } finally {
      setActionLoading(false);
    }
  };

  const handleDispute = async () => {
    if (!disputeReason.trim()) {
      toast.error("Укажите причину спора");
      return;
    }
    setActionLoading(true);
    try {
      await axios.post(
        `${API}/guarantor/deals/${dealId}/dispute?reason=${encodeURIComponent(disputeReason)}`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success("Спор открыт. Администратор рассмотрит вашу заявку.");
      setShowDisputeForm(false);
      fetchDeal();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Ошибка открытия спора");
    } finally {
      setActionLoading(false);
    }
  };

  const copyInviteLink = () => {
    const link = `${window.location.origin}/guarantor/deal/${dealId}?code=${deal.invite_code}`;
    navigator.clipboard.writeText(link);
    toast.success("Ссылка скопирована!");
  };

  // Loading state
  if (authLoading || loading) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-[#7C3AED] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // Auth required
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
        <div className="text-center">
          <Shield className="w-12 h-12 text-[#7C3AED] mx-auto mb-4" />
          <h2 className="text-xl text-white mb-4">Требуется авторизация</h2>
          <Link to="/auth">
            <Button className="bg-[#7C3AED] hover:bg-[#6D28D9]" title="Войти в аккаунт">Войти</Button>
          </Link>
        </div>
      </div>
    );
  }

  if (!deal) return null;

  // Determine user role in this deal
  const isCreator = deal.creator_id === user?.id;
  const isCounterparty = deal.counterparty_id === user?.id;
  const isBuyer = (deal.creator_role === "buyer" && isCreator) || (deal.creator_role === "seller" && isCounterparty);
  const isSeller = !isBuyer && (isCreator || isCounterparty);

  // Status info
  const statusConfig = {
    pending_counterparty: { label: "Ожидает участника", color: "text-[#F59E0B]", bg: "bg-[#F59E0B]/10", icon: Users },
    pending_payment: { label: "Ожидает оплаты", color: "text-[#3B82F6]", bg: "bg-[#3B82F6]/10", icon: Clock },
    funded: { label: "Средства заморожены", color: "text-[#10B981]", bg: "bg-[#10B981]/10", icon: Lock },
    completed: { label: "Завершена", color: "text-[#10B981]", bg: "bg-[#10B981]/10", icon: CheckCircle },
    disputed: { label: "Спор", color: "text-[#EF4444]", bg: "bg-[#EF4444]/10", icon: AlertTriangle },
    cancelled: { label: "Отменена", color: "text-[#71717A]", bg: "bg-[#71717A]/10", icon: XCircle }
  };

  const status = statusConfig[deal.status] || statusConfig.pending_counterparty;
  const StatusIcon = status.icon;

  return (
    <div className="min-h-screen bg-[#0A0A0A]">
      {/* Header */}
      <header className="border-b border-white/5">
        <div className="max-w-2xl mx-auto px-4 py-4">
          <div className="flex items-center gap-4">
            <Link to="/trader/guarantor">
              <Button variant="ghost" size="icon" className="text-[#A1A1AA] hover:text-white hover:bg-white/5">
                <ArrowLeft className="w-5 h-5" />
              </Button>
            </Link>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-[#7C3AED] flex items-center justify-center">
                <Shield className="w-4 h-4 text-white" />
              </div>
              <span className="text-lg font-semibold text-white">Гарант-сделка</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-2xl mx-auto px-4 py-8">
        {/* Status Badge */}
        <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full ${status.bg} ${status.color} mb-6`}>
          <StatusIcon className="w-4 h-4" />
          <span className="font-medium">{status.label}</span>
        </div>

        {/* Deal Info Card */}
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-6 mb-6">
          <div className="mb-6">
            <h1 className="text-2xl font-bold text-white mb-2">{deal.title}</h1>
            <p className="text-[#71717A]">{deal.description}</p>
          </div>

          {/* Amount */}
          <div className="flex items-center justify-between p-4 bg-[#0A0A0A] rounded-xl mb-4">
            <span className="text-[#A1A1AA]">Сумма сделки</span>
            <span className="text-2xl font-bold text-[#10B981] font-['JetBrains_Mono']">
              {parseFloat(deal.amount || 0).toFixed(2)} {deal.currency}
            </span>
          </div>

          {/* Commission */}
          <div className="flex items-center justify-between p-4 bg-[#0A0A0A] rounded-xl mb-4">
            <span className="text-[#A1A1AA]">Комиссия сервиса (5%)</span>
            <span className="text-[#F59E0B] font-['JetBrains_Mono']">
              {parseFloat(deal.commission || 0).toFixed(2)} {deal.currency}
            </span>
          </div>

          {/* Seller receives */}
          <div className="flex items-center justify-between p-4 bg-[#7C3AED]/10 rounded-xl">
            <span className="text-[#A78BFA]">Продавец получит</span>
            <span className="text-lg font-bold text-white font-['JetBrains_Mono']">
              {(deal.amount - deal.commission).toFixed(2)} {deal.currency}
            </span>
          </div>
        </div>

        {/* Participants */}
        <div className="bg-[#121212] border border-white/5 rounded-2xl p-6 mb-6">
          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
            <Users className="w-4 h-4" /> Участники
          </h3>
          
          <div className="space-y-3">
            {/* Creator */}
            <div className="flex items-center justify-between p-3 bg-[#0A0A0A] rounded-lg">
              <div>
                <div className="text-sm text-[#71717A]">
                  {deal.creator_role === "buyer" ? "Покупатель" : "Продавец"}
                </div>
                <div className="text-white font-medium">
                  @{deal.creator_nickname}
                  {isCreator && <span className="ml-2 text-xs text-[#7C3AED]">(вы)</span>}
                </div>
              </div>
            </div>

            {/* Counterparty */}
            <div className="flex items-center justify-between p-3 bg-[#0A0A0A] rounded-lg">
              <div>
                <div className="text-sm text-[#71717A]">
                  {deal.creator_role === "buyer" ? "Продавец" : "Покупатель"}
                </div>
                <div className="text-white font-medium">
                  {deal.counterparty_nickname ? (
                    <>
                      @{deal.counterparty_nickname}
                      {isCounterparty && <span className="ml-2 text-xs text-[#7C3AED]">(вы)</span>}
                    </>
                  ) : (
                    <span className="text-[#F59E0B]">Ожидает присоединения</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Conditions */}
        {deal.conditions && (
          <div className="bg-[#121212] border border-white/5 rounded-2xl p-6 mb-6">
            <h3 className="text-white font-semibold mb-3">Условия сделки</h3>
            <p className="text-[#A1A1AA] whitespace-pre-wrap">{deal.conditions}</p>
          </div>
        )}

        {/* Invite Link (for pending_counterparty status) */}
        {deal.status === "pending_counterparty" && deal.invite_link && isCreator && (
          <div className="bg-[#7C3AED]/10 border border-[#7C3AED]/30 rounded-2xl p-6 mb-6">
            <h3 className="text-[#A78BFA] font-semibold mb-3 flex items-center gap-2">
              <Copy className="w-4 h-4" /> Пригласить второго участника
            </h3>
            <p className="text-sm text-[#71717A] mb-3">
              Отправьте эту ссылку второму участнику сделки
            </p>
            <div className="flex gap-2">
              <input
                type="text"
                readOnly
                value={`${window.location.origin}${deal.invite_link}`}
                className="flex-1 bg-[#0A0A0A] border border-white/10 rounded-lg px-3 py-2 text-white text-sm font-mono"
              />
              <Button onClick={copyInviteLink} className="bg-[#7C3AED] hover:bg-[#6D28D9]" title="Скопировать">
                <Copy className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="space-y-3">
          {/* Join (for counterparty with invite code) */}
          {deal.status === "pending_counterparty" && !isCreator && inviteCode && (
            <Button
              onClick={handleJoin}
              disabled={actionLoading}
              className="w-full h-12 bg-[#7C3AED] hover:bg-[#6D28D9] text-white rounded-xl"
            >
              {actionLoading ? (
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <Users className="w-5 h-5 mr-2" />
                  Присоединиться к сделке
                </>
              )}
            </Button>
          )}

          {/* Fund (for buyer when pending_payment) */}
          {deal.status === "pending_payment" && isBuyer && (
            <Button
              onClick={handleFund}
              disabled={actionLoading}
              className="w-full h-12 bg-[#10B981] hover:bg-[#059669] text-white rounded-xl"
             title="Перейти к оплате">
              {actionLoading ? (
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <Lock className="w-5 h-5 mr-2" />
                  Оплатить {parseFloat(deal.amount || 0).toFixed(2)} {deal.currency}
                </>
              )}
            </Button>
          )}

          {/* Confirm (for buyer when funded) */}
          {deal.status === "funded" && isBuyer && (
            <>
              <Button
                onClick={handleConfirm}
                disabled={actionLoading}
                className="w-full h-12 bg-[#10B981] hover:bg-[#059669] text-white rounded-xl"
               title="Подтвердить получение оплаты">
                {actionLoading ? (
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <>
                    <CheckCircle className="w-5 h-5 mr-2" />
                    Подтвердить получение
                  </>
                )}
              </Button>

              {!showDisputeForm ? (
                <Button
                  onClick={() => setShowDisputeForm(true)}
                  variant="outline"
                  className="w-full h-10 border-[#EF4444]/30 text-[#EF4444] hover:bg-[#EF4444]/10 rounded-xl"
                 title="Открыть спор по сделке">
                  <AlertTriangle className="w-4 h-4 mr-2" />
                  Открыть спор
                </Button>
              ) : (
                <div className="p-4 bg-[#121212] border border-[#EF4444]/20 rounded-xl space-y-3">
                  <Textarea
                    value={disputeReason}
                    onChange={(e) => setDisputeReason(e.target.value)}
                    placeholder="Опишите проблему..."
                    className="bg-[#0A0A0A] border-white/10 text-white"
                    rows={3}
                  />
                  <div className="flex gap-2">
                    <Button
                      onClick={handleDispute}
                      disabled={actionLoading}
                      className="flex-1 bg-[#EF4444] hover:bg-[#DC2626]"
                    >
                      {actionLoading ? "Отправка..." : "Отправить спор"}
                    </Button>
                    <Button
                      onClick={() => setShowDisputeForm(false)}
                      variant="outline"
                     title="Отменить действие">
                      Отмена
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}

          {/* Seller waiting message */}
          {deal.status === "funded" && isSeller && (
            <div className="p-4 bg-[#3B82F6]/10 border border-[#3B82F6]/30 rounded-xl text-center">
              <Clock className="w-8 h-8 text-[#3B82F6] mx-auto mb-2" />
              <p className="text-[#3B82F6]">Ожидайте подтверждения от покупателя</p>
              <p className="text-sm text-[#71717A] mt-1">Выполните свою часть сделки</p>
            </div>
          )}

          {/* Completed message */}
          {deal.status === "completed" && (
            <div className="p-4 bg-[#10B981]/10 border border-[#10B981]/30 rounded-xl text-center">
              <CheckCircle className="w-8 h-8 text-[#10B981] mx-auto mb-2" />
              <p className="text-[#10B981] font-semibold">Сделка успешно завершена!</p>
              {isSeller && (
                <p className="text-sm text-[#71717A] mt-1">
                  Вы получили {(deal.amount - deal.commission).toFixed(2)} {deal.currency}
                </p>
              )}
            </div>
          )}

          {/* Disputed message */}
          {deal.status === "disputed" && (
            <div className="p-4 bg-[#EF4444]/10 border border-[#EF4444]/30 rounded-xl text-center">
              <AlertTriangle className="w-8 h-8 text-[#EF4444] mx-auto mb-2" />
              <p className="text-[#EF4444] font-semibold">Открыт спор</p>
              <p className="text-sm text-[#71717A] mt-1">
                Администратор рассмотрит вашу заявку в ближайшее время
              </p>
            </div>
          )}
        </div>

        {/* Back link */}
        <div className="mt-8 text-center">
          <Link to="/trader/guarantor" className="text-[#7C3AED] hover:text-[#A78BFA] text-sm">
            ← Вернуться к списку сделок
          </Link>
        </div>
      </main>
    </div>
  );
}
