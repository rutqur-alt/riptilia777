"""
TON Blockchain Service - USDT Jetton operations
Handles deposits monitoring and withdrawals via TON network
"""
import logging
import secrets
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# USDT Contract on TON mainnet
USDT_CONTRACT = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"


class TonService:
    """Service for TON blockchain operations"""
    
    def __init__(self, db):
        self.db = db
        self.processed_tx_hashes = set()
    
    async def get_config(self) -> Optional[Dict]:
        """Get hot wallet configuration from database"""
        config = await self.db.platform_settings.find_one(
            {"type": "auto_withdraw"}, 
            {"_id": 0}
        )
        return config
    
    async def get_wallet_balance(self, wallet_address: str = None) -> float:
        """Get USDT balance of hot wallet via TonAPI"""
        try:
            config = await self.get_config()
            if not config and not wallet_address:
                return 0.0
            
            address = wallet_address or config.get("wallet_address")
            if not address:
                return 0.0
            
            # Convert to UQ format
            from pytoniq_core import Address
            try:
                addr = Address(address)
                api_address = addr.to_str(is_bounceable=False)
            except:
                api_address = address
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"https://tonapi.io/v2/accounts/{api_address}/jettons"
                )
                
                if response.status_code != 200:
                    return 0.0
                
                data = response.json()
                for b in data.get("balances", []):
                    jetton = b.get("jetton", {})
                    symbol = jetton.get("symbol", "").upper()
                    if symbol == "USD₮" or "USDT" in symbol:
                        return int(b.get("balance", "0")) / 1_000_000
                
                return 0.0
        except Exception as e:
            logger.error(f"Error getting wallet balance: {e}")
            return 0.0
    
    async def send_usdt(
        self, 
        to_address: str, 
        amount: float, 
        withdrawal_id: str = ""
    ) -> Dict[str, Any]:
        """
        Send USDT to specified address via TON network
        Uses TonAPI for Jetton wallet lookup and tonutils for sending
        """
        config = await self.get_config()
        
        if not config:
            return {"success": False, "error": "Автовывод не настроен"}
        
        seed_phrase = config.get("seed_phrase")
        wallet_address = config.get("wallet_address")
        toncenter_api_key = config.get("toncenter_api_key", "")
        
        if not seed_phrase:
            return {"success": False, "error": "Seed phrase не настроен"}
        
        if not wallet_address:
            return {"success": False, "error": "Адрес кошелька не настроен"}
        
        if not toncenter_api_key:
            return {"success": False, "error": "Toncenter API ключ не настроен"}
        
        try:
            from tonutils.client import ToncenterV3Client
            from tonutils.wallet import WalletV5R1
            from pytoniq_core import Address, begin_cell
            
            # Create Toncenter client
            ton_client = ToncenterV3Client(
                api_key=toncenter_api_key,
                is_testnet=False,
                rps=5
            )
            
            # Create wallet from seed phrase
            mnemonic_list = seed_phrase.strip().split()
            
            if len(mnemonic_list) != 24:
                return {
                    "success": False, 
                    "error": f"Неверный seed phrase: ожидается 24 слова, получено {len(mnemonic_list)}"
                }
            
            # WalletV5R1.from_mnemonic - SYNC function
            wallet, public_key, private_key, _ = WalletV5R1.from_mnemonic(
                client=ton_client,
                mnemonic=mnemonic_list
            )
            
            wallet_addr_uq = wallet.address.to_str(is_bounceable=False)
            logger.info(f"Wallet loaded: {wallet_addr_uq}")
            
            # Get Jetton Wallet address via TonAPI
            async with httpx.AsyncClient(timeout=30.0) as http_client:
                response = await http_client.get(
                    f"https://tonapi.io/v2/accounts/{wallet_addr_uq}/jettons"
                )
                
                if response.status_code != 200:
                    return {"success": False, "error": f"TonAPI error: {response.status_code}"}
                
                data = response.json()
                balances = data.get("balances", [])
                
                # Find USDT
                sender_jetton_wallet = None
                balance = 0
                for b in balances:
                    jetton = b.get("jetton", {})
                    symbol = jetton.get("symbol", "").upper()
                    name = jetton.get("name", "").upper()
                    if symbol == "USD₮" or "USDT" in symbol or "TETHER" in name:
                        wallet_info = b.get("wallet_address", {})
                        sender_jetton_wallet = wallet_info.get("address")
                        balance = int(b.get("balance", "0"))
                        break
                
                if not sender_jetton_wallet:
                    return {
                        "success": False, 
                        "error": "USDT кошелёк не найден. Убедитесь что на кошельке есть USDT."
                    }
                
                hot_balance = balance / 1_000_000
                logger.info(f"Sender Jetton Wallet: {sender_jetton_wallet}, Balance: {hot_balance} USDT")
                
                # Check balance
                amount_nano = int(amount * 1_000_000)
                if balance < amount_nano:
                    return {
                        "success": False,
                        "error": f"Недостаточно USDT. Баланс: {hot_balance:.2f}, требуется: {amount:.2f}",
                        "hot_wallet_balance": hot_balance,
                        "required": amount
                    }
            
            # Build Transfer Body (TEP-74 standard)
            destination_addr = Address(to_address)
            sender_jetton_addr = Address(sender_jetton_wallet)
            
            query_id = secrets.randbits(64)
            
            transfer_body = (
                begin_cell()
                .store_uint(0xf8a7ea5, 32)   # op::transfer
                .store_uint(query_id, 64)     # query_id
                .store_coins(amount_nano)     # amount
                .store_address(destination_addr)   # destination
                .store_address(wallet.address)     # response_destination
                .store_bit(0)                 # no custom_payload
                .store_coins(1)               # forward_ton_amount (1 nanoton)
                .store_bit(0)                 # no forward_payload
                .end_cell()
            )
            
            # Send to our Jetton Wallet (not master contract!)
            tx_hash = await wallet.transfer(
                destination=sender_jetton_addr,
                amount=0.05,  # TON for gas
                body=transfer_body
            )
            
            tx_hash_str = str(tx_hash) if tx_hash else "pending"
            logger.info(f"✅ USDT transfer sent! TX: {tx_hash_str}")
            
            return {
                "success": True,
                "tx_hash": tx_hash_str,
                "amount_usdt": amount,
                "to_address": to_address,
                "real_transaction": True
            }
            
        except ImportError as e:
            logger.error(f"Import error: {e}")
            return {"success": False, "error": f"Missing dependency: {str(e)}"}
        except Exception as e:
            logger.error(f"USDT transfer failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def check_incoming_transactions(self, wallet_address: str = None) -> List[Dict]:
        """
        Check incoming USDT Jetton transactions via TonAPI
        Returns list of new transactions
        """
        config = await self.get_config()
        address = wallet_address or (config.get("wallet_address") if config else None)
        usdt_contract = (config.get("usdt_contract") if config else None) or USDT_CONTRACT
        
        if not address:
            return []
        
        try:
            from pytoniq_core import Address
            try:
                addr = Address(address)
                api_address = addr.to_str(is_bounceable=False)
            except:
                api_address = address
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"https://tonapi.io/v2/accounts/{api_address}/jettons/{usdt_contract}/history",
                    params={"limit": 50}
                )
                
                if response.status_code != 200:
                    logger.warning(f"TonAPI error: {response.status_code}")
                    return []
                
                data = response.json()
                events = data.get("events", [])
                
                transactions = []
                
                for event in events:
                    event_id = event.get("event_id", "")
                    if not event_id:
                        continue
                    
                    tx_hash = event_id
                    
                    # Skip already processed
                    if tx_hash in self.processed_tx_hashes:
                        continue
                    
                    # Check database
                    existing = await self.db.usdt_deposits.find_one({"tx_hash": tx_hash})
                    if existing:
                        self.processed_tx_hashes.add(tx_hash)
                        continue
                    
                    existing_unident = await self.db.usdt_unidentified_deposits.find_one({"tx_hash": tx_hash})
                    if existing_unident:
                        self.processed_tx_hashes.add(tx_hash)
                        continue
                    
                    # Skip scam
                    if event.get("is_scam", False):
                        continue
                    
                    # Process actions
                    for action in event.get("actions", []):
                        if action.get("type") != "JettonTransfer":
                            continue
                        
                        transfer = action.get("JettonTransfer", {})
                        
                        # Check if incoming transfer
                        recipient = transfer.get("recipient", {})
                        recipient_address = recipient.get("address", "")
                        
                        is_incoming = False
                        try:
                            recv_addr = Address(recipient_address)
                            recv_uq = recv_addr.to_str(is_bounceable=False)
                            is_incoming = (recv_uq == api_address or recipient_address == address)
                        except:
                            is_incoming = recipient_address == address
                        
                        if not is_incoming:
                            continue
                        
                        # Amount (6 decimals)
                        amount_raw = transfer.get("amount", "0")
                        try:
                            amount_usdt = int(amount_raw) / 1_000_000
                        except:
                            amount_usdt = 0
                        
                        if amount_usdt <= 0:
                            continue
                        
                        # Comment
                        comment = transfer.get("comment", "") or ""
                        
                        # Sender
                        sender = transfer.get("sender", {})
                        sender_address = sender.get("address", "unknown")
                        
                        transactions.append({
                            "tx_hash": tx_hash,
                            "amount_usdt": amount_usdt,
                            "comment": comment.strip().upper(),
                            "sender": sender_address,
                            "timestamp": event.get("timestamp", 0)
                        })
                        
                        logger.info(f"Found USDT transfer: {amount_usdt} USDT, comment: '{comment}'")
                
                return transactions
                
        except (httpx.ConnectError, httpx.TimeoutException, OSError, ConnectionError) as e:
            logger.warning(f"Network error: {type(e).__name__}")
            return []
        except Exception as e:
            logger.error(f"Error checking transactions: {e}")
            return []
    
    async def process_deposit(self, tx: Dict) -> Dict:
        """
        Process incoming USDT transaction
        Match with deposit request by comment
        """
        tx_hash = tx.get("tx_hash")
        amount_usdt = tx.get("amount_usdt", 0)
        comment = tx.get("comment", "").strip()
        
        # Check duplicates
        if tx_hash in self.processed_tx_hashes:
            return {"skipped": True, "reason": "already_in_memory"}
        
        existing_deposit = await self.db.usdt_deposits.find_one({"tx_hash": tx_hash})
        if existing_deposit:
            self.processed_tx_hashes.add(tx_hash)
            return {"skipped": True, "reason": "already_credited"}
        
        existing_unident = await self.db.usdt_unidentified_deposits.find_one({"tx_hash": tx_hash})
        if existing_unident:
            self.processed_tx_hashes.add(tx_hash)
            return {"skipped": True, "reason": "already_unidentified"}
        
        # Generate unique ID helper
        def generate_id(prefix):
            return f"{prefix}{datetime.now().strftime('%Y%m%d')}_{secrets.token_hex(3).upper()}"
        
        if not comment or amount_usdt <= 0:
            # Unidentified deposit
            unidentified = {
                "id": generate_id("uid_"),
                "tx_hash": tx_hash,
                "amount_usdt": amount_usdt,
                "comment": comment,
                "sender": tx.get("sender"),
                "status": "unidentified",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await self.db.usdt_unidentified_deposits.insert_one(unidentified)
            self.processed_tx_hashes.add(tx_hash)
            logger.warning(f"Unidentified deposit: {amount_usdt} USDT, comment: '{comment}'")
            return {"unidentified": True, "tx_hash": tx_hash}
        
        # Find deposit request by comment
        deposit_request = await self.db.deposit_requests.find_one({
            "deposit_comment": comment,
            "status": "pending"
        }, {"_id": 0})
        
        if not deposit_request:
            # Try by request_id
            deposit_request = await self.db.deposit_requests.find_one({
                "request_id": comment,
                "status": "pending"
            }, {"_id": 0})
        
        if deposit_request:
            self.processed_tx_hashes.add(tx_hash)
            return {
                "deposit_request": deposit_request,
                "amount_usdt": amount_usdt,
                "tx_hash": tx_hash,
                "comment": comment
            }
        
        # No matching request - save as unidentified
        unidentified = {
            "id": generate_id("uid_"),
            "tx_hash": tx_hash,
            "amount_usdt": amount_usdt,
            "comment": comment,
            "sender": tx.get("sender"),
            "status": "unidentified",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await self.db.usdt_unidentified_deposits.insert_one(unidentified)
        self.processed_tx_hashes.add(tx_hash)
        logger.warning(f"No matching deposit request for comment: '{comment}', amount: {amount_usdt} USDT")
        
        return {"unidentified": True, "tx_hash": tx_hash, "comment": comment}


# Singleton instance (initialized with db in server.py)
ton_service: Optional[TonService] = None


def init_ton_service(db):
    """Initialize TON service with database connection"""
    global ton_service
    ton_service = TonService(db)
    return ton_service


def get_ton_service() -> Optional[TonService]:
    """Get TON service instance"""
    return ton_service
