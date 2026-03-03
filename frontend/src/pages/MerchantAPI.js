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
    - merchant_id, order_id, amount, currency, user_id, callback_url, payment_method
    
    Поле description и другие дополнительные поля НЕ участвуют в подписи!
    
    Алгоритм:
    1. Берём только разрешённые поля (см. выше)
    2. Убираем sign и None значения
    3. ВАЖНО: float приводим к int если число целое (1500.0 → 1500)
    4. Сортируем по ключам
    5. Формируем строку key=value&key2=value2
    6. Добавляем secret_key в конец
    7. Вычисляем HMAC-SHA256
    """
    # Поля которые участвуют в подписи для /create
    SIGN_FIELDS = ['merchant_id', 'order_id', 'amount', 'currency', 'user_id', 'callback_url', 'payment_method']
    
    sign_params = {}
    for k, v in params.items():
        if k not in SIGN_FIELDS or k == 'sign' or v is None:
            continue
        # ВАЖНО: приводим float к int если число целое
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

# 1. Получаем список способов оплаты (для показа на вашем сайте)
def get_payment_methods():
    """Получить доступные способы оплаты"""
    response = requests.get(
        f"{BASE_URL}/payment-methods",
        headers={"X-Api-Key": API_KEY}
    )
    return response.json()["payment_methods"]

# 2. Создаём инвойс с выбранным методом
def create_invoice(order_id: str, amount: float, callback_url: str, payment_method: str = None, user_id: str = None):
    """Создание инвойса на оплату"""
    # Поля для подписи (description НЕ входит!)
    params = {
        "merchant_id": MERCHANT_ID,
        "order_id": order_id,
        "amount": amount,  # Будет автоматически приведено к int если целое
        "currency": "RUB",
        "callback_url": callback_url,
        "payment_method": payment_method,
        "user_id": user_id
    }
    params["sign"] = generate_signature(params, SECRET_KEY)
    
    # description можно добавить ПОСЛЕ генерации подписи (оно не участвует в sign)
    params["description"] = "Оплата заказа"
    
    response = requests.post(
        f"{BASE_URL}/create",
        json=params,
        headers={"X-Api-Key": API_KEY, "Content-Type": "application/json"}
    )
    return response.json()

# Пример использования:
methods = get_payment_methods()
# [{"id": "card", "name": "Банковская карта"}, {"id": "sbp", "name": "СБП"}, ...]

# Покупатель выбрал "card" на вашем сайте
result = create_invoice(
    order_id="ORDER_12345",
    amount=1500,  # Используйте int, не float!
    callback_url="https://mysite.com/payment/callback",
    payment_method="card"
)

# Ответ:
# {
#   "status": "success",
#   "payment_id": "inv_...",
#   "payment_url": "${BASE_URL}/pay/inv_...",  <-- ОТКРЫТЬ В НОВОЙ ВКЛАДКЕ!
# }

# 3. На фронтенде: window.open(result["payment_url"], "_blank")`;

  const jsIntegrationExample = `// JavaScript пример для вашего сайта

const API_KEY = '${merchant?.api_key || 'YOUR_API_KEY'}';
const SECRET_KEY = '${merchant?.api_secret || 'YOUR_SECRET_KEY'}';
const MERCHANT_ID = '${merchant?.id || 'YOUR_MERCHANT_ID'}';
const API_BASE = '${BASE_URL}/api/v1/invoice';

// Поля которые участвуют в подписи для /create
const SIGN_FIELDS = ['merchant_id', 'order_id', 'amount', 'currency', 'user_id', 'callback_url', 'payment_method'];

/**
 * Генерация подписи для Reptiloid API
 * ВАЖНО: 
 * - Только поля из SIGN_FIELDS участвуют в подписи
 * - float числа приводятся к int (1500.0 → 1500)
 * - description и другие поля НЕ участвуют в подписи
 */
function generateSignature(params, secretKey) {
  const signParams = {};
  
  for (const [key, value] of Object.entries(params)) {
    if (!SIGN_FIELDS.includes(key) || key === 'sign' || value === null || value === undefined) {
      continue;
    }
    // ВАЖНО: приводим float к int если число целое
    let v = value;
    if (typeof v === 'number' && Number.isInteger(v)) {
      v = Math.floor(v);
    }
    signParams[key] = v;
  }
  
  const sortedKeys = Object.keys(signParams).sort();
  const signString = sortedKeys.map(k => \`\${k}=\${signParams[k]}\`).join('&') + secretKey;
  
  // Используйте crypto-js или Web Crypto API
  return CryptoJS.HmacSHA256(signString, secretKey).toString();
}

// 1. Получаем способы оплаты при загрузке страницы
async function loadPaymentMethods() {
  const res = await fetch(\`\${API_BASE}/payment-methods\`, {
    headers: { 'X-Api-Key': API_KEY }
  });
  const data = await res.json();
  return data.payment_methods;
  // Показываем покупателю выбор на ВАШЕМ сайте
}

// 2. Когда покупатель выбрал метод и нажал "Оплатить"
async function createPayment(amount, paymentMethod, userId = null) {
  const orderId = 'ORDER_' + Date.now();
  
  const params = {
    merchant_id: MERCHANT_ID,
    order_id: orderId,
    amount: Math.floor(amount), // Используйте целое число!
    currency: 'RUB',
    callback_url: 'https://yoursite.com/callback',
    payment_method: paymentMethod,
    user_id: userId
  };
  params.sign = generateSignature(params, SECRET_KEY);
  
  // description можно добавить ПОСЛЕ генерации подписи
  params.description = 'Оплата заказа';
  
  const res = await fetch(\`\${API_BASE}/create\`, {
    method: 'POST',
    headers: { 'X-Api-Key': API_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  
  const data = await res.json();
  
  // 3. ВАЖНО: Открываем страницу оплаты в НОВОЙ ВКЛАДКЕ
  // Покупатель увидит реквизиты на нашем домене
  window.open(data.payment_url, '_blank');
  
  return orderId; // Сохраняем для проверки статуса
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
              <p className="text-sm text-zinc-300"><code className="bg-zinc-800 px-1 rounded">GET /payment-methods</code> — получите список способов оплаты</p>
            </div>
            <div className="flex gap-3 items-start">
              <span className="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-sm font-bold shrink-0">2</span>
              <p className="text-sm text-zinc-300">Покажите покупателю выбор способа оплаты <strong>на вашем сайте</strong></p>
            </div>
            <div className="flex gap-3 items-start">
              <span className="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-sm font-bold shrink-0">3</span>
              <p className="text-sm text-zinc-300"><code className="bg-zinc-800 px-1 rounded">POST /create</code> — создайте инвойс с выбранным <code className="bg-zinc-800 px-1 rounded">payment_method</code></p>
            </div>
            <div className="flex gap-3 items-start">
              <span className="w-6 h-6 rounded-full bg-orange-500/20 text-orange-400 flex items-center justify-center text-sm font-bold shrink-0">4</span>
              <p className="text-sm text-zinc-300"><strong className="text-orange-400">window.open(payment_url, '_blank')</strong> — откройте страницу оплаты <strong>в новой вкладке</strong></p>
            </div>
            <div className="flex gap-3 items-start">
              <span className="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-sm font-bold shrink-0">5</span>
              <p className="text-sm text-zinc-300">Покупатель видит реквизиты на <strong>нашем домене</strong>, оплачивает, закрывает вкладку</p>
            </div>
            <div className="flex gap-3 items-start">
              <span className="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-sm font-bold shrink-0">6</span>
              <p className="text-sm text-zinc-300">Получите callback или проверяйте статус через <code className="bg-zinc-800 px-1 rounded">GET /status</code></p>
            </div>
          </div>
          
          <div className="bg-orange-500/10 border border-orange-500/20 rounded-lg p-3 mt-4">
            <p className="text-sm text-orange-300 font-medium">⚠️ Важно:</p>
            <ul className="text-sm text-zinc-400 mt-1 space-y-1">
              <li>• Реквизиты <strong>НЕ передаются</strong> на ваш сайт — это для безопасности</li>
              <li>• <code className="bg-zinc-800 px-1 rounded">payment_url</code> всегда открывайте в <strong>новой вкладке</strong></li>
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
          <p className="text-sm text-zinc-400 mt-1">Так выглядит страница выбора оператора, которую увидит покупатель</p>
        </CardHeader>
        <CardContent>
          <div className="bg-zinc-950 rounded-lg p-4 border border-zinc-800">
            <div className="space-y-3">
              {/* Header */}
              <div className="flex justify-between items-center border-b border-zinc-800 pb-3">
                <span className="text-zinc-400 text-sm">Все методы оплаты ▼</span>
                <div className="text-right">
                  <div className="text-zinc-500 text-xs">Пополнение</div>
                  <div className="text-emerald-400 font-bold">1 000 RUB</div>
                </div>
              </div>
              
              {/* Operators */}
              <div className="text-xs text-zinc-500 flex justify-between">
                <span>3 операторов</span>
                <span>Лучшая цена сверху</span>
              </div>
              
              {/* Operator Card */}
              <div className="bg-zinc-800/50 rounded-lg p-3 border border-emerald-500/30">
                <div className="flex justify-between items-start">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-zinc-200 font-medium">👤 Пользователь Два</span>
                      <span className="text-xs bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded">Лучшая цена</span>
                    </div>
                    <div className="text-xs text-zinc-500 mt-1">✓ 97%  •  70 сделок</div>
                    <div className="flex gap-2 mt-2">
                      <span className="text-xs bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded">Карта</span>
                      <span className="text-xs bg-purple-500/20 text-purple-400 px-2 py-0.5 rounded">СБП</span>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-emerald-400 font-bold">1 003,58 RUB</div>
                    <div className="text-xs text-zinc-500">+0.4%</div>
                  </div>
                </div>
              </div>

              {/* Another Operator */}
              <div className="bg-zinc-800/50 rounded-lg p-3 border border-zinc-700">
                <div className="flex justify-between items-start">
                  <div>
                    <div className="text-zinc-200 font-medium">👤 Пользователь Три</div>
                    <div className="text-xs text-zinc-500 mt-1">✓ 96%  •  90 сделок</div>
                    <div className="flex gap-2 mt-2">
                      <span className="text-xs bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded">Карта</span>
                      <span className="text-xs bg-purple-500/20 text-purple-400 px-2 py-0.5 rounded">СБП</span>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-zinc-300 font-bold">1 009,97 RUB</div>
                    <div className="text-xs text-zinc-500">+1%</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <p className="text-xs text-zinc-500 mt-3">
            Покупатель выбирает оператора → нажимает → видит реквизиты для оплаты
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
          <p className="text-sm text-zinc-400 mt-1">После выбора оператора покупатель видит реквизиты</p>
        </CardHeader>
        <CardContent>
          <div className="bg-zinc-950 rounded-lg p-4 border border-zinc-800">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Left side - Payment */}
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <span className="text-red-400 text-sm cursor-pointer">✕ Отменить сделку</span>
                </div>
                
                <div className="text-center py-4">
                  <div className="text-zinc-400 text-sm">Переведите точную сумму</div>
                  <div className="text-orange-400 text-sm mt-1">⏱️ Осталось: 29:56</div>
                </div>
                
                <div className="bg-zinc-800 rounded-lg p-4 text-center">
                  <div className="text-zinc-500 text-xs">Сумма к оплате</div>
                  <div className="text-2xl font-bold text-white mt-1">1 009,98 RUB</div>
                </div>
                
                <div className="bg-zinc-800 rounded-lg p-4">
                  <div className="flex items-center gap-2 text-purple-400 mb-2">
                    <span>⚡</span>
                    <span className="font-medium">СБП</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <code className="text-white font-mono">+7 900 120 30 36</code>
                    <button className="text-zinc-500 hover:text-white">📋</button>
                  </div>
                  <div className="text-zinc-500 text-sm mt-1">ВТБ</div>
                </div>
                
                <button className="w-full bg-emerald-600 hover:bg-emerald-500 text-white py-3 rounded-lg font-medium">
                  ✓ Я оплатил
                </button>
              </div>
              
              {/* Right side - Chat */}
              <div className="bg-zinc-800/50 rounded-lg p-3 border border-zinc-700">
                <div className="text-sm font-medium text-zinc-300 mb-2">💬 Сообщения</div>
                <div className="text-xs text-zinc-500 mb-3">Оператор: user3</div>
                
                <div className="bg-zinc-900 rounded p-2 text-xs space-y-1">
                  <div className="text-zinc-500">📋 Сделка #trd_f6880fd4</div>
                  <div className="text-zinc-400">💰 Сумма: 1,010 ₽</div>
                  <div className="text-zinc-400">📈 Курс: 79.0 ₽/USDT</div>
                  <div className="text-zinc-400">⏱ Время: 30 минут</div>
                  <div className="text-emerald-400 mt-2">🏦 РЕКВИЗИТЫ:</div>
                  <div className="text-zinc-300">⚡ ВТБ</div>
                  <div className="text-zinc-300">+7 900 120 30 36</div>
                </div>
                
                <div className="mt-3">
                  <input 
                    type="text" 
                    placeholder="Написать сообщение..." 
                    className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-300"
                    disabled
                  />
                </div>
              </div>
            </div>
          </div>
          <p className="text-xs text-zinc-500 mt-3">
            Покупатель переводит деньги по реквизитам → нажимает "Я оплатил" → оператор подтверждает → вы получаете webhook
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

      {/* Node.js SDK */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Code className="w-5 h-5 text-green-400" />
            Node.js SDK
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-zinc-400">
            Официальный SDK для быстрой интеграции с Node.js / TypeScript:
          </p>
          <pre className="bg-zinc-950 rounded-lg p-4 text-sm font-mono text-zinc-300 border border-zinc-800">
{`npm install reptiloid-sdk

// Использование
const ReptiloidSDK = require('reptiloid-sdk');

const sdk = new ReptiloidSDK({
  apiKey: '${merchant?.api_key || 'YOUR_API_KEY'}',
  secretKey: '${merchant?.api_secret || 'YOUR_SECRET_KEY'}',
  merchantId: '${merchant?.id || 'YOUR_MERCHANT_ID'}',
  baseUrl: '${BASE_URL}'
});

// Создание платежа
const invoice = await sdk.createInvoice({
  orderId: 'ORDER_123',
  amount: 1500,
  callbackUrl: 'https://yoursite.com/webhook',
  paymentMethod: 'card'
});

// Открыть страницу оплаты
window.open(invoice.paymentUrl, '_blank');

// Проверка webhook
app.post('/webhook', (req, res) => {
  const { sign, ...payload } = req.body;
  if (!sdk.verifyWebhook(payload, sign)) {
    return res.status(401).json({ status: 'error' });
  }
  // Обработка...
  res.json({ status: 'ok' });
});`}
          </pre>
        </CardContent>
      </Card>

      {/* Full Documentation Link */}
      <Card className="bg-gradient-to-r from-emerald-500/10 to-blue-500/10 border-emerald-500/30">
        <CardContent className="py-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-bold text-lg">Полная документация</h3>
              <p className="text-sm text-zinc-400">Все endpoints, примеры, коды ошибок</p>
            </div>
            <Button 
              className="bg-emerald-500 hover:bg-emerald-600"
              onClick={() => window.open(`${BASE_URL}/api/v1/invoice/docs`, '_blank')}
            >
              <ExternalLink className="w-4 h-4 mr-2" />
              Открыть JSON Docs
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default MerchantAPI;
