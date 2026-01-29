"""
Formatting Utilities
Helper functions for formatting numbers, addresses, and messages
"""

import re
from typing import Union, Optional
from datetime import datetime, timezone
import math

def format_number(number: Union[int, float], decimals: int = 4, suffix: str = "") -> str:
    """Format number with appropriate decimal places and suffixes"""
    try:
        if number == 0:
            return f"0{suffix}"
        
        # Handle very large numbers with suffixes
        abs_number = abs(number)
        
        if abs_number >= 1e9:
            formatted = f"{number / 1e9:.{decimals}f}B{suffix}"
        elif abs_number >= 1e6:
            formatted = f"{number / 1e6:.{decimals}f}M{suffix}"
        elif abs_number >= 1e3:
            formatted = f"{number / 1e3:.{decimals}f}K{suffix}"
        else:
            # For small numbers, show appropriate decimals
            if abs_number < 0.001:
                formatted = f"{number:.8f}{suffix}"
            elif abs_number < 0.01:
                formatted = f"{number:.6f}{suffix}"
            elif abs_number < 1:
                formatted = f"{number:.4f}{suffix}"
            else:
                formatted = f"{number:.{decimals}f}{suffix}"
        
        # Remove trailing zeros
        formatted = formatted.rstrip('0').rstrip('.') if '.' in formatted else formatted
        
        return formatted
        
    except (ValueError, TypeError):
        return f"0{suffix}"

def format_address(address: str, length: int = 8) -> str:
    """Format Ethereum address with truncation"""
    try:
        if not address or len(address) < 10:
            return address
        
        # Remove 0x prefix if present
        clean_address = address[2:] if address.startswith('0x') else address
        
        # Truncate and format
        if len(clean_address) <= length * 2:
            return f"0x{clean_address}"
        
        return f"0x{clean_address[:length]}...{clean_address[-length:]}"
        
    except Exception:
        return address

def format_time_ago(dt: datetime, reference: Optional[datetime] = None) -> str:
    """Format datetime as "time ago" string"""
    try:
        if reference is None:
            reference = datetime.now(timezone.utc)
        
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        
        delta = reference - dt
        seconds = delta.total_seconds()
        
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
        elif seconds < 2592000:
            weeks = int(seconds / 604800)
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        elif seconds < 31536000:
            months = int(seconds / 2592000)
            return f"{months} month{'s' if months != 1 else ''} ago"
        else:
            years = int(seconds / 31536000)
            return f"{years} year{'s' if years != 1 else ''} ago"
            
    except Exception:
        return "unknown time"

def truncate_string(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """Truncate string to maximum length"""
    try:
        if not text or len(text) <= max_length:
            return text
        
        return text[:max_length - len(suffix)] + suffix
        
    except Exception:
        return text

def format_percentage(value: float, decimals: int = 2) -> str:
    """Format percentage with appropriate formatting"""
    try:
        if abs(value) < 0.01:
            return f"{value:.4f}%"
        elif abs(value) < 1:
            return f"{value:.3f}%"
        else:
            return f"{value:.{decimals}f}%"
    except Exception:
        return "0.00%"

def format_gas_price(gas_price: int) -> str:
    """Format gas price from wei to gwei"""
    try:
        gwei = gas_price / 1e9
        return f"{gwei:.1f} gwei"
    except Exception:
        return "0 gwei"

def format_eth_amount(wei_amount: int) -> str:
    """Format ETH amount from wei to ETH"""
    try:
        eth = wei_amount / 1e18
        return format_number(eth, decimals=6, suffix=" ETH")
    except Exception:
        return "0 ETH"

def format_token_amount(amount: int, decimals: int = 18, symbol: str = "") -> str:
    """Format token amount with proper decimals"""
    try:
        if decimals == 0:
            formatted = f"{amount:,}"
        else:
            formatted = f"{amount / 10**decimals:.{min(6, decimals)}f}"
            # Remove trailing zeros
            formatted = formatted.rstrip('0').rstrip('.') if '.' in formatted else formatted
        
        if symbol:
            return f"{formatted} {symbol}"
        return formatted
        
    except Exception:
        return "0"

def format_price(price: float, currency: str = "ETH") -> str:
    """Format price with currency"""
    try:
        if abs(price) < 0.001:
            return f"{price:.8f} {currency}"
        elif abs(price) < 0.01:
            return f"{price:.6f} {currency}"
        elif abs(price) < 1:
            return f"{price:.4f} {currency}"
        else:
            return f"{price:.6f} {currency}"
    except Exception:
        return f"0 {currency}"

def format_transaction_hash(tx_hash: str, length: int = 6) -> str:
    """Format transaction hash with truncation"""
    try:
        if not tx_hash or len(tx_hash) < 10:
            return tx_hash
        
        clean_hash = tx_hash[2:] if tx_hash.startswith('0x') else tx_hash
        
        if len(clean_hash) <= length * 2:
            return f"0x{clean_hash}"
        
        return f"0x{clean_hash[:length]}...{clean_hash[-length:]}"
        
    except Exception:
        return tx_hash

def format_slippage(slippage_percent: float) -> str:
    """Format slippage percentage with color indicators"""
    try:
        formatted = f"{slippage_percent:.2f}%"
        
        if slippage_percent > 5:
            return f"🔴 {formatted}"
        elif slippage_percent > 2:
            return f"🟡 {formatted}"
        else:
            return f"🟢 {formatted}"
            
    except Exception:
        return "0.00%"

def format_profit_loss(profit_loss: float) -> str:
    """Format profit/loss with appropriate indicators"""
    try:
        if profit_loss > 0:
            return f"🟢 +{format_number(profit_loss, 4)} ETH"
        elif profit_loss < 0:
            return f"🔴 {format_number(profit_loss, 4)} ETH"
        else:
            return f"⚪ {format_number(profit_loss, 4)} ETH"
            
    except Exception:
        return "0 ETH"

def format_confidence(confidence: float) -> str:
    """Format confidence score with visual indicator"""
    try:
        percentage = confidence * 100
        
        if percentage >= 80:
            emoji = "🟢"
        elif percentage >= 60:
            emoji = "🟡"
        elif percentage >= 40:
            emoji = "🟠"
        else:
            emoji = "🔴"
        
        return f"{emoji} {percentage:.1f}%"
        
    except Exception:
        return "🔴 0.0%"

def format_liquidity(liquidity_eth: float) -> str:
    """Format liquidity with appropriate scaling"""
    try:
        if liquidity_eth < 0.01:
            return f"🔴 Low ({format_number(liquidity_eth, 4)} ETH)"
        elif liquidity_eth < 0.1:
            return f"🟡 Medium ({format_number(liquidity_eth, 4)} ETH)"
        elif liquidity_eth < 1:
            return f"🟢 Good ({format_number(liquidity_eth, 4)} ETH)"
        else:
            return f"🔥 High ({format_number(liquidity_eth, 2)} ETH)"
            
    except Exception:
        return "0 ETH"

def format_trade_status(status: str) -> str:
    """Format trade status with emoji"""
    status_emojis = {
        'pending': '⏳',
        'completed': '✅',
        'failed': '❌',
        'cancelled': '🚫'
    }
    
    emoji = status_emojis.get(status.lower(), '❓')
    return f"{emoji} {status.title()}"

def format_rank(rank: int) -> str:
    """Format rank with medal emojis"""
    if rank == 1:
        return "🥇"
    elif rank == 2:
        return "🥈"
    elif rank == 3:
        return "🥉"
    else:
        return f"#{rank}"

def format_duration(seconds: float) -> str:
    """Format duration in seconds to human readable format"""
    try:
        if seconds < 1:
            return f"{seconds*1000:.0f}ms"
        elif seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes}m {int(seconds % 60)}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"
            
    except Exception:
        return "0s"

def bold_text(text: str) -> str:
    """Wrap text in bold markdown"""
    return f"**{text}**"

def code_text(text: str) -> str:
    """Wrap text in code markdown"""
    return f"`{text}`"

def italic_text(text: str) -> str:
    """Wrap text in italic markdown"""
    return f"_{text}_"

def escape_markdown(text: str) -> str:
    """Escape markdown special characters"""
    special_chars = ['*', '_', '`', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    
    return text

def format_error_message(error: str, context: str = "") -> str:
    """Format error message with context"""
    if context:
        return f"❌ **Error in {context}:** {error}"
    return f"❌ **Error:** {error}"

def format_success_message(message: str, context: str = "") -> str:
    """Format success message with context"""
    if context:
        return f"✅ **{context}:** {message}"
    return f"✅ **Success:** {message}"
