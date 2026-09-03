from prometheus_client import Counter, Histogram

http_requests_total = Counter(
    "http_requests_total", "Total HTTP requests", ["route", "method", "status"]
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds", "HTTP request duration in seconds", ["route"]
)

# Proves RNF-2: fraction of requests rejected by load shedding must stay <= 5% under peak load
# (see ADR 0007 and docs/01-requirements.md).
consolidation_requests_rejected_total = Counter(
    "consolidation_requests_rejected_total", "Requests rejected by the concurrency limiter (503)"
)

event_processed_total = Counter(
    "event_processed_total", "EntryCreated events applied to the read model"
)
event_duplicate_total = Counter(
    "event_duplicate_total", "EntryCreated events skipped because they were already processed (ADR 0006)"
)

cache_hit_total = Counter("cache_hit_total", "Consolidated balance cache hits")
cache_miss_total = Counter("cache_miss_total", "Consolidated balance cache misses")
