# Test Results

## Current Test Status
Testing all chat types in admin panel - decision buttons and archive functionality

## Test Cases to Execute

### 1. Merchant Application
- [x] Open merchant application chat (CasinoX)
- [x] Click "Одобрить" button  
- [x] Verify commission modal appears
- [x] Confirm approval
- [x] Verify chat goes to archive (disappears from list)
- [x] Login as merchant (casino_new) - verify dashboard works
**STATUS: PASSED**

### 2. P2P Dispute
- [x] Open P2P dispute chat
- [x] Click "Вернуть покупателю" button
- [x] Verify "Решение принято" toast
- [x] Verify chat goes to archive
**STATUS: PASSED**

### 3. Crypto Payout
- [ ] Open payout chat
- [ ] Find "Завершить сделку" button
- [ ] Complete payout
- [ ] Verify chat goes to archive
**STATUS: IN PROGRESS - buttons not visible**

### 4. Shop Application
- [ ] Open shop application
- [ ] Test approve/reject
- [ ] Verify archive behavior

### 5. Guarantor Deal
- [ ] Open guarantor deal chat
- [ ] Test complete delivery
- [ ] Verify archive behavior

### 6. Support Ticket
- [ ] Open support ticket
- [ ] Test resolution
- [ ] Verify archive behavior

## Known Issues
1. Crypto payout buttons may not be visible - need investigation
2. WebSocket connection errors (not critical)

## Credentials
- Admin: admin/000000
- Merchant: casino_new/000000, merchant1/000000
- Users: user1/000000, user2/000000, user3/000000
