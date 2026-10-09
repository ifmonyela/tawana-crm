import math
import time
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

class TokenBucketRateLimiter:
    """Thread-safe and async-safe Token Bucket for CRM API ingestion & capacity throttling."""
    def __init__(self, capacity: int, refill_rate_per_sec: float):
        self.capacity = float(capacity)
        self.tokens = float(capacity)
        self.refill_rate = float(refill_rate_per_sec)
        self.last_update = time.time()
        self.lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> bool:
        async with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + (elapsed * self.refill_rate))
            self.last_update = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

def get_rep_workload_metrics(db_conn) -> List[Dict[str, Any]]:
    """Calculates live workload, effort points, and capacity utilization for each sales rep."""
    cursor = db_conn.cursor()
    cursor.execute("""
    SELECT 
        r.id, r.name, r.email, r.role, r.department, 
        r.max_capacity_points, r.target_quota, r.closed_won_revenue, r.avatar_url,
        COALESCE(SUM(CASE WHEN d.stage NOT IN ('Closed Won', 'Closed Lost') THEN d.effort_points ELSE 0 END), 0) AS current_load_points,
        COALESCE(SUM(CASE WHEN d.stage NOT IN ('Closed Won', 'Closed Lost') THEN 1 ELSE 0 END), 0) AS active_deals_count
    FROM reps r
    LEFT JOIN deals d ON r.id = d.assigned_rep_id
    GROUP BY r.id
    ORDER BY current_load_points DESC;
    """)
    rows = cursor.fetchall()
    results = []
    for r in rows:
        max_cap = r["max_capacity_points"]
        load = r["current_load_points"]
        utilization = round((load / max_cap) * 100, 1) if max_cap > 0 else 0.0

        if utilization > 90.0:
            status = "Overloaded"
        elif utilization >= 75.0:
            status = "Near Capacity"
        elif utilization >= 45.0:
            status = "Optimal"
        else:
            status = "Underutilized"

        results.append({
            "id": r["id"],
            "name": r["name"],
            "email": r["email"],
            "role": r["role"],
            "department": r["department"],
            "max_capacity_points": max_cap,
            "target_quota": r["target_quota"],
            "closed_won_revenue": r["closed_won_revenue"],
            "avatar_url": r["avatar_url"],
            "current_load_points": load,
            "active_deals_count": r["active_deals_count"],
            "utilization_pct": utilization,
            "capacity_status": status,
            "available_headroom": max(0, max_cap - load)
        })
    return results

def find_optimal_rep_for_deal(db_conn, effort_points: int, preferred_department: Optional[str] = None) -> Optional[int]:
    """
    Intelligent Rep Matcher: selects the best sales rep based on available capacity headroom,
    department fit, and lowest current utilization.
    """
    reps = get_rep_workload_metrics(db_conn)
    if not reps:
        return None

    # Filter to reps who have enough headroom
    candidates = [r for r in reps if r["available_headroom"] >= effort_points]
    if not candidates:
        # Fallback to rep with the highest remaining headroom even if slightly over
        candidates = sorted(reps, key=lambda r: r["available_headroom"], reverse=True)
        return candidates[0]["id"] if candidates else None

    # If department preferred, prioritize compatible reps
    if preferred_department:
        dept_candidates = [r for r in candidates if r["department"].lower() == preferred_department.lower()]
        if dept_candidates:
            candidates = dept_candidates

    # Sort by lowest utilization percentage (load balancing)
    candidates.sort(key=lambda r: r["utilization_pct"])
    return candidates[0]["id"]

def rebalance_sales_capacity(db_conn) -> Dict[str, Any]:
    """
    Automated Workload Rebalancer:
    Detects overloaded reps (>85% capacity) and safely migrates early-stage unworked deals
    ('Lead' or 'Qualified') to underutilized reps with compatible bandwidth.
    """
    cursor = db_conn.cursor()
    reps = get_rep_workload_metrics(db_conn)
    now = datetime.now(timezone.utc).isoformat()

    overloaded_reps = [r for r in reps if r["utilization_pct"] > 85.0]
    underutilized_reps = [r for r in reps if r["utilization_pct"] < 65.0]

    if not overloaded_reps:
        return {
            "status": "balanced",
            "message": "All sales reps are operating within safe capacity limits (<85%). No rebalancing needed.",
            "reassigned_deals": []
        }

    reassigned_deals = []

    for over_rep in overloaded_reps:
        # Fetch early-stage deals belonging to this rep
        cursor.execute("""
        SELECT id, name, amount, stage, effort_points, account_id 
        FROM deals 
        WHERE assigned_rep_id = ? AND stage IN ('Lead', 'Qualified')
        ORDER BY stage ASC, effort_points ASC;
        """, (over_rep["id"],))
        deals_to_consider = cursor.fetchall()

        current_load = over_rep["current_load_points"]
        max_cap = over_rep["max_capacity_points"]

        for deal in deals_to_consider:
            # Check if rep is now within healthy capacity (<80%)
            if (current_load / max_cap) * 100 <= 80.0:
                break

            deal_id = deal["id"]
            deal_points = deal["effort_points"]

            # Find target rep with bandwidth
            underutilized_reps.sort(key=lambda r: r["current_load_points"])
            target_rep = None
            for cand in underutilized_reps:
                if cand["id"] != over_rep["id"] and cand["available_headroom"] >= deal_points:
                    target_rep = cand
                    break

            if target_rep:
                # Execute transfer
                cursor.execute("""
                UPDATE deals SET assigned_rep_id = ?, updated_at = ? WHERE id = ?;
                """, (target_rep["id"], now, deal_id))

                # Log activity
                log_msg = f"Rebalanced deal '{deal['name']}' ({deal_points} pts) from {over_rep['name']} (overloaded at {over_rep['utilization_pct']}%) to {target_rep['name']} (capacity headroom {target_rep['available_headroom']} pts)"
                cursor.execute("""
                INSERT INTO activity_logs (deal_id, account_id, rep_id, action_type, message, timestamp)
                VALUES (?, ?, ?, 'CAPACITY_REBALANCE', ?, ?);
                """, (deal_id, deal["account_id"], target_rep["id"], log_msg, now))

                # Update running state
                current_load -= deal_points
                over_rep["current_load_points"] = current_load
                over_rep["utilization_pct"] = round((current_load / max_cap) * 100, 1)

                target_rep["current_load_points"] += deal_points
                target_rep["available_headroom"] -= deal_points
                target_rep["utilization_pct"] = round((target_rep["current_load_points"] / target_rep["max_capacity_points"]) * 100, 1)

                reassigned_deals.append({
                    "deal_id": deal_id,
                    "deal_name": deal["name"],
                    "points": deal_points,
                    "from_rep": over_rep["name"],
                    "to_rep": target_rep["name"],
                    "deal_amount": deal["amount"]
                })

    # Clear resolved rep capacity alerts
    cursor.execute("""
    UPDATE capacity_alerts 
    SET resolved = 1 
    WHERE entity_type = 'Rep' AND resolved = 0;
    """)

    db_conn.commit()

    return {
        "status": "success",
        "message": f"Successfully rebalanced {len(reassigned_deals)} deals across sales capacity pools.",
        "reassigned_deals": reassigned_deals
    }

def calculate_infrastructure_capacity(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Advanced CRM System Capacity Planner & Sizing Engine:
    Computes IOPS, QPS, Database Growth, Redis Working Set, Message Queue Throughput,
    Kubernetes Node count, and estimated Cloud Costs based on operational traffic.
    """
    reps = params.get("active_sales_reps", 50)
    inbound_leads_day = params.get("inbound_leads_per_day", 2500)
    integrations = params.get("api_integrations_count", 8)
    retention_yrs = params.get("data_retention_years", 3)
    peak_multiplier = params.get("peak_traffic_multiplier", 3.5)

    # Traffic calculations
    # Average Rep performs ~1.2 interactions / sec during business hours (8 hrs/day)
    rep_qps = (reps * 1.2 * (8 * 3600)) / 86400.0
    # Inbound leads generate ~12 read/write DB queries per ingested lead
    lead_qps = (inbound_leads_day * 12.0) / 86400.0
    # API integrations generate webhook and sync events
    api_qps = (integrations * 35000.0) / 86400.0

    avg_qps = round(rep_qps + lead_qps + api_qps, 2)
    peak_qps = round(avg_qps * peak_multiplier, 2)

    # IOPS breakdown: 75% reads, 25% writes
    write_iops = round(peak_qps * 0.25 * 3.5, 0)  # write amplification & indexes
    read_iops = round(peak_qps * 0.75 * 1.8, 0)
    total_iops = int(write_iops + read_iops)

    # Storage calculations
    # Annual records:
    leads_yr = inbound_leads_day * 365
    activities_yr = leads_yr * 6  # ~6 activity logs / status transitions per lead
    accounts_yr = reps * 180
    total_records_yr = leads_yr + activities_yr + accounts_yr

    # Avg row sizes:
    # Leads: 2.2 KB, Activities/Audit: 1.1 KB, Accounts/Deals: 3.5 KB
    raw_storage_gb_yr = ((leads_yr * 2.2) + (activities_yr * 1.1) + (accounts_yr * 3.5)) / (1024 * 1024)
    # WAL, B-Tree Indexes, and Snapshots overhead: +55%
    total_storage_gb_yr = round(raw_storage_gb_yr * 1.55, 2)
    multi_year_db_storage_gb = round(total_storage_gb_yr * retention_yrs, 1)

    # In-memory Caching (Redis Cluster)
    # Working set: 20% of last 60 days of data + session tokens
    active_60d_gb = (total_storage_gb_yr / 365.0) * 60.0
    cache_hot_set_gb = round(active_60d_gb * 0.20 + (reps * 0.05), 2)
    recommended_redis_ram_gb = max(8, int(math.ceil(cache_hot_set_gb * 1.4)))

    # Message Queue Throughput (Kafka / RabbitMQ)
    peak_events_per_sec = round((inbound_leads_day / 86400.0 * peak_multiplier) + (api_qps * peak_multiplier), 1)
    recommended_partitions = max(3, int(math.ceil(peak_events_per_sec / 250.0)))

    # Compute Recommendations (EKS / ECS / Nodes)
    # 1 vCPU per 250 Peak QPS + 100% redundancy margin
    req_cpu_cores = max(4, int(math.ceil((peak_qps / 180.0))))
    req_app_instances = max(2, int(math.ceil(req_cpu_cores / 4)))  # 4-core containers

    # Sharding Strategy
    if multi_year_db_storage_gb > 800 or peak_qps > 3000:
        sharding_rec = "Horizontal Tenant/Org Sharding with Citus or Vitess (Distributed SQL)"
    elif multi_year_db_storage_gb > 250 or peak_qps > 1000:
        sharding_rec = "Read Replicas Pool (1 Primary + 3 Read Replicas) + Partitioning by Created Date (Range Sharding)"
    else:
        sharding_rec = "Single Primary Multi-AZ RDS / Aurora PostgreSQL with Read Replica"

    # Cloud Infrastructure Cost Estimation (USD / Month)
    # DB: Aurora PostgreSQL compute ($0.12/ACU-hr) + Storage ($0.10/GB) + IOPS
    db_cost = round((req_app_instances * 95) + (multi_year_db_storage_gb * 0.12) + (total_iops * 0.02), 2)
    # Compute: c6i.xlarge instances ($120/mo each)
    compute_cost = round(req_app_instances * 135.0, 2)
    # Redis Cluster (ElastiCache):
    redis_cost = round(max(60.0, recommended_redis_ram_gb * 8.5), 2)
    # Kafka / Streaming:
    queue_cost = round(85.0 + (recommended_partitions * 12.0), 2)
    # Networking, S3 Backups & Observability:
    misc_cost = round(150.0 + (reps * 1.5), 2)

    total_monthly_usd = round(db_cost + compute_cost + redis_cost + queue_cost + misc_cost, 2)

    return {
        "metrics": {
            "average_qps": avg_qps,
            "peak_qps": peak_qps,
            "read_iops_required": int(read_iops),
            "write_iops_required": int(write_iops),
            "total_iops_required": total_iops,
            "annual_new_records": int(total_records_yr)
        },
        "storage_breakdown": {
            "raw_annual_data_gb": round(raw_storage_gb_yr, 2),
            "annual_total_storage_gb": total_storage_gb_yr,
            "multi_year_total_storage_gb": multi_year_db_storage_gb,
            "retention_years": retention_yrs
        },
        "compute_recommendation": {
            "required_vcpu_cores": req_cpu_cores,
            "recommended_app_instances": req_app_instances,
            "instance_size": "c6i.xlarge (4 vCPU, 8 GB RAM)",
            "autoscaling_min_replicas": req_app_instances,
            "autoscaling_max_replicas": req_app_instances * 3
        },
        "caching_and_queue": {
            "hot_working_set_gb": cache_hot_set_gb,
            "recommended_redis_ram_gb": recommended_redis_ram_gb,
            "peak_events_per_sec": peak_events_per_sec,
            "recommended_queue_partitions": recommended_partitions,
            "message_queue_technology": "Apache Kafka (KRaft mode) or AWS MSK"
        },
        "sharding_recommendation": sharding_rec,
        "estimated_monthly_cost_usd": total_monthly_usd,
        "cost_breakdown": {
            "database_rds_usd": db_cost,
            "app_compute_usd": compute_cost,
            "redis_cache_usd": redis_cost,
            "message_queue_usd": queue_cost,
            "networking_and_logs_usd": misc_cost
        }
    }

async def run_capacity_stress_simulation(
    total_events: int = 400,
    concurrency_workers: int = 8,
    rate_limit_capacity: int = 150,
    rate_limit_refill_per_sec: int = 100
) -> Dict[str, Any]:
    """
    Simulates high-velocity event ingestion into the CRM with Token Bucket rate limiting,
    measuring latency distribution, throttle rate, and queuing backpressure.
    """
    limiter = TokenBucketRateLimiter(rate_limit_capacity, rate_limit_refill_per_sec)
    latencies = []
    throttled_count = 0
    processed_count = 0
    queued_count = 0

    semaphore = asyncio.Semaphore(concurrency_workers)
    start_time = time.time()

    async def worker_task(event_id: int):
        nonlocal throttled_count, processed_count, queued_count
        t0 = time.time()
        async with semaphore:
            # Check capacity token bucket
            allowed = await limiter.acquire(1)
            if not allowed:
                # In a CRM with backpressure, burst events are queued or throttled with 429
                if queued_count < (rate_limit_capacity // 2):
                    # Queued briefly then retried
                    queued_count += 1
                    await asyncio.sleep(0.015)
                    # Retry
                    if await limiter.acquire(1):
                        processed_count += 1
                        latency = (time.time() - t0) * 1000.0
                        latencies.append(latency)
                        return
                throttled_count += 1
                latency = (time.time() - t0) * 1000.0
                latencies.append(latency)
                return

            # Simulate database write + index transaction
            await asyncio.sleep(0.003)
            processed_count += 1
            latency = (time.time() - t0) * 1000.0
            latencies.append(latency)

    tasks = [worker_task(i) for i in range(total_events)]
    await asyncio.gather(*tasks)

    duration = max(0.001, time.time() - start_time)
    latencies.sort()

    p50 = latencies[int(len(latencies) * 0.50)] if latencies else 0.0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0.0
    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0

    throughput = round(processed_count / duration, 1)

    if throttled_count == 0:
        backpressure_status = "Optimal (Zero Drops, Capacity Headroom Available)"
    elif throttled_count < (total_events * 0.15):
        backpressure_status = "Slight Backpressure (Graceful Token Bucket Throttling)"
    else:
        backpressure_status = "High Contention (Autoscaling / Worker Increase Recommended)"

    return {
        "total_events_sent": total_events,
        "events_processed": processed_count,
        "events_throttled": throttled_count,
        "events_queued": queued_count,
        "avg_latency_ms": round(avg_lat, 2),
        "p50_latency_ms": round(p50, 2),
        "p95_latency_ms": round(p95, 2),
        "p99_latency_ms": round(p99, 2),
        "total_duration_sec": round(duration, 3),
        "effective_throughput_eps": throughput,
        "backpressure_status": backpressure_status
    }
