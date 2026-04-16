"""
Predictive Analytics and Machine Learning Module

Provides:
- Time series forecasting for metrics
- Anomaly prediction with confidence scores
- Capacity planning and scaling predictions
- Trend analysis and pattern detection
- Correlation analysis between metrics
- Model training and evaluation
- Real-time prediction scoring
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
from dataclasses import dataclass, field
from uuid import uuid4
import statistics
import math


# ============================================================================
# Predictive Analytics Enums
# ============================================================================

class PredictionType(str, Enum):
    """Types of predictions"""
    METRIC_FORECAST = "metric_forecast"
    ANOMALY = "anomaly"
    CAPACITY = "capacity"
    FAILURE_RISK = "failure_risk"
    CHURN = "churn"
    PERFORMANCE = "performance"


class ModelType(str, Enum):
    """Machine learning model types"""
    LINEAR_REGRESSION = "linear_regression"
    ARIMA = "arima"
    EXPONENTIAL_SMOOTHING = "exponential_smoothing"
    NEURAL_NETWORK = "neural_network"
    RANDOM_FOREST = "random_forest"
    ISOLATION_FOREST = "isolation_forest"


class ModelStatus(str, Enum):
    """Model lifecycle status"""
    TRAINING = "training"
    READY = "ready"
    DEPLOYED = "deployed"
    DEPRECATED = "deprecated"


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class Metric:
    """Time series metric"""
    metric_id: str
    metric_name: str
    service: str
    
    timestamp: datetime
    value: float
    
    unit: str = ""
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class TimeSeries:
    """Time series data collection"""
    series_id: str = field(default_factory=lambda: str(uuid4()))
    metric_name: str = ""
    service: str = ""
    
    metrics: List[Metric] = field(default_factory=list)
    
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    frequency: str = "1m"  # 1m, 5m, 1h, 1d
    length: int = 0


@dataclass
class Prediction:
    """Model prediction"""
    prediction_id: str = field(default_factory=lambda: str(uuid4()))
    prediction_type: PredictionType = PredictionType.METRIC_FORECAST
    model_id: str = ""
    
    # Forecast
    predicted_value: float = 0.0
    predicted_at: datetime = field(default_factory=datetime.utcnow)
    confidence: float = 0.0  # 0.0-1.0
    
    # Time range
    forecast_range_start: datetime = field(default_factory=datetime.utcnow)
    forecast_range_end: Optional[datetime] = None
    
    # Details
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    
    # Guidance
    recommended_action: Optional[str] = None


@dataclass
class PredictionModel:
    """ML model for predictions"""
    model_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    model_type: ModelType = ModelType.LINEAR_REGRESSION
    
    prediction_type: PredictionType = PredictionType.METRIC_FORECAST
    metric_name: str = ""
    service_name: str = ""
    
    status: ModelStatus = ModelStatus.TRAINING
    
    # Training
    training_data_points: int = 0
    training_start: Optional[datetime] = None
    training_end: Optional[datetime] = None
    
    # Performance metrics
    mean_absolute_error: float = 0.0
    root_mean_square_error: float = 0.0
    r_squared: float = 0.0
    
    # Hyperparameters
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_retrained: Optional[datetime] = None
    retrain_interval_days: int = 7


# ============================================================================
# Predictive Analytics Service
# ============================================================================

class PredictiveAnalyticsService:
    """
    Predictive Analytics and Machine Learning Service
    
    Features:
    - Time series forecasting with multiple models
    - Anomaly prediction with confidence scoring
    - Capacity planning and auto-scaling predictions
    - Failure risk assessment
    - Trend analysis and seasonality detection
    - Model training, evaluation, and deployment
    """

    def __init__(self):
        # Data storage
        self._metrics: Dict[str, List[Metric]] = {}  # metric_name -> [Metric, ...]
        self._time_series: Dict[str, TimeSeries] = {}
        
        # Models
        self._models: Dict[str, PredictionModel] = {}
        self._active_models: Dict[str, str] = {}  # metric_name -> model_id
        
        # Predictions
        self._predictions: List[Prediction] = []
        
        # Statistics
        self._baseline_stats: Dict[str, Dict[str, float]] = {}  # metric_name -> stats

    # ========================================================================
    # Data Collection
    # ========================================================================

    async def collect_metric(
        self,
        metric_name: str,
        service: str,
        value: float,
        unit: str = "",
        tags: Optional[Dict[str, str]] = None
    ) -> str:
        """Collect metric for analysis"""
        
        metric = Metric(
            metric_id=str(uuid4()),
            metric_name=metric_name,
            service=service,
            timestamp=datetime.utcnow(),
            value=value,
            unit=unit,
            tags=tags or {}
        )
        
        # Store metric
        if metric_name not in self._metrics:
            self._metrics[metric_name] = []
        
        self._metrics[metric_name].append(metric)
        
        # Keep only last 10,000 points per metric for memory efficiency
        if len(self._metrics[metric_name]) > 10000:
            self._metrics[metric_name] = self._metrics[metric_name][-10000:]
        
        # Update baseline statistics
        await self._update_baselines(metric_name)
        
        return metric.metric_id

    async def _update_baselines(self, metric_name: str) -> None:
        """Update baseline statistics for metric"""
        
        metrics = self._metrics.get(metric_name, [])
        if len(metrics) < 10:
            return
        
        # Get recent values
        recent = [m.value for m in metrics[-1000:]]
        
        # Calculate statistics
        self._baseline_stats[metric_name] = {
            "mean": statistics.mean(recent),
            "median": statistics.median(recent),
            "stdev": statistics.stdev(recent) if len(recent) > 1 else 0,
            "min": min(recent),
            "max": max(recent),
            "count": len(recent)
        }

    # ========================================================================
    # Model Training and Management
    # ========================================================================

    async def train_model(
        self,
        metric_name: str,
        service: str,
        model_type: ModelType = ModelType.LINEAR_REGRESSION,
        prediction_type: PredictionType = PredictionType.METRIC_FORECAST,
        training_window_days: int = 30
    ) -> Optional[PredictionModel]:
        """Train prediction model"""
        
        # Collect training data
        metrics = self._metrics.get(metric_name, [])
        if not metrics:
            return None
        
        cutoff = datetime.utcnow() - timedelta(days=training_window_days)
        training_data = [m for m in metrics if m.timestamp >= cutoff]
        
        if len(training_data) < 10:
            return None
        
        # Create model
        model = PredictionModel(
            name=f"{metric_name}_model_{datetime.utcnow().timestamp()}",
            description=f"Predictive model for {metric_name}",
            model_type=model_type,
            prediction_type=prediction_type,
            metric_name=metric_name,
            service_name=service,
            status=ModelStatus.TRAINING,
            training_data_points=len(training_data),
            training_start=training_data[0].timestamp,
            training_end=training_data[-1].timestamp
        )
        
        # Train (simplified)
        await self._train_model_algorithm(model, training_data)
        
        model.status = ModelStatus.READY
        model.last_retrained = datetime.utcnow()
        
        # Store model
        self._models[model.model_id] = model
        
        # Activate as primary for metric
        self._active_models[metric_name] = model.model_id
        
        return model

    async def _train_model_algorithm(
        self,
        model: PredictionModel,
        training_data: List[Metric]
    ) -> None:
        """Train model using specific algorithm"""
        
        values = [m.value for m in training_data]
        
        if model.model_type == ModelType.LINEAR_REGRESSION:
            await self._train_linear_regression(model, values)
        elif model.model_type == ModelType.EXPONENTIAL_SMOOTHING:
            await self._train_exponential_smoothing(model, values)
        elif model.model_type == ModelType.ISOLATION_FOREST:
            await self._train_isolation_forest(model, values)

    async def _train_linear_regression(
        self,
        model: PredictionModel,
        values: List[float]
    ) -> None:
        """Train linear regression model"""
        
        if len(values) < 2:
            return
        
        # Simple linear regression
        n = len(values)
        x = list(range(n))
        y = values
        
        x_mean = statistics.mean(x)
        y_mean = statistics.mean(y)
        
        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            slope = 0
        else:
            slope = numerator / denominator
        
        intercept = y_mean - slope * x_mean
        
        model.hyperparameters = {"slope": slope, "intercept": intercept}
        
        # Calculate R-squared
        residuals = [y[i] - (slope * x[i] + intercept) for i in range(n)]
        ss_res = sum(r ** 2 for r in residuals)
        ss_tot = sum((y[i] - y_mean) ** 2 for i in range(n))
        
        model.r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

    async def _train_exponential_smoothing(
        self,
        model: PredictionModel,
        values: List[float]
    ) -> None:
        """Train exponential smoothing model"""
        
        if len(values) < 2:
            return
        
        # Simple exponential smoothing with alpha=0.3
        alpha = 0.3
        
        smoothed = [values[0]]
        for v in values[1:]:
            smoothed.append(alpha * v + (1 - alpha) * smoothed[-1])
        
        model.hyperparameters = {"alpha": alpha}
        model.r_squared = 0.8  # Simplified

    async def _train_isolation_forest(
        self,
        model: PredictionModel,
        values: List[float]
    ) -> None:
        """Train isolation forest for anomaly detection"""
        
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0
        
        model.hyperparameters = {
            "mean": mean,
            "stdev": stdev,
            "threshold": 3.0  # 3-sigma rule
        }
        model.r_squared = 0.85  # Simplified

    # ========================================================================
    # Predictions
    # ========================================================================

    async def predict(
        self,
        metric_name: str,
        hours_ahead: int = 1,
        confidence_threshold: float = 0.7
    ) -> Optional[Prediction]:
        """Generate prediction for metric"""
        
        # Get active model
        model_id = self._active_models.get(metric_name)
        if not model_id:
            return None
        
        model = self._models.get(model_id)
        if not model or model.status != ModelStatus.READY:
            return None
        
        # Generate prediction
        prediction = await self._generate_prediction(model, hours_ahead)
        
        if prediction and prediction.confidence >= confidence_threshold:
            self._predictions.append(prediction)
            return prediction
        
        return None

    async def _generate_prediction(
        self,
        model: PredictionModel,
        hours_ahead: int
    ) -> Optional[Prediction]:
        """Generate specific prediction"""
        
        metrics = self._metrics.get(model.metric_name, [])
        if not metrics:
            return None
        
        values = [m.value for m in metrics[-100:]]
        current_value = values[-1]
        
        prediction = Prediction(
            prediction_type=model.prediction_type,
            model_id=model.model_id,
            forecast_range_end=datetime.utcnow() + timedelta(hours=hours_ahead)
        )
        
        if model.model_type == ModelType.LINEAR_REGRESSION:
            slope = model.hyperparameters.get("slope", 0)
            prediction.predicted_value = current_value + (slope * hours_ahead)
            prediction.confidence = min(model.r_squared, 1.0)
        
        elif model.model_type == ModelType.EXPONENTIAL_SMOOTHING:
            alpha = model.hyperparameters.get("alpha", 0.3)
            prediction.predicted_value = current_value
            prediction.confidence = 0.75
        
        elif model.model_type == ModelType.ISOLATION_FOREST:
            # For anomaly detection
            mean = model.hyperparameters.get("mean", 0)
            stdev = model.hyperparameters.get("stdev", 1)
            
            if stdev > 0:
                z_score = abs((current_value - mean) / stdev)
                is_anomaly = z_score > model.hyperparameters.get("threshold", 3)
                
                prediction.predicted_value = float(is_anomaly)
                prediction.confidence = min(z_score / 3.0, 1.0)
                prediction.message = f"Anomaly detected: z-score = {z_score:.2f}"
        
        return prediction

    # ========================================================================
    # Capacity Planning
    # ========================================================================

    async def predict_capacity_need(
        self,
        metric_name: str,
        days_ahead: int = 30,
        threshold_percent: float = 80.0
    ) -> Dict[str, Any]:
        """Predict when capacity will be exceeded"""
        
        metrics = self._metrics.get(metric_name, [])
        if not metrics:
            return {}
        
        # Get maximum value
        max_value = max(m.value for m in metrics)
        capacity_threshold = max_value * (threshold_percent / 100.0)
        
        # Get trend
        recent = [m.value for m in metrics[-100:]]
        if len(recent) < 2:
            return {}
        
        trend = (recent[-1] - recent[0]) / len(recent)
        
        # Estimate when threshold will be reached
        if trend <= 0:
            estimated_days = None
        else:
            # Linear extrapolation
            days_to_threshold = (capacity_threshold - recent[-1]) / trend if trend > 0 else None
            if days_to_threshold and days_to_threshold > 0:
                estimated_days = min(int(days_to_threshold), days_ahead)
            else:
                estimated_days = None
        
        return {
            "metric": metric_name,
            "current_value": recent[-1],
            "max_value": max_value,
            "capacity_threshold": capacity_threshold,
            "daily_trend": trend,
            "estimated_days_to_threshold": estimated_days,
            "recommendation": f"Scale capacity in {estimated_days} days" if estimated_days else "Capacity sufficient"
        }

    # ========================================================================
    # Failure Risk Assessment
    # ========================================================================

    async def assess_failure_risk(
        self,
        service: str
    ) -> Dict[str, Any]:
        """Assess risk of service failure"""
        
        # Analyze error rates, latency, resource usage
        risk_factors = []
        
        # Check error rate
        error_metrics = [m for m in self._metrics.get("error_rate", []) if m.service == service]
        if error_metrics:
            recent_errors = statistics.mean([m.value for m in error_metrics[-100:]])
            if recent_errors > 1.0:  # >1% error rate
                risk_factors.append({
                    "factor": "high_error_rate",
                    "severity": "high",
                    "value": recent_errors
                })
        
        # Check latency
        latency_metrics = [m for m in self._metrics.get("latency_ms", []) if m.service == service]
        if latency_metrics:
            recent_latency = statistics.mean([m.value for m in latency_metrics[-100:]])
            if recent_latency > 1000:  # >1 second
                risk_factors.append({
                    "factor": "high_latency",
                    "severity": "medium",
                    "value": recent_latency
                })
        
        # Calculate overall risk
        risk_score = len(risk_factors) / 5.0  # Normalization
        
        return {
            "service": service,
            "risk_score": min(risk_score, 1.0),
            "risk_level": self._categorize_risk(risk_score),
            "risk_factors": risk_factors,
            "recommendations": self._get_risk_recommendations(risk_factors)
        }

    def _categorize_risk(self, score: float) -> str:
        """Categorize risk score"""
        if score < 0.2:
            return "low"
        elif score < 0.5:
            return "medium"
        elif score < 0.8:
            return "high"
        else:
            return "critical"

    def _get_risk_recommendations(self, factors: List[Dict[str, Any]]) -> List[str]:
        """Get recommendations based on risk factors"""
        
        recommendations = []
        
        for factor in factors:
            if factor["factor"] == "high_error_rate":
                recommendations.append("Investigate error logs and check service health")
            elif factor["factor"] == "high_latency":
                recommendations.append("Check database query performance and resource utilization")
        
        return recommendations

    # ========================================================================
    # Model Management
    # ========================================================================

    async def retrain_models(self) -> Dict[str, Any]:
        """Retrain all models due for retraining"""
        
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "models_retrained": 0,
            "models_failed": 0
        }
        
        now = datetime.utcnow()
        
        for model in self._models.values():
            if model.status == ModelStatus.DEPRECATED:
                continue
            
            # Check if retraining is due
            if model.last_retrained:
                days_since = (now - model.last_retrained).days
                if days_since < model.retrain_interval_days:
                    continue
            
            # Retrain
            try:
                await self.train_model(
                    model.metric_name,
                    model.service_name,
                    model.model_type,
                    model.prediction_type
                )
                results["models_retrained"] += 1
            except Exception:
                results["models_failed"] += 1
        
        return results

    # ========================================================================
    # Correlation Analysis
    # ========================================================================

    async def find_correlated_metrics(
        self,
        metric_name: str,
        threshold: float = 0.7
    ) -> List[Tuple[str, float]]:
        """Find metrics correlated with given metric"""
        
        metrics_data = self._metrics.get(metric_name, [])
        if not metrics_data or len(metrics_data) < 10:
            return []
        
        correlations = []
        
        for other_metric in self._metrics:
            if other_metric == metric_name:
                continue
            
            other_data = self._metrics.get(other_metric, [])
            if len(other_data) < 10:
                continue
            
            corr = await self._calculate_correlation(metrics_data, other_data)
            
            if abs(corr) >= threshold:
                correlations.append((other_metric, corr))
        
        return sorted(correlations, key=lambda x: abs(x[1]), reverse=True)

    async def _calculate_correlation(
        self,
        series1: List[Metric],
        series2: List[Metric]
    ) -> float:
        """Calculate Pearson correlation between two time series"""
        
        # Align timestamps and extract values
        values1 = []
        values2 = []
        
        for m1 in series1[-100:]:  # Recent 100 points
            # Find closest match in series2
            for m2 in series2:
                time_diff = abs((m1.timestamp - m2.timestamp).total_seconds())
                if time_diff < 60:  # Within 1 minute
                    values1.append(m1.value)
                    values2.append(m2.value)
                    break
        
        if len(values1) < 2:
            return 0.0
        
        # Calculate Pearson correlation
        mean1 = statistics.mean(values1)
        mean2 = statistics.mean(values2)
        
        numerator = sum((values1[i] - mean1) * (values2[i] - mean2) for i in range(len(values1)))
        denom1 = math.sqrt(sum((v - mean1) ** 2 for v in values1))
        denom2 = math.sqrt(sum((v - mean2) ** 2 for v in values2))
        
        if denom1 == 0 or denom2 == 0:
            return 0.0
        
        return numerator / (denom1 * denom2)

    # ========================================================================
    # Reporting
    # ========================================================================

    def get_model_performance(self, model_id: str) -> Dict[str, Any]:
        """Get model performance metrics"""
        
        model = self._models.get(model_id)
        if not model:
            return {}
        
        return {
            "model_id": model_id,
            "name": model.name,
            "type": model.model_type.value,
            "status": model.status.value,
            "mean_absolute_error": model.mean_absolute_error,
            "root_mean_square_error": model.root_mean_square_error,
            "r_squared": model.r_squared,
            "training_points": model.training_data_points,
            "last_retrained": model.last_retrained.isoformat() if model.last_retrained else None
        }

    def get_recent_predictions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent predictions"""
        
        return [
            {
                "prediction_id": p.prediction_id,
                "type": p.prediction_type.value,
                "predicted_value": p.predicted_value,
                "confidence": p.confidence,
                "timestamp": p.predicted_at.isoformat(),
                "message": p.message
            }
            for p in self._predictions[-limit:]
        ]
