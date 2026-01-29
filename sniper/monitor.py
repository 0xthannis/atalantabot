"""
Token Launch Monitor
Real-time monitoring of new token launches via websocket events
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime, timezone
from web3 import AsyncWeb3
from web3.providers.websocket import WebsocketProviderV2
import websockets

from config import Config, FACTORY_ABI

logger = logging.getLogger(__name__)

@dataclass
class TokenLaunch:
    """Token launch event data"""
    token_address: str
    token0: str
    token1: str
    pair_address: str
    all_pairs_length: int
    block_number: int
    transaction_hash: str
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'token_address': self.token_address,
            'token0': self.token0,
            'token1': self.token1,
            'pair_address': self.pair_address,
            'all_pairs_length': self.all_pairs_length,
            'block_number': self.block_number,
            'transaction_hash': self.transaction_hash,
            'timestamp': self.timestamp.isoformat()
        }

class TokenMonitor:
    """Real-time token launch monitor using websockets"""
    
    def __init__(self, async_w3: AsyncWeb3):
        self.async_w3 = async_w3
        self.factory_address = Config.KUMBADYA_FACTORY
        self.factory_contract = async_w3.eth.contract(
            address=self.factory_address,
            abi=FACTORY_ABI
        )
        
        # Event callbacks
        self.launch_callbacks: List[Callable[[TokenLaunch], None]] = []
        
        # Monitoring state
        self.is_monitoring = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.websocket_connection: Optional[Any] = None
        
        # Recent launches cache
        self.recent_launches: List[TokenLaunch] = []
        self.max_cache_size = 100
        
        # Filter settings
        self.min_liquidity_eth: float = 0.5
        self.blacklisted_tokens: set = set()
        self.whitelisted_tokens: set = set()
        
    async def start_monitoring(self) -> None:
        """Start monitoring for new token launches"""
        if self.is_monitoring:
            logger.warning("Token monitoring already running")
            return
        
        self.is_monitoring = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Started token launch monitoring")
    
    async def stop_monitoring(self) -> None:
        """Stop monitoring token launches"""
        self.is_monitoring = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        if self.websocket_connection:
            await self.websocket_connection.close()
            self.websocket_connection = None
        
        logger.info("Stopped token launch monitoring")
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop using websocket events"""
        while self.is_monitoring:
            try:
                # Subscribe to PairCreated events
                await self._subscribe_to_events()
                
                # Keep connection alive and process events
                await self._process_events()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(5)  # Wait before reconnecting
    
    async def _subscribe_to_events(self) -> None:
        """Subscribe to factory events via websocket"""
        try:
            # Create websocket filter for PairCreated events
            pair_created_filter = self.factory_contract.events.PairCreated.create_filter(
                from_block='latest'
            )
            
            # Start monitoring
            self.monitor_task = asyncio.create_task(
                self._watch_events(pair_created_filter)
            )
            
        except Exception as e:
            logger.error(f"Error subscribing to events: {e}")
            raise
    
    async def _watch_events(self, event_filter) -> None:
        """Watch for new events"""
        try:
            async for event in event_filter:
                if not self.is_monitoring:
                    break
                
                await self._handle_pair_created_event(event)
                
        except Exception as e:
            logger.error(f"Error watching events: {e}")
    
    async def _handle_pair_created_event(self, event) -> None:
        """Handle PairCreated event"""
        try:
            # Extract event data
            token0 = event.args.token0
            token1 = event.args.token1
            pair = event.args.pair
            all_pairs_length = event.args.allPairsLength
            
            # Determine which is the new token (not WETH)
            weth_address = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"  # WETH placeholder
            
            if token0.lower() == weth_address.lower():
                new_token_address = token1
            elif token1.lower() == weth_address.lower():
                new_token_address = token0
            else:
                # Skip if neither token is WETH (not a standard pair)
                return
            
            # Apply filters
            if not await self._should_process_token(new_token_address):
                return
            
            # Create token launch object
            launch = TokenLaunch(
                token_address=new_token_address,
                token0=token0,
                token1=token1,
                pair_address=pair,
                all_pairs_length=all_pairs_length,
                block_number=event.blockNumber,
                transaction_hash=event.transactionHash.hex(),
                timestamp=datetime.now(timezone.utc)
            )
            
            # Add to cache
            self.recent_launches.append(launch)
            if len(self.recent_launches) > self.max_cache_size:
                self.recent_launches = self.recent_launches[-self.max_cache_size:]
            
            # Notify callbacks
            await self._notify_callbacks(launch)
            
            logger.info(f"New token launch detected: {new_token_address}")
            
        except Exception as e:
            logger.error(f"Error handling PairCreated event: {e}")
    
    async def _should_process_token(self, token_address: str) -> bool:
        """Check if token should be processed based on filters"""
        try:
            # Check blacklist
            if token_address.lower() in [t.lower() for t in self.blacklisted_tokens]:
                return False
            
            # Check whitelist (if not empty, only process whitelisted tokens)
            if self.whitelisted_tokens:
                if token_address.lower() not in [t.lower() for t in self.whitelisted_tokens]:
                    return False
            
            # Additional checks can be added here
            # For example: honeypot detection, liquidity check, etc.
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking token filters: {e}")
            return False
    
    async def _notify_callbacks(self, launch: TokenLaunch) -> None:
        """Notify all registered callbacks"""
        for callback in self.launch_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(launch)
                else:
                    callback(launch)
            except Exception as e:
                logger.error(f"Error in launch callback: {e}")
    
    def add_launch_callback(self, callback: Callable[[TokenLaunch], None]) -> None:
        """Add callback for new token launches"""
        self.launch_callbacks.append(callback)
        logger.info(f"Added launch callback: {callback.__name__}")
    
    def remove_launch_callback(self, callback: Callable[[TokenLaunch], None]) -> None:
        """Remove launch callback"""
        if callback in self.launch_callbacks:
            self.launch_callbacks.remove(callback)
            logger.info(f"Removed launch callback: {callback.__name__}")
    
    async def get_recent_launches(self, limit: int = 20) -> List[TokenLaunch]:
        """Get recent token launches"""
        return self.recent_launches[-limit:]
    
    async def get_launch_by_address(self, token_address: str) -> Optional[TokenLaunch]:
        """Get launch info by token address"""
        for launch in self.recent_launches:
            if launch.token_address.lower() == token_address.lower():
                return launch
        return None
    
    def add_blacklisted_token(self, token_address: str) -> None:
        """Add token to blacklist"""
        self.blacklisted_tokens.add(token_address.lower())
        logger.info(f"Added token to blacklist: {token_address}")
    
    def remove_blacklisted_token(self, token_address: str) -> None:
        """Remove token from blacklist"""
        self.blacklisted_tokens.discard(token_address.lower())
        logger.info(f"Removed token from blacklist: {token_address}")
    
    def add_whitelisted_token(self, token_address: str) -> None:
        """Add token to whitelist"""
        self.whitelisted_tokens.add(token_address.lower())
        logger.info(f"Added token to whitelist: {token_address}")
    
    def remove_whitelisted_token(self, token_address: str) -> None:
        """Remove token from whitelist"""
        self.whitelisted_tokens.discard(token_address.lower())
        logger.info(f"Removed token from whitelist: {token_address}")
    
    def set_min_liquidity(self, min_liquidity_eth: float) -> None:
        """Set minimum liquidity threshold"""
        self.min_liquidity_eth = min_liquidity_eth
        logger.info(f"Set minimum liquidity threshold: {min_liquidity_eth} ETH")
    
    async def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status"""
        return {
            'is_monitoring': self.is_monitoring,
            'recent_launches_count': len(self.recent_launches),
            'blacklisted_tokens_count': len(self.blacklisted_tokens),
            'whitelisted_tokens_count': len(self.whitelisted_tokens),
            'min_liquidity_eth': self.min_liquidity_eth,
            'factory_address': self.factory_address
        }
    
    async def simulate_launch_detection(self, token_address: str) -> TokenLaunch:
        """Simulate a token launch for testing"""
        launch = TokenLaunch(
            token_address=token_address,
            token0="0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",  # WETH
            token1=token_address,
            pair_address="0x" + "0" * 40,  # Placeholder
            all_pairs_length=1,
            block_number=12345,
            transaction_hash="0x" + "0" * 64,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Add to cache
        self.recent_launches.append(launch)
        
        # Notify callbacks
        await self._notify_callbacks(launch)
        
        return launch
    
    def clear_cache(self) -> None:
        """Clear recent launches cache"""
        self.recent_launches.clear()
        logger.info("Token launches cache cleared")
