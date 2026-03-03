# BITARBITR P2P Platform - PRD

## Original Problem Statement
P2P платформа для обмена криптовалюты с автоматическим зачислением USDT депозитов и выводом средств через TON блокчейн.

---

## Latest Updates (28.01.2026)

### ✅ Trader Work Mode Toggle
- Добавлен переключатель "На линии / Офлайн" в header рабочего стола трейдера
- Красный баннер с кнопкой "Включить" когда режим работы выключен
- API: `PUT /trader/profile?is_available=true/false`
- Toast уведомления при переключении режима

### ✅ Фильтрация и лимиты трейдера (NEW!)
- **Мультиселект методов оплаты**:
  - Dropdown с галочками для выбора нескольких методов
  - Выбранные методы показываются тегами с крестиками
  - Кнопка "Сбросить выбор" в dropdown
- **Фильтры на рабочем столе**:
  - По сумме (мин/макс в рублях)
  - По методам оплаты (Карта, СБП, SIM, Mono, СНГ и т.д.)
- **Настройка лимитов**:
  - Модальное окно для настройки мин/макс суммы сделок
  - Заявки вне лимитов отображаются с пометкой "Вне лимитов"
- **API обновлён**:
  - `GET /trader/available-orders?min_amount=X&max_amount=Y&payment_methods=card,sbp,sim`
  - `PUT /trader/profile?min_deal_amount_rub=X&max_deal_amount_rub=Y`
- Каждая заявка содержит метаданные: `can_accept`, `reason`, `within_limits`, `method_compatible`

---

## Hot Wallet Configuration
- **Address**: `UQDqsQMz1OsKtj4UlXJFbU4WYJghZKyugYVvWZE0WwA5liux`
- **Wallet Type**: Wallet V5 R1
- **USDT Contract**: `EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs`

## Tech Stack
- **Backend**: FastAPI + Motor (async MongoDB)
- **Frontend**: React + Shadcn/UI
- **Blockchain**: TON (tonutils, pytoniq-core, TonAPI)
- **Database**: MongoDB

---

## Implemented Features (27.01.2026)

### ✅ External Site Integration (NEW!)
- `GET /api/v1/invoice/payment-methods` — получение списка способов оплаты
- `POST /api/v1/invoice/create` — создание инвойса, возвращает `payment_url`
- Страница оплаты открывается в **новой вкладке** на домене платформы
- DemoShop работает как полностью внешний сайт
- Реквизиты НЕ передаются на сайт мерчанта (безопасность)

### ✅ Payment Details Display
- Все типы реквизитов отображаются покупателю: card, sbp, sim, qr_code, mono_bank, sng_sbp, sng_card
- Поддержка: card_number, phone_number, qr_data, manual_text, account_number

### ✅ Dispute System
- Трейдер отображается зелёным как "Трейдер" (не "Клиент")
- Кнопка "Завершить в пользу покупателя" работает на рабочем столе трейдера
- Кнопка "Платёж получен - закрыть спор" в чате спора
- Покупатель может отменить заказ в любом статусе

### ✅ Order Management
- Покупатель может отменить заказ даже после "Я оплатил"
- Трейдер может завершить сделку в любом статусе (включая спор)
- Автоматический возврат USDT при истечении заказа

### ✅ Notification System
- In-app уведомления для всех ролей
- Telegram уведомления и broadcast
- События: новые заказы, споры, сообщения, депозиты, выводы

### ✅ TON Service Module
- `TonService` class with all TON operations
- `send_usdt()` - отправка USDT через TON (WalletV5R1)
- `check_incoming_transactions()` - мониторинг входящих транзакций
- Auto-deposit processing

### ✅ Referral System (USDT)
- Считается от **ЗАРАБОТКА трейдера** (commission)
- До 3 уровней: 5%, 3%, 1%
- Хранится и отображается в USDT
- Вывод на основной USDT баланс

### ✅ Auto-Cancel Orders
- 10 минут — трейдер не взял заказ
- 30 минут — покупатель не оплатил после взятия (включая waiting_requisites)
- USDT автоматически возвращаются трейдеру

### ✅ Admin Features
- Полная статистика пользователей
- Сброс пароля пользователей
- Database reset (password protected)
- Approve merchants/traders

---

## API Endpoints

### Invoice API (for external sites)
- `GET /api/v1/invoice/payment-methods` — список способов оплаты
- `POST /api/v1/invoice/create` — создание инвойса
- `GET /api/v1/invoice/status` — проверка статуса
- `GET /api/v1/invoice/docs` — документация

### Shop API
- `GET /api/shop/pay/{order_id}` — страница оплаты (для покупателя)
- `POST /api/shop/pay/{order_id}/confirm` — покупатель подтвердил оплату
- `POST /api/shop/pay/{order_id}/cancel` — отмена заказа

### Trader API
- `GET /api/trader/available-orders` — доступные заявки
- `POST /api/trader/orders/{id}/confirm` — подтверждение оплаты
- `GET /api/trader/disputes` — споры трейдера

### Dispute API
- `POST /api/disputes/{id}/messages` — отправка сообщения
- `POST /api/disputes/{id}/confirm-payment` — закрытие спора (трейдер)

### Admin API
- `POST /api/admin/users/{id}/reset-password` — сброс пароля
- `POST /api/admin/database-reset` — сброс базы данных

---

## Key Files
- `/app/backend/server.py` — главный сервер, cleanup задачи
- `/app/backend/routers/invoice_api.py` — API для мерчантов
- `/app/backend/routers/shop.py` — страница оплаты
- `/app/backend/routers/trader.py` — рабочий стол трейдера
- `/app/backend/routers/disputes.py` — система споров
- `/app/backend/routers/admin.py` — админка
- `/app/frontend/src/pages/DemoShop.jsx` — демо-магазин
- `/app/frontend/src/pages/PaymentPage.jsx` — страница оплаты
- `/app/frontend/src/pages/DisputeChat.jsx` — чат спора
- `/app/frontend/src/pages/trader/Workspace.jsx` — рабочий стол трейдера

---

## Credentials
- **Admin**: admin / 000000
- **Trader**: 111 / 000000
- **DB Reset Password**: RESET_ALL_DATA_2024
- **Telegram Bot Token**: 7799633848:AAHUscaVl2ufnYeDsV3GA9cXrCKLapN9O7M

---

## Ready for Deployment ✅
All features tested and working:
- External site integration
- Payment flow (buyer → trader → completion)
- Dispute resolution
- Auto-cancel with USDT refund
- Notifications (in-app + Telegram)
- Admin panel

---

## DemoShop Features (Updated 27.01.2026)

### Transaction History & Balance
- **История транзакций**: полный список всех сделок мерчанта
- **Баланс магазина**: автоподсчёт из завершённых транзакций
- **Статистика**: Оплачено / В обработке / Всего
- **Автообновление**: каждые 10 секунд на странице истории

### Integration Testing Flow
1. Подключение к любому серверу BITARBITR через API URL
2. Ввод API Key и Secret Key
3. Выбор суммы и способа оплаты
4. Создание инвойса → открытие в новой вкладке
5. Отслеживание статуса в истории

---

## Pending/Upcoming Tasks

### ✅ P1: Webhook Notifications (COMPLETED 28.01.2026)
- Автоматическая отправка webhook при изменении статуса заказа
- Поддерживаемые события: `paid`, `cancelled`, `expired`, `dispute`
- Retry-политика: 1м → 5м → 15м → 1ч → 2ч → 4ч → 12ч → 24ч
- История webhook в коллекции `webhook_history`

### ✅ P2: Node.js SDK (COMPLETED 28.01.2026)
- Путь: `/app/sdk/nodejs/`
- Методы: `getPaymentMethods()`, `createInvoice()`, `getStatus()`, `getTransactions()`, `getStats()`, `verifyWebhook()`
- TypeScript definitions включены
- Документация в README.md

### ✅ BugFix: Payment Page Redirect (28.01.2026)
- **Проблема**: Неавторизованные пользователи могли редиректиться на главную страницу вместо страницы оплаты
- **Решение**: 
  - `PaymentPage.jsx` теперь использует отдельный axios instance без auth interceptors
  - `auth.js` interceptor теперь пропускает публичные страницы (`/pay/`, `/dispute/`, `/demo`)
  - Добавлена кнопка "Повторить" при ошибке загрузки заказа
  - Улучшена обработка ошибок (404, сетевые ошибки)

### ✅ BugFix: Payment URL Generation (28.01.2026)
- **Проблема**: `payment_url` генерировался с неправильным доменом (preview URL вместо production)
- **Решение**: 
  - `invoice_api.py` теперь определяет base_url из заголовка `Origin` запроса
  - Если `Origin` содержит production домен (bitarbitr.org) — использует его
  - Fallback на `SITE_URL` из env если Origin недоступен
  - Исключает preview URLs когда запрос приходит с production

### ✅ P3: Analytics & Python SDK (COMPLETED 28.01.2026)

#### Аналитика (`/api/v1/invoice/analytics`)
- **conversion_funnel**: total, paid, cancelled, expired, disputed + overall_conversion
- **markers**: распределение маркеров 5-20₽, конверсия по каждому значению
- **payment_methods**: конверсия и объём по каждому методу оплаты
- **amount_distribution**: распределение по суммам (0-500, 500-1000, 1000-2000, 2000-5000, 5000-10000, 10000+)
- **peak_hours**: пиковые часы для оплаты

#### Python SDK (`/app/sdk/python/`)
- Синхронный клиент: `BitarbitrSDK`
- Асинхронный клиент: `AsyncBitarbitrSDK`
- Методы: `get_payment_methods()`, `create_invoice()`, `get_status()`, `get_transactions()`, `get_stats()`, `get_analytics()`, `verify_webhook()`
- pip installable package (pyproject.toml)
- Полная документация в README.md


### ✅ Admin: Trader Locked Balance Check & Unfreeze (28.01.2026)
- **Проблема**: Баланс трейдера мог "застрять" в замороженном состоянии без активных заказов
- **Решение - UI в админ-панели**:
  - Кнопка 🔒 (Lock) для каждого трейдера в списке пользователей
  - Модальное окно "Проверка баланса трейдера" с информацией:
    - Доступный и замороженный баланс
    - Количество и сумма активных заказов
    - Статус соответствия (зелёный ✓ или красный ⚠)
    - Список активных заказов со статусами
  - Форма разморозки (если обнаружено несоответствие):
    - Поле суммы (автозаполнение разницей)
    - Поле причины (обязательно)
    - Кнопка "Разморозить"
- **API endpoints**:
  - `GET /api/admin/traders/{trader_id}/locked-check` — проверка баланса
  - `POST /api/admin/traders/{trader_id}/unfreeze?amount=X&reason=Y` — разморозка
- **Файлы**: 
  - `/app/frontend/src/pages/admin/Users.jsx` — UI
  - `/app/backend/routers/admin.py` — endpoints (lines 2481-2600)

### Future Tasks
- P4: Панель аналитики в UI мерчанта (визуализация данных)
- P5: Автоматические отчёты по email


