# P2P Crypto Exchange Platform - PRD

## Original Problem Statement
Создать P2P криптовалютную биржу с новой финансовой системой на базе TON блокчейна.

## Core Requirements
1. **Архитектура:** Гибридная система (Python/FastAPI + Node.js TON service + PostgreSQL/MongoDB)
2. **Валюта:** USDT (Jettons на TON сети)
3. **Модель:** Кастодиальная (единый hot wallet)
4. **Роли:** Trader, Merchant, Support, Moderator, Admin

## User Personas
- **Трейдер (111):** Покупает/продает USDT, управляет объявлениями
- **Мерчант (222):** Бизнес-пользователь с расширенным API
- **Админ (admin):** Полный доступ к управлению платформой

## What's Been Implemented

### Sprint 1 - Financial Core Scaffolding ✅
- [x] Node.js `ton-service` микросервис для TON блокчейна
- [x] PostgreSQL схема для финансовых данных
- [x] Новые API endpoints `/api/wallet/*`
- [x] UI: `TonWalletPage.jsx`, `TonFinanceAdmin.jsx`
- [x] Интеграция в роутинг и навигацию

### UI Cleanup ✅ (2026-03-04)
- [x] Удалены старые пункты меню финансов
- [x] Удален блок "Основной баланс" из TraderDashboard
- [x] Исправлена синтаксическая ошибка в TraderBalance.jsx

## Current Blockers
- **TON Service FATAL:** Rate limiting (429) от testnet.toncenter.com

## Tech Stack
- **Backend:** FastAPI, Motor (MongoDB), asyncpg (PostgreSQL)
- **Frontend:** React, Redux, Tailwind CSS
- **TON Integration:** Node.js, @ton/ton library
- **Databases:** MongoDB (app data), PostgreSQL (finance data)

## Test Credentials
- Trader: `111` / `string`
- Merchant: `222` / `string`
- Admin: `admin` / `000000`
- Database: `test_database`

## Key Files
- `/app/ton-service/index.js` - TON blockchain service
- `/app/backend/src/routes/wallet_api.py` - Finance API
- `/app/frontend/src/pages/shared/TonWalletPage.jsx` - User wallet UI
- `/app/frontend/src/pages/Admin/TonFinanceAdmin.jsx` - Admin finance UI

---
Last updated: 2026-03-04
