from math import sqrt
from typing import Iterable, Optional

from .models import KPIResults


def _mean(values):
    return sum(values) / len(values) if values else 0.0


def population_variance(values: Iterable[float]) -> float:
    arr = list(values)
    if not arr:
        return 0.0
    mu = _mean(arr)
    return sum((x - mu) ** 2 for x in arr) / len(arr)


def percentile_inclusive(values, p: float) -> Optional[float]:
    arr = sorted(values)
    if not arr:
        return None
    if len(arr) == 1:
        return float(arr[0])
    idx = (len(arr) - 1) * (p / 100.0)
    lo = int(idx)
    hi = min(lo + 1, len(arr) - 1)
    frac = idx - lo
    return float(arr[lo] * (1 - frac) + arr[hi] * frac)


def compute_kpis(lead_times, t1_backlog_units, t1_orders, demand_series) -> KPIResults:
    lt = list(lead_times)
    backlog = list(t1_backlog_units)

    mean_lt: Optional[float] = _mean(lt) if lt else None
    p95_lt: Optional[float] = percentile_inclusive(lt, 95)
    std_lt: Optional[float] = sqrt(population_variance(lt)) if lt else None

    demand_var = population_variance(demand_series)
    t1_var = population_variance(t1_orders)
    bullwhip = None if demand_var == 0 else float(t1_var / demand_var)

    return KPIResults(
        mean_lead_time=mean_lt,
        p95_lead_time=p95_lt,
        std_lead_time=std_lt,
        mean_t1_backlog_units=_mean(backlog) if backlog else 0.0,
        max_t1_backlog_units=max(backlog) if backlog else 0,
        bullwhip_ratio=bullwhip,
    )
