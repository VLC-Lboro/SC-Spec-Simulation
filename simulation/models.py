from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional


DemandType = Literal["poisson", "normal", "deterministic"]


@dataclass
class OEMOrderRecord:
    order_id: int
    qty: int
    day_placed: int
    day_shipped: Optional[int] = None
    day_received: Optional[int] = None


@dataclass
class T1BacklogOrder:
    order_id: int
    qty: int
    day_received_from_oem: int
    day_shipped: Optional[int] = None


@dataclass
class T23BacklogOrder:
    qty: int
    day_received_from_t1: int


@dataclass
class ShipmentToT1:
    qty: int
    dispatch_day: int
    arrival_day: int


@dataclass
class ShipmentToOEM:
    order_id: int
    qty: int
    dispatch_day: int
    arrival_day: int


@dataclass
class VisibilityFlags:
    share_forecast_oem_to_t1: bool
    share_oem_inventory_to_t1: bool
    share_t23_capacity_to_t1: bool


@dataclass
class PolicyParams:
    S_oem: float
    S_t1: float
    beta_f: float = 0.0
    alpha_inv: float = 0.0
    oem_inventory_target: float = 0.0
    oem_forecast_horizon: int = 7


@dataclass
class SimulationConfig:
    simulation_horizon: int = 180
    random_seed: int = 42
    demand_distribution_type: DemandType = "poisson"
    demand_lambda: float = 20.0
    demand_mean: float = 20.0
    demand_std_dev: float = 3.0
    demand_deterministic_value: int = 20
    transport_delay_t1_to_oem: int = 2
    transport_delay_t23_to_t1: int = 2
    t1_daily_capacity: int = 40
    t23_daily_capacity: int = 50
    initial_oem_inventory: int = 60
    initial_t1_inventory: int = 80
    selected_scenario_id: int = 1
    replications_per_scenario: int = 1
    policy_params: PolicyParams = field(default_factory=lambda: PolicyParams(S_oem=70, S_t1=90))


@dataclass
class DailyMetrics:
    daily_oem_demand: List[int] = field(default_factory=list)
    oem_to_t1_orders: List[int] = field(default_factory=list)
    t1_to_t23_orders: List[int] = field(default_factory=list)
    t1_backlog_units: List[int] = field(default_factory=list)
    t1_on_hand: List[int] = field(default_factory=list)
    t1_shipments_to_oem: List[int] = field(default_factory=list)
    t23_backlog_units: List[int] = field(default_factory=list)
    t23_production: List[int] = field(default_factory=list)
    oem_on_hand: List[int] = field(default_factory=list)


@dataclass
class SimulationState:
    current_day: int
    oem_on_hand: int
    t1_on_hand: int
    oem_orders: Dict[int, OEMOrderRecord] = field(default_factory=dict)
    t1_backlog_queue: List[T1BacklogOrder] = field(default_factory=list)
    t1_inbound_shipments: List[ShipmentToT1] = field(default_factory=list)
    t1_outbound_shipments: List[ShipmentToOEM] = field(default_factory=list)
    t23_order_backlog_queue: List[T23BacklogOrder] = field(default_factory=list)
    next_order_id: int = 1


@dataclass
class KPIResults:
    mean_lead_time: Optional[float]
    p95_lead_time: Optional[float]
    std_lead_time: Optional[float]
    mean_t1_backlog_units: float
    max_t1_backlog_units: int
    bullwhip_ratio: Optional[float]


@dataclass
class SimulationResult:
    config: SimulationConfig
    kpis: KPIResults
    daily_metrics: DailyMetrics
    completed_orders: List[OEMOrderRecord]
