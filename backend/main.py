import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from models import (
    RepCreate, RepUpdate, RepResponse,
    DealCreate, DealUpdate, DealResponse,
    AccountCreate, AccountResponse,
    ContactCreate, ContactResponse,
    InfrastructureRequirementsRequest, InfrastructureRequirementsResponse,
    StressTestRequest, StressTestResponse
)
from database import get_db, init_db
from capacity_engine import (
    get_rep_workload_metrics,
    find_optimal_rep_for_deal,
    rebalance_sales_capacity,
    calculate_infrastructure_capacity,
    run_capacity_stress_simulation
)

# Initialize database schema and initial data
init_db()

app = FastAPI(
    title="Tawana CRM - Advanced Capacity Management Platform",
    description="Enterprise CRM with integrated Sales Workload Balancing, Account Quota Monitoring, and Infrastructure Sizing Engine",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Tawana CRM Capacity Platform",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": "SQLite (WAL Mode Enabled)"
    }

# ----------------- DASHBOARD ENDPOINTS -----------------

@app.get("/api/dashboard/stats")
def get_dashboard_stats():
    conn = get_db()
    cursor = conn.cursor()

    # Total pipeline and deals
    cursor.execute("""
    SELECT 
        COUNT(*) as total_deals,
        COALESCE(SUM(amount), 0) as total_pipeline,
        COALESCE(SUM(amount * (probability / 100.0)), 0) as weighted_pipeline,
        COALESCE(SUM(CASE WHEN stage = 'Closed Won' THEN amount ELSE 0 END), 0) as won_revenue
    FROM deals;
    """)
    deal_stats = dict(cursor.fetchone())

    # Active deals count
    cursor.execute("SELECT COUNT(*) FROM deals WHERE stage NOT IN ('Closed Won', 'Closed Lost');")
    active_deals = cursor.fetchone()[0]

    # Rep capacity metrics
    reps = get_rep_workload_metrics(conn)
    total_reps = len(reps)
    overloaded_reps = len([r for r in reps if r["capacity_status"] in ('Overloaded', 'Near Capacity')])
    avg_utilization = round(sum(r["utilization_pct"] for r in reps) / total_reps, 1) if total_reps > 0 else 0.0

    # Account metrics
    cursor.execute("""
    SELECT 
        COUNT(*) as total_accounts,
        COALESCE(SUM(mrr), 0) as total_mrr,
        COALESCE(SUM(CASE WHEN (seats_used * 1.0 / seats_limit) > 0.85 OR (api_calls_used * 1.0 / api_calls_limit) > 0.85 OR (storage_gb_used * 1.0 / storage_gb_limit) > 0.85 THEN 1 ELSE 0 END), 0) as accounts_near_capacity
    FROM accounts;
    """)
    account_stats = dict(cursor.fetchone())

    # Recent activities
    cursor.execute("""
    SELECT id, action_type, message, timestamp 
    FROM activity_logs 
    ORDER BY id DESC LIMIT 8;
    """)
    recent_activities = [dict(r) for r in cursor.fetchall()]

    # Unresolved alerts
    cursor.execute("""
    SELECT id, entity_type, severity, title, message, created_at 
    FROM capacity_alerts 
    WHERE resolved = 0 
    ORDER BY id DESC;
    """)
    alerts = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return {
        "pipeline": {
            "total_deals": deal_stats["total_deals"],
            "active_deals": active_deals,
            "total_pipeline_value": round(deal_stats["total_pipeline"], 2),
            "weighted_pipeline_value": round(deal_stats["weighted_pipeline"], 2),
            "won_revenue": round(deal_stats["won_revenue"], 2),
        },
        "capacity": {
            "total_sales_reps": total_reps,
            "overloaded_reps": overloaded_reps,
            "average_utilization_pct": avg_utilization,
            "system_status": "Overloaded" if overloaded_reps >= 2 else "Optimal"
        },
        "accounts": {
            "total_accounts": account_stats["total_accounts"],
            "total_mrr": round(account_stats["total_mrr"], 2),
            "accounts_near_capacity": account_stats["accounts_near_capacity"]
        },
        "active_alerts": alerts,
        "recent_activities": recent_activities
    }

# ----------------- REPS & WORKLOAD CAPACITY -----------------

@app.get("/api/reps", response_model=List[RepResponse])
def get_reps():
    conn = get_db()
    reps = get_rep_workload_metrics(conn)
    conn.close()
    return reps

@app.post("/api/reps", status_code=status.HTTP_201_CREATED)
def create_rep(payload: RepCreate):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO reps (name, email, role, department, max_capacity_points, target_quota, avatar_url)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (payload.name, payload.email, payload.role, payload.department, payload.max_capacity_points, payload.target_quota, payload.avatar_url or "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=150"))
        conn.commit()
        rep_id = cursor.lastrowid
        conn.close()
        return {"id": rep_id, "message": "Sales representative added successfully."}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/reps/{rep_id}")
def update_rep(rep_id: int, payload: RepUpdate):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM reps WHERE id = ?;", (rep_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Rep not found")

    fields = []
    values = []
    if payload.name is not None:
        fields.append("name = ?"); values.append(payload.name)
    if payload.email is not None:
        fields.append("email = ?"); values.append(payload.email)
    if payload.role is not None:
        fields.append("role = ?"); values.append(payload.role)
    if payload.department is not None:
        fields.append("department = ?"); values.append(payload.department)
    if payload.max_capacity_points is not None:
        fields.append("max_capacity_points = ?"); values.append(payload.max_capacity_points)
    if payload.target_quota is not None:
        fields.append("target_quota = ?"); values.append(payload.target_quota)

    if fields:
        values.append(rep_id)
        cursor.execute(f"UPDATE reps SET {', '.join(fields)} WHERE id = ?;", tuple(values))
        conn.commit()

    conn.close()
    return {"message": "Rep updated successfully"}

@app.post("/api/capacity/rebalance")
def trigger_capacity_rebalance():
    conn = get_db()
    result = rebalance_sales_capacity(conn)
    conn.close()
    return result

# ----------------- DEALS & PIPELINE -----------------

@app.get("/api/deals", response_model=List[DealResponse])
def get_deals(stage: Optional[str] = None, rep_id: Optional[int] = None):
    conn = get_db()
    cursor = conn.cursor()
    query = """
    SELECT 
        d.id, d.account_id, d.name, d.amount, d.stage, d.probability, d.effort_points,
        d.assigned_rep_id, d.expected_close_date, d.created_at, d.updated_at,
        r.name as assigned_rep_name,
        a.name as account_name
    FROM deals d
    LEFT JOIN reps r ON d.assigned_rep_id = r.id
    LEFT JOIN accounts a ON d.account_id = a.id
    WHERE 1=1
    """
    params = []
    if stage:
        query += " AND d.stage = ?"
        params.append(stage)
    if rep_id:
        query += " AND d.assigned_rep_id = ?"
        params.append(rep_id)

    query += " ORDER BY d.id DESC;"
    cursor.execute(query, tuple(params))
    deals = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return deals

@app.post("/api/deals", status_code=status.HTTP_201_CREATED)
def create_deal(payload: DealCreate):
    conn = get_db()
    cursor = conn.cursor()

    # Intelligent Auto-Assignment if rep not chosen
    assigned_rep_id = payload.assigned_rep_id
    auto_assigned = False
    if not assigned_rep_id:
        assigned_rep_id = find_optimal_rep_for_deal(conn, payload.effort_points)
        auto_assigned = True

    now = datetime.now(timezone.utc).isoformat()
    cursor.execute("""
    INSERT INTO deals (account_id, name, amount, stage, probability, effort_points, assigned_rep_id, expected_close_date, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        payload.account_id, payload.name, payload.amount, payload.stage,
        payload.probability, payload.effort_points, assigned_rep_id,
        payload.expected_close_date or "2026-12-31", now, now
    ))
    deal_id = cursor.lastrowid

    # Check rep capacity limit and warn if overloaded
    rep_msg = ""
    if assigned_rep_id:
        cursor.execute("SELECT name FROM reps WHERE id = ?;", (assigned_rep_id,))
        rep_row = cursor.fetchone()
        rep_name = rep_row["name"] if rep_row else f"Rep #{assigned_rep_id}"
        rep_msg = f" (Assigned to {rep_name}{' via Smart Capacity Engine' if auto_assigned else ''})"

    log_msg = f"Created new deal '{payload.name}' (${payload.amount:,.0f}, {payload.effort_points} capacity pts){rep_msg}"
    cursor.execute("""
    INSERT INTO activity_logs (deal_id, account_id, rep_id, action_type, message, timestamp)
    VALUES (?, ?, ?, 'DEAL_CREATED', ?, ?);
    """, (deal_id, payload.account_id, assigned_rep_id, log_msg, now))

    conn.commit()
    conn.close()
    return {"id": deal_id, "assigned_rep_id": assigned_rep_id, "auto_assigned": auto_assigned}

@app.put("/api/deals/{deal_id}")
def update_deal(deal_id: int, payload: DealUpdate):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM deals WHERE id = ?;", (deal_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Deal not found")

    fields = []
    values = []
    now = datetime.now(timezone.utc).isoformat()

    if payload.name is not None:
        fields.append("name = ?"); values.append(payload.name)
    if payload.amount is not None:
        fields.append("amount = ?"); values.append(payload.amount)
    if payload.stage is not None:
        fields.append("stage = ?"); values.append(payload.stage)
    if payload.probability is not None:
        fields.append("probability = ?"); values.append(payload.probability)
    if payload.effort_points is not None:
        fields.append("effort_points = ?"); values.append(payload.effort_points)
    if payload.assigned_rep_id is not None:
        fields.append("assigned_rep_id = ?"); values.append(payload.assigned_rep_id)
    if payload.expected_close_date is not None:
        fields.append("expected_close_date = ?"); values.append(payload.expected_close_date)

    fields.append("updated_at = ?")
    values.append(now)

    values.append(deal_id)
    cursor.execute(f"UPDATE deals SET {', '.join(fields)} WHERE id = ?;", tuple(values))

    # Log stage change or modification
    if payload.stage and payload.stage != existing["stage"]:
        log_msg = f"Deal '{existing['name']}' moved from {existing['stage']} -> {payload.stage}"
        cursor.execute("""
        INSERT INTO activity_logs (deal_id, account_id, rep_id, action_type, message, timestamp)
        VALUES (?, ?, ?, 'STAGE_CHANGE', ?, ?);
        """, (deal_id, existing["account_id"], existing["assigned_rep_id"], log_msg, now))

    conn.commit()
    conn.close()
    return {"message": "Deal updated successfully"}

@app.delete("/api/deals/{deal_id}")
def delete_deal(deal_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM deals WHERE id = ?;", (deal_id,))
    conn.commit()
    conn.close()
    return {"message": "Deal deleted successfully"}

# ----------------- ACCOUNTS & QUOTA CAPACITY -----------------

@app.get("/api/accounts", response_model=List[AccountResponse])
def get_accounts():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT 
        a.id, a.name, a.domain, a.industry, a.tier, a.health_score, a.mrr,
        a.assigned_rep_id, a.seats_limit, a.seats_used,
        a.api_calls_limit, a.api_calls_used,
        a.storage_gb_limit, a.storage_gb_used, a.created_at,
        r.name as assigned_rep_name
    FROM accounts a
    LEFT JOIN reps r ON a.assigned_rep_id = r.id
    ORDER BY a.mrr DESC;
    """)
    rows = cursor.fetchall()
    accounts = []
    for r in rows:
        seats_pct = round((r["seats_used"] / r["seats_limit"]) * 100, 1)
        api_pct = round((r["api_calls_used"] / r["api_calls_limit"]) * 100, 1)
        storage_pct = round((r["storage_gb_used"] / r["storage_gb_limit"]) * 100, 1)

        near_cap = any(p >= 80.0 for p in [seats_pct, api_pct, storage_pct])
        over_cap = any(p >= 100.0 for p in [seats_pct, api_pct, storage_pct])

        accounts.append({
            "id": r["id"],
            "name": r["name"],
            "domain": r["domain"],
            "industry": r["industry"],
            "tier": r["tier"],
            "health_score": r["health_score"],
            "mrr": r["mrr"],
            "assigned_rep_id": r["assigned_rep_id"],
            "assigned_rep_name": r["assigned_rep_name"],
            "seats_limit": r["seats_limit"],
            "seats_used": r["seats_used"],
            "seats_utilization_pct": seats_pct,
            "api_calls_limit": r["api_calls_limit"],
            "api_calls_used": r["api_calls_used"],
            "api_calls_utilization_pct": api_pct,
            "storage_gb_limit": r["storage_gb_limit"],
            "storage_gb_used": r["storage_gb_used"],
            "storage_gb_utilization_pct": storage_pct,
            "is_near_capacity": near_cap,
            "is_over_capacity": over_cap,
            "created_at": r["created_at"]
        })
    conn.close()
    return accounts

@app.post("/api/accounts", status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreate):
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    cursor.execute("""
    INSERT INTO accounts (name, domain, industry, tier, health_score, mrr, assigned_rep_id, seats_limit, seats_used, api_calls_limit, api_calls_used, storage_gb_limit, storage_gb_used, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        payload.name, payload.domain, payload.industry, payload.tier,
        payload.health_score, payload.mrr, payload.assigned_rep_id,
        payload.seats_limit, int(payload.seats_limit * 0.4),
        payload.api_calls_limit, int(payload.api_calls_limit * 0.3),
        payload.storage_gb_limit, round(payload.storage_gb_limit * 0.25, 1),
        now
    ))
    acc_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"id": acc_id, "message": "Account created successfully."}

@app.put("/api/accounts/{account_id}/usage")
def update_account_usage(account_id: int, seats_delta: int = 0, api_delta: int = 0, storage_delta_gb: float = 0.0):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts WHERE id = ?;", (account_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Account not found")

    new_seats = max(0, row["seats_used"] + seats_delta)
    new_api = max(0, row["api_calls_used"] + api_delta)
    new_storage = max(0.0, round(row["storage_gb_used"] + storage_delta_gb, 1))

    cursor.execute("""
    UPDATE accounts 
    SET seats_used = ?, api_calls_used = ?, storage_gb_used = ?
    WHERE id = ?;
    """, (new_seats, new_api, new_storage, account_id))

    # Check capacity alerts
    now = datetime.now(timezone.utc).isoformat()
    if (new_seats / row["seats_limit"]) >= 0.90:
        cursor.execute("""
        INSERT INTO capacity_alerts (entity_type, entity_id, severity, title, message, resolved, created_at)
        VALUES ('Account', ?, 'warning', ?, ?, 0, ?);
        """, (account_id, f"{row['name']} Seats Quota Warning", f"Seats consumption at {new_seats}/{row['seats_limit']} ({round((new_seats/row['seats_limit'])*100)}%)", now))

    conn.commit()
    conn.close()
    return {"message": "Account usage updated"}

# ----------------- CONTACTS -----------------

@app.get("/api/contacts", response_model=List[ContactResponse])
def get_contacts():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT c.id, c.account_id, c.name, c.email, c.phone, c.role, c.created_at, a.name as account_name
    FROM contacts c
    LEFT JOIN accounts a ON c.account_id = a.id
    ORDER BY c.id DESC;
    """)
    contacts = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return contacts

@app.post("/api/contacts", status_code=status.HTTP_201_CREATED)
def create_contact(payload: ContactCreate):
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    cursor.execute("""
    INSERT INTO contacts (account_id, name, email, phone, role, created_at)
    VALUES (?, ?, ?, ?, ?, ?);
    """, (payload.account_id, payload.name, payload.email, payload.phone, payload.role, now))
    cid = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"id": cid, "message": "Contact created successfully."}

# ----------------- CAPACITY ALERTS -----------------

@app.get("/api/capacity/alerts")
def get_alerts():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM capacity_alerts ORDER BY resolved ASC, id DESC;")
    alerts = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return alerts

@app.post("/api/capacity/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE capacity_alerts SET resolved = 1 WHERE id = ?;", (alert_id,))
    conn.commit()
    conn.close()
    return {"message": "Alert resolved"}

# ----------------- INFRASTRUCTURE CAPACITY SIZER & LAB -----------------

@app.post("/api/capacity/infrastructure/calculate", response_model=InfrastructureRequirementsResponse)
def calculate_infrastructure(req: InfrastructureRequirementsRequest):
    return calculate_infrastructure_capacity(req.model_dump())

@app.post("/api/capacity/simulator/stress-test", response_model=StressTestResponse)
async def run_stress_test(req: StressTestRequest):
    return await run_capacity_stress_simulation(
        total_events=req.total_events,
        concurrency_workers=req.concurrency_workers,
        rate_limit_capacity=req.rate_limit_capacity,
        rate_limit_refill_per_sec=req.rate_limit_refill_per_sec
    )

# ----------------- FRONTEND SPA MOUNT -----------------

if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/{full_path:path}")
def serve_spa(full_path: str):
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({"status": "Frontend not yet generated"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
