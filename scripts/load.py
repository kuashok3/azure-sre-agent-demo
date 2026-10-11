"""Generate traffic (the "sudden request spike" scenario) and summarise what users experienced.

Usage:
    python scripts/load.py                                   # 20 workers for 30 s
    python scripts/load.py --concurrency 50 --duration 120   # bigger spike
    python scripts/load.py --base-url https://<app>.azurecontainerapps.io

Traffic mix per worker loop: list orders (60%), create order (30%), create + checkout (10%).
The summary prints success ratio and p50/p95/p99 latency: the same SLIs we track in Azure.
Only point this at environments you own.
"""

import argparse
import random
import sys
import threading
import time
from collections import Counter

from _common import base_url, request


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(pct / 100 * (len(ordered) - 1))))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate demo traffic")
    parser.add_argument("--base-url")
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--duration", type=int, default=30, help="seconds")
    args = parser.parse_args()
    url = base_url(args.base_url)

    statuses: Counter = Counter()
    latencies: list[float] = []
    lock = threading.Lock()
    stop_at = time.monotonic() + args.duration

    def record(status: int, elapsed_ms: float) -> None:
        with lock:
            statuses[status] += 1
            latencies.append(elapsed_ms)

    def worker(worker_id: int) -> None:
        rng = random.Random(worker_id)
        while time.monotonic() < stop_at:
            roll = rng.random()
            try:
                if roll < 0.6:
                    status, _, _, ms = request("GET", f"{url}/api/v1/orders?limit=10", timeout=15)
                    record(status, ms)
                else:
                    order = {
                        "customer_id": f"load-{worker_id}",
                        "items": [
                            {
                                "sku": "LOAD-1",
                                "quantity": rng.randint(1, 5),
                                "unit_price_cents": 999,
                            }
                        ],
                    }
                    status, body, _, ms = request("POST", f"{url}/api/v1/orders", order, timeout=15)
                    record(status, ms)
                    if roll >= 0.9 and status == 201:
                        status, _, _, ms = request(
                            "POST", f"{url}/api/v1/orders/{body['id']}/checkout", timeout=15
                        )
                        record(status, ms)
            except OSError:  # connection refused / timeout at socket level
                record(0, 15000.0)

    print(f"Sending traffic to {url}: {args.concurrency} workers for {args.duration}s ...")
    threads = [
        threading.Thread(target=worker, args=(i,), daemon=True) for i in range(args.concurrency)
    ]
    started = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.monotonic() - started

    total = sum(statuses.values())
    # 4xx are client errors, not service failures, so they count as "good" for the SLI.
    good = sum(n for s, n in statuses.items() if 200 <= s < 500)
    print(f"\nRequests: {total}  ({total / elapsed:.1f} req/s)")
    print("Status codes:", dict(sorted(statuses.items())), "(0 = no response)")
    print(f"Success ratio (non-5xx): {good / total:.2%}" if total else "No requests completed")
    print(
        f"Latency ms: p50={percentile(latencies, 50):.0f}  p95={percentile(latencies, 95):.0f}  "
        f"p99={percentile(latencies, 99):.0f}  max={max(latencies, default=0):.0f}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
