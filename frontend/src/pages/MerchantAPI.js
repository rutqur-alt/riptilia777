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
HEADERS = {"X-Api-Key": API_KEY, "Content-Type": "application/json"}

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

# ========== WHITE-LABEL ИНТЕГРАЦИЯ ==========

# 1. Создаём инвойс
def create_invoice(order_id: str, amount: int, callback_url: str):
    params = {
        "merchant_id": MERCHANT_ID,
        "order_id": order_id,
        "amount": amount,
        "currency": "RUB",
        "callback_url": callback_url,
        "user_id": None
    }
    params["sign"] = generate_signature(params, SECRET_KEY)
    
    response = requests.post(f"{BASE_URL}/create", json=params, headers=HEADERS)
    return response.json()  # {"status": "success", "payment_id": "inv_..."}

# 2. Получаем список операторов (для отображения на ВАШЕМ сайте)
def get_operators(invoice_id: str):
    response = requests.get(f"{BASE_URL}/{invoice_id}/operators", headers=HEADERS)
    return response.json()  # {"operators": [...]}

# 3. Клиент выбрал оператора → получаем реквизиты
def select_operator(invoice_id: str, offer_id: str, payment_method: str):
    response = requests.post(
        f"{BASE_URL}/{invoice_id}/select-operator",
        json={"offer_id": offer_id, "payment_method": payment_method},
        headers=HEADERS
    )
    return response.json()  # {"payment": {"requisites": {...}}}

# 4. Клиент оплатил → отмечаем
def mark_paid(invoice_id: str):
    response = requests.post(f"{BASE_URL}/{invoice_id}/mark-paid", headers=HEADERS)
    return response.json()

# === ПРИМЕР ИСПОЛЬЗОВАНИЯ ===
invoice = create_invoice("ORDER_123", 1500, "https://mysite.com/webhook")
invoice_id = invoice["payment_id"]

# Показываем операторов на ВАШЕМ сайте
operators = get_operators(invoice_id)
for op in operators["operators"]:
    print(f"{op['nickname']} - {op['amount_to_pay']} RUB ({op['payment_methods']})")

# Клиент выбрал оператора
result = select_operator(invoice_id, operators["operators"][0]["offer_id"], "card")
print(f"Реквизиты: {result['payment']['requisites']['number']}")

# Клиент оплатил
mark_paid(invoice_id)`;

  const jsIntegrationExample = `// ========== WHITE-LABEL ИНТЕГРАЦИЯ (JavaScript) ==========
// Клиент НЕ покидает ваш сайт. Всё через API.

const API_KEY = '${merchant?.api_key || 'YOUR_API_KEY'}';
const SECRET_KEY = '${merchant?.api_secret || 'YOUR_SECRET_KEY'}';
const MERCHANT_ID = '${merchant?.id || 'YOUR_MERCHANT_ID'}';
const API_BASE = '${BASE_URL}/api/v1/invoice';
const HEADERS = { 'X-Api-Key': API_KEY, 'Content-Type': 'application/json' };

// Подпись
const SIGN_FIELDS = ['merchant_id', 'order_id', 'amount', 'currency', 'user_id', 'callback_url'];
function generateSignature(params, secretKey) {
  const signParams = {};
  for (const [k, v] of Object.entries(params)) {
    if (!SIGN_FIELDS.includes(k) || k === 'sign' || v == null) continue;
    signParams[k] = typeof v === 'number' && Number.isInteger(v) ? Math.floor(v) : v;
  }
  const signString = Object.keys(signParams).sort().map(k => \`\${k}=\${signParams[k]}\`).join('&') + secretKey;
  return CryptoJS.HmacSHA256(signString, secretKey).toString();
}

// 1. Создать инвойс
async function createInvoice(amount, orderId) {
  const params = {
    merchant_id: MERCHANT_ID,
    order_id: orderId,
    amount: Math.floor(amount),
    currency: 'RUB',
    callback_url: 'https://yoursite.com/webhook',
    user_id: null
  };
  params.sign = generateSignature(params, SECRET_KEY);
  
  const res = await fetch(\`\${API_BASE}/create\`, {
    method: 'POST', headers: HEADERS, body: JSON.stringify(params)
  });
  return res.json();
}

// 2. Получить операторов (показать на ВАШЕМ сайте)
async function getOperators(invoiceId) {
  const res = await fetch(\`\${API_BASE}/\${invoiceId}/operators\`, { headers: HEADERS });
  return res.json();
}

// 3. Выбрать оператора → получить реквизиты
async function selectOperator(invoiceId, offerId, paymentMethod) {
  const res = await fetch(\`\${API_BASE}/\${invoiceId}/select-operator\`, {
    method: 'POST', headers: HEADERS,
    body: JSON.stringify({ offer_id: offerId, payment_method: paymentMethod })
  });
  return res.json();
}

// 4. Отметить как оплачено
async function markPaid(invoiceId) {
  const res = await fetch(\`\${API_BASE}/\${invoiceId}/mark-paid\`, {
    method: 'POST', headers: HEADERS
  });
  return res.json();
}

// === ПРИМЕР ИСПОЛЬЗОВАНИЯ ===
async function processPayment(amount) {
  // 1. Создаём инвойс
  const invoice = await createInvoice(amount, 'ORDER_' + Date.now());
  
  // 2. Показываем операторов на ВАШЕМ сайте
  const { operators } = await getOperators(invoice.payment_id);
  renderOperatorsList(operators);  // Ваша функция рендера
  
  // 3. Когда клиент выбрал оператора
  const result = await selectOperator(invoice.payment_id, selectedOfferId, 'card');
  showRequisites(result.payment.requisites);  // Ваша функция показа реквизитов
  
  // 4. Когда клиент нажал "Я оплатил"
  await markPaid(invoice.payment_id);
}`;

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
              { method: 'POST', path: '/api/v1/invoice/create', desc: 'Создать инвойс' },
              { method: 'GET', path: '/api/v1/invoice/{id}/operators', desc: 'Получить операторов для инвойса' },
              { method: 'POST', path: '/api/v1/invoice/{id}/select-operator', desc: 'Выбрать оператора, получить реквизиты' },
              { method: 'POST', path: '/api/v1/invoice/{id}/mark-paid', desc: 'Отметить как оплачено' },
              { method: 'GET', path: '/api/v1/invoice/{id}/messages', desc: 'Получить сообщения чата' },
              { method: 'POST', path: '/api/v1/invoice/{id}/messages', desc: 'Отправить сообщение в чат' },
              { method: 'GET', path: '/api/v1/invoice/status', desc: 'Проверить статус платежа' },
              { method: 'GET', path: '/api/v1/invoice/transactions', desc: 'Список всех транзакций' },
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

      {/* Integration Flow - WHITE LABEL */}
      <Card className="bg-gradient-to-r from-emerald-500/10 to-blue-500/10 border-emerald-500/30">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Shield className="w-5 h-5 text-emerald-400" />
            White-label интеграция
          </CardTitle>
          <p className="text-sm text-zinc-400 mt-1">Клиент НЕ покидает ваш сайт. Всё через API.</p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-3">
            <div className="flex gap-3 items-start">
              <span className="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-sm font-bold shrink-0">1</span>
              <div>
                <p className="text-sm text-zinc-300"><code className="bg-zinc-800 px-1 rounded">POST /create</code> — создайте инвойс</p>
                <p className="text-xs text-zinc-500 mt-1">Получите invoice_id</p>
              </div>
            </div>
            <div className="flex gap-3 items-start">
              <span className="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-sm font-bold shrink-0">2</span>
              <div>
                <p className="text-sm text-zinc-300"><code className="bg-zinc-800 px-1 rounded">GET /{'{id}'}/operators</code> — получите список операторов</p>
                <p className="text-xs text-zinc-500 mt-1">Покажите их на ВАШЕМ сайте (никнейм, рейтинг, методы оплаты)</p>
              </div>
            </div>
            <div className="flex gap-3 items-start">
              <span className="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-sm font-bold shrink-0">3</span>
              <div>
                <p className="text-sm text-zinc-300"><code className="bg-zinc-800 px-1 rounded">POST /{'{id}'}/select-operator</code> — клиент выбрал оператора</p>
                <p className="text-xs text-zinc-500 mt-1">Получите реквизиты (номер карты/телефон). Покажите на ВАШЕМ сайте.</p>
              </div>
            </div>
            <div className="flex gap-3 items-start">
              <span className="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-sm font-bold shrink-0">4</span>
              <div>
                <p className="text-sm text-zinc-300"><code className="bg-zinc-800 px-1 rounded">POST /{'{id}'}/mark-paid</code> — клиент нажал "Я оплатил"</p>
                <p className="text-xs text-zinc-500 mt-1">Статус меняется на "paid", отправляется webhook</p>
              </div>
            </div>
            <div className="flex gap-3 items-start">
              <span className="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-sm font-bold shrink-0">5</span>
              <div>
                <p className="text-sm text-zinc-300">Ждите webhook <code className="bg-zinc-800 px-1 rounded">completed</code> или проверяйте статус</p>
                <p className="text-xs text-zinc-500 mt-1">Оператор подтвердит получение средств</p>
              </div>
            </div>
          </div>
          
          <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-3 mt-4">
            <p className="text-sm text-emerald-300 font-medium">✓ Преимущества:</p>
            <ul className="text-sm text-zinc-400 mt-1 space-y-1">
              <li>• Клиент не видит наш домен</li>
              <li>• Полный контроль над UI/UX</li>
              <li>• Ваш бренд на всех этапах</li>
            </ul>
          </div>
        </CardContent>
      </Card>

      {/* API Response Examples */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Code className="w-5 h-5 text-purple-400" />
            Ответ GET /{'{id}'}/operators
          </CardTitle>
          <p className="text-sm text-zinc-400 mt-1">Список операторов для отображения на вашем сайте</p>
        </CardHeader>
        <CardContent>
          <pre className="bg-zinc-950 rounded-lg p-4 text-sm font-mono text-zinc-300 border border-zinc-800 overflow-x-auto">
{`{
  "status": "success",
  "invoice_id": "inv_...",
  "amount_rub": 1000,
  "exchange_rate": 78.5,
  "operators": [
    {
      "offer_id": "off_abc123",
      "nickname": "Трейдер Один",
      "rating": 98,
      "trades_count": 156,
      "payment_methods": ["card", "sbp"],
      "amount_to_pay": 1003,      // Сумма с комиссией
      "commission_percent": 0.3
    },
    {
      "offer_id": "off_xyz789",
      "nickname": "Оператор PRO",
      "rating": 100,
      "trades_count": 420,
      "payment_methods": ["sbp"],
      "amount_to_pay": 1010,
      "commission_percent": 1.0
    }
  ]
}`}
          </pre>
          <p className="text-xs text-zinc-500 mt-3">
            Отобразите этот список на вашем сайте. Клиент выбирает оператора.
          </p>
        </CardContent>
      </Card>

      {/* Select Operator Response */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Code className="w-5 h-5 text-blue-400" />
            Ответ POST /{'{id}'}/select-operator
          </CardTitle>
          <p className="text-sm text-zinc-400 mt-1">Реквизиты для отображения на вашем сайте</p>
        </CardHeader>
        <CardContent>
          <pre className="bg-zinc-950 rounded-lg p-4 text-sm font-mono text-zinc-300 border border-zinc-800 overflow-x-auto">
{`// Запрос
{ "offer_id": "off_abc123", "payment_method": "card" }

// Ответ
{
  "status": "success",
  "trade_id": "trd_...",
  "operator": {
    "nickname": "Трейдер Один",
    "rating": 98
  },
  "payment": {
    "method": "card",
    "amount": 1003,
    "requisites": {
      "type": "card",
      "bank": "Тинькофф",
      "number": "4276 1234 5678 9012",  // Номер карты
      "holder": "IVANOV IVAN"           // Получатель
    }
  },
  "expires_at": "2026-03-03T20:30:00Z",
  "time_limit_minutes": 30
}`}
          </pre>
          <p className="text-xs text-zinc-500 mt-3">
            Покажите реквизиты клиенту. Запустите таймер на 30 минут.
          </p>
        </CardContent>
      </Card>

      {/* Mark Paid */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Shield className="w-5 h-5 text-emerald-400" />
            POST /{'{id}'}/mark-paid
          </CardTitle>
          <p className="text-sm text-zinc-400 mt-1">Клиент нажал "Я оплатил" на вашем сайте</p>
        </CardHeader>
        <CardContent>
          <pre className="bg-zinc-950 rounded-lg p-4 text-sm font-mono text-zinc-300 border border-zinc-800 overflow-x-auto">
{`// Ответ
{
  "status": "success",
  "message": "Оплата отмечена. Ожидайте подтверждения от оператора.",
  "trade_status": "paid"
}

// Вам придёт webhook "paid", затем "completed" когда оператор подтвердит`}
          </pre>
        </CardContent>
      </Card>

      {/* Chat API */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <ExternalLink className="w-5 h-5 text-purple-400" />
            Chat API — чат с оператором
          </CardTitle>
          <p className="text-sm text-zinc-400 mt-1">Интегрируйте чат поддержки на ваш сайт</p>
        </CardHeader>
        <CardContent>
          <pre className="bg-zinc-950 rounded-lg p-4 text-sm font-mono text-zinc-300 border border-zinc-800 overflow-x-auto">
{`// GET /{id}/messages — Получить сообщения
{
  "status": "success",
  "messages": [
    { "id": "...", "sender": "system", "text": "Сделка создана", "timestamp": "..." },
    { "id": "...", "sender": "operator", "text": "Здравствуйте!", "timestamp": "..." },
    { "id": "...", "sender": "client", "text": "Оплатил", "timestamp": "..." }
  ]
}

// POST /{id}/messages — Отправить сообщение от клиента
// Body: { "text": "Сообщение клиента" }
{
  "status": "success",
  "message": { "id": "...", "sender": "client", "text": "...", "timestamp": "..." }
}`}
          </pre>
          <p className="text-xs text-zinc-500 mt-3">
            Polling: запрашивайте сообщения каждые 3-5 секунд для real-time обновлений.
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
