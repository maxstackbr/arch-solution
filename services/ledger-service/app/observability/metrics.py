from prometheus_client import Counter, Histogram

http_requests_total = Counter(
    "http_requests_total", "Total HTTP requests", ["route", "method", "status"]
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds", "HTTP request duration in seconds", ["route"]
)

# Proves RNF-1: publish failures never affect the HTTP response (see ADR 0005).
event_publish_failures_total = Counter(
    "event_publish_failures_total", "Failed attempts to publish EntryCreated events"
)
