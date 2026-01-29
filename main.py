"""
Atalanta Bot - Main Application
Professional Telegram bot for MegaETH trading and arbitrage
"""

import asyncio
import logging
import signal
import sys
from contextlib import suppress

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError

from config import Config, Config as BotConfig
from database import Database
from dex.kumbaya import KumbayaDEX
from dex.prismfi import PrismFiDEX
from dex.multi_dex import MultiDEXScanner
from sniper.monitor import TokenMonitor
from sniper.executor import SniperExecutor
from ai.predictor import AIPredictor
from handlers.commands import CommandHandler as CmdHandler
from handlers.callbacks import CallbackHandler
from handlers.wallet import WalletHandler
from utils.security import RateLimiter, security_logger

# Configure logging
logging.basicConfig(
    level=getattr(logging, BotConfig.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(BotConfig.LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class AtalantaBot:
    """Main Atalanta bot application"""
    
    def __init__(self):
        self.application = None
        self.database = None
        self.rate_limiter = None
        
        # DEX integrations
        self.w3 = None
        self.async_w3 = None
        self.kumbaya = None
        self.prismfi = None
        self.multi_dex = None
        
        # Core components
        self.token_monitor = None
        self.sniper_executor = None
        self.ai_predictor = None
        
        # Handlers
        self.command_handler = None
        self.callback_handler = None
        self.wallet_handler = None
        
        # State
        self.is_running = False
        self.shutdown_event = asyncio.Event()
    
    async def initialize(self) -> None:
        """Initialize all bot components"""
        try:
            logger.info("Initializing Atalanta Bot...")
            
            # Validate configuration
            BotConfig.validate()
            
            # Initialize database
            self.database = Database(BotConfig.DATABASE_PATH)
            await self.database.initialize()
            logger.info("Database initialized")
            
            # Initialize Web3 connections
            await self._initialize_web3()
            
            # Initialize DEX integrations
            await self._initialize_dex()
            
            # Initialize core components
            await self._initialize_components()
            
            # Initialize handlers
            await self._initialize_handlers()
            
            # Initialize Telegram application
            await self._initialize_telegram()
            
            logger.info("Atalanta Bot initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            raise
    
    async def _initialize_web3(self) -> None:
        """Initialize Web3 connections"""
        from web3 import Web3, AsyncWeb3
        from web3.providers.async import AsyncHTTPProvider
        
        # Initialize sync Web3
        self.w3 = Web3(Web3.HTTPProvider(BotConfig.MEGAETH_RPC))
        
        # Initialize async Web3
        self.async_w3 = AsyncWeb3(AsyncHTTPProvider(BotConfig.MEGAETH_RPC))
        
        # Test connections
        chain_id = self.w3.eth.chain_id
        if chain_id != BotConfig.CHAIN_ID:
            raise ValueError(f"Invalid chain ID: {chain_id}, expected {BotConfig.CHAIN_ID}")
        
        logger.info(f"Connected to MegaETH (Chain ID: {chain_id})")
    
    async def _initialize_dex(self) -> None:
        """Initialize DEX integrations"""
        # Initialize Kumbaya
        self.kumbaya = KumbayaDEX(self.w3, self.async_w3)
        logger.info("Kumbaya DEX initialized")
        
        # Initialize PrismFi
        self.prismfi = PrismFiDEX(self.w3, self.async_w3)
        logger.info("PrismFi DEX initialized")
        
        # Initialize Multi-DEX scanner
        self.multi_dex = MultiDEXScanner(self.kumbaya, self.prismfi)
        logger.info("Multi-DEX scanner initialized")
    
    async def _initialize_components(self) -> None:
        """Initialize core components"""
        # Initialize token monitor
        self.token_monitor = TokenMonitor(self.async_w3)
        await self.token_monitor.start_monitoring()
        logger.info("Token monitor started")
        
        # Initialize sniper executor
        self.sniper_executor = SniperExecutor(self.w3, self.async_w3, self.kumbaya, self.database)
        await self.sniper_executor.start_executor()
        logger.info("Sniper executor started")
        
        # Initialize AI predictor
        self.ai_predictor = AIPredictor(BotConfig.MODEL_PATH)
        logger.info("AI predictor initialized")
        
        # Initialize rate limiter
        self.rate_limiter = RateLimiter(
            BotConfig.REQUESTS_PER_SECOND,
            BotConfig.REQUESTS_PER_MINUTE
        )
        await self.rate_limiter.start_cleanup()
        logger.info("Rate limiter initialized")
    
    async def _initialize_handlers(self) -> None:
        """Initialize handlers"""
        self.command_handler = CmdHandler(self.database, self.ai_predictor)
        self.callback_handler = CallbackHandler(self.database, self.sniper_executor)
        self.wallet_handler = WalletHandler(self.database)
        logger.info("Handlers initialized")
    
    async def _initialize_telegram(self) -> None:
        """Initialize Telegram application"""
        # Create application
        self.application = Application.builder().token(BotConfig.TELEGRAM_TOKEN).build()
        
        # Add bot data to context
        self.application.bot_data.update({
            'database': self.database,
            'kumbaya': self.kumbaya,
            'prismfi': self.prismfi,
            'multi_dex': self.multi_dex,
            'token_monitor': self.token_monitor,
            'sniper_executor': self.sniper_executor,
            'ai_predictor': self.ai_predictor,
            'wallet_handler': self.wallet_handler,
            'rate_limiter': self.rate_limiter
        })
        
        # Add handlers
        # Command handlers
        for handler in self.command_handler.get_handlers():
            self.application.add_handler(handler)
        
        # Callback query handler
        self.application.add_handler(CallbackQueryHandler(self.callback_handler.handle_callback))
        
        # Error handler
        self.application.add_error_handler(self._error_handler)
        
        logger.info("Telegram application initialized")
    
    async def start(self) -> None:
        """Start the bot"""
        try:
            logger.info("Starting Atalanta Bot...")
            
            # Start arbitrage scanner
            await self.multi_dex.start_scanning()
            
            # Start bot polling
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(drop_pending_updates=True)
            
            self.is_running = True
            logger.info("Atalanta Bot started successfully!")
            
            # Wait for shutdown
            await self.shutdown_event.wait()
            
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the bot gracefully"""
        try:
            logger.info("Stopping Atalanta Bot...")
            
            self.is_running = False
            self.shutdown_event.set()
            
            # Stop components
            if self.multi_dex:
                await self.multi_dex.stop_scanning()
            
            if self.token_monitor:
                await self.token_monitor.stop_monitoring()
            
            if self.sniper_executor:
                await self.sniper_executor.stop_executor()
            
            if self.rate_limiter:
                await self.rate_limiter.stop_cleanup()
            
            # Stop Telegram application
            if self.application:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
            
            # Cleanup database
            if self.database:
                await self.database.cleanup_old_data()
            
            logger.info("Atalanta Bot stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")
    
    async def _error_handler(self, update: object, context) -> None:
        """Handle errors"""
        logger.error(f"Exception while handling an update: {context.error}")
        
        # Try to notify user
        if update and hasattr(update, 'effective_chat'):
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ An error occurred. Please try again later."
                )
            except Exception:
                pass
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        try:
            health_status = {
                'status': 'healthy',
                'timestamp': asyncio.get_event_loop().time(),
                'components': {}
            }
            
            # Check database
            try:
                await self.database.get_leaderboard(1)
                health_status['components']['database'] = 'healthy'
            except Exception as e:
                health_status['components']['database'] = f'unhealthy: {e}'
                health_status['status'] = 'degraded'
            
            # Check Web3 connection
            try:
                chain_id = self.w3.eth.chain_id
                health_status['components']['web3'] = f'healthy (chain: {chain_id})'
            except Exception as e:
                health_status['components']['web3'] = f'unhealthy: {e}'
                health_status['status'] = 'degraded'
            
            # Check DEX integrations
            try:
                if await self.kumbaya.get_token_info("0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"):
                    health_status['components']['kumbaya'] = 'healthy'
                else:
                    health_status['components']['kumbaya'] = 'degraded'
                    health_status['status'] = 'degraded'
            except Exception as e:
                health_status['components']['kumbaya'] = f'unhealthy: {e}'
                health_status['status'] = 'degraded'
            
            # Check monitoring services
            if self.token_monitor and self.token_monitor.is_monitoring:
                health_status['components']['token_monitor'] = 'healthy'
            else:
                health_status['components']['token_monitor'] = 'unhealthy'
                health_status['status'] = 'degraded'
            
            if self.sniper_executor and self.sniper_executor.is_executing:
                health_status['components']['sniper_executor'] = 'healthy'
            else:
                health_status['components']['sniper_executor'] = 'unhealthy'
                health_status['status'] = 'degraded'
            
            return health_status
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': asyncio.get_event_loop().time()
            }

async def main():
    """Main entry point"""
    bot = AtalantaBot()
    
    # Setup signal handlers
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(bot.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Initialize and start bot
        await bot.initialize()
        await bot.start()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        # Ensure cleanup
        if bot.is_running:
            await bot.stop()

if __name__ == '__main__':
    # Run the bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        sys.exit(1)
