import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Wallet, ArrowLeft, Shield, Users, CreditCard, CheckCircle, AlertTriangle, Percent, Package, Handshake, Lock, ArrowRight } from "lucide-react";

export default function Guarantor() {
  const steps = [
    {
      number: "01",
      icon: <Handshake className="w-6 h-6" />,
      title: "Договорённость",
      description: "Покупатель и продавец договариваются о сделке в любом месте: мессенджер, форум, лично. Они уже знают сумму, условия и друг друга."
    },
    {
      number: "02",
      icon: <Package className="w-6 h-6" />,
      title: "Создание сделки",
      description: "Один из участников создаёт сделку на платформе: указывает сумму, валюту, описание и условия выполнения. Второй участник подтверждает согласие."
    },
    {
      number: "03",
      icon: <Lock className="w-6 h-6" />,
      title: "Оплата гаранту",
      description: "Покупатель переводит криптовалюту НЕ продавцу, а на платформу. Деньги замораживаются и находятся у гаранта до завершения сделки."
    },
    {
      number: "04",
      icon: <CheckCircle className="w-6 h-6" />,
      title: "Выполнение и подтверждение",
      description: "Продавец выполняет свою часть сделки. Покупатель проверяет и нажимает «Подтвердить». Платформа удерживает 5% комиссии и переводит 95% продавцу."
    }
  ];

  const useCases = [
    { icon: "🛒", title: "Товары", description: "Покупка любых товаров у незнакомых продавцов" },
    { icon: "💼", title: "Услуги", description: "Фриланс, консультации, работа" },
    { icon: "🎮", title: "Аккаунты", description: "Игровые аккаунты, подписки, лицензии" },
    { icon: "📱", title: "Цифровые товары", description: "Софт, курсы, дизайн, контент" },
    { icon: "📢", title: "Реклама", description: "Размещение рекламы, промо" },
    { icon: "🤝", title: "Любые сделки", description: "Любые личные договорённости" }
  ];

  return (
    <div className="min-h-screen bg-[#0A0A0A]">
      {/* Header */}
      <header className="border-b border-white/5">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <div className="flex items-center gap-4">
            <Link to="/">
              <Button variant="ghost" size="icon" className="text-[#A1A1AA] hover:text-white hover:bg-white/5">
                <ArrowLeft className="w-5 h-5" />
              </Button>
            </Link>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-[#7C3AED] flex items-center justify-center">
                <Wallet className="w-4 h-4 text-white" />
              </div>
              <span className="text-lg font-semibold text-white">Гарант-сервис</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-4xl mx-auto px-4 py-8">
        {/* Hero */}
        <div className="text-center mb-12">
          <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-[#7C3AED] to-[#A78BFA] flex items-center justify-center mx-auto mb-6 shadow-lg shadow-[#7C3AED]/20">
            <Shield className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-3xl md:text-4xl font-bold text-white mb-4">
            Безопасные сделки с гарантом
          </h1>
          <p className="text-[#71717A] max-w-2xl mx-auto text-lg">
            Платформа выступает независимым посредником между покупателем и продавцом. 
            Мы гарантируем честный расчёт для любых сделок.
          </p>
        </div>

        {/* Commission highlight */}
        <div className="bg-gradient-to-r from-[#7C3AED]/20 to-[#A78BFA]/10 border border-[#7C3AED]/30 rounded-2xl p-6 mb-10 text-center">
          <div className="flex items-center justify-center gap-3 mb-2">
            <Percent className="w-6 h-6 text-[#A78BFA]" />
            <span className="text-2xl font-bold text-white">Комиссия 5%</span>
          </div>
          <p className="text-[#A1A1AA]">
            Удерживается автоматически только с успешно завершённых сделок
          </p>
        </div>

        {/* 3 parties */}
        <div className="grid md:grid-cols-3 gap-4 mb-12">
          <div className="bg-[#121212] border border-white/5 rounded-xl p-5 text-center">
            <div className="w-12 h-12 rounded-full bg-[#10B981]/10 flex items-center justify-center mx-auto mb-3">
              <Users className="w-6 h-6 text-[#10B981]" />
            </div>
            <h3 className="text-white font-medium mb-1">Покупатель</h3>
            <p className="text-[#71717A] text-sm">Переводит деньги гаранту, получает товар/услугу</p>
          </div>
          <div className="bg-[#121212] border border-white/5 rounded-xl p-5 text-center">
            <div className="w-12 h-12 rounded-full bg-[#3B82F6]/10 flex items-center justify-center mx-auto mb-3">
              <Users className="w-6 h-6 text-[#3B82F6]" />
            </div>
            <h3 className="text-white font-medium mb-1">Продавец</h3>
            <p className="text-[#71717A] text-sm">Выполняет условия, получает 95% от суммы</p>
          </div>
          <div className="bg-[#121212] border border-[#7C3AED]/30 rounded-xl p-5 text-center">
            <div className="w-12 h-12 rounded-full bg-[#7C3AED]/10 flex items-center justify-center mx-auto mb-3">
              <Shield className="w-6 h-6 text-[#7C3AED]" />
            </div>
            <h3 className="text-white font-medium mb-1">Платформа-гарант</h3>
            <p className="text-[#71717A] text-sm">Держит деньги, контролирует сделку</p>
          </div>
        </div>

        {/* How it works - Steps */}
        <div className="mb-12">
          <h2 className="text-xl font-semibold text-white mb-6 flex items-center gap-2">
            <ArrowRight className="w-5 h-5 text-[#7C3AED]" />
            Как проходит сделка
          </h2>
          
          <div className="space-y-4">
            {steps.map((step, index) => (
              <div 
                key={index}
                data-testid={`guarantor-step-${index}`}
                className="bg-[#121212] border border-white/5 rounded-xl p-5 flex gap-4"
              >
                <div className="flex-shrink-0">
                  <div className="w-14 h-14 rounded-xl bg-[#7C3AED]/10 flex items-center justify-center">
                    <span className="text-[#7C3AED] font-bold text-lg">{step.number}</span>
                  </div>
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-[#7C3AED]">{step.icon}</span>
                    <h3 className="text-white font-medium">{step.title}</h3>
                  </div>
                  <p className="text-[#71717A] text-sm">{step.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Example calculation */}
        <div className="bg-[#121212] border border-white/5 rounded-xl p-6 mb-12">
          <h3 className="text-white font-medium mb-4 flex items-center gap-2">
            <CreditCard className="w-5 h-5 text-[#10B981]" />
            Пример расчёта
          </h3>
          <div className="grid md:grid-cols-3 gap-4 text-center">
            <div className="bg-[#0A0A0A] rounded-lg p-4">
              <div className="text-2xl font-bold text-white mb-1">1000 USDT</div>
              <div className="text-sm text-[#71717A]">Сумма сделки</div>
            </div>
            <div className="bg-[#7C3AED]/10 rounded-lg p-4">
              <div className="text-2xl font-bold text-[#A78BFA] mb-1">50 USDT</div>
              <div className="text-sm text-[#71717A]">Комиссия (5%)</div>
            </div>
            <div className="bg-[#10B981]/10 rounded-lg p-4">
              <div className="text-2xl font-bold text-[#10B981] mb-1">950 USDT</div>
              <div className="text-sm text-[#71717A]">Получает продавец</div>
            </div>
          </div>
        </div>

        {/* Use cases */}
        <div className="mb-12">
          <h2 className="text-xl font-semibold text-white mb-6 flex items-center gap-2">
            <Package className="w-5 h-5 text-[#10B981]" />
            Для каких сделок подходит
          </h2>
          
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {useCases.map((item, index) => (
              <div 
                key={index}
                className="bg-[#121212] border border-white/5 rounded-xl p-4 hover:border-white/10 transition-colors"
              >
                <span className="text-2xl mb-2 block">{item.icon}</span>
                <h3 className="text-white font-medium text-sm mb-1">{item.title}</h3>
                <p className="text-[#52525B] text-xs">{item.description}</p>
              </div>
            ))}
          </div>
          
          <p className="text-center text-[#52525B] text-sm mt-4">
            Платформа не ограничивает тип сделок — мы гарантируем честный расчёт
          </p>
        </div>

        {/* Dispute resolution */}
        <div className="bg-[#121212] border border-[#F59E0B]/20 rounded-xl p-6 mb-10">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 rounded-lg bg-[#F59E0B]/10 flex items-center justify-center flex-shrink-0">
              <AlertTriangle className="w-5 h-5 text-[#F59E0B]" />
            </div>
            <div>
              <h3 className="text-white font-medium mb-2">Если что-то пошло не так</h3>
              <p className="text-[#71717A] text-sm mb-4">
                Любой участник может открыть спор. Деньги остаются замороженными, 
                пока администратор не разберётся в ситуации.
              </p>
              <div className="space-y-2 text-sm">
                <div className="flex items-center gap-2 text-[#71717A]">
                  <CheckCircle className="w-4 h-4 text-[#10B981]" />
                  Вернуть деньги покупателю
                </div>
                <div className="flex items-center gap-2 text-[#71717A]">
                  <CheckCircle className="w-4 h-4 text-[#10B981]" />
                  Отправить продавцу
                </div>
                <div className="flex items-center gap-2 text-[#71717A]">
                  <CheckCircle className="w-4 h-4 text-[#10B981]" />
                  Разделить сумму
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Why use */}
        <div className="bg-gradient-to-r from-[#1A1A1A] to-[#121212] border border-white/5 rounded-xl p-6 mb-10">
          <h3 className="text-white font-medium mb-4">Зачем нужен гарант?</h3>
          <div className="grid md:grid-cols-2 gap-4">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-[#EF4444]/10 flex items-center justify-center flex-shrink-0">
                <span className="text-[#EF4444]">✕</span>
              </div>
              <div>
                <div className="text-white text-sm font-medium">Без гаранта</div>
                <div className="text-[#52525B] text-xs">Риск обмана, потеря денег, нет защиты</div>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-[#10B981]/10 flex items-center justify-center flex-shrink-0">
                <CheckCircle className="w-4 h-4 text-[#10B981]" />
              </div>
              <div>
                <div className="text-white text-sm font-medium">С гарантом</div>
                <div className="text-[#52525B] text-xs">Деньги защищены, независимый арбитр</div>
              </div>
            </div>
          </div>
        </div>

        {/* CTA */}
        <div className="text-center">
          <Link to="/guarantor/create">
            <Button 
              data-testid="guarantor-start-btn"
              className="bg-[#7C3AED] hover:bg-[#6D28D9] text-white rounded-xl h-12 px-10 text-lg"
             title="Создать новую сделку">
              Создать сделку
            </Button>
          </Link>
          <p className="text-[#52525B] text-sm mt-3">
            Безопасно • Быстро • 5% комиссия
          </p>
        </div>
      </main>
    </div>
  );
}
