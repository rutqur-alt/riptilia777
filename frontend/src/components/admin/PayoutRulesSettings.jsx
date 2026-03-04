import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { TrendingUp, FileText, Loader, RefreshCw, Wifi, WifiOff } from "lucide-react";
import { useAuth, API } from "@/App";
import axios from "axios";
import { LoadingSpinner, PageHeader } from "@/components/admin/SharedComponents";

export function PayoutRulesSettings() {
  const { token } = useAuth();
  const [rules, setRules] = useState("");
  const [exchangeRate, setExchangeRate] = useState(96.5);
  const [markupPercent, setMarkupPercent] = useState(1); // Наценка в процентах
  const [minSuccessfulTrades, setMinSuccessfulTrades] = useState(20); // Минимум успешных сделок
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [liveRate, setLiveRate] = useState(null);
  const [refreshingRate, setRefreshingRate] = useState(false);

  // Рассчитываем курс продажи автоматически
  const sellRate = exchangeRate * (1 + markupPercent / 100);

  useEffect(() => { 
    fetchSettings(); 
    fetchLiveRate();
  }, []);

  const fetchSettings = async () => {
    try {
      const res = await axios.get(`${API}/admin/payout-settings`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setRules(res.data.rules || "");
      const baseRate = res.data.exchange_rate || res.data.base_rate || 96.5;
      setExchangeRate(baseRate);
      // Рассчитываем процент наценки из сохранённого sell_rate
      const savedSellRate = res.data.sell_rate || baseRate * 1.01;
      const calcMarkup = baseRate > 0 ? ((savedSellRate / baseRate) - 1) * 100 : 1;
      setMarkupPercent(Math.round(calcMarkup * 10) / 10); // Округляем до 1 знака
      // Минимум успешных сделок
      setMinSuccessfulTrades(res.data.min_successful_trades ?? 20);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const fetchLiveRate = async () => {
    try {
      const apiBase = API.replace("/api", "");
      const res = await axios.get(`${apiBase}/api/exchange-rate`);
      setLiveRate(res.data);
    } catch (e) {
      console.error("Live rate error:", e);
    }
  };

  const refreshRateFromExchange = async () => {
    setRefreshingRate(true);
    try {
      const res = await axios.post(`${API.replace("/api", "")}/api/exchange-rate/refresh`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.data.success) {
        setLiveRate({ ...liveRate, base_rate: res.data.rate, rate_source: res.data.cached?.source, rate_updated_at: res.data.cached?.updated_at });
        setExchangeRate(res.data.rate);
        toast.success("Курс обновлен: " + res.data.rate + " RUB/USDT (" + (res.data.cached?.source || "Rapira") + ")");
      }
    } catch (e) {
      toast.error("Ошибка обновления курса с биржи");
    } finally {
      setRefreshingRate(false);
    }
  };

  const applyLiveRate = () => {
    if (liveRate?.base_rate) {
      setExchangeRate(liveRate.base_rate);
      toast.success("Базовый курс установлен: " + liveRate.base_rate + " RUB/USDT");
    }
  };

  const saveSettings = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/admin/payout-settings`, 
        { rules, exchange_rate: exchangeRate, sell_rate: sellRate, markup_percent: markupPercent, min_successful_trades: minSuccessfulTrades },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(`Настройки сохранены: курс продажи ${sellRate.toFixed(2)} ₽/USDT, мин. сделок: ${minSuccessfulTrades}`);
    } catch (e) {
      toast.error("Ошибка сохранения");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-6" data-testid="payout-rules-settings">
      <PageHeader title="Правила выплат" subtitle="Настройки курса и правила для покупки криптовалюты" />
      
      {/* Live Exchange Rate from Rapira */}
      <div className="bg-gradient-to-r from-[#1E3A5F] to-[#0F172A] border border-[#3B82F6]/20 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-white font-semibold flex items-center gap-2">
            {liveRate ? <Wifi className="w-5 h-5 text-[#10B981]" /> : <WifiOff className="w-5 h-5 text-[#EF4444]" />}
            Курс биржи (живой)
          </h3>
          <Button 
            onClick={refreshRateFromExchange} 
            disabled={refreshingRate}
            variant="outline" 
            size="sm" 
            className="border-[#3B82F6]/30 text-[#3B82F6] hover:bg-[#3B82F6]/10"
            title="Обновить курс с биржи"
          >
            <RefreshCw className={"w-4 h-4 mr-2" + (refreshingRate ? " animate-spin" : "")} />
            Обновить с биржи
          </Button>
        </div>
        
        {liveRate ? (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-[#0A0A0A]/50 rounded-lg p-4">
              <div className="text-[#71717A] text-xs mb-1">Базовый курс (биржа)</div>
              <div className="text-2xl font-bold text-[#3B82F6] font-['JetBrains_Mono']">
                {liveRate.base_rate?.toFixed(2)} P
              </div>
            </div>
            <div className="bg-[#0A0A0A]/50 rounded-lg p-4">
              <div className="text-[#71717A] text-xs mb-1">Курс продажи</div>
              <div className="text-2xl font-bold text-[#10B981] font-['JetBrains_Mono']">
                {liveRate.sell_rate?.toFixed(2)} P
              </div>
            </div>
            <div className="bg-[#0A0A0A]/50 rounded-lg p-4">
              <div className="text-[#71717A] text-xs mb-1">Источник</div>
              <div className="text-lg font-bold text-white">{liveRate.rate_source || "\u2014"}</div>
              <div className="text-[#52525B] text-xs">Обновление каждые 5 мин</div>
            </div>
            <div className="bg-[#0A0A0A]/50 rounded-lg p-4">
              <div className="text-[#71717A] text-xs mb-1">Последнее обновление</div>
              <div className="text-lg font-bold text-white">
                {liveRate.rate_updated_at ? new Date(liveRate.rate_updated_at).toLocaleTimeString("ru-RU") : "\u2014"}
              </div>
              <div className="text-[#52525B] text-xs">
                {liveRate.rate_updated_at ? new Date(liveRate.rate_updated_at).toLocaleDateString("ru-RU") : ""}
              </div>
            </div>
          </div>
        ) : (
          <div className="text-[#71717A] text-center py-4">
            Загрузка курса с биржи...
          </div>
        )}
        
        <div className="mt-4 p-3 bg-[#0A0A0A]/30 rounded-lg border border-white/5">
          <div className="flex items-center gap-2 text-xs text-[#71717A]">
            <div className="w-2 h-2 bg-[#10B981] rounded-full animate-pulse" />
            Базовый курс USDT/RUB автоматически подтягивается с биржи Rapira каждые 5 минут и используется как основа для расчёта курсов мерчантов
          </div>
        </div>
      </div>

      {/* Manual Rate Settings */}
      <div className="bg-[#121212] border border-white/5 rounded-xl p-6">
        <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-[#F97316]" />
          Настройки курсов
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="text-[#71717A] text-xs mb-1 block">Базовый курс USDT/RUB</label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                step="0.01"
                value={exchangeRate}
                onChange={(e) => setExchangeRate(parseFloat(e.target.value) || 0)}
                className="flex-1 bg-[#0A0A0A] border border-white/10 rounded-lg px-3 py-2 text-white font-mono"
              />
              <span className="text-[#71717A]">₽</span>
              {liveRate?.base_rate && liveRate.base_rate !== exchangeRate && (
                <Button 
                  onClick={applyLiveRate} 
                  variant="outline" 
                  size="sm" 
                  className="border-[#3B82F6]/30 text-[#3B82F6] text-xs"
                  title="Применить курс с биржи"
                >
                  Применить {liveRate.base_rate?.toFixed(2)} ₽
                </Button>
              )}
            </div>
            <p className="text-[#52525B] text-xs mt-1">
              Курс по которому мерчант отдаёт USDT (автоматически обновляется с биржи)
            </p>
          </div>
          <div>
            <label className="text-[#71717A] text-xs mb-1 block">Наценка платформы</label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                step="0.1"
                min="0"
                max="100"
                value={markupPercent}
                onChange={(e) => setMarkupPercent(parseFloat(e.target.value) || 0)}
                className="w-24 bg-[#0A0A0A] border border-white/10 rounded-lg px-3 py-2 text-white font-mono"
              />
              <span className="text-[#71717A]">%</span>
              <div className="flex-1 text-right">
                <span className="text-[#71717A] text-sm">Курс продажи: </span>
                <span className="text-[#10B981] font-bold font-mono">{sellRate.toFixed(2)} ₽</span>
              </div>
            </div>
            <p className="text-[#52525B] text-xs mt-1">
              Наценка добавляется к базовому курсу = курс продажи для покупателя
            </p>
          </div>
        </div>
        <div className="mt-4 p-3 bg-[#0A0A0A] rounded-lg border border-white/5">
          <div className="text-xs text-[#71717A]">
            <span className="text-white font-medium">Итого:</span> Базовый {exchangeRate.toFixed(2)} ₽ + {markupPercent}% = <span className="text-[#10B981] font-bold">{sellRate.toFixed(2)} ₽/USDT</span> (прибыль платформы: {(sellRate - exchangeRate).toFixed(2)} ₽ за 1 USDT)
          </div>
        </div>
      </div>

      {/* Minimum Successful Trades */}
      <div className="bg-[#121212] border border-white/5 rounded-xl p-6">
        <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
          <FileText className="w-5 h-5 text-[#F59E0B]" />
          Требования к покупателям
        </h3>
        <div>
          <label className="text-[#71717A] text-xs mb-1 block">Минимум успешных сделок для покупки криптовалюты</label>
          <div className="flex items-center gap-3">
            <input
              type="number"
              step="1"
              min="0"
              max="1000"
              value={minSuccessfulTrades}
              onChange={(e) => setMinSuccessfulTrades(parseInt(e.target.value) || 0)}
              className="w-32 bg-[#0A0A0A] border border-white/10 rounded-lg px-3 py-2 text-white font-mono text-lg"
            />
            <span className="text-[#71717A]">сделок</span>
          </div>
          <p className="text-[#52525B] text-xs mt-2">
            Пользователь должен совершить указанное количество успешных P2P сделок на платформе, прежде чем сможет покупать криптовалюту
          </p>
        </div>
      </div>

      {/* Rules Text */}
      <div className="bg-[#121212] border border-white/5 rounded-xl p-6">
        <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
          <FileText className="w-5 h-5 text-[#3B82F6]" />
          Правила покупки
        </h3>
        <p className="text-[#71717A] text-sm mb-4">
          Этот текст будет показан покупателю перед совершением покупки. Он должен принять правила для продолжения.
        </p>
        <textarea
          value={rules}
          onChange={(e) => setRules(e.target.value)}
          placeholder="Введите правила покупки криптовалюты..."
          rows={12}
          className="w-full bg-[#0A0A0A] border border-white/10 rounded-lg px-4 py-3 text-white text-sm resize-none"
        />
        <p className="text-[#52525B] text-xs mt-2">
          Поддерживается форматирование: **жирный**, *курсив*, - списки
        </p>
      </div>

      {/* Preview */}
      <div className="bg-[#121212] border border-white/5 rounded-xl p-6">
        <h3 className="text-white font-semibold mb-4">Предпросмотр</h3>
        <div className="bg-[#0A0A0A] border border-[#3B82F6]/20 rounded-lg p-4 max-h-64 overflow-y-auto">
          <pre className="text-white text-sm whitespace-pre-wrap font-sans">
            {rules || "Правила не заданы"}
          </pre>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end">
        <Button 
          onClick={saveSettings} 
          disabled={saving}
          className="bg-[#10B981] hover:bg-[#059669] text-white px-8"
          title="Сохранить изменения">
          {saving ? <Loader className="w-4 h-4 animate-spin mr-2" /> : null}
          Сохранить настройки
        </Button>
      </div>
    </div>
  );
}

export default PayoutRulesSettings;
