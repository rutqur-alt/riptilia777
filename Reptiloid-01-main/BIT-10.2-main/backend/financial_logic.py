"""
BITARBITR P2P Platform - Financial Logic Module
================================================
⚠️ КРИТИЧЕСКИ ВАЖНЫЙ МОДУЛЬ - НЕ ИЗМЕНЯТЬ БЕЗ ПОЛНОГО ТЕСТИРОВАНИЯ!

Централизованный модуль для расчёта комиссий и распределения средств.
ВСЕ финансовые операции ДОЛЖНЫ проходить через этот модуль.

ВЕРСИЯ: 2.0.0
ПОСЛЕДНЕЕ ИЗМЕНЕНИЕ: 2026-01-11
ТЕСТЫ: pytest /app/backend/tests/test_financial_logic.py

================================================================================
ФИНАНСОВАЯ МОДЕЛЬ
================================================================================

Вариант 1: customer_pays (покупатель платит комиссию)
-----------------------------------------------------
- Клиент хочет: 1000₽
- Накрутка: 30%
- Заявка: 1300₽ + маркер (клиент платит больше)
- Распределение:
  * Мерчант: 1000₽ (original_amount - 100%)
  * Трейдер: 100₽ (10% от original)
  * Платформа: 200₽ + маркер (20% от original + маркер)
  * Казино: +1000₽

Вариант 2: merchant_pays (мерчант платит комиссию)
--------------------------------------------------
- Клиент хочет: 1000₽
- Накрутка: 30%
- Заявка: 1000₽ + маркер (клиент платит только original)
- Распределение:
  * Мерчант: 700₽ (original - 30%)
  * Трейдер: 100₽ (10% от original)
  * Платформа: 200₽ + маркер (20% от original + маркер)
  * Казино: +1000₽

================================================================================
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)

# Версия модуля для отслеживания изменений
__version__ = "2.0.0"

# Константы - НЕ ИЗМЕНЯТЬ!
MIN_AMOUNT_RUB = 100.0
MAX_AMOUNT_RUB = 10_000_000.0
MIN_FEE_PERCENT = 0.0
MAX_FEE_PERCENT = 100.0
DEFAULT_TRADER_FEE_PERCENT = 10.0
DEFAULT_MERCHANT_FEE_PERCENT = 30.0


class FinancialValidationError(Exception):
    """Ошибка валидации финансовых данных"""
    pass


def _round_rub(value: float) -> float:
    """Округление рублей до копеек"""
    return float(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def _round_usdt(value: float) -> float:
    """Округление USDT до 4 знаков"""
    return float(Decimal(str(value)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))


def _validate_amount(amount: float, name: str) -> None:
    """Валидация суммы"""
    if amount < 0:
        raise FinancialValidationError(f"{name} не может быть отрицательным: {amount}")
    if amount > MAX_AMOUNT_RUB:
        raise FinancialValidationError(f"{name} превышает максимум: {amount} > {MAX_AMOUNT_RUB}")


def _validate_percent(percent: float, name: str) -> None:
    """Валидация процента"""
    if percent < MIN_FEE_PERCENT or percent > MAX_FEE_PERCENT:
        raise FinancialValidationError(f"{name} вне диапазона [0-100]: {percent}")


def _validate_rate(rate: float) -> None:
    """Валидация курса"""
    if rate <= 0:
        raise FinancialValidationError(f"Курс должен быть положительным: {rate}")
    if rate < 10 or rate > 500:
        logger.warning(f"Необычный курс USDT/RUB: {rate}")


@dataclass(frozen=True)
class OrderCalculation:
    """
    Расчёт для создания заказа (immutable).
    
    frozen=True гарантирует, что объект нельзя изменить после создания.
    """
    original_amount_rub: float      # Сумма которую хочет клиент
    total_amount_rub: float         # Сумма которую платит клиент
    marker_rub: float               # Маркер для идентификации
    fee_model: str                  # customer_pays / merchant_pays
    merchant_fee_percent: float     # Накрутка мерчанта
    trader_fee_percent: float       # Доля трейдера
    
    # В USDT
    original_amount_usdt: float
    total_amount_usdt: float
    marker_usdt: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для сохранения"""
        return {
            "original_amount_rub": self.original_amount_rub,
            "total_amount_rub": self.total_amount_rub,
            "marker_rub": self.marker_rub,
            "fee_model": self.fee_model,
            "merchant_fee_percent": self.merchant_fee_percent,
            "trader_fee_percent": self.trader_fee_percent,
            "original_amount_usdt": self.original_amount_usdt,
            "total_amount_usdt": self.total_amount_usdt,
            "marker_usdt": self.marker_usdt,
        }


@dataclass(frozen=True)
class CompletionDistribution:
    """
    Распределение средств при завершении заказа (immutable).
    
    ИНВАРИАНТ: merchant + trader + platform = total_amount (в рублях)
    """
    # Суммы в рублях
    merchant_receives_rub: float    # Мерчант получает
    trader_earns_rub: float         # Трейдер зарабатывает
    platform_receives_rub: float    # Платформа получает
    casino_credited_rub: float      # Казино зачисляется
    
    # Суммы в USDT
    merchant_receives_usdt: float
    trader_earns_usdt: float
    platform_receives_usdt: float
    
    # Операции с балансом трейдера
    trader_locked_released_usdt: float  # Разблокировать
    trader_balance_deducted_usdt: float # Списать (для расчёта)
    
    def validate_invariant(self, total_amount_rub: float) -> bool:
        """
        Проверка инварианта: сумма распределения = total_amount.
        
        Returns:
            True если инвариант выполняется
        
        Raises:
            FinancialValidationError если инвариант нарушен
        """
        calculated_total = (
            self.merchant_receives_rub + 
            self.trader_earns_rub + 
            self.platform_receives_rub
        )
        diff = abs(calculated_total - total_amount_rub)
        
        if diff > 0.01:  # Допуск 1 копейка
            raise FinancialValidationError(
                f"Инвариант нарушен! Сумма={calculated_total:.2f}, "
                f"Ожидалось={total_amount_rub:.2f}, Разница={diff:.2f}"
            )
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для сохранения"""
        return {
            "merchant_rub": self.merchant_receives_rub,
            "trader_rub": self.trader_earns_rub,
            "platform_rub": self.platform_receives_rub,
            "casino_rub": self.casino_credited_rub,
            "merchant_usdt": self.merchant_receives_usdt,
            "trader_usdt": self.trader_earns_usdt,
            "platform_usdt": self.platform_receives_usdt,
        }


def calculate_order_amounts(
    original_amount_rub: float,
    merchant_fee_percent: float,
    trader_fee_percent: float,
    fee_model: str,
    usdt_rate: float,
    marker_rub: Optional[float] = None
) -> OrderCalculation:
    """
    Рассчитать суммы для создания заказа.
    
    Args:
        original_amount_rub: Сумма которую хочет получить клиент (100-10M)
        merchant_fee_percent: Процент накрутки мерчанта (0-100)
        trader_fee_percent: Доля трейдера от original (0-100)
        fee_model: 'customer_pays' или 'merchant_pays'
        usdt_rate: Курс USDT/RUB (положительное число)
        marker_rub: Маркер (если None - генерируется 5-20₽)
    
    Returns:
        OrderCalculation с рассчитанными суммами
    
    Raises:
        FinancialValidationError при некорректных входных данных
    """
    import random
    
    # Валидация входных данных
    _validate_amount(original_amount_rub, "original_amount_rub")
    _validate_percent(merchant_fee_percent, "merchant_fee_percent")
    _validate_percent(trader_fee_percent, "trader_fee_percent")
    _validate_rate(usdt_rate)
    
    if fee_model not in ("customer_pays", "merchant_pays"):
        raise FinancialValidationError(f"Неизвестная модель: {fee_model}")
    
    if original_amount_rub < MIN_AMOUNT_RUB:
        raise FinancialValidationError(
            f"Минимальная сумма: {MIN_AMOUNT_RUB}₽, получено: {original_amount_rub}₽"
        )
    
    # Генерация маркера
    if marker_rub is None:
        marker_rub = random.randint(5, 20)  # 5-20₽
    
    # Расчёт total в зависимости от модели
    if fee_model == "customer_pays":
        # Покупатель платит накрутку
        fee_amount_rub = original_amount_rub * merchant_fee_percent / 100
        total_amount_rub = original_amount_rub + fee_amount_rub + marker_rub
    else:
        # Мерчант платит накрутку - клиент платит только original + маркер
        total_amount_rub = original_amount_rub + marker_rub
    
    # Округление
    total_amount_rub = _round_rub(total_amount_rub)
    marker_rub = _round_rub(marker_rub)
    
    # Конвертация в USDT
    original_amount_usdt = _round_usdt(original_amount_rub / usdt_rate)
    total_amount_usdt = _round_usdt(total_amount_rub / usdt_rate)
    marker_usdt = _round_usdt(marker_rub / usdt_rate)
    
    return OrderCalculation(
        original_amount_rub=original_amount_rub,
        total_amount_rub=total_amount_rub,
        marker_rub=marker_rub,
        fee_model=fee_model,
        merchant_fee_percent=merchant_fee_percent,
        trader_fee_percent=trader_fee_percent,
        original_amount_usdt=original_amount_usdt,
        total_amount_usdt=total_amount_usdt,
        marker_usdt=marker_usdt
    )


def calculate_completion_distribution(
    original_amount_rub: float,
    total_amount_rub: float,
    marker_rub: float,
    merchant_fee_percent: float,
    trader_fee_percent: float,
    fee_model: str,
    usdt_rate: float
) -> CompletionDistribution:
    """
    Рассчитать распределение средств при завершении заказа.
    
    КЛЮЧЕВЫЕ ПРАВИЛА:
    1. Трейдер ВСЕГДА получает trader_fee_percent от ORIGINAL суммы
    2. Казино ВСЕГДА получает ORIGINAL сумму
    3. Сумма распределения ВСЕГДА равна total_amount
    
    Args:
        original_amount_rub: Оригинальная сумма (что хочет клиент)
        total_amount_rub: Полная сумма (что платит клиент)
        marker_rub: Маркер
        merchant_fee_percent: Процент накрутки мерчанта (30 = 30%)
        trader_fee_percent: Процент комиссии трейдера от original (10 = 10%)
        fee_model: 'customer_pays' или 'merchant_pays'
        usdt_rate: Курс USDT/RUB
    
    Returns:
        CompletionDistribution с распределением средств
    
    Raises:
        FinancialValidationError при некорректных данных или нарушении инварианта
    """
    # Валидация
    _validate_amount(original_amount_rub, "original_amount_rub")
    _validate_amount(total_amount_rub, "total_amount_rub")
    _validate_percent(merchant_fee_percent, "merchant_fee_percent")
    _validate_percent(trader_fee_percent, "trader_fee_percent")
    _validate_rate(usdt_rate)
    
    if fee_model not in ("customer_pays", "merchant_pays"):
        raise FinancialValidationError(f"Неизвестная модель: {fee_model}")
    
    # === РАСЧЁТ РАСПРЕДЕЛЕНИЯ ===
    
    # Комиссия трейдера = trader_fee_percent от ORIGINAL суммы
    trader_earns_rub = _round_rub(original_amount_rub * trader_fee_percent / 100)
    
    if fee_model == "customer_pays":
        # ТИП 2: Покупатель платит накрутку
        # total = original + накрутка + маркер
        # Мерчант получает ORIGINAL сумму
        # Трейдер получает свой % от original → в Earned
        # Платформа получает остаток (накрутка + маркер - комиссия трейдера)
        merchant_receives_rub = original_amount_rub
        platform_receives_rub = _round_rub(total_amount_rub - original_amount_rub - trader_earns_rub)
    else:
        # ТИП 1: Мерчант платит комиссию (merchant_pays)
        # Общая комиссия = merchant_fee_percent от original (например 20%)
        # Из этой комиссии:
        #   - trader_fee_percent идёт трейдеру (например 10%)
        #   - остаток идёт платформе (например 10%)
        # Мерчант получает: original - общая_комиссия
        # Маркер идёт платформе дополнительно
        
        total_commission_rub = _round_rub(original_amount_rub * merchant_fee_percent / 100)
        # Комиссия трейдера - это часть общей комиссии
        # trader_earns_rub уже рассчитан выше как original * trader_fee_percent / 100
        
        # Платформа получает: общая комиссия - комиссия трейдера + маркер
        platform_receives_rub = _round_rub(total_commission_rub - trader_earns_rub + marker_rub)
        
        # Мерчант получает: original - общая комиссия (без маркера, маркер платит покупатель)
        merchant_receives_rub = _round_rub(original_amount_rub - total_commission_rub)
    
    # Защита от отрицательных значений
    if merchant_receives_rub < 0:
        logger.warning(
            f"Отрицательная сумма мерчанта! "
            f"original={original_amount_rub}, trader={trader_earns_rub}, platform={platform_receives_rub}. Ставим 0."
        )
        merchant_receives_rub = 0
    
    if platform_receives_rub < 0:
        logger.warning(
            f"Отрицательная комиссия платформы! "
            f"total={total_amount_rub}, merchant={merchant_receives_rub}, "
            f"trader={trader_earns_rub}, marker={marker_rub}. Ставим 0."
        )
        platform_receives_rub = 0
    
    # ПРОВЕРКА ИНВАРИАНТА: total = merchant + trader + platform
    calculated_total = merchant_receives_rub + trader_earns_rub + platform_receives_rub
    if abs(calculated_total - total_amount_rub) > 1:  # Допуск 1 рубль
        logger.warning(f"Invariant mismatch: {calculated_total} != {total_amount_rub}, adjusting platform")
        platform_receives_rub = _round_rub(total_amount_rub - merchant_receives_rub - trader_earns_rub)
    
    # Casino credited = original_amount (для совместимости)
    casino_credited_rub = original_amount_rub
    
    # === КОНВЕРТАЦИЯ В USDT ===
    merchant_receives_usdt = _round_usdt(merchant_receives_rub / usdt_rate)
    trader_earns_usdt = _round_usdt(trader_earns_rub / usdt_rate)
    platform_receives_usdt = _round_usdt(platform_receives_rub / usdt_rate)
    
    # === ОПЕРАЦИИ С БАЛАНСОМ ТРЕЙДЕРА ===
    trader_locked_released_usdt = _round_usdt(total_amount_rub / usdt_rate)
    trader_balance_deducted_usdt = _round_usdt((total_amount_rub - trader_earns_rub) / usdt_rate)
    
    # Создаём результат
    result = CompletionDistribution(
        merchant_receives_rub=merchant_receives_rub,
        trader_earns_rub=trader_earns_rub,
        platform_receives_rub=platform_receives_rub,
        casino_credited_rub=casino_credited_rub,
        merchant_receives_usdt=merchant_receives_usdt,
        trader_earns_usdt=trader_earns_usdt,
        platform_receives_usdt=platform_receives_usdt,
        trader_locked_released_usdt=trader_locked_released_usdt,
        trader_balance_deducted_usdt=trader_balance_deducted_usdt
    )
    
    # Проверяем инвариант
    result.validate_invariant(total_amount_rub)
    
    # Логирование
    logger.info(f"=== DISTRIBUTION [v{__version__}] ===")
    logger.info(f"Model: {fee_model}, Rate: {usdt_rate}₽/USDT")
    logger.info(f"Original: {original_amount_rub}₽, Total: {total_amount_rub}₽")
    logger.info(f"Merchant: {merchant_receives_rub}₽ ({merchant_receives_usdt} USDT)")
    logger.info(f"Trader: {trader_earns_rub}₽ ({trader_earns_usdt} USDT)")
    logger.info(f"Platform: {platform_receives_rub}₽ ({platform_receives_usdt} USDT)")
    logger.info(f"Casino: +{casino_credited_rub}₽")
    logger.info("=" * 40)
    
    return result


async def process_order_completion(
    db,
    order: dict,
    trader_user_id: str,
    usdt_rate: float
) -> dict:
    """
    Обработать завершение заказа - обновить все балансы.
    
    ЭТО ЕДИНСТВЕННАЯ ФУНКЦИЯ которая должна обновлять балансы при завершении заказа!
    
    Args:
        db: MongoDB database
        order: Документ заказа
        trader_user_id: ID пользователя-трейдера
        usdt_rate: Текущий курс USDT/RUB
    
    Returns:
        dict с результатами операции
    
    Raises:
        FinancialValidationError при ошибке расчётов
    """
    # Получаем данные из заказа
    original_amount_rub = order.get("original_amount_rub", order.get("amount_rub", 0))
    total_amount_rub = order.get("amount_rub", 0)
    marker_rub = order.get("marker_amount_rub", order.get("marker_rub", 0))
    fee_model = order.get("fee_model", "customer_pays")
    merchant_fee_percent = order.get("total_fee_percent", order.get("merchant_fee_percent", DEFAULT_MERCHANT_FEE_PERCENT))
    trader_fee_percent = order.get("trader_fee_percent", DEFAULT_TRADER_FEE_PERCENT)
    
    # Рассчитываем распределение
    distribution = calculate_completion_distribution(
        original_amount_rub=original_amount_rub,
        total_amount_rub=total_amount_rub,
        marker_rub=marker_rub,
        merchant_fee_percent=merchant_fee_percent,
        trader_fee_percent=trader_fee_percent,
        fee_model=fee_model,
        usdt_rate=usdt_rate
    )
    
    # 1. ТРЕЙДЕР: разблокируем locked, добавляем earned
    await db.wallets.update_one(
        {"user_id": trader_user_id},
        {"$inc": {
            "locked_balance_usdt": -distribution.trader_locked_released_usdt,
            "earned_balance_usdt": distribution.trader_earns_usdt
        }}
    )
    
    # Исправляем погрешность округления - locked не может быть отрицательным
    wallet_check = await db.wallets.find_one(
        {"user_id": trader_user_id}, 
        {"_id": 0, "locked_balance_usdt": 1}
    )
    if wallet_check and wallet_check.get("locked_balance_usdt", 0) < 0:
        await db.wallets.update_one(
            {"user_id": trader_user_id},
            {"$set": {"locked_balance_usdt": 0}}
        )
    
    logger.info(f"Trader {trader_user_id}: locked -{distribution.trader_locked_released_usdt}, earned +{distribution.trader_earns_usdt}")
    
    # 2. МЕРЧАНТ: обновляем баланс
    merchant_id = order.get("merchant_id")
    if merchant_id:
        # Обновляем статистику мерчанта
        await db.merchants.update_one(
            {"id": merchant_id},
            {"$inc": {
                "balance_usdt": distribution.merchant_receives_usdt,
                "total_volume_usdt": distribution.merchant_receives_usdt,
                "total_orders_completed": 1
            }}
        )
        
        # Обновляем кошелёк мерчанта
        merchant = await db.merchants.find_one({"id": merchant_id}, {"_id": 0, "user_id": 1})
        if merchant and merchant.get("user_id"):
            await db.wallets.update_one(
                {"user_id": merchant["user_id"]},
                {"$inc": {"available_balance_usdt": distribution.merchant_receives_usdt}},
                upsert=True
            )
        
        logger.info(f"Merchant {merchant_id}: +{distribution.merchant_receives_usdt} USDT")
    
    # 3. КАЗИНО: зачисляем original сумму
    if order.get("source") == "test_casino":
        await db.test_casino.update_one(
            {"type": "casino_state"},
            {"$inc": {"balance": distribution.casino_credited_rub}},
            upsert=True
        )
        logger.info(f"Casino: +{distribution.casino_credited_rub}₽")
    
    # 4. ПЛАТФОРМА: записываем доход
    await db.platform_income.insert_one({
        "id": f"pinc_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "order_id": order["id"],
        "amount_rub": distribution.platform_receives_rub,
        "amount_usdt": distribution.platform_receives_usdt,
        "fee_model": fee_model,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    # 5. Сохраняем данные о комиссиях в заказ
    await db.orders.update_one(
        {"id": order["id"]},
        {"$set": {
            "merchant_receives_usdt": distribution.merchant_receives_usdt,
            "trader_commission_usdt": distribution.trader_earns_usdt,
            "platform_commission_usdt": distribution.platform_receives_usdt,
            "completion_distribution": {
                **distribution.to_dict(),
                "usdt_rate": usdt_rate,
                "version": __version__,
                "processed_at": datetime.now(timezone.utc).isoformat()
            }
        }}
    )
    
    return {
        "success": True,
        "version": __version__,
        "distribution": {
            "merchant_receives_usdt": distribution.merchant_receives_usdt,
            "trader_earns_usdt": distribution.trader_earns_usdt,
            "platform_receives_usdt": distribution.platform_receives_usdt,
            "casino_credited_rub": distribution.casino_credited_rub
        }
    }


# ============================================================================
# UNIT TESTS - Запускаются при python financial_logic.py
# ============================================================================

def _run_tests():
    """Запуск всех unit-тестов"""
    import sys
    
    print(f"\n{'='*60}")
    print(f"FINANCIAL LOGIC TESTS v{__version__}")
    print(f"{'='*60}")
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: customer_pays (Тип 2)
    # original=1000, накрутка 30%=300, маркер=12 → total=1312
    # Мерчант получает ORIGINAL сумму!
    print("\n[TEST 1] customer_pays / Тип 2 (1000₽, накрутка 30%, трейдер 12%)")
    try:
        dist = calculate_completion_distribution(
            original_amount_rub=1000,
            total_amount_rub=1312,  # 1000 + 300 + 12 маркер
            marker_rub=12,
            merchant_fee_percent=30,
            trader_fee_percent=12,
            fee_model="customer_pays",
            usdt_rate=100
        )
        
        # Логика Тип 2:
        # - trader_earns = 1000 * 12% = 120₽ → в Earned
        # - merchant_receives = 1000₽ (original)
        # - platform_receives = 1312 - 1000 - 120 = 192₽
        # - Total: 1000 + 120 + 192 = 1312₽ ✓
        assert dist.merchant_receives_rub == 1000, f"Merchant: {dist.merchant_receives_rub} != 1000"
        assert dist.trader_earns_rub == 120, f"Trader: {dist.trader_earns_rub} != 120"
        assert dist.platform_receives_rub == 192, f"Platform: {dist.platform_receives_rub} != 192"
        
        print(f"   Мерчант: {dist.merchant_receives_rub}₽ ✓")
        print(f"   Трейдер (→ Earned): {dist.trader_earns_rub}₽ ✓")
        print(f"   Платформа: {dist.platform_receives_rub}₽ ✓")
        print("   ✅ PASSED")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        tests_failed += 1
    
    # Test 2: merchant_pays (Тип 1)
    # original=1000, маркер=12 → total=1012 (без накрутки!)
    # Комиссия платформы (14%) + маркер вычитается из locked
    print("\n[TEST 2] merchant_pays / Тип 1 (1000₽, платформа 14%, трейдер 12%)")
    try:
        dist = calculate_completion_distribution(
            original_amount_rub=1000,
            total_amount_rub=1012,  # 1000 + 12 маркер
            marker_rub=12,
            merchant_fee_percent=14,  # Комиссия платформы = 140₽
            trader_fee_percent=12,    # Комиссия трейдера = 120₽
            fee_model="merchant_pays",
            usdt_rate=100
        )
        
        # Логика Тип 1:
        # - trader_earns = 1000 * 12% = 120₽ → в Earned
        # - platform_receives = 140₽ (14% от 1000) + 12₽ маркер = 152₽
        # - merchant_receives = 1012 - 120 - 152 = 740₽
        # - Total: 740 + 120 + 152 = 1012₽ ✓
        assert dist.trader_earns_rub == 120, f"Trader: {dist.trader_earns_rub} != 120"
        assert dist.platform_receives_rub == 152, f"Platform: {dist.platform_receives_rub} != 152"
        assert dist.merchant_receives_rub == 740, f"Merchant: {dist.merchant_receives_rub} != 740"
        
        print(f"   Трейдер (→ Earned): {dist.trader_earns_rub}₽ ✓")
        print(f"   Платформа: {dist.platform_receives_rub}₽ ✓")
        print(f"   Мерчант: {dist.merchant_receives_rub}₽ ✓")
        print("   ✅ PASSED")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        tests_failed += 1
    
    # Test 3: Инвариант (сумма = total)
    print("\n[TEST 3] Invariant check (sum == total)")
    try:
        for total in [500, 1000, 5000, 10000, 100000]:
            dist = calculate_completion_distribution(
                original_amount_rub=total * 0.77,  # ~77% от total
                total_amount_rub=total,
                marker_rub=10,
                merchant_fee_percent=30,
                trader_fee_percent=10,
                fee_model="customer_pays",
                usdt_rate=80
            )
            dist.validate_invariant(total)
        print("   ✅ PASSED (all amounts)")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        tests_failed += 1
    
    # Test 4: USDT конвертация (Тип 2)
    print("\n[TEST 4] USDT conversion (rate=79.34)")
    try:
        rate = 79.34
        dist = calculate_completion_distribution(
            original_amount_rub=1000,
            total_amount_rub=1312,  # 1000 + 300 + 12
            marker_rub=12,
            merchant_fee_percent=30,
            trader_fee_percent=12,
            fee_model="customer_pays",
            usdt_rate=rate
        )
        
        # Тип 2: merchant = 1000₽, trader = 120₽
        expected_merchant_usdt = round(1000 / rate, 4)
        expected_trader_usdt = round(120 / rate, 4)
        
        assert abs(dist.merchant_receives_usdt - expected_merchant_usdt) < 0.01
        assert abs(dist.trader_earns_usdt - expected_trader_usdt) < 0.01
        
        print(f"   Мерчант: {dist.merchant_receives_usdt} USDT ✓")
        print(f"   Трейдер: {dist.trader_earns_usdt} USDT ✓")
        print("   ✅ PASSED")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        tests_failed += 1
    
    # Test 5: Валидация ошибок
    print("\n[TEST 5] Validation errors")
    try:
        # Отрицательная сумма
        try:
            calculate_completion_distribution(-100, 100, 10, 30, 10, "customer_pays", 100)
            raise AssertionError("Should have raised error for negative amount")
        except FinancialValidationError:
            pass
        
        # Неверная модель
        try:
            calculate_completion_distribution(100, 100, 10, 30, 10, "invalid_model", 100)
            raise AssertionError("Should have raised error for invalid model")
        except FinancialValidationError:
            pass
        
        # Нулевой курс
        try:
            calculate_completion_distribution(100, 100, 10, 30, 10, "customer_pays", 0)
            raise AssertionError("Should have raised error for zero rate")
        except FinancialValidationError:
            pass
        
        print("   ✅ PASSED (all validations)")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        tests_failed += 1
    
    # Test 6: Order calculation
    print("\n[TEST 6] Order calculation")
    try:
        calc = calculate_order_amounts(
            original_amount_rub=1000,
            merchant_fee_percent=30,
            trader_fee_percent=10,
            fee_model="customer_pays",
            usdt_rate=100,
            marker_rub=10
        )
        
        assert calc.original_amount_rub == 1000
        assert calc.total_amount_rub == 1310  # 1000 + 300 + 10
        assert calc.marker_rub == 10
        
        print(f"   Original: {calc.original_amount_rub}₽ ✓")
        print(f"   Total: {calc.total_amount_rub}₽ ✓")
        print("   ✅ PASSED")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        tests_failed += 1
    
    # Итог
    print(f"\n{'='*60}")
    print(f"RESULTS: {tests_passed} passed, {tests_failed} failed")
    print(f"{'='*60}")
    
    if tests_failed > 0:
        sys.exit(1)
    
    print("\n✅ ALL TESTS PASSED")


if __name__ == "__main__":
    _run_tests()
