"""
Pareto front exploration for bi-objective CAH optimization.

Implements augmented ε-constraint method for complete Pareto front
generation, overcoming limitations of weighted-sum scalarization.

Key advantage: Can find Pareto optimal points in non-convex regions
of the objective space (impossible with weighted-sum).

Reference: Mavrotas (2009). "Effective implementation of the ε-constraint
           method in Multi-Objective Mathematical Programming problems."
           Applied Mathematics and Computation 213(2):455-465.
"""

from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass, field
import numpy as np
from scipy.optimize import minimize

from .models import (
    CAHParameters,
    QualityBenchmarks,
    DecisionVariables,
    ParetoPoint,
)
from .objectives import CAHObjectiveFunctions
from .constraints import CAHConstraints


@dataclass
class ParetoFront:
    """Collection of Pareto optimal points."""
    
    points: List[ParetoPoint] = field(default_factory=list)
    
    def add(self, point: ParetoPoint):
        """Add point and filter dominated solutions."""
        # Remove any points dominated by new point
        self.points = [p for p in self.points if not point.dominates(p)]
        
        # Only add if not dominated by existing points
        if not any(p.dominates(point) for p in self.points):
            self.points.append(point)
    
    def get_margins(self) -> np.ndarray:
        """Get array of margin values."""
        return np.array([p.margin for p in self.points])
    
    def get_qualities(self) -> np.ndarray:
        """Get array of quality values."""
        return np.array([p.quality for p in self.points])
    
    def get_ideal_point(self) -> Tuple[float, float]:
        """Get ideal (utopia) point: (max_margin, max_quality)."""
        if not self.points:
            return (0.0, 0.0)
        return (max(p.margin for p in self.points),
                max(p.quality for p in self.points))
    
    def get_nadir_point(self) -> Tuple[float, float]:
        """Get nadir point: (min_margin, min_quality) on Pareto front."""
        if not self.points:
            return (0.0, 0.0)
        return (min(p.margin for p in self.points),
                min(p.quality for p in self.points))
    
    def to_array(self) -> np.ndarray:
        """Convert to numpy array [[margin, quality], ...]."""
        if not self.points:
            return np.empty((0, 2))
        return np.array([[p.margin, p.quality] for p in self.points])


class ParetoFrontExplorer:
    """
    Complete Pareto front exploration using augmented ε-constraint.
    
    Algorithm:
    1. Compute ideal point by optimizing each objective separately
    2. Divide quality range [Q_min, Q_max] into n_points intervals
    3. For each interval bound ε:
       - Maximize margin subject to quality ≥ ε
       - Add small penalty on slack to ensure Pareto optimality
    4. Filter dominated points
    
    This method is COMPLETE: it can find all Pareto optimal points,
    including those in non-convex regions of the Pareto front.
    
    Example:
        >>> explorer = ParetoFrontExplorer()
        >>> front = explorer.explore(n_points=20)
        >>> print(f"Found {len(front.points)} Pareto optimal solutions")
    """
    
    def __init__(
        self,
        params: CAHParameters = None,
        benchmarks: QualityBenchmarks = None,
        margin_floor: float = 0.05,
    ):
        self.params = params or CAHParameters()
        self.benchmarks = benchmarks or QualityBenchmarks()
        self.margin_floor = margin_floor
        
        self.objectives = CAHObjectiveFunctions(self.params, self.benchmarks)
        self.constraints = CAHConstraints(margin_floor)
        self.variables = DecisionVariables()
        
        # Augmented ε-constraint parameter
        self.augmentation_coeff = 1e-4  # Small penalty on slack
    
    def explore(
        self,
        n_points: int = 20,
        seed: int = None,
    ) -> ParetoFront:
        """
        Generate complete Pareto front.
        
        Args:
            n_points: Number of points to generate on the front
            seed: Random seed for reproducibility
            
        Returns:
            ParetoFront containing all non-dominated solutions
        """
        rng = np.random.default_rng(seed)
        front = ParetoFront()
        
        # Step 1: Find anchor points (optimize each objective individually)
        x_max_margin, margin_max = self._optimize_margin_only(rng)
        x_max_quality, quality_max = self._optimize_quality_only(rng)
        
        # Add anchor points
        front.add(ParetoPoint(
            x=x_max_margin,
            margin=margin_max,
            quality=self.objectives.composite_quality(x_max_margin),
            epsilon=0.0,
        ))
        front.add(ParetoPoint(
            x=x_max_quality,
            margin=self.objectives.margin(x_max_quality),
            quality=quality_max,
            epsilon=quality_max,
        ))
        
        # Step 2: Determine quality range
        quality_min = self.objectives.composite_quality(x_max_margin)
        quality_range = np.linspace(quality_min, quality_max, n_points)
        
        # Step 3: ε-constraint sweep
        for epsilon in quality_range[1:-1]:  # Skip anchor points
            try:
                point = self._solve_epsilon_constraint(epsilon, rng)
                if point is not None:
                    front.add(point)
            except Exception:
                continue
        
        return front
    
    def explore_tchebycheff(
        self,
        n_points: int = 20,
        seed: int = None,
    ) -> ParetoFront:
        """
        Generate Pareto front using weighted Tchebycheff method.
        
        Minimizes: max_i { w_i × (f_i - z_i*) }
        
        This method is also COMPLETE and provides more uniform
        distribution of points along the Pareto front.
        """
        rng = np.random.default_rng(seed)
        front = ParetoFront()
        
        # Get ideal point
        x_max_margin, margin_ideal = self._optimize_margin_only(rng)
        x_max_quality, quality_ideal = self._optimize_quality_only(rng)
        ideal = (margin_ideal, quality_ideal)
        
        # Generate weight combinations
        weights = np.linspace(0.01, 0.99, n_points)
        
        for w in weights:
            weight_vector = (w, 1 - w)
            point = self._solve_tchebycheff(ideal, weight_vector, rng)
            if point is not None:
                front.add(point)
        
        return front
    
    def _optimize_margin_only(
        self,
        rng: np.random.Generator,
    ) -> Tuple[np.ndarray, float]:
        """Maximize margin subject to constraints."""
        bounds = self.variables.bounds
        scipy_constraints = self.constraints.add_margin_constraint(
            self.objectives,
            self.margin_floor,
        )
        
        best_x = None
        best_margin = -np.inf
        
        for _ in range(5):
            x0 = self.variables.get_random_point(rng)
            
            result = minimize(
                lambda x: -self.objectives.margin(x),
                x0,
                method="SLSQP",
                bounds=bounds,
                constraints=scipy_constraints,
                options={"maxiter": 300},
            )
            
            if result.success:
                margin = self.objectives.margin(result.x)
                if margin > best_margin:
                    best_margin = margin
                    best_x = result.x
        
        return best_x, best_margin
    
    def _optimize_quality_only(
        self,
        rng: np.random.Generator,
    ) -> Tuple[np.ndarray, float]:
        """Maximize quality subject to constraints."""
        bounds = self.variables.bounds
        scipy_constraints = self.constraints.add_margin_constraint(
            self.objectives,
            self.margin_floor,
        )
        
        best_x = None
        best_quality = -np.inf
        
        for _ in range(5):
            x0 = self.variables.get_random_point(rng)
            
            result = minimize(
                lambda x: -self.objectives.composite_quality(x),
                x0,
                method="SLSQP",
                bounds=bounds,
                constraints=scipy_constraints,
                options={"maxiter": 300},
            )
            
            if result.success:
                quality = self.objectives.composite_quality(result.x)
                if quality > best_quality:
                    best_quality = quality
                    best_x = result.x
        
        return best_x, best_quality
    
    def _solve_epsilon_constraint(
        self,
        epsilon: float,
        rng: np.random.Generator,
    ) -> Optional[ParetoPoint]:
        """
        Solve augmented ε-constraint subproblem.
        
        max  margin(x) + δ × s / R
        s.t. quality(x) + s = ε
             s ≥ 0
             original constraints
        
        where δ is small augmentation coefficient and R is quality range.
        """
        bounds = self.variables.bounds
        base_constraints = self.constraints.add_margin_constraint(
            self.objectives,
            self.margin_floor,
        )
        
        # Add quality ≥ epsilon constraint
        quality_constraint = {
            "type": "ineq",
            "fun": lambda x: self.objectives.composite_quality(x) - epsilon,
        }
        all_constraints = base_constraints + [quality_constraint]
        
        # Objective: maximize margin (with small augmentation on quality slack)
        def augmented_objective(x):
            margin = self.objectives.margin(x)
            quality = self.objectives.composite_quality(x)
            slack = max(0, quality - epsilon)
            return -(margin + self.augmentation_coeff * slack)
        
        x0 = self.variables.get_random_point(rng)
        
        result = minimize(
            augmented_objective,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=all_constraints,
            options={"maxiter": 300},
        )
        
        if result.success:
            x = result.x
            return ParetoPoint(
                x=x,
                margin=self.objectives.margin(x),
                quality=self.objectives.composite_quality(x),
                epsilon=epsilon,
            )
        
        return None
    
    def _solve_tchebycheff(
        self,
        ideal: Tuple[float, float],
        weights: Tuple[float, float],
        rng: np.random.Generator,
    ) -> Optional[ParetoPoint]:
        """
        Solve weighted Tchebycheff subproblem.
        
        min  max { w₁(z₁* - f₁(x)), w₂(z₂* - f₂(x)) }
        s.t. constraints
        """
        bounds = self.variables.bounds
        base_constraints = self.constraints.add_margin_constraint(
            self.objectives,
            self.margin_floor,
        )
        
        def tchebycheff_objective(x):
            margin = self.objectives.margin(x)
            quality = self.objectives.composite_quality(x)
            
            # Deviation from ideal (normalized)
            dev_margin = weights[0] * (ideal[0] - margin) / max(abs(ideal[0]), 1e-6)
            dev_quality = weights[1] * (ideal[1] - quality) / max(abs(ideal[1]), 1e-6)
            
            # Max deviation (Tchebycheff scalarization)
            return max(dev_margin, dev_quality)
        
        x0 = self.variables.get_random_point(rng)
        
        result = minimize(
            tchebycheff_objective,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=base_constraints,
            options={"maxiter": 300},
        )
        
        if result.success:
            x = result.x
            return ParetoPoint(
                x=x,
                margin=self.objectives.margin(x),
                quality=self.objectives.composite_quality(x),
                epsilon=0.0,
            )
        
        return None
    
    def hypervolume(self, front: ParetoFront, reference: Tuple[float, float] = None) -> float:
        """
        Compute hypervolume indicator for Pareto front quality.
        
        Hypervolume is the dominated region between the Pareto front
        and a reference point. Higher is better.
        
        Args:
            front: Pareto front to evaluate
            reference: Reference point (default: nadir point - 0.1)
            
        Returns:
            Hypervolume value
        """
        if not front.points:
            return 0.0
        
        if reference is None:
            nadir = front.get_nadir_point()
            reference = (nadir[0] - 0.1, nadir[1] - 0.1)
        
        # Simple 2D hypervolume calculation
        points = sorted(front.points, key=lambda p: p.margin, reverse=True)
        
        hv = 0.0
        prev_quality = reference[1]
        
        for p in points:
            if p.margin > reference[0] and p.quality > reference[1]:
                width = p.margin - reference[0]
                height = p.quality - prev_quality
                hv += width * height
                prev_quality = p.quality
        
        return hv
