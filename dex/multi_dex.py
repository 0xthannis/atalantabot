"""
Multi-DEX Arbitrage Scanner
Scans and executes arbitrage opportunities across multiple DEXes on MegaETH
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timezone
import time

from config import Config
from .kumbaya import KumbayaDEX
from .prismfi import PrismFiDEX

logger = logging.getLogger(__name__)

@dataclass
class ArbitrageOpportunity:
    """Arbitrage opportunity data structure"""
    token_address: str
    token_symbol: str
    dex_a: str
    dex_b: str
    price_a: float
    price_b: float
    profit_percentage: float
    gas_estimate: float
    net_profit: float
    is_executable: bool
    discovered_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            'token_address': self.token_address,
            'token_symbol': self.token_symbol,
            'dex_a': self.dex_a,
            'dex_b': self.dex_b,
            'price_a': self.price_a,
            'price_b': self.price_b,
            'profit_percentage': self.profit_percentage,
            'gas_estimate': self.gas_estimate,
            'net_profit': self.net_profit,
            'is_executable': self.is_executable,
            'discovered_at': self.discovered_at
        }

class MultiDEXScanner:
    """Multi-DEX arbitrage scanner and executor"""
    
    def __init__(self, kumbaya: KumbayaDEX, prismfi: PrismFiDEX):
        self.kumbaya = kumbaya
        self.prismfi = prismfi
        
        # Available DEXes
        self.dexes = {
            'kumbaya': kumbaya,
            'prismfi': prismfi
        }
        
        # Common tokens to monitor
        self.monitor_tokens = [
            "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",  # ETH
            # Add popular tokens as they become available on MegaETH
        ]
        
        # Recent opportunities cache
        self.recent_opportunities: List[ArbitrageOpportunity] = []
        self.max_cache_size = 100
        
        # Scanning state
        self.is_scanning = False
        self.scan_task: Optional[asyncio.Task] = None
        
    async def start_scanning(self) -> None:
        """Start continuous arbitrage scanning"""
        if self.is_scanning:
            logger.warning("Arbitrage scanning already running")
            return
        
        self.is_scanning = True
        self.scan_task = asyncio.create_task(self._scan_loop())
        logger.info("Started arbitrage scanning")
    
    async def stop_scanning(self) -> None:
        """Stop continuous arbitrage scanning"""
        self.is_scanning = False
        if self.scan_task:
            self.scan_task.cancel()
            try:
                await self.scan_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped arbitrage scanning")
    
    async def _scan_loop(self) -> None:
        """Main scanning loop"""
        while self.is_scanning:
            try:
                opportunities = await self.scan_arbitrage_opportunities()
                
                # Filter profitable opportunities
                profitable_opps = [
                    opp for opp in opportunities 
                    if opp.profit_percentage > Config.MIN_PROFIT_THRESHOLD and opp.is_executable
                ]
                
                if profitable_opps:
                    logger.info(f"Found {len(profitable_opps)} profitable arbitrage opportunities")
                    
                    # Add to cache
                    self.recent_opportunities.extend(profitable_opps)
                    
                    # Limit cache size
                    if len(self.recent_opportunities) > self.max_cache_size:
                        self.recent_opportunities = self.recent_opportunities[-self.max_cache_size:]
                
                await asyncio.sleep(Config.SCAN_INTERVAL)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in arbitrage scan loop: {e}")
                await asyncio.sleep(Config.SCAN_INTERVAL)
    
    async def scan_arbitrage_opportunities(self) -> List[ArbitrageOpportunity]:
        """Scan for arbitrage opportunities across all DEX pairs"""
        opportunities = []
        
        # Get all DEX combinations
        dex_names = list(self.dexes.keys())
        for i in range(len(dex_names)):
            for j in range(i + 1, len(dex_names)):
                dex_a_name = dex_names[i]
                dex_b_name = dex_names[j]
                dex_a = self.dexes[dex_a_name]
                dex_b = self.dexes[dex_b_name]
                
                # Check if both DEXes are available
                if (not hasattr(dex_a, 'is_available') or await dex_a.is_available()) and \
                   (not hasattr(dex_b, 'is_available') or await dex_b.is_available()):
                    
                    # Scan tokens for arbitrage between these DEXes
                    opps = await self._scan_dex_pair(dex_a, dex_b, dex_a_name, dex_b_name)
                    opportunities.extend(opps)
        
        return opportunities
    
    async def _scan_dex_pair(self, dex_a, dex_b, dex_a_name: str, dex_b_name: str) -> List[ArbitrageOpportunity]:
        """Scan for arbitrage opportunities between two specific DEXes"""
        opportunities = []
        
        # For each token, compare prices
        for token_address in self.monitor_tokens:
            try:
                # Get prices from both DEXes
                price_a_task = dex_a.get_token_price(token_address)
                price_b_task = dex_b.get_token_price(token_address)
                
                price_a, price_b = await asyncio.gather(
                    price_a_task, price_b_task, return_exceptions=True
                )
                
                # Skip if either price is not available
                if isinstance(price_a, Exception) or isinstance(price_b, Exception):
                    continue
                
                if price_a is None or price_b is None:
                    continue
                
                # Calculate price difference
                if price_a > 0 and price_b > 0:
                    price_diff_pct = abs(price_a - price_b) / min(price_a, price_b) * 100
                    
                    if price_diff_pct > Config.MIN_PROFIT_THRESHOLD:
                        # Determine direction of arbitrage
                        if price_a < price_b:
                            # Buy on DEX A, sell on DEX B
                            buy_dex, sell_dex = dex_a_name, dex_b_name
                            buy_price, sell_price = price_a, price_b
                        else:
                            # Buy on DEX B, sell on DEX A
                            buy_dex, sell_dex = dex_b_name, dex_a_name
                            buy_price, sell_price = price_b, price_a
                        
                        # Estimate gas costs
                        gas_estimate = await self._estimate_arbitrage_gas(token_address, buy_dex, sell_dex)
                        
                        # Calculate net profit
                        trade_amount = 0.1  # 0.1 ETH for estimation
                        gross_profit = (sell_price - buy_price) * trade_amount
                        gas_cost_eth = gas_estimate * self._get_gas_price() / 1e18
                        net_profit = gross_profit - gas_cost_eth
                        
                        # Check if profitable after gas
                        is_executable = net_profit > 0.001  # Minimum 0.001 ETH profit
                        
                        # Get token info
                        token_info = await dex_a.get_token_info(token_address)
                        token_symbol = token_info['symbol'] if token_info else "UNKNOWN"
                        
                        opportunity = ArbitrageOpportunity(
                            token_address=token_address,
                            token_symbol=token_symbol,
                            dex_a=buy_dex,
                            dex_b=sell_dex,
                            price_a=buy_price,
                            price_b=sell_price,
                            profit_percentage=price_diff_pct,
                            gas_estimate=gas_estimate,
                            net_profit=net_profit,
                            is_executable=is_executable,
                            discovered_at=datetime.now(timezone.utc)
                        )
                        
                        opportunities.append(opportunity)
                        
            except Exception as e:
                logger.error(f"Error scanning token {token_address} between {dex_a_name} and {dex_b_name}: {e}")
                continue
        
        return opportunities
    
    async def _estimate_arbitrage_gas(self, token_address: str, buy_dex: str, sell_dex: str) -> int:
        """Estimate gas for arbitrage execution"""
        try:
            # Estimate gas for buy transaction
            buy_dex_obj = self.dexes[buy_dex]
            sell_dex_obj = self.dexes[sell_dex]
            
            # Sample address for estimation
            sample_address = "0x1234567890123456789012345678901234567890"
            amount_in = 10000000000000000  # 0.01 ETH
            
            # Path for buy
            buy_path = [Config.WETH_ADDRESS, token_address]
            
            # Path for sell
            sell_path = [token_address, Config.WETH_ADDRESS]
            
            # Estimate gas for both transactions
            buy_gas_task = None
            sell_gas_task = None
            
            if hasattr(buy_dex_obj, 'estimate_swap_gas'):
                buy_gas_task = buy_dex_obj.estimate_swap_gas(amount_in, buy_path, sample_address)
            
            if hasattr(sell_dex_obj, 'estimate_swap_gas'):
                # Estimate token amount for sell (simplified)
                token_amount = 1000000  # Placeholder
                sell_gas_task = sell_dex_obj.estimate_swap_gas(token_amount, sell_path, sample_address)
            
            gas_estimates = await asyncio.gather(
                buy_gas_task, sell_gas_task, return_exceptions=True
            )
            
            total_gas = 0
            for gas in gas_estimates:
                if not isinstance(gas, Exception) and gas is not None:
                    total_gas += gas
            
            return total_gas or Config.DEFAULT_GAS_LIMIT * 2
            
        except Exception as e:
            logger.error(f"Error estimating arbitrage gas: {e}")
            return Config.DEFAULT_GAS_LIMIT * 2
    
    def _get_gas_price(self) -> int:
        """Get current gas price"""
        try:
            return self.kumbaya.w3.eth.gas_price
        except Exception:
            return int(1e10)  # 10 gwei fallback
    
    async def execute_arbitrage(self, opportunity: ArbitrageOpportunity, user_address: str, 
                              amount_eth: float) -> Optional[str]:
        """Execute arbitrage opportunity"""
        try:
            if not opportunity.is_executable:
                logger.warning("Attempting to execute non-executable arbitrage")
                return None
            
            # Get DEX objects
            buy_dex = self.dexes[opportunity.dex_a]
            sell_dex = self.dexes[opportunity.dex_b]
            
            # Convert amount to wei
            amount_in = int(amount_eth * 1e18)
            
            # Build buy transaction
            buy_path = [Config.WETH_ADDRESS, opportunity.token_address]
            buy_tx = buy_dex.build_swap_transaction(
                amount_in, 0, buy_path, user_address
            )
            
            if not buy_tx:
                logger.error("Failed to build buy transaction")
                return None
            
            # For now, return the transaction data for user to sign
            # In production, you'd handle the full execution flow
            logger.info(f"Arbitrage transaction prepared for {opportunity.token_symbol}")
            
            return json.dumps({
                'buy_transaction': buy_tx,
                'opportunity': opportunity.to_dict()
            })
            
        except Exception as e:
            logger.error(f"Error executing arbitrage: {e}")
            return None
    
    async def get_recent_opportunities(self, limit: int = 20) -> List[ArbitrageOpportunity]:
        """Get recent arbitrage opportunities"""
        return self.recent_opportunities[-limit:]
    
    async def add_monitor_token(self, token_address: str) -> None:
        """Add a token to monitor for arbitrage"""
        if token_address not in self.monitor_tokens:
            self.monitor_tokens.append(token_address)
            logger.info(f"Added token {token_address} to arbitrage monitoring")
    
    async def remove_monitor_token(self, token_address: str) -> None:
        """Remove a token from arbitrage monitoring"""
        if token_address in self.monitor_tokens:
            self.monitor_tokens.remove(token_address)
            logger.info(f"Removed token {token_address} from arbitrage monitoring")
    
    def get_scanning_status(self) -> Dict[str, Any]:
        """Get current scanning status"""
        return {
            'is_scanning': self.is_scanning,
            'monitor_tokens_count': len(self.monitor_tokens),
            'recent_opportunities_count': len(self.recent_opportunities),
            'available_dexes': [name for name, dex in self.dexes.items() 
                               if not hasattr(dex, 'is_available') or dex.is_available()]
        }
    
    async def get_best_opportunity(self) -> Optional[ArbitrageOpportunity]:
        """Get the best current arbitrage opportunity"""
        executable_opps = [
            opp for opp in self.recent_opportunities 
            if opp.is_executable and opp.net_profit > 0
        ]
        
        if not executable_opps:
            return None
        
        # Return the opportunity with highest net profit
        return max(executable_opps, key=lambda x: x.net_profit)
    
    def clear_cache(self) -> None:
        """Clear opportunities cache"""
        self.recent_opportunities.clear()
        logger.info("Arbitrage opportunities cache cleared")
