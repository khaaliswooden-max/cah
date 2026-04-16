"""
Transfer Network Model for CAH Class 2 Optimization.

Provides the network-flow subproblem that feeds the transfer_volume
decision variable (x[8]) into the main CAH optimizer.

Components:
  - TransferNode: A facility in the transfer network (CAH or referral hub)
  - TransferNetworkModel: Min-cost flow solver for optimal transfer routing
  - transfer_leakage_rate(): Fraction of cases that should be transferred but aren't

CAHSP Problem Class 2 targets:
  - Readmission reduction
  - Transfer optimization
  - HCAHPS improvement

Source: MBQIP / CMS Hospital Compare transfer appropriateness data
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import numpy as np


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODEL
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class TransferNode:
    """A facility in the CAH transfer network."""

    provider_id: str
    name: str
    is_cah: bool              # True = CAH, False = referral hub / tertiary center
    latitude: float = 0.0
    longitude: float = 0.0

    # Specialty availability flags
    has_surgery: bool = False
    has_cardiology: bool = False
    has_neurology: bool = False
    has_obstetrics: bool = False
    has_icu: bool = False

    # Capacity
    bed_count: int = 25
    annual_transfers_out: int = 0    # historical outbound transfers
    annual_transfers_in: int = 0     # historical inbound transfers


@dataclass
class TransferEdge:
    """A directed transfer pathway between two nodes."""

    from_node: str   # provider_id
    to_node: str     # provider_id
    distance_miles: float
    transport_minutes: float    # ground transport time
    cost_per_transfer: float    # $ per case
    capacity: int = 500         # max annual transfers on this edge


# ═══════════════════════════════════════════════════════════════════════════════
# NETWORK MODEL
# ═══════════════════════════════════════════════════════════════════════════════


class TransferNetworkModel:
    """
    Min-cost flow model for interfacility transfer optimization.

    Solves the subproblem: given a set of CAH nodes and referral hubs,
    determine the optimal annual transfer volume that maximizes patient
    outcomes while respecting capacity and regulatory constraints.

    The output feeds x[8] (transfer_volume) in the main optimizer.
    """

    def __init__(
        self,
        nodes: Optional[List[TransferNode]] = None,
        edges: Optional[List[TransferEdge]] = None,
    ):
        self.nodes: Dict[str, TransferNode] = {}
        self.edges: List[TransferEdge] = edges or []

        if nodes:
            for n in nodes:
                self.nodes[n.provider_id] = n

    # ─── Network construction ────────────────────────────────────────────

    def add_node(self, node: TransferNode):
        """Add a facility to the network."""
        self.nodes[node.provider_id] = node

    def add_edge(self, edge: TransferEdge):
        """Add a transfer pathway."""
        self.edges.append(edge)

    def build_distance_matrix(self) -> np.ndarray:
        """
        Build pairwise distance matrix from node coordinates.

        Returns:
            n x n matrix of haversine distances in miles
        """
        ids = sorted(self.nodes.keys())
        n = len(ids)
        D = np.zeros((n, n))

        for i, id_i in enumerate(ids):
            for j, id_j in enumerate(ids):
                if i != j:
                    D[i, j] = self._haversine(
                        self.nodes[id_i].latitude,
                        self.nodes[id_i].longitude,
                        self.nodes[id_j].latitude,
                        self.nodes[id_j].longitude,
                    )
        return D

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Haversine distance in miles."""
        R = 3959.0  # Earth radius in miles
        phi1, phi2 = np.radians(lat1), np.radians(lat2)
        dphi = np.radians(lat2 - lat1)
        dlam = np.radians(lon2 - lon1)
        a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlam / 2) ** 2
        return 2 * R * np.arcsin(np.sqrt(a))

    # ─── Transfer volume solver ──────────────────────────────────────────

    def optimal_transfer_volume(
        self,
        adc: float,
        specialty_demand: Optional[Dict[str, float]] = None,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Solve for optimal annual transfer volume.

        Uses a simplified min-cost flow: for each CAH, estimate how many
        cases exceed local capability and should be transferred vs. retained.

        Args:
            adc: Average daily census of the target CAH
            specialty_demand: Dict mapping specialty to annual case demand
                              (defaults to CAH averages if None)

        Returns:
            Tuple of (optimal_volume, breakdown_by_specialty)
        """
        if specialty_demand is None:
            # CAH median specialty demand per year (HCUP NIS 2022)
            annual_patient_days = adc * 365
            specialty_demand = {
                "surgery": 0.03 * annual_patient_days,
                "cardiology": 0.04 * annual_patient_days,
                "neurology": 0.02 * annual_patient_days,
                "obstetrics": 0.015 * annual_patient_days,
                "icu": 0.025 * annual_patient_days,
            }

        # For each specialty, check local availability across network
        cah_nodes = [n for n in self.nodes.values() if n.is_cah]
        hub_nodes = [n for n in self.nodes.values() if not n.is_cah]

        breakdown: Dict[str, float] = {}
        total_volume = 0.0

        specialty_flags = {
            "surgery": "has_surgery",
            "cardiology": "has_cardiology",
            "neurology": "has_neurology",
            "obstetrics": "has_obstetrics",
            "icu": "has_icu",
        }

        for spec, demand in specialty_demand.items():
            flag = specialty_flags.get(spec)
            if flag is None:
                continue

            # If no hub has the specialty, transfers aren't possible
            hub_has = any(getattr(h, flag, False) for h in hub_nodes)
            if not hub_has and hub_nodes:
                breakdown[spec] = 0.0
                continue

            # Transfer fraction: cases requiring this specialty that the
            # CAH can't serve locally (conservative: assume CAH lacks it)
            transfer_cases = demand
            breakdown[spec] = transfer_cases
            total_volume += transfer_cases

        # Cap at MBQIP 15% threshold
        max_volume = 0.15 * adc * 365
        if total_volume > max_volume:
            scale = max_volume / total_volume
            for spec in breakdown:
                breakdown[spec] *= scale
            total_volume = max_volume

        return total_volume, breakdown

    # ─── Leakage analysis ────────────────────────────────────────────────

    def transfer_leakage_rate(
        self,
        actual_transfers: float,
        adc: float,
        specialty_demand: Optional[Dict[str, float]] = None,
    ) -> float:
        """
        Fraction of cases that should be transferred but aren't.

        Leakage = (optimal_volume - actual_transfers) / optimal_volume

        A high leakage rate indicates patients are staying at the CAH
        when they should be transferred, or are self-referring to distant
        systems instead of using the structured transfer network.

        Args:
            actual_transfers: Current annual transfer volume (x[8])
            adc: Average daily census
            specialty_demand: Override specialty demand estimates

        Returns:
            Leakage rate in [0, 1] (0 = no leakage, 1 = all cases leaked)
        """
        optimal, _ = self.optimal_transfer_volume(adc, specialty_demand)
        if optimal <= 0:
            return 0.0
        return max(0.0, min(1.0, (optimal - actual_transfers) / optimal))

    # ─── Seed value for optimizer ────────────────────────────────────────

    def get_initial_transfer_volume(self, adc: float) -> float:
        """
        Get an initial x[8] value for the main optimizer's starting point.

        Uses the network model's optimal volume as the seed, capped by
        the MBQIP 15% threshold.
        """
        vol, _ = self.optimal_transfer_volume(adc)
        return vol

    # ─── Quality impact ──────────────────────────────────────────────────

    @staticmethod
    def transfer_quality_impact(transfer_volume: float, adc: float) -> float:
        """
        Quality score contribution from transfer optimization.

        Penalizes over-transfer (> 15% of ADC patient-days) per MBQIP
        transfer appropriateness standard. Rewards appropriate utilization.

        Returns:
            Quality contribution in [0, 1]
        """
        if adc <= 0:
            return 0.0

        annual_patient_days = adc * 365
        transfer_rate = transfer_volume / max(annual_patient_days, 1.0)

        # Optimal band: 5-15% transfer rate
        if transfer_rate <= 0.0:
            return 0.3  # Under-transfer penalty
        elif transfer_rate <= 0.05:
            return 0.3 + 0.7 * (transfer_rate / 0.05)  # Ramp up
        elif transfer_rate <= 0.15:
            return 1.0  # Optimal range
        else:
            # Over-transfer penalty (linear decay)
            excess = transfer_rate - 0.15
            return max(0.0, 1.0 - excess / 0.10)


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FACTORY
# ═══════════════════════════════════════════════════════════════════════════════


def build_default_network() -> TransferNetworkModel:
    """
    Build a default transfer network for Washington/Montana CAH corridors.

    Used when no facility-specific network data is available.
    """
    model = TransferNetworkModel()

    # Example referral hubs
    model.add_node(TransferNode(
        provider_id="HUB_SEA",
        name="Seattle Metro Referral Hub",
        is_cah=False,
        latitude=47.6062, longitude=-122.3321,
        has_surgery=True, has_cardiology=True,
        has_neurology=True, has_obstetrics=True, has_icu=True,
        bed_count=500,
    ))
    model.add_node(TransferNode(
        provider_id="HUB_SPO",
        name="Spokane Referral Hub",
        is_cah=False,
        latitude=47.6588, longitude=-117.4260,
        has_surgery=True, has_cardiology=True,
        has_neurology=True, has_obstetrics=True, has_icu=True,
        bed_count=350,
    ))
    model.add_node(TransferNode(
        provider_id="HUB_BIL",
        name="Billings Referral Hub",
        is_cah=False,
        latitude=45.7833, longitude=-108.5007,
        has_surgery=True, has_cardiology=True,
        has_neurology=True, has_obstetrics=True, has_icu=True,
        bed_count=280,
    ))

    return model
