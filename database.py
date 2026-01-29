"""
Atalanta Bot Database Layer
SQLite wrapper using aiosqlite for user data, trades, points, and referrals
"""

import sqlite3
import aiosqlite
import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict
import json
import logging

logger = logging.getLogger(__name__)

@dataclass
class User:
    """User data model"""
    telegram_id: int
    username: str
    first_name: str
    wallet_address: Optional[str] = None
    is_premium: bool = False
    points: int = 0
    referral_code: Optional[str] = None
    referred_by: Optional[str] = None
    created_at: datetime = None
    last_active: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.last_active is None:
            self.last_active = datetime.now(timezone.utc)

@dataclass
class Trade:
    """Trade data model"""
    id: Optional[int]
    user_id: int
    token_address: str
    token_symbol: str
    trade_type: str  # 'snipe', 'arbitrage', 'farm', 'manual'
    amount_in: float
    amount_out: float
    token_amount: float
    price_usd: Optional[float]
    gas_used: Optional[int]
    gas_cost: Optional[float]
    tx_hash: str
    status: str  # 'pending', 'completed', 'failed'
    profit_loss: Optional[float]
    created_at: datetime
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

@dataclass
class ArbitrageOpportunity:
    """Arbitrage opportunity data model"""
    id: Optional[int]
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
    
    def __post_init__(self):
        if self.discovered_at is None:
            self.discovered_at = datetime.now(timezone.utc)

@dataclass
class Prediction:
    """AI prediction data model"""
    id: Optional[int]
    token_address: str
    token_symbol: str
    prediction_type: str  # 'price', 'pump', 'rug'
    confidence: float
    prediction_value: float
    actual_value: Optional[float]
    is_correct: Optional[bool]
    created_at: datetime
    resolved_at: Optional[datetime]
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

class Database:
    """Async SQLite database wrapper for Atalanta bot"""
    
    def __init__(self, db_path: str = "atalanta.db"):
        self.db_path = db_path
        self._lock = asyncio.Lock()
        
    async def initialize(self) -> None:
        """Initialize database tables"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        telegram_id INTEGER PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        wallet_address TEXT,
                        is_premium BOOLEAN DEFAULT FALSE,
                        points INTEGER DEFAULT 0,
                        referral_code TEXT UNIQUE,
                        referred_by TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS trades (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        token_address TEXT,
                        token_symbol TEXT,
                        trade_type TEXT,
                        amount_in REAL,
                        amount_out REAL,
                        token_amount REAL,
                        price_usd REAL,
                        gas_used INTEGER,
                        gas_cost REAL,
                        tx_hash TEXT UNIQUE,
                        status TEXT,
                        profit_loss REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (telegram_id)
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS arbitrage_opportunities (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        token_address TEXT,
                        token_symbol TEXT,
                        dex_a TEXT,
                        dex_b TEXT,
                        price_a REAL,
                        price_b REAL,
                        profit_percentage REAL,
                        gas_estimate REAL,
                        net_profit REAL,
                        is_executable BOOLEAN,
                        discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS predictions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        token_address TEXT,
                        token_symbol TEXT,
                        prediction_type TEXT,
                        confidence REAL,
                        prediction_value REAL,
                        actual_value REAL,
                        is_correct BOOLEAN,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        resolved_at TIMESTAMP
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS user_stats (
                        user_id INTEGER PRIMARY KEY,
                        total_trades INTEGER DEFAULT 0,
                        successful_trades INTEGER DEFAULT 0,
                        total_profit REAL DEFAULT 0,
                        total_volume REAL DEFAULT 0,
                        best_trade REAL DEFAULT 0,
                        avg_slippage REAL DEFAULT 0,
                        FOREIGN KEY (user_id) REFERENCES users (telegram_id)
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS bot_stats (
                        stat_key TEXT PRIMARY KEY,
                        stat_value TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for performance
                await db.execute("CREATE INDEX IF NOT EXISTS idx_trades_user_id ON trades(user_id)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_trades_token_address ON trades(token_address)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_trades_created_at ON trades(created_at)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_predictions_token_address ON predictions(token_address)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_arbitrage_discovered_at ON arbitrage_opportunities(discovered_at)")
                
                await db.commit()
                logger.info("Database initialized successfully")
    
    async def create_user(self, user: User) -> bool:
        """Create a new user"""
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute("""
                        INSERT INTO users 
                        (telegram_id, username, first_name, wallet_address, is_premium, points, 
                         referral_code, referred_by, created_at, last_active)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        user.telegram_id, user.username, user.first_name, user.wallet_address,
                        user.is_premium, user.points, user.referral_code, user.referred_by,
                        user.created_at, user.last_active
                    ))
                    
                    # Initialize user stats
                    await db.execute("""
                        INSERT INTO user_stats (user_id, total_trades, successful_trades, 
                                              total_profit, total_volume, best_trade, avg_slippage)
                        VALUES (?, 0, 0, 0, 0, 0, 0)
                    """, (user.telegram_id,))
                    
                    await db.commit()
                    return True
        except sqlite3.IntegrityError as e:
            logger.warning(f"User already exists: {user.telegram_id} - {e}")
            return False
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return False
    
    async def get_user(self, telegram_id: int) -> Optional[User]:
        """Get user by telegram ID"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT * FROM users WHERE telegram_id = ?",
                    (telegram_id,)
                )
                row = await cursor.fetchone()
                
                if row:
                    return User(
                        telegram_id=row['telegram_id'],
                        username=row['username'],
                        first_name=row['first_name'],
                        wallet_address=row['wallet_address'],
                        is_premium=bool(row['is_premium']),
                        points=row['points'],
                        referral_code=row['referral_code'],
                        referred_by=row['referred_by'],
                        created_at=datetime.fromisoformat(row['created_at']),
                        last_active=datetime.fromisoformat(row['last_active'])
                    )
                return None
        except Exception as e:
            logger.error(f"Error getting user {telegram_id}: {e}")
            return None
    
    async def update_user(self, user: User) -> bool:
        """Update user data"""
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute("""
                        UPDATE users SET 
                            username = ?, first_name = ?, wallet_address = ?, 
                            is_premium = ?, points = ?, last_active = ?
                        WHERE telegram_id = ?
                    """, (
                        user.username, user.first_name, user.wallet_address,
                        user.is_premium, user.points, user.last_active,
                        user.telegram_id
                    ))
                    await db.commit()
                    return True
        except Exception as e:
            logger.error(f"Error updating user {user.telegram_id}: {e}")
            return False
    
    async def add_points(self, telegram_id: int, points: int) -> bool:
        """Add points to user"""
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute(
                        "UPDATE users SET points = points + ? WHERE telegram_id = ?",
                        (points, telegram_id)
                    )
                    await db.commit()
                    return True
        except Exception as e:
            logger.error(f"Error adding points to user {telegram_id}: {e}")
            return False
    
    async def create_trade(self, trade: Trade) -> Optional[int]:
        """Create a new trade record"""
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute("""
                        INSERT INTO trades 
                        (user_id, token_address, token_symbol, trade_type, amount_in, amount_out,
                         token_amount, price_usd, gas_used, gas_cost, tx_hash, status, profit_loss)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        trade.user_id, trade.token_address, trade.token_symbol, trade.trade_type,
                        trade.amount_in, trade.amount_out, trade.token_amount, trade.price_usd,
                        trade.gas_used, trade.gas_cost, trade.tx_hash, trade.status, trade.profit_loss
                    ))
                    await db.commit()
                    return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error creating trade: {e}")
            return None
    
    async def update_trade_status(self, tx_hash: str, status: str, 
                                 profit_loss: Optional[float] = None) -> bool:
        """Update trade status and profit/loss"""
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    if profit_loss is not None:
                        await db.execute("""
                            UPDATE trades SET status = ?, profit_loss = ?
                            WHERE tx_hash = ?
                        """, (status, profit_loss, tx_hash))
                    else:
                        await db.execute(
                            "UPDATE trades SET status = ? WHERE tx_hash = ?",
                            (status, tx_hash)
                        )
                    await db.commit()
                    return True
        except Exception as e:
            logger.error(f"Error updating trade status {tx_hash}: {e}")
            return False
    
    async def get_user_trades(self, telegram_id: int, limit: int = 50) -> List[Trade]:
        """Get user's trade history"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("""
                    SELECT * FROM trades 
                    WHERE user_id = ? 
                    ORDER BY created_at DESC 
                    LIMIT ?
                """, (telegram_id, limit))
                
                trades = []
                async for row in cursor:
                    trade = Trade(
                        id=row['id'],
                        user_id=row['user_id'],
                        token_address=row['token_address'],
                        token_symbol=row['token_symbol'],
                        trade_type=row['trade_type'],
                        amount_in=row['amount_in'],
                        amount_out=row['amount_out'],
                        token_amount=row['token_amount'],
                        price_usd=row['price_usd'],
                        gas_used=row['gas_used'],
                        gas_cost=row['gas_cost'],
                        tx_hash=row['tx_hash'],
                        status=row['status'],
                        profit_loss=row['profit_loss'],
                        created_at=datetime.fromisoformat(row['created_at'])
                    )
                    trades.append(trade)
                return trades
        except Exception as e:
            logger.error(f"Error getting trades for user {telegram_id}: {e}")
            return []
    
    async def save_arbitrage_opportunity(self, opp: ArbitrageOpportunity) -> Optional[int]:
        """Save arbitrage opportunity"""
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute("""
                        INSERT INTO arbitrage_opportunities 
                        (token_address, token_symbol, dex_a, dex_b, price_a, price_b,
                         profit_percentage, gas_estimate, net_profit, is_executable)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        opp.token_address, opp.token_symbol, opp.dex_a, opp.dex_b,
                        opp.price_a, opp.price_b, opp.profit_percentage,
                        opp.gas_estimate, opp.net_profit, opp.is_executable
                    ))
                    await db.commit()
                    return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error saving arbitrage opportunity: {e}")
            return None
    
    async def get_recent_arbitrage_opportunities(self, hours: int = 1) -> List[ArbitrageOpportunity]:
        """Get recent arbitrage opportunities"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("""
                    SELECT * FROM arbitrage_opportunities 
                    WHERE discovered_at > datetime('now', '-{} hours')
                    ORDER BY discovered_at DESC
                """.format(hours))
                
                opportunities = []
                async for row in cursor:
                    opp = ArbitrageOpportunity(
                        id=row['id'],
                        token_address=row['token_address'],
                        token_symbol=row['token_symbol'],
                        dex_a=row['dex_a'],
                        dex_b=row['dex_b'],
                        price_a=row['price_a'],
                        price_b=row['price_b'],
                        profit_percentage=row['profit_percentage'],
                        gas_estimate=row['gas_estimate'],
                        net_profit=row['net_profit'],
                        is_executable=bool(row['is_executable']),
                        discovered_at=datetime.fromisoformat(row['discovered_at'])
                    )
                    opportunities.append(opp)
                return opportunities
        except Exception as e:
            logger.error(f"Error getting recent arbitrage opportunities: {e}")
            return []
    
    async def save_prediction(self, prediction: Prediction) -> Optional[int]:
        """Save AI prediction"""
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute("""
                        INSERT INTO predictions 
                        (token_address, token_symbol, prediction_type, confidence, prediction_value,
                         actual_value, is_correct, created_at, resolved_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        prediction.token_address, prediction.token_symbol, prediction.prediction_type,
                        prediction.confidence, prediction.prediction_value, prediction.actual_value,
                        prediction.is_correct, prediction.created_at, prediction.resolved_at
                    ))
                    await db.commit()
                    return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error saving prediction: {e}")
            return None
    
    async def get_leaderboard(self, limit: int = 10) -> List[Tuple[int, str, int]]:
        """Get top users by points"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT telegram_id, username, points 
                    FROM users 
                    ORDER BY points DESC 
                    LIMIT ?
                """, (limit,))
                
                leaderboard = []
                async for row in cursor:
                    leaderboard.append((row['telegram_id'], row['username'], row['points']))
                return leaderboard
        except Exception as e:
            logger.error(f"Error getting leaderboard: {e}")
            return []
    
    async def get_user_stats(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Get user trading statistics"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("""
                    SELECT * FROM user_stats WHERE user_id = ?
                """, (telegram_id,))
                
                row = await cursor.fetchone()
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"Error getting user stats {telegram_id}: {e}")
            return None
    
    async def update_user_stats(self, telegram_id: int, **kwargs) -> bool:
        """Update user statistics"""
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
                    values = list(kwargs.values()) + [telegram_id]
                    
                    await db.execute(f"""
                        UPDATE user_stats SET {set_clause} WHERE user_id = ?
                    """, values)
                    await db.commit()
                    return True
        except Exception as e:
            logger.error(f"Error updating user stats {telegram_id}: {e}")
            return False
    
    async def cleanup_old_data(self, days: int = 30) -> int:
        """Clean up old data (arbitrage opportunities, etc.)"""
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute("""
                        DELETE FROM arbitrage_opportunities 
                        WHERE discovered_at < datetime('now', '-{} days')
                    """.format(days))
                    
                    deleted_count = cursor.rowcount
                    await db.commit()
                    logger.info(f"Cleaned up {deleted_count} old arbitrage opportunities")
                    return deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
            return 0
