"""
Security Utilities
Rate limiting, input validation, and security helpers
"""

import re
import time
import asyncio
import hashlib
import secrets
from typing import Dict, Optional, Any, List
from datetime import datetime, timezone
from collections import defaultdict, deque

from aiolimiter import AsyncLimiter

class RateLimiter:
    """Advanced rate limiter with multiple windows and user tracking"""
    
    def __init__(self, requests_per_second: int = 10, requests_per_minute: int = 100):
        self.rps_limiter = AsyncLimiter(requests_per_second, 1)
        self.rpm_limiter = AsyncLimiter(requests_per_minute, 60)
        
        # User-specific tracking
        self.user_requests: Dict[int, deque] = defaultdict(lambda: deque())
        self.user_limits: Dict[int, Dict[str, Any]] = {}
        
        # Global tracking
        self.global_requests: deque = deque(maxlen=10000)
        
        # Cleanup task
        self.cleanup_task: Optional[asyncio.Task] = None
    
    async def acquire(self, user_id: int) -> bool:
        """Acquire rate limit for user"""
        try:
            # Check global limits
            if not await self._check_global_limits():
                return False
            
            # Check user-specific limits
            if not await self._check_user_limits(user_id):
                return False
            
            # Use aiolimiter for sliding window
            await self.rps_limiter.acquire()
            await self.rpm_limiter.acquire()
            
            # Track request
            self._track_request(user_id)
            
            return True
            
        except Exception:
            return False
    
    async def _check_global_limits(self) -> bool:
        """Check global rate limits"""
        now = time.time()
        
        # Remove old requests
        while self.global_requests and now - self.global_requests[0] > 60:
            self.global_requests.popleft()
        
        # Check if under limit
        return len(self.global_requests) < 1000  # Global limit
    
    async def _check_user_limits(self, user_id: int) -> bool:
        """Check user-specific rate limits"""
        now = time.time()
        user_requests = self.user_requests[user_id]
        
        # Remove old requests (1 minute window)
        while user_requests and now - user_requests[0] > 60:
            user_requests.popleft()
        
        # Get user limit (default 20 per minute)
        user_limit = self.user_limits.get(user_id, {}).get('rpm', 20)
        
        return len(user_requests) < user_limit
    
    def _track_request(self, user_id: int) -> None:
        """Track a request for rate limiting"""
        now = time.time()
        
        # Add to user tracking
        self.user_requests[user_id].append(now)
        
        # Add to global tracking
        self.global_requests.append(now)
    
    def set_user_limit(self, user_id: int, requests_per_minute: int) -> None:
        """Set custom rate limit for user"""
        self.user_limits[user_id] = {'rpm': requests_per_minute}
    
    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get rate limiting stats for user"""
        user_requests = self.user_requests[user_id]
        now = time.time()
        
        # Count requests in different time windows
        last_minute = sum(1 for req_time in user_requests if now - req_time <= 60)
        last_hour = sum(1 for req_time in user_requests if now - req_time <= 3600)
        
        return {
            'requests_last_minute': last_minute,
            'requests_last_hour': last_hour,
            'limit_per_minute': self.user_limits.get(user_id, {}).get('rpm', 20),
            'is_rate_limited': last_minute >= self.user_limits.get(user_id, {}).get('rpm', 20)
        }
    
    async def start_cleanup(self) -> None:
        """Start cleanup task for old data"""
        if self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop_cleanup(self) -> None:
        """Stop cleanup task"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            self.cleanup_task = None
    
    async def _cleanup_loop(self) -> None:
        """Cleanup old rate limiting data"""
        while True:
            try:
                await asyncio.sleep(300)  # Cleanup every 5 minutes
                
                now = time.time()
                cutoff_time = now - 3600  # Keep 1 hour of data
                
                # Clean user requests
                users_to_remove = []
                for user_id, requests in self.user_requests.items():
                    # Remove old requests
                    while requests and requests[0] < cutoff_time:
                        requests.popleft()
                    
                    # Remove empty user entries
                    if not requests:
                        users_to_remove.append(user_id)
                
                for user_id in users_to_remove:
                    del self.user_requests[user_id]
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in rate limiter cleanup: {e}")

def validate_address(address: str) -> bool:
    """Validate Ethereum address format"""
    if not address:
        return False
    
    # Check basic format
    if not re.match(r'^0x[a-fA-F0-9]{40}$', address):
        return False
    
    # Check checksum (optional but recommended)
    try:
        # Remove 0x prefix
        clean_address = address[2:].lower()
        
        # Hash the address
        address_hash = hashlib.sha256(clean_address.encode()).hexdigest()
        
        # Check each character against the hash
        for i, char in enumerate(address[2:]):
            if char.isupper():
                # Uppercase character should have corresponding hash bit >= 8
                if int(address_hash[i], 16) < 8:
                    return False
            elif char.islower():
                # Lowercase character should have corresponding hash bit < 8
                if int(address_hash[i], 16) >= 8:
                    return False
        
        return True
        
    except Exception:
        return False

def validate_amount(amount: str, min_amount: float = 0.0, max_amount: float = None) -> Optional[float]:
    """Validate and parse amount string"""
    try:
        # Remove whitespace
        amount_str = amount.strip()
        
        # Check if it's a valid number
        if not re.match(r'^\d*\.?\d*$', amount_str):
            return None
        
        # Convert to float
        amount_float = float(amount_str)
        
        # Check range
        if amount_float < min_amount:
            return None
        
        if max_amount is not None and amount_float > max_amount:
            return None
        
        return amount_float
        
    except (ValueError, TypeError):
        return None

def validate_slippage(slippage: str, max_slippage: float = 50.0) -> Optional[float]:
    """Validate slippage percentage"""
    try:
        slippage_float = float(slippage.strip())
        
        if slippage_float < 0 or slippage_float > max_slippage:
            return None
        
        return slippage_float
        
    except (ValueError, TypeError):
        return None

def validate_token_symbol(symbol: str) -> bool:
    """Validate token symbol"""
    if not symbol:
        return False
    
    # Check length (1-10 characters)
    if len(symbol) < 1 or len(symbol) > 10:
        return False
    
    # Check characters (letters and numbers only)
    if not re.match(r'^[A-Za-z0-9]+$', symbol):
        return False
    
    return True

def sanitize_input(text: str, max_length: int = 1000) -> str:
    """Sanitize user input"""
    if not text:
        return ""
    
    # Remove potentially harmful characters
    sanitized = re.sub(r'[<>"\']', '', text)
    
    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    # Strip whitespace
    sanitized = sanitized.strip()
    
    return sanitized

def generate_nonce(length: int = 16) -> str:
    """Generate cryptographically secure nonce"""
    return secrets.token_hex(length)

def hash_sensitive_data(data: str) -> str:
    """Hash sensitive data for logging"""
    return hashlib.sha256(data.encode()).hexdigest()

def mask_address(address: str) -> str:
    """Mask address for logging (show only first 6 and last 4 characters)"""
    if len(address) < 10:
        return "****"
    
    return f"{address[:6]}****{address[-4:]}"

def check_sql_injection(input_text: str) -> bool:
    """Check for potential SQL injection patterns"""
    dangerous_patterns = [
        r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)',
        r'(--|#|/\*|\*/)',
        r'(\bOR\b.*=.*\bOR\b)',
        r'(\bAND\b.*=.*\bAND\b)',
        r'(\'\s*OR\s*\')',
        r'(\bWHERE\b.*\bOR\b)',
        r'(1\s*=\s*1)',
        r'(TRUE\s*=\s*TRUE)'
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, input_text, re.IGNORECASE):
            return True
    
    return False

def validate_transaction_data(tx_data: Dict[str, Any]) -> bool:
    """Validate transaction data structure"""
    required_fields = ['to', 'value', 'data']
    
    for field in required_fields:
        if field not in tx_data:
            return False
    
    # Validate 'to' address
    if not validate_address(tx_data['to']):
        return False
    
    # Validate value (should be non-negative integer)
    try:
        value = int(tx_data['value'])
        if value < 0:
            return False
    except (ValueError, TypeError):
        return False
    
    # Validate data (should be hex string)
    data = tx_data['data']
    if not isinstance(data, str) or not data.startswith('0x'):
        return False
    
    try:
        int(data, 16)  # Try to parse as hex
    except ValueError:
        return False
    
    return True

def create_session_token() -> str:
    """Create secure session token"""
    return secrets.token_urlsafe(32)

def verify_signature(message: str, signature: str, address: str) -> bool:
    """Verify Ethereum signature (simplified)"""
    # In production, you'd use eth_account to properly verify signatures
    try:
        # Basic format checks
        if not signature.startswith('0x') or len(signature) != 132:
            return False
        
        if not validate_address(address):
            return False
        
        # Additional verification would go here
        return True
        
    except Exception:
        return False

def encrypt_sensitive_data(data: str, key: str) -> str:
    """Encrypt sensitive data (placeholder implementation)"""
    # In production, use proper encryption like Fernet
    return f"encrypted_{hash_sensitive_data(data + key)}"

def decrypt_sensitive_data(encrypted_data: str, key: str) -> str:
    """Decrypt sensitive data (placeholder implementation)"""
    # In production, use proper decryption
    if encrypted_data.startswith('encrypted_'):
        return "decrypted_placeholder"
    return encrypted_data

class SecurityLogger:
    """Security event logger"""
    
    def __init__(self):
        self.suspicious_activities: List[Dict[str, Any]] = []
        self.max_log_size = 1000
    
    def log_suspicious_activity(self, user_id: int, activity_type: str, details: str) -> None:
        """Log suspicious activity"""
        event = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'user_id': user_id,
            'activity_type': activity_type,
            'details': details,
            'severity': self._determine_severity(activity_type)
        }
        
        self.suspicious_activities.append(event)
        
        # Maintain log size
        if len(self.suspicious_activities) > self.max_log_size:
            self.suspicious_activities = self.suspicious_activities[-self.max_log_size:]
    
    def _determine_severity(self, activity_type: str) -> str:
        """Determine severity of activity"""
        high_severity = ['sql_injection', 'invalid_signature', 'rate_limit_exceeded']
        medium_severity = ['invalid_address', 'invalid_amount', 'suspicious_input']
        
        if activity_type in high_severity:
            return 'HIGH'
        elif activity_type in medium_severity:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def get_user_risk_score(self, user_id: int) -> float:
        """Calculate risk score for user based on activities"""
        user_activities = [
            activity for activity in self.suspicious_activities
            if activity['user_id'] == user_id
        ]
        
        if not user_activities:
            return 0.0
        
        # Calculate weighted score
        score = 0.0
        for activity in user_activities:
            severity_weight = {
                'HIGH': 10.0,
                'MEDIUM': 5.0,
                'LOW': 1.0
            }
            score += severity_weight.get(activity['severity'], 1.0)
        
        # Normalize to 0-100 scale
        return min(100.0, score)
    
    def get_recent_suspicious_activities(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent suspicious activities"""
        cutoff_time = datetime.now(timezone.utc).timestamp() - (hours * 3600)
        
        return [
            activity for activity in self.suspicious_activities
            if datetime.fromisoformat(activity['timestamp']).timestamp() > cutoff_time
        ]

# Global security logger instance
security_logger = SecurityLogger()
