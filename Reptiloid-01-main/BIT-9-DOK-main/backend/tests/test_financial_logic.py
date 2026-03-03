"""
ТЕСТЫ ФИНАНСОВОЙ ЛОГИКИ
========================
⚠️ ЗАПУСКАТЬ ПЕРЕД КАЖДЫМ ДЕПЛОЕМ!

Запуск: pytest /app/backend/tests/test_financial_logic.py -v

Эти тесты гарантируют, что финансовые расчёты работают корректно.

БИЗНЕС-ЛОГИКА (v2.0.0):
=======================
1. Трейдер ВСЕГДА получает trader_fee_percent от ORIGINAL суммы
2. Мерчант получает original - trader_earns (трейдер берёт из доли мерчанта)
3. Платформа получает маркер + накрутку (если customer_pays)
4. Сумма распределения ВСЕГДА равна total_amount

customer_pays (1000₽, 30%, 10%):
- total = 1000 + 300 + 10 = 1310₽
- trader = 100₽ (10% от 1000)
- merchant = 900₽ (1000 - 100)
- platform = 310₽ (300 + 10)

merchant_pays (1000₽, 30%, 10%):
- total = 1000 + 10 = 1010₽
- trader = 100₽ (10% от 1000)
- merchant = 900₽ (1000 - 100)
- platform = 10₽ (только маркер)
"""

import pytest
import sys
sys.path.insert(0, '/app/backend')

from financial_logic import (
    calculate_order_amounts,
    calculate_completion_distribution,
    FinancialValidationError,
    __version__
)


class TestCustomerPaysModel:
    """Тесты модели customer_pays (покупатель платит комиссию)"""
    
    def test_basic_distribution(self):
        """Базовый тест: 1000₽, 30% fee, 10% trader"""
        dist = calculate_completion_distribution(
            original_amount_rub=1000,
            total_amount_rub=1310,  # 1000 + 300 + 10
            marker_rub=10,
            merchant_fee_percent=30,
            trader_fee_percent=10,
            fee_model="customer_pays",
            usdt_rate=100
        )
        
        # Трейдер берёт 10% от original из доли мерчанта
        assert dist.trader_earns_rub == 100  # 10% of original
        assert dist.merchant_receives_rub == 900  # original - trader = 1000 - 100
        assert dist.platform_receives_rub == 310  # 30% markup + marker = 300 + 10
        assert dist.casino_credited_rub == 1000  # original
    
    def test_invariant_sum_equals_total(self):
        """Инвариант: merchant + trader + platform = total"""
        dist = calculate_completion_distribution(
            original_amount_rub=1000,
            total_amount_rub=1310,
            marker_rub=10,
            merchant_fee_percent=30,
            trader_fee_percent=10,
            fee_model="customer_pays",
            usdt_rate=100
        )
        
        total = dist.merchant_receives_rub + dist.trader_earns_rub + dist.platform_receives_rub
        assert abs(total - 1310) < 0.01
    
    def test_different_amounts(self):
        """Тест с разными суммами"""
        for original in [500, 1500, 2000, 5000, 10000]:
            marker = 15
            total = original * 1.3 + marker  # 30% markup
            
            dist = calculate_completion_distribution(
                original_amount_rub=original,
                total_amount_rub=total,
                marker_rub=marker,
                merchant_fee_percent=30,
                trader_fee_percent=10,
                fee_model="customer_pays",
                usdt_rate=80
            )
            
            # Трейдер получает 10% от original
            assert abs(dist.trader_earns_rub - original * 0.1) < 0.01
            # Мерчант получает original - trader_earns
            assert abs(dist.merchant_receives_rub - (original - original * 0.1)) < 0.01
            assert dist.casino_credited_rub == original


class TestMerchantPaysModel:
    """Тесты модели merchant_pays (мерчант платит комиссию)"""
    
    def test_basic_distribution(self):
        """Базовый тест: 1000₽, 30% fee, 10% trader"""
        dist = calculate_completion_distribution(
            original_amount_rub=1000,
            total_amount_rub=1010,  # 1000 + 10 (без накрутки)
            marker_rub=10,
            merchant_fee_percent=30,
            trader_fee_percent=10,
            fee_model="merchant_pays",
            usdt_rate=100
        )
        
        # В merchant_pays накрутка не берётся с клиента
        # Трейдер всё равно получает 10% от original
        assert dist.trader_earns_rub == 100  # 10% of original
        assert dist.merchant_receives_rub == 900  # original - trader = 1000 - 100
        assert dist.platform_receives_rub == 10  # только маркер (накрутка не берётся)
        assert dist.casino_credited_rub == 1000  # original
    
    def test_invariant_sum_equals_total(self):
        """Инвариант: merchant + trader + platform = total"""
        dist = calculate_completion_distribution(
            original_amount_rub=1000,
            total_amount_rub=1010,
            marker_rub=10,
            merchant_fee_percent=30,
            trader_fee_percent=10,
            fee_model="merchant_pays",
            usdt_rate=100
        )
        
        total = dist.merchant_receives_rub + dist.trader_earns_rub + dist.platform_receives_rub
        assert abs(total - 1010) < 0.01
    
    def test_platform_gets_less_in_merchant_pays(self):
        """Платформа получает меньше в merchant_pays (только маркер)"""
        # customer_pays
        dist1 = calculate_completion_distribution(
            original_amount_rub=1000,
            total_amount_rub=1310,
            marker_rub=10,
            merchant_fee_percent=30,
            trader_fee_percent=10,
            fee_model="customer_pays",
            usdt_rate=100
        )
        
        # merchant_pays
        dist2 = calculate_completion_distribution(
            original_amount_rub=1000,
            total_amount_rub=1010,
            marker_rub=10,
            merchant_fee_percent=30,
            trader_fee_percent=10,
            fee_model="merchant_pays",
            usdt_rate=100
        )
        
        # Мерчант получает одинаково в обоих моделях
        assert dist1.merchant_receives_rub == dist2.merchant_receives_rub
        # Трейдер получает одинаково
        assert dist1.trader_earns_rub == dist2.trader_earns_rub
        # Платформа получает больше в customer_pays (накрутка + маркер vs только маркер)
        assert dist1.platform_receives_rub > dist2.platform_receives_rub


class TestUSDTConversion:
    """Тесты конвертации в USDT"""
    
    def test_conversion_rate_100(self):
        """Конвертация при курсе 100"""
        dist = calculate_completion_distribution(
            original_amount_rub=1000,
            total_amount_rub=1310,
            marker_rub=10,
            merchant_fee_percent=30,
            trader_fee_percent=10,
            fee_model="customer_pays",
            usdt_rate=100
        )
        
        # merchant = 900₽ / 100 = 9 USDT
        # trader = 100₽ / 100 = 1 USDT
        assert dist.merchant_receives_usdt == 9.0  # 900/100
        assert dist.trader_earns_usdt == 1.0  # 100/100
    
    def test_conversion_rate_79(self):
        """Конвертация при реальном курсе ~79"""
        rate = 79.34
        dist = calculate_completion_distribution(
            original_amount_rub=1000,
            total_amount_rub=1310,
            marker_rub=10,
            merchant_fee_percent=30,
            trader_fee_percent=10,
            fee_model="customer_pays",
            usdt_rate=rate
        )
        
        # merchant = 900₽ / 79.34 ≈ 11.34 USDT
        # trader = 100₽ / 79.34 ≈ 1.26 USDT
        expected_merchant = round(900 / rate, 4)
        expected_trader = round(100 / rate, 4)
        
        assert abs(dist.merchant_receives_usdt - expected_merchant) < 0.001
        assert abs(dist.trader_earns_usdt - expected_trader) < 0.001


class TestValidation:
    """Тесты валидации входных данных"""
    
    def test_negative_amount_raises_error(self):
        """Отрицательная сумма вызывает ошибку"""
        with pytest.raises(FinancialValidationError):
            calculate_completion_distribution(
                original_amount_rub=-1000,
                total_amount_rub=1310,
                marker_rub=10,
                merchant_fee_percent=30,
                trader_fee_percent=10,
                fee_model="customer_pays",
                usdt_rate=100
            )
    
    def test_invalid_fee_model_raises_error(self):
        """Неверная модель вызывает ошибку"""
        with pytest.raises(FinancialValidationError):
            calculate_completion_distribution(
                original_amount_rub=1000,
                total_amount_rub=1310,
                marker_rub=10,
                merchant_fee_percent=30,
                trader_fee_percent=10,
                fee_model="invalid_model",
                usdt_rate=100
            )
    
    def test_zero_rate_raises_error(self):
        """Нулевой курс вызывает ошибку"""
        with pytest.raises(FinancialValidationError):
            calculate_completion_distribution(
                original_amount_rub=1000,
                total_amount_rub=1310,
                marker_rub=10,
                merchant_fee_percent=30,
                trader_fee_percent=10,
                fee_model="customer_pays",
                usdt_rate=0
            )
    
    def test_percent_out_of_range_raises_error(self):
        """Процент вне диапазона вызывает ошибку"""
        with pytest.raises(FinancialValidationError):
            calculate_completion_distribution(
                original_amount_rub=1000,
                total_amount_rub=1310,
                marker_rub=10,
                merchant_fee_percent=150,  # > 100%
                trader_fee_percent=10,
                fee_model="customer_pays",
                usdt_rate=100
            )


class TestOrderCalculation:
    """Тесты создания заказа"""
    
    def test_customer_pays_adds_markup(self):
        """customer_pays добавляет накрутку"""
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
    
    def test_merchant_pays_no_markup(self):
        """merchant_pays без накрутки"""
        calc = calculate_order_amounts(
            original_amount_rub=1000,
            merchant_fee_percent=30,
            trader_fee_percent=10,
            fee_model="merchant_pays",
            usdt_rate=100,
            marker_rub=10
        )
        
        assert calc.original_amount_rub == 1000
        assert calc.total_amount_rub == 1010  # 1000 + 10 (только маркер)


class TestRegressionScenarios:
    """Регрессионные тесты для известных сценариев"""
    
    def test_scenario_three_orders_customer_pays(self):
        """3 заказа 500+1500+2000 с customer_pays"""
        amounts = [500, 1500, 2000]
        rate = 79.34
        total_earned = 0
        total_merchant = 0
        
        for original in amounts:
            total_amount = original * 1.3 + 14  # ~маркер
            
            dist = calculate_completion_distribution(
                original_amount_rub=original,
                total_amount_rub=total_amount,
                marker_rub=14,
                merchant_fee_percent=30,
                trader_fee_percent=10,
                fee_model="customer_pays",
                usdt_rate=rate
            )
            
            total_earned += dist.trader_earns_usdt
            total_merchant += dist.merchant_receives_usdt
        
        # Ожидания: 
        # trader = (500+1500+2000) * 0.10 / 79.34 ≈ 5.04 USDT
        # merchant = (500+1500+2000) * 0.90 / 79.34 ≈ 45.37 USDT (original - trader)
        expected_trader = (500 + 1500 + 2000) * 0.10 / rate
        expected_merchant = (500 + 1500 + 2000) * 0.90 / rate  # 90% because trader takes 10%
        
        assert abs(total_earned - expected_trader) < 0.1
        assert abs(total_merchant - expected_merchant) < 0.1
    
    def test_scenario_three_orders_merchant_pays(self):
        """3 заказа 500+1500+2000 с merchant_pays"""
        amounts = [500, 1500, 2000]
        rate = 79.34
        total_earned = 0
        total_merchant = 0
        
        for original in amounts:
            total_amount = original + 14  # только маркер
            
            dist = calculate_completion_distribution(
                original_amount_rub=original,
                total_amount_rub=total_amount,
                marker_rub=14,
                merchant_fee_percent=30,
                trader_fee_percent=10,
                fee_model="merchant_pays",
                usdt_rate=rate
            )
            
            total_earned += dist.trader_earns_usdt
            total_merchant += dist.merchant_receives_usdt
        
        # Ожидания одинаковые с customer_pays для merchant и trader
        # (разница только в том, что платформа получает меньше)
        expected_trader = (500 + 1500 + 2000) * 0.10 / rate
        expected_merchant = (500 + 1500 + 2000) * 0.90 / rate
        
        assert abs(total_earned - expected_trader) < 0.1
        assert abs(total_merchant - expected_merchant) < 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
