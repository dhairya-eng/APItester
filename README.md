# APItester

# Vibetester

A hands-on system design lab: start with a single naive API server, load-test it until it breaks, then progressively fix each real bottleneck — thread pools, vertical scaling limits, horizontal scaling, distributed state, and load balancer failover — using the same tools production systems actually use.

This isn't a tutorial repo. Every stage below was driven by an actual load test result, including the confusing and wrong ones — a CPU-starved test run, a shared-state bug caught live via inconsistent `/stats` responses, and a load balancer silently retrying failed requests. The point was to *feel* each failure mode before fixing it, not read about it.

## Stack

- **FastAPI** — the API under test
- **Locust** — load generation and traffic simulation
- **Docker + docker-compose** — running multiple isolated API instances
- **Nginx** — load balancing, rate limiting, passive health checks, failover
- **Redis** — shared, atomic state across horizontally-scaled instances

## The journey

### 1. Naive single-server API
A minimal FastAPI app with a `/work` endpoint (simulated CPU + I/O cost) and a `/stats` endpoint tracking an in-memory request counter. Deliberately fragile — the counter only works because there's exactly one process.

### 2. Load test it and find the real bottleneck
Using Locust, ramped from 10 to 1000+ concurrent users. The server didn't fail with connection errors — it degraded silently. Response times climbed from ~600ms to 29+ seconds while showing **0% failures**, because FastAPI's default thread pool (~40 threads) queues excess requests with no bound instead of rejecting them. No errors doesn't mean healthy.

### 3. Vertical scaling — and its ceiling
Ran the same app with `uvicorn --workers 4` (4 separate OS processes on one machine). Throughput roughly tripled and the latency ceiling dropped from ~17s to ~6s — but the same unbounded-queue shape persisted, just later. More processes on one box only buys so much; it's bounded by that box's CPU core count.

### 4. Horizontal scaling — Docker + Nginx
Split the app across 3 independent containers behind an Nginx load balancer doing round-robin distribution. Along the way, hit a real methodology bug: running the load generator on the same machine as the system under test caused CPU starvation and false failures (`HTTP 499`s from Locust's own client-side timeouts, not the app). Lesson: never load-test from the same box you're testing.

### 5. The shared-state bug
With 3 containers running, `curl /stats` repeatedly returned wildly inconsistent numbers depending on which container happened to answer — because each instance's counter was private, in-memory, and unaware of the others. Classic distributed systems trap: nothing you keep in local process memory is trustworthy once you have more than one instance.

### 6. Fixing it with Redis
Replaced the in-memory counter with Redis's atomic `INCR` command, giving every container a single, consistent, race-condition-free source of truth. Verified by hammering `/work` and confirming `/stats` only ever climbed monotonically, regardless of which container served the request.

### 7. Resilience — rate limiting and failover
Added Nginx-level rate limiting (per-IP request caps) and passive health checks (`max_fails` / `fail_timeout`). Killed a live container mid-traffic (`docker stop api2`) and watched Nginx automatically retry failed requests on the surviving containers — **zero client-visible errors**, at the cost of a small latency hit on the unlucky in-flight requests. Failover isn't free; it trades correctness for latency, not the other way around.

## What's intentionally not here

Observability (Prometheus/Grafana dashboards) was scoped out — every failure mode above was diagnosed directly from Locust output and container logs, which was the point: understand the failure before you automate watching for it.

## Running it

```bash
docker compose up --build
```

Load test:
```bash
locust -f locustfile.py --host=http://localhost:8000 --headless -u 500 -r 50 -t 60s
```

Watch it fail over:
```bash
# terminal 1
for i in {1..200}; do curl -s -X POST http://localhost:8000/work -o /dev/null -w "%{http_code}\n"; sleep 0.1; done

# terminal 2, mid-run
docker stop api2
```
