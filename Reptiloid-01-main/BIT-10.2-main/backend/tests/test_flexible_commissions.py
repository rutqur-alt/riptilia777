"""
ТЕСТЫ ГИБКИХ КОМИССИЙ ПО МЕТОДАМ ОПЛАТЫ
========================================
Тестирование:
1. GET /api/admin/merchants/{id}/method-commissions - получение гибких комиссий по методам
2. PUT /api/admin/merchants/{id}/method-commissions - сохранение комиссий card, sbp с интервалами
3. PUT /api/admin/merchants/{id}/fee-settings - смена fee_model (merchant_pays/customer_pays)
4. PUT /api/admin/traders/{id}/fee-settings - сохранение интервалов комиссий трейдера
5. POST /api/trader/orders/{id}/confirm - проверка что при fee_model=merchant_pays используются комиссии по методу оплаты

Запуск: pytest /app/backend/tests/test_flexible_commissions.py -v
"""

import pytest
import requests
import os
import time
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Тестовые учётные данные
ADMIN_CREDS = {"login": "admin", "password": "000000"}
TRADER_CREDS = {"login": "111", "password": "000000"}


class TestSetup:
    """Проверка доступности API и аутентификации"""
    
    def test_api_available(self):
        """Проверка что API доступен"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        assert response.status_code == 200, f"API not available: {response.text}"
        print("✓ API is available")
    
    def test_admin_login(self):
        """Авторизация админа"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["role"] == "admin"
        print(f"✓ Admin login successful: {data.get('nickname')}")
    
    def test_trader_login(self):
        """Авторизация трейдера"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TRADER_CREDS)
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["role"] == "trader"
        print(f"✓ Trader login successful: {data.get('nickname')}")


@pytest.fixture
def admin_token():
    """Получить токен админа"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
    if response.status_code == 200:
        return response.json()["token"]
    pytest.skip("Admin authentication failed")


@pytest.fixture
def trader_token():
    """Получить токен трейдера"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=TRADER_CREDS)
    if response.status_code == 200:
        return response.json()["token"]
    pytest.skip("Trader authentication failed")


@pytest.fixture
def merchant_id(admin_token):
    """Получить ID мерчанта"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.get(f"{BASE_URL}/api/admin/merchants", headers=headers)
    if response.status_code == 200:
        merchants = response.json().get("merchants", [])
        if merchants:
            return merchants[0]["id"]
    pytest.skip("No merchants found")


@pytest.fixture
def trader_id(admin_token):
    """Получить ID трейдера"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.get(f"{BASE_URL}/api/admin/traders", headers=headers)
    if response.status_code == 200:
        traders = response.json().get("traders", [])
        if traders:
            return traders[0]["id"]
    pytest.skip("No traders found")


class TestMerchantMethodCommissions:
    """Тесты гибких комиссий по методам оплаты для мерчанта"""
    
    def test_get_method_commissions(self, admin_token, merchant_id):
        """GET /api/admin/merchants/{id}/method-commissions - получение комиссий"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(
            f"{BASE_URL}/api/admin/merchants/{merchant_id}/method-commissions",
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Проверяем структуру ответа
        assert "merchant_id" in data
        assert "methods" in data
        assert data["merchant_id"] == merchant_id
        
        print(f"✓ Method commissions retrieved for merchant {merchant_id}")
        print(f"  Methods configured: {len(data['methods'])}")
        
        for method in data["methods"]:
            print(f"  - {method['payment_method']}: {len(method.get('intervals', []))} intervals")
        
        return data
    
    def test_save_card_commissions_with_intervals(self, admin_token, merchant_id):
        """PUT /api/admin/merchants/{id}/method-commissions - сохранение комиссий card с интервалами"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Комиссии для card: 100-999=15%, 1000-5999=14.5%, 6000-10999=14%, 11000-15999=13.5%
        payload = {
            "methods": [
                {
                    "payment_method": "card",
                    "intervals": [
                        {"min_amount": 100, "max_amount": 999, "percent": 15.0},
                        {"min_amount": 1000, "max_amount": 5999, "percent": 14.5},
                        {"min_amount": 6000, "max_amount": 10999, "percent": 14.0},
                        {"min_amount": 11000, "max_amount": 15999, "percent": 13.5}
                    ]
                }
            ]
        }
        
        response = requests.put(
            f"{BASE_URL}/api/admin/merchants/{merchant_id}/method-commissions",
            json=payload,
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["success"] == True
        
        # Проверяем что сохранилось
        get_response = requests.get(
            f"{BASE_URL}/api/admin/merchants/{merchant_id}/method-commissions",
            headers=headers
        )
        saved_data = get_response.json()
        
        card_method = None
        for method in saved_data.get("methods", []):
            if method["payment_method"] == "card":
                card_method = method
                break
        
        assert card_method is not None, "Card method not found after save"
        assert len(card_method["intervals"]) == 4, f"Expected 4 intervals, got {len(card_method['intervals'])}"
        
        # Проверяем конкретные значения
        intervals = card_method["intervals"]
        assert intervals[0]["min_amount"] == 100
        assert intervals[0]["max_amount"] == 999
        assert intervals[0]["percent"] == 15.0
        
        assert intervals[1]["min_amount"] == 1000
        assert intervals[1]["max_amount"] == 5999
        assert intervals[1]["percent"] == 14.5
        
        print("✓ Card commissions saved with 4 intervals:")
        for i in intervals:
            print(f"  {i['min_amount']}-{i['max_amount']}₽: {i['percent']}%")
    
    def test_save_sbp_commissions_with_intervals(self, admin_token, merchant_id):
        """PUT /api/admin/merchants/{id}/method-commissions - сохранение комиссий sbp с интервалами"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Сначала получаем текущие комиссии чтобы не потерять card
        get_response = requests.get(
            f"{BASE_URL}/api/admin/merchants/{merchant_id}/method-commissions",
            headers=headers
        )
        current_methods = get_response.json().get("methods", [])
        
        # Добавляем/обновляем sbp
        sbp_intervals = [
            {"min_amount": 100, "max_amount": 5000, "percent": 12.0},
            {"min_amount": 5001, "max_amount": 50000, "percent": 10.0}
        ]
        
        # Обновляем или добавляем sbp
        sbp_found = False
        for method in current_methods:
            if method["payment_method"] == "sbp":
                method["intervals"] = sbp_intervals
                sbp_found = True
                break
        
        if not sbp_found:
            current_methods.append({
                "payment_method": "sbp",
                "intervals": sbp_intervals
            })
        
        payload = {"methods": current_methods}
        
        response = requests.put(
            f"{BASE_URL}/api/admin/merchants/{merchant_id}/method-commissions",
            json=payload,
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        
        # Проверяем что сохранилось
        get_response = requests.get(
            f"{BASE_URL}/api/admin/merchants/{merchant_id}/method-commissions",
            headers=headers
        )
        saved_data = get_response.json()
        
        sbp_method = None
        for method in saved_data.get("methods", []):
            if method["payment_method"] == "sbp":
                sbp_method = method
                break
        
        assert sbp_method is not None, "SBP method not found after save"
        assert len(sbp_method["intervals"]) == 2, f"Expected 2 intervals, got {len(sbp_method['intervals'])}"
        
        # Проверяем значения
        intervals = sbp_method["intervals"]
        assert intervals[0]["min_amount"] == 100
        assert intervals[0]["max_amount"] == 5000
        assert intervals[0]["percent"] == 12.0
        
        assert intervals[1]["min_amount"] == 5001
        assert intervals[1]["max_amount"] == 50000
        assert intervals[1]["percent"] == 10.0
        
        print("✓ SBP commissions saved with 2 intervals:")
        for i in intervals:
            print(f"  {i['min_amount']}-{i['max_amount']}₽: {i['percent']}%")
    
    def test_invalid_payment_method_rejected(self, admin_token, merchant_id):
        """Проверка что неизвестный метод оплаты отклоняется"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        payload = {
            "methods": [
                {
                    "payment_method": "invalid_method",
                    "intervals": [
                        {"min_amount": 100, "max_amount": 1000, "percent": 10.0}
                    ]
                }
            ]
        }
        
        response = requests.put(
            f"{BASE_URL}/api/admin/merchants/{merchant_id}/method-commissions",
            json=payload,
            headers=headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Invalid payment method correctly rejected")
    
    def test_invalid_interval_rejected(self, admin_token, merchant_id):
        """Проверка что невалидный интервал (min >= max) отклоняется"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        payload = {
            "methods": [
                {
                    "payment_method": "card",
                    "intervals": [
                        {"min_amount": 1000, "max_amount": 500, "percent": 10.0}  # min > max
                    ]
                }
            ]
        }
        
        response = requests.put(
            f"{BASE_URL}/api/admin/merchants/{merchant_id}/method-commissions",
            json=payload,
            headers=headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Invalid interval (min > max) correctly rejected")


class TestMerchantFeeSettings:
    """Тесты настроек fee_model мерчанта"""
    
    def test_get_fee_settings(self, admin_token, merchant_id):
        """GET /api/admin/merchants/{id}/fee-settings - получение настроек"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(
            f"{BASE_URL}/api/admin/merchants/{merchant_id}/fee-settings",
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "fee_model" in data
        assert "total_fee_percent" in data
        assert "merchant_id" in data
        
        print(f"✓ Fee settings retrieved:")
        print(f"  fee_model: {data['fee_model']}")
        print(f"  total_fee_percent: {data['total_fee_percent']}%")
        
        return data
    
    def test_set_fee_model_merchant_pays(self, admin_token, merchant_id):
        """PUT /api/admin/merchants/{id}/fee-settings - установка merchant_pays (Тип 1)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        payload = {
            "fee_model": "merchant_pays",
            "total_fee_percent": 5.0
        }
        
        response = requests.put(
            f"{BASE_URL}/api/admin/merchants/{merchant_id}/fee-settings",
            json=payload,
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["success"] == True
        assert data["fee_model"] == "merchant_pays"
        
        # Проверяем что сохранилось
        get_response = requests.get(
            f"{BASE_URL}/api/admin/merchants/{merchant_id}/fee-settings",
            headers=headers
        )
        saved = get_response.json()
        assert saved["fee_model"] == "merchant_pays"
        
        print("✓ Fee model set to merchant_pays (Тип 1)")
    
    def test_set_fee_model_customer_pays(self, admin_token, merchant_id):
        """PUT /api/admin/merchants/{id}/fee-settings - установка customer_pays (Тип 2)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        payload = {
            "fee_model": "customer_pays",
            "total_fee_percent": 30.0
        }
        
        response = requests.put(
            f"{BASE_URL}/api/admin/merchants/{merchant_id}/fee-settings",
            json=payload,
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["success"] == True
        assert data["fee_model"] == "customer_pays"
        
        print("✓ Fee model set to customer_pays (Тип 2)")
        
        # Возвращаем обратно merchant_pays для дальнейших тестов
        payload = {
            "fee_model": "merchant_pays",
            "total_fee_percent": 5.0
        }
        requests.put(
            f"{BASE_URL}/api/admin/merchants/{merchant_id}/fee-settings",
            json=payload,
            headers=headers
        )
    
    def test_invalid_fee_model_rejected(self, admin_token, merchant_id):
        """Проверка что невалидный fee_model отклоняется"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        payload = {
            "fee_model": "invalid_model",
            "total_fee_percent": 10.0
        }
        
        response = requests.put(
            f"{BASE_URL}/api/admin/merchants/{merchant_id}/fee-settings",
            json=payload,
            headers=headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Invalid fee_model correctly rejected")


class TestTraderFeeSettings:
    """Тесты настроек комиссии трейдера"""
    
    def test_get_trader_fee_settings(self, admin_token, trader_id):
        """GET /api/admin/traders/{id}/fee-settings - получение настроек"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(
            f"{BASE_URL}/api/admin/traders/{trader_id}/fee-settings",
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "trader_id" in data
        assert "default_percent" in data
        assert "intervals" in data
        
        print(f"✓ Trader fee settings retrieved:")
        print(f"  default_percent: {data['default_percent']}%")
        print(f"  intervals: {len(data['intervals'])}")
        
        return data
    
    def test_set_trader_fee_intervals(self, admin_token, trader_id):
        """PUT /api/admin/traders/{id}/fee-settings - установка интервалов комиссий"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        payload = {
            "default_percent": 10.0,
            "intervals": [
                {"min_amount": 100, "max_amount": 999, "percent": 12.0},
                {"min_amount": 1000, "max_amount": 4999, "percent": 10.0},
                {"min_amount": 5000, "max_amount": 50000, "percent": 8.0}
            ]
        }
        
        response = requests.put(
            f"{BASE_URL}/api/admin/traders/{trader_id}/fee-settings",
            json=payload,
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["success"] == True
        
        # Проверяем что сохранилось
        get_response = requests.get(
            f"{BASE_URL}/api/admin/traders/{trader_id}/fee-settings",
            headers=headers
        )
        saved = get_response.json()
        
        assert saved["default_percent"] == 10.0
        assert len(saved["intervals"]) == 3
        
        print("✓ Trader fee intervals saved:")
        for i in saved["intervals"]:
            print(f"  {i['min_amount']}-{i['max_amount']}₽: {i['percent']}%")
    
    def test_invalid_trader_interval_rejected(self, admin_token, trader_id):
        """Проверка что невалидный интервал отклоняется"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        payload = {
            "default_percent": 10.0,
            "intervals": [
                {"min_amount": 5000, "max_amount": 1000, "percent": 10.0}  # min > max
            ]
        }
        
        response = requests.put(
            f"{BASE_URL}/api/admin/traders/{trader_id}/fee-settings",
            json=payload,
            headers=headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Invalid trader interval correctly rejected")
    
    def test_trader_percent_out_of_range_rejected(self, admin_token, trader_id):
        """Проверка что процент > 50 отклоняется"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        payload = {
            "default_percent": 60.0,  # > 50
            "intervals": []
        }
        
        response = requests.put(
            f"{BASE_URL}/api/admin/traders/{trader_id}/fee-settings",
            json=payload,
            headers=headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Trader percent > 50 correctly rejected")


class TestOrderConfirmWithMethodCommissions:
    """Тесты подтверждения заказа с использованием комиссий по методу оплаты"""
    
    def test_setup_commissions_for_confirm_test(self, admin_token, merchant_id):
        """Подготовка: установка комиссий для теста confirm"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Устанавливаем fee_model = merchant_pays
        fee_payload = {
            "fee_model": "merchant_pays",
            "total_fee_percent": 5.0
        }
        response = requests.put(
            f"{BASE_URL}/api/admin/merchants/{merchant_id}/fee-settings",
            json=fee_payload,
            headers=headers
        )
        assert response.status_code == 200
        
        # Устанавливаем комиссии по методам
        commissions_payload = {
            "methods": [
                {
                    "payment_method": "card",
                    "intervals": [
                        {"min_amount": 100, "max_amount": 999, "percent": 15.0},
                        {"min_amount": 1000, "max_amount": 5999, "percent": 14.5},
                        {"min_amount": 6000, "max_amount": 10999, "percent": 14.0}
                    ]
                },
                {
                    "payment_method": "sbp",
                    "intervals": [
                        {"min_amount": 100, "max_amount": 5000, "percent": 12.0},
                        {"min_amount": 5001, "max_amount": 50000, "percent": 10.0}
                    ]
                }
            ]
        }
        response = requests.put(
            f"{BASE_URL}/api/admin/merchants/{merchant_id}/method-commissions",
            json=commissions_payload,
            headers=headers
        )
        assert response.status_code == 200
        
        print("✓ Commissions setup complete for confirm test")
    
    def test_verify_method_commissions_in_db(self, admin_token, merchant_id):
        """Проверка что комиссии сохранены в БД"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Получаем fee_settings
        fee_response = requests.get(
            f"{BASE_URL}/api/admin/merchants/{merchant_id}/fee-settings",
            headers=headers
        )
        fee_data = fee_response.json()
        assert fee_data["fee_model"] == "merchant_pays", f"Expected merchant_pays, got {fee_data['fee_model']}"
        
        # Получаем method-commissions
        comm_response = requests.get(
            f"{BASE_URL}/api/admin/merchants/{merchant_id}/method-commissions",
            headers=headers
        )
        comm_data = comm_response.json()
        
        # Проверяем card
        card_found = False
        for method in comm_data.get("methods", []):
            if method["payment_method"] == "card":
                card_found = True
                intervals = method["intervals"]
                # Проверяем интервал 1000-5999 = 14.5%
                for interval in intervals:
                    if interval["min_amount"] == 1000 and interval["max_amount"] == 5999:
                        assert interval["percent"] == 14.5, f"Expected 14.5%, got {interval['percent']}%"
                        print(f"✓ Card interval 1000-5999₽ = {interval['percent']}% verified")
                        break
        
        assert card_found, "Card method not found in commissions"
        
        # Проверяем sbp
        sbp_found = False
        for method in comm_data.get("methods", []):
            if method["payment_method"] == "sbp":
                sbp_found = True
                intervals = method["intervals"]
                # Проверяем интервал 100-5000 = 12%
                for interval in intervals:
                    if interval["min_amount"] == 100 and interval["max_amount"] == 5000:
                        assert interval["percent"] == 12.0, f"Expected 12%, got {interval['percent']}%"
                        print(f"✓ SBP interval 100-5000₽ = {interval['percent']}% verified")
                        break
        
        assert sbp_found, "SBP method not found in commissions"


class TestAllPaymentMethods:
    """Тесты всех 7 методов оплаты"""
    
    def test_all_valid_payment_methods(self, admin_token, merchant_id):
        """Проверка что все 7 методов оплаты принимаются"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        valid_methods = ['card', 'sbp', 'sim', 'mono_bank', 'sng_sbp', 'sng_card', 'qr_code']
        
        for method in valid_methods:
            payload = {
                "methods": [
                    {
                        "payment_method": method,
                        "intervals": [
                            {"min_amount": 100, "max_amount": 10000, "percent": 10.0}
                        ]
                    }
                ]
            }
            
            response = requests.put(
                f"{BASE_URL}/api/admin/merchants/{merchant_id}/method-commissions",
                json=payload,
                headers=headers
            )
            
            assert response.status_code == 200, f"Method {method} failed: {response.text}"
            print(f"✓ Payment method '{method}' accepted")


class TestEdgeCases:
    """Тесты граничных случаев"""
    
    def test_empty_methods_list(self, admin_token, merchant_id):
        """Проверка сохранения пустого списка методов"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        payload = {"methods": []}
        
        response = requests.put(
            f"{BASE_URL}/api/admin/merchants/{merchant_id}/method-commissions",
            json=payload,
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        print("✓ Empty methods list accepted")
    
    def test_empty_intervals_list(self, admin_token, merchant_id):
        """Проверка сохранения метода с пустым списком интервалов"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        payload = {
            "methods": [
                {
                    "payment_method": "card",
                    "intervals": []
                }
            ]
        }
        
        response = requests.put(
            f"{BASE_URL}/api/admin/merchants/{merchant_id}/method-commissions",
            json=payload,
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        print("✓ Empty intervals list accepted")
    
    def test_percent_boundary_values(self, admin_token, merchant_id):
        """Проверка граничных значений процента (0 и 100)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Тест 0%
        payload = {
            "methods": [
                {
                    "payment_method": "card",
                    "intervals": [
                        {"min_amount": 100, "max_amount": 1000, "percent": 0.0}
                    ]
                }
            ]
        }
        
        response = requests.put(
            f"{BASE_URL}/api/admin/merchants/{merchant_id}/method-commissions",
            json=payload,
            headers=headers
        )
        assert response.status_code == 200, f"0% failed: {response.text}"
        print("✓ 0% commission accepted")
        
        # Тест 100%
        payload["methods"][0]["intervals"][0]["percent"] = 100.0
        response = requests.put(
            f"{BASE_URL}/api/admin/merchants/{merchant_id}/method-commissions",
            json=payload,
            headers=headers
        )
        assert response.status_code == 200, f"100% failed: {response.text}"
        print("✓ 100% commission accepted")
        
        # Тест > 100% - должен быть отклонён
        payload["methods"][0]["intervals"][0]["percent"] = 101.0
        response = requests.put(
            f"{BASE_URL}/api/admin/merchants/{merchant_id}/method-commissions",
            json=payload,
            headers=headers
        )
        assert response.status_code == 400, f"Expected 400 for 101%, got {response.status_code}"
        print("✓ 101% commission correctly rejected")


class TestRestoreOriginalSettings:
    """Восстановление оригинальных настроек после тестов"""
    
    def test_restore_merchant_commissions(self, admin_token, merchant_id):
        """Восстановление комиссий мерчанта"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        payload = {
            "methods": [
                {
                    "payment_method": "card",
                    "intervals": [
                        {"min_amount": 100, "max_amount": 999, "percent": 15.0},
                        {"min_amount": 1000, "max_amount": 5999, "percent": 14.5},
                        {"min_amount": 6000, "max_amount": 10999, "percent": 14.0},
                        {"min_amount": 11000, "max_amount": 15999, "percent": 13.5}
                    ]
                },
                {
                    "payment_method": "sbp",
                    "intervals": [
                        {"min_amount": 100, "max_amount": 5000, "percent": 12.0},
                        {"min_amount": 5001, "max_amount": 50000, "percent": 10.0}
                    ]
                }
            ]
        }
        
        response = requests.put(
            f"{BASE_URL}/api/admin/merchants/{merchant_id}/method-commissions",
            json=payload,
            headers=headers
        )
        
        assert response.status_code == 200
        print("✓ Merchant commissions restored")
    
    def test_restore_trader_settings(self, admin_token, trader_id):
        """Восстановление настроек трейдера"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        payload = {
            "default_percent": 10.0,
            "intervals": []
        }
        
        response = requests.put(
            f"{BASE_URL}/api/admin/traders/{trader_id}/fee-settings",
            json=payload,
            headers=headers
        )
        
        assert response.status_code == 200
        print("✓ Trader settings restored")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
