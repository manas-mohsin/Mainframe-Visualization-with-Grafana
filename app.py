import os
import time
import random
from datetime import datetime, timezone

from prometheus_client import Gauge, Histogram, Counter, start_http_server


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def env_list(name: str, default_csv: str) -> list[str]:
    raw = os.getenv(name, default_csv)
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts or [p.strip() for p in default_csv.split(",") if p.strip()]


PORT = int(os.getenv("EXPORTER_PORT", "8000"))
LPARS = env_list("MAINFRAME_LPARS", "LPAR1")
SYSPLEX = os.getenv("SYSPLX", "PLEX1")
INTERVAL = float(os.getenv("UPDATE_INTERVAL_SECONDS", "5"))

random.seed(int(os.getenv("RANDOM_SEED", "42")))

# --- Metrics (Prometheus) ---
CPU = Gauge(
    "mainframe_cpu_utilization_percent",
    "Simulated z/OS CPU utilization percentage by LPAR",
    ["lpar", "sysplex"],
)

ZIIP = Gauge(
    "mainframe_ziip_utilization_percent",
    "Simulated zIIP utilization percentage by LPAR",
    ["lpar", "sysplex"],
)

MIPS = Gauge(
    "mainframe_mips_consumed",
    "Simulated MIPS consumed by LPAR",
    ["lpar", "sysplex"],
)

IOPS = Gauge(
    "mainframe_io_ops_per_sec",
    "Simulated I/O operations per second",
    ["lpar", "sysplex"],
)

MEM_TOTAL = Gauge(
    "mainframe_memory_total_bytes",
    "Simulated total memory (bytes) assigned to the LPAR",
    ["lpar", "sysplex"],
)

MEM_USED = Gauge(
    "mainframe_memory_used_bytes",
    "Simulated used memory (bytes) in the LPAR",
    ["lpar", "sysplex"],
)

JOBQ = Gauge(
    "mainframe_job_queue_depth",
    "Simulated JES job queue depth",
    ["lpar", "sysplex"],
)

CFQ = Gauge(
    "mainframe_cf_queue_depth",
    "Simulated coupling facility queue depth (sysplex health proxy)",
    ["lpar", "sysplex"],
)

UPTIME = Gauge(
    "mainframe_uptime_seconds",
    "Simulated uptime since exporter start (seconds)",
    ["lpar", "sysplex"],
)

AS_CPU = Gauge(
    "mainframe_address_space_cpu_percent",
    "Simulated CPU% by address space",
    ["lpar", "sysplex", "address_space"],
)

AS_RSS = Gauge(
    "mainframe_address_space_rss_bytes",
    "Simulated resident memory (RSS) by address space",
    ["lpar", "sysplex", "address_space"],
)

TXN_LAT = Histogram(
    "mainframe_transaction_response_seconds",
    "Simulated transaction response time (seconds)",
    ["lpar", "sysplex", "service"],
    buckets=(0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0),
)

TXN_TOTAL = Counter(
    "mainframe_transactions_total",
    "Simulated number of transactions processed",
    ["lpar", "sysplex", "service"],
)


ADDRESS_SPACES = [
    "DFHSIP",   # CICS region
    "DBM1",     # DB2
    "MSTR",     # DB2
    "TCPIP",
    "VTAM",
    "JES2",
    "SMF",
    "RMF",
    "IMSCTL",
    "MQM",
]

SERVICES = ["CICS", "DB2", "IMS", "MQ"]


def init_state():
    state = {}
    for lpar in LPARS:
        total_mem = random.choice([32, 48, 64, 96, 128]) * (1024 ** 3)
        used_mem = total_mem * random.uniform(0.45, 0.75)
        state[lpar] = {
            "cpu": random.uniform(10, 70),
            "ziip": random.uniform(5, 60),
            "mips_cap": random.choice([8000, 10000, 12000, 16000]),
            "iops": random.uniform(500, 3500),
            "mem_total": total_mem,
            "mem_used": used_mem,
            "jobq": random.uniform(0, 40),
            "cfq": random.uniform(1, 20),
        }
    return state


def simulate_loop():
    started = datetime.now(timezone.utc).timestamp()
    state = init_state()

    # Set static totals
    for lpar in LPARS:
        MEM_TOTAL.labels(lpar=lpar, sysplex=SYSPLEX).set(state[lpar]["mem_total"])

    while True:
        now = datetime.now(timezone.utc).timestamp()
        for lpar in LPARS:
            s = state[lpar]

            # Random walk with mild mean reversion
            s["cpu"] = clamp(s["cpu"] + random.uniform(-6, 6) + (35 - s["cpu"]) * 0.03, 0, 100)
            s["ziip"] = clamp(s["ziip"] + random.uniform(-6, 6) + (25 - s["ziip"]) * 0.03, 0, 100)
            s["iops"] = clamp(s["iops"] + random.uniform(-250, 250), 0, 8000)
            s["jobq"] = clamp(s["jobq"] + random.uniform(-3, 3), 0, 200)
            s["cfq"] = clamp(s["cfq"] + random.uniform(-2, 2) + (10 - s["cfq"]) * 0.02, 0, 80)

            # MIPS consumed roughly proportional to CPU%
            mips = s["mips_cap"] * (s["cpu"] / 100.0) * random.uniform(0.85, 1.15)

            # Memory drift
            drift = random.uniform(-0.7, 0.9) * (1024 ** 3)  # +- ~1GB
            s["mem_used"] = clamp(s["mem_used"] + drift, s["mem_total"] * 0.30, s["mem_total"] * 0.97)

            CPU.labels(lpar=lpar, sysplex=SYSPLEX).set(s["cpu"])
            ZIIP.labels(lpar=lpar, sysplex=SYSPLEX).set(s["ziip"])
            MIPS.labels(lpar=lpar, sysplex=SYSPLEX).set(mips)
            IOPS.labels(lpar=lpar, sysplex=SYSPLEX).set(s["iops"])
            MEM_USED.labels(lpar=lpar, sysplex=SYSPLEX).set(s["mem_used"])
            JOBQ.labels(lpar=lpar, sysplex=SYSPLEX).set(s["jobq"])
            CFQ.labels(lpar=lpar, sysplex=SYSPLEX).set(s["cfq"])
            UPTIME.labels(lpar=lpar, sysplex=SYSPLEX).set(now - started)

            # Address spaces: distribute CPU% around a skewed distribution
            # Keep total address-space CPU within ~total CPU (not exact; this is a demo).
            weights = [random.random() ** 1.8 for _ in ADDRESS_SPACES]  # more skew
            wsum = sum(weights) or 1.0
            for addr, w in zip(ADDRESS_SPACES, weights):
                as_cpu = s["cpu"] * (w / wsum) * random.uniform(0.7, 1.3)
                as_cpu = clamp(as_cpu, 0, 100)
                AS_CPU.labels(lpar=lpar, sysplex=SYSPLEX, address_space=addr).set(as_cpu)

                # RSS roughly proportional, but noisy
                rss = (s["mem_used"] / len(ADDRESS_SPACES)) * random.uniform(0.6, 1.6)
                AS_RSS.labels(lpar=lpar, sysplex=SYSPLEX, address_space=addr).set(rss)

            # Transaction latency & throughput
            for service in SERVICES:
                # transactions per interval, influenced by CPU and job queue
                base = 250 if service == "CICS" else 160
                tps = base * (0.5 + s["cpu"] / 200.0) * random.uniform(0.8, 1.3)
                count = int(max(10, tps * INTERVAL / 5.0))
                for _ in range(count):
                    # service-specific latency profile in seconds
                    if service == "CICS":
                        lat = random.lognormvariate(-3.2, 0.55)
                    elif service == "DB2":
                        lat = random.lognormvariate(-2.8, 0.60)
                    elif service == "IMS":
                        lat = random.lognormvariate(-3.0, 0.55)
                    else:  # MQ
                        lat = random.lognormvariate(-3.4, 0.50)

                    # Add pressure when job queue depth rises
                    lat *= (1.0 + (s["jobq"] / 400.0))

                    TXN_LAT.labels(lpar=lpar, sysplex=SYSPLEX, service=service).observe(lat)
                    TXN_TOTAL.labels(lpar=lpar, sysplex=SYSPLEX, service=service).inc()

        time.sleep(INTERVAL)


if __name__ == "__main__":
    start_http_server(PORT)
    print(f"Mainframe exporter listening on :{PORT} for LPARS={LPARS} sysplex={SYSPLEX}")
    simulate_loop()
