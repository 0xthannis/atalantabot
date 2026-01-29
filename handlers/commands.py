"""
Command Handlers
Handles all Telegram bot commands
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler as TelegramCommandHandler, MessageHandler, filters
from telegram.constants import ParseMode

from config import Config, WELCOME_MESSAGE, ERROR_MESSAGES, SUCCESS_MESSAGES, KEYBOARD_TEMPLATES
from database import Database, User, Trade
from ai.predictor import AIPredictor, TokenFeatures
from utils.formatting import format_number, format_address, format_time_ago

logger = logging.getLogger(__name__)

class CommandHandler:
    """Handles all bot commands"""
    
    def __init__(self, database: Database, ai_predictor: AIPredictor):
        self.database = database
        self.ai_predictor = ai_predictor
        
        # Rate limiting
        self.user_last_command: Dict[int, datetime] = {}
        self.command_cooldown = 1.0  # seconds
    
    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        user = update.effective_user
        if not user:
            return
        
        try:
            # Create or update user
            db_user = await self.database.get_user(user.id)
            if not db_user:
                new_user = User(
                    telegram_id=user.id,
                    username=user.username or "",
                    first_name=user.first_name or ""
                )
                await self.database.create_user(new_user)
            else:
                # Update last active
                db_user.last_active = datetime.now(timezone.utc)
                await self.database.update_user(db_user)
            
            # Send welcome message
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎯 Start Sniping", callback_data="menu_snipe")],
                [InlineKeyboardButton("💱 Arbitrage", callback_data="menu_arb")],
                [InlineKeyboardButton("🔗 Connect Wallet", callback_data="wallet_connect")],
                [InlineKeyboardButton("📊 My Stats", callback_data="stats_my")]
            ])
            
            await update.message.reply_text(
                WELCOME_MESSAGE,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"Error in start command: {e}")
            await update.message.reply_text("❌ Error starting bot. Please try again.")
    
    async def handle_snipe(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /snipe command"""
        user = update.effective_user
        if not user:
            return
        
        try:
            # Check rate limit
            if not await self._check_rate_limit(user.id):
                await update.message.reply_text(ERROR_MESSAGES["rate_limit"])
                return
            
            # Parse command arguments
            args = context.args
            if len(args) < 1:
                await update.message.reply_text(
                    "🎯 **Snipe Command Usage:**\n\n"
                    "`/snipe <token_address> [amount_eth] [slippage%]`\n\n"
                    "**Examples:**\n"
                    "`/snipe 0x1234... 0.1 2`\n"
                    "`/snipe 0x5678... 0.05`",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            token_address = args[0]
            amount_eth = float(args[1]) if len(args) > 1 else 0.1
            max_slippage = float(args[2]) if len(args) > 2 else Config.DEFAULT_SLIPPAGE * 100
            
            # Validate inputs
            if not self._is_valid_address(token_address):
                await update.message.reply_text(ERROR_MESSAGES["invalid_address"])
                return
            
            if amount_eth < Config.MIN_TRADE_AMOUNT:
                await update.message.reply_text(ERROR_MESSAGES["invalid_amount"])
                return
            
            if max_slippage > Config.MAX_SLIPPAGE * 100:
                await update.message.reply_text(ERROR_MESSAGES["high_slippage"])
                return
            
            # Get user info
            db_user = await self.database.get_user(user.id)
            if not db_user or not db_user.wallet_address:
                await update.message.reply_text(ERROR_MESSAGES["wallet_not_connected"])
                return
            
            # Get token info
            from ..dex.kumbaya import KumbayaDEX
            kumbaya = context.bot_data.get('kumbaya')
            if not kumbaya:
                await update.message.reply_text("❌ DEX not available")
                return
            
            token_info = await kumbaya.get_token_info(token_address)
            if not token_info:
                await update.message.reply_text(ERROR_MESSAGES["token_not_found"])
                return
            
            # Perform AI analysis
            features = await self._gather_token_features(token_address, kumbaya)
            ai_score = await self.ai_predictor.score_token_launch(features)
            
            # Perform safety checks
            honeypot_check = await kumbaya.simulate_honeypot(token_address)
            liquidity_check = await kumbaya.check_liquidity(token_address, amount_eth * 0.5)
            
            # Build confirmation message
            checks = []
            if honeypot_check.get('is_honeypot'):
                checks.append("⚠️ **Potential Honeypot Detected**")
            else:
                checks.append("✅ **Honeypot Check Passed**")
            
            if liquidity_check:
                checks.append("✅ **Sufficient Liquidity**")
            else:
                checks.append("⚠️ **Low Liquidity**")
            
            checks.append(f"🤖 **AI Score:** {ai_score.prediction_value:.1f}/100 ({ai_score.confidence:.1%} confidence)")
            
            # Create confirmation keyboard
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "⚡ EXECUTE SNIPE",
                        callback_data=f"snipe_execute_{token_address}_{amount_eth}_{max_slippage}"
                    ),
                    InlineKeyboardButton("❌ CANCEL", callback_data="snipe_cancel")
                ]
            ])
            
            message = (
                f"🎯 **Snipe Confirmation**\n\n"
                f"**Token:** `{token_info['symbol']}`\n"
                f"**Address:** `{format_address(token_address)}`\n"
                f"**Amount:** {amount_eth} ETH\n"
                f"**Max Slippage:** {max_slippage}%\n\n"
                f"**Quick Checks:**\n"
                + "\n".join(checks) +
                f"\n\n⚡ **Ready to execute...**"
            )
            
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
            
        except ValueError as e:
            await update.message.reply_text(ERROR_MESSAGES["invalid_amount"])
        except Exception as e:
            logger.error(f"Error in snipe command: {e}")
            await update.message.reply_text("❌ Error processing snipe command")
    
    async def handle_arb(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /arb command"""
        user = update.effective_user
        if not user:
            return
        
        try:
            # Get arbitrage scanner
            multi_dex = context.bot_data.get('multi_dex')
            if not multi_dex:
                await update.message.reply_text("❌ Arbitrage scanner not available")
                return
            
            # Get recent opportunities
            opportunities = await multi_dex.get_recent_opportunities(limit=10)
            
            if not opportunities:
                await update.message.reply_text(
                    "🔄 **No Arbitrage Opportunities Found**\n\n"
                    "Scanning for profitable opportunities across DEXes...\n"
                    "Check back in a few moments!"
                )
                return
            
            # Format opportunities
            message = "💱 **Recent Arbitrage Opportunities**\n\n"
            
            for i, opp in enumerate(opportunities[:5], 1):
                message += (
                    f"{i}. **{opp.token_symbol}**\n"
                    f"   Buy: {opp.dex_a} → Sell: {opp.dex_b}\n"
                    f"   Profit: {opp.profit_percentage:.2f}%\n"
                    f"   Net: {opp.net_profit:.4f} ETH\n"
                    f"   Status: {'✅ Executable' if opp.is_executable else '❌ Not executable'}\n\n"
                )
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh", callback_data="arb_refresh")],
                [InlineKeyboardButton("⚡ Execute Best", callback_data="arb_execute_best")]
            ])
            
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"Error in arb command: {e}")
            await update.message.reply_text("❌ Error fetching arbitrage opportunities")
    
    async def handle_predict(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /predict command"""
        user = update.effective_user
        if not user:
            return
        
        try:
            args = context.args
            if len(args) < 1:
                await update.message.reply_text(
                    "🤖 **AI Prediction Command:**\n\n"
                    "`/predict <token_address>`\n\n"
                    "Get AI-powered analysis and predictions for any token."
                )
                return
            
            token_address = args[0]
            if not self._is_valid_address(token_address):
                await update.message.reply_text(ERROR_MESSAGES["invalid_address"])
                return
            
            # Get DEX instance
            kumbaya = context.bot_data.get('kumbaya')
            if not kumbaya:
                await update.message.reply_text("❌ DEX not available")
                return
            
            # Get token info
            token_info = await kumbaya.get_token_info(token_address)
            if not token_info:
                await update.message.reply_text(ERROR_MESSAGES["token_not_found"])
                return
            
            # Gather features and make predictions
            features = await self._gather_token_features(token_address, kumbaya)
            
            # Multiple predictions
            launch_score = await self.ai_predictor.score_token_launch(features)
            
            # Simulate price prediction (would need historical data in production)
            price_prediction = await self.ai_predictor.predict_price_movement(
                token_address, [1.0, 1.1, 1.05, 1.15, 1.12]  # Sample data
            )
            
            # Simulate pump detection
            pump_signal = await self.ai_predictor.detect_pump_signals(token_address, [])
            
            # Format results
            message = (
                f"🤖 **AI Analysis for {token_info['symbol']}**\n\n"
                f"**Address:** `{format_address(token_address)}`\n\n"
                f"📊 **Launch Score:** {launch_score.prediction_value:.1f}/100\n"
                f"   Confidence: {launch_score.confidence:.1%}\n\n"
                f"📈 **Price Prediction:** {price_prediction.prediction_value:+.2f}%\n"
                f"   Confidence: {price_prediction.confidence:.1%}\n\n"
                f"🚀 **Pump Signal:** {pump_signal.prediction_value:.1f}/100\n"
                f"   Confidence: {pump_signal.confidence:.1%}\n\n"
                f"**Key Features:**\n"
                f"• Liquidity: {features.liquidity_eth:.2f} ETH\n"
                f"• Holders: {features.holder_count}\n"
                f"• 24h Transactions: {features.transaction_count_24h}\n"
                f"• Buy/Sell Ratio: {features.buy_sell_ratio:.2f}\n"
                f"• Honeypot Risk: {features.honeypot_score:.2f}"
            )
            
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Error in predict command: {e}")
            await update.message.reply_text("❌ Error generating prediction")
    
    async def handle_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /wallet command"""
        user = update.effective_user
        if not user:
            return
        
        try:
            db_user = await self.database.get_user(user.id)
            if not db_user:
                await update.message.reply_text("❌ User not found. Please use /start first.")
                return
            
            if not db_user.wallet_address:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗 Connect Wallet", callback_data="wallet_connect")]
                ])
                await update.message.reply_text(
                    "💼 **Wallet Not Connected**\n\n"
                    "Connect your wallet to start trading:",
                    reply_markup=keyboard
                )
                return
            
            # Get user stats
            stats = await self.database.get_user_stats(user.id)
            trades = await self.database.get_user_trades(user.id, limit=5)
            
            message = (
                f"💼 **Wallet Information**\n\n"
                f"**Address:** `{format_address(db_user.wallet_address)}`\n"
                f"**Status:** {'🟢 Connected' if db_user.wallet_address else '🔴 Not Connected'}\n"
                f"**Premium:** {'✅ Yes' if db_user.is_premium else '❌ No'}\n"
                f"**Points:** {db_user.points:,}\n\n"
            )
            
            if stats:
                message += (
                    f"📊 **Trading Stats:**\n"
                    f"• Total Trades: {stats['total_trades']}\n"
                    f"• Success Rate: {stats['successful_trades']}/{stats['total_trades']}\n"
                    f"• Total Profit: {stats['total_profit']:.4f} ETH\n"
                    f"• Total Volume: {stats['total_volume']:.2f} ETH\n\n"
                )
            
            if trades:
                message += "📈 **Recent Trades:**\n"
                for trade in trades[:3]:
                    status_emoji = "✅" if trade.status == "completed" else "⏳" if trade.status == "pending" else "❌"
                    message += f"• {status_emoji} {trade.token_symbol} - {trade.amount_in:.3f} ETH\n"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Portfolio", callback_data="wallet_portfolio")],
                [InlineKeyboardButton("⚙️ Settings", callback_data="wallet_settings")]
            ])
            
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"Error in wallet command: {e}")
            await update.message.reply_text("❌ Error fetching wallet information")
    
    async def handle_farm(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /farm command"""
        await update.message.reply_text(
            "🌾 **KPI Farming**\n\n"
            "Auto-farming features coming soon!\n\n"
            "• Adaptive DCA strategies\n"
            "• Volume generation for rewards\n"
            "• Milestone tracking\n"
            "• Gas optimization\n\n"
            "Stay tuned for updates! 🚀"
        )
    
    async def handle_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /stats command"""
        user = update.effective_user
        if not user:
            return
        
        try:
            # Get global leaderboard
            leaderboard = await self.database.get_leaderboard(limit=10)
            
            message = "🏆 **Global Leaderboard**\n\n"
            
            for i, (telegram_id, username, points) in enumerate(leaderboard, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                display_name = username or f"User {telegram_id}"
                message += f"{medal} {display_name}: {points:,} points\n"
            
            # Get user's rank
            db_user = await self.database.get_user(user.id)
            if db_user:
                user_rank = next((i for i, (tid, _, _) in enumerate(leaderboard, 1) if tid == user.id), None)
                if user_rank:
                    message += f"\n🎯 **Your Rank:** #{user_rank} with {db_user.points:,} points"
                else:
                    message += f"\n🎯 **Your Points:** {db_user.points:,}"
            
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Error in stats command: {e}")
            await update.message.reply_text("❌ Error fetching statistics")
    
    async def handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command"""
        help_text = (
            "🤖 **Atalanta Bot Help**\n\n"
            "**Commands:**\n"
            "/start - Start the bot and show main menu\n"
            "/snipe <address> [amount] [slippage] - Snipe new tokens\n"
            "/arb - Show arbitrage opportunities\n"
            "/predict <address> - Get AI predictions\n"
            "/wallet - Manage your wallet\n"
            "/farm - KPI farming features\n"
            "/stats - Global leaderboard\n"
            "/help - Show this help message\n\n"
            "**Features:**\n"
            "• ⚡ Real-time token sniping\n"
            "• 💱 Multi-DEX arbitrage\n"
            "• 🤖 AI-powered predictions\n"
            "• 🔒 Secure wallet connection\n"
            "• 🎮 Gamification & rewards\n\n"
            "**Security:**\n"
            "• No private keys stored\n"
            "• WalletConnect integration\n"
            "• All actions require your signature\n\n"
            "Need help? Contact support! 📞"
        )
        
        await update.message.reply_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def _check_rate_limit(self, user_id: int) -> bool:
        """Check if user is rate limited"""
        now = datetime.now(timezone.utc)
        last_command = self.user_last_command.get(user_id)
        
        if last_command and (now - last_command).total_seconds() < self.command_cooldown:
            return False
        
        self.user_last_command[user_id] = now
        return True
    
    def _is_valid_address(self, address: str) -> bool:
        """Check if address is valid Ethereum address"""
        try:
            return len(address) == 42 and address.startswith('0x')
        except:
            return False
    
    async def _gather_token_features(self, token_address: str, kumbaya) -> TokenFeatures:
        """Gather features for AI analysis"""
        try:
            # Get basic token info
            token_info = await kumbaya.get_token_info(token_address)
            
            # Get liquidity
            liquidity = await kumbaya.get_pair_liquidity(
                await kumbaya.get_pair_address(token_address)
            ) if await kumbaya.get_pair_address(token_address) else 0
            
            # Simulate other features (would need real data sources in production)
            features = TokenFeatures(
                token_address=token_address,
                liquidity_eth=liquidity,
                holder_count=150,  # Placeholder
                transaction_count_24h=500,  # Placeholder
                buy_sell_ratio=1.2,  # Placeholder
                price_volatility=0.15,  # Placeholder
                dev_wallet_balance=5.0,  # Placeholder
                contract_age_hours=24.0,  # Placeholder
                honeypot_score=0.1,  # Placeholder
                social_mentions=50  # Placeholder
            )
            
            return features
            
        except Exception as e:
            logger.error(f"Error gathering token features: {e}")
            # Return default features
            return TokenFeatures(
                token_address=token_address,
                liquidity_eth=0,
                holder_count=0,
                transaction_count_24h=0,
                buy_sell_ratio=1.0,
                price_volatility=0.5,
                dev_wallet_balance=0,
                contract_age_hours=0,
                honeypot_score=0.5,
                social_mentions=0
            )
    
    def get_handlers(self) -> List:
        """Get all command handlers"""
        return [
            TelegramCommandHandler("start", self.handle_start),
            TelegramCommandHandler("snipe", self.handle_snipe),
            TelegramCommandHandler("arb", self.handle_arb),
            TelegramCommandHandler("predict", self.handle_predict),
            TelegramCommandHandler("wallet", self.handle_wallet),
            TelegramCommandHandler("farm", self.handle_farm),
            TelegramCommandHandler("stats", self.handle_stats),
            TelegramCommandHandler("help", self.handle_help),
        ]
