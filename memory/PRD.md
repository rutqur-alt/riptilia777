# P2P Crypto Exchange Platform - PRD

## Original Problem Statement
Создать P2P криптовалютную биржу с полной финансовой системой на базе TON блокчейна согласно ТЗ v3.0.

## Core Requirements (ТЗ v3.0)
1. **Архитектура:** Гибридная система (Python/FastAPI + Node.js TON service + MongoDB)
2. **Валюта:** USDT (Jettons на TON сети)
3. **Модель:** Кастодиальная (единый hot wallet)
4. **Роли:** Trader, Merchant I/II, Moderator I/II, Support, Admin

## Ролевая модель и лимиты (из ТЗ)
| Роль | Лимит вывода/сутки | Одобрение до |
|------|-------------------|--------------|
| Trader | 50 USDT | - |
| Merchant I | 200 USDT | - |
| Merchant II | 1000 USDT | - |
| Moderator I | - | 500 USDT |
| Moderator II | - | 2000 USDT |
| Admin | Без лимита | Всё |

## What's Been Implemented

### Sprint 1 - Financial Core ✅ (2026-03-03)
- [x] Node.js `ton-service` микросервис с rate limiting
- [x] API endpoints `/api/wallet/*`, `/api/admin/finance/*`
- [x] UI страницы: UserFinancePage, AdminFinancePage

### Sprint 2 - Full Financial Dashboard ✅ (2026-03-04)
- [x] Полная аналитика: Hot Wallet, Долг трейдерам/мерчантам, ДЕФИЦИТ индикатор
- [x] Управление кошельком: просмотр, смена, генерация нового
- [x] Поиск пользователей: по ID/логину/никнейму с детальной информацией
- [x] Корректировка баланса пользователей (Admin only)
- [x] Кнопка копирования ID в списке пользователей
- [x] Одобрение/отклонение заявок на вывод
- [x] График объёма торгов по дням
- [x] Топ-10 трейдеров и мерчантов

## Tech Stack
- **Backend:** FastAPI, Motor (MongoDB)
- **Frontend:** React, Redux, Tailwind CSS, Shadcn/UI
- **TON Integration:** Node.js, @ton/ton library
- **Database:** MongoDB (all data)

## Test Credentials
- Trader: `111` / `string` (balance: 100 USDT)
- Merchant: `222` / `string` (balance: 100-200 USDT)
- Admin: `admin` / `000000` (role: owner)
- Database: `test_database`

## Key API Endpoints
### User Wallet
- `GET /api/wallet/balance` — баланс пользователя
- `GET /api/wallet/deposit-address` — адрес депозита + memo
- `POST /api/wallet/withdraw` — запрос на вывод

### Admin Finance
- `GET /api/admin/analytics/full` — полная аналитика
- `GET /api/admin/wallet/current` — текущий кошелёк
- `POST /api/admin/wallet/change` — смена кошелька
- `POST /api/admin/wallet/generate` — генерация нового
- `GET /api/admin/users/search` — поиск пользователей
- `GET /api/admin/users/{id}/details` — детали пользователя
- `POST /api/admin/users/adjust-balance` — корректировка баланса
- `GET /api/admin/finance/pending-withdrawals` — заявки на вывод
- `POST /api/admin/finance/approve-withdrawal/{id}` — одобрить
- `POST /api/admin/finance/reject-withdrawal/{id}` — отклонить

## Key Files
- `/app/ton-service/index.js` — TON blockchain service
- `/app/backend/routes/wallet_api.py` — Finance API (расширенный)
- `/app/backend/routes/ton_finance.py` — TON service integration
- `/app/frontend/src/pages/finance/AdminFinancePage.jsx` — Admin dashboard (полный)
- `/app/frontend/src/pages/finance/UserFinancePage.jsx` — User wallet
- `/app/frontend/src/components/admin/UsersManagement.jsx` — Пользователи с копированием ID

## Known Limitations
- Hot wallet balance = 0 (testnet, needs funding)
- E2E депозит/вывод не протестирован с реальными транзакциями

## Backlog (ТЗ v3.0)
- [ ] Лимиты выводов по ролям
- [ ] 2FA для критических операций  
- [ ] Глобальный СТОП выводов
- [ ] Блокировки по пользователям/ролям
- [ ] Экспорт CSV/Excel
- [ ] Audit logs расширенные
- [ ] Уведомления Telegram

---
Last updated: 2026-03-04
