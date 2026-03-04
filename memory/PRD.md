# P2P Crypto Exchange Platform (Reptiloid)

## Original Problem Statement
Build a production-ready P2P crypto exchange platform based on TON blockchain with:
- Role-based system (Trader, Merchant, Moderator, Support, Admin)
- Admin Financial Hub with analytics and withdrawal approval
- User wallet with deposit/withdrawal functionality
- Secure withdrawal flow with balance freezing and admin approval
- TON mainnet integration

## Current Architecture
- **Frontend**: React + Tailwind CSS + Shadcn UI
- **Backend**: FastAPI (Python)
- **Database**: MongoDB (temporary - should migrate to PostgreSQL for ACID compliance)
- **Blockchain**: TON via Node.js microservice (`ton-service`)
- **Network**: **MAINNET** (switched from testnet)

## What's Been Implemented

### Completed (2026-03-04)
1. **Admin Finance Dashboard** (`/admin/ton-finance`)
   - Hot wallet balance display
   - User liabilities (traders + merchants balances)
   - Platform profit/deficit indicator
   - Period-based analytics (1d, 7d, 30d, 90d)
   - Daily volume chart
   - Withdrawal approval queue
   - User search and balance adjustment
   - Wallet management (change/generate)

2. **User Wallet Page** (`UserFinancePage.jsx`)
   - Available and frozen balance display
   - Deposit address with memo
   - Transaction history with filters
   - Withdrawal request form

3. **Withdrawal Workflow**
   - User requests withdrawal → balance frozen
   - Admin approves → hot wallet sends funds
   - Admin rejects → frozen balance refunded
   - Hot wallet balance check before approval

4. **TON Service (Node.js)**
   - Wallet generation
   - Balance checking
   - Transaction sending
   - Deposit listener

5. **Performance Optimization**
   - Parallelized MongoDB queries using `asyncio.gather`
   - Analytics endpoint response time: ~0.7-2s (was 10+ seconds)

6. **Balance Synchronization Fix (2026-03-04)**
   - Fixed sidebar balance to show AVAILABLE balance (total - frozen), not total
   - Added frozen balance indicator in all UI components
   - Updated traders and merchants registration to include `frozen_usdt` field
   - Migrated existing users to have `frozen_usdt: 0` field
   - Fixed withdrawal validation to check available balance, not total

### Mainnet Migration (2026-03-04)
- TON service switched to mainnet
- New mainnet wallet generated: `EQCxIoq1inAuvVt3U77cPyopvQXeSQjTfyJzhAVtdfCbqapC`
- Frontend updated to show mainnet explorer links

## P0/P1/P2 Priority Tasks

### P0 - Critical (Must be done for production)
1. ~~Optimize slow admin dashboard~~ ✅ DONE
2. ~~Switch to TON mainnet~~ ✅ DONE
3. **User needs to fund the mainnet hot wallet with USDT/TON**

### P1 - Important
1. **E2E Test on Mainnet** - Test deposit/withdrawal with real funds
2. **Migrate financial data to PostgreSQL** - MongoDB lacks ACID compliance

### P2 - Should Do
1. Financial notifications (Telegram/Email)
2. 2FA for critical operations
3. API rate limiting for TON service
4. Consolidate dispute resolution endpoints

## Known Technical Debt
1. **Financial data in MongoDB** - Should be in PostgreSQL for ACID compliance
2. **No 2FA** - Critical operations lack second factor
3. **Multiple dispute endpoints** - Need consolidation

## Test Credentials
- **Admin**: `admin` / `000000`
- **Trader**: `111` / `string`
- **Merchant**: `222` / `string`

## Key Files
- `/app/backend/routes/wallet_api.py` - All financial APIs
- `/app/backend/routes/ton_finance.py` - TON integration layer
- `/app/frontend/src/pages/finance/AdminFinancePage.jsx` - Admin dashboard
- `/app/frontend/src/pages/finance/UserFinancePage.jsx` - User wallet
- `/app/ton-service/index.js` - TON blockchain microservice
- `/app/ton-service/.env` - TON service config (MAINNET)

## Mainnet Wallet Info
- **Address**: `EQCxIoq1inAuvVt3U77cPyopvQXeSQjTfyJzhAVtdfCbqapC`
- **Network**: TON Mainnet
- **Explorer**: https://tonviewer.com/EQCxIoq1inAuvVt3U77cPyopvQXeSQjTfyJzhAVtdfCbqapC
- **Mnemonic**: Stored in `/app/ton-service/.env` (BACKUP REQUIRED!)
