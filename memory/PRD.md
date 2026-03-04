# P2P Crypto Exchange Platform - PRD

## Original Problem Statement
Создать P2P криптовалютную биржу с новой финансовой системой на базе TON блокчейна согласно ТЗ v3.0.

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
- [x] PostgreSQL схема (не используется, fallback на MongoDB)
- [x] API endpoints `/api/wallet/*`, `/api/admin/finance/*`
- [x] UI страницы: UserFinancePage, AdminFinancePage, FinancesOverview

### Bug Fixes ✅ (2026-03-04)
- [x] TON сервис — добавлен exponential backoff для rate limiting
- [x] Финансовые API переведены с PostgreSQL на MongoDB
- [x] Исправлен формат данных analytics (liabilities.total_ton)
- [x] Балансы пользователей отображаются корректно

## Tech Stack
- **Backend:** FastAPI, Motor (MongoDB)
- **Frontend:** React, Redux, Tailwind CSS, Shadcn/UI
- **TON Integration:** Node.js, @ton/ton library
- **Database:** MongoDB (all data)

## Test Credentials
- Trader: `111` / `string` (balance: 100 USDT)
- Merchant: `222` / `string` (balance: 100 USDT)
- Admin: `admin` / `000000` (role: owner)
- Database: `test_database`

## Key API Endpoints
- `GET /api/wallet/balance` — баланс пользователя
- `GET /api/wallet/deposit-address` — адрес депозита + memo
- `POST /api/wallet/withdraw` — запрос на вывод
- `GET /api/admin/finance/analytics` — аналитика для админа
- `GET /api/admin/finance/pending-withdrawals` — заявки на вывод
- `POST /api/admin/finance/approve-withdrawal/{id}` — одобрить вывод
- `GET /api/super-admin/finances` — обзор доходов платформы

## Key Files
- `/app/ton-service/index.js` — TON blockchain service
- `/app/backend/routes/wallet_api.py` — Finance API
- `/app/backend/routes/ton_finance.py` — TON service integration
- `/app/frontend/src/pages/finance/UserFinancePage.jsx` — User wallet
- `/app/frontend/src/pages/finance/AdminFinancePage.jsx` — Admin dashboard

## Known Limitations
- Hot wallet balance = 0 (testnet, needs funding)
- PostgreSQL не запущен (все данные в MongoDB)
- E2E депозит/вывод не протестирован с реальными транзакциями

## Backlog (ТЗ v3.0)
- [ ] Лимиты выводов по ролям
- [ ] 2FA для критических операций  
- [ ] Смена hot wallet
- [ ] Глобальный СТОП выводов
- [ ] Блокировки по пользователям
- [ ] Вывод прибыли платформы
- [ ] Аналитика с графиками (Chart.js)
- [ ] Экспорт CSV/Excel
- [ ] Audit logs расширенные

---
Last updated: 2026-03-04
