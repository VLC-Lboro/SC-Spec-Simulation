# 3-Stage Supply Chain DES Simulator

Discrete-event/day-stepped simulation for a 3-stage automotive supply chain:
T23 aggregate -> T1 manufacturer -> OEM.

## Features
- Scenarios 1-5 for supply chain visibility policies.
- Daily event-order simulation as specified.
- KPI outputs: lead time mean/std/p95, T1 backlog mean/max, bullwhip ratio.
- Streamlit GUI to set inputs and run replications.
- Guard against strict-FIFO deadlock by splitting oversized OEM daily replenishment orders
  into multiple same-day full orders capped by T1 daily shipping capacity.

## Run
```bash
cd "c:\Users\wsvl\OneDrive - Loughborough University\IP-Spec-Sim-Folder\SC-Spec-Simulation-main"
streamlit run app.py
```

## Test
```bash
pytest -q
```
