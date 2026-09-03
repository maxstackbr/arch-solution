#!/usr/bin/env python3
"""End-to-end smoke test against a running `docker-compose up` environment.

Posts one entry to the Ledger Service and polls the Consolidation Service until the
consolidated balance reflects it (or a timeout is hit) — proving the full asynchronous
flow described in docs/02-target-architecture.md#3-fluxo-de-escrita--post-entries works for
real, including the consistency-eventual window (RNF-3).

Usage: python3 scripts/smoke_test.py
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

LEDGER_URL = os.environ.get("LEDGER_URL", "http://localhost:8001")
CONSOLIDATION_URL = os.environ.get("CONSOLIDATION_URL", "http://localhost:8002")
API_KEY = os.environ.get("API_KEY", "local-dev-key-change-me")
POLL_TIMEOUT_SECONDS = 15
POLL_INTERVAL_SECONDS = 1


def _request(method: str, url: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method, headers={"X-API-Key": API_KEY, "Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def main() -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    amount = "42.50"

    # Read the baseline BEFORE posting: consolidation is asynchronous but can complete in
    # milliseconds, so a baseline taken after the POST may already include the new entry —
    # the script would then wait for the amount to be counted a second time and time out.
    print(f"1) Reading baseline GET /consolidated/{today} ({CONSOLIDATION_URL})...")
    before_status, before = _request("GET", f"{CONSOLIDATION_URL}/consolidated/{today}")
    baseline_credits = float(before["total_credits"]) if before_status == 200 else 0.0
    print(f"   OK: baseline total_credits = {baseline_credits}")

    print(f"2) POST /entries on Ledger Service ({LEDGER_URL})...")
    status, entry = _request(
        "POST",
        f"{LEDGER_URL}/entries",
        {"amount": amount, "type": "CREDIT", "description": "smoke_test"},
    )
    if status != 201:
        print(f"   FAILED: expected 201, got {status}: {entry}")
        return 1
    print(f"   OK: entry {entry['id']} created")

    print(f"3) Polling GET /consolidated/{today} until it reflects the entry...")
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        status, balance = _request("GET", f"{CONSOLIDATION_URL}/consolidated/{today}")
        if status == 200 and float(balance["total_credits"]) >= baseline_credits + float(amount):
            elapsed = POLL_TIMEOUT_SECONDS - (deadline - time.monotonic())
            # Most of this figure is the today-balance cache TTL (CACHE_TTL_TODAY_SECONDS,
            # 5s by default — ADR 0007), not consolidation lag: the baseline read above
            # populated the cache. The real end-to-end lag is visible in the worker logs.
            print(f"   OK: consolidated balance reflects the new entry after ~{elapsed:.1f}s")
            print(f"   {json.dumps(balance, indent=2)}")
            print("\nSMOKE TEST PASSED")
            return 0
        time.sleep(POLL_INTERVAL_SECONDS)

    print("   FAILED: consolidated balance did not reflect the new entry within timeout")
    return 1


if __name__ == "__main__":
    sys.exit(main())
