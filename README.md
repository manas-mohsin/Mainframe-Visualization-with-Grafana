# Grafana Mainframe Visualization (Demo Project)

This repository is a **GitHub-ready Grafana project** that visualizes **mainframe-style operational metrics** (CPU, zIIP, MIPS, memory, I/O, queues, transaction latency, address-space hot spots).

It ships with:

- **Grafana** (dashboard auto-provisioned)
- **Prometheus** (scrapes metrics)
- A small **"mainframe exporter"** (Python) that **simulates** z/OS-like metrics in Prometheus format

> ✅ You can use this as a starting point and replace the simulator with real mainframe telemetry (SMF/RMF, OMEGAMON, z/OSMF, etc.) later.

---

## Quick start

### 1) Run the stack

```bash
docker compose up --build
```

### 2) Open Grafana

- URL: http://localhost:3000
- User: `admin`
- Password: `admin`

The dashboard will appear under:

**Dashboards → Mainframe → Mainframe Overview**

### 3) Verify metrics

- Exporter metrics: http://localhost:8000/metrics
- Prometheus UI: http://localhost:9090

---

## What you get

### Dashboard: "Mainframe Overview"

Panels include:

- Uptime, CPU%, zIIP%, Memory Used%
- CPU and zIIP time series
- MIPS consumed
- I/O ops/sec
- JES job queue depth + coupling facility queue depth
- Transaction response p95 per service (CICS / DB2 / IMS / MQ)
- Transaction throughput
- Top address spaces by CPU% and RSS

---

## Project structure

```
.
├─ docker-compose.yml
├─ exporter/
│  ├─ app.py
│  ├─ Dockerfile
│  └─ requirements.txt
├─ prometheus/
│  └─ prometheus.yml
└─ grafana/
   ├─ provisioning/
   │  ├─ datasources/
   │  │  └─ datasource.yml
   │  └─ dashboards/
   │     └─ dashboards.yml
   └─ dashboards/
      └─ mainframe-overview.json
```

---

## Configuration

You can tune the simulator using environment variables in `docker-compose.yml`:

- `MAINFRAME_LPARS=LPAR1,LPAR2` — which LPARs to simulate
- `SYSPLX=PLEX1` — sysplex label
- `UPDATE_INTERVAL_SECONDS=5` — exporter update interval
- `EXPORTER_PORT=8000` — exporter port

---

## Replacing the simulator with real mainframe data

The dashboard expects Prometheus metrics like:

- `mainframe_cpu_utilization_percent{lpar="LPAR1",sysplex="PLEX1"}`
- `mainframe_transaction_response_seconds_bucket{service="CICS",...}`

To switch to real data, you can:

1. Keep the **same metric names/labels** and implement a real exporter (Go, Python, Java)
2. Or update the dashboard queries to match your existing metric naming

---

## Development tips

### Start/stop

```bash
docker compose up --build
docker compose down
```

### Watch exporter logs

```bash
docker compose logs -f mainframe-exporter
```

---

## License

MIT — see [LICENSE](LICENSE).
