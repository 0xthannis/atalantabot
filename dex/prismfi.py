"""
PrismFi DEX Integration
Handles interactions with PrismFi protocol on MegaETH
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from web3 import Web3, AsyncWeb3
from web3.contract import Contract
from web3.exceptions import TransactionNotFound, ContractLogicError
import json
from datetime import datetime, timezone

from config import Config, PRISMFI_ROUTER, ROUTER_ABI, FACTORY_ABI, PAIR_ABI, ERC20_ABI

logger = logging.getLogger(__name__)

class PrismFiDEX:
    """PrismFi DEX integration class"""
    
    def __init__(self, w3: Web3, async_w3: AsyncWeb3):
        self.w3 = w3
        self.async_w3 = async_w3
        self.router_address = PRISMFI_ROUTER
        
        if not self.router_address:
            logger.warning("PrismFi router address not configured")
            self.router_contract = None
            return
        
        # Initialize router contract
        self.router_contract = w3.eth.contract(
            address=Web3.to_checksum_address(self.router_address),
            abi=ROUTER_ABI
        )
        
        # Cache for token info and pairs
        self._token_info_cache: Dict[str, Dict[str, Any]] = {}
        self._pair_cache: Dict[str, str] = {}
        
    async def is_available(self) -> bool:
        """Check if PrismFi is available and configured"""
        return self.router_contract is not None and bool(self.router_address)
    
    async def get_token_price(self, token_address: str, base_token: str = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE") -> Optional[float]:
        """Get token price from PrismFi"""
        if not await self.is_available():
            return None
        
        try:
            # This would need to be implemented based on PrismFi's specific API
            # For now, return None as placeholder
            logger.info(f"PrismFi price query for {token_address} - not implemented yet")
            return None
            
        except Exception as e:
            logger.error(f"Error getting PrismFi price for {token_address}: {e}")
            return None
    
    async def get_amounts_out(self, amount_in: int, path: List[str]) -> Optional[List[int]]:
        """Get output amounts for swap on PrismFi"""
        if not await self.is_available():
            return None
        
        try:
            amounts = await self.router_contract.functions.getAmountsOut(amount_in, path).call()
            return amounts
        except Exception as e:
            logger.error(f"Error getting PrismFi amounts out: {e}")
            return None
    
    async def estimate_swap_gas(self, amount_in: int, path: List[str], to_address: str) -> Optional[int]:
        """Estimate gas for PrismFi swap"""
        if not await self.is_available():
            return None
        
        try:
            deadline = int((datetime.now(timezone.utc).timestamp() + 300))
            
            tx_data = self.router_contract.functions.swapExactETHForTokens(
                0,
                path,
                Web3.to_checksum_address(to_address),
                deadline
            ).build_transaction({
                'from': Web3.to_checksum_address(to_address),
                'value': amount_in,
                'gas': Config.DEFAULT_GAS_LIMIT,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': await self.async_w3.eth.get_transaction_count(to_address)
            })
            
            gas_estimate = await self.async_w3.eth.estimate_gas(tx_data)
            return gas_estimate
            
        except Exception as e:
            logger.error(f"Error estimating PrismFi swap gas: {e}")
            return None
    
    def build_swap_transaction(self, amount_in: int, amount_out_min: int, path: List[str], 
                              to_address: str, deadline: Optional[int] = None) -> Dict[str, Any]:
        """Build PrismFi swap transaction"""
        if not self.router_contract:
            return {}
        
        if deadline is None:
            deadline = int((datetime.now(timezone.utc).timestamp() + 300))
        
        try:
            tx_data = self.router_contract.functions.swapExactETHForTokens(
                amount_out_min,
                path,
                Web3.to_checksum_address(to_address),
                deadline
            ).build_transaction({
                'from': Web3.to_checksum_address(to_address),
                'value': amount_in,
                'gas': Config.DEFAULT_GAS_LIMIT,
                'gasPrice': int(self.w3.eth.gas_price * Config.GAS_MULTIPLIER),
                'chainId': Config.CHAIN_ID
            })
            
            return tx_data
            
        except Exception as e:
            logger.error(f"Error building PrismFi swap transaction: {e}")
            return {}
    
    async def get_liquidity_pools(self) -> List[Dict[str, Any]]:
        """Get available liquidity pools on PrismFi"""
        if not await self.is_available():
            return []
        
        # This would need to be implemented based on PrismFi's specific API
        logger.info("PrismFi liquidity pools query - not implemented yet")
        return []
    
    def clear_cache(self):
        """Clear internal caches"""
        self._token_info_cache.clear()
        self._pair_cache.clear()
        logger.info("PrismFi DEX cache cleared")
