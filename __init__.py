"""
CAH Dual-Objective Optimization Module
======================================

Constrained optimization for Critical Access Hospitals achieving:
- Minimum 5% operating margin (profitability floor)
- Maximum verified quality of care (MBQIP benchmarks)

Mathematical Framework:
- Charnes-Cooper transformation for fractional objectives
- Augmented ε-constraint for complete Pareto front exploration
- Bertsimas-Sim robust optimization for deterministic uncertainty handling
- KKT verification with LICQ constraint qualification

MV-CAHI Compliant: Executes in <5 seconds on standard hardware.

Example:
    >>> from cah.optimization import CAHOptimizer, CAHParameters
    >>> optimizer = CAHOptimizer(theta=0.6)
    >>> result = optimizer.optimize()
    >>> print(f"Margin: {result.margin:.2%}, Quality: {result.quality:.3f}")
"""

from .models import (
    CAHParameters,
    QualityBenchmarks,
    DecisionVariables,
    OptimizationResult,
    ParetoPoint,
)
from .objectives import CAHObjectiveFunctions
from .constraints import CAHConstraints
from .solver import CAHOptimizer
from .robust import RobustCAHOptimizer, UncertaintySet
from .pareto import ParetoFrontExplorer

__all__ = [
    # Data Models
    "CAHParameters",
    "QualityBenchmarks", 
    "DecisionVariables",
    "OptimizationResult",
    "ParetoPoint",
    # Core Components
    "CAHObjectiveFunctions",
    "CAHConstraints",
    "CAHOptimizer",
    # Extensions
    "RobustCAHOptimizer",
    "UncertaintySet",
    "ParetoFrontExplorer",
]

__version__ = "1.0.0"
