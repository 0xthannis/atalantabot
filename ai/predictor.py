"""
AI Predictor
Lightweight ML models for token launch scoring and price prediction
"""

import asyncio
import logging
import numpy as np
import pickle
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ML imports
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

logger = logging.getLogger(__name__)

@dataclass
class TokenFeatures:
    """Features for token analysis"""
    token_address: str
    liquidity_eth: float
    holder_count: int
    transaction_count_24h: int
    buy_sell_ratio: float
    price_volatility: float
    dev_wallet_balance: float
    contract_age_hours: float
    honeypot_score: float
    social_mentions: int
    
    def to_array(self) -> np.ndarray:
        """Convert to numpy array for ML"""
        return np.array([
            self.liquidity_eth,
            self.holder_count,
            self.transaction_count_24h,
            self.buy_sell_ratio,
            self.price_volatility,
            self.dev_wallet_balance,
            self.contract_age_hours,
            self.honeypot_score,
            self.social_mentions
        ])

@dataclass
class PredictionResult:
    """Prediction result"""
    token_address: str
    prediction_type: str
    confidence: float
    prediction_value: float
    features_used: List[str]
    model_version: str
    created_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'token_address': self.token_address,
            'prediction_type': self.prediction_type,
            'confidence': self.confidence,
            'prediction_value': self.prediction_value,
            'features_used': self.features_used,
            'model_version': self.model_version,
            'created_at': self.created_at.isoformat()
        }

class AIPredictor:
    """AI-powered token analysis and prediction"""
    
    def __init__(self, model_path: str = "models/"):
        self.model_path = Path(model_path)
        self.model_path.mkdir(exist_ok=True)
        
        # Models
        self.launch_classifier: Optional[RandomForestClassifier] = None
        self.price_scaler: Optional[StandardScaler] = None
        
        # Feature names
        self.feature_names = [
            'liquidity_eth',
            'holder_count', 
            'transaction_count_24h',
            'buy_sell_ratio',
            'price_volatility',
            'dev_wallet_balance',
            'contract_age_hours',
            'honeypot_score',
            'social_mentions'
        ]
        
        # Model metadata
        self.model_version = "1.0.0"
        self.last_training_date: Optional[datetime] = None
        
        # Prediction cache
        self.prediction_cache: Dict[str, PredictionResult] = {}
        self.cache_ttl = timedelta(minutes=30)
        
        # Initialize or load models
        self._initialize_models()
    
    def _initialize_models(self) -> None:
        """Initialize or load ML models"""
        try:
            # Try to load existing models
            classifier_path = self.model_path / "launch_classifier.pkl"
            scaler_path = self.model_path / "price_scaler.pkl"
            
            if classifier_path.exists() and scaler_path.exists():
                with open(classifier_path, 'rb') as f:
                    self.launch_classifier = pickle.load(f)
                
                with open(scaler_path, 'rb') as f:
                    self.price_scaler = pickle.load(f)
                
                logger.info("Loaded existing ML models")
            else:
                # Create new models
                self.launch_classifier = RandomForestClassifier(
                    n_estimators=100,
                    max_depth=10,
                    random_state=42
                )
                self.price_scaler = StandardScaler()
                
                logger.info("Created new ML models")
                
        except Exception as e:
            logger.error(f"Error initializing models: {e}")
            # Create fallback models
            self.launch_classifier = RandomForestClassifier(
                n_estimators=50, max_depth=5, random_state=42
            )
            self.price_scaler = StandardScaler()
    
    async def score_token_launch(self, features: TokenFeatures) -> PredictionResult:
        """Score a token launch (0-100, higher is better)"""
        try:
            # Check cache first
            cache_key = f"launch_{features.token_address}"
            if cache_key in self.prediction_cache:
                cached_result = self.prediction_cache[cache_key]
                if datetime.now(timezone.utc) - cached_result.created_at < self.cache_ttl:
                    return cached_result
            
            # Prepare features
            feature_array = features.to_array().reshape(1, -1)
            
            # Scale features
            if self.price_scaler:
                scaled_features = self.price_scaler.transform(feature_array)
            else:
                scaled_features = feature_array
            
            # Make prediction
            if self.launch_classifier:
                prediction_proba = self.launch_classifier.predict_proba(scaled_features)[0]
                # Assuming binary classification: 0 = bad, 1 = good
                confidence = prediction_proba[1] if len(prediction_proba) > 1 else 0.5
                prediction_value = confidence * 100  # Convert to 0-100 scale
            else:
                # Fallback: simple heuristic scoring
                prediction_value = self._heuristic_score(features)
                confidence = 0.6  # Lower confidence for heuristic
            
            result = PredictionResult(
                token_address=features.token_address,
                prediction_type="launch_score",
                confidence=confidence,
                prediction_value=prediction_value,
                features_used=self.feature_names,
                model_version=self.model_version,
                created_at=datetime.now(timezone.utc)
            )
            
            # Cache result
            self.prediction_cache[cache_key] = result
            
            return result
            
        except Exception as e:
            logger.error(f"Error scoring token launch: {e}")
            # Return fallback result
            return PredictionResult(
                token_address=features.token_address,
                prediction_type="launch_score",
                confidence=0.3,
                prediction_value=50.0,
                features_used=self.feature_names,
                model_version="fallback",
                created_at=datetime.now(timezone.utc)
            )
    
    def _heuristic_score(self, features: TokenFeatures) -> float:
        """Fallback heuristic scoring"""
        score = 50.0  # Base score
        
        # Liquidity scoring
        if features.liquidity_eth > 10:
            score += 20
        elif features.liquidity_eth > 1:
            score += 10
        elif features.liquidity_eth < 0.1:
            score -= 20
        
        # Holder count scoring
        if features.holder_count > 100:
            score += 15
        elif features.holder_count > 50:
            score += 10
        elif features.holder_count < 10:
            score -= 10
        
        # Transaction activity
        if features.transaction_count_24h > 1000:
            score += 15
        elif features.transaction_count_24h > 100:
            score += 5
        
        # Buy/sell ratio (more buys is good)
        if features.buy_sell_ratio > 1.5:
            score += 10
        elif features.buy_sell_ratio < 0.5:
            score -= 15
        
        # Honeypot penalty
        if features.honeypot_score > 0.7:
            score -= 30
        elif features.honeypot_score > 0.3:
            score -= 10
        
        # Social mentions
        if features.social_mentions > 100:
            score += 10
        elif features.social_mentions > 50:
            score += 5
        
        return max(0, min(100, score))
    
    async def predict_price_movement(self, token_address: str, 
                                   historical_prices: List[float],
                                   periods_ahead: int = 1) -> PredictionResult:
        """Predict price movement using simple trend analysis"""
        try:
            if len(historical_prices) < 10:
                # Not enough data
                return PredictionResult(
                    token_address=token_address,
                    prediction_type="price_movement",
                    confidence=0.2,
                    prediction_value=0.0,
                    features_used=["price_history"],
                    model_version="insufficient_data",
                    created_at=datetime.now(timezone.utc)
                )
            
            # Simple moving average and trend analysis
            prices = np.array(historical_prices[-20:])  # Last 20 prices
            
            # Calculate moving averages
            short_ma = np.mean(prices[-5:])
            long_ma = np.mean(prices[-10:])
            
            # Calculate trend
            if short_ma > long_ma:
                trend = 1  # Upward
            elif short_ma < long_ma:
                trend = -1  # Downward
            else:
                trend = 0  # Neutral
            
            # Calculate volatility
            returns = np.diff(prices) / prices[:-1]
            volatility = np.std(returns) if len(returns) > 0 else 0
            
            # Simple prediction based on trend and volatility
            predicted_change = trend * volatility * 2  # Simple scaling
            confidence = min(0.8, max(0.3, 1 - volatility))  # Higher confidence for less volatile tokens
            
            result = PredictionResult(
                token_address=token_address,
                prediction_type="price_movement",
                confidence=confidence,
                prediction_value=predicted_change * 100,  # Percentage change
                features_used=["price_trend", "volatility"],
                model_version="simple_trend",
                created_at=datetime.now(timezone.utc)
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error predicting price movement: {e}")
            return PredictionResult(
                token_address=token_address,
                prediction_type="price_movement",
                confidence=0.1,
                prediction_value=0.0,
                features_used=["error"],
                model_version="error",
                created_at=datetime.now(timezone.utc)
            )
    
    async def detect_pump_signals(self, token_address: str,
                                 recent_trades: List[Dict[str, Any]]) -> PredictionResult:
        """Detect potential pump signals"""
        try:
            if not recent_trades:
                return PredictionResult(
                    token_address=token_address,
                    prediction_type="pump_signal",
                    confidence=0.1,
                    prediction_value=0.0,
                    features_used=["no_data"],
                    model_version="no_data",
                    created_at=datetime.now(timezone.utc)
                )
            
            # Analyze recent trades for pump patterns
            total_volume = sum(trade.get('amount', 0) for trade in recent_trades)
            buy_count = sum(1 for trade in recent_trades if trade.get('type') == 'buy')
            sell_count = sum(1 for trade in recent_trades if trade.get('type') == 'sell')
            
            # Calculate pump score
            pump_score = 0
            
            # High volume indicator
            if total_volume > 10:  # 10+ ETH in recent trades
                pump_score += 30
            elif total_volume > 5:
                pump_score += 15
            
            # Buy pressure
            if buy_count > sell_count * 2:
                pump_score += 25
            elif buy_count > sell_count:
                pump_score += 10
            
            # Rapid price increase (if price data available)
            prices = [trade.get('price', 0) for trade in recent_trades if trade.get('price')]
            if len(prices) > 5:
                price_change = (prices[-1] - prices[0]) / prices[0] if prices[0] > 0 else 0
                if price_change > 0.5:  # 50%+ increase
                    pump_score += 25
                elif price_change > 0.2:  # 20%+ increase
                    pump_score += 10
            
            # Confidence based on data quality
            confidence = min(0.9, len(recent_trades) / 50)  # More trades = higher confidence
            
            result = PredictionResult(
                token_address=token_address,
                prediction_type="pump_signal",
                confidence=confidence,
                prediction_value=min(100, pump_score),
                features_used=["volume", "buy_pressure", "price_change"],
                model_version="pattern_analysis",
                created_at=datetime.now(timezone.utc)
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error detecting pump signals: {e}")
            return PredictionResult(
                token_address=token_address,
                prediction_type="pump_signal",
                confidence=0.1,
                prediction_value=0.0,
                features_used=["error"],
                model_version="error",
                created_at=datetime.now(timezone.utc)
            )
    
    async def train_models(self, training_data: List[Tuple[TokenFeatures, int]]) -> bool:
        """Train the ML models with historical data"""
        try:
            if len(training_data) < 50:
                logger.warning("Insufficient training data")
                return False
            
            # Prepare training data
            X = np.array([features.to_array() for features, _ in training_data])
            y = np.array([label for _, label in training_data])
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )
            
            # Scale features
            if self.price_scaler:
                X_train_scaled = self.price_scaler.fit_transform(X_train)
                X_test_scaled = self.price_scaler.transform(X_test)
            else:
                X_train_scaled = X_train
                X_test_scaled = X_test
            
            # Train classifier
            if self.launch_classifier:
                self.launch_classifier.fit(X_train_scaled, y_train)
                
                # Evaluate
                y_pred = self.launch_classifier.predict(X_test_scaled)
                accuracy = accuracy_score(y_test, y_pred)
                
                logger.info(f"Model training completed. Accuracy: {accuracy:.2f}")
                
                # Save models
                self._save_models()
                
                self.last_training_date = datetime.now(timezone.utc)
                return True
            
        except Exception as e:
            logger.error(f"Error training models: {e}")
            return False
    
    def _save_models(self) -> None:
        """Save trained models to disk"""
        try:
            if self.launch_classifier:
                with open(self.model_path / "launch_classifier.pkl", 'wb') as f:
                    pickle.dump(self.launch_classifier, f)
            
            if self.price_scaler:
                with open(self.model_path / "price_scaler.pkl", 'wb') as f:
                    pickle.dump(self.price_scaler, f)
            
            logger.info("Models saved successfully")
            
        except Exception as e:
            logger.error(f"Error saving models: {e}")
    
    async def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
        return {
            'model_version': self.model_version,
            'last_training_date': self.last_training_date.isoformat() if self.last_training_date else None,
            'feature_count': len(self.feature_names),
            'cache_size': len(self.prediction_cache),
            'model_loaded': self.launch_classifier is not None
        }
    
    def clear_cache(self) -> None:
        """Clear prediction cache"""
        self.prediction_cache.clear()
        logger.info("AI prediction cache cleared")
    
    async def batch_predict(self, features_list: List[TokenFeatures]) -> List[PredictionResult]:
        """Batch prediction for multiple tokens"""
        tasks = [self.score_token_launch(features) for features in features_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = []
        for result in results:
            if isinstance(result, PredictionResult):
                valid_results.append(result)
            else:
                logger.error(f"Batch prediction error: {result}")
        
        return valid_results
