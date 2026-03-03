import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { useAuth, API } from '@/App';
import axios from 'axios';
import { Copy, RefreshCw, Code, Key, Shield, ExternalLink, Eye, EyeOff } from 'lucide-react';

const MerchantAPI = () => {
  const { user, token } = useAuth();
  const [merchant, setMerchant] = useState(null);
  const [loading, setLoading] = useState(true);
  const [regeneratingApi, setRegeneratingApi] = useState(false);
  const [regeneratingSecret, setRegeneratingSecret] = useState(false);
  const [showSecret, setShowSecret] = useState(false);

  useEffect(() => {
    fetchMerchant();
  }, []);

  const fetchMerchant = async () => {
    try {
      const res = await axios.get(`${API}/merchant/profile`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setMerchant(res.data);
    } catch (error) {
      toast.error('Ошибка загрузки профиля');
    } finally {
      setLoading(false);
    }
  };

  const regenerateApiKey = async () => {
    if (!window.confirm('Вы уверены? Старый API ключ перестанет работать.')) return;
    
    setRegeneratingApi(true);
    try {
      const res = await axios.post(`${API}/merchant/regenerate-api-key`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setMerchant(prev => ({ ...prev, api_key: res.data.api_key }));
      toast.success('API ключ обновлён');
    } catch (error) {
      toast.error('Ошибка обновления ключа');
    } finally {
      setRegeneratingApi(false);
    }
  };

  const regenerateSecretKey = async () => {
    if (!window.confirm('Вы уверены? Старый Secret ключ перестанет работать. Все подписи нужно будет пересчитать.')) return;
    
    setRegeneratingSecret(true);
    try {
      const res = await axios.post(`${API}/merchant/regenerate-secret-key`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setMerchant(prev => ({ ...prev, api_secret: res.data.secret_key }));
      toast.success('Secret ключ обновлён');
    } catch (error) {
      toast.error('Ошибка обновления ключа');
    } finally {
      setRegeneratingSecret(false);
    }
  };

  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text);
    toast.success(`${label} скопирован`);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="animate-spin w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  // Домен платформы для документации
  const BASE_URL = window.location.origin;

  const signatureExample = `import hmac
import hashlib

def generate_signature(params: dict, secret_key: str) -> str:
    """
    Генерация HMAC-SHA256 подписи для Reptiloid API
    
    ВАЖНО! Для /v1/invoice/create в подпись входят ТОЛЬКО эти поля:
    - merchant_id, order_id, amount, currency, user_id, callback_url
    
    Поле description НЕ участвует в подписи!
    
    Алгоритм:
    1. Берём только разрешённые поля
    2. Убираем sign и None значения
    3. ВАЖНО: float приводим к int если число целое (1500.0 → 1500)
    4. Сортируем по ключам
    5. Формируем строку key=value&key2=value2
    6. Добавляем secret_key в конец
    7. Вычисляем HMAC-SHA256
    """
    SIGN_FIELDS = ['merchant_id', 'order_id', 'amount', 'currency', 'user_id', 'callback_url']
    
    sign_params = {}
    for k, v in params.items():
        if k not in SIGN_FIELDS or k == 'sign' or v is None:
            continue
        if isinstance(v, float) and v == int(v):
            v = int(v)
        sign_params[k] = v
    
    sorted_params = sorted(sign_params.items())
    sign_string = '&'.join(f"{k}={v}" for k, v in sorted_params)
    sign_string += secret_key
    
    return hmac.new(
        secret_key.encode('utf-8'),
        sign_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()`;

  const createInvoiceExample = `import requests

API_KEY = "${merchant?.api_key || 'YOUR_API_KEY'}"
SECRET_KEY = "${merchant?.api_secret || 'YOUR_SECRET_KEY'}"
MERCHANT_ID = "${merchant?.id || 'YOUR_MERCHANT_ID'}"
BASE_URL = "${BASE_URL}/api/v1/invoice"

def generate_signature(params: dict, secret_key: str) -> str:
    """Генерация HMAC-SHA256 подписи"""
    import hmac, hashlib
    SIGN_FIELDS = ['merchant_id', 'order_id', 'amount', 'currency', 'user_id', 'callback_url']
    
    sign_params = {}
    for k, v in params.items():
        if k not in SIGN_FIELDS or k == 'sign' or v is None:
            continue
        if isinstance(v, float) and v == int(v):
            v = int(v)
        sign_params[k] = v
    
    sorted_params = sorted(sign_params.items())
    sign_string = '&'.join(f"{k}={v}" for k, v in sorted_params)
    sign_string += secret_key
    
    return hmac.new(secret_key.encode(), sign_string.encode(), hashlib.sha256).hexdigest()

def create_invoice(order_id: str, amount: int, callback_url: str, user_id: str = None):
    """
    Создание инвойса на оплату
    
    После создания инвойса покупатель перейдёт на страницу payment_url,
    где сам выберет оператора и способ оплаты из доступных вариантов.
    """
    params = {
        "merchant_id": MERCHANT_ID,
        "order_id": order_id,
        "amount": amount,  # Сумма в рублях (целое число!)
        "currency": "RUB",
        "callback_url": callback_url,
        "user_id": user_id
    }
    params["sign"] = generate_signature(params, SECRET_KEY)
    params["description"] = "Оплата заказа"  # Добавляем ПОСЛЕ подписи
    
    response = requests.post(
        f"{BASE_URL}/create",
        json=params,
        headers={"X-Api-Key": API_KEY, "Content-Type": "application/json"}
    )
    return response.json()

# Пример использования:
result = create_invoice(
    order_id="ORDER_12345",
    amount=1500,  # 1500 рублей
    callback_url="https://mysite.com/payment/callback"
)

# Ответ:
# {
#   "status": "success",
#   "payment_id": "inv_...",
#   "payment_url": "${BASE_URL}/select-operator/inv_..."
# }

# Открываем страницу оплаты в новой вкладке:
# window.open(result["payment_url"], "_blank")
#
# Покупатель увидит список операторов, выберет оператора и способ оплаты,
# затем увидит реквизиты и оплатит.`;

  const jsIntegrationExample = `// JavaScript пример для вашего сайта

const API_KEY = '${merchant?.api_key || 'YOUR_API_KEY'}';
const SECRET_KEY = '${merchant?.api_secret || 'YOUR_SECRET_KEY'}';
const MERCHANT_ID = '${merchant?.id || 'YOUR_MERCHANT_ID'}';
const API_BASE = '${BASE_URL}/api/v1/invoice';

// Поля которые участвуют в подписи
const SIGN_FIELDS = ['merchant_id', 'order_id', 'amount', 'currency', 'user_id', 'callback_url'];

/**
 * Генерация подписи для Reptiloid API
 */
function generateSignature(params, secretKey) {
  const signParams = {};
  
  for (const [key, value] of Object.entries(params)) {
    if (!SIGN_FIELDS.includes(key) || key === 'sign' || value === null || value === undefined) {
      continue;
    }
    let v = value;
    if (typeof v === 'number' && Number.isInteger(v)) {
      v = Math.floor(v);
    }
    signParams[key] = v;
  }
  
  const sortedKeys = Object.keys(signParams).sort();
  const signString = sortedKeys.map(k => \`\${k}=\${signParams[k]}\`).join('&') + secretKey;
  
  // Используйте crypto-js
  return CryptoJS.HmacSHA256(signString, secretKey).toString();
}

/**
 * Создание платежа
 * После создания откройте payment_url в новой вкладке.
 * Покупатель сам выберет оператора и способ оплаты.
 */
async function createPayment(amount, description = 'Оплата заказа') {
  const orderId = 'ORDER_' + Date.now();
  
  const params = {
    merchant_id: MERCHANT_ID,
    order_id: orderId,
    amount: Math.floor(amount), // Целое число в рублях
    currency: 'RUB',
    callback_url: 'https://yoursite.com/callback',
    user_id: null
  };
  params.sign = generateSignature(params, SECRET_KEY);
  params.description = description; // После подписи
  
  const res = await fetch(\`\${API_BASE}/create\`, {
    method: 'POST',
    headers: { 'X-Api-Key': API_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  
  const data = await res.json();
  
  if (data.status === 'success') {
    // Открываем страницу оплаты в новой вкладке
    // Покупатель увидит список операторов и выберет подходящего
    window.open(data.payment_url, '_blank');
  }
  
  return { orderId, paymentId: data.payment_id };
}

// Пример использования:
// При нажатии кнопки "Оплатить" на вашем сайте
document.getElementById('payButton').onclick = async () => {
  const amount = 1500; // Сумма в рублях
  const { orderId, paymentId } = await createPayment(amount);
  
  // Сохраните orderId для проверки статуса
  console.log('Создан платёж:', paymentId);
};`;

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">API Интеграция</h1>
        <p className="text-zinc-400 text-sm">Invoice API v1 - Приём рублевых платежей через p2p USDT</p>
      </div>

      {/* API Keys */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* API Key */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Key className="w-5 h-5 text-emerald-400" />
              API Key
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm text-zinc-400">Используется в заголовке X-Api-Key</label>
              <div className="flex gap-2">
                <div className="flex-1 bg-zinc-950 rounded-lg px-4 py-3 font-mono text-sm border border-zinc-800 truncate">
                  {merchant?.api_key}
                </div>
                <Button 
                  variant="outline" 
                  size="icon"
                  className="border-zinc-700 shrink-0"
                  title="Скопировать"
                  onClick={() => copyToClipboard(merchant?.api_key, 'API Key')}
                  data-testid="copy-api-key"
                >
                  <Copy className="w-4 h-4" />
                </Button>
              </div>
            </div>

            <Button 
              variant="outline" 
              size="sm"
              className="border-orange-500/50 text-orange-400 hover:bg-orange-500/10"
              onClick={regenerateApiKey}
              disabled={regeneratingApi}
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${regeneratingApi ? 'animate-spin' : ''}`} />
              Перегенерировать
            </Button>
          </CardContent>
        </Card>

        {/* Secret Key */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Shield className="w-5 h-5 text-blue-400" />
              Secret Key
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm text-zinc-400">Для генерации подписи (HMAC-SHA256)</label>
              <div className="flex gap-2">
                <div className="flex-1 bg-zinc-950 rounded-lg px-4 py-3 font-mono text-sm border border-zinc-800 truncate">
                  {showSecret 
                    ? (merchant?.api_secret || 'Не установлен')
                    : '••••••••••••••••••••••••••••••••'
                  }
                </div>
                <Button 
                  variant="outline" 
                  size="icon"
                  className="border-zinc-700 shrink-0"
                  onClick={() => setShowSecret(!showSecret)}
                >
                  {showSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </Button>
                <Button 
                  variant="outline" 
                  size="icon"
                  className="border-zinc-700 shrink-0"
                  title="Скопировать"
                  onClick={() => copyToClipboard(merchant?.api_secret, 'Secret Key')}
                  data-testid="copy-secret-key"
                >
                  <Copy className="w-4 h-4" />
                </Button>
              </div>
              <p className="text-xs text-red-400">
                ⚠️ Никогда не передавайте Secret Key в запросах!
              </p>
            </div>

            <Button 
              variant="outline" 
              size="sm"
              className="border-orange-500/50 text-orange-400 hover:bg-orange-500/10"
              onClick={regenerateSecretKey}
              disabled={regeneratingSecret}
              data-testid="regenerate-secret-key"
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${regeneratingSecret ? 'animate-spin' : ''}`} />
              Перегенерировать
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Merchant ID */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardContent className="py-4">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-sm text-zinc-400">Merchant ID:</span>
              <span className="ml-2 font-mono text-emerald-400">{merchant?.id}</span>
            </div>
            <Button 
              variant="ghost" 
              size="sm"
              onClick={() => copyToClipboard(merchant?.id, 'Merchant ID')}
            >
              <Copy className="w-4 h-4" />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* API Endpoints */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg">Invoice API v1 - Endpoints</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[
              { method: 'GET', path: '/api/v1/invoice/payment-methods', desc: 'Получить способы оплаты' },
              { method: 'POST', path: '/api/v1/invoice/create', desc: 'Создать инвойс на оплату' },
              { method: 'GET', path: '/api/v1/invoice/status', desc: 'Проверить статус платежа' },
              { method: 'GET', path: '/api/v1/invoice/transactions', desc: 'Список всех транзакций' },
              { method: 'GET', path: '/api/v1/invoice/docs', desc: 'Документация API (JSON)' },
            ].map((endpoint, idx) => (
              <div key={idx} className="flex items-center gap-4 p-3 bg-zinc-800/50 rounded-lg">
                <span className={`px-2 py-1 rounded text-xs font-bold font-mono ${
                  endpoint.method === 'POST' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-blue-500/20 text-blue-400'
                }`}>
                  {endpoint.method}
                </span>
                <code className="font-mono text-sm text-zinc-300 flex-1">
                  {endpoint.path}
                </code>
                <span className="text-sm text-zinc-500">{endpoint.desc}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Integration Flow - IMPORTANT */}
      <Card className="bg-gradient-to-r from-blue-500/10 to-emerald-500/10 border-blue-500/30">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <ExternalLink className="w-5 h-5 text-blue-400" />
            Как интегрировать на свой сайт
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-3">
            <div className="flex gap-3 items-start">
              <span className="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-sm font-bold shrink-0">1</span>
              <p className="text-sm text-zinc-300"><code className="bg-zinc-800 px-1 rounded">POST /create</code> — создайте инвойс на сумму в RUB</p>
            </div>
            <div className="flex gap-3 items-start">
              <span className="w-6 h-6 rounded-full bg-orange-500/20 text-orange-400 flex items-center justify-center text-sm font-bold shrink-0">2</span>
              <p className="text-sm text-zinc-300"><strong className="text-orange-400">window.open(payment_url, '_blank')</strong> — откройте страницу оплаты <strong>в новой вкладке</strong></p>
            </div>
            <div className="flex gap-3 items-start">
              <span className="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-sm font-bold shrink-0">3</span>
              <p className="text-sm text-zinc-300">Покупатель выбирает оператора из списка (методы оплаты видны в карточках)</p>
            </div>
            <div className="flex gap-3 items-start">
              <span className="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-sm font-bold shrink-0">4</span>
              <p className="text-sm text-zinc-300">Покупатель видит реквизиты, оплачивает, нажимает "Я оплатил"</p>
            </div>
            <div className="flex gap-3 items-start">
              <span className="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-sm font-bold shrink-0">5</span>
              <p className="text-sm text-zinc-300">Получите <strong>webhook</strong> или проверяйте статус через <code className="bg-zinc-800 px-1 rounded">GET /status</code></p>
            </div>
          </div>
          
          <div className="bg-orange-500/10 border border-orange-500/20 rounded-lg p-3 mt-4">
            <p className="text-sm text-orange-300 font-medium">⚠️ Важно:</p>
            <ul className="text-sm text-zinc-400 mt-1 space-y-1">
              <li>• <code className="bg-zinc-800 px-1 rounded">payment_url</code> всегда открывайте в <strong>новой вкладке</strong></li>
              <li>• Покупатель выбирает оператора и метод оплаты на нашей странице</li>
              <li>• Чат для споров тоже на нашем домене</li>
            </ul>
          </div>
        </CardContent>
      </Card>

      {/* UI Example - Select Operator */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <ExternalLink className="w-5 h-5 text-purple-400" />
            Пример UI: Выбор оператора
          </CardTitle>
          <p className="text-sm text-zinc-400 mt-1">Покупатель выбирает оператора из списка. Методы оплаты видны в карточках.</p>
        </CardHeader>
        <CardContent>
          <img 
            src="https://customer-assets.emergentagent.com/job_fbca4ceb-9112-496d-8675-a1b10145ddee/artifacts/wjkjx2ei_image.png"
            alt="Выбор оператора"
            className="rounded-lg border border-zinc-800 w-full"
          />
          <p className="text-xs text-zinc-500 mt-3">
            Покупатель видит: никнейм, рейтинг, количество сделок, методы оплаты и сумму к оплате
          </p>
        </CardContent>
      </Card>

      {/* UI Example - Select Payment Method */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Shield className="w-5 h-5 text-blue-400" />
            Пример UI: Выбор способа оплаты
          </CardTitle>
          <p className="text-sm text-zinc-400 mt-1">После выбора оператора покупатель выбирает способ оплаты</p>
        </CardHeader>
        <CardContent>
          <img 
            src="https://customer-assets.emergentagent.com/job_fbca4ceb-9112-496d-8675-a1b10145ddee/artifacts/1niq0xge_image.png"
            alt="Выбор способа оплаты"
            className="rounded-lg border border-zinc-800 max-w-md mx-auto"
          />
          <p className="text-xs text-zinc-500 mt-3">
            Покупатель выбирает СБП или Банковскую карту → подтверждает
          </p>
        </CardContent>
      </Card>

      {/* UI Example - Payment Screen */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Shield className="w-5 h-5 text-orange-400" />
            Пример UI: Экран оплаты
          </CardTitle>
          <p className="text-sm text-zinc-400 mt-1">Покупатель видит реквизиты и переводит деньги</p>
        </CardHeader>
        <CardContent>
          <img 
            src="https://customer-assets.emergentagent.com/job_fbca4ceb-9112-496d-8675-a1b10145ddee/artifacts/hmsjjefu_image.png"
            alt="Экран оплаты"
            className="rounded-lg border border-zinc-800 w-full"
          />
          <p className="text-xs text-zinc-500 mt-3">
            Покупатель видит: таймер, сумму, реквизиты и чат с оператором. После оплаты нажимает "Я оплатил".
          </p>
        </CardContent>
      </Card>

      {/* Signature Example */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Shield className="w-5 h-5 text-blue-400" />
            Генерация подписи (HMAC-SHA256)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="relative">
            <pre className="bg-zinc-950 rounded-lg p-4 overflow-x-auto text-sm font-mono text-zinc-300 border border-zinc-800">
              {signatureExample}
            </pre>
            <Button
              variant="ghost"
              size="sm"
              className="absolute top-2 right-2"
              title="Скопировать"
              onClick={() => copyToClipboard(signatureExample, 'Код')}
            >
              <Copy className="w-4 h-4" />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Create Invoice Example */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Code className="w-5 h-5 text-emerald-400" />
            Пример создания инвойса (Python)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="relative">
            <pre className="bg-zinc-950 rounded-lg p-4 overflow-x-auto text-sm font-mono text-zinc-300 border border-zinc-800 max-h-[500px]">
              {createInvoiceExample}
            </pre>
            <Button
              variant="ghost"
              size="sm"
              className="absolute top-2 right-2"
              title="Скопировать"
              onClick={() => copyToClipboard(createInvoiceExample, 'Код')}
            >
              <Copy className="w-4 h-4" />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* JavaScript Example */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Code className="w-5 h-5 text-yellow-400" />
            Пример интеграции (JavaScript)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="relative">
            <pre className="bg-zinc-950 rounded-lg p-4 overflow-x-auto text-sm font-mono text-zinc-300 border border-zinc-800 max-h-[500px]">
              {jsIntegrationExample}
            </pre>
            <Button
              variant="ghost"
              size="sm"
              className="absolute top-2 right-2"
              title="Скопировать"
              onClick={() => copyToClipboard(jsIntegrationExample, 'Код')}
            >
              <Copy className="w-4 h-4" />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Callback Info */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg">Webhook уведомления</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-zinc-400">
            Система автоматически отправляет POST-запрос на ваш <code className="bg-zinc-800 px-1 rounded">callback_url</code> при изменении статуса платежа:
          </p>
          
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
              <span className="text-sm"><code className="bg-zinc-800 px-1 rounded">paid</code> — платёж успешно завершён</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-red-500"></span>
              <span className="text-sm"><code className="bg-zinc-800 px-1 rounded">cancelled</code> — платёж отменён покупателем</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-zinc-500"></span>
              <span className="text-sm"><code className="bg-zinc-800 px-1 rounded">expired</code> — истёк срок ожидания</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-orange-500"></span>
              <span className="text-sm"><code className="bg-zinc-800 px-1 rounded">dispute</code> — открыт спор</span>
            </div>
          </div>
          
          <pre className="bg-zinc-950 rounded-lg p-4 text-sm font-mono text-zinc-300 border border-zinc-800">
{`{
  "order_id": "ORDER_12345",
  "payment_id": "inv_20250128_ABC123",
  "status": "paid",
  "amount": 1500.00,
  "amount_usdt": 15.50,
  "timestamp": "2025-01-28T12:00:00Z",
  "sign": "f6g7h8i9j0..."
}`}
          </pre>
          <div className="bg-orange-500/10 border border-orange-500/20 rounded-lg p-3">
            <p className="text-sm text-orange-300">
              <strong>⚠️ Важно:</strong> Всегда проверяйте подпись <code>sign</code> в webhook! 
              Ответьте <code>{`{ "status": "ok" }`}</code> для подтверждения получения.
            </p>
          </div>
          <p className="text-xs text-zinc-500">
            Retry-политика: 1 мин → 5 мин → 15 мин → 1 час → 2 часа → 4 часа → 12 часов → 24 часа
          </p>
        </CardContent>
      </Card>

      {/* Dispute System */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg">Система споров</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-zinc-400">
            При статусе <code className="bg-zinc-800 px-1 rounded">dispute</code> в ответе API появляется уникальная ссылка для клиента:
          </p>
          <pre className="bg-zinc-950 rounded-lg p-4 text-sm font-mono text-zinc-300 border border-zinc-800">
{`{
  "status": "success",
  "data": {
    "order_id": "ORDER_12345",
    "status": "dispute",
    "dispute_url": "${BASE_URL}/dispute/abc123def456"
  }
}`}
          </pre>
          <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3">
            <p className="text-sm text-blue-300">
              Передайте <code>dispute_url</code> клиенту — он сможет напрямую общаться с нашей поддержкой по данному платежу.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Проверка подписи webhook (вместо SDK) */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Code className="w-5 h-5 text-green-400" />
            Проверка подписи Webhook
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-zinc-400">
            При получении webhook всегда проверяйте подпись для безопасности:
          </p>
          <pre className="bg-zinc-950 rounded-lg p-4 text-sm font-mono text-zinc-300 border border-zinc-800">
{`// Node.js / Express пример
const crypto = require('crypto');

const SECRET_KEY = '${merchant?.api_secret || 'YOUR_SECRET_KEY'}';

// Поля которые участвуют в подписи
const SIGN_FIELDS = ['order_id', 'payment_id', 'status', 'amount', 'timestamp'];

function verifyWebhookSignature(payload, receivedSign) {
  const signParams = {};
  for (const [key, value] of Object.entries(payload)) {
    if (!SIGN_FIELDS.includes(key) || key === 'sign' || value === null) continue;
    let v = value;
    if (typeof v === 'number' && Number.isInteger(v)) v = Math.floor(v);
    signParams[key] = v;
  }
  
  const sortedKeys = Object.keys(signParams).sort();
  const signString = sortedKeys.map(k => \`\${k}=\${signParams[k]}\`).join('&') + SECRET_KEY;
  
  const expectedSign = crypto
    .createHmac('sha256', SECRET_KEY)
    .update(signString)
    .digest('hex');
  
  return expectedSign === receivedSign;
}

// Обработка webhook
app.post('/webhook', (req, res) => {
  const { sign, ...payload } = req.body;
  
  if (!verifyWebhookSignature(payload, sign)) {
    return res.status(401).json({ status: 'error', message: 'Invalid signature' });
  }
  
  // Обработка платежа
  console.log('Webhook received:', payload.status, payload.payment_id);
  
  // ВАЖНО: Всегда отвечайте { status: 'ok' }
  res.json({ status: 'ok' });
});`}
          </pre>
        </CardContent>
      </Card>

    </div>
  );
};

export default MerchantAPI;
