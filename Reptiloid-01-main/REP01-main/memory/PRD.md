# Crypto Trading Platform PRD

## Обновление от 2025-01-24 (Миграция ПОЛНОСТЬЮ завершена)

### ✅ ЗАВЕРШЕНО: Backend рефакторинг server.py

#### Итоговый результат
| Метрика | Было | Стало | Изменение |
|---------|------|-------|-----------|
| server.py | 11200+ строк | **546 строк** | **-95.1%** |
| routes/trades.py | 664 строк | **1079 строк** | +415 строк (миграция) |

#### Финальная структура server.py (546 строк):
- **Импорты и конфигурация** (строки 1-97)
- **Maintenance middleware** (строки 168-205)  
- **Auth helpers** (строки 222-331) - hash_password, verify_password, create_token, get_current_user
- **Background tasks** (строки 335-513) - startup, auto_cancel_expired_trades, cleanup_old_purchase_files
- **Health check** (строки 515-546)

✅ **Вся бизнес-логика перенесена в модульные файлы!**

---

## Общий прогресс рефакторинга

| Компонент | Исходно | Финал | Изменение |
|-----------|---------|-------|-----------|
| server.py | 11200+ | **546** | **-95.1%** |
| AdminPanel.js | 5099 | **304** | **-94.0%** |
| **ИТОГО** | **16299+** | **850** | **-94.8%** |

### Backend модули (/app/backend/routes/) - 32 файла
| Файл | Строк | Описание |
|------|-------|----------|
| routes/shop.py | ~1428 | Shop management |
| routes/trades.py | **~1079** | P2P сделки + disputes ★ |
| routes/crypto_payouts.py | ~1007 | Crypto payouts |
| routes/marketplace.py | ~865 | Marketplace API |
| routes/admin_chats.py | ~803 | Admin/Staff/User chats |
| routes/staff_admin.py | ~787 | Staff admin, disputes |
| routes/trade_chats.py | ~625 | Trade chats |
| routes/support.py | ~528 | Support tickets |
| routes/admin_users.py | ~507 | Admin user mgmt |
| routes/chat_management.py | ~507 | Chat leave/archive/search |
| routes/admin_management.py | ~501 | Traders/Staff/Trades |
| routes/unified_messaging.py | ~429 | Unified messaging |
| routes/admin.py | ~421 | Admin API |
| routes/super_admin.py | ~379 | Super-admin API |
| routes/guarantor.py | ~250 | Guarantor deals |
| routes/merchant_messages.py | ~240 | Merchant API |
| routes/admin_dashboard.py | ~232 | Analytics, dashboard |
| routes/private_messaging.py | ~230 | Private messaging |
| routes/user_chats.py | ~223 | User-side chat |
| routes/payment_links.py | ~211 | Merchant payments |
| routes/forum.py | ~180 | Global forum |
| routes/staff_templates.py | ~174 | Message templates |
| routes/notifications.py | ~160 | Notifications |
| routes/merchant.py | ~150 | Merchant products |
| routes/reviews.py | ~150 | Reviews |
| routes/broadcast.py | ~149 | Admin broadcasts |
| routes/transfers.py | ~70 | User transfers |
| routes/payment_links.py | ~211 | Merchant payments |
| routes/forum.py | ~180 | Global forum |
| routes/notifications.py | ~160 | Notifications |
| routes/merchant.py | ~150 | Merchant products |
| routes/reviews.py | ~150 | Reviews & favorites |
| routes/transfers.py | ~70 | User transfers |

### Frontend компоненты admin (всего ~5000 строк)
| Файл | Строк | Описание |
|------|-------|----------|
| UnifiedMessagesHub.jsx | 1840 | Центр сообщений |
| AdminMessagesToStaff.jsx | ~434 | Сообщения персонала ★ NEW |
| UsersManagement.jsx | 410 | Управление пользователями |
| SuperAdminOverview.jsx | 198 | Дашборд админа |
| CryptoPayouts.jsx | ~199 | Выплаты крипто ★ NEW |
| BroadcastPage.jsx | 183 | Рассылки |
| StaffMonitoring.jsx | 181 | Мониторинг персонала |
| MerchantsList.jsx | ~170 | Список мерчантов |
| StaffManagement.jsx | ~150 | Управление персоналом |
| MarketShops.jsx | ~145 | Магазины маркета |
| SharedComponents.jsx | 140 | Общие компоненты |
| PayoutRulesSettings.jsx | ~126 | Правила выплат ★ NEW |
| P2PTrades.jsx | ~120 | Список P2P сделок |
| MarketProducts.jsx | ~105 | Товары маркета |
| SystemSettings.jsx | ~130 | Системные настройки (исправлен баг) |
| FinancesOverview.jsx | ~100 | Финансовая сводка |
| MarketWithdrawals.jsx | ~90 | Выводы средств |
| P2POffers.jsx | ~85 | P2P объявления |
| MarketGuarantor.jsx | ~85 | Гарант-сделки |
| CommissionsSettings.jsx | ~75 | Настройки комиссий |
| ActivityLogs.jsx | ~70 | Логи действий |

---

## Архитектура

### Backend Routes
```
/app/backend/
├── server.py (7569 строк)
└── routes/ (19 модулей, ~5700 строк)
    ├── auth.py, traders.py, merchants.py
    ├── requisites.py, offers.py, trades.py
    ├── payment_links.py, admin.py, super_admin.py
    ├── support.py, shop.py, marketplace.py
    ├── guarantor.py, merchant.py, forum.py
    ├── reviews.py, notifications.py, transfers.py
    └── private_messaging.py, messaging.py
```

### Frontend Components
```
/app/frontend/src/
├── pages/
│   └── AdminPanel.js (304 строк - уменьшен на 94%! Только роутинг и навигация)
└── components/admin/ (21 компонент, ~5000 строк)
```

---

## Оставшиеся задачи

### P1 - Высокий приоритет
- [x] ~~Компонентизация MarketProducts, MarketGuarantor, MarketWithdrawals~~ ✅
- [x] ~~Компонентизация CommissionsSettings, SystemSettings, ActivityLogs~~ ✅
- [ ] Продолжить модуляризацию server.py (~7.5k строк)
- [ ] Извлечь оставшиеся компоненты из AdminPanel.js:
  - PayoutRulesSettings, CryptoPayouts (~300 строк)
  - AdminMessagesToStaff (~120 строк)

### P2 - Средний приоритет
- [ ] UI для 30-минутного таймера P2P сделок
- [ ] UI для broadcast уведомлений

### P3 - Backlog
- [ ] 2FA аутентификация
- [ ] WebSocket real-time обновления

---

## Учётные данные для тестирования

Пароль: `000000`

| Роль | Логин |
|------|-------|
| Admin (owner) | admin |
| Mod P2P | mod_p2p |
| Mod Market | mod_market |
| Support | support |
| Users | user1, user2, user3 |
| Merchants | merchant1, merchant2 |
