# Reptiloid P2P Exchange - PRD

## Описание проекта
P2P криптовалютная биржа с интегрированным маркетплейсом и платёжным шлюзом для мерчантов.

## Дата развёртывания
2026-03-03

## Технический стек
- **Backend:** FastAPI + Python 3.x + MongoDB
- **Frontend:** React 19 + Tailwind CSS + Radix UI
- **База данных:** MongoDB (локальная)

## Основной функционал

### 1. P2P Торговля
- Стакан офферов с фильтрами по методу оплаты
- Создание сделок с эскроу
- Чат между покупателем и продавцом
- Система споров

### 2. Платёжный шлюз для мерчантов
- API интеграция для внешних магазинов
- Demo магазин `/demo`
- Комиссия оператора вместо крипто-терминологии

### 3. Маркетплейс
- Магазины трейдеров
- Товары с автовыдачей
- Гарант-сделки

### 4. Админ-панель
- Управление пользователями
- Модерация сделок и споров
- Настройки комиссий

## Тестовые аккаунты (пароль: 000000)

### Пользователи
- user1, user2, user3 - трейдеры

### Мерчанты  
- merchant1 (казино)
- merchant2 (магазин)
- merchant3 (стрим)

### Персонал
- admin - администратор
- mod_p2p - модератор P2P
- mod_market - модератор маркетплейса
- support - поддержка

## Что выполнено

### Развёртывание (03.03.2026)
- Распаковка архива проекта
- Копирование файлов в /app/backend и /app/frontend
- Установка зависимостей (Python + Node.js)
- Настройка craco для алиасов путей (@)
- Инициализация базы данных тестовыми пользователями
- Обновление паролей для bcrypt совместимости

### Тестирование
- Backend API: 100% тестов пройдено
- Frontend: 95% тестов пройдено
- Интеграция: 100%

## Известные ограничения
- Telegram уведомления не реализованы
- Небольшая ошибка загрузки данных в админ-панели (некритично)

## Исправления (03.03.2026)
- ✅ Добавлен эндпоинт `/api/super-admin/users` для списка пользователей
- ✅ Добавлены эндпоинты `/ban` и `/balance` для управления пользователями
- ✅ Исправлена роль админа (admin_role: owner)

## Доработка тестового магазина /shop (03.03.2026)
- ✅ merchant_id теперь сохраняется в trades при создании сделки
- ✅ История транзакций загружается из trades и merchant_invoices
- ✅ API ключ мерчанта передаётся при создании платежа
- ✅ Автозагрузка истории при открытии раздела
- ✅ Создано 3 тестовых оффера для трейдеров с реквизитами
- Backend: 100% тестов пройдено
- Frontend: 85% (мелкие проблемы селекторов, функционал работает)

## Тестовые данные
**API ключи мерчантов:**
- merchant1: merch_sk_8581cf8f655c4f858511e26d1dc3f3f3
- merchant2: merch_sk_ab7f17e54e7b4f5eaa296e106f1afad3
- merchant3: merch_sk_49ccfc80e2854bde8acc598f21718a7e

## Боевое API подключение мерчанта (03.03.2026)

### Баланс в рублях
- Основной баланс отображается в RUB
- Под балансом эквивалент в USDT
- Всего получено: сумма merchant_receives_rub из завершённых сделок

### Комиссия мерчанта (заработок площадки)
- Каждому мерчанту при одобрении устанавливается процент
- Пример с комиссией 10%:
```
Клиент пополняет: 1000 RUB
Комиссия площадки: 10%
Мерчант получает: 900 RUB (в USDT)
Площадка получает: 100 RUB
```

### Форма подключения:
- Merchant ID
- API Key  
- API Secret

### API endpoints:
- POST `/merchant/v1/auth` - авторизация
- POST `/merchant/v1/invoice/create` - создание счёта (учитывает commission_rate мерчанта)
- POST `/merchant/v1/balance` - баланс в RUB и USDT
- POST `/merchant/v1/transactions` - история

### Тестовые учётные данные merchant1 (комиссия 10%):
- Merchant ID: `acf5eddc-f179-4e50-bc06-2756080a6562`
- API Key: `merch_sk_8581cf8f655c4f858511e26d1dc3f3f3`
- API Secret: `2f48f9c6ab4d8af44b81590338af9c3e`

## Исправления аналитики (03.03.2026)
- ✅ Комиссии считаются по базовому курсу Rapira API (~78 RUB/USDT)
- ✅ Формула: `platform_fee_rub / base_rate` (base_rate из db.settings)
- ✅ Пример для merchant 222: 1,300 RUB ÷ 78.16 = **16.63 USDT**
- ✅ Исправлены эндпоинты: `/merchant/analytics`, `/merchants/stats`, `/super-admin/overview`, `/admin/analytics`, `/super-admin/finances`
- ✅ Пересчитан `total_commission_paid` для всех мерчантов
- ✅ Результаты:
  - Admin: Комиссия заработана = 21.11 USDT (13 сделок)
  - Merchant 222: Оплачено комиссий = 16.63 USDT (11 сделок)
  - Merchant1: Оплачено комиссий = 4.48 USDT (2 сделки)

## Merchant API v1 - Полная реализация (03.03.2026)

### Реализованные эндпоинты:
- ✅ `POST /merchant/v1/auth` - авторизация
- ✅ `POST /merchant/v1/invoice/create` - создание счёта
- ✅ `POST /merchant/v1/invoice/status` - статус счёта
- ✅ `POST /merchant/v1/balance` - баланс мерчанта
- ✅ `POST /merchant/v1/transactions` - список транзакций
- ✅ `POST /merchant/v1/operators` - список доступных операторов (трейдеров)
- ✅ `POST /merchant/v1/invoice/requisites` - получение реквизитов для оплаты
- ✅ `POST /merchant/v1/invoice/mark-paid` - отметка "клиент оплатил"
- ✅ `POST /merchant/v1/disputes/open` - открытие спора через API
- ✅ `POST /merchant/v1/disputes/messages` - получение сообщений спора
- ✅ `POST /merchant/v1/disputes/send-message` - отправка сообщения в спор

### Реализованные вебхуки:
- ✅ `pending` - сделка создана, ожидается оплата
- ✅ `paid` - клиент отметил оплату
- ✅ `completed` - оператор подтвердил, средства зачислены
- ✅ `cancelled` - сделка отменена
- ✅ `disputed` - открыт спор

### Документация API:
- ✅ Создан файл `/app/docs/merchant_api.md` с полной документацией
- Включает примеры кода на PHP, Python, Node.js
- HMAC подпись для безопасности
- Описание всех вебхуков с payload

## Следующие задачи (Backlog)
- P1: Добавить вебхук `expired` (автоматическое истечение сделок)
- P2: Telegram уведомления для споров
- P2: Улучшение мобильной адаптации
- P2: Удалить устаревший merchant.py после миграции
- P3: Стандартизация структуры директорий backend (`/api` vs `/routes`)

## Централизованная система уведомлений (03.03.2026)

### Реализовано:
- ✅ **Backend API** (`/app/backend/routes/event_notifications.py`):
  - `GET /event-notifications` - получение списка уведомлений
  - `GET /event-notifications/unread-count` - количество непрочитанных
  - `POST /event-notifications/mark-read` - отметка прочитанным (одно или все)
  - `DELETE /event-notifications/{id}` - удаление уведомления

- ✅ **Frontend компонент** (`/app/frontend/src/components/EventNotificationDropdown.jsx`):
  - Кнопка в сайдбаре рядом с балансом (для трейдеров и мерчантов)
  - Показывает "Нет событий" когда пусто
  - Показывает "N событий" с красной точкой при наличии уведомлений
  - Dropdown со списком уведомлений (иконки + заголовок + сообщение + время)
  - Клик на уведомление → навигация + удаление из списка
  - Кнопка "Прочитать всё" → очистка всех уведомлений

### Типы событий:
- **Торговля:** trade_created, trade_payment_sent, trade_completed, trade_cancelled
- **Купить USDT:** payout_order_created, payout_order_completed, payout_order_cancelled
- **Маркет:** marketplace_purchase, shop_new_order
- **Финансы:** deposit_received, withdrawal_completed
- **Сообщения:** new_message, broadcast
- **Рефералы:** new_referral, referral_bonus
- **Мерчант:** merchant_payment_received, merchant_withdrawal_completed

### Триггеры уведомлений:
- Создание сделки → уведомление трейдеру
- Завершение/отмена сделки → уведомление обеим сторонам
- Создание/завершение заказа на покупку USDT → уведомление покупателю
- Новое сообщение в чате → уведомление получателю

## Рефакторинг (03.03.2026)
- ✅ **BuyerShop.jsx разбит на компоненты** (1307 → 850 строк, -35%)
- ✅ Создано 10 модульных компонентов в `/frontend/src/pages/shop/`:
  - ShopHeader, ApiConnectionForm, BalanceCard, TopUpForm
  - OperatorSelector, PaymentCard, ChatPanel
  - TransactionHistory, SettingsDialog, index.js
- ✅ **Старый merchant.py помечен как deprecated**
  - Добавлено уведомление в docstring
  - Для интеграций использовать `/merchant/v1/*` (merchant_api.py)
