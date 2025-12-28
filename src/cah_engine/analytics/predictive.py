"""
Predictive Models

Census forecasting, transfer risk scoring, and denial probability models.
Designed for MV-CAHI compliance with minimal computational requirements.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Any, Optional
import math

import numpy as np
from numpy.typing import NDArray

from cah_engine.core.models import ClinicalEncounter, SimulationResult
from cah_engine.core.enums import EncounterType, RiskTier


@dataclass
class ForecastResult:
    """Result of a forecasting operation."""
    
    point_forecast: list[float]
    lower_bound: list[float]  # 80% prediction interval
    upper_bound: list[float]
    dates: list[date]
    model_name: str = ""
    confidence_level: float = 0.80
    mape: Optional[float] = None  # Mean Absolute Percentage Error
    
    def get_forecast_for_date(self, target_date: date) -> Optional[dict]:
        """Get forecast for a specific date."""
        if target_date in self.dates:
            idx = self.dates.index(target_date)
            return {
                "date": target_date,
                "forecast": self.point_forecast[idx],
                "lower": self.lower_bound[idx],
                "upper": self.upper_bound[idx],
            }
        return None
    
    @property
    def forecast_horizon(self) -> int:
        """Number of days in forecast."""
        return len(self.point_forecast)


@dataclass
class RiskScore:
    """Risk score with contributing factors."""
    
    score: float  # 0-100
    tier: RiskTier
    factors: list[tuple[str, float]] = field(default_factory=list)  # (factor_name, contribution)
    confidence: float = 0.0
    
    def __post_init__(self):
        if not self.tier:
            self.tier = RiskTier.from_score(self.score)
    
    @property
    def top_factors(self) -> list[tuple[str, float]]:
        """Get top 3 contributing factors."""
        sorted_factors = sorted(self.factors, key=lambda x: abs(x[1]), reverse=True)
        return sorted_factors[:3]


class BaseModel(ABC):
    """Abstract base class for predictive models."""
    
    def __init__(self, name: str = "base_model"):
        self.name = name
        self.trained = False
        self.last_trained: Optional[datetime] = None
        self.training_samples: int = 0
    
    @abstractmethod
    def train(self, data: Any) -> None:
        """Train the model on historical data."""
        pass
    
    @abstractmethod
    def predict(self, inputs: Any) -> Any:
        """Generate predictions."""
        pass
    
    def get_staleness_hours(self) -> float:
        """Get hours since last training."""
        if self.last_trained is None:
            return float("inf")
        delta = datetime.now() - self.last_trained
        return delta.total_seconds() / 3600


class CensusForecaster(BaseModel):
    """
    Census forecasting model.
    
    Uses SARIMA-like approach with day-of-week seasonality.
    Optimized for small data volumes typical of CAHs.
    
    Model: Y_t = c + φ₁Y_{t-1} + ... + θ₁ε_{t-1} + ... + βX_t + ε_t
    
    Parameters:
    - Typical order: SARIMA(1,1,1)(1,1,1)[7] for weekly seasonality
    
    Training Requirements:
    - Minimum 2 years historical data
    - Daily granularity
    """
    
    def __init__(self):
        super().__init__(name="census_forecaster")
        
        # Model parameters
        self.mean_census: float = 0.0
        self.std_census: float = 1.0
        self.day_of_week_effects: NDArray = np.zeros(7)
        self.trend: float = 0.0
        self.ar_coef: float = 0.5  # Autoregressive coefficient
        self.ma_coef: float = 0.2  # Moving average coefficient
        
        # History for prediction
        self.recent_values: list[float] = []
        self.recent_errors: list[float] = []
    
    def train(self, historical_census: list[tuple[date, float]]) -> None:
        """
        Train on historical daily census data.
        
        Args:
            historical_census: List of (date, census) tuples
        """
        if len(historical_census) < 30:
            raise ValueError("Minimum 30 days of data required for training")
        
        # Sort by date
        sorted_data = sorted(historical_census, key=lambda x: x[0])
        dates = [d[0] for d in sorted_data]
        values = np.array([d[1] for d in sorted_data])
        
        # Calculate basic statistics
        self.mean_census = float(np.mean(values))
        self.std_census = float(np.std(values)) if np.std(values) > 0 else 1.0
        
        # Calculate day-of-week effects
        dow_sums = np.zeros(7)
        dow_counts = np.zeros(7)
        for i, dt in enumerate(dates):
            dow = dt.weekday()
            dow_sums[dow] += values[i] - self.mean_census
            dow_counts[dow] += 1
        
        for dow in range(7):
            if dow_counts[dow] > 0:
                self.day_of_week_effects[dow] = dow_sums[dow] / dow_counts[dow]
        
        # Estimate trend
        if len(values) > 30:
            x = np.arange(len(values))
            coeffs = np.polyfit(x, values, 1)
            self.trend = coeffs[0]
        
        # Estimate AR coefficient (simple lag-1 autocorrelation)
        if len(values) > 1:
            demeaned = values - self.mean_census
            self.ar_coef = np.corrcoef(demeaned[:-1], demeaned[1:])[0, 1]
            self.ar_coef = max(0.1, min(0.9, self.ar_coef))  # Bound coefficient
        
        # Store recent values for prediction
        self.recent_values = list(values[-14:])  # Last 2 weeks
        
        # Calculate recent errors (for MA component)
        fitted = self._fitted_values(values)
        errors = values - fitted
        self.recent_errors = list(errors[-7:])
        
        self.trained = True
        self.last_trained = datetime.now()
        self.training_samples = len(historical_census)
    
    def predict(self, horizon: int = 7, start_date: Optional[date] = None) -> ForecastResult:
        """
        Generate census forecast.
        
        Args:
            horizon: Number of days to forecast
            start_date: Start date for forecast (defaults to tomorrow)
            
        Returns:
            ForecastResult with point forecasts and prediction intervals
        """
        if not self.trained:
            raise ValueError("Model must be trained before prediction")
        
        if start_date is None:
            start_date = date.today() + timedelta(days=1)
        
        forecasts = []
        lower_bounds = []
        upper_bounds = []
        dates = []
        
        # Use last known value for initial forecast
        last_value = self.recent_values[-1] if self.recent_values else self.mean_census
        last_error = self.recent_errors[-1] if self.recent_errors else 0.0
        
        for h in range(horizon):
            forecast_date = start_date + timedelta(days=h)
            dates.append(forecast_date)
            
            # Day-of-week effect
            dow_effect = self.day_of_week_effects[forecast_date.weekday()]
            
            # Trend effect
            trend_effect = self.trend * h
            
            # AR component (decay with horizon)
            ar_component = self.ar_coef ** (h + 1) * (last_value - self.mean_census)
            
            # MA component (only for first few steps)
            ma_component = 0.0
            if h < len(self.recent_errors):
                ma_component = self.ma_coef * last_error
            
            # Point forecast
            forecast = self.mean_census + dow_effect + trend_effect + ar_component + ma_component
            forecast = max(0, forecast)  # Census can't be negative
            forecasts.append(forecast)
            
            # Prediction interval (wider for further horizons)
            uncertainty = self.std_census * math.sqrt(1 + 0.1 * h)
            lower_bounds.append(max(0, forecast - 1.28 * uncertainty))  # 80% interval
            upper_bounds.append(forecast + 1.28 * uncertainty)
        
        return ForecastResult(
            point_forecast=forecasts,
            lower_bound=lower_bounds,
            upper_bound=upper_bounds,
            dates=dates,
            model_name=self.name,
            confidence_level=0.80,
        )
    
    def _fitted_values(self, values: NDArray) -> NDArray:
        """Calculate fitted values for error estimation."""
        fitted = np.zeros_like(values)
        fitted[0] = self.mean_census
        
        for i in range(1, len(values)):
            fitted[i] = self.mean_census + self.ar_coef * (values[i-1] - self.mean_census)
        
        return fitted
    
    def update_incremental(self, new_observation: tuple[date, float]) -> None:
        """Update model with a new observation (online learning)."""
        dt, value = new_observation
        
        # Update recent values
        self.recent_values.append(value)
        if len(self.recent_values) > 14:
            self.recent_values.pop(0)
        
        # Update mean (exponential smoothing)
        alpha = 0.1
        self.mean_census = alpha * value + (1 - alpha) * self.mean_census
        
        # Update day-of-week effect
        dow = dt.weekday()
        dow_alpha = 0.05
        observed_effect = value - self.mean_census
        self.day_of_week_effects[dow] = (
            dow_alpha * observed_effect +
            (1 - dow_alpha) * self.day_of_week_effects[dow]
        )


class TransferRiskModel(BaseModel):
    """
    Transfer risk scoring model.
    
    Logistic regression-based model for predicting transfer probability.
    
    Model: P(transfer) = 1 / (1 + exp(-(β₀ + β₁x₁ + ... + βₖxₖ)))
    
    Features:
    - Age
    - Principal diagnosis category
    - Charlson comorbidity index
    - ED arrival mode
    - Time of day
    - Current census
    - Specialist availability
    """
    
    def __init__(self):
        super().__init__(name="transfer_risk")
        
        # Model coefficients (default values based on typical CAH patterns)
        self.intercept: float = -2.0  # Base log-odds (low transfer rate)
        self.coefficients: dict[str, float] = {
            "age_over_65": 0.3,
            "age_over_80": 0.5,
            "high_acuity_dx": 1.2,
            "cardiac_dx": 0.8,
            "stroke_dx": 1.5,
            "trauma_dx": 1.0,
            "surgical_need": 1.8,
            "icu_need": 2.0,
            "specialist_unavailable": 0.7,
            "night_admission": 0.2,
            "weekend_admission": 0.15,
            "high_census": 0.3,
            "comorbidity_score": 0.1,  # Per Charlson point
        }
        
        # High-acuity diagnosis prefixes (ICD-10)
        self.high_acuity_prefixes = [
            "I21", "I22",  # MI
            "I60", "I61", "I62", "I63", "I64",  # Stroke
            "S",  # Trauma
            "T",  # Poisoning/toxic effects
        ]
        
        self.cardiac_prefixes = ["I2", "I3", "I4", "I5"]
        self.stroke_prefixes = ["I6", "G45"]
    
    def train(self, encounters: list[ClinicalEncounter]) -> None:
        """
        Train on historical encounter data.
        
        In practice, this would use logistic regression to learn coefficients.
        For MV-CAHI compliance, we use simplified calibration.
        """
        if len(encounters) < 100:
            # Use default coefficients
            self.trained = True
            self.last_trained = datetime.now()
            self.training_samples = len(encounters)
            return
        
        # Calculate actual transfer rate
        transfers = sum(1 for e in encounters if e.is_transfer())
        transfer_rate = transfers / len(encounters)
        
        # Adjust intercept to match observed rate
        # P = 1/(1+exp(-intercept)) when all features are 0
        # Solve for intercept: intercept = log(P/(1-P))
        if 0 < transfer_rate < 1:
            self.intercept = math.log(transfer_rate / (1 - transfer_rate))
        
        self.trained = True
        self.last_trained = datetime.now()
        self.training_samples = len(encounters)
    
    def predict(
        self,
        encounter: ClinicalEncounter,
        current_census: int = 10,
        specialist_available: bool = True,
    ) -> RiskScore:
        """
        Calculate transfer risk score.
        
        Args:
            encounter: The clinical encounter to score
            current_census: Current facility census
            specialist_available: Whether relevant specialist is available
            
        Returns:
            RiskScore with probability and contributing factors
        """
        factors = []
        log_odds = self.intercept
        
        # Age factors
        admit_date = encounter.admit_datetime.date()
        # Assume age if not available (would normally come from patient data)
        age_estimate = 65  # Default
        
        if age_estimate >= 80:
            contribution = self.coefficients["age_over_80"]
            log_odds += contribution
            factors.append(("Age ≥80", contribution))
        elif age_estimate >= 65:
            contribution = self.coefficients["age_over_65"]
            log_odds += contribution
            factors.append(("Age ≥65", contribution))
        
        # Diagnosis factors
        dx = encounter.principal_diagnosis.upper()
        
        # High acuity check
        if any(dx.startswith(p) for p in self.high_acuity_prefixes):
            contribution = self.coefficients["high_acuity_dx"]
            log_odds += contribution
            factors.append(("High-acuity diagnosis", contribution))
        
        # Cardiac
        if any(dx.startswith(p) for p in self.cardiac_prefixes):
            contribution = self.coefficients["cardiac_dx"]
            log_odds += contribution
            factors.append(("Cardiac diagnosis", contribution))
        
        # Stroke
        if any(dx.startswith(p) for p in self.stroke_prefixes):
            contribution = self.coefficients["stroke_dx"]
            log_odds += contribution
            factors.append(("Stroke/CVA", contribution))
        
        # Specialist availability
        if not specialist_available:
            contribution = self.coefficients["specialist_unavailable"]
            log_odds += contribution
            factors.append(("Specialist unavailable", contribution))
        
        # Time factors
        hour = encounter.admit_datetime.hour
        if hour < 7 or hour >= 19:
            contribution = self.coefficients["night_admission"]
            log_odds += contribution
            factors.append(("Night admission", contribution))
        
        if encounter.admit_datetime.weekday() >= 5:
            contribution = self.coefficients["weekend_admission"]
            log_odds += contribution
            factors.append(("Weekend admission", contribution))
        
        # Census factor
        if current_census >= 20:  # High census for CAH
            contribution = self.coefficients["high_census"]
            log_odds += contribution
            factors.append(("High census", contribution))
        
        # Calculate probability
        probability = 1 / (1 + math.exp(-log_odds))
        score = probability * 100
        
        # Determine tier
        tier = RiskTier.from_score(score)
        
        # Confidence based on training data
        confidence = min(0.95, 0.5 + 0.001 * self.training_samples)
        
        return RiskScore(
            score=score,
            tier=tier,
            factors=factors,
            confidence=confidence,
        )


class DenialProbabilityModel(BaseModel):
    """
    Claim denial probability model.
    
    Predicts probability of claim denial by category.
    """
    
    def __init__(self):
        super().__init__(name="denial_probability")
        
        # Base denial rates by payer type
        self.payer_rates: dict[str, float] = {
            "medicare": 0.08,
            "medicaid": 0.12,
            "commercial": 0.15,
            "self_pay": 0.05,
            "default": 0.10,
        }
        
        # Risk factors
        self.risk_factors: dict[str, float] = {
            "missing_diagnosis": 0.8,
            "invalid_diagnosis_format": 0.6,
            "missing_procedure": 0.2,
            "missing_authorization": 0.7,
            "prior_denial_same_dx": 0.3,
            "complex_case": 0.15,
            "high_charge": 0.1,
        }
    
    def train(self, historical_claims: list[dict]) -> None:
        """Train on historical claim outcomes."""
        if len(historical_claims) < 50:
            self.trained = True
            self.last_trained = datetime.now()
            self.training_samples = len(historical_claims)
            return
        
        # Calculate payer-specific denial rates
        payer_denials: dict[str, list[bool]] = {}
        
        for claim in historical_claims:
            payer = claim.get("payer_type", "default").lower()
            denied = claim.get("denied", False)
            
            if payer not in payer_denials:
                payer_denials[payer] = []
            payer_denials[payer].append(denied)
        
        for payer, outcomes in payer_denials.items():
            if outcomes:
                self.payer_rates[payer] = sum(outcomes) / len(outcomes)
        
        self.trained = True
        self.last_trained = datetime.now()
        self.training_samples = len(historical_claims)
    
    def predict(
        self,
        payer_type: str,
        diagnosis_codes: list[str],
        procedure_codes: list[str],
        has_authorization: bool = True,
        total_charges: float = 0.0,
    ) -> dict[str, float]:
        """
        Predict denial probability.
        
        Returns probabilities by denial category.
        """
        # Base rate from payer
        base_rate = self.payer_rates.get(payer_type.lower(), self.payer_rates["default"])
        
        # Adjust for risk factors
        risk_adjustment = 0.0
        
        # Diagnosis checks
        if not diagnosis_codes:
            risk_adjustment += self.risk_factors["missing_diagnosis"]
        else:
            for dx in diagnosis_codes:
                if not self._is_valid_icd10(dx):
                    risk_adjustment += self.risk_factors["invalid_diagnosis_format"]
                    break
        
        # Procedure checks
        if not procedure_codes:
            risk_adjustment += self.risk_factors["missing_procedure"]
        
        # Authorization
        if not has_authorization and payer_type.lower() in ("commercial",):
            risk_adjustment += self.risk_factors["missing_authorization"]
        
        # High charges
        if total_charges > 50000:
            risk_adjustment += self.risk_factors["high_charge"]
        
        # Overall probability (bounded)
        overall = min(0.95, base_rate + risk_adjustment)
        
        # Break down by category
        return {
            "overall": overall,
            "eligibility": base_rate * 0.2,
            "medical_necessity": overall * 0.3 if total_charges > 10000 else overall * 0.15,
            "coding": risk_adjustment * 0.5 if risk_adjustment > 0 else base_rate * 0.1,
            "authorization": 0.0 if has_authorization else self.risk_factors["missing_authorization"],
            "other": base_rate * 0.1,
        }
    
    def _is_valid_icd10(self, code: str) -> bool:
        """Basic ICD-10 validation."""
        if not code or len(code) < 3:
            return False
        return code[0].isalpha() and code[1:3].isdigit()

