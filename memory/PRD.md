# Reptiloid P2P Exchange - Product Requirements Document

## Original Problem Statement
Build a P2P cryptocurrency exchange platform named "Reptiloid" with a focus on creating a robust, secure, and well-documented redirect-based Merchant API for accepting payments.

## Core Features Implemented
- **Redirect-based Merchant API** for accepting RUB payments via P2P USDT
- **Demo Store** that simulates real merchant integration
- **Live Webhooks** with full E2E notification flow
- **Admin Panel** for configuring business rules
- **Trader Dashboard** for managing offers and trades
- **Merchant Dashboard** for viewing transactions and API keys

## Key Technical Components
- **Frontend**: React, Redux, Axios, Tailwind CSS
- **Backend**: FastAPI, Pydantic, Motor (async MongoDB)
- **Database**: MongoDB

## API Documentation (Updated March 4, 2026)
The merchant-facing API documentation has been completely rewritten to be 100% accurate and match the current working implementation.

### Main Endpoints:
- `POST /api/v1/invoice/create` - Create payment (get payment_url)
- `GET /api/v1/invoice/status` - Check payment status
- `GET /api/v1/invoice/transactions` - Transaction list
- `GET /api/v1/invoice/stats` - Payment statistics

### Webhook Statuses:
- `pending` - Customer selected operator, waiting for payment
- `paid` - Customer paid, waiting for operator confirmation
- `completed` - Payment successful
- `cancelled` - Cancelled (timeout 30 min after operator selection)
- `expired` - Expired (customer didn't select operator within 30 min)
- `disputed` - Dispute opened, waiting for arbitration

## Completed Work
- [x] Correct fund distribution logic (commission based on original_amount_rub)
- [x] Dispute resolution logic fixes across all endpoints
- [x] Unified merchant transaction view (original_amount_rub, trd_... IDs)
- [x] Configurable payout rules (min successful trades for traders)
- [x] Live webhooks for demo store
- [x] State synchronization between trades and invoices
- [x] **API Documentation rewrite (March 4, 2026)**
- [x] **Trader dashboard: base rate display (March 4, 2026)** - Shows USDT/RUB rate
- [x] **Notification links fixed (March 4, 2026)** - All notification links now lead to specific trade pages

## Known Technical Debt
- **Duplicate API Endpoints**: At least 4 endpoints for resolving disputes exist and need consolidation
- **Backend Directory Structure**: Routes scattered between /src/api and /src/routes

## Future Tasks (Backlog)
1. **(P1) Refactor Dispute Resolution**: Consolidate 4+ dispute endpoints into single authoritative endpoint
2. **(P1) Cleanup invoice_api.py**: Remove unused white-label API endpoints
3. **(P2) Deprecate Old Merchant API**: Remove legacy API from merchant_api.py
4. **(P3) Standardize Backend Routes**: Consolidate all routes into /src/routes
5. **(P3) Migrate Legacy Notifications**: Move data from notifications to event_notifications collection

## Test Credentials
- **Super Admin**: admin / 000000
- **Trader "111"**: 111 / string
- **Merchant "222"**: 222 / string (commission 10%)

## Key Files
- `/frontend/src/pages/MerchantAPI.js` - Merchant API documentation page (UPDATED)
- `/backend/routes/invoice_api.py` - Invoice API implementation
- `/backend/routes/trades.py` - Core trade logic
- `/frontend/src/pages/demo/DemoShop.jsx` - Demo store reference implementation
