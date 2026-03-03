# Пример интеграции с Bitarbitr API

## Python пример

```python
import hmac
import hashlib
import requests

# Ваши ключи из личного кабинета мерчанта
API_KEY = "sk_live_ваш_api_ключ"
SECRET_KEY = "ваш_secret_key"
MERCHANT_ID = "merch_ваш_id"
BASE_URL = "https://bitarbitr.org/api/v1/invoice"

# ВАЖНО! Поля которые участвуют в подписи для /create
SIGN_FIELDS = ['merchant_id', 'order_id', 'amount', 'currency', 'user_id', 'callback_url', 'payment_method']

def generate_signature(params: dict, secret_key: str) -> str:
    """
    Генерация HMAC-SHA256 подписи для Bitarbitr API
    
    ВАЖНО:
    - Только поля из SIGN_FIELDS участвуют в подписи
    - float приводится к int если число целое (1500.0 → 1500)
    - description и другие поля НЕ участвуют в подписи
    """
    sign_params = {}
    for k, v in params.items():
        if k not in SIGN_FIELDS or k == 'sign' or v is None:
            continue
        # Приводим float к int если число целое
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
    ).hexdigest()


def get_payment_methods():
    """Получить доступные способы оплаты"""
    response = requests.get(
        f"{BASE_URL}/payment-methods",
        headers={"X-Api-Key": API_KEY}
    )
    return response.json()["payment_methods"]


def create_invoice(order_id: str, amount: int, callback_url: str, payment_method: str = None, user_id: str = None):
    """
    Создание инвойса на оплату
    
    ВАЖНО: amount должен быть int, не float!
    """
    params = {
        "merchant_id": MERCHANT_ID,
        "order_id": order_id,
        "amount": amount,  # Используйте int!
        "currency": "RUB",
        "callback_url": callback_url,
        "payment_method": payment_method,
        "user_id": user_id
    }
    
    # Генерируем подпись
    params["sign"] = generate_signature(params, SECRET_KEY)
    
    # description можно добавить ПОСЛЕ генерации подписи
    params["description"] = "Оплата заказа"
    
    response = requests.post(
        f"{BASE_URL}/create",
        json=params,
        headers={"X-Api-Key": API_KEY, "Content-Type": "application/json"}
    )
    return response.json()


def check_status(order_id: str):
    """Проверить статус платежа"""
    params = {
        "merchant_id": MERCHANT_ID,
        "order_id": order_id
    }
    params["sign"] = generate_signature(params, SECRET_KEY)
    
    response = requests.get(
        f"{BASE_URL}/status",
        params=params,
        headers={"X-Api-Key": API_KEY}
    )
    return response.json()


# ============ ПРИМЕР ИСПОЛЬЗОВАНИЯ ============

if __name__ == "__main__":
    # 1. Получаем способы оплаты (показываем покупателю на ВАШЕМ сайте)
    methods = get_payment_methods()
    print("Доступные способы оплаты:")
    for m in methods:
        print(f"  - {m['id']}: {m['name']}")
    
    # 2. Покупатель выбрал способ оплаты на вашем сайте
    selected_method = "card"  # или "sbp", "sim" и т.д.
    
    # 3. Создаём инвойс
    result = create_invoice(
        order_id="ORDER_12345",
        amount=1500,  # ВАЖНО: int, не float!
        callback_url="https://yoursite.com/payment/callback",
        payment_method=selected_method,
        user_id="user_123"
    )
    
    print("\nРезультат создания инвойса:")
    print(result)
    
    # 4. Перенаправляем покупателя на страницу оплаты
    # ВАЖНО: открывайте в новой вкладке!
    if result.get("status") == "success":
        payment_url = result["payment_url"]
        print(f"\nОткройте в браузере: {payment_url}")
        # На фронтенде: window.open(payment_url, '_blank')
    
    # 5. Проверка статуса (опционально, можно использовать webhook)
    status = check_status("ORDER_12345")
    print(f"\nСтатус платежа: {status}")
```

---

## JavaScript пример

```javascript
const CryptoJS = require('crypto-js'); // npm install crypto-js

// Ваши ключи из личного кабинета мерчанта
const API_KEY = 'sk_live_ваш_api_ключ';
const SECRET_KEY = 'ваш_secret_key';
const MERCHANT_ID = 'merch_ваш_id';
const API_BASE = 'https://bitarbitr.org/api/v1/invoice';

// ВАЖНО! Поля которые участвуют в подписи для /create
const SIGN_FIELDS = ['merchant_id', 'order_id', 'amount', 'currency', 'user_id', 'callback_url', 'payment_method'];

/**
 * Генерация подписи для Bitarbitr API
 * 
 * ВАЖНО:
 * - Только поля из SIGN_FIELDS участвуют в подписи
 * - Числа должны быть целыми (1500, не 1500.0)
 * - description и другие поля НЕ участвуют в подписи
 */
function generateSignature(params, secretKey) {
  const signParams = {};
  
  for (const [key, value] of Object.entries(params)) {
    if (!SIGN_FIELDS.includes(key) || key === 'sign' || value === null || value === undefined) {
      continue;
    }
    // Приводим к int если число целое
    let v = value;
    if (typeof v === 'number' && Number.isInteger(v)) {
      v = Math.floor(v);
    }
    signParams[key] = v;
  }
  
  const sortedKeys = Object.keys(signParams).sort();
  const signString = sortedKeys.map(k => `${k}=${signParams[k]}`).join('&') + secretKey;
  
  return CryptoJS.HmacSHA256(signString, secretKey).toString();
}

/**
 * Получить доступные способы оплаты
 */
async function getPaymentMethods() {
  const res = await fetch(`${API_BASE}/payment-methods`, {
    headers: { 'X-Api-Key': API_KEY }
  });
  const data = await res.json();
  return data.payment_methods;
}

/**
 * Создать инвойс на оплату
 * 
 * ВАЖНО: amount должен быть целым числом!
 */
async function createInvoice(orderId, amount, callbackUrl, paymentMethod, userId = null) {
  const params = {
    merchant_id: MERCHANT_ID,
    order_id: orderId,
    amount: Math.floor(amount), // Используйте целое число!
    currency: 'RUB',
    callback_url: callbackUrl,
    payment_method: paymentMethod,
    user_id: userId
  };
  
  // Генерируем подпись
  params.sign = generateSignature(params, SECRET_KEY);
  
  // description можно добавить ПОСЛЕ генерации подписи
  params.description = 'Оплата заказа';
  
  const res = await fetch(`${API_BASE}/create`, {
    method: 'POST',
    headers: { 
      'X-Api-Key': API_KEY, 
      'Content-Type': 'application/json' 
    },
    body: JSON.stringify(params)
  });
  
  return await res.json();
}

// ============ ПРИМЕР ИСПОЛЬЗОВАНИЯ ============

async function main() {
  // 1. Получаем способы оплаты
  const methods = await getPaymentMethods();
  console.log('Доступные способы оплаты:', methods);
  
  // 2. Создаём инвойс
  const result = await createInvoice(
    'ORDER_' + Date.now(),
    1500, // ВАЖНО: целое число!
    'https://yoursite.com/callback',
    'card',
    'user_123'
  );
  
  console.log('Результат:', result);
  
  // 3. Открываем страницу оплаты в новой вкладке
  if (result.status === 'success') {
    // На фронтенде:
    // window.open(result.payment_url, '_blank');
    console.log('Откройте:', result.payment_url);
  }
}

main();
```

---

## Webhook (callback)

При изменении статуса платежа на ваш `callback_url` придёт POST запрос:

```json
{
  "order_id": "ORDER_12345",
  "payment_id": "inv_20250128_ABC123",
  "status": "paid",
  "amount": 1500,
  "amount_usdt": 15.50,
  "timestamp": "2025-01-28T12:00:00Z",
  "sign": "abc123..."
}
```

**Статусы:**
- `paid` — платёж успешно завершён
- `cancelled` — платёж отменён
- `expired` — истёк срок ожидания
- `dispute` — открыт спор

**Важно:** Проверяйте подпись в callback для безопасности!

---

## Частые ошибки

### INVALID_SIGNATURE

1. **Неправильные поля в подписи** — используйте ТОЛЬКО: `merchant_id`, `order_id`, `amount`, `currency`, `user_id`, `callback_url`, `payment_method`
2. **float вместо int** — `1500.0` должно быть `1500`
3. **description в подписи** — НЕ включайте `description` в подпись!

### Страница оплаты не открывается

Убедитесь что открываете `payment_url` в **новой вкладке**:
```javascript
window.open(result.payment_url, '_blank');
```

---

## Контакты поддержки

При возникновении вопросов обращайтесь в поддержку Bitarbitr.
