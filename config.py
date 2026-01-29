"""
Atalanta Bot Configuration
Core constants, contract addresses, and environment loading
"""

import os
from dataclasses import dataclass
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class Config:
    """Bot configuration class"""
    
    # Telegram Configuration
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
    BOT_USERNAME: str = os.getenv("BOT_USERNAME", "AtalantaBot")
    
    # MegaETH Configuration
    MEGAETH_RPC: str = os.getenv("MEGAETH_RPC", "https://rpc.megaeth.com")
    MEGAETH_WS: str = os.getenv("MEGAETH_WS", "wss://ws.megaeth.com")
    CHAIN_ID: int = 534352  # MegaETH chain ID
    
    # Contract Addresses
    KUMBADYA_FACTORY: str = "0x53447989580f541bc138d29A0FcCf72AfbBE1355"
    KUMBADYA_ROUTER: str = "0x8268DC930BA98759E916DEd4c9F367A844814023"
    
    # Additional DEX Addresses (to be updated with actual addresses)
    PRISMFI_ROUTER: str = os.getenv("PRISMFI_ROUTER", "")
    GTE_ROUTER: str = os.getenv("GTE_ROUTER", "")
    VALHALLA_ROUTER: str = os.getenv("VALHALLA_ROUTER", "")
    WARPEXCHANGE_ROUTER: str = os.getenv("WARPEXCHANGE_ROUTER", "")
    
    # Perps Platforms
    VALHALLA_PERPS: str = os.getenv("VALHALLA_PERPS", "")
    GTE_PERPS: str = os.getenv("GTE_PERPS", "")
    
    # Gas Configuration
    DEFAULT_GAS_LIMIT: int = 300000
    MAX_GAS_PRICE: int = int(5e10)  # 50 gwei
    GAS_MULTIPLIER: float = 1.1
    
    # Trading Configuration
    MIN_PROFIT_THRESHOLD: float = 0.005  # 0.5%
    DEFAULT_SLIPPAGE: float = 0.02  # 2%
    MAX_SLIPPAGE: float = 0.1  # 10%
    MIN_TRADE_AMOUNT: float = 0.001  # 0.001 ETH
    
    # Rate Limiting
    REQUESTS_PER_SECOND: int = 10
    REQUESTS_PER_MINUTE: int = 100
    
    # Database Configuration
    DATABASE_PATH: str = "atalanta.db"
    
    # AI Configuration
    MODEL_PATH: str = "models/"
    PREDICTION_CONFIDENCE_THRESHOLD: float = 0.7
    
    # Security Configuration
    WALLETCONNECT_PROJECT_ID: str = os.getenv("WALLETCONNECT_PROJECT_ID", "")
    MAX_WALLET_CONNECTIONS: int = 3
    
    # Gamification
    REFERRAL_COMMISSION: float = 0.2  # 20%
    POINTS_PER_TRADE: int = 10
    POINTS_PER_REFERRAL: int = 50
    
    # Monitoring Configuration
    SCAN_INTERVAL: int = 5  # seconds
    WEBSOCKET_TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = "atalanta.log"
    
    @classmethod
    def validate(cls) -> None:
        """Validate critical configuration"""
        if not cls.TELEGRAM_TOKEN:
            raise ValueError("TELEGRAM_TOKEN is required")
        
        if not cls.MEGAETH_RPC:
            raise ValueError("MEGAETH_RPC is required")
        
        # WalletConnect is optional for now
        if not cls.WALLETCONNECT_PROJECT_ID:
            import logging
            logging.warning("WALLETCONNECT_PROJECT_ID not set - wallet features will be limited")

# ERC-20 ABI (minimal)
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "name",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    }
]

# Uniswap-style Router ABI (minimal)
ROUTER_ABI = [
    {
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "amountOutMin", "type": "uint256"},
            {"name": "path", "type": "address[]"},
            {"name": "to", "type": "address"},
            {"name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactETHForTokens",
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "amountOut", "type": "uint256"},
            {"name": "amountInMax", "type": "uint256"},
            {"name": "path", "type": "address[]"},
            {"name": "to", "type": "address"},
            {"name": "deadline", "type": "uint256"}
        ],
        "name": "swapTokensForExactETH",
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [{"name": "amountIn", "type": "uint256"}, {"name": "path", "type": "address[]"}],
        "name": "getAmountsOut",
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# Factory ABI (minimal)
FACTORY_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "token0", "type": "address"},
            {"indexed": True, "name": "token1", "type": "address"},
            {"indexed": False, "name": "pair", "type": "address"},
            {"indexed": False, "name": "allPairsLength", "type": "uint256"}
        ],
        "name": "PairCreated",
        "type": "event"
    },
    {
        "inputs": [{"name": "tokenA", "type": "address"}, {"name": "tokenB", "type": "address"}],
        "name": "getPair",
        "outputs": [{"name": "pair", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# Pair ABI (minimal)
PAIR_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "getReserves",
        "outputs": [
            {"name": "reserve0", "type": "uint112"},
            {"name": "reserve1", "type": "uint112"},
            {"name": "blockTimestampLast", "type": "uint32"}
        ],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "token0",
        "outputs": [{"name": "", "type": "address"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "token1",
        "outputs": [{"name": "", "type": "address"}],
        "type": "function"
    }
]

# Message templates
WELCOME_MESSAGE = """
🚀 **Welcome to Atalanta - The Ultimate MegaETH Trading Bot!**

*Atalanta is your professional companion for navigating the ultra-fast MegaETH ecosystem with 10ms block times and 100k+ TPS.*

🔥 **Core Features:**
• ⚡ Real-time token launch sniping
• 🔄 Multi-DEX arbitrage scanner  
• 📊 Perps liquidation hunting
• 🤖 AI-powered predictions
• 🎮 Gamification & rewards

📝 **Getting Started:**
/start - Show this welcome message
/snipe <address> [amount] [slippage] - Snipe new tokens
/arb - Scan arbitrage opportunities
/farm - Auto-farm KPI rewards
/predict - AI price predictions
/wallet - Connect your wallet

⚠️ **Security First:**
• No private keys stored
• WalletConnect integration
• All actions require your signature

Join our community and become a MegaETH degen! 🎯
"""

SNIPET_CONFIRMATION_TEMPLATE = """
🎯 **Snipe Confirmation**

**Token:** `{token_symbol}`
**Address:** `{token_address}`
**Amount:** {amount_eth} ETH
**Max Slippage:** {slippage}%

**Quick Checks:**
{checks}

⚡ **Ready to snipe in {time_left}s...**

{buttons}
"""

# Error messages
ERROR_MESSAGES = {
    "invalid_address": "❌ Invalid token address format",
    "insufficient_balance": "❌ Insufficient balance",
    "high_slippage": "⚠️ High slippage detected - proceed with caution",
    "transaction_failed": "❌ Transaction failed",
    "wallet_not_connected": "❌ Wallet not connected. Use /wallet to connect",
    "rate_limit": "⏱️ Rate limit exceeded. Please wait...",
    "network_error": "🔄 Network error. Retrying...",
    "invalid_amount": "❌ Invalid amount format",
    "token_not_found": "❌ Token not found or not tradable"
}

# Success messages
SUCCESS_MESSAGES = {
    "snipe_successful": "🎯 **Snipe Successful!**\n\nBought {amount_tokens} {token_symbol}\nTransaction: {tx_hash}",
    "arbitrage_executed": "💰 **Arbitrage Executed!**\n\nProfit: {profit} ETH\nTransaction: {tx_hash}",
    "wallet_connected": "🔐 **Wallet Connected**\n\nAddress: {address}",
    "position_opened": "📈 **Position Opened**\n\nSize: {size} ETH\nLeverage: {leverage}x"
}

# Inline keyboard templates
KEYBOARD_TEMPLATES = {
    "confirm_snipe": [
        {"text": "⚡ EXECUTE SNIPE", "callback_data": "snipe_execute"},
        {"text": "❌ CANCEL", "callback_data": "snipe_cancel"}
    ],
    "wallet_actions": [
        {"text": "🔗 Connect Wallet", "callback_data": "wallet_connect"},
        {"text": "💰 Balance", "callback_data": "wallet_balance"},
        {"text": "📊 Portfolio", "callback_data": "wallet_portfolio"}
    ],
    "main_menu": [
        {"text": "🎯 Snipe", "callback_data": "menu_snipe"},
        {"text": "💱 Arbitrage", "callback_data": "menu_arb"},
        {"text": "📊 Predict", "callback_data": "menu_predict"},
        {"text": "⚙️ Settings", "callback_data": "menu_settings"}
    ]
}
