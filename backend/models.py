from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class RepBase(BaseModel):
    name: str
    email: str
    role: str = "Account Executive"
    department: str = "Enterprise"
    max_capacity_points: int = Field(default=25, ge=5, le=100)
    target_quota: float = Field(default=250000.0, ge=0)

class RepCreate(RepBase):
    avatar_url: Optional[str] = None

class RepUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    max_capacity_points: Optional[int] = None
    target_quota: Optional[float] = None

class RepResponse(RepBase):
    id: int
    current_load_points: int
    active_deals_count: int
    utilization_pct: float
    capacity_status: str  # 'Optimal', 'Near Capacity', 'Overloaded', 'Underutilized'
    closed_won_revenue: float
    avatar_url: Optional[str] = None

class DealBase(BaseModel):
    account_id: int
    name: str
    amount: float = Field(ge=0)
    stage: str = "Lead"  # 'Lead', 'Qualified', 'Proposal', 'Negotiation', 'Closed Won', 'Closed Lost'
    probability: int = Field(default=20, ge=0, le=100)
    effort_points: int = Field(default=3, ge=1, le=10, description="Capacity weight / complexity units")
    expected_close_date: Optional[str] = None

class DealCreate(DealBase):
    assigned_rep_id: Optional[int] = None  # If None, auto-assigned via capacity engine

class DealUpdate(BaseModel):
    account_id: Optional[int] = None
    name: Optional[str] = None
    amount: Optional[float] = None
    stage: Optional[str] = None
    probability: Optional[int] = None
    effort_points: Optional[int] = None
    assigned_rep_id: Optional[int] = None
    expected_close_date: Optional[str] = None

class DealResponse(DealBase):
    id: int
    assigned_rep_id: Optional[int] = None
    assigned_rep_name: Optional[str] = None
    account_name: Optional[str] = None
    created_at: str
    updated_at: str

class AccountBase(BaseModel):
    name: str
    domain: str
    industry: str = "Technology"
    tier: str = "Mid-Market"  # 'Startup', 'SMB', 'Mid-Market', 'Enterprise'
    health_score: int = Field(default=85, ge=0, le=100)
    mrr: float = Field(default=1500.0, ge=0)
    seats_limit: int = Field(default=25, ge=1)
    api_calls_limit: int = Field(default=100000, ge=1000)
    storage_gb_limit: int = Field(default=100, ge=5)

class AccountCreate(AccountBase):
    assigned_rep_id: Optional[int] = None

class AccountResponse(AccountBase):
    id: int
    assigned_rep_id: Optional[int] = None
    assigned_rep_name: Optional[str] = None
    seats_used: int
    seats_utilization_pct: float
    api_calls_used: int
    api_calls_utilization_pct: float
    storage_gb_used: float
    storage_gb_utilization_pct: float
    is_near_capacity: bool
    is_over_capacity: bool
    created_at: str

class ContactCreate(BaseModel):
    account_id: int
    name: str
    email: str
    phone: Optional[str] = None
    role: str = "Decision Maker"

class ContactResponse(BaseModel):
    id: int
    account_id: int
    account_name: Optional[str] = None
    name: str
    email: str
    phone: Optional[str] = None
    role: str
    created_at: str

class InfrastructureRequirementsRequest(BaseModel):
    active_sales_reps: int = Field(default=50, ge=1, le=50000)
    inbound_leads_per_day: int = Field(default=2500, ge=10, le=1000000)
    api_integrations_count: int = Field(default=8, ge=0, le=100)
    data_retention_years: int = Field(default=3, ge=1, le=10)
    peak_traffic_multiplier: float = Field(default=3.5, ge=1.0, le=10.0)

class InfrastructureRequirementsResponse(BaseModel):
    metrics: Dict[str, Any]
    storage_breakdown: Dict[str, Any]
    compute_recommendation: Dict[str, Any]
    caching_and_queue: Dict[str, Any]
    estimated_monthly_cost_usd: float
    sharding_recommendation: str

class StressTestRequest(BaseModel):
    total_events: int = Field(default=400, ge=50, le=2000)
    concurrency_workers: int = Field(default=8, ge=1, le=32)
    rate_limit_capacity: int = Field(default=150, ge=10, le=500)
    rate_limit_refill_per_sec: int = Field(default=100, ge=10, le=500)

class StressTestResponse(BaseModel):
    total_events_sent: int
    events_processed: int
    events_throttled: int
    events_queued: int
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    total_duration_sec: float
    effective_throughput_eps: float
    backpressure_status: str
