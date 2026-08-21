import time
import random
from fastapi import FastAPI
import redis

app = FastAPI()

# Connect to the Redis container by its service name — Docker's internal
# DNS resolves "redis" to the right container automatically.
r = redis.Redis(host="redis", port=6379, decode_responses=True)

@app.post("/work")
def do_work():
    # INCR is atomic — even if two containers call this at the exact
    # same instant, Redis guarantees no increments get lost. This is
    # the property your in-memory `request_count += 1` never had.
    total_requests = r.incr("request_count")

    time.sleep(random.uniform(0.05, 0.15))
    total = sum(i * i for i in range(1000000))

    return {"status": "done", "result": total, "handled_by": "single-instance"}

@app.get("/stats")
def get_stats():
    count = r.get("request_count")
    return {"total_requests": int(count) if count else 0}

@app.get("/health")
def health():
    return {"status": "ok"}