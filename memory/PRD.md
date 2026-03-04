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
- [x] Поиск пользователей с копированием ID
- [x] Корректировка баланса пользователей

### Sprint 3 - Withdrawal Flow ✅ (2026-03-04)
- [x] Заморозка баланса при запросе на вывод
- [x] Проверка hot wallet при одобрении (ошибка если недостаточно)
- [x] Возврат средств при отклонении (frozen → balance)
- [x] История транзакций у пользователя (вывод, возврат)
- [x] Удалён раздел "Финансы" из меню админа
- [x] Оптимизирована загрузка USDT Кошелёк

## Withdrawal Flow (Correct Implementation)

### 1. User Request Withdrawal
```
POST /api/wallet/withdraw
→ balance_usdt: 100 → 50
→ frozen_usdt: 0 → 50
→ Create withdrawal_request (status: pending)
→ Create transaction record
```

### 2. Admin Approve
```
POST /api/admin/finance/approve-withdrawal/{id}
→ CHECK hot_wallet_balance >= amount
→ If insufficient: ERROR "Недостаточно средств в кошельке биржи!"
→ frozen_usdt: 50 → 0
→ Status: completed
```

### 3. Admin Reject
```
POST /api/admin/finance/reject-withdrawal/{id}
→ frozen_usdt: 50 → 0
→ balance_usdt: 50 → 100 (refund)
→ Create refund transaction
→ Status: rejected
```

## Tech Stack
- **Backend:** FastAPI, Motor (MongoDB)
- **Frontend:** React, Redux, Tailwind CSS, Shadcn/UI
- **TON Integration:** Node.js, @ton/ton library
- **Database:** MongoDB

## Test Credentials
- Trader: `111` / `string`
- Merchant: `222` / `string`
- Admin: `admin` / `000000`

## Key Collections (MongoDB)
- `traders` - balance_usdt, frozen_usdt
- `merchants` - balance_usdt, frozen_usdt
- `withdrawal_requests` - pending/completed/rejected
- `transactions` - history of all operations
- `audit_logs` - admin actions

## Backlog (ТЗ v3.0)
- [ ] Лимиты выводов по ролям (50/200/1000 USDT)
- [ ] 2FA для критических операций  
- [ ] Глобальный СТОП выводов
- [ ] Блокировки по пользователям/ролям
- [ ] Экспорт CSV/Excel
- [ ] Уведомления Telegram
- [ ] E2E тест депозита на testnet

---
Last updated: 2026-03-04
