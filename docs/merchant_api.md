# Reptiloid Merchant API v1

## Документация по интеграции платёжной системы

**Версия API:** 1.0  
**Базовый URL:** `https://your-domain.com/api/merchant/v1`

---

## Содержание

1. [Введение](#введение)
2. [Аутентификация](#аутентификация)
3. [Генерация HMAC подписи](#генерация-hmac-подписи)
4. [Эндпоинты API](#эндпоинты-api)
   - [Авторизация](#авторизация)
   - [Создание счёта](#создание-счёта)
   - [Статус счёта](#статус-счёта)
   - [Баланс мерчанта](#баланс-мерчанта)
   - [Список транзакций](#список-транзакций)
   - [Список операторов](#список-операторов)
   - [Получение реквизитов](#получение-реквизитов)
   - [Отметка оплаты](#отметка-оплаты)
   - [Открытие спора](#открытие-спора)
   - [Сообщения спора](#сообщения-спора)
   - [Отправка сообщения в спор](#отправка-сообщения-в-спор)
5. [Вебхуки](#вебхуки)
6. [Примеры кода](#примеры-кода)
7. [Коды ошибок](#коды-ошибок)

---

## Введение

Merchant API позволяет интегрировать приём платежей через P2P-операторов на вашем сайте. 

### Главный принцип: Клиент НИКОГДА не покидает ваш сайт

Весь процесс оплаты происходит через API. Клиент видит только ваш домен, реквизиты отображаются на вашем сайте, споры ведутся через ваш интерфейс.

### Схема работы

```
ВАШ САЙТ (casino.com)                         REPTILOID API
─────────────────────────────────────────────────────────────

1. Клиент нажимает "Пополнить 1000₽"
   
2. Ваш сервер ────────────────────────→  POST /invoice/create
              ←────────────────────────  { invoice_id: "INV_..." }

3. Ваш сервер ────────────────────────→  POST /operators
              ←────────────────────────  { operators: [...] }
   
   ВЫ показываете клиенту список операторов на ВАШЕМ сайте

4. Клиент выбирает оператора → ваш сервер создаёт trade

5. Ваш сервер ────────────────────────→  POST /invoice/requisites
              ←────────────────────────  { card: "4276...", bank: "Сбер" }
   
   ВЫ показываете реквизиты клиенту на ВАШЕМ сайте

6. Клиент переводит деньги по реквизитам

7. Клиент нажимает "Я оплатил" на ВАШЕМ сайте
   Ваш сервер ────────────────────────→  POST /invoice/mark-paid

8. Оператор подтверждает ─────────────→  Webhook "completed" на ваш сервер

9. ВЫ начисляете товар/услугу клиенту
```

### Споры — тоже через API

Если клиент хочет открыть спор или написать в чат спора — это тоже делается через API:
- `POST /disputes/open` — открыть спор
- `POST /disputes/messages` — получить сообщения
- `POST /disputes/send-message` — отправить сообщение от имени клиента

Клиент **никогда** не переходит на наш домен.

---

## Аутентификация

Все запросы требуют три параметра аутентификации:

| Параметр | Описание |
|----------|----------|
| `api_key` | Публичный ключ API (выдаётся в личном кабинете) |
| `api_secret` | Секретный ключ API (храните в безопасности!) |
| `merchant_id` | Ваш уникальный идентификатор мерчанта |

**Важно:** Никогда не передавайте `api_secret` в клиентский код!

---

## Генерация HMAC подписи

Для дополнительной безопасности можно использовать HMAC-SHA256 подпись.

### Алгоритм:

1. Собрать JSON объект с параметрами запроса (без поля `signature`)
2. Отсортировать ключи по алфавиту
3. Сериализовать в строку JSON
4. Вычислить HMAC-SHA256 с использованием `api_secret`

### Python:
```python
import hmac
import hashlib
import json

def generate_signature(api_secret: str, data: dict) -> str:
    sorted_data = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hmac.new(
        api_secret.encode('utf-8'),
        sorted_data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

# Пример
data = {
    "api_key": "your_api_key",
    "merchant_id": "your_merchant_id",
    "amount_rub": 1000
}
signature = generate_signature("your_api_secret", data)
```

### PHP:
```php
function generateSignature(string $apiSecret, array $data): string {
    ksort($data);
    $jsonData = json_encode($data, JSON_UNESCAPED_UNICODE);
    return hash_hmac('sha256', $jsonData, $apiSecret);
}

// Пример
$data = [
    'api_key' => 'your_api_key',
    'merchant_id' => 'your_merchant_id',
    'amount_rub' => 1000
];
$signature = generateSignature('your_api_secret', $data);
```

### Node.js:
```javascript
const crypto = require('crypto');

function generateSignature(apiSecret, data) {
    const sortedKeys = Object.keys(data).sort();
    const sortedData = {};
    sortedKeys.forEach(key => sortedData[key] = data[key]);
    const jsonData = JSON.stringify(sortedData);
    return crypto.createHmac('sha256', apiSecret).update(jsonData).digest('hex');
}

// Пример
const data = {
    api_key: 'your_api_key',
    merchant_id: 'your_merchant_id',
    amount_rub: 1000
};
const signature = generateSignature('your_api_secret', data);
```

---

## Эндпоинты API

### Авторизация

Проверка API ключей и получение информации о мерчанте.

**POST** `/merchant/v1/auth`

#### Запрос:
```json
{
    "api_key": "your_api_key",
    "api_secret": "your_api_secret",
    "merchant_id": "your_merchant_id"
}
```

#### Ответ:
```json
{
    "success": true,
    "merchant_id": "222",
    "merchant_name": "My Shop",
    "balance_usdt": 150.25,
    "balance_rub": 11744.53,
    "commission_rate": 10.0,
    "total_client_rub": 50000.00,
    "total_received_rub": 45000.00,
    "transactions_count": 47,
    "status": "active",
    "exchange_rate": 78.15
}
```

---

### Создание счёта

Создать новый счёт на оплату.

**POST** `/merchant/v1/invoice/create`

#### Запрос:
```json
{
    "api_key": "your_api_key",
    "api_secret": "your_api_secret",
    "merchant_id": "your_merchant_id",
    "amount_rub": 1000,
    "order_id": "ORDER_12345",
    "description": "Пополнение баланса",
    "callback_url": "https://your-site.com/webhook",
    "signature": "optional_hmac_signature"
}
```

| Параметр | Тип | Обязательный | Описание |
|----------|-----|--------------|----------|
| `amount_rub` | int | Да | Сумма пополнения (что получит клиент на вашем сайте) |
| `order_id` | string | Нет | Ваш внутренний номер заказа |
| `description` | string | Нет | Описание платежа |
| `callback_url` | string | Нет | URL для получения вебхуков |
| `signature` | string | Нет | HMAC подпись для дополнительной безопасности |

#### Ответ:
```json
{
    "success": true,
    "invoice_id": "INV_20241215123456_A1B2C3D4",
    "amount_rub": 1000,
    "amount_usdt": 12.79,
    "merchant_commission_percent": 10.0,
    "merchant_receives_rub": 900.00,
    "status": "pending",
    "expires_at": "2024-12-15T14:34:56+00:00"
}
```

> **Важно:** После создания счёта вызовите `/operators` для получения списка операторов и покажите их клиенту на ВАШЕМ сайте.

---

### Статус счёта

Получить текущий статус счёта.

**POST** `/merchant/v1/invoice/status`

#### Запрос:
```json
{
    "api_key": "your_api_key",
    "api_secret": "your_api_secret",
    "merchant_id": "your_merchant_id",
    "invoice_id": "INV_20241215123456_A1B2C3D4"
}
```

#### Ответ:
```json
{
    "success": true,
    "invoice_id": "INV_20241215123456_A1B2C3D4",
    "status": "completed",
    "amount_rub": 1000,
    "client_amount_rub": 1000,
    "client_paid_rub": 1015,
    "merchant_receives_rub": 900.00,
    "trade_id": "trd_abc12345",
    "paid_at": "2024-12-15T13:45:00+00:00",
    "completed_at": "2024-12-15T13:50:00+00:00"
}
```

---

### Баланс мерчанта

Получить текущий баланс и статистику.

**POST** `/merchant/v1/balance`

#### Запрос:
```json
{
    "api_key": "your_api_key",
    "api_secret": "your_api_secret",
    "merchant_id": "your_merchant_id"
}
```

#### Ответ:
```json
{
    "success": true,
    "balance_usdt": 150.25,
    "total_client_rub": 50000.00,
    "total_received_rub": 45000.00,
    "total_received_usdt": 575.85,
    "transactions_count": 47,
    "exchange_rate": 78.15
}
```

---

### Список транзакций

Получить историю транзакций.

**POST** `/merchant/v1/transactions`

#### Запрос:
```json
{
    "api_key": "your_api_key",
    "api_secret": "your_api_secret",
    "merchant_id": "your_merchant_id",
    "status": "completed",
    "limit": 50,
    "offset": 0
}
```

| Параметр | Тип | Обязательный | Описание |
|----------|-----|--------------|----------|
| `status` | string | Нет | Фильтр по статусу (pending, paid, completed, cancelled, disputed) |
| `limit` | int | Нет | Количество записей (по умолчанию 50) |
| `offset` | int | Нет | Смещение для пагинации |

#### Ответ:
```json
{
    "success": true,
    "transactions": [
        {
            "id": "trd_abc12345",
            "client_amount_rub": 1000,
            "client_pays_rub": 1015,
            "merchant_receives_rub": 900,
            "status": "completed",
            "created_at": "2024-12-15T13:30:00+00:00",
            "completed_at": "2024-12-15T13:50:00+00:00"
        }
    ],
    "total": 47
}
```

---

### Список операторов

Получить список доступных операторов (трейдеров) для указанной суммы.

**POST** `/merchant/v1/operators`

#### Запрос:
```json
{
    "api_key": "your_api_key",
    "api_secret": "your_api_secret",
    "merchant_id": "your_merchant_id",
    "amount_rub": 1000
}
```

#### Ответ:
```json
{
    "success": true,
    "amount_rub": 1000,
    "base_rate": 78.15,
    "operators": [
        {
            "operator_id": "offer_123",
            "trader_id": "trader_456",
            "nickname": "Пользователь Два",
            "is_online": true,
            "success_rate": 97,
            "trades_count": 70,
            "price_rub": 78.50,
            "to_pay_rub": 1003.58,
            "commission_percent": 0.4,
            "min_amount_rub": 500,
            "max_amount_rub": 50000,
            "payment_methods": ["card", "sbp"],
            "requisites": [
                {
                    "id": "req_001",
                    "type": "card",
                    "bank_name": "Тинькофф"
                },
                {
                    "id": "req_002",
                    "type": "sbp",
                    "bank_name": "Тинькофф"
                }
            ]
        }
    ]
}
```

#### Пример UI: Выбор оператора

```
┌─────────────────────────────────────────────────────────────────┐
│  Все методы оплаты ▼                          Пополнение        │
│                                                1 000 RUB        │
├─────────────────────────────────────────────────────────────────┤
│  3 операторов                            Лучшая цена сверху     │
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 👤 Пользователь Два  [Лучшая цена]                        │  │
│  │    ✓ 97%  70 сделок                                       │  │
│  │                                                           │  │
│  │    [Банковская карта] [СБП]           1 003,58 RUB +0.4%  │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 👤 Пользователь Три                                       │  │
│  │    ✓ 96%  90 сделок                                       │  │
│  │                                                           │  │
│  │    [Банковская карта] [СБП]           1 009,97 RUB +1%    │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

Поля из API для отображения:
- nickname → "Пользователь Два"
- success_rate → "97%"
- trades_count → "70 сделок"
- payment_methods → ["card", "sbp"] → иконки методов оплаты
- to_pay_rub → "1 003,58 RUB"
- commission_percent → "+0.4%"
```

---

### Получение реквизитов

После выбора оператора и создания сделки — получить реквизиты для оплаты.

**POST** `/merchant/v1/invoice/requisites`

#### Запрос:
```json
{
    "api_key": "your_api_key",
    "api_secret": "your_api_secret",
    "merchant_id": "your_merchant_id",
    "payment_id": "INV_20241215123456_A1B2C3D4"
}
```

#### Ответ:
```json
{
    "success": true,
    "payment_id": "INV_20241215123456_A1B2C3D4",
    "trade_id": "trd_abc12345",
    "status": "pending",
    "amount_rub": 1000,
    "client_amount_rub": 1000,
    "client_pays_rub": 1009.98,
    "expires_at": "2024-12-15T14:00:00+00:00",
    "requisites": [
        {
            "type": "sbp",
            "phone": "+7 900 120 30 36",
            "bank_name": "ВТБ",
            "card_holder": null
        }
    ],
    "trader_login": "user3"
}
```

| Поле | Описание |
|------|----------|
| `client_amount_rub` | Сумма пополнения клиента (1000 RUB) |
| `client_pays_rub` | Сумма к оплате с наценкой оператора (1009.98 RUB) |
| `requisites[].type` | Тип: `card`, `sbp`, `sim`, `qr` |
| `requisites[].phone` | Телефон (для СБП) |
| `requisites[].card_number` | Номер карты (для card) |
| `requisites[].bank_name` | Название банка |

#### Пример UI: Экран оплаты с реквизитами

```
┌──────────────────────────────────────┐  ┌─────────────────────────────────┐
│  ✕ Отменить сделку                   │  │  💬 Сообщения                   │
│                                      │  │     Оператор: user3             │
│           ⏱️                          │  ├─────────────────────────────────┤
│                                      │  │  ┌─────────────────────────────┐│
│   Переведите точную сумму            │  │  │ 📋 Сделка #trd_f6880fd4    ││
│      Осталось: 29:56                 │  │  │ 💰 Сумма к оплате: 1,010 ₽  ││
│                                      │  │  │ 📈 Курс: 79.0 ₽/USDT       ││
│  ┌────────────────────────────────┐  │  │  │ ⏱ Время: 30 минут          ││
│  │      Сумма к оплате            │  │  │  │                             ││
│  │                                │  │  │  │ 🏦 РЕКВИЗИТЫ ДЛЯ ОПЛАТЫ:   ││
│  │      1 009,98 RUB              │  │  │  │ ⚡ ВТБ                       ││
│  │                                │  │  │  │ Телефон: +7 900 120 30 36  ││
│  └────────────────────────────────┘  │  │  └─────────────────────────────┘│
│                                      │  │                                 │
│  ┌────────────────────────────────┐  │  │                                 │
│  │ ⚡ СБП                          │  │  │                                 │
│  │                                │  │  │                                 │
│  │ +7 900 120 30 36          📋  │  │  │                                 │
│  │ ВТБ                            │  │  │  ┌─────────────────────────────┐│
│  └────────────────────────────────┘  │  │  │ Написать сообщение...    ➤ ││
│                                      │  │  └─────────────────────────────┘│
│  ┌────────────────────────────────┐  │  └─────────────────────────────────┘
│  │      ✓ Я оплатил               │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘

Поля из API /invoice/requisites:
- expires_at → таймер "Осталось: 29:56"
- amount_rub → "1 009,98 RUB"
- requisites[0].type → "sbp" → "⚡ СБП"
- requisites[0].phone → "+7 900 120 30 36"
- requisites[0].bank_name → "ВТБ"

Чат справа через API:
- GET /disputes/messages → сообщения
- POST /disputes/send-message → отправка
```

---

### Отметка оплаты

Сообщить системе, что клиент перевёл деньги.

**POST** `/merchant/v1/invoice/mark-paid`

#### Запрос:
```json
{
    "api_key": "your_api_key",
    "api_secret": "your_api_secret",
    "merchant_id": "your_merchant_id",
    "payment_id": "INV_20241215123456_A1B2C3D4"
}
```

#### Ответ:
```json
{
    "success": true,
    "payment_id": "INV_20241215123456_A1B2C3D4",
    "trade_id": "trd_abc12345",
    "status": "paid",
    "paid_at": "2024-12-15T13:45:00+00:00",
    "message": "Ожидайте подтверждения от оператора"
}
```

---

### Открытие спора

Открыть спор по платежу (доступно через 10 минут после отметки "оплачено").

**POST** `/merchant/v1/disputes/open`

#### Запрос:
```json
{
    "api_key": "your_api_key",
    "api_secret": "your_api_secret",
    "merchant_id": "your_merchant_id",
    "payment_id": "INV_20241215123456_A1B2C3D4",
    "reason": "Оператор не подтверждает оплату"
}
```

#### Ответ:
```json
{
    "success": true,
    "payment_id": "INV_20241215123456_A1B2C3D4",
    "trade_id": "trd_abc12345",
    "status": "disputed",
    "reason": "Оператор не подтверждает оплату",
    "disputed_at": "2024-12-15T14:00:00+00:00"
}
```

---

### Сообщения спора

Получить историю сообщений спора.

**POST** `/merchant/v1/disputes/messages`

#### Запрос:
```json
{
    "api_key": "your_api_key",
    "api_secret": "your_api_secret",
    "merchant_id": "your_merchant_id",
    "payment_id": "INV_20241215123456_A1B2C3D4"
}
```

#### Ответ:
```json
{
    "success": true,
    "trade_id": "trd_abc12345",
    "status": "disputed",
    "messages": [
        {
            "id": "msg_001",
            "sender_type": "system",
            "content": "Спор открыт клиентом!",
            "created_at": "2024-12-15T14:00:00+00:00"
        },
        {
            "id": "msg_002",
            "sender_type": "admin",
            "content": "Администратор подключился к чату",
            "created_at": "2024-12-15T14:01:00+00:00"
        }
    ]
}
```

---

### Отправка сообщения в спор

Отправить сообщение в чат спора от имени клиента мерчанта.

**POST** `/merchant/v1/disputes/send-message`

#### Запрос:
```json
{
    "api_key": "your_api_key",
    "api_secret": "your_api_secret",
    "merchant_id": "your_merchant_id",
    "payment_id": "INV_20241215123456_A1B2C3D4",
    "message": "Я перевёл деньги, вот чек",
    "sender_name": "Клиент Иван"
}
```

#### Ответ:
```json
{
    "success": true,
    "message_id": "msg_abc123",
    "created_at": "2024-12-15T14:05:00+00:00"
}
```

---

## Вебхуки

Вебхуки отправляются на URL, указанный в `callback_url` при создании счёта или в настройках мерчанта (`webhook_url`).

### Формат вебхука

```json
{
    "event": "completed",
    "payment_id": "INV_20241215123456_A1B2C3D4",
    "order_id": "ORDER_12345",
    "status": "completed",
    "amount_rub": 1000,
    "timestamp": "2024-12-15T13:50:00+00:00",
    "trade_id": "trd_abc12345",
    "sign": "hmac_signature_here"
}
```

### Проверка подписи вебхука

```python
def verify_webhook(payload: dict, api_secret: str) -> bool:
    received_sign = payload.pop('sign', None)
    if not received_sign:
        return False
    expected_sign = generate_signature(api_secret, payload)
    return hmac.compare_digest(expected_sign, received_sign)
```

### События вебхуков

| Событие | Описание |
|---------|----------|
| `pending` | Сделка создана, ожидается оплата |
| `paid` | Клиент отметил оплату, ожидается подтверждение оператора |
| `completed` | Оператор подтвердил оплату, средства зачислены |
| `cancelled` | Сделка отменена (истекло время или отказ) |
| `expired` | Счёт истёк без оплаты |
| `disputed` | Открыт спор по платежу |

### Payload для каждого события

#### pending
```json
{
    "event": "pending",
    "payment_id": "INV_...",
    "order_id": "ORDER_12345",
    "status": "pending",
    "amount_rub": 1000,
    "timestamp": "...",
    "trade_id": "trd_...",
    "client_amount_rub": 1000,
    "client_pays_rub": 1015,
    "expires_at": "...",
    "sign": "..."
}
```

#### paid
```json
{
    "event": "paid",
    "payment_id": "INV_...",
    "order_id": "ORDER_12345",
    "status": "paid",
    "amount_rub": 1000,
    "timestamp": "...",
    "trade_id": "trd_...",
    "paid_at": "...",
    "sign": "..."
}
```

#### completed
```json
{
    "event": "completed",
    "payment_id": "INV_...",
    "order_id": "ORDER_12345",
    "status": "completed",
    "amount_rub": 1000,
    "timestamp": "...",
    "trade_id": "trd_...",
    "amount_usdt": 12.79,
    "client_amount_rub": 1000,
    "merchant_receives_rub": 900,
    "merchant_receives_usdt": 11.51,
    "completed_at": "...",
    "sign": "..."
}
```

#### cancelled

Отправляется при отмене сделки (вручную или автоматически по таймауту).

```json
{
    "event": "cancelled",
    "payment_id": "INV_...",
    "order_id": "ORDER_12345",
    "status": "cancelled",
    "amount_rub": 1000,
    "timestamp": "...",
    "trade_id": "trd_...",
    "reason": "auto_timeout",
    "cancel_reason": "Клиент не оплатил в течение 30 минут",
    "cancelled_at": "...",
    "cancelled_by": "system",
    "sign": "..."
}
```

**Возможные значения `reason`:**
| Значение | Описание |
|----------|----------|
| `auto_timeout` | Автоматическая отмена — клиент не нажал "Оплатил" в течение 30 минут |
| `buyer_cancelled` | Клиент сам отменил сделку |
| `seller_cancelled` | Оператор отменил сделку |
| `admin_cancelled` | Администратор отменил сделку |

**Поля:**
- `reason` — краткий код причины отмены
- `cancel_reason` — человекочитаемое описание причины
- `cancelled_by` — кто отменил: `system`, `buyer`, `seller`, `admin`

#### disputed
```json
{
    "event": "disputed",
    "payment_id": "INV_...",
    "order_id": "ORDER_12345",
    "status": "disputed",
    "amount_rub": 1000,
    "timestamp": "...",
    "trade_id": "trd_...",
    "reason": "Оператор не подтверждает оплату",
    "disputed_at": "...",
    "disputed_by": "клиентом",
    "sign": "..."
}
```

---

## Примеры кода

### PHP — Полный пример интеграции

```php
<?php

class ReptiloidAPI {
    private string $apiKey;
    private string $apiSecret;
    private string $merchantId;
    private string $baseUrl;

    public function __construct(string $apiKey, string $apiSecret, string $merchantId, string $baseUrl = 'https://your-domain.com/api') {
        $this->apiKey = $apiKey;
        $this->apiSecret = $apiSecret;
        $this->merchantId = $merchantId;
        $this->baseUrl = $baseUrl;
    }

    private function request(string $endpoint, array $data = []): array {
        $data['api_key'] = $this->apiKey;
        $data['api_secret'] = $this->apiSecret;
        $data['merchant_id'] = $this->merchantId;

        $ch = curl_init($this->baseUrl . $endpoint);
        curl_setopt_array($ch, [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => json_encode($data),
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
            CURLOPT_TIMEOUT => 30
        ]);

        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        if ($httpCode !== 200) {
            throw new Exception("API Error: HTTP $httpCode");
        }

        return json_decode($response, true);
    }

    public function auth(): array {
        return $this->request('/merchant/v1/auth');
    }

    public function createInvoice(int $amountRub, ?string $orderId = null, ?string $description = null): array {
        return $this->request('/merchant/v1/invoice/create', [
            'amount_rub' => $amountRub,
            'order_id' => $orderId,
            'description' => $description ?? 'Пополнение баланса'
        ]);
    }

    public function getInvoiceStatus(string $invoiceId): array {
        return $this->request('/merchant/v1/invoice/status', [
            'invoice_id' => $invoiceId
        ]);
    }

    public function getOperators(float $amountRub): array {
        return $this->request('/merchant/v1/operators', [
            'amount_rub' => $amountRub
        ]);
    }

    public function getRequisites(string $paymentId): array {
        return $this->request('/merchant/v1/invoice/requisites', [
            'payment_id' => $paymentId
        ]);
    }

    public function markPaid(string $paymentId): array {
        return $this->request('/merchant/v1/invoice/mark-paid', [
            'payment_id' => $paymentId
        ]);
    }

    public function openDispute(string $paymentId, string $reason = ''): array {
        return $this->request('/merchant/v1/disputes/open', [
            'payment_id' => $paymentId,
            'reason' => $reason
        ]);
    }

    public function getDisputeMessages(string $paymentId): array {
        return $this->request('/merchant/v1/disputes/messages', [
            'payment_id' => $paymentId
        ]);
    }

    public function sendDisputeMessage(string $paymentId, string $message, string $senderName = 'Клиент'): array {
        return $this->request('/merchant/v1/disputes/send-message', [
            'payment_id' => $paymentId,
            'message' => $message,
            'sender_name' => $senderName
        ]);
    }

    public static function verifyWebhook(array $payload, string $apiSecret): bool {
        $receivedSign = $payload['sign'] ?? null;
        if (!$receivedSign) return false;
        
        unset($payload['sign']);
        ksort($payload);
        $expectedSign = hash_hmac('sha256', json_encode($payload, JSON_UNESCAPED_UNICODE), $apiSecret);
        
        return hash_equals($expectedSign, $receivedSign);
    }
}

// Использование
$api = new ReptiloidAPI('your_api_key', 'your_api_secret', 'your_merchant_id');

// Создать счёт
$invoice = $api->createInvoice(1000, 'ORDER_123', 'Пополнение баланса');
echo "Invoice ID: " . $invoice['invoice_id'];

// Получить операторов
$operators = $api->getOperators(1000);
foreach ($operators['operators'] as $op) {
    echo "{$op['nickname']}: {$op['to_pay_rub']} RUB\n";
}

// Webhook handler
$webhookPayload = json_decode(file_get_contents('php://input'), true);
if (ReptiloidAPI::verifyWebhook($webhookPayload, 'your_api_secret')) {
    switch ($webhookPayload['event']) {
        case 'completed':
            // Начислить товар клиенту
            break;
        case 'cancelled':
            // Отменить заказ
            break;
    }
}
```

### Python — Полный пример интеграции

```python
import requests
import hmac
import hashlib
import json
from typing import Optional

class ReptiloidAPI:
    def __init__(self, api_key: str, api_secret: str, merchant_id: str, base_url: str = 'https://your-domain.com/api'):
        self.api_key = api_key
        self.api_secret = api_secret
        self.merchant_id = merchant_id
        self.base_url = base_url

    def _request(self, endpoint: str, data: dict = None) -> dict:
        if data is None:
            data = {}
        
        data['api_key'] = self.api_key
        data['api_secret'] = self.api_secret
        data['merchant_id'] = self.merchant_id

        response = requests.post(
            f"{self.base_url}{endpoint}",
            json=data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    def auth(self) -> dict:
        return self._request('/merchant/v1/auth')

    def create_invoice(self, amount_rub: int, order_id: str = None, description: str = None) -> dict:
        return self._request('/merchant/v1/invoice/create', {
            'amount_rub': amount_rub,
            'order_id': order_id,
            'description': description or 'Пополнение баланса'
        })

    def get_invoice_status(self, invoice_id: str) -> dict:
        return self._request('/merchant/v1/invoice/status', {
            'invoice_id': invoice_id
        })

    def get_operators(self, amount_rub: float) -> dict:
        return self._request('/merchant/v1/operators', {
            'amount_rub': amount_rub
        })

    def get_requisites(self, payment_id: str) -> dict:
        return self._request('/merchant/v1/invoice/requisites', {
            'payment_id': payment_id
        })

    def mark_paid(self, payment_id: str) -> dict:
        return self._request('/merchant/v1/invoice/mark-paid', {
            'payment_id': payment_id
        })

    def open_dispute(self, payment_id: str, reason: str = '') -> dict:
        return self._request('/merchant/v1/disputes/open', {
            'payment_id': payment_id,
            'reason': reason
        })

    def get_dispute_messages(self, payment_id: str) -> dict:
        return self._request('/merchant/v1/disputes/messages', {
            'payment_id': payment_id
        })

    def send_dispute_message(self, payment_id: str, message: str, sender_name: str = 'Клиент') -> dict:
        return self._request('/merchant/v1/disputes/send-message', {
            'payment_id': payment_id,
            'message': message,
            'sender_name': sender_name
        })

    @staticmethod
    def generate_signature(api_secret: str, data: dict) -> str:
        sorted_data = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hmac.new(
            api_secret.encode('utf-8'),
            sorted_data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    @staticmethod
    def verify_webhook(payload: dict, api_secret: str) -> bool:
        received_sign = payload.pop('sign', None)
        if not received_sign:
            return False
        expected_sign = ReptiloidAPI.generate_signature(api_secret, payload)
        return hmac.compare_digest(expected_sign, received_sign)


# Использование
api = ReptiloidAPI('your_api_key', 'your_api_secret', 'your_merchant_id')

# Создать счёт
invoice = api.create_invoice(1000, 'ORDER_123', 'Пополнение баланса')
print(f"Invoice ID: {invoice['invoice_id']}")

# Получить операторов
operators = api.get_operators(1000)
for op in operators['operators']:
    print(f"{op['nickname']}: {op['to_pay_rub']} RUB")

# Flask webhook handler
from flask import Flask, request, jsonify
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook_handler():
    payload = request.get_json()
    
    if not ReptiloidAPI.verify_webhook(payload.copy(), 'your_api_secret'):
        return jsonify({'error': 'Invalid signature'}), 403
    
    event = payload.get('event')
    order_id = payload.get('order_id')
    
    if event == 'completed':
        # Начислить товар клиенту
        print(f"Order {order_id} completed!")
    elif event == 'cancelled':
        # Отменить заказ
        print(f"Order {order_id} cancelled")
    
    return jsonify({'status': 'ok'})
```

### Node.js — Полный пример интеграции

```javascript
const crypto = require('crypto');
const axios = require('axios');

class ReptiloidAPI {
    constructor(apiKey, apiSecret, merchantId, baseUrl = 'https://your-domain.com/api') {
        this.apiKey = apiKey;
        this.apiSecret = apiSecret;
        this.merchantId = merchantId;
        this.baseUrl = baseUrl;
    }

    async _request(endpoint, data = {}) {
        data.api_key = this.apiKey;
        data.api_secret = this.apiSecret;
        data.merchant_id = this.merchantId;

        const response = await axios.post(`${this.baseUrl}${endpoint}`, data, {
            headers: { 'Content-Type': 'application/json' },
            timeout: 30000
        });
        return response.data;
    }

    async auth() {
        return this._request('/merchant/v1/auth');
    }

    async createInvoice(amountRub, orderId = null, description = null) {
        return this._request('/merchant/v1/invoice/create', {
            amount_rub: amountRub,
            order_id: orderId,
            description: description || 'Пополнение баланса'
        });
    }

    async getInvoiceStatus(invoiceId) {
        return this._request('/merchant/v1/invoice/status', {
            invoice_id: invoiceId
        });
    }

    async getOperators(amountRub) {
        return this._request('/merchant/v1/operators', {
            amount_rub: amountRub
        });
    }

    async getRequisites(paymentId) {
        return this._request('/merchant/v1/invoice/requisites', {
            payment_id: paymentId
        });
    }

    async markPaid(paymentId) {
        return this._request('/merchant/v1/invoice/mark-paid', {
            payment_id: paymentId
        });
    }

    async openDispute(paymentId, reason = '') {
        return this._request('/merchant/v1/disputes/open', {
            payment_id: paymentId,
            reason: reason
        });
    }

    async getDisputeMessages(paymentId) {
        return this._request('/merchant/v1/disputes/messages', {
            payment_id: paymentId
        });
    }

    async sendDisputeMessage(paymentId, message, senderName = 'Клиент') {
        return this._request('/merchant/v1/disputes/send-message', {
            payment_id: paymentId,
            message: message,
            sender_name: senderName
        });
    }

    static generateSignature(apiSecret, data) {
        const sortedKeys = Object.keys(data).sort();
        const sortedData = {};
        sortedKeys.forEach(key => sortedData[key] = data[key]);
        const jsonData = JSON.stringify(sortedData);
        return crypto.createHmac('sha256', apiSecret).update(jsonData).digest('hex');
    }

    static verifyWebhook(payload, apiSecret) {
        const receivedSign = payload.sign;
        if (!receivedSign) return false;
        
        const payloadCopy = { ...payload };
        delete payloadCopy.sign;
        
        const expectedSign = ReptiloidAPI.generateSignature(apiSecret, payloadCopy);
        return crypto.timingSafeEqual(
            Buffer.from(expectedSign),
            Buffer.from(receivedSign)
        );
    }
}

// Использование
const api = new ReptiloidAPI('your_api_key', 'your_api_secret', 'your_merchant_id');

// Создать счёт
(async () => {
    const invoice = await api.createInvoice(1000, 'ORDER_123', 'Пополнение баланса');
    console.log(`Invoice ID: ${invoice.invoice_id}`);

    // Получить операторов
    const operators = await api.getOperators(1000);
    operators.operators.forEach(op => {
        console.log(`${op.nickname}: ${op.to_pay_rub} RUB`);
    });
})();

// Express webhook handler
const express = require('express');
const app = express();
app.use(express.json());

app.post('/webhook', (req, res) => {
    const payload = req.body;
    
    if (!ReptiloidAPI.verifyWebhook({ ...payload }, 'your_api_secret')) {
        return res.status(403).json({ error: 'Invalid signature' });
    }
    
    const event = payload.event;
    const orderId = payload.order_id;
    
    switch (event) {
        case 'completed':
            console.log(`Order ${orderId} completed!`);
            // Начислить товар клиенту
            break;
        case 'cancelled':
            console.log(`Order ${orderId} cancelled`);
            // Отменить заказ
            break;
    }
    
    res.json({ status: 'ok' });
});

app.listen(3000);

module.exports = ReptiloidAPI;
```

---

## Коды ошибок

| Код | Описание |
|-----|----------|
| `INVALID_API_KEY` | Неверный API ключ |
| `INVALID_API_SECRET` | Неверный секретный ключ |
| `INVALID_MERCHANT_ID` | Неверный ID мерчанта |
| `MERCHANT_NOT_ACTIVE` | Мерчант не активен |
| `INVALID_SIGNATURE` | Неверная HMAC подпись |
| `INVOICE_NOT_FOUND` | Счёт не найден |
| `TRADE_NOT_FOUND` | Сделка не найдена |
| `INVALID_STATUS` | Неверный статус для операции |
| `DISPUTE_COOLDOWN` | Спор можно открыть через X секунд |
| `NOT_IN_DISPUTE` | Сделка не в статусе спора |

---

## Поддержка

По вопросам интеграции обращайтесь к вашему менеджеру или в техническую поддержку.

**Email:** support@reptiloid.com  
**Telegram:** @reptiloid_support
