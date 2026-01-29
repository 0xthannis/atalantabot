"""
Sniper Executor
Handles the execution of token sniping operations
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timezone
from web3 import Web3, AsyncWeb3
import json

from config import Config
from ..dex.kumbaya import KumbayaDEX
from ..database import Trade

logger = logging.getLogger(__name__)

@dataclass
class SnipeRequest:
    """Snipe request data"""
    user_id: int
    token_address: str
    amount_eth: float
    max_slippage_percent: float
    wallet_address: str
    request_time: datetime
    priority_fee: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'user_id': self.user_id,
            'token_address': self.token_address,
            'amount_eth': self.amount_eth,
            'max_slippage_percent': self.max_slippage_percent,
            'wallet_address': self.wallet_address,
            'request_time': self.request_time.isoformat(),
            'priority_fee': self.priority_fee
        }

@dataclass
class SnipeResult:
    """Snipe execution result"""
    success: bool
    transaction_hash: Optional[str]
    error_message: Optional[str]
    gas_used: Optional[int]
    gas_cost: Optional[float]
    token_amount_received: Optional[float]
    actual_slippage: Optional[float]
    execution_time: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'success': self.success,
            'transaction_hash': self.transaction_hash,
            'error_message': self.error_message,
            'gas_used': self.gas_used,
            'gas_cost': self.gas_cost,
            'token_amount_received': self.token_amount_received,
            'actual_slippage': self.actual_slippage,
            'execution_time': self.execution_time
        }

class SniperExecutor:
    """Handles the execution of token sniping operations"""
    
    def __init__(self, w3: Web3, async_w3: AsyncWeb3, kumbaya: KumbayaDEX, database):
        self.w3 = w3
        self.async_w3 = async_w3
        self.kumbaya = kumbaya
        self.database = database
        
        # Execution queue and state
        self.execution_queue: asyncio.Queue = asyncio.Queue()
        self.is_executing = False
        self.execution_task: Optional[asyncio.Task] = None
        
        # Snipe settings
        self.max_concurrent_snipes: int = 5
        self.max_gas_price: int = int(Config.MAX_GAS_PRICE)
        self.priority_fee_multiplier: float = 1.2
        
        # Active snipes tracking
        self.active_snipes: Dict[str, SnipeRequest] = {}
        self.snipe_results: Dict[str, SnipeResult] = {}
        
    async def start_executor(self) -> None:
        """Start the snipe executor"""
        if self.is_executing:
            logger.warning("Snipe executor already running")
            return
        
        self.is_executing = True
        self.execution_task = asyncio.create_task(self._execution_loop())
        logger.info("Started snipe executor")
    
    async def stop_executor(self) -> None:
        """Stop the snipe executor"""
        self.is_executing = False
        if self.execution_task:
            self.execution_task.cancel()
            try:
                await self.execution_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped snipe executor")
    
    async def _execution_loop(self) -> None:
        """Main execution loop"""
        while self.is_executing:
            try:
                # Wait for snipe request with timeout
                try:
                    snipe_request = await asyncio.wait_for(
                        self.execution_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Execute snipe
                await self._execute_snipe(snipe_request)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in execution loop: {e}")
                await asyncio.sleep(0.1)
    
    async def submit_snipe(self, snipe_request: SnipeRequest) -> str:
        """Submit a snipe request to the execution queue"""
        # Generate request ID
        request_id = f"snipe_{snipe_request.user_id}_{int(snipe_request.request_time.timestamp())}"
        
        # Add to active snipes
        self.active_snipes[request_id] = snipe_request
        
        # Submit to queue
        await self.execution_queue.put(snipe_request)
        
        logger.info(f"Submitted snipe request: {request_id}")
        return request_id
    
    async def _execute_snipe(self, snipe_request: SnipeRequest) -> SnipeResult:
        """Execute a single snipe operation"""
        start_time = datetime.now(timezone.utc)
        
        try:
            logger.info(f"Executing snipe for token {snipe_request.token_address}")
            
            # Pre-execution checks
            if not await self._pre_execution_checks(snipe_request):
                return SnipeResult(
                    success=False,
                    transaction_hash=None,
                    error_message="Pre-execution checks failed",
                    gas_used=None,
                    gas_cost=None,
                    token_amount_received=None,
                    actual_slippage=None,
                    execution_time=0
                )
            
            # Get token info
            token_info = await self.kumbaya.get_token_info(snipe_request.token_address)
            if not token_info:
                return SnipeResult(
                    success=False,
                    transaction_hash=None,
                    error_message="Failed to get token info",
                    gas_used=None,
                    gas_cost=None,
                    token_amount_received=None,
                    actual_slippage=None,
                    execution_time=0
                )
            
            # Build swap transaction
            amount_in_wei = int(snipe_request.amount_eth * 1e18)
            path = [Config.WETH_ADDRESS, snipe_request.token_address]
            
            # Calculate minimum output with slippage
            min_out = await self.kumbaya.calculate_slippage(
                amount_in_wei, path, snipe_request.max_slippage_percent
            )
            
            # Build transaction
            tx_data = self.kumbaya.build_swap_transaction(
                amount_in_wei, min_out, path, snipe_request.wallet_address
            )
            
            if not tx_data:
                return SnipeResult(
                    success=False,
                    transaction_hash=None,
                    error_message="Failed to build transaction",
                    gas_used=None,
                    gas_cost=None,
                    token_amount_received=None,
                    actual_slippage=None,
                    execution_time=0
                )
            
            # Estimate gas and adjust if needed
            gas_estimate = await self.async_w3.eth.estimate_gas(tx_data)
            gas_price = await self._get_optimal_gas_price()
            
            tx_data['gas'] = gas_estimate
            tx_data['gasPrice'] = gas_price
            
            # For security, we don't execute directly
            # Instead, we return the transaction data for user to sign
            # In a real implementation, you'd use WalletConnect or similar
            
            # Create pending trade record
            trade = Trade(
                id=None,
                user_id=snipe_request.user_id,
                token_address=snipe_request.token_address,
                token_symbol=token_info['symbol'],
                trade_type='snipe',
                amount_in=snipe_request.amount_eth,
                amount_out=0,  # Will be updated after execution
                token_amount=0,  # Will be updated after execution
                price_usd=None,
                gas_used=gas_estimate,
                gas_cost=gas_estimate * gas_price / 1e18,
                tx_hash="pending",
                status='pending',
                profit_loss=None,
                created_at=datetime.now(timezone.utc)
            )
            
            trade_id = await self.database.create_trade(trade)
            
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            # Return success with transaction data
            result = SnipeResult(
                success=True,
                transaction_hash=None,  # Will be set after user signs
                error_message=None,
                gas_used=gas_estimate,
                gas_cost=gas_estimate * gas_price / 1e18,
                token_amount_received=None,  # Will be calculated after execution
                actual_slippage=None,  # Will be calculated after execution
                execution_time=execution_time
            )
            
            # Store result
            self.snipe_results[f"snipe_{snipe_request.user_id}_{int(snipe_request.request_time.timestamp())}"] = result
            
            logger.info(f"Snipe transaction prepared for {token_info['symbol']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing snipe: {e}")
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            return SnipeResult(
                success=False,
                transaction_hash=None,
                error_message=str(e),
                gas_used=None,
                gas_cost=None,
                token_amount_received=None,
                actual_slippage=None,
                execution_time=execution_time
            )
    
    async def _pre_execution_checks(self, snipe_request: SnipeRequest) -> bool:
        """Perform pre-execution safety checks"""
        try:
            # Check if token has sufficient liquidity
            has_liquidity = await self.kumbaya.check_liquidity(
                snipe_request.token_address, 
                min_liquidity_eth=snipe_request.amount_eth * 0.5
            )
            if not has_liquidity:
                logger.warning(f"Insufficient liquidity for {snipe_request.token_address}")
                return False
            
            # Basic honeypot check
            honeypot_check = await self.kumbaya.simulate_honeypot(snipe_request.token_address)
            if honeypot_check.get('is_honeypot', False):
                logger.warning(f"Potential honeypot detected: {snipe_request.token_address}")
                return False
            
            # Check gas price
            current_gas_price = await self.async_w3.eth.gas_price
            if current_gas_price > self.max_gas_price:
                logger.warning(f"Gas price too high: {current_gas_price}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error in pre-execution checks: {e}")
            return False
    
    async def _get_optimal_gas_price(self) -> int:
        """Get optimal gas price for execution"""
        try:
            base_gas_price = await self.async_w3.eth.gas_price
            
            # Add priority fee for faster execution
            optimal_gas_price = int(base_gas_price * self.priority_fee_multiplier)
            
            # Cap at maximum
            optimal_gas_price = min(optimal_gas_price, self.max_gas_price)
            
            return optimal_gas_price
            
        except Exception as e:
            logger.error(f"Error getting optimal gas price: {e}")
            return int(1e10)  # 10 gwei fallback
    
    async def execute_transaction(self, signed_tx: str, user_id: int, token_address: str) -> Dict[str, Any]:
        """Execute a signed transaction"""
        try:
            # Send transaction
            tx_hash = await self.async_w3.eth.send_raw_transaction(signed_tx)
            
            # Wait for receipt
            receipt = await self.async_w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            
            if receipt.status == 1:
                # Transaction successful
                # Update trade record
                await self.database.update_trade_status(tx_hash.hex(), 'completed')
                
                # Calculate token amount received (simplified)
                # In production, you'd parse transaction logs for exact amounts
                
                return {
                    'success': True,
                    'tx_hash': tx_hash.hex(),
                    'gas_used': receipt.gasUsed,
                    'block_number': receipt.blockNumber
                }
            else:
                # Transaction failed
                await self.database.update_trade_status(tx_hash.hex(), 'failed')
                
                return {
                    'success': False,
                    'tx_hash': tx_hash.hex(),
                    'error': 'Transaction failed on-chain'
                }
                
        except Exception as e:
            logger.error(f"Error executing transaction: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_snipe_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a snipe request"""
        if request_id in self.snipe_results:
            result = self.snipe_results[request_id]
            return result.to_dict()
        
        return None
    
    async def cancel_snipe(self, request_id: str) -> bool:
        """Cancel a pending snipe request"""
        # This is a simplified implementation
        # In production, you'd need more sophisticated cancellation logic
        
        if request_id in self.active_snipes:
            del self.active_snipes[request_id]
            logger.info(f"Cancelled snipe request: {request_id}")
            return True
        
        return False
    
    async def get_active_snipes(self) -> List[Dict[str, Any]]:
        """Get all active snipe requests"""
        return [snipe.to_dict() for snipe in self.active_snipes.values()]
    
    async def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics"""
        total_snipes = len(self.snipe_results)
        successful_snipes = sum(1 for result in self.snipe_results.values() if result.success)
        
        avg_execution_time = 0
        if self.snipe_results:
            avg_execution_time = sum(
                result.execution_time for result in self.snipe_results.values()
            ) / len(self.snipe_results)
        
        return {
            'total_snipes': total_snipes,
            'successful_snipes': successful_snipes,
            'success_rate': successful_snipes / total_snipes if total_snipes > 0 else 0,
            'avg_execution_time': avg_execution_time,
            'is_executing': self.is_executing,
            'queue_size': self.execution_queue.qsize()
        }
    
    def set_max_gas_price(self, max_gas_price: int) -> None:
        """Set maximum gas price"""
        self.max_gas_price = max_gas_price
        logger.info(f"Set maximum gas price: {max_gas_price}")
    
    def set_priority_fee_multiplier(self, multiplier: float) -> None:
        """Set priority fee multiplier"""
        self.priority_fee_multiplier = multiplier
        logger.info(f"Set priority fee multiplier: {multiplier}")
    
    def clear_cache(self) -> None:
        """Clear execution cache"""
        self.snipe_results.clear()
        logger.info("Snipe results cache cleared")
