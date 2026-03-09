from typing import Dict

from .models import PolicyParams, SimulationConfig, VisibilityFlags


def round_non_negative_int(value: float) -> int:
    return max(0, int(round(value)))


def get_visibility_flags(scenario_id: int) -> VisibilityFlags:
    if scenario_id == 1:
        return VisibilityFlags(False, False, False)
    if scenario_id == 2:
        return VisibilityFlags(True, False, False)
    if scenario_id == 3:
        return VisibilityFlags(False, True, False)
    if scenario_id == 4:
        return VisibilityFlags(False, False, True)
    if scenario_id == 5:
        return VisibilityFlags(True, True, True)
    raise ValueError("selected_scenario_id must be in {1,2,3,4,5}")


def expected_demand(config: SimulationConfig) -> float:
    if config.demand_distribution_type == "poisson":
        return config.demand_lambda
    if config.demand_distribution_type == "normal":
        return config.demand_mean
    return float(config.demand_deterministic_value)


def forecast_sum(current_day: int, horizon: int, simulation_horizon: int, expected: float) -> float:
    remaining_days = max(0, simulation_horizon - (current_day + 1))
    steps = min(horizon, remaining_days)
    return expected * steps


def oem_order_qty(ip_oem: int, params: PolicyParams) -> int:
    raw = params.S_oem - ip_oem
    return round_non_negative_int(raw)


def t1_order_qty(
    config: SimulationConfig,
    params: PolicyParams,
    ip_t1: int,
    oem_on_hand: int,
    current_day: int,
) -> int:
    flags = get_visibility_flags(config.selected_scenario_id)
    base_target = float(params.S_t1)

    if flags.share_forecast_oem_to_t1:
        f_sum = forecast_sum(
            current_day=current_day,
            horizon=params.oem_forecast_horizon,
            simulation_horizon=config.simulation_horizon,
            expected=expected_demand(config),
        )
        base_target = base_target + params.beta_f * f_sum

    if flags.share_oem_inventory_to_t1:
        base_target = base_target - params.alpha_inv * (oem_on_hand - params.oem_inventory_target)
        base_target = max(0.0, base_target)

    raw_order = max(0.0, base_target - ip_t1)

    if flags.share_t23_capacity_to_t1:
        raw_order = min(raw_order, float(config.t23_daily_capacity))

    return round_non_negative_int(raw_order)
