#!/usr/bin/env python3
"""Validates RNF-2 in practice: ~50 req/s sustained against GET /consolidated/{date}, at most
5% loss (5xx/timeout/connection error). See docs/01-requirements.md#rnf-2 and ADR 0007.

Usage: python3 scripts/load_test.py [--rps 50] [--duration 10]
"""

import argparse
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

CONSOLIDATION_URL = os.environ.get("CONSOLIDATION_URL", "http://localhost:8002")
API_KEY = os.environ.get("API_KEY", "local-dev-key-change-me")
REQUEST_TIMEOUT_SECONDS = 3


def _do_request(url: str) -> str:
    req = urllib.request.Request(url, headers={"X-API-Key": API_KEY})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
            return "ok" if resp.status == 200 else f"http_{resp.status}"
    except urllib.error.HTTPError as exc:
        return f"http_{exc.code}"
    except Exception as exc:  # timeouts, connection refused, etc. — all count as loss
        return f"error_{type(exc).__name__}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rps", type=int, default=50)
    parser.add_argument("--duration", type=int, default=10)
    args = parser.parse_args()

    today = datetime.now(timezone.utc).date().isoformat()
    url = f"{CONSOLIDATION_URL}/consolidated/{today}"

    print(f"Sending ~{args.rps} req/s for {args.duration}s against {url}")

    results: list[str] = []
    interval = 1.0 / args.rps
    with ThreadPoolExecutor(max_workers=args.rps * 2) as pool:
        futures = []
        start = time.monotonic()
        next_send = start
        while time.monotonic() - start < args.duration:
            futures.append(pool.submit(_do_request, url))
            next_send += interval
            sleep_for = next_send - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)
        results = [f.result() for f in futures]

    total = len(results)
    ok = sum(1 for r in results if r == "ok")
    # 4xx means the request was rejected on its own merits (wrong API key, bad date) — a
    # misconfigured run, not capacity loss. Counting it as loss would report "RNF-2 FAILED"
    # for what is really a setup mistake.
    client_errors = sum(1 for r in results if r.startswith("http_4"))
    lost = total - ok - client_errors
    measured = total - client_errors
    loss_pct = (lost / measured * 100) if measured else 0.0

    print(f"\nTotal requests: {total}")
    print(f"Successful (200): {ok}")
    print(f"Lost (5xx/timeout/error): {lost}  ({loss_pct:.2f}%)")
    if client_errors:
        print(f"Client errors (4xx, excluded from the loss rate): {client_errors}")
        print("  -> check API_KEY and the target URL; this is a configuration problem, not overload.")

    breakdown: dict[str, int] = {}
    for r in results:
        if r != "ok":
            breakdown[r] = breakdown.get(r, 0) + 1
    for reason, count in sorted(breakdown.items()):
        print(f"  - {reason}: {count}")

    target = "<= 5%"
    verdict = "PASSED" if loss_pct <= 5.0 else "FAILED"
    print(f"\nRNF-2 target: {target} loss -> {verdict} ({loss_pct:.2f}%)")
    return 0 if loss_pct <= 5.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
