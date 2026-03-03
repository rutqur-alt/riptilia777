# API Документация - Invoice API v1

## Общая информация

REST API для приема рублевых платежей через систему p2p-обмена на USDT.

### Базовый URL
```
https://p2p-gateway.preview.emergentagent.com/api/v1/invoice
```

### Аутентификация
Все запросы требуют передачи API ключа в заголовке:
```
X-Api-Key: <ваш_api_key>
```

### Rate Limiting
| Endpoint | Лимит |
|----------|-------|
| POST /create | 60 запросов/мин |
| GET /status | 120 запросов/мин |
| GET /transactions | 30 запросов/мин |

При превышении лимита возвращается HTTP 429:
```json
{
  "status": "error",
  "code": "RATE_LIMIT_EXCEEDED",
  "message": "Превышен лимит запросов. Повторите через N сек."
}
```

### Подпись запросов (HMAC-SHA256)

Все запросы должны содержать подпись `sign` для верификации:

1. Собрать все параметры запроса (кроме `sign`)
2. Отсортировать по ключам в алфавитном порядке
3. Сформировать строку: `key1=value1&key2=value2&...`
4. Добавить Secret Key в конец строки
5. Вычислить HMAC-SHA256 хеш
6. Передать хеш в поле `sign`

**Пример (Python):**
```python
import hmac
import hashlib

def generate_signature(params: dict, secret_key: str) -> str:
    # Убираем sign из параметров
    sign_params = {k: v for k, v in params.items() if k != 'sign' and v is not None}
    
    # Сортируем и формируем строку
    sorted_params = sorted(sign_params.items())
    sign_string = '&'.join(f"{k}={v}" for k, v in sorted_params)
    sign_string += secret_key
    
    # HMAC-SHA256
    signature = hmac.new(
        secret_key.encode('utf-8'),
        sign_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature
```

---

## Endpoints

### 1. Создание инвойса

**POST** `/create`

Создание нового платежа. Возвращает реквизиты для оплаты.

#### Headers
```
X-Api-Key: <API_KEY>
Content-Type: application/json
```

#### Request Body
```json
{
    "merchant_id": "mrc_20250124_ABC123",
    "order_id": "UNIQUE_ORDER_123456",
    "amount": 1500.00,
    "currency": "RUB",
    "user_id": "client_789",
    "callback_url": "https://callback.merchant.com/handle",
    "description": "Пополнение счёта",
    "sign": "a1b2c3d4e5f6..."
}
```

| Параметр | Тип | Обязательный | Описание |
|----------|-----|--------------|----------|
| merchant_id | string | Да | ID мерчанта в системе |
| order_id | string | Да | Уникальный ID заказа в системе мерчанта |
| amount | number | Да | Сумма к оплате в рублях (мин. 100 ₽) |
| currency | string | Нет | Код валюты (по умолчанию "RUB") |
| user_id | string | Нет | ID пользователя в системе мерчанта |
| callback_url | string | Да | URL для callback уведомлений |
| description | string | Нет | Описание платежа |
| sign | string | Да | HMAC-SHA256 подпись |

#### Response (Success)
```json
{
    "status": "success",
    "payment_id": "inv_20250124_ABC789",
    "payment_url": "https://api.example.com/pay/inv_20250124_ABC789",
    "details": {
        "recipient": "Тинькофф Банк",
        "card_number": "5536 **** **** 1234",
        "phone_number": "+7 (999) 123-45-67",
        "comment": "UNIQUE_ORDER_123456",
        "amount": 1500.00,
        "expires_at": "2025-01-24T12:30:00Z"
    }
}
```

#### Errors
```json
{"status": "error", "code": "INVALID_SIGNATURE", "message": "Неверная подпись запроса"}
{"status": "error", "code": "INVALID_AMOUNT", "message": "Сумма меньше минимальной (100 RUB)"}
{"status": "error", "code": "DUPLICATE_ORDER_ID", "message": "Заказ с таким order_id уже существует"}
{"status": "error", "code": "NO_TRADERS_AVAILABLE", "message": "Нет доступных трейдеров для данной суммы"}
```

---

### 2. Проверка статуса платежа

**GET** `/status`

Получение текущего статуса платежа.

#### Query Parameters
```
merchant_id=<MERCHANT_ID>&order_id=<ORDER_ID>&sign=<SIGNATURE>
```

или

```
merchant_id=<MERCHANT_ID>&payment_id=<PAYMENT_ID>&sign=<SIGNATURE>
```

| Параметр | Тип | Обязательный | Описание |
|----------|-----|--------------|----------|
| merchant_id | string | Да | ID мерчанта |
| order_id | string | Нет* | ID заказа в системе мерчанта |
| payment_id | string | Нет* | ID платежа в нашей системе |
| sign | string | Да | HMAC-SHA256 подпись |

*Требуется order_id или payment_id

#### Response
```json
{
    "status": "success",
    "data": {
        "order_id": "UNIQUE_ORDER_123456",
        "payment_id": "inv_20250124_ABC789",
        "status": "paid",
        "amount": 1500.00,
        "amount_usdt": 15.79,
        "created_at": "2025-01-24T12:00:00Z",
        "paid_at": "2025-01-24T12:05:00Z",
        "expires_at": "2025-01-24T12:30:00Z"
    }
}
```

#### При статусе "dispute"
```json
{
    "status": "success",
    "data": {
        "order_id": "UNIQUE_ORDER_123456",
        "payment_id": "inv_20250124_ABC789",
        "status": "dispute",
        "amount": 1500.00,
        "dispute_url": "https://api.example.com/dispute/abc123def456"
    }
}
```

---

### 3. Список транзакций

**GET** `/transactions`

Получение списка всех транзакций мерчанта.

#### Query Parameters
| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| status | string | all | Фильтр: active, completed, dispute |
| limit | number | 50 | Количество записей |
| offset | number | 0 | Смещение |

#### Response
```json
{
    "status": "success",
    "data": {
        "transactions": [
            {
                "id": "inv_20250124_ABC789",
                "external_id": "UNIQUE_ORDER_123456",
                "amount_rub": 1500.00,
                "amount_usdt": 15.79,
                "status": "completed",
                "created_at": "2025-01-24T12:00:00Z",
                "dispute_url": null
            }
        ],
        "total": 100,
        "limit": 50,
        "offset": 0
    }
}
```

---

## Callback уведомления

После подтверждения платежа наша система отправляет POST-запрос на `callback_url`.

### Request
```
POST https://callback.merchant.com/handle
Content-Type: application/json
```

```json
{
    "order_id": "UNIQUE_ORDER_123456",
    "payment_id": "inv_20250124_ABC789",
    "status": "paid",
    "amount": 1500.00,
    "sign": "f6g7h8i9j0..."
}
```

### Статусы callback
| Статус | Описание |
|--------|----------|
| paid | Платёж успешно завершён |
| failed | Платёж не удался |
| expired | Истёк срок оплаты |

### Ожидаемый ответ
```json
{"status": "ok"}
```

HTTP код должен быть 200. При любом другом ответе система повторит отправку по схеме:
- 1 минута
- 5 минут
- 15 минут
- 1 час
- 2 часа
- 4 часа
- 12 часов
- 24 часа

**ВАЖНО:** Мерчант обязан проверять подпись `sign` во входящем callback!

---

## Система споров (Disputes)

### Ссылка на спор

При статусе `dispute` в ответе API появляется `dispute_url` - уникальная ссылка для клиента.

```json
{
    "dispute_url": "https://api.example.com/dispute/abc123def456"
}
```

### Использование

1. Клиент обращается в поддержку мерчанта с проблемой
2. Мерчант находит транзакцию в панели и копирует ссылку на спор
3. Мерчант передаёт ссылку клиенту
4. Клиент переходит по ссылке и общается напрямую с нашей поддержкой
5. После решения спора статус обновляется в API

### Жизненный цикл ссылки
- **Активна** - пока спор открыт, клиент может отправлять сообщения
- **Закрыта** - после решения спора показывается результат, но новые сообщения недоступны

---

## Статусы платежей

| Статус | Описание |
|--------|----------|
| pending | Ожидает оплаты от клиента |
| paid | Оплачен, завершён успешно |
| failed | Ошибка или отмена |
| expired | Истёк срок ожидания оплаты (30 мин) |
| dispute | Открыт спор по платежу |

---

## Коды ошибок

| Код | Описание |
|-----|----------|
| INVALID_API_KEY | Неверный API ключ |
| INVALID_SIGNATURE | Неверная подпись запроса |
| MERCHANT_MISMATCH | Merchant ID не соответствует API ключу |
| DUPLICATE_ORDER_ID | Заказ с таким order_id уже существует |
| INVALID_AMOUNT | Некорректная сумма (< 100 RUB) |
| NO_TRADERS_AVAILABLE | Нет доступных трейдеров |
| NOT_FOUND | Платёж не найден |
| MISSING_PARAMS | Отсутствуют обязательные параметры |

---

## Примеры интеграции

### Python
```python
import requests
import hmac
import hashlib

API_URL = "https://api.example.com/api/v1/invoice"
API_KEY = "sk_live_xxxxxx"
SECRET_KEY = "your_secret_key"
MERCHANT_ID = "mrc_xxxxxx"

def create_signature(params, secret):
    sign_params = {k: v for k, v in sorted(params.items()) if v is not None}
    sign_string = '&'.join(f"{k}={v}" for k, v in sign_params.items())
    sign_string += secret
    return hmac.new(secret.encode(), sign_string.encode(), hashlib.sha256).hexdigest()

def create_invoice(order_id, amount, callback_url, user_id=None):
    params = {
        "merchant_id": MERCHANT_ID,
        "order_id": order_id,
        "amount": amount,
        "currency": "RUB",
        "user_id": user_id,
        "callback_url": callback_url
    }
    params["sign"] = create_signature(params, SECRET_KEY)
    
    response = requests.post(
        f"{API_URL}/create",
        json=params,
        headers={"X-Api-Key": API_KEY}
    )
    return response.json()

# Создание платежа
result = create_invoice(
    order_id="ORDER_001",
    amount=1500,
    callback_url="https://mysite.com/callback"
)
print(result)
```

### PHP
```php
<?php
$api_url = "https://api.example.com/api/v1/invoice";
$api_key = "sk_live_xxxxxx";
$secret_key = "your_secret_key";
$merchant_id = "mrc_xxxxxx";

function create_signature($params, $secret) {
    ksort($params);
    $sign_string = http_build_query($params) . $secret;
    return hash_hmac('sha256', $sign_string, $secret);
}

function create_invoice($order_id, $amount, $callback_url) {
    global $api_url, $api_key, $secret_key, $merchant_id;
    
    $params = [
        'merchant_id' => $merchant_id,
        'order_id' => $order_id,
        'amount' => $amount,
        'currency' => 'RUB',
        'callback_url' => $callback_url
    ];
    $params['sign'] = create_signature($params, $secret_key);
    
    $ch = curl_init($api_url . '/create');
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($params));
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        'X-Api-Key: ' . $api_key,
        'Content-Type: application/json'
    ]);
    
    $response = curl_exec($ch);
    curl_close($ch);
    
    return json_decode($response, true);
}

// Использование
$result = create_invoice('ORDER_001', 1500, 'https://mysite.com/callback');
print_r($result);
?>
```

---

## Поддержка

При возникновении вопросов по интеграции обращайтесь в техническую поддержку.
