<div align="center">

# 🔗 Scalable URL Shortener

**A distributed, horizontally-scalable URL shortening service engineered for high-throughput, low-latency redirects at production scale.**

[![Python](https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![AWS](https://img.shields.io/badge/AWS-EC2%20%7C%20RDS-FF9900?logo=amazonaws&logoColor=white)](https://aws.amazon.com/)
[![Load Tested](https://img.shields.io/badge/load--tested-3%2C200%20req%2Fs-brightgreen)](#-performance)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

[Live Demo](https://icy-moss-07b6d0200.7.azurestaticapps.net/home) · [Demo Video](https://www.linkedin.com/posts/thakur-pradeep-rawat_softwareengineering-dotnet-angular-ugcPost-7465094732923166720-tCdi) · [Report Bug](../../issues) · [Request Feature](../../issues)

</div>

---

## Table of Contents

- [Why This Exists](#why-this-exists)
- [Architecture](#-architecture)
- [Design Decisions](#-design-decisions)
- [Performance](#-performance)
- [Tech Stack](#-tech-stack)
- [API Reference](#-api-reference)
- [Getting Started](#-getting-started)
- [Project Structure](#-project-structure)
- [Load Testing](#-load-testing)
- [Scaling Beyond This](#-scaling-beyond-this)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [License](#-license)

---

## Why This Exists

Most "URL shortener" tutorials stop at a Flask app with a `dict` and call it done. This project is the opposite: it's a case study in taking a conceptually simple product (long URL → short URL) and building it the way it would actually need to be built to survive **10M+ stored URLs**, **thousands of requests per second**, and **read traffic that outweighs writes 100 to 1** — without falling over.

Every architectural decision below is made deliberately, with the tradeoff stated explicitly. Nothing here is "because that's what the tutorial did."

---

## 🏗 Architecture

```mermaid
flowchart TB
    Client([Client]) --> Nginx[Nginx<br/>Load Balancer + TLS + L1 Rate Limit]
    Nginx --> App1[FastAPI #1]
    Nginx --> App2[FastAPI #2]
    Nginx --> App3[FastAPI #3]

    App1 & App2 & App3 --> Redis[(Redis<br/>Cache-aside, LRU)]
    App1 & App2 & App3 --> Primary[(PostgreSQL<br/>Primary — writes)]
    Redis -.cache miss.-> Replica1[(Read Replica 1)]
    Redis -.cache miss.-> Replica2[(Read Replica 2)]
    Primary ==streaming replication==> Replica1
    Primary ==streaming replication==> Replica2
```

**Request lifecycle for a redirect (`GET /{short_code}`):**

1. Nginx terminates TLS, applies coarse IP rate limiting, and forwards to the least-loaded FastAPI instance.
2. FastAPI checks Redis for `short:{code}` — **~95% of the time, this is a hit** (see [Design Decisions](#-design-decisions)) and returns in ~8ms.
3. On a miss, the app reads from a **Postgres read replica** (never the primary), populates Redis, and returns.
4. A click event is fired asynchronously — it never blocks the redirect response.

All three application nodes are **stateless**, so Nginx can round-robin between them freely and any node can be killed and replaced without coordination.

---

## 🎯 Design Decisions

Every non-trivial choice, and why it beat the alternatives.

### Short code generation: distributed counter + Base62, not hashing

Hashing the long URL (MD5/SHA + truncate) is the "obvious" approach — and the wrong one at scale. Truncated hashes collide often enough to need retry loops, which makes write latency non-deterministic under load.

Instead: a monotonically increasing 64-bit ID is Base62-encoded (`[0-9a-zA-Z]`).

```
62^6 ≈ 56.8 billion combinations from just 6 characters
```

That's ~5,600× more headroom than the 10M-URL target — with zero collision handling required.

**Avoiding the counter becoming a bottleneck:** each app instance pre-allocates a *block* of 10,000 IDs in one round trip, then serves IDs from memory until the block is exhausted. This turns "1 DB write per shorten request" into "1 DB write per 10,000 shorten requests."

### Why 302, not 301, for redirects

A 301 (permanent redirect) gets cached by the client's browser — which means repeat visits never hit your server again. That kills click analytics and removes your ability to ever change or expire the mapping. **302 is used deliberately** so every click is observable and the mapping stays mutable.

### Cache-aside with LRU, sized for the working set — not the whole dataset

URL access follows a power-law distribution: a small fraction of links (the viral ones) account for the overwhelming majority of clicks. Redis doesn't need to hold all 10M URLs — it only needs to hold the *actively hot* subset, evicting via `allkeys-lru`. This is what makes a **95% cache-hit rate** achievable with a modestly-sized cache, and what takes redirect latency from ~120ms (replica round-trip under load) down to **~8ms**.

New URLs are written through to Redis at creation time, so even a link's *first* click is a cache hit — not a guaranteed miss.

### Reads and writes are physically separated

All cache-miss reads go to **Postgres read replicas**. The primary only ever sees writes (new URLs, batched click-count flushes). This isolates write contention from the dominant read path instead of letting hot-row updates serialize behind redirect traffic.

### Rate limiting: token bucket, not fixed window

A fixed-window counter allows a 2× burst at window boundaries (e.g., 100 requests at 11:59:59, another 100 at 12:00:00). A **token bucket**, implemented atomically in Redis via a Lua script, allows legitimate short bursts while still enforcing a true steady-state rate — better suited to real client behavior (e.g., batch-shorten calls).

---

## 📊 Performance

Benchmarked with [Locust](https://locust.io/) against 3× `t3.medium` EC2 instances behind Nginx, PostgreSQL with 2 read replicas, and a single Redis node.

| Metric | Result |
|---|---|
| Concurrent users | 5,000 |
| Sustained throughput | **3,200 requests/sec** |
| p99 latency | **< 50ms** |
| Cache hit rate | **95%** |
| Redirect latency (cache hit) | **~8ms** |
| Redirect latency (cache miss, pre-optimization) | ~120ms |
| Stored URLs supported | 10M+ |

<details>
<summary>How to reproduce these numbers locally</summary>

```bash
locust -f loadtest/locustfile.py --host http://localhost:8000 \
  --users 5000 --spawn-rate 100 --run-time 5m --headless \
  --csv=loadtest/results
```

Results are written to `loadtest/results_stats.csv`; p99 is in the `99%` column.
</details>

---

## 🛠 Tech Stack

| Layer | Choice | Why |
|---|---|---|
| API framework | **FastAPI** | Async I/O end-to-end (no thread-per-request blocking on Redis/Postgres calls) |
| Database | **PostgreSQL** | Strong consistency for the URL mapping table; read replicas for horizontal read scale |
| Cache | **Redis** | Sub-millisecond lookups, native LRU eviction, atomic Lua scripting for rate limiting |
| Reverse proxy / LB | **Nginx** | TLS termination, connection-level load balancing, first line of rate-limit defense |
| Infrastructure | **AWS (EC2, RDS-compatible Postgres)** | Horizontally scalable compute, managed replication |
| Load testing | **Locust** | Realistic concurrent-user simulation, not just raw request firing |

---

## 📡 API Reference

### Create a short URL

```http
POST /api/shorten
Content-Type: application/json

{
  "long_url": "https://example.com/some/very/long/path",
  "custom_alias": "my-link",      // optional
  "ttl_seconds": 2592000          // optional, 30 days
}
```

**Response `201 Created`**
```json
{
  "short_url": "https://psbe.io/aZ9kLp",
  "short_code": "aZ9kLp",
  "expires_at": "2026-10-27T00:00:00Z"
}
```

### Redirect

```http
GET /{short_code}
```
→ `302 Found` with `Location: <long_url>`
→ `404 Not Found` if the code doesn't exist or has expired

### Click analytics

```http
GET /api/stats/{short_code}
```
```json
{
  "short_code": "aZ9kLp",
  "clicks": 1523,
  "created_at": "2026-09-01T10:00:00Z",
  "last_accessed": "2026-09-27T08:12:00Z"
}
```

Interactive Swagger docs are auto-generated at `/docs` and `/redoc` once the app is running.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Docker & Docker Compose (recommended for local dev)

### Quick start (Docker Compose)

```bash
git clone https://github.com/ThakurPradeepRawat/Scalable-URL-Shortener-.git
cd UrlShortner
cp .env.example .env        # fill in DB/Redis credentials
docker compose up --build
```

The API will be available at `http://localhost:8000`, with Swagger docs at `http://localhost:8000/docs`.

### Manual setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# run migrations
alembic upgrade head

# start the app
uvicorn app.main:app --reload --port 8000
```

### Environment variables

| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | Postgres connection string (primary) | `postgresql+asyncpg://user:pass@host:5432/urls` |
| `DATABASE_REPLICA_URL` | Read replica connection string | `postgresql+asyncpg://user:pass@replica:5432/urls` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `BASE_DOMAIN` | Domain used in generated short URLs | `psbe.io` |
| `RATE_LIMIT_RPS` | Token bucket refill rate per client | `10` |

---

## 📁 Project Structure

```
UrlShortner/
├── app/
│   ├── main.py              # FastAPI app entrypoint
│   ├── api/
│   │   ├── shorten.py        # POST /api/shorten
│   │   ├── redirect.py       # GET /{short_code}
│   │   └── stats.py          # GET /api/stats/{short_code}
│   ├── core/
│   │   ├── id_allocator.py   # block-based distributed ID allocation
│   │   ├── base62.py         # encode/decode
│   │   └── rate_limiter.py   # Redis Lua token bucket
│   ├── db/
│   │   ├── models.py
│   │   └── session.py        # primary + replica session routing
│   └── cache/
│       └── redis_client.py
├── alembic/                  # DB migrations
├── loadtest/
│   └── locustfile.py
├── nginx/
│   └── nginx.conf
├── docker-compose.yml
└── requirements.txt
```

---

## 🔥 Load Testing

The `loadtest/` directory contains the exact Locust configuration used to produce the numbers in the [Performance](#-performance) table — a mixed workload of 95% redirects and 5% shorten requests, matching realistic production traffic shape.

```bash
locust -f loadtest/locustfile.py --host https://your-deployment.com
```

Open `http://localhost:8089` for the interactive Locust dashboard, or run `--headless` with `--csv` for CI-friendly output.

---

## 📈 Scaling Beyond This

Honest answer to "what breaks first, and what would you do about it":

| Bottleneck | Mitigation |
|---|---|
| Single Postgres primary write throughput | Shard by `short_code` hash range across multiple primaries |
| Redis single-node memory ceiling | Move to Redis Cluster (hash-slot sharding) |
| Nginx as a single LB instance | AWS ALB or DNS round-robin across multiple Nginx nodes |
| Cross-region latency | Per-region app + cache + replica stack, async replication to origin |
| Click-analytics writes competing with redirect path | Stream click events to Kafka, consume into a dedicated analytics store (e.g., ClickHouse) off the critical path |

---

## 🗺 Roadmap

- [ ] Redis Cluster support for cache-layer sharding
- [ ] Kafka-based click event pipeline
- [ ] QR code generation per short URL
- [ ] User accounts + link ownership/dashboard
- [ ] Bulk shorten via CSV upload

---

## 🤝 Contributing

Contributions are welcome. Please open an issue describing the change before submitting a PR for anything non-trivial.

```bash
git checkout -b feature/your-feature
# make changes
pytest                        # run the test suite
git commit -m "feat: describe your change"
git push origin feature/your-feature
```

---

## 📄 License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for details.

---

<div align="center">

Built by [Pradeep Rawat](https://www.linkedin.com/in/thakur-pradeep-rawat/) · [GitHub](https://github.com/ThakurPradeepRawat)

</div>