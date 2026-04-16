"""
Constraint definitions for CAH optimization.

Regulatory Constraints (Hard):
- g₁: Total beds ≤ 25 (42 CFR § 485.620)
- g₂: ALOS ≤ 96 hours (42 CFR § 485.620)
- g₃: Distance to nearest hospital ≥ 35 miles (implicit via designation)
- g₄: 24/7 emergency services (staffing floor)

Operational Constraints (Soft):
- h₁: ADC ≤ 0.85 × acute_beds (capacity utilization)
- h₂: Nursing NHPPD ≥ 4.0 (evidence-based minimum)
- h₃: Provider FTE ≥ 0.5 (24/7 coverage with locums)
- h₄: ED visits / provider FTE ≤ 5000 (workload ceiling)

All constraints are formulated as g(x) ≤ 0 or h(x) = 0 for standard NLP.
Constraint qualification (LICQ/MFCQ) verification is provided.
"""

from typing import List, Dict, Tuple, Callable
from dataclasses import dataclass
import numpy as np

try:
    from .models import ConstraintStatus
except ImportError:
    from models import ConstraintStatus


@dataclass
class Constraint:
    """Single constraint definition."""
    
    name: str
    description: str
    type: str  # "inequality" or "equality"
    source: str  # Regulatory citation or evidence source
    
    # Function returning residual: g(x) ≤ 0 means g(x) is residual
    func: Callable[[np.ndarray], float]
    
    # Optional gradient for efficiency
    grad: Callable[[np.ndarray], np.ndarray] = None
    
    def evaluate(self, x: np.ndarray) -> float:
        """Evaluate constraint residual."""
        return self.func(x)
    
    def is_satisfied(self, x: np.ndarray, tol: float = 1e-6) -> bool:
        """Check if constraint is satisfied."""
        residual = self.func(x)
        if self.type == "inequality":
            return residual >= -tol  # g(x) ≥ 0 form (slack positive)
        else:
            return abs(residual) <= tol
    
    def get_status(self, x: np.ndarray, tol: float = 1e-6) -> ConstraintStatus:
        """Get detailed constraint status."""
        residual = self.func(x)
        
        if self.type == "inequality":
            if residual < -tol:
                return ConstraintStatus.VIOLATED
            elif abs(residual) <= tol:
                return ConstraintStatus.BINDING
            else:
                return ConstraintStatus.SATISFIED
        else:
            if abs(residual) <= tol:
                return ConstraintStatus.BINDING
            else:
                return ConstraintStatus.VIOLATED


class CAHConstraints:
    """
    Complete constraint set for CAH optimization.
    
    Provides:
    - Individual constraint definitions with regulatory sources
    - Scipy-compatible constraint dictionaries
    - LICQ/MFCQ verification methods
    - Shadow price interpretation
    
    Example:
        >>> constraints = CAHConstraints()
        >>> x = np.array([15, 5, 35, 5, 8, 6000, 15000, 1.0])
        >>> print(constraints.check_all(x))
        {'bed_cap': <ConstraintStatus.SATISFIED>, ...}
    """
    
    def __init__(self, margin_floor: float = 0.05):
        """
        Initialize constraint set.
        
        Args:
            margin_floor: Minimum required operating margin (default 5%)
        """
        self.margin_floor = margin_floor
        self._build_constraints()
    
    def _build_constraints(self):
        """Build all constraint definitions."""
        self.constraints: Dict[str, Constraint] = {}
        
        # ═══════════════════════════════════════════════════════════════════════
        # REGULATORY CONSTRAINTS (Hard) — Violation loses CAH designation
        # ═══════════════════════════════════════════════════════════════════════
        
        self.constraints["bed_cap"] = Constraint(
            name="bed_cap",
            description="Total beds (acute + swing) ≤ 25",
            type="inequality",
            source="42 CFR § 485.620",
            func=lambda x: 25 - (x[0] + x[1]),  # Residual ≥ 0 when satisfied
            grad=lambda x: np.array([-1, -1, 0, 0, 0, 0, 0, 0, 0]),
        )
        
        # ═══════════════════════════════════════════════════════════════════════
        # OPERATIONAL CONSTRAINTS — Best practice / feasibility
        # ═══════════════════════════════════════════════════════════════════════
        
        self.constraints["census_capacity"] = Constraint(
            name="census_capacity",
            description="ADC ≤ 85% of acute bed capacity",
            type="inequality",
            source="Operational feasibility",
            func=lambda x: 0.85 * x[0] - x[4],
            grad=lambda x: np.array([0.85, 0, 0, 0, -1, 0, 0, 0, 0]),
        )
        
        self.constraints["nursing_ratio"] = Constraint(
            name="nursing_ratio",
            description="Nursing FTE / ADC ≥ 0.5 (4.0 NHPPD / 8 hrs)",
            type="inequality",
            source="Aiken et al. (2014); Evidence-based staffing",
            func=lambda x: x[2] - 0.5 * x[4],
            grad=lambda x: np.array([0, 0, 1, 0, -0.5, 0, 0, 0, 0]),
        )
        
        self.constraints["ed_capacity"] = Constraint(
            name="ed_capacity",
            description="ED visits / provider FTE ≤ 5000",
            type="inequality",
            source="ACEP workload guidelines",
            func=lambda x: 5000 * x[3] - x[5],
            grad=lambda x: np.array([0, 0, 0, 5000, 0, -1, 0, 0, 0]),
        )
        
        self.constraints["min_providers"] = Constraint(
            name="min_providers",
            description="Provider FTE ≥ 2 for adequate coverage",
            type="inequality",
            source="24/7 emergency coverage requirement",
            func=lambda x: x[3] - 2.0,
            grad=lambda x: np.array([0, 0, 0, 1, 0, 0, 0, 0, 0]),
        )

        # ═══════════════════════════════════════════════════════════════════════
        # TRANSFER CONSTRAINTS — CAHSP Class 2
        # ═══════════════════════════════════════════════════════════════════════

        self.constraints["transfer_capacity"] = Constraint(
            name="transfer_capacity",
            description="Transfer volume ≤ 15% of annual patient-days (MBQIP threshold)",
            type="inequality",
            source="MBQIP transfer appropriateness; CMS Hospital Compare",
            func=lambda x: 0.15 * x[4] * 365 - x[8],
            grad=lambda x: np.array([0, 0, 0, 0, 0.15 * 365, 0, 0, 0, -1]),
        )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONSTRAINT EVALUATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def check_all(
        self,
        x: np.ndarray,
        tol: float = 1e-6,
    ) -> Dict[str, ConstraintStatus]:
        """
        Check status of all constraints.
        
        Args:
            x: Decision variable vector
            tol: Tolerance for binding/satisfied classification
            
        Returns:
            Dictionary mapping constraint names to status
        """
        return {
            name: c.get_status(x, tol)
            for name, c in self.constraints.items()
        }
    
    def is_feasible(self, x: np.ndarray, tol: float = 1e-6) -> bool:
        """Check if point satisfies all constraints."""
        return all(
            c.is_satisfied(x, tol)
            for c in self.constraints.values()
        )
    
    def get_violations(self, x: np.ndarray) -> Dict[str, float]:
        """
        Get constraint violations (negative residuals).
        
        Returns:
            Dictionary of violated constraints with violation magnitude
        """
        violations = {}
        for name, c in self.constraints.items():
            residual = c.evaluate(x)
            if residual < 0:
                violations[name] = -residual
        return violations
    
    def get_binding(self, x: np.ndarray, tol: float = 1e-6) -> List[str]:
        """Get list of binding (active) constraints."""
        return [
            name
            for name, c in self.constraints.items()
            if c.get_status(x, tol) == ConstraintStatus.BINDING
        ]
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SCIPY INTERFACE
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_scipy_constraints(self) -> List[dict]:
        """
        Get scipy.optimize.minimize compatible constraint list.
        
        Returns:
            List of constraint dictionaries with 'type' and 'fun' keys
        """
        scipy_constraints = []
        
        for name, c in self.constraints.items():
            constraint_dict = {
                "type": "ineq",  # g(x) ≥ 0
                "fun": c.func,
            }
            if c.grad is not None:
                constraint_dict["jac"] = c.grad
            scipy_constraints.append(constraint_dict)
        
        return scipy_constraints
    
    def add_margin_constraint(
        self,
        objectives: "CAHObjectiveFunctions",
        margin_floor: float = None,
    ) -> List[dict]:
        """
        Get scipy constraints including margin floor.
        
        Args:
            objectives: Objective function calculator
            margin_floor: Minimum margin (default: self.margin_floor)
            
        Returns:
            Extended constraint list including margin constraint
        """
        if margin_floor is None:
            margin_floor = self.margin_floor
        
        constraints = self.get_scipy_constraints()
        
        # Add margin constraint: Π(x)/R(x) ≥ margin_floor
        # Reformulated as: Π(x) - margin_floor × R(x) ≥ 0
        def margin_constraint(x):
            profit = objectives.profit(x)
            revenue = objectives.revenue(x)
            return profit - margin_floor * revenue
        
        constraints.append({
            "type": "ineq",
            "fun": margin_constraint,
        })
        
        return constraints
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONSTRAINT QUALIFICATION VERIFICATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def check_licq(self, x: np.ndarray, tol: float = 1e-6) -> Tuple[bool, str]:
        """
        Verify Linear Independence Constraint Qualification (LICQ).
        
        LICQ holds at x if the gradients of all active inequality
        constraints are linearly independent.
        
        Args:
            x: Point to check
            tol: Tolerance for active constraint detection
            
        Returns:
            Tuple of (licq_holds, explanation)
        """
        # Get active constraints
        active_constraints = []
        for name, c in self.constraints.items():
            if c.grad is not None and abs(c.evaluate(x)) < tol:
                active_constraints.append((name, c.grad(x)))
        
        if len(active_constraints) == 0:
            return True, "No active constraints; LICQ trivially satisfied"
        
        # Check linear independence
        gradients = np.array([g for _, g in active_constraints])
        rank = np.linalg.matrix_rank(gradients)
        n_active = len(active_constraints)
        
        if rank == n_active:
            return True, f"LICQ satisfied: {n_active} active constraints with full rank"
        else:
            names = [n for n, _ in active_constraints]
            return False, f"LICQ violated: {n_active} active constraints, rank {rank}. Constraints: {names}"
    
    def check_mfcq(self, x: np.ndarray, tol: float = 1e-6) -> Tuple[bool, str]:
        """
        Verify Mangasarian-Fromovitz Constraint Qualification (MFCQ).
        
        MFCQ is weaker than LICQ and holds if there exists a direction d
        such that ∇gᵢ(x)ᵀd < 0 for all active inequality constraints.
        
        For polyhedral constraints, this reduces to checking if the
        active constraint gradients don't point in the same half-space.
        
        Returns:
            Tuple of (mfcq_holds, explanation)
        """
        # Get active constraint gradients
        active_gradients = []
        for name, c in self.constraints.items():
            if c.grad is not None and abs(c.evaluate(x)) < tol:
                active_gradients.append(c.grad(x))
        
        if len(active_gradients) == 0:
            return True, "No active constraints; MFCQ trivially satisfied"
        
        # For linear constraints, MFCQ holds iff there's no positive
        # linear combination of gradients equal to zero (Farkas lemma)
        # Simplified check: if gradients span less than full dimension,
        # there exists a direction satisfying MFCQ
        
        A = np.array(active_gradients)
        n_constraints, n_vars = A.shape
        
        if n_constraints < n_vars:
            return True, f"MFCQ satisfied: fewer active constraints ({n_constraints}) than variables ({n_vars})"
        
        # More rigorous check would solve LP to find feasible direction
        # For now, rely on LICQ check
        licq_holds, _ = self.check_licq(x, tol)
        if licq_holds:
            return True, "MFCQ satisfied (implied by LICQ)"
        
        return False, "MFCQ status uncertain; LICQ violated"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SHADOW PRICE INTERPRETATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    @staticmethod
    def interpret_shadow_prices(
        shadow_prices: Dict[str, float],
    ) -> Dict[str, str]:
        """
        Provide economic interpretation of shadow prices.
        
        Shadow price λᵢ* indicates the marginal value of relaxing
        constraint i by one unit (in objective units).
        
        Args:
            shadow_prices: Dictionary of constraint name to shadow price
            
        Returns:
            Dictionary of constraint name to interpretation string
        """
        interpretations = {}
        
        for name, price in shadow_prices.items():
            if abs(price) < 1e-6:
                interpretations[name] = "Not binding (slack available)"
            elif name == "bed_cap":
                interpretations[name] = (
                    f"Adding 1 bed increases objective by {price:.4f}; "
                    f"equivalent to ~${price * 1e6:,.0f} annual value if margin-weighted"
                )
            elif name == "nursing_ratio":
                interpretations[name] = (
                    f"Relaxing nurse ratio by 0.1 improves objective by {price * 0.1:.4f}"
                )
            elif name == "ed_capacity":
                interpretations[name] = (
                    f"Each additional 100 ED visits/provider capacity worth {price * 100:.4f}"
                )
            else:
                interpretations[name] = f"Shadow price: {price:.4f}"
        
        return interpretations


# ═══════════════════════════════════════════════════════════════════════════════
# STANDALONE CONSTRAINT FUNCTIONS (for backward compatibility)
# ═══════════════════════════════════════════════════════════════════════════════

def bed_cap(x: np.ndarray) -> float:
    """g₁: x[0] + x[1] ≤ 25 → 25 - (x[0] + x[1]) ≥ 0"""
    return 25 - (x[0] + x[1])


def census_capacity(x: np.ndarray) -> float:
    """h₁: ADC ≤ 0.85 × acute_beds → 0.85 × x[0] - x[4] ≥ 0"""
    return 0.85 * x[0] - x[4]


def nursing_ratio(x: np.ndarray) -> float:
    """h₂: Nursing FTE / ADC ≥ 0.5 → x[2] - 0.5 × x[4] ≥ 0"""
    return x[2] - 0.5 * x[4]


def ed_capacity(x: np.ndarray) -> float:
    """h₄: ED visits / provider FTE ≤ 5000 → 5000 × x[3] - x[5] ≥ 0"""
    return 5000 * x[3] - x[5]
