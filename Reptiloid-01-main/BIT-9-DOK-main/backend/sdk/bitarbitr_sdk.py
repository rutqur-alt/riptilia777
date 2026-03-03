"""
BITARBITR Invoice API SDK для Python

Установка:
    pip install requests

Использование:
    from bitarbitr_sdk import BitarbitrClient

    client = BitarbitrClient(
        api_key="sk_live_xxx",
        secret_key="your_secret_key",
        merchant_id="mrc_xxx"
    )

    # Создание инвойса
    invoice = client.create_invoice(
        order_id="ORDER_001",
        amount=1500.00,
        callback_url="https://mysite.com/callback"
    )

    # Проверка статуса
    status = client.get_status(payment_id=invoice["payment_id"])

    # Список транзакций
    transactions = client.get_transactions(status="completed", limit=50)
"""

import hmac
import hashlib
import requests
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime


class BitarbitrError(Exception):
    """Базовое исключение SDK"""
    def __init__(self, code: str, message: str, http_status: int = None):
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(f"{code}: {message}")


class SignatureError(BitarbitrError):
    """Ошибка подписи"""
    pass


class RateLimitError(BitarbitrError):
    """Превышен rate limit"""
    def __init__(self, message: str, reset_in: int = None):
        super().__init__("RATE_LIMIT_EXCEEDED", message, 429)
        self.reset_in = reset_in


class AuthenticationError(BitarbitrError):
    """Ошибка аутентификации"""
    pass


@dataclass
class Invoice:
    """Инвойс (платёж)"""
    payment_id: str
    payment_url: str
    details: Dict[str, Any]
    
    @classmethod
    def from_response(cls, data: dict) -> "Invoice":
        return cls(
            payment_id=data["payment_id"],
            payment_url=data["payment_url"],
            details=data["details"]
        )


@dataclass
class InvoiceStatus:
    """Статус инвойса"""
    order_id: str
    payment_id: str
    status: str
    amount: float
    amount_usdt: Optional[float] = None
    created_at: Optional[str] = None
    paid_at: Optional[str] = None
    expires_at: Optional[str] = None
    dispute_url: Optional[str] = None
    
    @classmethod
    def from_response(cls, data: dict) -> "InvoiceStatus":
        return cls(
            order_id=data.get("order_id"),
            payment_id=data.get("payment_id"),
            status=data.get("status"),
            amount=data.get("amount"),
            amount_usdt=data.get("amount_usdt"),
            created_at=data.get("created_at"),
            paid_at=data.get("paid_at"),
            expires_at=data.get("expires_at"),
            dispute_url=data.get("dispute_url")
        )


@dataclass
class Stats:
    """Статистика API"""
    period: str
    total_invoices: int
    paid: int
    pending: int
    failed: int
    disputes: int
    total_rub: float
    total_usdt: float
    conversion_rate: float
    
    @classmethod
    def from_response(cls, data: dict) -> "Stats":
        summary = data.get("summary", {})
        volume = data.get("volume", {})
        return cls(
            period=data.get("period"),
            total_invoices=summary.get("total_invoices", 0),
            paid=summary.get("paid", 0),
            pending=summary.get("pending", 0),
            failed=summary.get("failed", 0),
            disputes=summary.get("disputes", 0),
            total_rub=volume.get("total_rub", 0),
            total_usdt=volume.get("total_usdt", 0),
            conversion_rate=data.get("conversion_rate", 0)
        )


class BitarbitrClient:
    """
    Клиент для работы с BITARBITR Invoice API v1
    
    Args:
        api_key: API ключ мерчанта
        secret_key: Secret ключ для подписи запросов
        merchant_id: ID мерчанта в системе
        base_url: Базовый URL API (по умолчанию production)
        timeout: Таймаут запросов в секундах
    """
    
    DEFAULT_BASE_URL = "https://bitarbitr.org/api/v1/invoice"
    
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        merchant_id: str,
        base_url: str = None,
        timeout: int = 30
    ):
        self.api_key = api_key
        self.secret_key = secret_key
        self.merchant_id = merchant_id
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json"
        })
    
    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """Генерация HMAC-SHA256 подписи"""
        sign_params = {k: v for k, v in params.items() if k != 'sign' and v is not None}
        sorted_params = sorted(sign_params.items())
        sign_string = '&'.join(f"{k}={v}" for k, v in sorted_params)
        sign_string += self.secret_key
        
        return hmac.new(
            self.secret_key.encode('utf-8'),
            sign_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _handle_response(self, response: requests.Response) -> dict:
        """Обработка ответа API"""
        try:
            data = response.json()
        except:
            raise BitarbitrError("PARSE_ERROR", f"Failed to parse response: {response.text}", response.status_code)
        
        if response.status_code == 429:
            raise RateLimitError(data.get("message", "Rate limit exceeded"))
        
        if response.status_code == 401:
            raise AuthenticationError("INVALID_API_KEY", data.get("message", "Invalid API key"), 401)
        
        if response.status_code == 400:
            detail = data.get("detail", data)
            if isinstance(detail, dict):
                raise BitarbitrError(detail.get("code", "ERROR"), detail.get("message", str(detail)), 400)
            raise BitarbitrError("BAD_REQUEST", str(detail), 400)
        
        if response.status_code >= 400:
            raise BitarbitrError("API_ERROR", str(data), response.status_code)
        
        return data
    
    def create_invoice(
        self,
        order_id: str,
        amount: float,
        callback_url: str,
        user_id: str = None,
        currency: str = "RUB",
        description: str = None
    ) -> Invoice:
        """
        Создание инвойса на оплату
        
        Args:
            order_id: Уникальный ID заказа в вашей системе
            amount: Сумма в рублях (мин. 100)
            callback_url: URL для callback уведомлений
            user_id: ID пользователя в вашей системе (опционально)
            currency: Валюта (по умолчанию RUB)
            description: Описание платежа (опционально)
        
        Returns:
            Invoice: Созданный инвойс с реквизитами
        
        Raises:
            BitarbitrError: При ошибке API
            RateLimitError: При превышении лимита запросов
        """
        params = {
            "merchant_id": self.merchant_id,
            "order_id": order_id,
            "amount": amount,
            "currency": currency,
            "user_id": user_id,
            "callback_url": callback_url,
            "description": description
        }
        params["sign"] = self._generate_signature(params)
        
        response = self._session.post(
            f"{self.base_url}/create",
            json=params,
            timeout=self.timeout
        )
        
        data = self._handle_response(response)
        return Invoice.from_response(data)
    
    def get_status(
        self,
        order_id: str = None,
        payment_id: str = None
    ) -> InvoiceStatus:
        """
        Проверка статуса платежа
        
        Args:
            order_id: ID заказа в вашей системе
            payment_id: ID платежа в нашей системе
            
        Требуется order_id или payment_id
        
        Returns:
            InvoiceStatus: Статус платежа
        """
        if not order_id and not payment_id:
            raise ValueError("Требуется order_id или payment_id")
        
        params = {"merchant_id": self.merchant_id}
        if order_id:
            params["order_id"] = order_id
        if payment_id:
            params["payment_id"] = payment_id
        params["sign"] = self._generate_signature(params)
        
        response = self._session.get(
            f"{self.base_url}/status",
            params=params,
            timeout=self.timeout
        )
        
        data = self._handle_response(response)
        return InvoiceStatus.from_response(data["data"])
    
    def get_transactions(
        self,
        status: str = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Получение списка транзакций
        
        Args:
            status: Фильтр по статусу (active, completed, dispute)
            limit: Количество записей (макс. 100)
            offset: Смещение для пагинации
        
        Returns:
            dict: {"transactions": [...], "total": int, "limit": int, "offset": int}
        """
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        
        response = self._session.get(
            f"{self.base_url}/transactions",
            params=params,
            timeout=self.timeout
        )
        
        data = self._handle_response(response)
        return data["data"]
    
    def get_stats(self, period: str = "today") -> Stats:
        """
        Получение статистики
        
        Args:
            period: Период (today, week, month, all)
        
        Returns:
            Stats: Статистика по периоду
        """
        response = self._session.get(
            f"{self.base_url}/stats",
            params={"period": period},
            timeout=self.timeout
        )
        
        data = self._handle_response(response)
        return Stats.from_response(data["data"])
    
    def verify_callback(self, payload: Dict[str, Any]) -> bool:
        """
        Проверка подписи входящего callback
        
        Args:
            payload: Данные callback запроса
        
        Returns:
            bool: True если подпись валидна
        """
        provided_sign = payload.get("sign", "")
        expected_sign = self._generate_signature(payload)
        return hmac.compare_digest(expected_sign.lower(), provided_sign.lower())


# Пример использования
if __name__ == "__main__":
    # Демонстрация
    client = BitarbitrClient(
        api_key="sk_live_50deadc48545483d500e5d30e354510f23c98a1980072302",
        secret_key="31e6f7b773d9732a641992717f0f8f0e29593131cc1b0419fb6872ab3616edb7",
        merchant_id="mrc_20260124_A66181"
    )
    
    # Создание инвойса
    print("=== Создание инвойса ===")
    try:
        invoice = client.create_invoice(
            order_id=f"SDK_TEST_{datetime.now().strftime('%H%M%S')}",
            amount=1000.00,
            callback_url="https://mysite.com/callback"
        )
        print(f"Payment ID: {invoice.payment_id}")
        print(f"Payment URL: {invoice.payment_url}")
        print(f"Card: {invoice.details.get('card_number')}")
        
        # Проверка статуса
        print("\n=== Проверка статуса ===")
        status = client.get_status(payment_id=invoice.payment_id)
        print(f"Status: {status.status}")
        print(f"Amount: {status.amount} RUB")
        
    except BitarbitrError as e:
        print(f"Error: {e}")
    
    # Статистика
    print("\n=== Статистика ===")
    try:
        stats = client.get_stats("today")
        print(f"Total invoices: {stats.total_invoices}")
        print(f"Paid: {stats.paid}")
        print(f"Volume: {stats.total_rub} RUB")
        print(f"Conversion: {stats.conversion_rate}%")
    except BitarbitrError as e:
        print(f"Error: {e}")
