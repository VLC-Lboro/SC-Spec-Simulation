import streamlit as st

from simulation.engine import run_replications
from simulation.models import PolicyParams, SimulationConfig


st.set_page_config(page_title="3-Stage SC DES Simulator", layout="wide")
st.title("3-Stage Supply Chain Discrete Event Simulation")
st.caption("T23 Aggregate → T1 Manufacturer → OEM")

with st.sidebar:
    st.header("Simulation Inputs")
    scenario_id = st.selectbox("Scenario", [1, 2, 3, 4, 5], index=0)
    horizon = st.number_input("Simulation horizon (days)", 1, 5000, 180)
    reps = st.number_input("Replications", 1, 200, 5)
    seed = st.number_input("Random seed", 0, 10_000_000, 42)

    st.subheader("Demand")
    demand_type = st.selectbox("Demand distribution", ["poisson", "normal", "deterministic"])
    demand_lambda = st.number_input("Poisson lambda", min_value=0.1, value=20.0)
    demand_mean = st.number_input("Normal mean", value=20.0)
    demand_std = st.number_input("Normal std_dev", min_value=0.0, value=3.0)
    demand_det = st.number_input("Deterministic demand", min_value=0, value=20)

    st.subheader("Physical system")
    d1 = st.number_input("Transport delay T1→OEM (days)", min_value=0, value=2)
    d2 = st.number_input("Transport delay T23→T1 (days)", min_value=0, value=2)
    t1_cap = st.number_input("T1 daily capacity", min_value=0, value=40)
    t23_cap = st.number_input("T23 daily capacity", min_value=0, value=50)
    init_oem = st.number_input("Initial OEM inventory", min_value=0, value=60)
    init_t1 = st.number_input("Initial T1 inventory", min_value=0, value=80)

    st.subheader("Policy parameters")
    s_oem = st.number_input("S_oem", min_value=0.0, value=70.0)
    s_t1 = st.number_input("S_t1", min_value=0.0, value=90.0)
    beta_f = st.number_input("beta_f", min_value=0.0, value=0.2)
    alpha_inv = st.number_input("alpha_inv", min_value=0.0, value=0.2)
    oem_target = st.number_input("OEM inventory target", min_value=0.0, value=70.0)
    forecast_h = st.number_input("Forecast horizon H", min_value=1, value=7)

run = st.button("Run Simulation", type="primary")

if run:
    cfg = SimulationConfig(
        simulation_horizon=int(horizon),
        random_seed=int(seed),
        demand_distribution_type=demand_type,
        demand_lambda=float(demand_lambda),
        demand_mean=float(demand_mean),
        demand_std_dev=float(demand_std),
        demand_deterministic_value=int(demand_det),
        transport_delay_t1_to_oem=int(d1),
        transport_delay_t23_to_t1=int(d2),
        t1_daily_capacity=int(t1_cap),
        t23_daily_capacity=int(t23_cap),
        initial_oem_inventory=int(init_oem),
        initial_t1_inventory=int(init_t1),
        selected_scenario_id=int(scenario_id),
        replications_per_scenario=int(reps),
        policy_params=PolicyParams(
            S_oem=float(s_oem),
            S_t1=float(s_t1),
            beta_f=float(beta_f),
            alpha_inv=float(alpha_inv),
            oem_inventory_target=float(oem_target),
            oem_forecast_horizon=int(forecast_h),
        ),
    )

    output = run_replications(cfg)
    summary = output["summary"]
    first = output["replication_results"][0]

    st.subheader("KPI Summary (average across replications)")
    st.json(summary)

    st.subheader("Daily Time-Series (Replication 1)")
    ts = {
        "oem_demand": first.daily_metrics.daily_oem_demand,
        "oem_to_t1_orders": first.daily_metrics.oem_to_t1_orders,
        "t1_to_t23_orders": first.daily_metrics.t1_to_t23_orders,
        "t1_backlog": first.daily_metrics.t1_backlog_units,
        "t1_on_hand": first.daily_metrics.t1_on_hand,
        "t23_backlog": first.daily_metrics.t23_backlog_units,
        "t23_production": first.daily_metrics.t23_production,
        "oem_on_hand": first.daily_metrics.oem_on_hand,
    }
    st.line_chart({k: ts[k] for k in ["oem_demand", "oem_to_t1_orders", "t1_to_t23_orders"]})
    st.line_chart({k: ts[k] for k in ["t1_backlog", "t23_backlog"]})
    st.line_chart({k: ts[k] for k in ["oem_on_hand", "t1_on_hand"]})

    st.subheader("Completed OEM Orders (Replication 1)")
    orders_rows = [
        {
            "order_id": o.order_id,
            "qty": o.qty,
            "day_placed": o.day_placed,
            "day_shipped": o.day_shipped,
            "day_received": o.day_received,
            "lead_time": (o.day_received - o.day_placed) if o.day_received is not None else None,
        }
        for o in first.completed_orders
    ]
    st.dataframe(orders_rows, use_container_width=True)

st.markdown("---")
st.subheader("Assumptions implemented")
st.markdown(
    """
- Forecast in Scenarios 2/5 uses expected demand and covers **next H days excluding today**.
- OEM policy remains baseline order-up-to for all scenarios.
- T1 inventory visibility adjustment uses `oem_on_hand` (not `IP_oem`) in line with scenario text.
- Bullwhip ratio is `undefined (None)` when demand variance is zero.
- Each replication uses `random_seed + i`.
"""
)

st.subheader("Potential gaps / contradictions identified")
st.markdown(
    """
- Scenario text alternates between forecast window notations `t:t+H` and `k>0`; implementation chooses `k=1..H`.
- Poisson constraints mention `lambda > 0` in one section and `lambda >= 0` in another; implementation enforces `> 0`.
- 95th percentile definition references “standard inclusion method”; implementation uses inclusive linear interpolation.
"""
)
