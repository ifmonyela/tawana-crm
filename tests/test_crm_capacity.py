import os
import sys
import pytest
import asyncio

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from database import get_db, init_db
from capacity_engine import (
    get_rep_workload_metrics,
    find_optimal_rep_for_deal,
    rebalance_sales_capacity,
    calculate_infrastructure_capacity,
    run_capacity_stress_simulation
)

@pytest.fixture(autouse=True)
def setup_database():
    import sqlite3
    from database import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Clean tables
    for table in ["deals", "contacts", "accounts", "reps", "activity_logs", "capacity_alerts"]:
        cursor.execute(f"DROP TABLE IF EXISTS {table};")
    conn.commit()
    conn.close()
    init_db()


def test_rep_workload_calculation():
    conn = get_db()
    reps = get_rep_workload_metrics(conn)
    conn.close()

    assert len(reps) >= 6
    # Verify that Elena Rostova is detected with high utilization (>85%)
    elena = next(r for r in reps if r["name"] == "Elena Rostova")
    assert elena["max_capacity_points"] == 30
    assert elena["current_load_points"] > 20
    assert elena["capacity_status"] in ("Overloaded", "Near Capacity")

    # Verify David Kim has headroom
    david = next(r for r in reps if r["name"] == "David Kim")
    assert david["available_headroom"] > 10

def test_find_optimal_rep_for_deal():
    conn = get_db()
    # A heavy deal (4 points) should be assigned to a rep with headroom rather than overloaded Elena
    rep_id = find_optimal_rep_for_deal(conn, effort_points=4, preferred_department="Mid-Market")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM reps WHERE id = ?;", (rep_id,))
    assigned_name = cursor.fetchone()["name"]
    conn.close()

    # Elena and Priya are near capacity; David Kim has ample headroom in Mid-Market
    assert assigned_name in ("David Kim", "Marcus Vance", "Sarah Jenkins", "Liam O'Connor")

def test_rebalance_sales_capacity():
    conn = get_db()
    rebalance_result = rebalance_sales_capacity(conn)
    reps_after = get_rep_workload_metrics(conn)
    conn.close()

    assert rebalance_result["status"] in ("success", "balanced")
    if rebalance_result["status"] == "success":
        assert len(rebalance_result["reassigned_deals"]) > 0

    # Verify that no rep has critical >95% overload after rebalancing
    for r in reps_after:
        assert r["utilization_pct"] <= 92.0

def test_calculate_infrastructure_capacity():
    params = {
        "active_sales_reps": 100,
        "inbound_leads_per_day": 5000,
        "api_integrations_count": 12,
        "data_retention_years": 5,
        "peak_traffic_multiplier": 4.0
    }
    result = calculate_infrastructure_capacity(params)

    assert "metrics" in result
    assert result["metrics"]["peak_qps"] > 0
    assert result["metrics"]["total_iops_required"] > 0
    assert result["storage_breakdown"]["multi_year_total_storage_gb"] > 0
    assert result["compute_recommendation"]["required_vcpu_cores"] >= 4
    assert result["estimated_monthly_cost_usd"] > 0
    assert any(term in result["sharding_recommendation"] for term in ["Horizontal", "Replica", "Partitioning"])

def test_run_capacity_stress_simulation():
    res = asyncio.run(run_capacity_stress_simulation(
        total_events=120,
        concurrency_workers=6,
        rate_limit_capacity=50,
        rate_limit_refill_per_sec=40
    ))

    assert res["total_events_sent"] == 120
    assert res["events_processed"] > 0
    assert res["p50_latency_ms"] >= 0
    assert res["effective_throughput_eps"] > 0
    assert any(term in res["backpressure_status"] for term in ["Optimal", "Backpressure", "Contention"])

def test_fastapi_endpoints():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)

    # Health check
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

    # Dashboard stats
    res = client.get("/api/dashboard/stats")
    assert res.status_code == 200
    data = res.json()
    assert "pipeline" in data
    assert "capacity" in data
    assert data["capacity"]["total_sales_reps"] >= 6

    # Reps endpoint
    res = client.get("/api/reps")
    assert res.status_code == 200
    assert len(res.json()) >= 6

    # Deals endpoint
    res = client.get("/api/deals")
    assert res.status_code == 200
    assert len(res.json()) > 0

    # Infrastructure calculation endpoint
    res = client.post("/api/capacity/infrastructure/calculate", json={
        "active_sales_reps": 75,
        "inbound_leads_per_day": 3000,
        "api_integrations_count": 10,
        "data_retention_years": 3,
        "peak_traffic_multiplier": 3.0
    })
    assert res.status_code == 200
    inf_data = res.json()
    assert inf_data["metrics"]["peak_qps"] > 0
    assert inf_data["estimated_monthly_cost_usd"] > 0

