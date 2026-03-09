from simulation.engine import run_simulation
from simulation.models import PolicyParams, SimulationConfig


def base_config(**kwargs):
    cfg = SimulationConfig(
        simulation_horizon=40,
        random_seed=123,
        demand_distribution_type="deterministic",
        demand_deterministic_value=10,
        transport_delay_t1_to_oem=1,
        transport_delay_t23_to_t1=1,
        t1_daily_capacity=20,
        t23_daily_capacity=20,
        initial_oem_inventory=20,
        initial_t1_inventory=20,
        selected_scenario_id=1,
        replications_per_scenario=1,
        policy_params=PolicyParams(S_oem=30, S_t1=35),
    )
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


def test_runs_and_produces_metrics():
    result = run_simulation(base_config())
    assert len(result.daily_metrics.daily_oem_demand) == 40
    assert result.kpis.mean_t1_backlog_units >= 0
    assert result.kpis.max_t1_backlog_units >= 0


def test_no_negative_states_in_timeseries():
    result = run_simulation(base_config())
    assert min(result.daily_metrics.oem_on_hand) >= 0
    assert min(result.daily_metrics.t1_on_hand) >= 0
    assert min(result.daily_metrics.t1_backlog_units) >= 0
    assert min(result.daily_metrics.t23_backlog_units) >= 0


def test_capacity_visibility_caps_t1_orders():
    cfg = base_config(selected_scenario_id=4)
    cfg.policy_params = PolicyParams(S_oem=30, S_t1=100)
    cfg.t23_daily_capacity = 7
    result = run_simulation(cfg)
    assert max(result.daily_metrics.t1_to_t23_orders) <= 7


def test_bullwhip_undefined_for_zero_demand_variance():
    result = run_simulation(base_config(demand_distribution_type="deterministic", demand_deterministic_value=10))
    assert result.kpis.bullwhip_ratio is None


def test_large_oem_order_is_split_and_not_fifo_deadlocked():
    cfg = base_config(
        simulation_horizon=30,
        demand_distribution_type="deterministic",
        demand_deterministic_value=105,
        transport_delay_t1_to_oem=2,
        transport_delay_t23_to_t1=5,
        t1_daily_capacity=95,
        t23_daily_capacity=100,
        initial_oem_inventory=140,
        initial_t1_inventory=180,
        selected_scenario_id=1,
    )
    cfg.policy_params = PolicyParams(
        S_oem=160,
        S_t1=220,
        beta_f=1.6,
        alpha_inv=1.3,
        oem_inventory_target=160,
        oem_forecast_horizon=3,
    )

    result = run_simulation(cfg)
    # Regression check for prior all-zero shipments deadlock.
    assert sum(result.daily_metrics.t1_shipments_to_oem) > 0


def test_user_reported_baseline_pattern_has_many_shipping_days_not_two():
    cfg = SimulationConfig(
        simulation_horizon=365,
        replications_per_scenario=1,
        random_seed=40,
        demand_distribution_type="poisson",
        demand_lambda=105,
        transport_delay_t1_to_oem=2,
        transport_delay_t23_to_t1=5,
        t1_daily_capacity=95,
        t23_daily_capacity=100,
        initial_oem_inventory=140,
        initial_t1_inventory=180,
        selected_scenario_id=1,
        policy_params=PolicyParams(
            S_oem=160,
            S_t1=220,
            beta_f=1.6,
            alpha_inv=1.3,
            oem_inventory_target=160,
            oem_forecast_horizon=3,
        ),
    )
    result = run_simulation(cfg)
    ship_days = sum(1 for x in result.daily_metrics.t1_shipments_to_oem if x > 0)
    assert ship_days > 100
