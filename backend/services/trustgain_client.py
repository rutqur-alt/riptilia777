"""
TrustGain API Client - Strict implementation per https://docs.trustgain.io/

Two separate integrations:
1. NSPK (QR) - income operations via QR payment
2. TransGrant (CNG) - income operations via TransGrant

Authentication: Authorization: Token <api_token>
Signature (for payouts): X-Authorization-Timestamp + X-Authorization-Content-SHA256
Webhook verification: Payments-Signature header with t=timestamp,s=signature
"""
import httpx
import hmac
import hashlib
import json
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 5


class TrustGainClient:
    """
    Client for TrustGain API.
    Per docs: https://docs.trustgain.io/
    
    Auth: Authorization: Token <token>
    API URL: https://api.trustgain.io (prod) or https://stagingapi.trustgain.io (staging)
    """

    def __init__(self, api_url: str, api_key: str, secret_key: str = ""):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.secret_key = secret_key
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=DEFAULT_TIMEOUT,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Token {self.api_key}",
                }
            )
        return self._client

    def _generate_signature(self, timestamp: str, body: str) -> str:
        """
        Generate HMAC-SHA256 signature per docs:
        hmacSha256(secret_key, timestamp + "." + request_body)
        """
        payload = f"{timestamp}.{body}"
        return hmac.new(
            key=self.secret_key.encode("utf-8"),
            msg=payload.encode("utf-8"),
            digestmod=hashlib.sha256
        ).hexdigest()

    @staticmethod
    def verify_webhook_signature(secret_key: str, signature_header: str, body: str) -> bool:
        """
        Verify webhook signature from TrustGain.
        Header format: Payments-Signature: "t=<timestamp>,s=<signature>"
        Signature: hmacSha256(webhook_secret, timestamp + "." + body)
        """
        try:
            parts = {}
            for part in signature_header.split(","):
                k, v = part.strip().split("=", 1)
                parts[k] = v
            
            timestamp = parts.get("t", "")
            provided_sig = parts.get("s", "")
            
            if not timestamp or not provided_sig:
                return False
            
            expected = hmac.new(
                key=secret_key.encode("utf-8"),
                msg=f"{timestamp}.{body}".encode("utf-8"),
                digestmod=hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(expected, provided_sig)
        except Exception as e:
            logger.error(f"[TrustGain] Webhook signature verification error: {e}")
            return False

    async def _request(
        self, method: str, path: str,
        data: dict = None,
        sign: bool = False
    ) -> Dict[str, Any]:
        """
        Make API request with retry logic.
        sign=True adds X-Authorization-Timestamp and X-Authorization-Content-SHA256 headers (required for payouts).
        """
        url = f"{self.api_url}{path}"
        body = json.dumps(data, separators=(',', ':')) if data else ""
        
        headers = {}
        if sign and self.secret_key:
            timestamp = str(int(datetime.now(timezone.utc).timestamp()))
            signature = self._generate_signature(timestamp, body)
            headers["X-Authorization-Timestamp"] = timestamp
            headers["X-Authorization-Content-SHA256"] = signature

        client = self._get_client()
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers)
                elif method.upper() == "POST":
                    response = await client.post(url, headers=headers, content=body if body else None)
                elif method.upper() == "PUT":
                    response = await client.put(url, headers=headers, content=body if body else None)
                elif method.upper() == "DELETE":
                    response = await client.delete(url, headers=headers)
                else:
                    response = await client.request(method, url, headers=headers, content=body if body else None)

                if response.status_code >= 500:
                    last_error = f"Server error {response.status_code}: {response.text}"
                    logger.warning(f"[TrustGain] Attempt {attempt+1}/{MAX_RETRIES} failed: {last_error}")
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY)
                    continue

                result = response.json() if response.text else {}
                if response.status_code >= 400:
                    logger.error(f"[TrustGain] API error {response.status_code} on {method} {path}: {result}")
                    return {"success": False, "status_code": response.status_code, "error": result}

                return {"success": True, "status_code": response.status_code, "data": result}

            except httpx.TimeoutException as e:
                last_error = f"Timeout: {e}"
                logger.warning(f"[TrustGain] Attempt {attempt+1}/{MAX_RETRIES} timeout on {path}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
            except Exception as e:
                last_error = f"Error: {e}"
                logger.error(f"[TrustGain] Attempt {attempt+1}/{MAX_RETRIES} error on {path}: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)

        return {"success": False, "error": last_error, "status_code": 0}

    # ==================== Gateways ====================

    async def get_gateways(self, filters: dict = None) -> Dict[str, Any]:
        """
        POST /gateways/filter
        Get list of available gateways (payment methods).
        Empty filter = all gateways.
        """
        return await self._request("POST", "/gateways/filter", data=filters or {})

    # ==================== Currencies ====================

    async def get_currencies(self) -> Dict[str, Any]:
        """POST /currencies/filter - Get available currencies"""
        return await self._request("POST", "/currencies/filter", data={})

    async def get_currency_rates(self) -> Dict[str, Any]:
        """POST /currency_rates/filter - Get exchange rates"""
        return await self._request("POST", "/currency_rates/filter", data={})

    # ==================== Operations (Income) ====================

    async def create_income_operation(
        self,
        amount: str,
        merchant_id: str,
        gateway_id: str,
        client_id: str,
        client_ip: str = "127.0.0.1",
        idempotency_key: str = None,
        webhook_url: str = None,
        back_url: str = None,
        success_redirect_url: str = None,
        failure_redirect_url: str = None,
        requisite_number: str = None,
    ) -> Dict[str, Any]:
        """
        POST /operations
        Create income (deposit/cashin) operation.
        Per docs: kind=income, amount, merchant_id, gateway_id, client_id are required.
        """
        if not idempotency_key:
            idempotency_key = str(uuid.uuid4())

        payload = {
            "kind": "income",
            "amount": str(amount),
            "idempotency_key": idempotency_key,
            "merchant_id": merchant_id,
            "gateway_id": gateway_id,
            "client_id": str(client_id),
            "client_ip": client_ip,
        }
        if webhook_url:
            payload["webhook_url"] = webhook_url
        if back_url:
            payload["back_url"] = back_url
        if success_redirect_url:
            payload["success_redirect_url"] = success_redirect_url
        if failure_redirect_url:
            payload["failure_redirect_url"] = failure_redirect_url
        if requisite_number:
            payload["requisite_number"] = requisite_number

        result = await self._request("POST", "/operations", data=payload)
        if result.get("success"):
            op_id = result.get("data", {}).get("id", "unknown")
            logger.info(f"[TrustGain] Income operation created: {op_id}")
        else:
            logger.error(f"[TrustGain] Failed to create income operation: {result.get('error')}")
        return result

    # ==================== Operations (Payout) ====================

    async def create_payout_operation(
        self,
        amount: str,
        merchant_id: str,
        gateway_id: str,
        client_id: str,
        payout_requisite: dict,
        idempotency_key: str = None,
        webhook_url: str = None,
        operation_action: str = "check",
    ) -> Dict[str, Any]:
        """
        POST /operations/payout
        Create payout operation. Requires signature headers.
        Per docs: payout_requisite can contain card_number, number (IBAN/phone), sbp, or qr_payload.
        """
        if not idempotency_key:
            idempotency_key = str(uuid.uuid4())

        payload = {
            "amount": str(amount),
            "merchant_id": merchant_id,
            "idempotency_key": idempotency_key,
            "gateway_id": gateway_id,
            "client_id": str(client_id),
            "operation_action": operation_action,
            "payout_requisite": payout_requisite,
        }
        if webhook_url:
            payload["webhook_url"] = webhook_url

        result = await self._request("POST", "/operations/payout", data=payload, sign=True)
        if result.get("success"):
            op_id = result.get("data", {}).get("id", "unknown")
            logger.info(f"[TrustGain] Payout operation created: {op_id}")
        else:
            logger.error(f"[TrustGain] Failed to create payout: {result.get('error')}")
        return result

    async def process_payout(self, operation_id: str) -> Dict[str, Any]:
        """
        PUT /operations/{operation_id}/process_payout
        Process a payout that is in 'checking' status. Requires signature.
        """
        return await self._request("PUT", f"/operations/{operation_id}/process_payout", sign=True)

    # ==================== Operation Status ====================

    async def get_operation(self, operation_id: str) -> Dict[str, Any]:
        """GET /operations/{operation_id} - Get operation status"""
        return await self._request("GET", f"/operations/{operation_id}")

    async def filter_operations(self, filters: dict = None) -> Dict[str, Any]:
        """POST /operations/filter - Filter operations"""
        return await self._request("POST", "/operations/filter", data=filters or {})

    # ==================== Cashin (payment confirmation) ====================

    async def confirm_payment(self, operation_id: str, payment_reference: str) -> Dict[str, Any]:
        """
        POST /cashins/{operation_id}/pay
        Confirm payment with bank transaction ID.
        """
        return await self._request("POST", f"/cashins/{operation_id}/pay", data={
            "payment_reference": payment_reference
        })

    # ==================== Disputes ====================

    async def create_dispute(
        self, operation_id: str, amount: str, merchant_id: str, comment: str
    ) -> Dict[str, Any]:
        """POST /disputes - Create a dispute"""
        return await self._request("POST", "/disputes", data={
            "dispute": {
                "operation_id": operation_id,
                "amount": str(amount),
                "merchant_id": merchant_id,
                "comment": comment,
            }
        })

    async def filter_disputes(self, filters: dict = None) -> Dict[str, Any]:
        """POST /disputes/filter - Filter disputes"""
        return await self._request("POST", "/disputes/filter", data=filters or {})

    # ==================== Bank Codes (NSPK) ====================

    async def get_bank_codes(self) -> Dict[str, Any]:
        """POST /bank_codes/filter - Get NSPK bank identifiers for SBP"""
        return await self._request("POST", "/bank_codes/filter", data={})

    # ==================== Provider Payment Requisites ====================

    async def get_appropriate_requisites(self, merchant_id: str, gateway_id: str) -> Dict[str, Any]:
        """POST /provider_payment_requisites/appropriate_for_merchant"""
        return await self._request("POST", "/provider_payment_requisites/appropriate_for_merchant", data={
            "merchant_id": merchant_id,
            "gateway_id": gateway_id,
        })

    # ==================== Health Check ====================

    async def check_health(self) -> bool:
        """Check if TrustGain API is reachable by fetching currencies"""
        try:
            result = await self._request("POST", "/currencies/filter", data={})
            return result.get("success", False)
        except Exception as e:
            logger.error(f"[TrustGain] Health check failed: {e}")
            return False

    # ==================== Access Tokens ====================

    async def create_access_token(self, lifespan: int = 90, ip_whitelist: list = None) -> Dict[str, Any]:
        """POST /access_tokens - Create a new access token"""
        payload = {"lifespan": lifespan}
        if ip_whitelist:
            payload["ip_addresses_whitelist"] = ip_whitelist
        return await self._request("POST", "/access_tokens", data=payload)

    async def revoke_access_token(self, token_id: str) -> Dict[str, Any]:
        """DELETE /access_tokens/{token_id} - Revoke an access token"""
        return await self._request("DELETE", f"/access_tokens/{token_id}")

    # ==================== Cleanup ====================

    async def close(self):
        """Close the HTTP client"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
