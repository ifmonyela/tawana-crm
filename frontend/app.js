// Tawana CRM Capacity Management Engine Frontend Controller
let repCapacityChart = null;
let pipelineStagesChart = null;
let currentTab = 'dashboard';
let cachedData = {
  reps: [],
  deals: [],
  accounts: [],
  alerts: [],
  stats: null
};

document.addEventListener('DOMContentLoaded', () => {
  initApp();
});

async function initApp() {
  await fetchFreshData();
  runInfrastructureSizing();
  // Auto-refresh periodically every 30 seconds
  setInterval(fetchFreshData, 30000);
}

// ----------------- TAB NAVIGATION -----------------

function switchTab(tabId) {
  currentTab = tabId;
  const tabs = ['dashboard', 'capacity', 'deals', 'accounts', 'infrastructure', 'alerts'];
  tabs.forEach(t => {
    const el = document.getElementById(`tab-${t}`);
    const navEl = document.getElementById(`nav-${t}`);
    if (el) el.classList.toggle('hidden', t !== tabId);
    if (navEl) {
      if (t === tabId) {
        navEl.classList.add('bg-slate-800', 'text-white', 'font-semibold');
        navEl.classList.remove('text-slate-300');
      } else {
        navEl.classList.remove('bg-slate-800', 'text-white', 'font-semibold');
        navEl.classList.add('text-slate-300');
      }
    }
  });

  const titles = {
    dashboard: 'Executive Dashboard',
    capacity: 'Sales Rep Capacity & Bandwidth Planner',
    deals: 'Deals & Opportunities Pipeline',
    accounts: 'Accounts & Customer Quota Monitor',
    infrastructure: 'System Capacity Sizer & Load Lab',
    alerts: 'Capacity Incidents & Alerts'
  };
  const titleEl = document.getElementById('page-title');
  if (titleEl) titleEl.innerText = titles[tabId] || 'Tawana CRM';

  if (tabId === 'dashboard') {
    renderCharts();
  }
}

// ----------------- DATA FETCHING -----------------

async function fetchFreshData() {
  try {
    const [statsRes, repsRes, dealsRes, accountsRes, alertsRes] = await Promise.all([
      fetch('/api/dashboard/stats').then(r => r.json()),
      fetch('/api/reps').then(r => r.json()),
      fetch('/api/deals').then(r => r.json()),
      fetch('/api/accounts').then(r => r.json()),
      fetch('/api/capacity/alerts').then(r => r.json())
    ]);

    cachedData.stats = statsRes;
    cachedData.reps = repsRes;
    cachedData.deals = dealsRes;
    cachedData.accounts = accountsRes;
    cachedData.alerts = alertsRes;

    renderDashboard(statsRes);
    renderRepCapacityPlanner(repsRes);
    renderKanbanDeals(dealsRes);
    renderAccountsTable(accountsRes);
    renderAlerts(alertsRes);
    populateSelectDropdowns();
  } catch (err) {
    console.error('Failed to load CRM data:', err);
  }
}

// ----------------- 1. DASHBOARD VIEW -----------------

function renderDashboard(data) {
  if (!data) return;

  // KPIs
  document.getElementById('kpi-total-pipeline').innerText = `$${(data.pipeline.total_pipeline_value).toLocaleString()}`;
  document.getElementById('kpi-weighted-pipeline').innerText = `$${(data.pipeline.weighted_pipeline_value).toLocaleString()}`;
  document.getElementById('kpi-active-deals-count').innerText = `${data.pipeline.active_deals} active deals`;
  document.getElementById('kpi-avg-utilization').innerText = `${data.capacity.average_utilization_pct}%`;
  document.getElementById('kpi-total-mrr').innerText = `$${(data.accounts.total_mrr).toLocaleString()}`;
  document.getElementById('kpi-accounts-near-cap').innerText = data.accounts.accounts_near_capacity;

  const overloadedReps = data.capacity.overloaded_reps;
  const overloadedText = document.getElementById('kpi-overloaded-reps-text');
  const repStatusBadge = document.getElementById('kpi-rep-status-badge');
  const rebalanceCallout = document.getElementById('rebalance-callout');
  const badgeOverloadedCount = document.getElementById('badge-overloaded-count');

  if (badgeOverloadedCount) {
    badgeOverloadedCount.innerText = `${overloadedReps} Alert${overloadedReps !== 1 ? 's' : ''}`;
    badgeOverloadedCount.className = overloadedReps > 0
      ? 'text-xs px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/30'
      : 'text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30';
  }

  if (overloadedReps > 0) {
    overloadedText.innerText = `${overloadedReps} rep${overloadedReps > 1 ? 's' : ''} over capacity limit`;
    repStatusBadge.innerText = 'Overloaded';
    repStatusBadge.className = 'text-[11px] font-semibold px-2 py-0.5 rounded bg-rose-500/20 text-rose-300';
    if (rebalanceCallout) rebalanceCallout.classList.remove('hidden');
  } else {
    overloadedText.innerText = 'All reps within healthy capacity (<85%)';
    repStatusBadge.innerText = 'Optimal';
    repStatusBadge.className = 'text-[11px] font-semibold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300';
    if (rebalanceCallout) rebalanceCallout.classList.add('hidden');
  }

  // Activity Feed
  const feedList = document.getElementById('activity-feed-list');
  if (feedList) {
    feedList.innerHTML = (data.recent_activities || []).map(act => {
      let iconColor = 'bg-indigo-500/20 text-indigo-400';
      if (act.action_type.includes('CAPACITY') || act.action_type.includes('WARNING')) iconColor = 'bg-rose-500/20 text-rose-400';
      if (act.action_type.includes('REBALANCE')) iconColor = 'bg-teal-500/20 text-teal-300';

      const timeStr = act.timestamp ? new Date(act.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';

      return `
        <div class="flex items-start gap-3 p-2.5 rounded-xl bg-slate-900/60 border border-slate-800/80 text-xs">
          <div class="p-1.5 rounded-lg ${iconColor} shrink-0 mt-0.5">
            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
          </div>
          <div class="flex-1">
            <p class="text-slate-200 font-medium">${act.message}</p>
            <span class="text-[10px] text-slate-500">${timeStr}</span>
          </div>
        </div>
      `;
    }).join('');
  }

  renderCharts();
}

// ----------------- CHART.JS VISUALIZATIONS -----------------

function renderCharts() {
  if (!cachedData.reps || cachedData.reps.length === 0) return;

  // 1. Rep Workload Capacity Stacked Bar Chart
  const repCtx = document.getElementById('chart-rep-capacity');
  if (repCtx) {
    const labels = cachedData.reps.map(r => r.name.split(' ')[0]);
    const usedPoints = cachedData.reps.map(r => r.current_load_points);
    const headroomPoints = cachedData.reps.map(r => Math.max(0, r.max_capacity_points - r.current_load_points));
    const colors = cachedData.reps.map(r => {
      if (r.capacity_status === 'Overloaded') return 'rgba(244, 63, 94, 0.85)';
      if (r.capacity_status === 'Near Capacity') return 'rgba(251, 146, 60, 0.85)';
      return 'rgba(20, 184, 166, 0.85)';
    });

    if (repCapacityChart) repCapacityChart.destroy();

    repCapacityChart = new Chart(repCtx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Assigned Effort Points',
            data: usedPoints,
            backgroundColor: colors,
            borderRadius: 6
          },
          {
            label: 'Available Headroom',
            data: headroomPoints,
            backgroundColor: 'rgba(51, 65, 85, 0.4)',
            borderRadius: 6
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { stacked: true, grid: { color: 'rgba(51, 65, 85, 0.2)' }, ticks: { color: '#94a3b8' } },
          y: { stacked: true, grid: { color: 'rgba(51, 65, 85, 0.2)' }, ticks: { color: '#94a3b8' } }
        },
        plugins: {
          legend: { labels: { color: '#cbd5e1', font: { size: 11 } } },
          tooltip: {
            callbacks: {
              afterLabel: function(ctx) {
                const rep = cachedData.reps[ctx.dataIndex];
                return `Utilization: ${rep.utilization_pct}% (${rep.capacity_status})`;
              }
            }
          }
        }
      }
    });
  }

  // 2. Pipeline Stages Chart
  const pipeCtx = document.getElementById('chart-pipeline-stages');
  if (pipeCtx && cachedData.deals) {
    const stages = ['Lead', 'Qualified', 'Proposal', 'Negotiation', 'Closed Won'];
    const stageValues = stages.map(st => {
      return cachedData.deals
        .filter(d => d.stage === st)
        .reduce((sum, d) => sum + d.amount, 0);
    });

    if (pipelineStagesChart) pipelineStagesChart.destroy();

    pipelineStagesChart = new Chart(pipeCtx, {
      type: 'bar',
      data: {
        labels: stages,
        datasets: [{
          label: 'Pipeline Value ($)',
          data: stageValues,
          backgroundColor: [
            'rgba(148, 163, 184, 0.7)',
            'rgba(99, 102, 241, 0.75)',
            'rgba(20, 184, 166, 0.75)',
            'rgba(245, 158, 11, 0.75)',
            'rgba(16, 185, 129, 0.75)'
          ],
          borderColor: [
            '#94a3b8',
            '#6366f1',
            '#14b8a6',
            '#f59e0b',
            '#10b981'
          ],
          borderWidth: 1.5,
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { grid: { color: 'rgba(51, 65, 85, 0.2)' }, ticks: { color: '#94a3b8' } },
          y: { grid: { color: 'rgba(51, 65, 85, 0.2)' }, ticks: { color: '#94a3b8' } }
        },
        plugins: {
          legend: { display: false }
        }
      }
    });
  }
}

// ----------------- 2. REP CAPACITY PLANNER VIEW -----------------

function renderRepCapacityPlanner(reps) {
  const grid = document.getElementById('reps-grid');
  if (!grid) return;

  grid.innerHTML = reps.map(r => {
    let statusClass = 'bg-teal-500/10 text-teal-300 border-teal-500/30';
    let progressBg = 'bg-teal-500';
    if (r.capacity_status === 'Overloaded') {
      statusClass = 'bg-rose-500/20 text-rose-300 border-rose-500/40';
      progressBg = 'bg-rose-500';
    } else if (r.capacity_status === 'Near Capacity') {
      statusClass = 'bg-amber-500/20 text-amber-300 border-amber-500/40';
      progressBg = 'bg-amber-500';
    }

    const quotaPct = Math.min(100, Math.round((r.closed_won_revenue / r.target_quota) * 100));

    return `
      <div class="glass-card rounded-2xl p-5 border border-slate-800 glass-card-hover transition">
        <div class="flex items-start justify-between mb-4">
          <div class="flex items-center gap-3">
            <img src="${r.avatar_url || 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=150'}" alt="${r.name}" class="w-11 h-11 rounded-full object-cover border-2 border-slate-700">
            <div>
              <h3 class="text-sm font-bold text-white">${r.name}</h3>
              <p class="text-[11px] text-slate-400">${r.role} &bull; <span class="text-indigo-400 font-medium">${r.department}</span></p>
            </div>
          </div>
          <span class="text-[11px] px-2.5 py-1 rounded-full border font-semibold ${statusClass}">${r.capacity_status}</span>
        </div>

        <!-- Workload Meter -->
        <div class="space-y-2 mb-4 bg-slate-900/60 p-3.5 rounded-xl border border-slate-800/80">
          <div class="flex justify-between text-xs">
            <span class="text-slate-400 font-medium">Workload Utilization</span>
            <span class="font-bold text-white font-mono">${r.current_load_points} / ${r.max_capacity_points} pts (${r.utilization_pct}%)</span>
          </div>
          <div class="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden">
            <div class="${progressBg} h-2.5 rounded-full transition-all duration-500" style="width: ${Math.min(100, r.utilization_pct)}%"></div>
          </div>
          <div class="flex justify-between text-[11px] text-slate-500">
            <span>Active Deals: <b class="text-slate-300">${r.active_deals_count}</b></span>
            <span>Headroom: <b class="${r.available_headroom > 3 ? 'text-teal-400' : 'text-rose-400'}">${r.available_headroom} pts</b></span>
          </div>
        </div>

        <!-- Quota Progress -->
        <div class="space-y-1.5 text-xs">
          <div class="flex justify-between text-slate-400 text-[11px]">
            <span>Closed Won: $${(r.closed_won_revenue).toLocaleString()}</span>
            <span>Target: $${(r.target_quota).toLocaleString()}</span>
          </div>
          <div class="w-full bg-slate-800 rounded-full h-1.5">
            <div class="bg-indigo-500 h-1.5 rounded-full" style="width: ${quotaPct}%"></div>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

// ----------------- CAPACITY REBALANCING -----------------

async function triggerQuickRebalance() {
  try {
    const res = await fetch('/api/capacity/rebalance', { method: 'POST' }).then(r => r.json());
    const box = document.getElementById('rebalance-result-box');
    if (box) {
      box.classList.remove('hidden');
      if (res.status === 'success' && res.reassigned_deals.length > 0) {
        box.innerHTML = `
          <div class="font-bold text-teal-300 mb-1 flex items-center gap-1.5">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
            ${res.message}
          </div>
          <div class="space-y-1 mt-2">
            ${res.reassigned_deals.map(d => `
              <div class="text-[11px] bg-teal-950/80 p-2 rounded border border-teal-500/20">
                Transferred <b>${d.deal_name}</b> (${d.points} pts) from <span class="text-rose-300 font-semibold">${d.from_rep}</span> &rarr; <span class="text-emerald-300 font-semibold">${d.to_rep}</span>
              </div>
            `).join('')}
          </div>
        `;
      } else {
        box.innerHTML = `<span class="text-teal-300 font-medium">${res.message}</span>`;
      }
    }
    // Refresh all state
    await fetchFreshData();
  } catch (err) {
    alert('Rebalance error: ' + err.message);
  }
}

// ----------------- 3. DEALS & PIPELINE KANBAN -----------------

function renderKanbanDeals(deals) {
  const stages = [
    { key: 'Lead', colId: 'col-stage-lead', countId: 'count-stage-lead' },
    { key: 'Qualified', colId: 'col-stage-qualified', countId: 'count-stage-qualified' },
    { key: 'Proposal', colId: 'col-stage-proposal', countId: 'count-stage-proposal' },
    { key: 'Negotiation', colId: 'col-stage-negotiation', countId: 'count-stage-negotiation' },
    { key: 'Closed Won', colId: 'col-stage-won', countId: 'count-stage-won' }
  ];

  stages.forEach(s => {
    const stageDeals = deals.filter(d => d.stage === s.key);
    const countEl = document.getElementById(s.countId);
    const colEl = document.getElementById(s.colId);
    if (countEl) countEl.innerText = stageDeals.length;

    if (colEl) {
      if (stageDeals.length === 0) {
        colEl.innerHTML = `<div class="p-4 rounded-lg border border-dashed border-slate-800 text-center text-slate-500 text-xs italic">No deals in stage</div>`;
      } else {
        colEl.innerHTML = stageDeals.map(d => {
          return `
            <div class="p-3.5 rounded-xl bg-slate-900 border border-slate-800 hover:border-indigo-500/50 transition shadow-sm space-y-2.5">
              <div class="flex items-start justify-between gap-2">
                <h4 class="text-xs font-bold text-white line-clamp-1">${d.name}</h4>
                <span class="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 shrink-0">
                  ⚡ ${d.effort_points} pts
                </span>
              </div>

              <div class="text-[11px] text-slate-400 flex items-center justify-between">
                <span>${d.account_name || 'Account #' + d.account_id}</span>
                <span class="font-bold text-white text-xs">$${(d.amount).toLocaleString()}</span>
              </div>

              <div class="pt-2 border-t border-slate-800 flex items-center justify-between text-[11px]">
                <div class="flex items-center gap-1.5">
                  <span class="w-5 h-5 rounded-full bg-slate-700 text-slate-200 text-[10px] flex items-center justify-center font-bold">
                    ${(d.assigned_rep_name || 'U').charAt(0)}
                  </span>
                  <span class="text-slate-300 truncate max-w-[80px]">${d.assigned_rep_name || 'Unassigned'}</span>
                </div>

                <!-- Advance Action Button -->
                ${getNextStage(d.stage) ? `
                  <button onclick="advanceDealStage(${d.id}, '${getNextStage(d.stage)}')" title="Advance to ${getNextStage(d.stage)}" class="p-1 hover:bg-slate-800 text-slate-400 hover:text-teal-400 rounded transition">
                    <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3" /></svg>
                  </button>
                ` : '<span class="text-[10px] text-emerald-400 font-semibold">&check; Won</span>'}
              </div>
            </div>
          `;
        }).join('');
      }
    }
  });
}

function getNextStage(current) {
  const flow = {
    'Lead': 'Qualified',
    'Qualified': 'Proposal',
    'Proposal': 'Negotiation',
    'Negotiation': 'Closed Won'
  };
  return flow[current] || null;
}

async function advanceDealStage(dealId, nextStage) {
  try {
    await fetch(`/api/deals/${dealId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ stage: nextStage })
    });
    await fetchFreshData();
  } catch (err) {
    alert('Error moving deal: ' + err.message);
  }
}

// ----------------- 4. ACCOUNTS & QUOTAS VIEW -----------------

function renderAccountsTable(accounts) {
  const tbody = document.getElementById('accounts-table-body');
  if (!tbody) return;

  const quotaBadge = document.getElementById('badge-account-quota');
  const nearCapCount = accounts.filter(a => a.is_near_capacity).length;
  if (quotaBadge) {
    quotaBadge.innerText = `${nearCapCount} Near Limit`;
    quotaBadge.className = nearCapCount > 0
      ? 'text-xs px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30'
      : 'text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30';
  }

  tbody.innerHTML = accounts.map(a => {
    let tierBadge = 'bg-slate-800 text-slate-300';
    if (a.tier === 'Enterprise') tierBadge = 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30';
    if (a.tier === 'Mid-Market') tierBadge = 'bg-teal-500/20 text-teal-300 border border-teal-500/30';

    let statusChip = '<span class="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400">Within Quota</span>';
    if (a.is_near_capacity) {
      statusChip = '<span class="px-2 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/40 font-semibold animate-pulse">&uarr; Upsell Alert</span>';
    }

    return `
      <tr class="hover:bg-slate-900/60 transition">
        <td class="px-5 py-3">
          <div class="font-bold text-white text-xs">${a.name}</div>
          <div class="text-[11px] text-slate-400">${a.domain}</div>
        </td>
        <td class="px-4 py-3"><span class="px-2 py-0.5 rounded text-[10px] font-semibold ${tierBadge}">${a.tier}</span></td>
        <td class="px-4 py-3 font-mono font-bold text-slate-200 text-xs">$${(a.mrr).toLocaleString()}</td>
        <td class="px-4 py-3">
          <span class="font-bold ${a.health_score > 80 ? 'text-emerald-400' : 'text-amber-400'}">${a.health_score}</span> / 100
        </td>
        <td class="px-4 py-3">
          <div class="text-[11px] text-slate-300 font-mono">${a.seats_used} / ${a.seats_limit} (${a.seats_utilization_pct}%)</div>
          <div class="w-20 bg-slate-800 rounded-full h-1.5 mt-1">
            <div class="${a.seats_utilization_pct > 85 ? 'bg-amber-400' : 'bg-teal-400'} h-1.5 rounded-full" style="width: ${Math.min(100, a.seats_utilization_pct)}%"></div>
          </div>
        </td>
        <td class="px-4 py-3">
          <div class="text-[11px] text-slate-300 font-mono">${(a.api_calls_used / 1000).toFixed(0)}k / ${(a.api_calls_limit / 1000).toFixed(0)}k (${a.api_calls_utilization_pct}%)</div>
          <div class="w-20 bg-slate-800 rounded-full h-1.5 mt-1">
            <div class="${a.api_calls_utilization_pct > 85 ? 'bg-amber-400' : 'bg-indigo-400'} h-1.5 rounded-full" style="width: ${Math.min(100, a.api_calls_utilization_pct)}%"></div>
          </div>
        </td>
        <td class="px-4 py-3">
          <div class="text-[11px] text-slate-300 font-mono">${a.storage_gb_used} / ${a.storage_gb_limit} GB (${a.storage_gb_utilization_pct}%)</div>
          <div class="w-20 bg-slate-800 rounded-full h-1.5 mt-1">
            <div class="${a.storage_gb_utilization_pct > 85 ? 'bg-amber-400' : 'bg-cyan-400'} h-1.5 rounded-full" style="width: ${Math.min(100, a.storage_gb_utilization_pct)}%"></div>
          </div>
        </td>
        <td class="px-4 py-3">${statusChip}</td>
        <td class="px-4 py-3 text-right">
          <button onclick="simulateAccountUsage(${a.id})" title="Simulate client usage increase" class="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-[11px] transition">
            + Surge Usage
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

async function simulateAccountUsage(accountId) {
  try {
    await fetch(`/api/accounts/${accountId}/usage?seats_delta=4&api_delta=35000&storage_delta_gb=25.0`, { method: 'PUT' });
    await fetchFreshData();
  } catch (err) {
    alert('Failed to simulate usage surge: ' + err.message);
  }
}

// ----------------- 5. INFRASTRUCTURE CAPACITY SIZER -----------------

let sizingTimeout = null;
function runInfrastructureSizing() {
  clearTimeout(sizingTimeout);
  sizingTimeout = setTimeout(async () => {
    const reps = parseInt(document.getElementById('input-reps').value);
    const leads = parseInt(document.getElementById('input-leads').value);
    const integrations = parseInt(document.getElementById('input-integrations').value);
    const retention = parseInt(document.getElementById('input-retention').value);
    const multiplier = parseFloat(document.getElementById('input-multiplier').value);

    document.getElementById('lbl-reps').innerText = reps.toLocaleString();
    document.getElementById('lbl-leads').innerText = leads.toLocaleString();
    document.getElementById('lbl-integrations').innerText = integrations;
    document.getElementById('lbl-retention').innerText = `${retention} Year${retention > 1 ? 's' : ''}`;
    document.getElementById('lbl-multiplier').innerText = `${multiplier}x`;

    try {
      const res = await fetch('/api/capacity/infrastructure/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          active_sales_reps: reps,
          inbound_leads_per_day: leads,
          api_integrations_count: integrations,
          data_retention_years: retention,
          peak_traffic_multiplier: multiplier
        })
      }).then(r => r.json());

      document.getElementById('out-peak-qps').innerText = res.metrics.peak_qps.toLocaleString();
      document.getElementById('out-total-iops').innerText = res.metrics.total_iops_required.toLocaleString();
      document.getElementById('out-storage-gb').innerText = `${res.storage_breakdown.multi_year_total_storage_gb.toLocaleString()} GB`;
      document.getElementById('out-redis-ram').innerText = `${res.caching_and_queue.recommended_redis_ram_gb} GB`;
      document.getElementById('out-compute-nodes').innerText = `${res.compute_recommendation.recommended_app_instances} Nodes`;
      document.getElementById('out-cloud-cost').innerText = `$${res.estimated_monthly_cost_usd.toLocaleString()}`;
      document.getElementById('sizing-sharding-badge').innerText = res.sharding_recommendation.split(' ')[0] + ' ' + (res.sharding_recommendation.split(' ')[1] || '');
      document.getElementById('out-topology-text').innerText = res.sharding_recommendation;

      document.getElementById('cost-db').innerText = `$${res.cost_breakdown.database_rds_usd.toLocaleString()}`;
      document.getElementById('cost-compute').innerText = `$${res.cost_breakdown.app_compute_usd.toLocaleString()}`;
      document.getElementById('cost-redis').innerText = `$${res.cost_breakdown.redis_cache_usd.toLocaleString()}`;
      document.getElementById('cost-queue').innerText = `$${res.cost_breakdown.message_queue_usd.toLocaleString()}`;
    } catch (err) {
      console.error('Sizing calculation failed:', err);
    }
  }, 120);
}

// ----------------- LIVE STRESS TESTING LAB -----------------

async function runLiveStressTest() {
  const btn = document.getElementById('btn-run-stress');
  const banner = document.getElementById('stress-status-banner');
  btn.disabled = true;
  btn.innerHTML = `
    <svg class="animate-spin w-4 h-4 text-white" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
    <span>Simulating High Ingestion Surge...</span>
  `;

  try {
    const res = await fetch('/api/capacity/simulator/stress-test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        total_events: 500,
        concurrency_workers: 10,
        rate_limit_capacity: 180,
        rate_limit_refill_per_sec: 140
      })
    }).then(r => r.json());

    document.getElementById('stress-sent').innerText = res.total_events_sent;
    document.getElementById('stress-processed').innerText = res.events_processed;
    document.getElementById('stress-throttled').innerText = res.events_throttled;
    document.getElementById('stress-p50').innerText = `${res.p50_latency_ms} ms`;
    document.getElementById('stress-p99').innerText = `${res.p99_latency_ms} ms`;
    document.getElementById('stress-eps').innerText = `${res.effective_throughput_eps} EPS`;

    if (banner) {
      banner.classList.remove('hidden');
      banner.className = 'p-3.5 rounded-xl text-xs font-medium flex items-center gap-2 ' +
        (res.events_throttled > 0 ? 'bg-amber-950/70 border border-amber-500/40 text-amber-200' : 'bg-emerald-950/70 border border-emerald-500/40 text-emerald-200');
      banner.innerHTML = `
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
        <span><b>Backpressure Telemetry:</b> ${res.backpressure_status}. Executed in ${res.total_duration_sec}s with Token Bucket throttling.</span>
      `;
    }
  } catch (err) {
    alert('Stress test failed: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `
      <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
      <span>Dispatch 500-Event Surge</span>
    `;
  }
}

// ----------------- 6. ALERTS VIEW -----------------

function renderAlerts(alerts) {
  const container = document.getElementById('alerts-container');
  const countBadge = document.getElementById('alerts-count-badge');
  const unresolved = alerts.filter(a => !a.resolved);

  if (countBadge) countBadge.innerText = unresolved.length;

  if (container) {
    if (alerts.length === 0) {
      container.innerHTML = `<div class="p-8 text-center text-slate-500 text-xs">No active capacity alerts. All systems running optimally.</div>`;
      return;
    }

    container.innerHTML = alerts.map(a => {
      let sevBg = 'bg-slate-900/60 border-slate-800 text-slate-300';
      if (!a.resolved) {
        if (a.severity === 'critical') sevBg = 'bg-rose-950/40 border-rose-500/40 text-rose-200';
        else if (a.severity === 'warning') sevBg = 'bg-amber-950/40 border-amber-500/40 text-amber-200';
      }

      return `
        <div class="p-4 rounded-xl border flex items-center justify-between gap-4 ${sevBg}">
          <div class="space-y-1">
            <div class="flex items-center gap-2">
              <span class="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-black/40 font-mono">${a.entity_type}</span>
              <h4 class="text-xs font-bold">${a.title}</h4>
              ${a.resolved ? '<span class="text-[10px] text-emerald-400 font-medium bg-emerald-500/10 px-1.5 py-0.5 rounded">&check; Resolved</span>' : ''}
            </div>
            <p class="text-xs text-slate-300">${a.message}</p>
          </div>
          ${!a.resolved ? `
            <button onclick="resolveAlert(${a.id})" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold shrink-0 transition">
              Resolve
            </button>
          ` : ''}
        </div>
      `;
    }).join('');
  }
}

async function resolveAlert(alertId) {
  try {
    await fetch(`/api/capacity/alerts/${alertId}/resolve`, { method: 'POST' });
    await fetchFreshData();
  } catch (err) {
    alert('Failed to resolve alert: ' + err.message);
  }
}

// ----------------- MODALS & SUBMISSIONS -----------------

function openNewDealModal() {
  document.getElementById('modal-deal').classList.remove('hidden');
}

function openNewAccountModal() {
  document.getElementById('modal-account').classList.remove('hidden');
}

function closeModal(modalId) {
  document.getElementById(modalId).classList.add('hidden');
}

function populateSelectDropdowns() {
  // Accounts dropdown for new deal
  const accSelect = document.getElementById('deal-select-account');
  if (accSelect && cachedData.accounts) {
    accSelect.innerHTML = cachedData.accounts.map(a => `<option value="${a.id}">${a.name} (${a.tier})</option>`).join('');
  }

  // Reps dropdown for new deal
  const repSelect = document.getElementById('deal-select-rep');
  if (repSelect && cachedData.reps) {
    let opts = '<option value="">⚡ Auto-Assign (Smart Capacity Matching)</option>';
    opts += cachedData.reps.map(r => `
      <option value="${r.id}">${r.name} - ${r.current_load_points}/${r.max_capacity_points} pts (${r.available_headroom} headroom)</option>
    `).join('');
    repSelect.innerHTML = opts;
  }
}

async function submitNewDeal(e) {
  e.preventDefault();
  const name = document.getElementById('deal-input-name').value;
  const account_id = parseInt(document.getElementById('deal-select-account').value);
  const amount = parseFloat(document.getElementById('deal-input-amount').value);
  const stage = document.getElementById('deal-select-stage').value;
  const effort_points = parseInt(document.getElementById('deal-select-effort').value);
  const repVal = document.getElementById('deal-select-rep').value;
  const assigned_rep_id = repVal ? parseInt(repVal) : null;

  try {
    const res = await fetch('/api/deals', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        account_id,
        name,
        amount,
        stage,
        effort_points,
        assigned_rep_id
      })
    }).then(r => r.json());

    closeModal('modal-deal');
    document.getElementById('form-add-deal').reset();
    await fetchFreshData();
    if (res.auto_assigned) {
      alert(`Deal automatically assigned based on sales capacity!`);
    }
  } catch (err) {
    alert('Error creating deal: ' + err.message);
  }
}

async function submitNewAccount(e) {
  e.preventDefault();
  const name = document.getElementById('acc-input-name').value;
  const domain = document.getElementById('acc-input-domain').value;
  const tier = document.getElementById('acc-select-tier').value;
  const mrr = parseFloat(document.getElementById('acc-input-mrr').value);
  const seats_limit = parseInt(document.getElementById('acc-input-seats').value);
  const api_calls_limit = parseInt(document.getElementById('acc-input-api').value);
  const storage_gb_limit = parseFloat(document.getElementById('acc-input-storage').value);

  try {
    await fetch('/api/accounts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        domain,
        tier,
        mrr,
        seats_limit,
        api_calls_limit,
        storage_gb_limit
      })
    });

    closeModal('modal-account');
    document.getElementById('form-add-account').reset();
    await fetchFreshData();
    switchTab('accounts');
  } catch (err) {
    alert('Error provisioning account: ' + err.message);
  }
}
