from __future__ import annotations

import random
from typing import Dict, List

from .metrics import compute_kpis
from .models import (
    DailyMetrics,
    OEMOrderRecord,
    ShipmentToOEM,
    ShipmentToT1,
    SimulationConfig,
    SimulationResult,
    SimulationState,
    T1BacklogOrder,
    T23BacklogOrder,
)
from .policies import oem_order_qty, t1_order_qty


def _validate_config(config: SimulationConfig) -> None:
    if config.simulation_horizon < 1:
        raise ValueError("simulation_horizon must be >= 1")
    if config.replications_per_scenario < 1:
        raise ValueError("replications_per_scenario must be >= 1")
    for v in [
        config.t1_daily_capacity,
        config.t23_daily_capacity,
        config.initial_oem_inventory,
        config.initial_t1_inventory,
        config.transport_delay_t1_to_oem,
        config.transport_delay_t23_to_t1,
    ]:
        if v < 0:
            raise ValueError("Capacities, inventories, and delays must be non-negative")

    if config.demand_distribution_type == "poisson" and config.demand_lambda <= 0:
        raise ValueError("Poisson lambda must be > 0")
    if config.demand_distribution_type == "normal" and config.demand_std_dev < 0:
        raise ValueError("Normal std_dev must be >= 0")
    if config.demand_distribution_type == "deterministic" and config.demand_deterministic_value < 0:
        raise ValueError("Deterministic demand value must be >= 0")


def _sample_poisson(rng: random.Random, lam: float) -> int:
    # Knuth algorithm
    from math import exp

    l = exp(-lam)
    k = 0
    p = 1.0
    while p > l:
        k += 1
        p *= rng.random()
    return k - 1


def _sample_demand(rng: random.Random, config: SimulationConfig) -> int:
    if config.demand_distribution_type == "poisson":
        return _sample_poisson(rng, config.demand_lambda)
    if config.demand_distribution_type == "normal":
        sampled = rng.gauss(config.demand_mean, config.demand_std_dev)
        rounded = int(round(sampled))
        return max(0, rounded)
    return int(config.demand_deterministic_value)


def run_simulation(config: SimulationConfig, seed_offset: int = 0) -> SimulationResult:
    _validate_config(config)
    rng = random.Random(config.random_seed + seed_offset)

    state = SimulationState(
        current_day=0,
        oem_on_hand=config.initial_oem_inventory,
        t1_on_hand=config.initial_t1_inventory,
    )
    metrics = DailyMetrics()

    for day in range(config.simulation_horizon):
        state.current_day = day
        arriving_t1 = [s for s in state.t1_inbound_shipments if s.arrival_day == day]
        state.t1_on_hand += sum(s.qty for s in arriving_t1)
        state.t1_inbound_shipments = [s for s in state.t1_inbound_shipments if s.arrival_day != day]

        arriving_oem = [s for s in state.t1_outbound_shipments if s.arrival_day == day]
        for shipment in arriving_oem:
            state.oem_on_hand += shipment.qty
            order = state.oem_orders.get(shipment.order_id)
            if order is not None and order.day_received is None:
                order.day_received = day
        state.t1_outbound_shipments = [s for s in state.t1_outbound_shipments if s.arrival_day != day]

        daily_demand = _sample_demand(rng, config)
        state.oem_on_hand = max(0, state.oem_on_hand - daily_demand)

        open_pipeline_qty = sum(v.qty for v in state.oem_orders.values() if v.day_received is None)
        ip_oem = state.oem_on_hand + open_pipeline_qty
        oem_qty = oem_order_qty(ip_oem, config.policy_params)

        if oem_qty > 0:
            order_id = state.next_order_id
            state.next_order_id += 1
            state.oem_orders[order_id] = OEMOrderRecord(order_id=order_id, qty=oem_qty, day_placed=day)
            state.t1_backlog_queue.append(T1BacklogOrder(order_id=order_id, qty=oem_qty, day_received_from_oem=day))

        available_shipping_capacity = config.t1_daily_capacity
        shipped_today = 0
        new_backlog: List[T1BacklogOrder] = []

        shipping_blocked = False
        for order in state.t1_backlog_queue:
            if shipping_blocked:
                new_backlog.append(order)
                continue

            if state.t1_on_hand >= order.qty and available_shipping_capacity >= order.qty:
                state.t1_on_hand -= order.qty
                available_shipping_capacity -= order.qty
                shipped_today += order.qty
                order.day_shipped = day

                if order.order_id in state.oem_orders:
                    state.oem_orders[order.order_id].day_shipped = day

                state.t1_outbound_shipments.append(
                    ShipmentToOEM(
                        order_id=order.order_id,
                        qty=order.qty,
                        dispatch_day=day,
                        arrival_day=day + config.transport_delay_t1_to_oem,
                    )
                )
            else:
                shipping_blocked = True
                new_backlog.append(order)

        state.t1_backlog_queue = new_backlog

        inbound_pipeline_qty = sum(s.qty for s in state.t1_inbound_shipments if s.arrival_day > day)
        backlog_qty = sum(o.qty for o in state.t1_backlog_queue)
        ip_t1 = state.t1_on_hand + inbound_pipeline_qty - backlog_qty
        t1_qty = t1_order_qty(
            config=config,
            params=config.policy_params,
            ip_t1=ip_t1,
            oem_on_hand=state.oem_on_hand,
            current_day=day,
        )

        if t1_qty > 0:
            state.t23_order_backlog_queue.append(T23BacklogOrder(qty=t1_qty, day_received_from_t1=day))

        available_capacity = config.t23_daily_capacity
        produced_today = 0
        for entry in state.t23_order_backlog_queue:
            if available_capacity <= 0:
                break
            done = min(entry.qty, available_capacity)
            entry.qty -= done
            available_capacity -= done
            produced_today += done

        state.t23_order_backlog_queue = [e for e in state.t23_order_backlog_queue if e.qty > 0]

        if produced_today > 0:
            state.t1_inbound_shipments.append(
                ShipmentToT1(
                    qty=produced_today,
                    dispatch_day=day,
                    arrival_day=day + config.transport_delay_t23_to_t1,
                )
            )

        metrics.daily_oem_demand.append(daily_demand)
        metrics.oem_to_t1_orders.append(oem_qty)
        metrics.t1_to_t23_orders.append(t1_qty)
        metrics.t1_backlog_units.append(sum(o.qty for o in state.t1_backlog_queue))
        metrics.t1_on_hand.append(state.t1_on_hand)
        metrics.t1_shipments_to_oem.append(shipped_today)
        metrics.t23_backlog_units.append(sum(e.qty for e in state.t23_order_backlog_queue))
        metrics.t23_production.append(produced_today)
        metrics.oem_on_hand.append(state.oem_on_hand)

    completed_orders = [o for o in state.oem_orders.values() if o.day_received is not None]
    lead_times = [o.day_received - o.day_placed for o in completed_orders if o.day_received is not None]

    kpis = compute_kpis(
        lead_times=lead_times,
        t1_backlog_units=metrics.t1_backlog_units,
        t1_orders=metrics.t1_to_t23_orders,
        demand_series=metrics.daily_oem_demand,
    )
    return SimulationResult(config=config, kpis=kpis, daily_metrics=metrics, completed_orders=completed_orders)


def run_replications(config: SimulationConfig) -> Dict:
    results = [run_simulation(config, seed_offset=i) for i in range(config.replications_per_scenario)]

    def _avg(values):
        vals = [v for v in values if v is not None]
        return sum(vals) / len(vals) if vals else None

    summary = {
        "replications": config.replications_per_scenario,
        "mean_lead_time": _avg([r.kpis.mean_lead_time for r in results]),
        "p95_lead_time": _avg([r.kpis.p95_lead_time for r in results]),
        "std_lead_time": _avg([r.kpis.std_lead_time for r in results]),
        "mean_t1_backlog_units": _avg([r.kpis.mean_t1_backlog_units for r in results]),
        "max_t1_backlog_units": _avg([r.kpis.max_t1_backlog_units for r in results]),
        "bullwhip_ratio": _avg([r.kpis.bullwhip_ratio for r in results]),
    }

    return {"summary": summary, "replication_results": results}
