import sqlite3
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "crm.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        role TEXT NOT NULL,
        department TEXT NOT NULL,
        max_capacity_points INTEGER NOT NULL DEFAULT 25,
        target_quota REAL NOT NULL DEFAULT 250000.0,
        closed_won_revenue REAL NOT NULL DEFAULT 0.0,
        avatar_url TEXT
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        domain TEXT NOT NULL,
        industry TEXT NOT NULL,
        tier TEXT NOT NULL,
        health_score INTEGER NOT NULL DEFAULT 85,
        mrr REAL NOT NULL DEFAULT 1500.0,
        assigned_rep_id INTEGER,
        seats_limit INTEGER NOT NULL DEFAULT 25,
        seats_used INTEGER NOT NULL DEFAULT 15,
        api_calls_limit INTEGER NOT NULL DEFAULT 100000,
        api_calls_used INTEGER NOT NULL DEFAULT 45000,
        storage_gb_limit REAL NOT NULL DEFAULT 100.0,
        storage_gb_used REAL NOT NULL DEFAULT 35.0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (assigned_rep_id) REFERENCES reps(id) ON DELETE SET NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT,
        role TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS deals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        amount REAL NOT NULL,
        stage TEXT NOT NULL,
        probability INTEGER NOT NULL DEFAULT 20,
        effort_points INTEGER NOT NULL DEFAULT 3,
        assigned_rep_id INTEGER,
        expected_close_date TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
        FOREIGN KEY (assigned_rep_id) REFERENCES reps(id) ON DELETE SET NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activity_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        deal_id INTEGER,
        account_id INTEGER,
        rep_id INTEGER,
        action_type TEXT NOT NULL,
        message TEXT NOT NULL,
        timestamp TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS capacity_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL, -- 'Rep', 'Account', 'System'
        entity_id INTEGER,
        severity TEXT NOT NULL, -- 'info', 'warning', 'critical'
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        resolved INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );
    """)

    conn.commit()
    conn.close()

    seed_database_if_empty()

def seed_database_if_empty():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM reps;")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    now = datetime.now(timezone.utc).isoformat()

    # Seed Reps
    reps_data = [
        ("Elena Rostova", "elena.r@nexus.io", "Principal AE", "Enterprise", 30, 500000.0, 320000.0, "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=150"),
        ("Marcus Vance", "marcus.v@nexus.io", "Senior AE", "Enterprise", 25, 400000.0, 210000.0, "https://images.unsplash.com/photo-1560250097-0b93528c311a?w=150"),
        ("Priya Sharma", "priya.s@nexus.io", "Senior AE", "Mid-Market", 25, 300000.0, 195000.0, "https://images.unsplash.com/photo-1580489944761-15a19d654956?w=150"),
        ("David Kim", "david.k@nexus.io", "AE", "Mid-Market", 22, 250000.0, 95000.0, "https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?w=150"),
        ("Sarah Jenkins", "sarah.j@nexus.io", "Account Executive", "SMB", 35, 200000.0, 145000.0, "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150"),
        ("Liam O'Connor", "liam.o@nexus.io", "Account Executive", "SMB", 30, 180000.0, 60000.0, "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150")
    ]

    cursor.executemany("""
    INSERT INTO reps (name, email, role, department, max_capacity_points, target_quota, closed_won_revenue, avatar_url)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, reps_data)

    # Seed Accounts
    accounts_data = [
        ("Acme Technologies", "acme-tech.com", "Cloud Infrastructure", "Enterprise", 94, 28500.0, 1, 100, 96, 5000000, 4820000, 1000.0, 940.0, now),
        ("CloudScale Systems", "cloudscale.net", "SaaS Platform", "Enterprise", 88, 22000.0, 2, 80, 52, 3000000, 1800000, 750.0, 410.0, now),
        ("FinPulse Global", "finpulse.io", "Fintech / Banking", "Enterprise", 91, 34000.0, 1, 150, 142, 10000000, 8900000, 2000.0, 1850.0, now),
        ("Nexus Health AI", "nexushealth.ai", "Healthcare Tech", "Mid-Market", 76, 8500.0, 3, 40, 38, 500000, 460000, 250.0, 210.0, now),
        ("Quantum Analytics", "quantumanalytics.co", "Data Analytics", "Mid-Market", 82, 6200.0, 4, 30, 16, 400000, 190000, 200.0, 95.0, now),
        ("Strata Security", "stratasec.io", "Cybersecurity", "Mid-Market", 68, 9400.0, 3, 50, 49, 800000, 785000, 300.0, 280.0, now),
        ("Apex Media Labs", "apexmedialabs.com", "Digital Media", "SMB", 79, 3100.0, 5, 20, 18, 150000, 125000, 100.0, 72.0, now),
        ("Veloce Logistics", "velocelog.com", "Supply Chain", "SMB", 85, 4200.0, 6, 25, 11, 200000, 75000, 150.0, 55.0, now),
        ("Hyperion Autonomous", "hyperionauto.io", "AI Robotics", "Startup", 92, 1800.0, 5, 10, 9, 80000, 78000, 50.0, 44.0, now),
        ("DataForge Engine", "dataforge.io", "Developer Tools", "Mid-Market", 87, 5600.0, 4, 35, 22, 350000, 210000, 180.0, 80.0, now)
    ]

    cursor.executemany("""
    INSERT INTO accounts (name, domain, industry, tier, health_score, mrr, assigned_rep_id, seats_limit, seats_used, api_calls_limit, api_calls_used, storage_gb_limit, storage_gb_used, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, accounts_data)

    # Seed Contacts
    contacts_data = [
        (1, "Sophia Laurent", "slaurent@acme-tech.com", "+1 555-0101", "VP of Engineering", now),
        (1, "Tyler Hayes", "thayes@acme-tech.com", "+1 555-0102", "Chief Architect", now),
        (2, "Daniel Vance", "dvance@cloudscale.net", "+1 555-0201", "Head of Product", now),
        (3, "Amara Thorne", "athorne@finpulse.io", "+1 555-0301", "CTO", now),
        (4, "Dr. Julian Mercer", "jmercer@nexushealth.ai", "+1 555-0401", "VP Clinical Ops", now),
        (5, "Rachel Green", "rgreen@quantumanalytics.co", "+1 555-0501", "Director of BI", now),
        (6, "Brandon Wu", "bwu@stratasec.io", "+1 555-0601", "Chief Security Officer", now),
        (7, "Chloe Morales", "cmorales@apexmedialabs.com", "+1 555-0701", "Ops Manager", now),
        (8, "Ethan Cole", "ecole@velocelog.com", "+1 555-0801", "Supply Chain Lead", now),
        (9, "Vikram Patel", "vpatel@hyperionauto.io", "+1 555-0901", "Founder & CEO", now),
        (10, "Lena Zhao", "lzhao@dataforge.io", "+1 555-1001", "Platform Architect", now)
    ]

    cursor.executemany("""
    INSERT INTO contacts (account_id, name, email, phone, role, created_at)
    VALUES (?, ?, ?, ?, ?, ?);
    """, contacts_data)

    # Seed Deals across reps with realistic effort weights
    # Notice: Elena (id 1) and Priya (id 3) are assigned heavy deals deliberately,
    # putting them at or above capacity!
    deals_data = [
        # Elena's Deals (Max 30, currently 29 pts)
        (1, "Acme Global Core Modernization", 220000.0, "Negotiation", 80, 5, 1, "2026-11-15", now, now),
        (1, "Acme AI Expansion Module", 85000.0, "Proposal", 60, 4, 1, "2026-12-01", now, now),
        (3, "FinPulse Next-Gen Liquidity Suite", 340000.0, "Negotiation", 85, 5, 1, "2026-10-30", now, now),
        (3, "FinPulse Realtime Ledger Pilot", 110000.0, "Proposal", 50, 4, 1, "2026-11-20", now, now),
        (1, "Acme Sandbox Compliance Addon", 45000.0, "Qualified", 40, 3, 1, "2026-12-15", now, now),
        (3, "FinPulse Security Audit Service", 55000.0, "Lead", 25, 4, 1, "2026-12-28", now, now),
        (1, "Acme Observability Connector", 38000.0, "Lead", 20, 4, 1, "2027-01-10", now, now),

        # Marcus's Deals (Max 25, currently 11 pts - Optimal Headroom)
        (2, "CloudScale Kubernetes Fleet Sync", 165000.0, "Proposal", 65, 4, 2, "2026-11-10", now, now),
        (2, "CloudScale Edge Cache Addon", 75000.0, "Qualified", 45, 3, 2, "2026-12-05", now, now),
        (2, "CloudScale Multi-Region DR", 90000.0, "Negotiation", 75, 4, 2, "2026-11-25", now, now),

        # Priya's Deals (Max 25, currently 24 pts - Near Capacity)
        (4, "Nexus Health HIPAA Federated Model", 95000.0, "Negotiation", 70, 5, 3, "2026-11-12", now, now),
        (4, "Nexus Health EMR FastBridge", 55000.0, "Proposal", 50, 4, 3, "2026-12-01", now, now),
        (6, "Strata Zero-Trust Gateway Suite", 115000.0, "Proposal", 60, 5, 3, "2026-11-28", now, now),
        (6, "Strata SOC Tier-1 Automation", 48000.0, "Qualified", 40, 3, 3, "2026-12-10", now, now),
        (6, "Strata Threat Intelligence Feed", 32000.0, "Lead", 20, 3, 3, "2026-12-20", now, now),
        (4, "Nexus Health Mobile Patient Portal", 28000.0, "Lead", 20, 4, 3, "2027-01-05", now, now),

        # David's Deals (Max 22, currently 6 pts - Underutilized Headroom)
        (5, "Quantum Analytics Lakehouse Ingest", 72000.0, "Proposal", 55, 3, 4, "2026-11-18", now, now),
        (10, "DataForge SDK CI/CD Pipeline", 58000.0, "Qualified", 45, 3, 4, "2026-12-08", now, now),

        # Sarah's Deals (Max 35, currently 22 pts - Optimal)
        (7, "Apex Media Multi-Channel Delivery", 38000.0, "Negotiation", 80, 4, 5, "2026-11-05", now, now),
        (7, "Apex Media Video Transcode Cloud", 26000.0, "Proposal", 60, 3, 5, "2026-11-22", now, now),
        (9, "Hyperion Telemetry Mesh", 42000.0, "Proposal", 50, 4, 5, "2026-12-02", now, now),
        (9, "Hyperion Edge Inference Node", 29000.0, "Qualified", 35, 3, 5, "2026-12-18", now, now),
        (7, "Apex Analytics Dashboard Addon", 18000.0, "Qualified", 40, 2, 5, "2026-11-30", now, now),
        (9, "Hyperion Developer Seats Pack", 15000.0, "Lead", 20, 2, 5, "2027-01-12", now, now),
        (7, "Apex Media Archival Tier", 14000.0, "Lead", 20, 2, 5, "2027-01-20", now, now),
        (9, "Hyperion Fleet Monitoring Pilot", 22000.0, "Lead", 20, 2, 5, "2027-01-15", now, now),

        # Liam's Deals (Max 30, currently 6 pts - Underutilized Headroom)
        (8, "Veloce Fleet Tracking Integration", 44000.0, "Qualified", 45, 3, 6, "2026-11-20", now, now),
        (8, "Veloce Automated Routing Engine", 36000.0, "Lead", 25, 3, 6, "2026-12-12", now, now)
    ]

    cursor.executemany("""
    INSERT INTO deals (account_id, name, amount, stage, probability, effort_points, assigned_rep_id, expected_close_date, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, deals_data)

    # Activity Logs
    logs_data = [
        (1, 1, 1, "STAGE_CHANGE", "Moved 'Acme Global Core Modernization' to Negotiation ($220,000)", now),
        (3, 3, 1, "STAGE_CHANGE", "Moved 'FinPulse Next-Gen Liquidity Suite' to Negotiation ($340,000)", now),
        (11, 4, 3, "CAPACITY_WARNING", "Rep Elena Rostova reached 97% capacity limit (29/30 points)", now),
        (13, 6, 3, "CAPACITY_WARNING", "Rep Priya Sharma reached 96% capacity limit (24/25 points)", now),
        (None, 1, None, "QUOTA_WARNING", "Account 'Acme Technologies' reached 96% seat limit (96/100 seats)", now),
        (None, 3, None, "QUOTA_WARNING", "Account 'FinPulse Global' reached 92% storage limit (1850/2000 GB)", now)
    ]

    cursor.executemany("""
    INSERT INTO activity_logs (deal_id, account_id, rep_id, action_type, message, timestamp)
    VALUES (?, ?, ?, ?, ?, ?);
    """, logs_data)

    # Initial Capacity Alerts
    alerts_data = [
        ("Rep", 1, "critical", "Elena Rostova at 97% Workload Capacity", "Rep has 29 points assigned against a 30-point ceiling. High risk of lead neglect and burnout.", 0, now),
        ("Rep", 3, "critical", "Priya Sharma at 96% Workload Capacity", "Rep has 24 points assigned against a 25-point ceiling. Rebalancing recommended.", 0, now),
        ("Account", 1, "warning", "Acme Technologies Seat Limit Alert", "Acme is consuming 96 of 100 provisioned seats (96% utilization). Immediate upsell candidate.", 0, now),
        ("Account", 3, "warning", "FinPulse Storage Capacity Warning", "Storage consumption at 1,850 GB of 2,000 GB allocation (92.5%).", 0, now),
        ("Account", 6, "warning", "Strata Security API Quota Alert", "API usage at 785,000 of 800,000 monthly calls (98.1%).", 0, now)
    ]

    cursor.executemany("""
    INSERT INTO capacity_alerts (entity_type, entity_id, severity, title, message, resolved, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?);
    """, alerts_data)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
