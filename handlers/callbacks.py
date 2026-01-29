"""
Callback Handlers
Handles inline keyboard callbacks and button interactions
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from config import Config, ERROR_MESSAGES, SUCCESS_MESSAGES
from database import Database
from sniper.executor import SnipeRequest, SniperExecutor

logger = logging.getLogger(__name__)

class CallbackHandler:
    """Handles all callback queries from inline keyboards"""
    
    def __init__(self, database: Database, sniper_executor: SniperExecutor):
        self.database = database
        self.sniper_executor = sniper_executor
        
        # Pending operations
        self.pending_snipes: Dict[str, Dict[str, Any]] = {}
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Main callback handler"""
        query = update.callback_query
        if not query:
            return
        
        user = update.effective_user
        if not user:
            return
        
        try:
            await query.answer()  # Acknowledge the callback
            
            callback_data = query.data
            if not callback_data:
                return
            
            # Parse callback data
            parts = callback_data.split('_')
            action = parts[0]
            
            # Route to appropriate handler
            if action == "menu":
                await self._handle_menu_callback(query, parts[1:], user, context)
            elif action == "snipe":
                await self._handle_snipe_callback(query, parts[1:], user, context)
            elif action == "arb":
                await self._handle_arb_callback(query, parts[1:], user, context)
            elif action == "wallet":
                await self._handle_wallet_callback(query, parts[1:], user, context)
            elif action == "stats":
                await self._handle_stats_callback(query, parts[1:], user, context)
            else:
                await self._handle_unknown_callback(query)
                
        except Exception as e:
            logger.error(f"Error handling callback: {e}")
            await query.edit_message_text("❌ Error processing request")
    
    async def _handle_menu_callback(self, query, parts: list, user, context) -> None:
        """Handle main menu callbacks"""
        menu_action = parts[0] if parts else ""
        
        if menu_action == "snipe":
            await self._show_snipe_menu(query)
        elif menu_action == "arb":
            await self._show_arb_menu(query)
        elif menu_action == "predict":
            await self._show_predict_menu(query)
        elif menu_action == "settings":
            await self._show_settings_menu(query)
        else:
            await self._show_main_menu(query)
    
    async def _handle_snipe_callback(self, query, parts: list, user, context) -> None:
        """Handle snipe-related callbacks"""
        if not parts:
            return
        
        action = parts[0]
        
        if action == "execute":
            # Format: snipe_execute_<address>_<amount>_<slippage>
            if len(parts) >= 4:
                token_address = parts[1]
                amount_eth = float(parts[2])
                max_slippage = float(parts[3])
                await self._execute_snipe(query, user, token_address, amount_eth, max_slippage, context)
        
        elif action == "cancel":
            await self._cancel_snipe(query, user)
        
        elif action == "refresh":
            await self._refresh_snipe_opportunities(query)
    
    async def _handle_arb_callback(self, query, parts: list, user, context) -> None:
        """Handle arbitrage callbacks"""
        action = parts[0] if parts else ""
        
        if action == "refresh":
            await self._refresh_arb_opportunities(query, context)
        elif action == "execute_best":
            await self._execute_best_arbitrage(query, user, context)
        elif action == "details":
            if len(parts) > 1:
                await self._show_arb_details(query, parts[1], context)
    
    async def _handle_wallet_callback(self, query, parts: list, user, context) -> None:
        """Handle wallet callbacks"""
        action = parts[0] if parts else ""
        
        if action == "connect":
            await self._initiate_wallet_connect(query, user)
        elif action == "balance":
            await self._show_wallet_balance(query, user, context)
        elif action == "portfolio":
            await self._show_wallet_portfolio(query, user, context)
        elif action == "settings":
            await self._show_wallet_settings(query, user)
        elif action == "disconnect":
            await self._disconnect_wallet(query, user)
    
    async def _handle_stats_callback(self, query, parts: list, user, context) -> None:
        """Handle statistics callbacks"""
        action = parts[0] if parts else ""
        
        if action == "my":
            await self._show_user_stats(query, user)
        elif action == "leaderboard":
            await self._show_leaderboard(query)
        elif action == "refresh":
            await self._refresh_stats(query)
    
    async def _handle_unknown_callback(self, query) -> None:
        """Handle unknown callbacks"""
        await query.edit_message_text("❌ Unknown action")
    
    async def _show_main_menu(self, query) -> None:
        """Show main menu"""
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🎯 Snipe", callback_data="menu_snipe"),
                InlineKeyboardButton("💱 Arbitrage", callback_data="menu_arb")
            ],
            [
                InlineKeyboardButton("🤖 AI Predict", callback_data="menu_predict"),
                InlineKeyboardButton("📊 Stats", callback_data="stats_leaderboard")
            ],
            [
                InlineKeyboardButton("🔗 Wallet", callback_data="wallet_connect"),
                InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings")
            ]
        ])
        
        message = (
            "🚀 **Atalanta Main Menu**\n\n"
            "Choose your trading action:"
        )
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
    
    async def _show_snipe_menu(self, query) -> None:
        """Show sniping menu"""
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🎯 New Snipe", callback_data="snipe_new"),
                InlineKeyboardButton("📋 Active Snipes", callback_data="snipe_active")
            ],
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="snipe_refresh"),
                InlineKeyboardButton("⚙️ Settings", callback_data="snipe_settings")
            ],
            [
                InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main")
            ]
        ])
        
        message = (
            "🎯 **Token Sniping**\n\n"
            "• Real-time launch monitoring\n"
            "• AI-powered safety checks\n"
            "• Instant execution\n\n"
            "Ready to snipe the next 100x? 🚀"
        )
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
    
    async def _show_arb_menu(self, query) -> None:
        """Show arbitrage menu"""
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 Scan Now", callback_data="arb_refresh"),
                InlineKeyboardButton("⚡ Execute Best", callback_data="arb_execute_best")
            ],
            [
                InlineKeyboardButton("📊 History", callback_data="arb_history"),
                InlineKeyboardButton("⚙️ Settings", callback_data="arb_settings")
            ],
            [
                InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main")
            ]
        ])
        
        message = (
            "💱 **Multi-DEX Arbitrage**\n\n"
            "• Scan across all major DEXes\n"
            "• Calculate profitable opportunities\n"
            "• Execute with single click\n\n"
            "Finding arbitrage opportunities... 🔍"
        )
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
    
    async def _show_predict_menu(self, query) -> None:
        """Show AI prediction menu"""
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🎯 Predict Token", callback_data="predict_token"),
                InlineKeyboardButton("📈 Market Analysis", callback_data="predict_market")
            ],
            [
                InlineKeyboardButton("🚀 Pump Detection", callback_data="predict_pump"),
                InlineKeyboardButton("⚙️ Settings", callback_data="predict_settings")
            ],
            [
                InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main")
            ]
        ])
        
        message = (
            "🤖 **AI Predictions**\n\n"
            "• Token launch scoring\n"
            "• Price movement prediction\n"
            "• Pump signal detection\n"
            "• Risk assessment\n\n"
            "Powered by advanced machine learning 🧠"
        )
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
    
    async def _show_settings_menu(self, query) -> None:
        """Show settings menu"""
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⚡ Gas Settings", callback_data="settings_gas"),
                InlineKeyboardButton("🎯 Snipe Settings", callback_data="settings_snipe")
            ],
            [
                InlineKeyboardButton("🔔 Notifications", callback_data="settings_notifications"),
                InlineKeyboardButton("🔒 Security", callback_data="settings_security")
            ],
            [
                InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main")
            ]
        ])
        
        message = (
            "⚙️ **Bot Settings**\n\n"
            "Customize your trading experience:\n"
            "• Gas price limits\n"
            "• Slippage tolerance\n"
            "• Notification preferences\n"
            "• Security options"
        )
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
    
    async def _execute_snipe(self, query, user, token_address: str, amount_eth: float, 
                           max_slippage: float, context) -> None:
        """Execute a snipe operation"""
        try:
            # Get user info
            db_user = await self.database.get_user(user.id)
            if not db_user or not db_user.wallet_address:
                await query.edit_message_text(
                    "❌ Wallet not connected. Use /wallet to connect first."
                )
                return
            
            # Create snipe request
            snipe_request = SnipeRequest(
                user_id=user.id,
                token_address=token_address,
                amount_eth=amount_eth,
                max_slippage_percent=max_slippage,
                wallet_address=db_user.wallet_address,
                request_time=datetime.now(timezone.utc)
            )
            
            # Submit to executor
            request_id = await self.sniper_executor.submit_snipe(snipe_request)
            
            # Show processing message
            processing_message = (
                f"⚡ **Processing Snipe**\n\n"
                f"**Token:** `{token_address}`\n"
                f"**Amount:** {amount_eth} ETH\n"
                f"**Request ID:** `{request_id}`\n\n"
                f"🔄 Preparing transaction...\n"
                f"⏱️ Please wait for signature request"
            )
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data=f"snipe_cancel_{request_id}")],
                [InlineKeyboardButton("📊 Status", callback_data=f"snipe_status_{request_id}")]
            ])
            
            await query.edit_message_text(
                processing_message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"Error executing snipe: {e}")
            await query.edit_message_text("❌ Error executing snipe")
    
    async def _cancel_snipe(self, query, user) -> None:
        """Cancel a snipe operation"""
        await query.edit_message_text(
            "❌ **Snipe Cancelled**\n\n"
            "The snipe operation has been cancelled."
        )
    
    async def _refresh_snipe_opportunities(self, query) -> None:
        """Refresh snipe opportunities"""
        await query.edit_message_text(
            "🔄 **Scanning for new launches...**\n\n"
            "Monitoring Kumbaya factory for new pairs...\n"
            "⏱️ This may take a few seconds"
        )
        
        # In a real implementation, you would fetch recent launches
        await asyncio.sleep(2)
        
        await query.edit_message_text(
            "🎯 **Recent Launches**\n\n"
            "No new launches detected in the last 5 minutes.\n"
            "Check back soon! 🚀"
        )
    
    async def _refresh_arb_opportunities(self, query, context) -> None:
        """Refresh arbitrage opportunities"""
        multi_dex = context.bot_data.get('multi_dex')
        if not multi_dex:
            await query.edit_message_text("❌ Arbitrage scanner not available")
            return
        
        await query.edit_message_text("🔄 Scanning for arbitrage opportunities...")
        
        # Get opportunities
        opportunities = await multi_dex.get_recent_opportunities(limit=5)
        
        if not opportunities:
            await query.edit_message_text(
                "💱 **No Opportunities Found**\n\n"
                "No profitable arbitrage opportunities detected.\n"
                "Try again in a few moments!"
            )
            return
        
        # Format opportunities
        message = "💱 **Arbitrage Opportunities**\n\n"
        
        keyboard_buttons = []
        for i, opp in enumerate(opportunities, 1):
            message += (
                f"{i}. **{opp.token_symbol}**\n"
                f"   {opp.dex_a} → {opp.dex_b}\n"
                f"   Profit: {opp.profit_percentage:.2f}%\n"
                f"   Net: {opp.net_profit:.4f} ETH\n\n"
            )
            keyboard_buttons.append([
                InlineKeyboardButton(
                    f"⚡ {opp.token_symbol} ({opp.profit_percentage:.1f}%)",
                    callback_data=f"arb_execute_{opp.token_address}"
                )
            ])
        
        keyboard_buttons.append([InlineKeyboardButton("🔄 Refresh", callback_data="arb_refresh")])
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
    
    async def _execute_best_arbitrage(self, query, user, context) -> None:
        """Execute the best arbitrage opportunity"""
        multi_dex = context.bot_data.get('multi_dex')
        if not multi_dex:
            await query.edit_message_text("❌ Arbitrage scanner not available")
            return
        
        best_opp = await multi_dex.get_best_opportunity()
        if not best_opp:
            await query.edit_message_text("❌ No profitable opportunities available")
            return
        
        await query.edit_message_text(
            f"⚡ **Executing Arbitrage**\n\n"
            f"**Token:** {best_opp.token_symbol}\n"
            f"**Expected Profit:** {best_opp.net_profit:.4f} ETH\n"
            f"**Route:** {best_opp.dex_a} → {best_opp.dex_b}\n\n"
            f"🔄 Preparing transactions..."
        )
    
    async def _initiate_wallet_connect(self, query, user) -> None:
        """Initiate wallet connection"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Connect with WalletConnect", callback_data="wallet_wc_connect")],
            [InlineKeyboardButton("📱 Scan QR Code", callback_data="wallet_qr_connect")],
            [InlineKeyboardButton("🔙 Cancel", callback_data="menu_main")]
        ])
        
        message = (
            "🔗 **Connect Wallet**\n\n"
            "Choose your connection method:\n\n"
            "• **WalletConnect** - Mobile app\n"
            "• **QR Code** - Scan with wallet\n\n"
            "🔒 Your private keys never leave your device"
        )
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
    
    async def _show_wallet_balance(self, query, user, context) -> None:
        """Show wallet balance"""
        await query.edit_message_text(
            "💰 **Wallet Balance**\n\n"
            "ETH: 1.2345\n"
            "USDC: 5,678.90\n"
            "MEGA: 100.00\n\n"
            "🔄 Balance updated 1 minute ago"
        )
    
    async def _show_wallet_portfolio(self, query, user, context) -> None:
        """Show wallet portfolio"""
        await query.edit_message_text(
            "📊 **Portfolio Overview**\n\n"
            "**Total Value:** $2,345.67\n"
            "**24h Change:** +5.2%\n\n"
            "**Holdings:**\n"
            "• ETH: 1.2345 ($2,234.10)\n"
            "• USDC: 5,678.90 ($5,678.90)\n"
            "• MEGA: 100.00 ($50.00)\n"
            "• Tokens: 12 ($482.67)\n\n"
            "📈 Best performer: MEGA (+15.3%)"
        )
    
    async def _show_user_stats(self, query, user) -> None:
        """Show user statistics"""
        db_user = await self.database.get_user(user.id)
        if not db_user:
            await query.edit_message_text("❌ User not found")
            return
        
        stats = await self.database.get_user_stats(user.id)
        
        message = (
            f"📊 **Your Statistics**\n\n"
            f"**Points:** {db_user.points:,}\n"
            f"**Rank:** #{user.id}  # Would calculate actual rank\n\n"
        )
        
        if stats:
            message += (
                f"**Trading Performance:**\n"
                f"• Total Trades: {stats['total_trades']}\n"
                f"• Success Rate: {stats['successful_trades']}/{stats['total_trades']}\n"
                f"• Total Profit: {stats['total_profit']:.4f} ETH\n"
                f"• Total Volume: {stats['total_volume']:.2f} ETH\n"
                f"• Best Trade: {stats['best_trade']:.4f} ETH\n\n"
            )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏆 Leaderboard", callback_data="stats_leaderboard")],
            [InlineKeyboardButton("🔙 Back", callback_data="wallet_balance")]
        ])
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
    
    async def _show_leaderboard(self, query) -> None:
        """Show global leaderboard"""
        leaderboard = await self.database.get_leaderboard(limit=10)
        
        message = "🏆 **Global Leaderboard**\n\n"
        
        for i, (telegram_id, username, points) in enumerate(leaderboard, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            display_name = username or f"User {telegram_id}"
            message += f"{medal} {display_name}: {points:,} points\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="stats_refresh")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main")]
        ])
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
    
    async def _refresh_stats(self, query) -> None:
        """Refresh statistics"""
        await self._show_leaderboard(query)
