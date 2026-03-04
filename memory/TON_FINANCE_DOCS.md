# TON Finance System - Sprint 1 Documentation

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      Reptiloid Exchange                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    HTTP/JSON    ┌──────────────────────────┐  │
│  │   Python     │◄───────────────►│   Node.js TON Service    │  │
│  │   FastAPI    │                 │   (Port 8002)            │  │
│  │  (Port 8001) │                 │                          │  │
│  │              │                 │  • Wallet Management     │  │
│  │  • Business  │                 │  • Transaction Signing   │  │
│  │    Logic     │                 │  • Deposit Listener      │  │
│  │  • Auth      │                 │  • Blockchain Queries    │  │
│  │  • API       │                 │                          │  │
│  └──────┬───────┘                 └────────────┬─────────────┘  │
│         │                                      │                 │
│         │                                      │                 │
│  ┌──────▼───────┐                 ┌────────────▼─────────────┐  │
│  │   MongoDB    │                 │       PostgreSQL         │  │
│  │              │                 │   (Finance Database)     │  │
│  │  • Users     │    user_id      │                          │  │
│  │  • Trades    │◄───────────────►│  • users_finance         │  │
│  │  • Offers    │                 │  • transactions          │  │
│  │  • Messages  │                 │  • wallet_config         │  │
│  │              │                 │  • audit_logs            │  │
│  └──────────────┘                 │  • withdrawal_queue      │  │
│                                   └──────────────────────────┘  │
│                                                                  │
│                          ┌──────────────────────────┐           │
│                          │     TON Blockchain       │           │
│                          │      (Testnet)           │           │
│                          │                          │           │
│                          │  Hot Wallet:             │           │
│                          │  kQBC_gx2hCv1RksJLWS...  │           │
│                          └──────────────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Node.js TON Service (`/app/ton-service/`)

**Purpose**: Isolated microservice for all TON blockchain interactions.

**Endpoints**:
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service health check |
| `/generate-wallet` | POST | Generate new wallet (setup only) |
| `/deposit-address/:userId` | GET | Get deposit address + memo |
| `/balance/:address` | GET | Get address balance |
| `/hot-wallet/balance` | GET | Get hot wallet balance |
| `/transactions/:address` | GET | Get blockchain transactions |
| `/send-ton` | POST | Send TON withdrawal |
| `/user-balance/:userId` | GET | Get user balance from PostgreSQL |
| `/user-transactions/:userId` | GET | Get user transaction history |
| `/create-user-finance` | POST | Create finance record for user |

**Security**:
- All endpoints require `X-Api-Key` header
- Private keys stored only in `.env`
- Separate logging (`ton-service.log`)

### 2. PostgreSQL Finance Database

**Tables**:

```sql
-- User financial data
users_finance (
  user_id VARCHAR(64) PRIMARY KEY,  -- Links to MongoDB
  balance_ton DECIMAL(20, 9),
  balance_usd DECIMAL(20, 2),
  frozen_ton DECIMAL(20, 9),
  frozen_usd DECIMAL(20, 2),
  ...
)

-- All transactions
transactions (
  tx_id VARCHAR(64) PRIMARY KEY,
  user_id VARCHAR(64),
  type VARCHAR(32),  -- deposit, withdraw, internal_transfer
  amount DECIMAL(20, 9),
  tx_hash VARCHAR(128),  -- Blockchain hash
  status VARCHAR(32),  -- pending, success, failed, review
  ...
)

-- Hot wallet configuration
wallet_config (
  address VARCHAR(128) PRIMARY KEY,
  wallet_type VARCHAR(32),  -- hot, cold
  current_seqno INTEGER,
  network VARCHAR(16),  -- testnet, mainnet
  ...
)

-- Admin actions audit
audit_logs (
  admin_user_id VARCHAR(64),
  action VARCHAR(64),
  target_user_id VARCHAR(64),
  details TEXT,
  ...
)

-- Withdrawal queue
withdrawal_queue (
  tx_id VARCHAR(64) PRIMARY KEY,
  requires_approval BOOLEAN,
  approved_by VARCHAR(64),
  status VARCHAR(32),
  ...
)
```

### 3. Python API Routes (`/api/wallet/*`)

**User Endpoints**:
- `GET /api/wallet/health` - Service health
- `GET /api/wallet/deposit-address` - Get deposit instructions
- `GET /api/wallet/balance` - Get TON balance
- `GET /api/wallet/transactions` - Transaction history
- `POST /api/wallet/withdraw` - Request withdrawal

**Admin Endpoints**:
- `GET /api/admin/finance/analytics` - Financial dashboard
- `GET /api/admin/finance/hot-wallet` - Hot wallet balance
- `GET /api/admin/finance/audit-logs` - Audit trail
- `GET /api/admin/finance/pending-withdrawals` - Pending approvals
- `POST /api/admin/finance/approve-withdrawal/:id` - Approve
- `POST /api/admin/finance/reject-withdrawal/:id` - Reject

## Deposit Flow

```
1. User calls GET /api/wallet/deposit-address
   → Returns: { address: "kQBC...", comment: "user_id_uuid" }

2. User sends TON to address with comment (memo)

3. TON Service Listener (every 5 sec):
   → Polls blockchain for new transactions
   → Parses incoming transactions
   → Matches comment to user_id in PostgreSQL
   → Credits balance atomically (DB transaction)
   → Creates transaction record

4. User sees updated balance in /api/wallet/balance
```

## Withdrawal Flow

```
1. User calls POST /api/wallet/withdraw
   { amount: 10, to_address: "EQ...", two_fa_code: "123456" }

2. Backend validates:
   - Balance sufficient
   - Daily limit not exceeded
   - 2FA code (if enabled)

3. If amount < 50 TON:
   → Auto-process via TON Service
   → Deduct balance, send transaction

4. If amount >= 50 TON:
   → Add to withdrawal_queue
   → Require admin/mod approval

5. Admin approves:
   → TON Service sends transaction
   → Update status to 'success'
```

## Configuration

### Environment Variables

**TON Service** (`/app/ton-service/.env`):
```
TON_NETWORK=testnet
TON_ENDPOINT=https://testnet.toncenter.com/api/v2/jsonRPC
HOT_WALLET_MNEMONIC=rent notice route...
POSTGRES_HOST=localhost
POSTGRES_DB=reptiloid_finance
```

**Python Backend** (`/app/backend/.env`):
```
POSTGRES_HOST=localhost
POSTGRES_DB=reptiloid_finance
TON_SERVICE_URL=http://localhost:8002
TON_SERVICE_API_KEY=ton_service_api_secret_key_2026
```

## Testing Checklist (Sprint 1)

- [x] PostgreSQL schema created
- [x] TON Service running on port 8002
- [x] Hot wallet generated (testnet)
- [x] Deposit listener running
- [x] Python API connected to TON Service
- [x] User can get deposit address
- [x] User balance stored in PostgreSQL
- [ ] **Test deposit with real testnet TON**
- [ ] **Test withdrawal to external address**

## Hot Wallet Address (Testnet)

```
kQBC_gx2hCv1RksJLWSBGDbYpS637SVLvXkLJoT5wrl33d4N
```

To get testnet TON:
1. Open Telegram: @testgiver_ton_bot
2. Send the wallet address
3. Receive 2 TON for testing

## Next Steps (Sprint 2)

1. Implement 2FA for withdrawals
2. Redis queue for withdrawal processing
3. User transaction history UI
4. Admin approval UI for large withdrawals
5. Cold storage sweep mechanism
