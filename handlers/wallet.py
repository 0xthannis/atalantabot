"""
Wallet Handler
Handles wallet connections, WalletConnect integration, and transaction signing
"""

import asyncio
import logging
import json
import uuid
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from config import Config, ERROR_MESSAGES, SUCCESS_MESSAGES
from database import Database

logger = logging.getLogger(__name__)

@dataclass
class WalletConnection:
    """Wallet connection data"""
    user_id: int
    wallet_address: str
    connection_id: str
    created_at: datetime
    is_active: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'user_id': self.user_id,
            'wallet_address': self.wallet_address,
            'connection_id': self.connection_id,
            'created_at': self.created_at.isoformat(),
            'is_active': self.is_active
        }

class WalletHandler:
    """Handles wallet connections and transaction signing"""
    
    def __init__(self, database: Database):
        self.database = database
        
        # Active connections
        self.active_connections: Dict[str, WalletConnection] = {}
        self.pending_connections: Dict[str, Dict[str, Any]] = {}
        
        # WalletConnect settings
        self.walletconnect_project_id = Config.WALLETCONNECT_PROJECT_ID
        self.max_connections_per_user = Config.MAX_WALLET_CONNECTIONS
        
        # Transaction signing
        self.pending_signatures: Dict[str, Dict[str, Any]] = {}
        self.signature_timeout = 300  # 5 minutes
    
    async def initiate_walletconnect(self, user_id: int) -> Optional[str]:
        """Initiate WalletConnect connection"""
        try:
            # Generate connection URI
            connection_id = str(uuid.uuid4())
            
            # In a real implementation, you would:
            # 1. Initialize WalletConnect client
            # 2. Generate connection URI
            # 3. Create QR code
            # 4. Wait for user approval
            
            # For now, simulate the process
            connection_uri = f"wc:{connection_id}@2?relay-protocol=irn&symKey={uuid.uuid4().hex}&projectId={self.walletconnect_project_id}"
            
            # Store pending connection
            self.pending_connections[connection_id] = {
                'user_id': user_id,
                'connection_uri': connection_uri,
                'created_at': datetime.now(timezone.utc),
                'method': 'walletconnect'
            }
            
            logger.info(f"Initiated WalletConnect for user {user_id}: {connection_id}")
            return connection_uri
            
        except Exception as e:
            logger.error(f"Error initiating WalletConnect: {e}")
            return None
    
    async def create_qr_connection(self, user_id: int) -> Optional[str]:
        """Create QR code connection"""
        try:
            connection_id = str(uuid.uuid4())
            
            # Generate QR code data
            qr_data = {
                'type': 'wallet_connection',
                'user_id': user_id,
                'connection_id': connection_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'bot_name': 'AtalantaBot'
            }
            
            # Store pending connection
            self.pending_connections[connection_id] = {
                'user_id': user_id,
                'qr_data': qr_data,
                'created_at': datetime.now(timezone.utc),
                'method': 'qr_code'
            }
            
            logger.info(f"Created QR connection for user {user_id}: {connection_id}")
            return connection_id
            
        except Exception as e:
            logger.error(f"Error creating QR connection: {e}")
            return None
    
    async def complete_wallet_connection(self, connection_id: str, wallet_address: str, 
                                      signature: Optional[str] = None) -> bool:
        """Complete wallet connection process"""
        try:
            # Check if connection exists
            if connection_id not in self.pending_connections:
                logger.warning(f"Connection not found: {connection_id}")
                return False
            
            pending = self.pending_connections[connection_id]
            user_id = pending['user_id']
            
            # Validate wallet address
            if not self._is_valid_address(wallet_address):
                logger.error(f"Invalid wallet address: {wallet_address}")
                return False
            
            # Check user connection limit
            user_connections = [
                conn for conn in self.active_connections.values() 
                if conn.user_id == user_id and conn.is_active
            ]
            
            if len(user_connections) >= self.max_connections_per_user:
                logger.warning(f"User {user_id} exceeded connection limit")
                return False
            
            # Create active connection
            connection = WalletConnection(
                user_id=user_id,
                wallet_address=wallet_address,
                connection_id=connection_id,
                created_at=datetime.now(timezone.utc)
            )
            
            # Store active connection
            self.active_connections[connection_id] = connection
            
            # Update user in database
            db_user = await self.database.get_user(user_id)
            if db_user:
                db_user.wallet_address = wallet_address
                db_user.last_active = datetime.now(timezone.utc)
                await self.database.update_user(db_user)
            
            # Remove from pending
            del self.pending_connections[connection_id]
            
            logger.info(f"Wallet connected for user {user_id}: {wallet_address}")
            return True
            
        except Exception as e:
            logger.error(f"Error completing wallet connection: {e}")
            return False
    
    async def disconnect_wallet(self, user_id: int, wallet_address: str) -> bool:
        """Disconnect wallet"""
        try:
            # Find and remove active connections
            connections_to_remove = [
                conn_id for conn_id, conn in self.active_connections.items()
                if conn.user_id == user_id and conn.wallet_address == wallet_address
            ]
            
            for conn_id in connections_to_remove:
                self.active_connections[conn_id].is_active = False
                del self.active_connections[conn_id]
            
            # Update user in database
            db_user = await self.database.get_user(user_id)
            if db_user and db_user.wallet_address == wallet_address:
                db_user.wallet_address = None
                await self.database.update_user(db_user)
            
            logger.info(f"Wallet disconnected for user {user_id}: {wallet_address}")
            return True
            
        except Exception as e:
            logger.error(f"Error disconnecting wallet: {e}")
            return False
    
    async def prepare_transaction_for_signing(self, user_id: int, transaction_data: Dict[str, Any]) -> Optional[str]:
        """Prepare transaction for user signature"""
        try:
            # Check if user has connected wallet
            user_connection = self._get_user_connection(user_id)
            if not user_connection:
                logger.error(f"No wallet connected for user {user_id}")
                return None
            
            # Generate signature request ID
            signature_id = str(uuid.uuid4())
            
            # Prepare EIP-712 typed data (if applicable)
            typed_data = self._create_eip712_data(transaction_data)
            
            # Store pending signature
            self.pending_signatures[signature_id] = {
                'user_id': user_id,
                'wallet_address': user_connection.wallet_address,
                'transaction_data': transaction_data,
                'typed_data': typed_data,
                'created_at': datetime.now(timezone.utc),
                'expires_at': datetime.now(timezone.utc).timestamp() + self.signature_timeout
            }
            
            logger.info(f"Prepared transaction for signing: {signature_id}")
            return signature_id
            
        except Exception as e:
            logger.error(f"Error preparing transaction for signing: {e}")
            return None
    
    async def sign_transaction(self, signature_id: str, signature: str) -> Optional[str]:
        """Process signed transaction"""
        try:
            # Check if signature request exists
            if signature_id not in self.pending_signatures:
                logger.error(f"Signature request not found: {signature_id}")
                return None
            
            pending = self.pending_signatures[signature_id]
            
            # Check if expired
            if datetime.now(timezone.utc).timestamp() > pending['expires_at']:
                logger.error(f"Signature request expired: {signature_id}")
                del self.pending_signatures[signature_id]
                return None
            
            # Verify signature (simplified - in production, verify against the typed data)
            if not self._verify_signature(pending['wallet_address'], pending['typed_data'], signature):
                logger.error(f"Invalid signature: {signature_id}")
                return None
            
            # Build signed transaction
            signed_tx = self._build_signed_transaction(pending['transaction_data'], signature)
            
            # Remove from pending
            del self.pending_signatures[signature_id]
            
            logger.info(f"Transaction signed successfully: {signature_id}")
            return signed_tx
            
        except Exception as e:
            logger.error(f"Error signing transaction: {e}")
            return None
    
    def _get_user_connection(self, user_id: int) -> Optional[WalletConnection]:
        """Get active wallet connection for user"""
        for connection in self.active_connections.values():
            if connection.user_id == user_id and connection.is_active:
                return connection
        return None
    
    def _is_valid_address(self, address: str) -> bool:
        """Check if address is valid Ethereum address"""
        try:
            return len(address) == 42 and address.startswith('0x')
        except:
            return False
    
    def _create_eip712_data(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create EIP-712 typed data for transaction"""
        # This is a simplified EIP-712 structure
        # In production, you'd create proper domain and typed data
        
        typed_data = {
            'types': {
                'EIP712Domain': [
                    {'name': 'name', 'type': 'string'},
                    {'name': 'version', 'type': 'string'},
                    {'name': 'chainId', 'type': 'uint256'},
                    {'name': 'verifyingContract', 'type': 'address'}
                ],
                'Transaction': [
                    {'name': 'to', 'type': 'address'},
                    {'name': 'value', 'type': 'uint256'},
                    {'name': 'data', 'type': 'bytes'}
                ]
            },
            'primaryType': 'Transaction',
            'domain': {
                'name': 'Atalanta Bot',
                'version': '1',
                'chainId': Config.CHAIN_ID,
                'verifyingContract': transaction_data.get('to', '0x0000000000000000000000000000000000000000')
            },
            'message': {
                'to': transaction_data.get('to', ''),
                'value': str(transaction_data.get('value', 0)),
                'data': transaction_data.get('data', '0x')
            }
        }
        
        return typed_data
    
    def _verify_signature(self, address: str, typed_data: Dict[str, Any], signature: str) -> bool:
        """Verify EIP-712 signature"""
        # In production, you'd use eth_account to verify the signature
        # For now, just check basic format
        try:
            return len(signature) == 132 and signature.startswith('0x')
        except:
            return False
    
    def _build_signed_transaction(self, transaction_data: Dict[str, Any], signature: str) -> str:
        """Build signed transaction"""
        # In production, you'd properly serialize the transaction with signature
        # For now, return a placeholder
        return f"0x{transaction_data.get('to', '')}{signature[2:]}"
    
    async def get_connection_status(self, user_id: int) -> Dict[str, Any]:
        """Get wallet connection status for user"""
        connection = self._get_user_connection(user_id)
        
        if connection:
            return {
                'connected': True,
                'wallet_address': connection.wallet_address,
                'connection_id': connection.connection_id,
                'connected_at': connection.created_at.isoformat()
            }
        else:
            return {
                'connected': False,
                'wallet_address': None,
                'connection_id': None,
                'connected_at': None
            }
    
    async def get_pending_connections(self, user_id: int) -> List[Dict[str, Any]]:
        """Get pending connections for user"""
        pending = []
        for conn_id, conn_data in self.pending_connections.items():
            if conn_data['user_id'] == user_id:
                pending.append({
                    'connection_id': conn_id,
                    'method': conn_data['method'],
                    'created_at': conn_data['created_at'].isoformat()
                })
        return pending
    
    async def cleanup_expired_connections(self) -> int:
        """Clean up expired pending connections"""
        expired = []
        current_time = datetime.now(timezone.utc)
        
        for conn_id, conn_data in self.pending_connections.items():
            if (current_time - conn_data['created_at']).total_seconds() > 600:  # 10 minutes
                expired.append(conn_id)
        
        for conn_id in expired:
            del self.pending_connections[conn_id]
        
        # Clean up expired signatures
        expired_sigs = []
        for sig_id, sig_data in self.pending_signatures.items():
            if current_time.timestamp() > sig_data['expires_at']:
                expired_sigs.append(sig_id)
        
        for sig_id in expired_sigs:
            del self.pending_signatures[sig_id]
        
        logger.info(f"Cleaned up {len(expired)} expired connections and {len(expired_sigs)} signatures")
        return len(expired) + len(expired_sigs)
    
    async def generate_walletconnect_qr(self, connection_uri: str) -> Optional[str]:
        """Generate QR code for WalletConnect URI"""
        try:
            # In production, you'd use a QR code library to generate actual QR code image
            # For now, return the URI as text
            return connection_uri
            
        except Exception as e:
            logger.error(f"Error generating QR code: {e}")
            return None
    
    def get_connection_info(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get connection information"""
        if connection_id in self.active_connections:
            return self.active_connections[connection_id].to_dict()
        elif connection_id in self.pending_connections:
            return self.pending_connections[connection_id]
        return None
    
    async def handle_walletconnect_callback(self, topic: str, message: Dict[str, Any]) -> bool:
        """Handle WalletConnect callback"""
        try:
            # In production, you'd handle actual WalletConnect events
            # For now, just log the callback
            logger.info(f"WalletConnect callback: {topic} - {message}")
            return True
            
        except Exception as e:
            logger.error(f"Error handling WalletConnect callback: {e}")
            return False
