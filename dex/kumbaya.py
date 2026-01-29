"""
Kumbaya DEX Integration
Handles interactions with Kumbaya protocol on MegaETH
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from web3 import Web3, AsyncWeb3
from web3.contract import Contract
from web3.exceptions import TransactionNotFound, ContractLogicError
import json
from datetime import datetime, timezone

from config import Config, KUMBADYA_ROUTER, KUMBADYA_FACTORY, ROUTER_ABI, FACTORY_ABI, PAIR_ABI, ERC20_ABI

logger = logging.getLogger(__name__)

class KumbayaDEX:
    """Kumbaya DEX integration class"""
    
    def __init__(self, w3: Web3, async_w3: AsyncWeb3):
        self.w3 = w3
        self.async_w3 = async_w3
        self.router_address = KUMBADYA_ROUTER
        self.factory_address = KUMBADYA_FACTORY
        
        # Initialize contracts
        self.router_contract = w3.eth.contract(
            address=Web3.to_checksum_address(self.router_address),
            abi=ROUTER_ABI
        )
        self.factory_contract = w3.eth.contract(
            address=Web3.to_checksum_address(self.factory_address),
            abi=FACTORY_ABI
        )
        
        # Cache for pair addresses
        self._pair_cache: Dict[str, str] = {}
        self._token_info_cache: Dict[str, Dict[str, Any]] = {}
        
    async def get_token_info(self, token_address: str) -> Optional[Dict[str, Any]]:
        """Get token information (name, symbol, decimals)"""
        token_address = Web3.to_checksum_address(token_address)
        
        # Check cache first
        if token_address in self._token_info_cache:
            return self._token_info_cache[token_address]
        
        try:
            token_contract = self.async_w3.eth.contract(
                address=token_address,
                abi=ERC20_ABI
            )
            
            # Get token info in parallel
            name_task = token_contract.functions.name().call()
            symbol_task = token_contract.functions.symbol().call()
            decimals_task = token_contract.functions.decimals().call()
            
            name, symbol, decimals = await asyncio.gather(
                name_task, symbol_task, decimals_task
            )
            
            token_info = {
                'address': token_address,
                'name': name,
                'symbol': symbol,
                'decimals': decimals
            }
            
            # Cache the result
            self._token_info_cache[token_address] = token_info
            
            return token_info
            
        except Exception as e:
            logger.error(f"Error getting token info for {token_address}: {e}")
            return None
    
    async def get_pair_address(self, token_a: str, token_b: str) -> Optional[str]:
        """Get pair address from factory"""
        token_a = Web3.to_checksum_address(token_a)
        token_b = Web3.to_checksum_address(token_b)
        
        # Create cache key
        cache_key = f"{token_a}-{token_b}"
        if cache_key in self._pair_cache:
            return self._pair_cache[cache_key]
        
        try:
            pair_address = await self.factory_contract.functions.getPair(token_a, token_b).call()
            
            if pair_address == "0x0000000000000000000000000000000000000000":
                return None
            
            # Cache the result
            self._pair_cache[cache_key] = pair_address
            self._pair_cache[f"{token_b}-{token_a}"] = pair_address  # Reverse order
            
            return pair_address
            
        except Exception as e:
            logger.error(f"Error getting pair address for {token_a}/{token_b}: {e}")
            return None
    
    async def get_pair_reserves(self, pair_address: str) -> Optional[Tuple[int, int, int]]:
        """Get pair reserves (reserve0, reserve1, timestamp)"""
        pair_address = Web3.to_checksum_address(pair_address)
        
        try:
            pair_contract = self.async_w3.eth.contract(
                address=pair_address,
                abi=PAIR_ABI
            )
            
            reserves = await pair_contract.functions.getReserves().call()
            return reserves
            
        except Exception as e:
            logger.error(f"Error getting reserves for pair {pair_address}: {e}")
            return None
    
    async def get_token_price(self, token_address: str, base_token: str = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE") -> Optional[float]:
        """Get token price in base token (ETH by default)"""
        try:
            pair_address = await self.get_pair_address(token_address, base_token)
            if not pair_address:
                return None
            
            reserves = await self.get_pair_reserves(pair_address)
            if not reserves:
                return None
            
            reserve0, reserve1, _ = reserves
            
            # Get token order
            pair_contract = self.async_w3.eth.contract(
                address=pair_address,
                abi=PAIR_ABI
            )
            
            token0 = await pair_contract.functions.token0().call()
            
            # Calculate price
            if Web3.to_checksum_address(token0) == Web3.to_checksum_address(token_address):
                price = float(reserve1) / float(reserve0) if reserve0 > 0 else 0
            else:
                price = float(reserve0) / float(reserve1) if reserve1 > 0 else 0
            
            return price
            
        except Exception as e:
            logger.error(f"Error getting price for {token_address}: {e}")
            return None
    
    async def get_amounts_out(self, amount_in: int, path: List[str]) -> Optional[List[int]]:
        """Get output amounts for a given input amount and path"""
        try:
            amounts = await self.router_contract.functions.getAmountsOut(amount_in, path).call()
            return amounts
        except Exception as e:
            logger.error(f"Error getting amounts out: {e}")
            return None
    
    async def estimate_swap_gas(self, amount_in: int, path: List[str], to_address: str) -> Optional[int]:
        """Estimate gas for swap transaction"""
        try:
            # Build transaction
            deadline = int((datetime.now(timezone.utc).timestamp() + 300))  # 5 minutes
            
            tx_data = self.router_contract.functions.swapExactETHForTokens(
                0,  # amountOutMin, will be calculated later
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
            
            # Estimate gas
            gas_estimate = await self.async_w3.eth.estimate_gas(tx_data)
            return gas_estimate
            
        except Exception as e:
            logger.error(f"Error estimating swap gas: {e}")
            return None
    
    def build_swap_transaction(self, amount_in: int, amount_out_min: int, path: List[str], 
                              to_address: str, deadline: Optional[int] = None) -> Dict[str, Any]:
        """Build swap transaction for user to sign"""
        if deadline is None:
            deadline = int((datetime.now(timezone.utc).timestamp() + 300))  # 5 minutes
        
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
            logger.error(f"Error building swap transaction: {e}")
            return {}
    
    async def calculate_slippage(self, amount_in: int, path: List[str], slippage_percent: float) -> int:
        """Calculate minimum output amount based on slippage"""
        try:
            amounts = await self.get_amounts_out(amount_in, path)
            if not amounts:
                return 0
            
            expected_out = amounts[-1]
            slippage_multiplier = (100 - slippage_percent) / 100
            min_out = int(expected_out * slippage_multiplier)
            
            return min_out
            
        except Exception as e:
            logger.error(f"Error calculating slippage: {e}")
            return 0
    
    async def check_liquidity(self, token_address: str, min_liquidity_eth: float = 1.0) -> bool:
        """Check if token has sufficient liquidity"""
        try:
            price = await self.get_token_price(token_address)
            if not price:
                return False
            
            pair_address = await self.get_pair_address(token_address)
            if not pair_address:
                return False
            
            reserves = await self.get_pair_reserves(pair_address)
            if not reserves:
                return False
            
            reserve0, reserve1, _ = reserves
            
            # Get token order
            pair_contract = self.async_w3.eth.contract(
                address=pair_address,
                abi=PAIR_ABI
            )
            
            token0 = await pair_contract.functions.token0().call()
            
            # Calculate ETH liquidity
            if Web3.to_checksum_address(token0) == Web3.to_checksum_address(token_address):
                eth_liquidity = self.w3.from_wei(reserve1, 'ether')
            else:
                eth_liquidity = self.w3.from_wei(reserve0, 'ether')
            
            return eth_liquidity >= min_liquidity_eth
            
        except Exception as e:
            logger.error(f"Error checking liquidity for {token_address}: {e}")
            return False
    
    async def get_recent_pairs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recently created pairs (for monitoring new launches)"""
        # This would require event filtering - simplified for now
        # In production, you'd use websocket events for real-time monitoring
        return []
    
    async def simulate_honeypot(self, token_address: str) -> Dict[str, Any]:
        """Basic honeypot simulation"""
        try:
            # Check if we can get a price
            price = await self.get_token_price(token_address)
            if not price:
                return {"is_honeypot": True, "reason": "No price available"}
            
            # Check liquidity
            has_liquidity = await self.check_liquidity(token_address, 0.1)
            if not has_liquidity:
                return {"is_honeypot": True, "reason": "Insufficient liquidity"}
            
            # Check buy/sell tax (simplified - would need more sophisticated analysis)
            # This is a basic check - real honeypot detection is more complex
            buy_amount = self.w3.to_wei(0.01, 'ether')
            
            pair_address = await self.get_pair_address(token_address)
            if not pair_address:
                return {"is_honeypot": True, "reason": "No pair exists"}
            
            # Simulate buy
            amounts_out = await self.get_amounts_out([buy_amount], [Config.WETH_ADDRESS, token_address])
            if not amounts_out:
                return {"is_honeypot": True, "reason": "Cannot simulate buy"}
            
            tokens_received = amounts_out[-1]
            
            # Simulate sell back
            amounts_back = await self.get_amounts_out(tokens_received, [token_address, Config.WETH_ADDRESS])
            if not amounts_back:
                return {"is_honeypot": True, "reason": "Cannot simulate sell"}
            
            eth_received = amounts_back[-1]
            loss_percentage = ((buy_amount - eth_received) / buy_amount) * 100
            
            # If loss > 10%, likely a honeypot
            is_honeypot = loss_percentage > 10
            
            return {
                "is_honeypot": is_honeypot,
                "reason": f"{'High tax detected' if is_honeypot else 'Normal behavior'}",
                "loss_percentage": loss_percentage,
                "price": price,
                "liquidity_eth": await self.get_pair_liquidity(pair_address)
            }
            
        except Exception as e:
            logger.error(f"Error simulating honeypot for {token_address}: {e}")
            return {"is_honeypot": True, "reason": f"Simulation error: {str(e)}"}
    
    async def get_pair_liquidity(self, pair_address: str) -> float:
        """Get total liquidity in ETH for a pair"""
        try:
            reserves = await self.get_pair_reserves(pair_address)
            if not reserves:
                return 0
            
            reserve0, reserve1, _ = reserves
            
            # Get token order
            pair_contract = self.async_w3.eth.contract(
                address=pair_address,
                abi=PAIR_ABI
            )
            
            token0 = await pair_contract.functions.token0().call()
            
            # Calculate total liquidity (simplified)
            if token0 == Config.WETH_ADDRESS:
                eth_liquidity = self.w3.from_wei(reserve0, 'ether')
            else:
                eth_liquidity = self.w3.from_wei(reserve1, 'ether')
            
            return eth_liquidity
            
        except Exception as e:
            logger.error(f"Error getting pair liquidity: {e}")
            return 0
    
    def clear_cache(self):
        """Clear internal caches"""
        self._pair_cache.clear()
        self._token_info_cache.clear()
        logger.info("Kumbaya DEX cache cleared")
