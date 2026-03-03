import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { useAuth, API } from '@/App';
import axios from 'axios';
import { Copy, RefreshCw, Code, Key, Shield, ExternalLink, Eye, EyeOff, CheckCircle, AlertTriangle, Clock, ArrowRight } from 'lucide-react';

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

  const BASE_URL = window.location.origin;

  const signatureExample = `import hmac
import hashlib

def generate_signature(params: dict, secret_key: str) -> str:
    """
    Генерация HMAC-SHA256 подписи для Reptiloid API
    
    Поля участвующие в подписи:
    merchant_id, order_id, amount, currency, user_id, callback_url
    
    ВАЖНО: description НЕ участвует в подписи!
    
    Алгоритм:
    1. Берём только разрешённые поля
    2. Убираем sign и None значения
    3. float приводим к int если число целое (1500.0 → 1500)
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

  const pythonExample = `import requests
import hmac
import hashlib

# === ВАШИ КЛЮЧИ ===
API_KEY = "${merchant?.api_key || 'YOUR_API_KEY'}"
SECRET_KEY = "${merchant?.api_secret || 'YOUR_SECRET_KEY'}"
MERCHANT_ID = "${merchant?.id || 'YOUR_MERCHANT_ID'}"
BASE_URL = "${BASE_URL}/api/v1/invoice"

def generate_signature(params: dict, secret_key: str) -> str:
    """Генерация HMAC-SHA256 подписи"""
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


def create_payment(order_id: str, amount: int, callback_url: str, description: str = None):
    """
    Создание платежа. Возвращает ссылку для редиректа клиента.
    
    Args:
        order_id: Уникальный ID заказа в вашей системе
        amount: Сумма в рублях (минимум 100)
        callback_url: URL для получения вебхуков
        description: Описание платежа (опционально)
    
    Returns:
        payment_url - ссылка для редиректа клиента на страницу оплаты
    """
    params = {
        "merchant_id": MERCHANT_ID,
        "order_id": order_id,
        "amount": amount,
        "currency": "RUB",
        "callback_url": callback_url,
        "user_id": None
    }
    params["sign"] = generate_signature(params, SECRET_KEY)
    
    # description не участвует в подписи, добавляем отдельно
    if description:
        params["description"] = description
    
    response = requests.post(
        f"{BASE_URL}/create",
        json=params,
        headers={"X-Api-Key": API_KEY, "Content-Type": "application/json"}
    )
    
    data = response.json()
    if data.get("status") == "success":
        return data["payment_url"]  # Редирект клиента сюда!
    else:
        raise Exception(data.get("message", "Ошибка создания платежа"))


def check_payment_status(order_id: str = None, payment_id: str = None):
    """
    Проверка статуса платежа.
    Можно проверять по order_id (ваш ID) или payment_id (наш ID).
    """
    params = {}
    if order_id:
        params["order_id"] = order_id
    if payment_id:
        params["payment_id"] = payment_id
    
    response = requests.get(
        f"{BASE_URL}/status",
        params=params,
        headers={"X-Api-Key": API_KEY}
    )
    
    return response.json()


# === ПРИМЕР ИСПОЛЬЗОВАНИЯ ===

# 1. Клиент нажал "Оплатить" на вашем сайте
payment_url = create_payment(
    order_id="ORDER_123456",
    amount=1500,
    callback_url="https://yoursite.com/webhook",
    description="Пополнение баланса"
)

# 2. Редиректим клиента на страницу оплаты
print(f"Redirect клиента на: {payment_url}")
# В веб-приложении: return redirect(payment_url)

# 3. Проверка статуса (опционально, вместо вебхука)
status = check_payment_status(order_id="ORDER_123456")
print(f"Статус: {status['data']['status']}")`;

  const jsExample = `// === ВАШИ КЛЮЧИ ===
const API_KEY = '${merchant?.api_key || 'YOUR_API_KEY'}';
const SECRET_KEY = '${merchant?.api_secret || 'YOUR_SECRET_KEY'}';
const MERCHANT_ID = '${merchant?.id || 'YOUR_MERCHANT_ID'}';
const API_BASE = '${BASE_URL}/api/v1/invoice';

// Подключите crypto-js: npm install crypto-js
// import CryptoJS from 'crypto-js';

const SIGN_FIELDS = ['merchant_id', 'order_id', 'amount', 'currency', 'user_id', 'callback_url'];

function generateSignature(params, secretKey) {
  const signParams = {};
  for (const [k, v] of Object.entries(params)) {
    if (!SIGN_FIELDS.includes(k) || k === 'sign' || v == null) continue;
    signParams[k] = typeof v === 'number' && Number.isInteger(v) ? Math.floor(v) : v;
  }
  const signString = Object.keys(signParams).sort()
    .map(k => \`\${k}=\${signParams[k]}\`).join('&') + secretKey;
  return CryptoJS.HmacSHA256(signString, secretKey).toString();
}

/**
 * Создание платежа
 * @param {number} amount - сумма в рублях
 * @param {string} orderId - уникальный ID заказа
 * @param {string} callbackUrl - URL для вебхуков
 * @returns {string} payment_url - ссылка для редиректа
 */
async function createPayment(amount, orderId, callbackUrl, description = null) {
  const params = {
    merchant_id: MERCHANT_ID,
    order_id: orderId,
    amount: Math.floor(amount),
    currency: 'RUB',
    callback_url: callbackUrl,
    user_id: null
  };
  params.sign = generateSignature(params, SECRET_KEY);
  
  if (description) params.description = description;
  
  const res = await fetch(\`\${API_BASE}/create\`, {
    method: 'POST',
    headers: { 'X-Api-Key': API_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  
  const data = await res.json();
  if (data.status === 'success') {
    return data.payment_url;  // Редирект клиента сюда!
  }
  throw new Error(data.message || 'Ошибка создания платежа');
}

// === ПРИМЕР ИСПОЛЬЗОВАНИЯ ===

// На сервере (Node.js/Express):
app.post('/pay', async (req, res) => {
  const { amount, orderId } = req.body;
  
  const paymentUrl = await createPayment(
    amount,
    orderId,
    'https://yoursite.com/webhook'
  );
  
  // Редирект клиента на страницу оплаты
  res.redirect(paymentUrl);
});

// На клиенте (React/Vue):
async function handlePayment() {
  const paymentUrl = await createPayment(1500, 'ORDER_' + Date.now(), '/webhook');
  window.location.href = paymentUrl;  // Редирект
}`;

  const webhookExample = `// Node.js / Express - обработка вебхуков
const crypto = require('crypto');

const SECRET_KEY = '${merchant?.api_secret || 'YOUR_SECRET_KEY'}';
const SIGN_FIELDS = ['order_id', 'payment_id', 'status', 'amount', 'amount_usdt', 'timestamp'];

function verifyWebhookSignature(payload, receivedSign) {
  const signParams = {};
  for (const [key, value] of Object.entries(payload)) {
    if (!SIGN_FIELDS.includes(key) || key === 'sign' || value === null) continue;
    let v = value;
    if (typeof v === 'number' && Number.isInteger(v)) v = Math.floor(v);
    signParams[key] = v;
  }
  
  const signString = Object.keys(signParams).sort()
    .map(k => \`\${k}=\${signParams[k]}\`).join('&') + SECRET_KEY;
  
  const expectedSign = crypto
    .createHmac('sha256', SECRET_KEY)
    .update(signString)
    .digest('hex');
  
  return expectedSign === receivedSign;
}

// Обработчик вебхуков
app.post('/webhook', (req, res) => {
  const { sign, ...payload } = req.body;
  
  // 1. Проверяем подпись
  if (!verifyWebhookSignature(payload, sign)) {
    console.error('Invalid webhook signature!');
    return res.status(401).json({ status: 'error', message: 'Invalid signature' });
  }
  
  // 2. Обрабатываем статус
  const { order_id, payment_id, status, amount, amount_usdt } = payload;
  
  switch (status) {
    case 'pending':
      // Клиент выбрал оператора, ожидает оплаты
      console.log(\`Заказ \${order_id}: ожидает оплаты\`);
      break;
      
    case 'paid':
      // Клиент оплатил, ожидает подтверждения оператора
      console.log(\`Заказ \${order_id}: клиент оплатил, ждём подтверждения\`);
      break;
      
    case 'completed':
      // ✅ ПЛАТЁЖ УСПЕШЕН - зачислите средства клиенту!
      console.log(\`Заказ \${order_id}: УСПЕХ! Сумма: \${amount} RUB / \${amount_usdt} USDT\`);
      // await creditUserBalance(order_id, amount_usdt);
      break;
      
    case 'cancelled':
      // Отмена (клиент отменил или таймаут)
      console.log(\`Заказ \${order_id}: отменён. Причина: \${payload.reason}\`);
      break;
      
    case 'disputed':
      // Открыт спор - ждите решения арбитража
      console.log(\`Заказ \${order_id}: открыт спор\`);
      break;
  }
  
  // 3. ВАЖНО: всегда отвечайте { status: 'ok' }
  res.json({ status: 'ok' });
});`;

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">API Интеграция</h1>
        <p className="text-zinc-400 text-sm">Invoice API v1 — Приём рублевых платежей через P2P USDT</p>
      </div>

      {/* Как это работает */}
      <Card className="bg-gradient-to-r from-emerald-500/10 to-blue-500/10 border-emerald-500/30">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <ArrowRight className="w-5 h-5 text-emerald-400" />
            Как работает интеграция
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-zinc-300">
            Простая интеграция с редиректом. Клиент переходит на нашу платформу для оплаты.
          </p>
          
          <div className="space-y-3">
            <div className="flex gap-3 items-start">
              <span className="w-8 h-8 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-sm font-bold shrink-0">1</span>
              <div>
                <p className="text-sm text-white font-medium">Создайте платёж через API</p>
                <p className="text-xs text-zinc-500 mt-1">POST /api/v1/invoice/create → получите payment_url</p>
              </div>
            </div>
            <div className="flex gap-3 items-start">
              <span className="w-8 h-8 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-sm font-bold shrink-0">2</span>
              <div>
                <p className="text-sm text-white font-medium">Перенаправьте клиента на payment_url</p>
                <p className="text-xs text-zinc-500 mt-1">Клиент увидит список операторов, выберет способ оплаты, получит реквизиты</p>
              </div>
            </div>
            <div className="flex gap-3 items-start">
              <span className="w-8 h-8 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-sm font-bold shrink-0">3</span>
              <div>
                <p className="text-sm text-white font-medium">Клиент оплачивает на нашей платформе</p>
                <p className="text-xs text-zinc-500 mt-1">Чат с оператором, проверка статуса — всё на нашей стороне</p>
              </div>
            </div>
            <div className="flex gap-3 items-start">
              <span className="w-8 h-8 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-sm font-bold shrink-0">4</span>
              <div>
                <p className="text-sm text-white font-medium">Получите webhook о статусе платежа</p>
                <p className="text-xs text-zinc-500 mt-1">completed = успех, зачислите средства клиенту</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* API Keys */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Key className="w-5 h-5 text-emerald-400" />
              API Key
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm text-zinc-400">Передаётся в заголовке X-Api-Key</label>
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

        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Shield className="w-5 h-5 text-blue-400" />
              Secret Key
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm text-zinc-400">Для генерации и проверки подписи (HMAC-SHA256)</label>
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
                Никогда не передавайте Secret Key в запросах! Используйте только для генерации подписи.
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
          <CardTitle className="text-lg">API Endpoints</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[
              { method: 'POST', path: '/api/v1/invoice/create', desc: 'Создать платёж (получить payment_url)' },
              { method: 'GET', path: '/api/v1/invoice/status', desc: 'Проверить статус платежа' },
              { method: 'GET', path: '/api/v1/invoice/transactions', desc: 'Список всех транзакций' },
              { method: 'GET', path: '/api/v1/invoice/stats', desc: 'Статистика платежей' },
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

      {/* Create Invoice */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Code className="w-5 h-5 text-emerald-400" />
            POST /api/v1/invoice/create
          </CardTitle>
          <p className="text-sm text-zinc-400 mt-1">Создание платежа</p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <h4 className="text-sm font-medium text-zinc-300 mb-2">Запрос:</h4>
            <pre className="bg-zinc-950 rounded-lg p-4 text-sm font-mono text-zinc-300 border border-zinc-800 overflow-x-auto">
{`Header: X-Api-Key: ${merchant?.api_key || 'YOUR_API_KEY'}

{
  "merchant_id": "${merchant?.id || 'YOUR_MERCHANT_ID'}",
  "order_id": "ORDER_123456",        // Уникальный ID в вашей системе
  "amount": 1500,                    // Сумма в рублях (мин. 100)
  "currency": "RUB",
  "callback_url": "https://yoursite.com/webhook",
  "user_id": null,                   // Опционально
  "description": "Пополнение",       // Опционально, НЕ входит в подпись
  "sign": "abc123..."                // HMAC-SHA256 подпись
}`}
            </pre>
          </div>
          
          <div>
            <h4 className="text-sm font-medium text-zinc-300 mb-2">Ответ:</h4>
            <pre className="bg-zinc-950 rounded-lg p-4 text-sm font-mono text-zinc-300 border border-zinc-800 overflow-x-auto">
{`{
  "status": "success",
  "payment_id": "inv_20250128_ABC123",
  "payment_url": "${BASE_URL}/select-operator/inv_20250128_ABC123",
  "details": {
    "original_amount": 1500,
    "total_amount": 1507,           // С маркером для идентификации
    "marker": 7,
    "amount_usdt": 15.50,
    "expires_at": "2025-01-28T12:30:00Z"
  }
}`}
            </pre>
          </div>
          
          <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-3">
            <p className="text-sm text-emerald-300">
              <strong>payment_url</strong> — перенаправьте клиента на этот URL для оплаты
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Check Status */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Code className="w-5 h-5 text-blue-400" />
            GET /api/v1/invoice/status
          </CardTitle>
          <p className="text-sm text-zinc-400 mt-1">Проверка статуса платежа</p>
        </CardHeader>
        <CardContent className="space-y-4">
          <pre className="bg-zinc-950 rounded-lg p-4 text-sm font-mono text-zinc-300 border border-zinc-800 overflow-x-auto">
{`GET /api/v1/invoice/status?order_id=ORDER_123456
Header: X-Api-Key: ${merchant?.api_key || 'YOUR_API_KEY'}

// или по payment_id:
GET /api/v1/invoice/status?payment_id=inv_20250128_ABC123

// Ответ:
{
  "status": "success",
  "data": {
    "order_id": "ORDER_123456",
    "payment_id": "inv_20250128_ABC123",
    "status": "completed",           // pending | paid | completed | cancelled | disputed
    "amount": 1500,
    "total_amount": 1507,
    "amount_usdt": 15.50,
    "created_at": "2025-01-28T12:00:00Z",
    "paid_at": "2025-01-28T12:05:00Z",
    "expires_at": "2025-01-28T12:30:00Z"
  }
}`}
          </pre>
        </CardContent>
      </Card>

      {/* Webhooks */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <ExternalLink className="w-5 h-5 text-purple-400" />
            Webhook уведомления
          </CardTitle>
          <p className="text-sm text-zinc-400 mt-1">Автоматические уведомления о статусе платежа</p>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-zinc-400">
            Система отправляет POST-запрос на ваш <code className="bg-zinc-800 px-1 rounded">callback_url</code> при каждом изменении статуса:
          </p>
          
          <div className="space-y-2">
            <div className="flex items-center gap-3 p-3 bg-zinc-800/50 rounded-lg">
              <span className="w-3 h-3 rounded-full bg-yellow-500"></span>
              <code className="bg-zinc-800 px-2 py-0.5 rounded text-sm">pending</code>
              <span className="text-sm text-zinc-400 flex-1">Клиент выбрал оператора, ожидает оплаты</span>
            </div>
            <div className="flex items-center gap-3 p-3 bg-zinc-800/50 rounded-lg">
              <span className="w-3 h-3 rounded-full bg-blue-500"></span>
              <code className="bg-zinc-800 px-2 py-0.5 rounded text-sm">paid</code>
              <span className="text-sm text-zinc-400 flex-1">Клиент оплатил, ожидает подтверждения оператора</span>
            </div>
            <div className="flex items-center gap-3 p-3 bg-emerald-500/10 rounded-lg border border-emerald-500/20">
              <span className="w-3 h-3 rounded-full bg-emerald-500"></span>
              <code className="bg-zinc-800 px-2 py-0.5 rounded text-sm">completed</code>
              <span className="text-sm text-emerald-400 flex-1 font-medium">Платёж успешен — зачислите средства клиенту!</span>
            </div>
            <div className="flex items-center gap-3 p-3 bg-zinc-800/50 rounded-lg">
              <span className="w-3 h-3 rounded-full bg-red-500"></span>
              <code className="bg-zinc-800 px-2 py-0.5 rounded text-sm">cancelled</code>
              <span className="text-sm text-zinc-400 flex-1">Отмена (клиент отменил или таймаут 30 мин)</span>
            </div>
            <div className="flex items-center gap-3 p-3 bg-zinc-800/50 rounded-lg">
              <span className="w-3 h-3 rounded-full bg-orange-500"></span>
              <code className="bg-zinc-800 px-2 py-0.5 rounded text-sm">disputed</code>
              <span className="text-sm text-zinc-400 flex-1">Открыт спор, ожидает решения арбитража</span>
            </div>
          </div>
          
          <div>
            <h4 className="text-sm font-medium text-zinc-300 mb-2">Формат webhook:</h4>
            <pre className="bg-zinc-950 rounded-lg p-4 text-sm font-mono text-zinc-300 border border-zinc-800 overflow-x-auto">
{`POST https://yoursite.com/webhook

{
  "order_id": "ORDER_123456",
  "payment_id": "inv_20250128_ABC123",
  "status": "completed",
  "amount": 1500,
  "amount_usdt": 15.50,
  "timestamp": "2025-01-28T12:10:00Z",
  "sign": "f6a7b8c9..."              // HMAC-SHA256 подпись
  
  // Дополнительные поля для некоторых статусов:
  "trade_id": "trd_abc123",          // ID сделки
  "reason": "auto_timeout",          // Причина отмены (для cancelled)
  "completed_at": "...",             // Время завершения (для completed)
}`}
            </pre>
          </div>
          
          <div className="bg-orange-500/10 border border-orange-500/20 rounded-lg p-3">
            <p className="text-sm text-orange-300">
              <strong>Важно:</strong> Всегда проверяйте подпись <code>sign</code>! Отвечайте <code>{`{ "status": "ok" }`}</code> для подтверждения.
            </p>
          </div>
          
          <p className="text-xs text-zinc-500">
            Retry-политика: 1 мин → 5 мин → 15 мин → 1 час → 2 часа → 4 часа → 12 часов → 24 часа
          </p>
        </CardContent>
      </Card>

      {/* Signature */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Shield className="w-5 h-5 text-blue-400" />
            Генерация подписи (HMAC-SHA256)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="relative">
            <pre className="bg-zinc-950 rounded-lg p-4 overflow-x-auto text-sm font-mono text-zinc-300 border border-zinc-800 max-h-[400px]">
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

      {/* Python Example */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Code className="w-5 h-5 text-emerald-400" />
            Полный пример (Python)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="relative">
            <pre className="bg-zinc-950 rounded-lg p-4 overflow-x-auto text-sm font-mono text-zinc-300 border border-zinc-800 max-h-[500px]">
              {pythonExample}
            </pre>
            <Button
              variant="ghost"
              size="sm"
              className="absolute top-2 right-2"
              title="Скопировать"
              onClick={() => copyToClipboard(pythonExample, 'Код')}
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
            Полный пример (JavaScript)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="relative">
            <pre className="bg-zinc-950 rounded-lg p-4 overflow-x-auto text-sm font-mono text-zinc-300 border border-zinc-800 max-h-[500px]">
              {jsExample}
            </pre>
            <Button
              variant="ghost"
              size="sm"
              className="absolute top-2 right-2"
              title="Скопировать"
              onClick={() => copyToClipboard(jsExample, 'Код')}
            >
              <Copy className="w-4 h-4" />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Webhook Handler Example */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Code className="w-5 h-5 text-purple-400" />
            Обработка вебхуков (Node.js)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="relative">
            <pre className="bg-zinc-950 rounded-lg p-4 overflow-x-auto text-sm font-mono text-zinc-300 border border-zinc-800 max-h-[500px]">
              {webhookExample}
            </pre>
            <Button
              variant="ghost"
              size="sm"
              className="absolute top-2 right-2"
              title="Скопировать"
              onClick={() => copyToClipboard(webhookExample, 'Код')}
            >
              <Copy className="w-4 h-4" />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Statuses */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg">Статусы платежа</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800">
                  <th className="text-left py-2 px-3 text-zinc-400">Статус</th>
                  <th className="text-left py-2 px-3 text-zinc-400">Описание</th>
                  <th className="text-left py-2 px-3 text-zinc-400">Действие</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-zinc-800/50">
                  <td className="py-3 px-3"><code className="bg-yellow-500/20 text-yellow-400 px-2 py-0.5 rounded">waiting_requisites</code></td>
                  <td className="py-3 px-3 text-zinc-300">Инвойс создан, ожидает выбора оператора</td>
                  <td className="py-3 px-3 text-zinc-500">Ждать</td>
                </tr>
                <tr className="border-b border-zinc-800/50">
                  <td className="py-3 px-3"><code className="bg-yellow-500/20 text-yellow-400 px-2 py-0.5 rounded">pending</code></td>
                  <td className="py-3 px-3 text-zinc-300">Клиент выбрал оператора, ожидает оплаты</td>
                  <td className="py-3 px-3 text-zinc-500">Ждать</td>
                </tr>
                <tr className="border-b border-zinc-800/50">
                  <td className="py-3 px-3"><code className="bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded">paid</code></td>
                  <td className="py-3 px-3 text-zinc-300">Клиент оплатил, ждём подтверждения</td>
                  <td className="py-3 px-3 text-zinc-500">Ждать</td>
                </tr>
                <tr className="border-b border-zinc-800/50">
                  <td className="py-3 px-3"><code className="bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded">completed</code></td>
                  <td className="py-3 px-3 text-emerald-300 font-medium">Платёж успешен!</td>
                  <td className="py-3 px-3 text-emerald-400">Зачислить средства</td>
                </tr>
                <tr className="border-b border-zinc-800/50">
                  <td className="py-3 px-3"><code className="bg-red-500/20 text-red-400 px-2 py-0.5 rounded">cancelled</code></td>
                  <td className="py-3 px-3 text-zinc-300">Отменён клиентом или по таймауту</td>
                  <td className="py-3 px-3 text-zinc-500">Ничего не делать</td>
                </tr>
                <tr className="border-b border-zinc-800/50">
                  <td className="py-3 px-3"><code className="bg-zinc-500/20 text-zinc-400 px-2 py-0.5 rounded">expired</code></td>
                  <td className="py-3 px-3 text-zinc-300">Истёк срок ожидания</td>
                  <td className="py-3 px-3 text-zinc-500">Ничего не делать</td>
                </tr>
                <tr>
                  <td className="py-3 px-3"><code className="bg-orange-500/20 text-orange-400 px-2 py-0.5 rounded">disputed</code></td>
                  <td className="py-3 px-3 text-zinc-300">Открыт спор</td>
                  <td className="py-3 px-3 text-zinc-500">Ждать решения арбитража</td>
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Errors */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg">Коды ошибок</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm">
            {[
              { code: 'INVALID_API_KEY', desc: 'Неверный API ключ' },
              { code: 'INVALID_SIGNATURE', desc: 'Неверная подпись запроса' },
              { code: 'MERCHANT_MISMATCH', desc: 'merchant_id не соответствует API ключу' },
              { code: 'DUPLICATE_ORDER_ID', desc: 'Заказ с таким order_id уже существует' },
              { code: 'INVALID_AMOUNT', desc: 'Сумма меньше минимальной (100 RUB)' },
              { code: 'RATE_LIMIT_EXCEEDED', desc: 'Превышен лимит запросов' },
              { code: 'NOT_FOUND', desc: 'Платёж не найден' },
            ].map((err, idx) => (
              <div key={idx} className="flex items-center gap-4 p-2 bg-zinc-800/30 rounded">
                <code className="text-red-400 font-mono">{err.code}</code>
                <span className="text-zinc-400">{err.desc}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Rate Limits */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg">Лимиты запросов</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between p-2 bg-zinc-800/30 rounded">
              <span className="text-zinc-300">/create</span>
              <span className="text-zinc-400">60 запросов/мин</span>
            </div>
            <div className="flex justify-between p-2 bg-zinc-800/30 rounded">
              <span className="text-zinc-300">/status</span>
              <span className="text-zinc-400">120 запросов/мин</span>
            </div>
            <div className="flex justify-between p-2 bg-zinc-800/30 rounded">
              <span className="text-zinc-300">/transactions</span>
              <span className="text-zinc-400">30 запросов/мин</span>
            </div>
          </div>
        </CardContent>
      </Card>

    </div>
  );
};

export default MerchantAPI;
