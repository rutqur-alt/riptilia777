import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { 
  Book, Code, Copy, Check, Key, CreditCard, RefreshCw,
  ArrowRight, FileText, Zap, Shield, Clock
} from "lucide-react";

/**
 * API Documentation page for merchants
 */

export default function ApiDocs() {
  const [copiedCode, setCopiedCode] = useState(null);

  const copyToClipboard = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedCode(id);
    toast.success("Скопировано!");
    setTimeout(() => setCopiedCode(null), 2000);
  };

  const CodeBlock = ({ code, language = "javascript", id }) => (
    <div className="relative">
      <pre className="bg-slate-900 text-slate-100 p-4 rounded-xl text-sm overflow-x-auto">
        <code>{code}</code>
      </pre>
      <button
        onClick={() => copyToClipboard(code, id)}
        className="absolute top-2 right-2 p-2 bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors"
      >
        {copiedCode === id ? (
          <Check className="w-4 h-4 text-green-400" />
        ) : (
          <Copy className="w-4 h-4 text-slate-300" />
        )}
      </button>
    </div>
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Header */}
      <header className="border-b border-slate-700 bg-slate-900/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
              <Book className="w-6 h-6 text-white" />
            </div>
            <div>
              <div className="text-xl font-bold text-white">P2P Gateway API</div>
              <div className="text-xs text-slate-400">Документация v1.0</div>
            </div>
          </div>
          <a 
            href="/merchant/register"
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
          >
            Стать мерчантом
          </a>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8">
        {/* Intro */}
        <div className="mb-12">
          <h1 className="text-4xl font-bold text-white mb-4">
            Интеграция платёжного шлюза
          </h1>
          <p className="text-lg text-slate-300 mb-6">
            Принимайте платежи на вашем сайте через P2P обмен. Клиенты платят в рублях, 
            вы получаете USDT на баланс мерчанта.
          </p>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
              <Zap className="w-8 h-8 text-yellow-400 mb-3" />
              <div className="text-white font-medium">Быстрая интеграция</div>
              <div className="text-slate-400 text-sm">3 API-вызова для полного цикла</div>
            </div>
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
              <Shield className="w-8 h-8 text-green-400 mb-3" />
              <div className="text-white font-medium">Безопасность</div>
              <div className="text-slate-400 text-sm">API-ключ + webhook подтверждения</div>
            </div>
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
              <Clock className="w-8 h-8 text-blue-400 mb-3" />
              <div className="text-white font-medium">24/7 поддержка</div>
              <div className="text-slate-400 text-sm">Встроенная система диспутов</div>
            </div>
          </div>
        </div>

        {/* Authentication */}
        <section className="mb-12">
          <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-2">
            <Key className="w-6 h-6 text-blue-400" />
            Аутентификация
          </h2>
          
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 mb-4">
            <p className="text-slate-300 mb-4">
              Все API-запросы требуют заголовок <code className="bg-slate-700 px-2 py-1 rounded">X-API-Key</code> с вашим API-ключом.
            </p>
            
            <CodeBlock
              id="auth"
              code={`// Пример запроса с API-ключом
fetch('https://your-domain.com/api/v1/merchant/balance', {
  headers: {
    'X-API-Key': 'pk_live_ваш_api_ключ'
  }
})`}
            />
            
            <div className="mt-4 p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
              <div className="text-yellow-400 font-medium mb-1">⚠️ Важно</div>
              <div className="text-yellow-300/80 text-sm">
                Никогда не публикуйте API-ключ в клиентском коде. Все запросы должны идти с вашего сервера.
              </div>
            </div>
          </div>
        </section>

        {/* Endpoints */}
        <section className="mb-12">
          <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-2">
            <Code className="w-6 h-6 text-purple-400" />
            API Endpoints
          </h2>

          {/* Create Payment */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 mb-6">
            <div className="flex items-center gap-3 mb-4">
              <span className="px-3 py-1 bg-green-500 text-white text-xs font-bold rounded">POST</span>
              <code className="text-white">/api/v1/payment/create</code>
            </div>
            
            <p className="text-slate-300 mb-4">
              Создание платёжной ссылки. Возвращает URL для перенаправления клиента.
            </p>
            
            <h4 className="text-white font-medium mb-2">Параметры запроса:</h4>
            <div className="bg-slate-900 rounded-lg p-4 mb-4">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-slate-400 border-b border-slate-700">
                    <th className="text-left py-2">Параметр</th>
                    <th className="text-left py-2">Тип</th>
                    <th className="text-left py-2">Описание</th>
                  </tr>
                </thead>
                <tbody className="text-slate-300">
                  <tr className="border-b border-slate-800">
                    <td className="py-2"><code>amount_rub</code> *</td>
                    <td>number</td>
                    <td>Сумма в рублях (мин. 100)</td>
                  </tr>
                  <tr className="border-b border-slate-800">
                    <td className="py-2"><code>description</code></td>
                    <td>string</td>
                    <td>Описание платежа</td>
                  </tr>
                  <tr className="border-b border-slate-800">
                    <td className="py-2"><code>client_id</code></td>
                    <td>string</td>
                    <td>ID клиента в вашей системе</td>
                  </tr>
                  <tr>
                    <td className="py-2"><code>webhook_url</code></td>
                    <td>string</td>
                    <td>URL для уведомления о статусе</td>
                  </tr>
                </tbody>
              </table>
            </div>
            
            <h4 className="text-white font-medium mb-2">Пример:</h4>
            <CodeBlock
              id="create"
              code={`const response = await fetch('https://your-domain.com/api/v1/payment/create', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'pk_live_ваш_api_ключ'
  },
  body: JSON.stringify({
    amount_rub: 1000,
    description: 'Пополнение баланса',
    client_id: 'user_123',
    webhook_url: 'https://your-site.com/webhook/payment'
  })
});

const data = await response.json();
// {
//   "payment_id": "abc12345",
//   "payment_url": "/deposit/abc12345",
//   "amount_rub": 1000,
//   "amount_usdt": 10.0,
//   "status": "active",
//   "expires_at": "2024-01-20T12:00:00Z"
// }

// Перенаправьте клиента на payment_url
window.location.href = 'https://your-domain.com' + data.payment_url;`}
            />
          </div>

          {/* Check Status */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 mb-6">
            <div className="flex items-center gap-3 mb-4">
              <span className="px-3 py-1 bg-blue-500 text-white text-xs font-bold rounded">GET</span>
              <code className="text-white">/api/v1/payment/{"{payment_id}"}/status</code>
            </div>
            
            <p className="text-slate-300 mb-4">
              Проверка статуса платежа.
            </p>
            
            <h4 className="text-white font-medium mb-2">Ответ:</h4>
            <CodeBlock
              id="status"
              code={`{
  "payment_id": "abc12345",
  "amount_rub": 1000,
  "amount_usdt": 10.0,
  "status": "completed",      // active, completed, expired
  "trade_status": "completed", // pending, paid, completed, disputed
  "created_at": "2024-01-19T12:00:00Z"
}`}
            />
          </div>

          {/* Get Balance */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 mb-6">
            <div className="flex items-center gap-3 mb-4">
              <span className="px-3 py-1 bg-blue-500 text-white text-xs font-bold rounded">GET</span>
              <code className="text-white">/api/v1/merchant/balance</code>
            </div>
            
            <p className="text-slate-300 mb-4">
              Получение баланса мерчанта.
            </p>
            
            <CodeBlock
              id="balance"
              code={`{
  "balance_usdt": 150.50,
  "total_commission_paid": 5.25,
  "merchant_name": "Lucky Vegas",
  "merchant_type": "casino"
}`}
            />
          </div>

          {/* List Payments */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
            <div className="flex items-center gap-3 mb-4">
              <span className="px-3 py-1 bg-blue-500 text-white text-xs font-bold rounded">GET</span>
              <code className="text-white">/api/v1/payments</code>
            </div>
            
            <p className="text-slate-300 mb-4">
              Список всех платежей мерчанта.
            </p>
            
            <h4 className="text-white font-medium mb-2">Параметры:</h4>
            <div className="bg-slate-900 rounded-lg p-4 mb-4">
              <table className="w-full text-sm">
                <tbody className="text-slate-300">
                  <tr className="border-b border-slate-800">
                    <td className="py-2"><code>status</code></td>
                    <td>Фильтр по статусу (active, completed, expired)</td>
                  </tr>
                  <tr>
                    <td className="py-2"><code>limit</code></td>
                    <td>Количество записей (по умолчанию 50)</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* Flow */}
        <section className="mb-12">
          <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-2">
            <RefreshCw className="w-6 h-6 text-green-400" />
            Процесс оплаты
          </h2>
          
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
            <div className="space-y-4">
              <div className="flex items-start gap-4">
                <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white font-bold shrink-0">1</div>
                <div>
                  <div className="text-white font-medium">Создание платежа</div>
                  <div className="text-slate-400 text-sm">Ваш сервер вызывает POST /api/v1/payment/create</div>
                </div>
              </div>
              
              <div className="flex items-start gap-4">
                <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white font-bold shrink-0">2</div>
                <div>
                  <div className="text-white font-medium">Перенаправление клиента</div>
                  <div className="text-slate-400 text-sm">Клиент переходит на payment_url для оплаты</div>
                </div>
              </div>
              
              <div className="flex items-start gap-4">
                <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white font-bold shrink-0">3</div>
                <div>
                  <div className="text-white font-medium">Клиент выбирает оператора и оплачивает</div>
                  <div className="text-slate-400 text-sm">P2P перевод на реквизиты трейдера</div>
                </div>
              </div>
              
              <div className="flex items-start gap-4">
                <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white font-bold shrink-0">4</div>
                <div>
                  <div className="text-white font-medium">Трейдер подтверждает получение</div>
                  <div className="text-slate-400 text-sm">Статус меняется на completed</div>
                </div>
              </div>
              
              <div className="flex items-start gap-4">
                <div className="w-8 h-8 rounded-full bg-green-500 flex items-center justify-center text-white font-bold shrink-0">✓</div>
                <div>
                  <div className="text-white font-medium">USDT зачислен на баланс мерчанта</div>
                  <div className="text-slate-400 text-sm">Webhook уведомление (если настроен)</div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Support */}
        <section>
          <div className="bg-gradient-to-r from-blue-600/20 to-purple-600/20 border border-blue-500/30 rounded-xl p-6 text-center">
            <h3 className="text-xl font-bold text-white mb-2">Нужна помощь с интеграцией?</h3>
            <p className="text-slate-300 mb-4">
              Наша команда поможет настроить платёжный шлюз на вашем сайте
            </p>
            <a 
              href="https://t.me/p2pgateway_support"
              className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium transition-colors"
            >
              Написать в поддержку
              <ArrowRight className="w-4 h-4" />
            </a>
          </div>
        </section>
      </main>
    </div>
  );
}
