# Tawana CRM | Enterprise Capacity-Driven CRM Platform

**Tawana CRM** is an enterprise-grade Customer Relationship Management system architected specifically around **multi-dimensional capacity requirements**. It bridges the gap between sales revenue operations, rep bandwidth protection, customer contract quota monitoring, and high-throughput cloud infrastructure sizing.

---

## 🚀 Key Modules & Capabilities

### 1. Sales Workload & Rep Capacity Planner
- **Effort-Weighted Deals**: Deals carry complexity effort points (1 to 5 pts) rather than naive headcounts.
- **Dynamic Bandwidth Meters**: Tracks rep capacity ceilings (e.g. 25–35 pts), active effort points, and headroom.
- **Autonomous Lead Assignment Engine**: Automatically routes inbound deals to reps with available capacity headroom, matching department fit while preventing pipeline burnout.
- **One-Click Autonomous Workload Rebalancer**: Detects reps operating in critical saturation (>85% capacity) and safely migrates early-stage unworked deals (`Lead` / `Qualified`) to underutilized reps with available bandwidth.

### 2. Multi-Stage Pipeline & Kanban Board
- Interactive 5-stage pipeline: **Lead &rarr; Qualified &rarr; Proposal &rarr; Negotiation &rarr; Closed Won**.
- Live probability-weighted revenue forecasting ($).
- Instant one-click stage progression and real-time deal card status tracking.

### 3. Customer Tier & Resource Quota Monitoring
- Real-time tracking of:
  - **Seat allocation & concurrent users**
  - **Monthly API calls & webhook bandwidth**
  - **Storage allocation (GB)**
- **Early-Warning Upsell Engine**: Triggers automated warnings when an account crosses 85% capacity utilization, pinpointing expansion revenue before quota exhaustion.

### 4. Technical Infrastructure Capacity Sizer
- Production-grade sizing model calculating:
  - **Peak & Average QPS** from concurrent reps, inbound lead velocity, and webhook integrations.
  - **Read & Write IOPS** requirements.
  - **Multi-Year Database Growth (GB)** with index and WAL overhead.
  - **In-Memory Caching (Redis Cluster)** hot working set sizing.
  - **Message Queue Partitioning** (Kafka / RabbitMQ) for peak events per second.
  - **Sharding Strategy Recommendation** (Horizontal Distributed SQL vs Read Replicas vs Single Aurora Multi-AZ).
  - **Estimated Monthly Cloud Infrastructure Cost ($ USD)**.

### 5. Live Token Bucket Stress & Concurrency Lab
- Real-time synthetic load generator hitting an asynchronous Token Bucket rate limiter and worker pool.
- Live measurement of **p50, p95, p99 latencies**, throughput (EPS), throttled events (HTTP 429), and queue backpressure telemetry.

---

## 🛠️ Tech Stack
- **Backend**: Python 3.14 + FastAPI + Pydantic v2 + SQLite (WAL Mode enabled for concurrent reads/writes) + Asyncio.
- **Frontend**: Responsive Single-Page Application (HTML5, Tailwind CSS, Chart.js, Glassmorphism design system).
- **Testing**: Pytest test suite (`tests/test_crm_capacity.py`).

---

## 🏃 Running the Application

### Option 1: Double-click launch script
Run `start_server.bat` or `start_server.ps1` in Windows.

### Option 2: Command Line
```powershell
cd C:\Users\kgapa\.gemini\antigravity\scratch\advanced-crm-capacity\backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Once started, open your web browser to:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 🧪 Running the Test Suite
```powershell
cd C:\Users\kgapa\.gemini\antigravity\scratch\advanced-crm-capacity
python -m pytest tests/
```

