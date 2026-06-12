"""
app.py — Local Glycles dashboard.
Run: python app.py   →   open http://localhost:5000
"""
import os
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from flask import Flask, render_template_string, jsonify, request
from dotenv import load_dotenv
import db

load_dotenv()
db.init_db()
app = Flask(__name__)


def get_tz():
    tz_name = db.get_timezone()
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, Exception):
        return timezone.utc


def to_local(ts_str: str, tz) -> str:
    """Convert a UTC ISO string to local time ISO string."""
    try:
        # Treat stored timestamps as UTC
        dt = datetime.fromisoformat(ts_str).replace(tzinfo=timezone.utc)
        local_dt = dt.astimezone(tz)
        return local_dt.strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        return ts_str


def now_local(tz) -> datetime:
    return datetime.now(timezone.utc).astimezone(tz)


# ─── HTML ──────────────────────────────────────────────────────────────────────
HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Glycles — Local</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/chartjs-plugin-annotation/3.0.1/chartjs-plugin-annotation.min.js"></script>
<style>
:root{
  --bg:#0f1117;--bg2:#181c27;--bg3:#1e2235;
  --border:#2a2f45;--text:#e8eaf6;--muted:#7a8099;
  --red:#c0392b;--orange:#e67e22;--green:#27ae60;--purple:#8e44ad;
  --accent:#aa0a28;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:'Inter',system-ui,sans-serif;font-size:14px}
nav{background:var(--bg2);border-bottom:1px solid var(--border);padding:.75rem 1.5rem;
    display:flex;align-items:center;gap:1rem;flex-wrap:wrap}
nav h1{font-size:1rem;font-weight:700;letter-spacing:-.02em}
nav h1 span{color:var(--accent)}
.nav-right{margin-left:auto;display:flex;align-items:center;gap:1rem;flex-wrap:wrap}
.nav-status{font-size:.75rem;color:var(--muted)}
.nav-status b{color:var(--green)}
.tz-badge{font-size:.72rem;color:var(--muted);background:var(--bg3);
          border:1px solid var(--border);border-radius:6px;padding:.2rem .5rem}

.container{max-width:1200px;margin:0 auto;padding:1.5rem}
.status-bar{display:flex;gap:1rem;margin-bottom:1.5rem;flex-wrap:wrap}
.stat-card{background:var(--bg2);border:1px solid var(--border);border-radius:12px;
           padding:1rem 1.25rem;flex:1;min-width:140px}
.stat-card .label{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:.3rem}
.stat-card .value{font-size:1.6rem;font-weight:700}
.stat-card .sub{font-size:.75rem;color:var(--muted);margin-top:.2rem}

h2{font-size:.8rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
   color:var(--muted);margin-bottom:1rem;margin-top:1.75rem}

.chart-wrap{background:var(--bg2);border:1px solid var(--border);border-radius:12px;
            padding:1.25rem;margin-bottom:1.5rem}
.chart-wrap canvas{width:100%!important}

.phase-legend{display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:1rem}
.phase-pill{display:flex;align-items:center;gap:.4rem;font-size:.75rem;color:var(--muted)}
.phase-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}

.stats-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:1rem;margin-bottom:1.5rem}
.phase-stat{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:1rem}
.phase-stat .phase-name{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.6rem}
.phase-stat .metric{display:flex;justify-content:space-between;font-size:.8rem;
                     padding:.2rem 0;border-bottom:1px solid var(--border)}
.phase-stat .metric:last-child{border:none}
.phase-stat .metric span{color:var(--muted)}

/* Two-column panels */
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem}
@media(max-width:700px){.two-col{grid-template-columns:1fr}}

.panel{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:1.25rem}
.panel-title{font-size:.82rem;font-weight:600;margin-bottom:.85rem}

.form-row{display:flex;gap:.75rem;align-items:flex-end;flex-wrap:wrap;margin-bottom:.75rem}
.form-field{display:flex;flex-direction:column;gap:.3rem;flex:1;min-width:110px}
.form-field label{font-size:.72rem;color:var(--muted)}
input[type=date],input[type=number],input[type=text],select{
  background:var(--bg3);border:1px solid var(--border);border-radius:8px;
  padding:.5rem .75rem;color:var(--text);font-size:.85rem;outline:none;width:100%}
input:focus,select:focus{border-color:var(--accent)}
.btn{background:var(--accent);color:#fff;border:none;border-radius:8px;
     padding:.5rem 1rem;font-size:.82rem;font-weight:600;cursor:pointer;white-space:nowrap}
.btn:hover{opacity:.85}
.btn-sm{padding:.3rem .7rem;font-size:.75rem}
.btn-ghost{background:transparent;border:1px solid var(--border);color:var(--muted)}
.btn-ghost:hover{color:var(--text);border-color:var(--text)}

.scroll-list{display:flex;flex-direction:column;gap:.5rem;max-height:280px;overflow-y:auto}
.list-item{display:flex;justify-content:space-between;align-items:center;
           background:var(--bg3);border-radius:8px;padding:.6rem .85rem;font-size:.82rem}
.list-item .main{font-weight:600}
.list-item .meta{color:var(--muted);font-size:.75rem}
.del{color:#e74c3c;cursor:pointer;background:none;border:none;font-size:.85rem}
.del:hover{opacity:.7}
.empty{color:var(--muted);font-size:.82rem;padding:.5rem 0}

.days-selector{display:flex;gap:.5rem;margin-bottom:1rem;flex-wrap:wrap}
.days-btn{padding:.3rem .7rem;border-radius:6px;border:1px solid var(--border);
          background:transparent;color:var(--muted);font-size:.75rem;cursor:pointer}
.days-btn.active,.days-btn:hover{background:var(--accent);color:#fff;border-color:var(--accent)}

/* Upload zone */
.upload-zone{border:1.5px dashed var(--border);border-radius:10px;
             padding:1.25rem;text-align:center;color:var(--muted);
             font-size:.8rem;cursor:pointer;transition:.15s}
.upload-zone:hover{border-color:var(--accent);color:var(--text)}
.upload-result{margin-top:.5rem;font-size:.78rem;padding:.4rem .7rem;
               border-radius:6px;display:none}
.upload-result.ok{background:rgba(39,174,96,.15);color:#27ae60}
.upload-result.err{background:rgba(192,57,43,.15);color:#e74c3c}

#loading{color:var(--muted);padding:2rem;text-align:center}
</style>
</head>
<body>
<nav>
  <h1>gl<span>y</span>cles <span style="color:var(--muted);font-weight:400">local</span></h1>
  <div class="nav-right">
    <span class="tz-badge" id="tz-badge">UTC</span>
    <span class="nav-status" id="nav-status">Loading…</span>
  </div>
</nav>

<div class="container">
  <div id="loading">Loading data…</div>
  <div id="main" style="display:none">

    <div class="status-bar" id="status-cards"></div>

    <h2>Glucose timeline</h2>
    <div class="days-selector">
      <button class="days-btn active" onclick="setDays(1)">24h</button>
      <button class="days-btn" onclick="setDays(3)">3d</button>
      <button class="days-btn" onclick="setDays(7)">7d</button>
      <button class="days-btn" onclick="setDays(14)">14d</button>
      <button class="days-btn" onclick="setDays(30)">30d</button>
      <button class="days-btn" onclick="setDays(90)">90d</button>
    </div>
    <div class="phase-legend" id="phase-legend"></div>
    <div class="chart-wrap"><canvas id="timelineChart" height="110"></canvas></div>

    <h2>Stats by cycle phase</h2>
    <div class="stats-grid" id="stats-grid"></div>

    <h2>Trend across cycles</h2>
    <div class="chart-wrap"><canvas id="trendChart" height="80"></canvas></div>

    <h2>Import data</h2>
    <div class="two-col" style="margin-bottom:1.5rem">
      <div class="panel">
        <div class="panel-title">LibreView glucose CSV</div>
        <div class="upload-zone" onclick="document.getElementById('glucoseFile').click()">
          Click to select CSV export from libreview.com
        </div>
        <input type="file" id="glucoseFile" accept=".csv" style="display:none"
               onchange="uploadFile('glucose', this)">
        <div class="upload-result" id="glucoseResult"></div>
      </div>
      <div class="panel">
        <div class="panel-title">Period dates TXT</div>
        <div class="upload-zone" onclick="document.getElementById('periodFile').click()">
          Click to select periods.txt
          <div style="font-size:.72rem;margin-top:.3rem;color:var(--muted)">
            One date per line: 2024-01-15 or 2024-01-15 28 (date + cycle length)
          </div>
        </div>
        <input type="file" id="periodFile" accept=".txt,.csv" style="display:none"
               onchange="uploadFile('period', this)">
        <div class="upload-result" id="periodResult"></div>
      </div>
      <div class="panel">
        <div class="panel-title">Activity CSV</div>
        <div class="upload-zone" onclick="document.getElementById('activityFile').click()">
          Click to select activity.csv
          <div style="font-size:.72rem;margin-top:.3rem;color:var(--muted)">
            Columns: date, type, duration_min, intensity, notes
          </div>
        </div>
        <input type="file" id="activityFile" accept=".csv" style="display:none"
               onchange="uploadFile('activity', this)">
        <div class="upload-result" id="activityResult"></div>
      </div>
      <div class="panel">
        <div class="panel-title">Timezone</div>
        <div class="form-row">
          <div class="form-field">
            <label>Your local timezone</label>
            <input type="text" id="tzInput" placeholder="e.g. Europe/Berlin">
          </div>
          <button class="btn" onclick="setTimezone()">Save</button>
        </div>
        <div class="upload-result" id="tzResult"></div>
        <div style="font-size:.72rem;color:var(--muted);margin-top:.5rem">
          Current: <span id="tzCurrent">UTC</span><br>
          All times shown in this timezone.
        </div>
      </div>
    </div>

    <h2>Exclude bad readings</h2>
    <div class="panel" style="margin-bottom:1.5rem">
      <div style="font-size:.82rem;font-weight:600;margin-bottom:.5rem">Mark a time range as bad sensor / unreliable data</div>
      <div style="font-size:.75rem;color:var(--muted);margin-bottom:.85rem">
        Excluded readings are hidden from the chart and ignored in all stats. The raw data stays in the database — you can remove an exclusion any time to restore it.
      </div>
      <div class="form-row">
        <div class="form-field">
          <label>From (YYYY-MM-DD HH:MM)</label>
          <input type="text" id="excStart" placeholder="2026-05-20 00:00">
        </div>
        <div class="form-field">
          <label>To (YYYY-MM-DD HH:MM)</label>
          <input type="text" id="excEnd" placeholder="2026-05-21 00:00">
        </div>
        <div class="form-field">
          <label>Reason (optional)</label>
          <input type="text" id="excReason" placeholder="Sensor drift, compression, etc.">
        </div>
        <button class="btn" style="align-self:flex-end" onclick="addExclusion()">Exclude</button>
      </div>
      <div class="scroll-list" id="exclusion-list" style="max-height:200px;margin-top:.75rem"></div>
    </div>

    <h2>Manage data</h2>
    <div class="two-col">
      <div class="panel">
        <div class="panel-title">Add cycle date</div>
        <div class="form-row">
          <div class="form-field">
            <label>Period start</label>
            <input type="date" id="cycleDate">
          </div>
          <div class="form-field" style="max-width:100px">
            <label>Cycle length</label>
            <input type="number" id="cycleLen" value="28" min="20" max="45">
          </div>
        </div>
        <div class="form-row">
          <div class="form-field">
            <label>Notes (optional)</label>
            <input type="text" id="cycleNotes" placeholder="optional…">
          </div>
        </div>
        <button class="btn" onclick="addCycle()">Add cycle</button>
        <div style="margin-top:1rem"><div class="scroll-list" id="cycle-list"></div></div>
      </div>

      <div class="panel">
        <div class="panel-title">Add activity</div>
        <div class="form-row">
          <div class="form-field">
            <label>Date & time</label>
            <input type="text" id="actTs" placeholder="2024-01-15 08:00">
          </div>
          <div class="form-field">
            <label>Type</label>
            <input type="text" id="actType" placeholder="Running, Gym…">
          </div>
        </div>
        <div class="form-row">
          <div class="form-field" style="max-width:100px">
            <label>Duration (min)</label>
            <input type="number" id="actDur" placeholder="45">
          </div>
          <div class="form-field">
            <label>Intensity</label>
            <select id="actIntensity">
              <option value="">—</option>
              <option value="low">Low</option>
              <option value="moderate">Moderate</option>
              <option value="high">High</option>
            </select>
          </div>
        </div>
        <button class="btn" onclick="addActivity()">Add activity</button>
        <div style="margin-top:1rem"><div class="scroll-list" id="activity-list"></div></div>
      </div>
    </div>

  </div>
</div>

<script>
const PHASES = ['menstrual','follicular','ovulatory','luteal'];
const PHASE_COLORS = {
  menstrual:'#c0392b', follicular:'#e67e22', ovulatory:'#27ae60',
  luteal:'#8e44ad', unknown:'#7f8c8d'
};
let timelineChart = null, trendChart = null, currentDays = 1;

// ── Init ────────────────────────────────────────────────────────────
async function init() {
  await Promise.all([loadDashboard(), loadCycles(), loadActivities(), loadSettings(), loadExclusions()]);
  document.getElementById('loading').style.display = 'none';
  document.getElementById('main').style.display = 'block';
}

async function loadSettings() {
  const res = await fetch('/api/settings');
  const s = await res.json();
  const tz = s.timezone || 'UTC';
  document.getElementById('tz-badge').textContent = tz;
  document.getElementById('tzCurrent').textContent = tz;
  document.getElementById('tzInput').value = tz;
}

// ── Dashboard ──────────────────────────────────────────────────────
async function loadDashboard(days = currentDays) {
  currentDays = days;
  const res = await fetch(`/api/dashboard?days=${days}`);
  const d = await res.json();

  const ns = document.getElementById('nav-status');
  if (d.latest) {
    ns.innerHTML = `Latest: <b>${d.latest.value_mmol} mmol/L</b> &nbsp;·&nbsp; ${fmt(d.latest.ts_local)} &nbsp;·&nbsp; ${d.total_readings} readings`;
  } else {
    ns.innerHTML = `<span style="color:#e67e22">No data — is the poller running?</span>`;
  }

  renderStatusCards(d);
  renderTimeline(d.readings, d.activities);
  renderStats(d.phase_stats);
  renderTrend(d.cycle_trend);
}

// ── Status cards ──────────────────────────────────────────────────
function renderStatusCards(d) {
  const el = document.getElementById('status-cards');
  const l = d.latest;
  el.innerHTML = [
    { label:'Current glucose', value: l ? `${l.value_mmol}` : '—',
      sub: l ? `mmol/L · ${trendArrow(l.trend)}` : 'No data' },
    { label:'Total readings',  value: d.total_readings, sub:'in database' },
    { label:'Cycles logged',   value: d.cycles.length,  sub:'period start dates' },
    { label:'Time in range',   value: d.overall_tir ? `${d.overall_tir}%` : '—',
      sub:'3.9–10.0 mmol/L' },
  ].map(c => `<div class="stat-card">
    <div class="label">${c.label}</div>
    <div class="value">${c.value}</div>
    <div class="sub">${c.sub}</div>
  </div>`).join('');
}

// ── Timeline ───────────────────────────────────────────────────────
function renderTimeline(readings, activities) {
  const leg = document.getElementById('phase-legend');
  leg.innerHTML = Object.entries(PHASE_COLORS).filter(([p]) => p !== 'unknown')
    .map(([p,c]) => `<div class="phase-pill"><div class="phase-dot" style="background:${c}"></div>${p}</div>`).join('');

  const labels = readings.map(r => r.ts_local);
  const values = readings.map(r => r.value_mmol);
  const colors = readings.map(r => PHASE_COLORS[r.phase] || '#7f8c8d');

  // Activity annotations
  const annotations = {
    low:  { type:'line', yMin:3.9, yMax:3.9, borderColor:'rgba(231,76,60,.4)', borderWidth:1, borderDash:[4,4] },
    high: { type:'line', yMin:10,  yMax:10,  borderColor:'rgba(231,76,60,.4)', borderWidth:1, borderDash:[4,4] },
  };
  (activities || []).forEach((a, i) => {
    annotations[`act_${i}`] = {
      type: 'line',
      xMin: a.ts_local, xMax: a.ts_local,
      borderColor: 'rgba(255,255,255,.25)',
      borderWidth: 1,
      borderDash: [2,4],
      label: {
        display: true,
        content: `${a.type || 'Activity'}${a.duration_min ? ' '+a.duration_min+'m' : ''}`,
        color: '#fff',
        backgroundColor: 'rgba(30,34,53,.85)',
        font: { size: 10 },
        position: 'start',
      }
    };
  });

  const ctx = document.getElementById('timelineChart').getContext('2d');
  if (timelineChart) timelineChart.destroy();
  timelineChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        data: values,
        borderColor: '#aa0a28',
        borderWidth: 1.5,
        pointRadius: readings.length > 300 ? 0 : 3,
        pointBackgroundColor: colors,
        pointBorderColor: colors,
        tension: 0.3,
        fill: false,
      }]
    },
    options: {
      responsive: true, animation: false,
      plugins: {
        legend: { display: false },
        annotation: { annotations },
        tooltip: { callbacks: {
          title: ctx => fmt(ctx[0].label),
          label: ctx => {
            const r = readings[ctx.dataIndex];
            return `${ctx.raw} mmol/L · ${r.phase} · ${trendArrow(r.trend)}`;
          }
        }}
      },
      scales: {
        x: { ticks: { color:'#7a8099', maxTicksLimit:10,
                      callback:(v,i) => fmt(labels[i]).slice(0,10) },
             grid: { color:'rgba(255,255,255,.05)' } },
        y: { min:2, max:16,
             ticks: { color:'#7a8099' },
             grid: { color:'rgba(255,255,255,.05)' } }
      }
    }
  });
}

// ── Phase stats ───────────────────────────────────────────────────
function renderStats(stats) {
  const el = document.getElementById('stats-grid');
  if (!stats) { el.innerHTML = '<div class="empty">Add cycle dates to see phase stats.</div>'; return; }
  el.innerHTML = PHASES.map(phase => {
    const s = stats[phase];
    if (!s) return `<div class="phase-stat">
      <div class="phase-name" style="color:${PHASE_COLORS[phase]}">${phase}</div>
      <div class="empty">No data</div></div>`;
    return `<div class="phase-stat">
      <div class="phase-name" style="color:${PHASE_COLORS[phase]}">${phase}</div>
      <div class="metric"><span>Avg</span>${s.mean} mmol/L</div>
      <div class="metric"><span>Std dev</span>±${s.std}</div>
      <div class="metric"><span>Min / Max</span>${s.min} / ${s.max}</div>
      <div class="metric"><span>Time in range</span>${s.time_in_range_pct}%</div>
      <div class="metric"><span>Readings</span>${s.count}</div>
    </div>`;
  }).join('');
}

// ── Trend ─────────────────────────────────────────────────────────
function renderTrend(trend) {
  const ctx = document.getElementById('trendChart').getContext('2d');
  if (trendChart) trendChart.destroy();
  if (!trend || trend.length < 2) {
    ctx.canvas.parentElement.innerHTML = '<div style="color:var(--muted);padding:1rem;font-size:.82rem">Need at least 2 cycles with glucose data to show trend.</div>';
    return;
  }
  trendChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: trend.map(t => t.cycle_label),
      datasets: PHASES.map(phase => ({
        label: phase, data: trend.map(t => t[phase]),
        borderColor: PHASE_COLORS[phase],
        backgroundColor: PHASE_COLORS[phase] + '22',
        borderWidth:2, pointRadius:5, tension:0.3, spanGaps:true,
      }))
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color:'#7a8099', boxWidth:12 } } },
      scales: {
        x: { ticks:{color:'#7a8099'}, grid:{color:'rgba(255,255,255,.05)'} },
        y: { min:3, ticks:{color:'#7a8099'}, grid:{color:'rgba(255,255,255,.05)'},
             title:{display:true,text:'mmol/L',color:'#7a8099'} }
      }
    }
  });
}

// ── Cycles ────────────────────────────────────────────────────────
async function loadCycles() {
  const res = await fetch('/api/cycles');
  const cycles = await res.json();
  const el = document.getElementById('cycle-list');
  if (!cycles.length) { el.innerHTML = '<div class="empty">No cycles yet.</div>'; return; }
  el.innerHTML = cycles.map(c => `
    <div class="list-item">
      <div><div class="main">${c.period_start}</div>
           <div class="meta">${c.cycle_length}d${c.notes ? ' · '+c.notes : ''}</div></div>
      <button class="del" onclick="deleteCycle('${c.period_start}')">✕</button>
    </div>`).join('');
}

async function addCycle() {
  const d = document.getElementById('cycleDate').value;
  const l = parseInt(document.getElementById('cycleLen').value) || 28;
  const n = document.getElementById('cycleNotes').value;
  if (!d) { alert('Pick a date first.'); return; }
  await fetch('/api/cycles', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ period_start:d, cycle_length:l, notes:n }) });
  document.getElementById('cycleDate').value = '';
  document.getElementById('cycleNotes').value = '';
  await loadCycles(); await loadDashboard();
}

async function deleteCycle(ds) {
  if (!confirm(`Delete cycle starting ${ds}?`)) return;
  await fetch(`/api/cycles/${ds}`, { method:'DELETE' });
  await loadCycles(); await loadDashboard();
}

// ── Activities ────────────────────────────────────────────────────
async function loadActivities() {
  const res = await fetch('/api/activities');
  const acts = await res.json();
  const el = document.getElementById('activity-list');
  if (!acts.length) { el.innerHTML = '<div class="empty">No activities yet.</div>'; return; }
  el.innerHTML = acts.slice(0,30).map(a => `
    <div class="list-item">
      <div><div class="main">${a.type || '—'} ${a.duration_min ? a.duration_min+'min' : ''}</div>
           <div class="meta">${a.ts.slice(0,16)} ${a.intensity ? '· '+a.intensity : ''}</div></div>
      <button class="del" onclick="deleteActivity(${a.id})">✕</button>
    </div>`).join('');
}

async function addActivity() {
  const ts    = document.getElementById('actTs').value.trim();
  const type  = document.getElementById('actType').value.trim();
  const dur   = document.getElementById('actDur').value;
  const inten = document.getElementById('actIntensity').value;
  if (!ts || !type) { alert('Date/time and type are required.'); return; }
  await fetch('/api/activities', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ ts, type, duration_min: dur ? parseInt(dur) : null,
                           intensity: inten, notes:'' }) });
  document.getElementById('actTs').value = '';
  document.getElementById('actType').value = '';
  document.getElementById('actDur').value = '';
  await loadActivities(); await loadDashboard();
}

async function deleteActivity(id) {
  await fetch(`/api/activities/${id}`, { method:'DELETE' });
  await loadActivities(); await loadDashboard();
}

// ── File uploads ──────────────────────────────────────────────────
async function uploadFile(type, input) {
  const file = input.files[0];
  if (!file) return;
  const resultEl = document.getElementById(type + 'Result');
  resultEl.style.display = 'block';
  resultEl.className = 'upload-result';
  resultEl.textContent = 'Uploading…';

  const form = new FormData();
  form.append('file', file);
  try {
    const res = await fetch(`/api/import/${type}`, { method:'POST', body: form });
    const data = await res.json();
    if (data.ok) {
      resultEl.className = 'upload-result ok';
      resultEl.textContent = data.message;
      await loadDashboard(); await loadCycles(); await loadActivities();
    } else {
      resultEl.className = 'upload-result err';
      resultEl.textContent = data.error || 'Import failed';
    }
  } catch(e) {
    resultEl.className = 'upload-result err';
    resultEl.textContent = `Error: ${e.message}`;
  }
  input.value = '';
}

async function setTimezone() {
  const tz = document.getElementById('tzInput').value.trim();
  if (!tz) return;
  const res = await fetch('/api/settings/timezone', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ timezone: tz })
  });
  const data = await res.json();
  const el = document.getElementById('tzResult');
  el.style.display = 'block';
  if (data.ok) {
    el.className = 'upload-result ok';
    el.textContent = `Saved. Reload to apply.`;
    document.getElementById('tz-badge').textContent = tz;
    document.getElementById('tzCurrent').textContent = tz;
  } else {
    el.className = 'upload-result err';
    el.textContent = data.error || 'Unknown error';
  }
}

// ── Exclusions ────────────────────────────────────────────────────
async function loadExclusions() {
  const res = await fetch('/api/exclusions');
  const excs = await res.json();
  const el = document.getElementById('exclusion-list');
  if (!excs.length) {
    el.innerHTML = '<div class="empty">No exclusions — all readings are included.</div>';
    return;
  }
  el.innerHTML = excs.map(e => `
    <div class="list-item">
      <div>
        <div class="main">${fmt(e.start)} → ${fmt(e.end)}</div>
        <div class="meta">${e.reason || 'No reason given'}</div>
      </div>
      <button class="del" onclick="deleteExclusion(${e.id})">✕</button>
    </div>`).join('');
}

async function addExclusion() {
  let start  = document.getElementById('excStart').value.trim();
  let end    = document.getElementById('excEnd').value.trim();
  const reason = document.getElementById('excReason').value.trim();
  if (!start || !end) { alert('Start and end are required.'); return; }
  // Normalize: accept "YYYY-MM-DD HH:MM" or "YYYY-MM-DD"
  const norm = s => s.includes('T') ? s : s.replace(' ','T') + (s.length === 10 ? 'T00:00:00' : ':00');
  start = norm(start); end = norm(end);
  if (start >= end) { alert('End must be after start.'); return; }
  await fetch('/api/exclusions', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ start, end, reason }) });
  document.getElementById('excStart').value = '';
  document.getElementById('excEnd').value = '';
  document.getElementById('excReason').value = '';
  await loadExclusions();
  await loadDashboard();
}

async function deleteExclusion(id) {
  if (!confirm('Remove this exclusion? Those readings will be included again.')) return;
  await fetch(`/api/exclusions/${id}`, { method:'DELETE' });
  await loadExclusions();
  await loadDashboard();
}

// ── Days selector ─────────────────────────────────────────────────
function setDays(n) {
  currentDays = n;
  document.querySelectorAll('.days-btn').forEach((b,i) => {
    b.classList.toggle('active', [1,3,7,14,30,90][i] === n);
  });
  loadDashboard(n);
}

// ── Helpers ───────────────────────────────────────────────────────
function fmt(ts) {
  return ts ? ts.replace('T',' ').slice(0,16) : '—';
}
function trendArrow(t) {
  const a = ['↑↑','↑↑','↑','↗','→','↘','↓','↓↓'];
  return (t!=null && a[t]) ? a[t] : '—';
}

setInterval(() => loadDashboard(currentDays), 5*60*1000);
init();
</script>
</body>
</html>
"""

# ─── API ───────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/settings")
def api_settings():
    return jsonify({"timezone": db.get_timezone()})


@app.route("/api/settings/timezone", methods=["POST"])
def api_set_timezone():
    data = request.get_json()
    tz_name = data.get("timezone", "UTC").strip()
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(tz_name)  # validate
        db.set_setting("timezone", tz_name)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": f"Invalid timezone: {tz_name}. Try 'Europe/Berlin'"})


@app.route("/api/dashboard")
def api_dashboard():
    tz = get_tz()
    days = int(request.args.get("days", 1))

    # Calculate start in local time, convert to UTC-equivalent ISO for DB query
    local_now = now_local(tz)
    local_start = local_now - timedelta(days=days)
    # Since DB stores UTC, shift query window by tz offset
    utc_offset = local_now.utcoffset().total_seconds() / 3600 if local_now.utcoffset() else 0
    start_utc = (local_start.replace(tzinfo=None) - timedelta(hours=utc_offset)).strftime("%Y-%m-%dT%H:%M:%S")

    readings     = db.get_readings(start=start_utc)
    all_readings = db.get_readings()
    cycles       = db.get_cycles()
    activities   = db.get_activities(start=start_utc)
    latest_raw   = db.get_latest_reading()
    total        = db.get_reading_count()

    # Apply exclusions — remove bad sensor periods from charts and stats
    readings     = db.filter_excluded(readings)
    all_readings = db.filter_excluded(all_readings)

    # Convert timestamps to local time
    def localize(r):
        r = dict(r)
        r["ts_local"] = to_local(r["ts"], tz)
        return r

    readings     = [localize(r) for r in readings]
    all_readings = [localize(r) for r in all_readings]
    activities   = [localize(a) for a in activities]
    latest       = localize(latest_raw) if latest_raw else None

    # Annotate phases using local date
    def annotate(r):
        d = date.fromisoformat(r["ts_local"][:10])
        phase = db.get_phase_for_date(d, cycles)
        r["phase"]       = phase
        r["phase_color"] = db.PHASE_COLORS[phase]
        return r

    readings     = [annotate(r) for r in readings]
    all_annotated = [annotate(r) for r in all_readings]

    in_range    = [r for r in all_annotated if 3.9 <= r["value_mmol"] <= 10.0]
    overall_tir = round(len(in_range) / len(all_annotated) * 100, 1) if all_annotated else None
    phase_stats = db.compute_phase_stats(all_annotated) if cycles else None
    cycle_trend = db.compute_cycle_trend(cycles, all_annotated) if cycles else []

    return jsonify({
        "readings":      readings,
        "activities":    activities,
        "cycles":        cycles,
        "latest":        latest,
        "total_readings": total,
        "phase_stats":   phase_stats,
        "cycle_trend":   cycle_trend,
        "overall_tir":   overall_tir,
        "timezone":      db.get_timezone(),
    })


@app.route("/api/cycles", methods=["GET"])
def api_get_cycles():
    return jsonify(db.get_cycles())


@app.route("/api/cycles", methods=["POST"])
def api_add_cycle():
    data = request.get_json()
    db.add_cycle(data["period_start"], int(data.get("cycle_length", 28)), data.get("notes", ""))
    return jsonify({"ok": True})


@app.route("/api/cycles/<date_str>", methods=["DELETE"])
def api_delete_cycle(date_str):
    db.delete_cycle(date_str)
    return jsonify({"ok": True})


@app.route("/api/activities", methods=["GET"])
def api_get_activities():
    return jsonify(db.get_activities())


@app.route("/api/activities", methods=["POST"])
def api_add_activity():
    data = request.get_json()
    raw_ts = data.get("ts", "").strip()
    # Normalize timestamp
    if "T" not in raw_ts and " " in raw_ts:
        raw_ts = raw_ts.replace(" ", "T")
    if len(raw_ts) == 10:
        raw_ts += "T00:00:00"
    db.add_activity(
        ts=raw_ts,
        act_type=data.get("type", ""),
        duration_min=data.get("duration_min"),
        intensity=data.get("intensity", ""),
        notes=data.get("notes", ""),
    )
    return jsonify({"ok": True})


@app.route("/api/activities/<int:act_id>", methods=["DELETE"])
def api_delete_activity(act_id):
    db.delete_activity(act_id)
    return jsonify({"ok": True})


@app.route("/api/import/<import_type>", methods=["POST"])
def api_import(import_type):
    import tempfile, importer as imp
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file provided"})
    file = request.files["file"]
    suffix = ".csv" if import_type != "period" else ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        file.save(tmp.name)
        path = tmp.name
    try:
        before = db.get_reading_count()
        if import_type == "glucose":
            imp.import_glucose_csv(path)
            after = db.get_reading_count()
            msg = f"Imported {after - before} new readings ({after} total)"
        elif import_type == "period":
            cycles_before = len(db.get_cycles())
            imp.import_period_txt(path)
            cycles_after = len(db.get_cycles())
            msg = f"Added {cycles_after - cycles_before} cycle dates"
        elif import_type == "activity":
            imp.import_activity_csv(path)
            msg = "Activities imported successfully"
        else:
            return jsonify({"ok": False, "error": f"Unknown import type: {import_type}"})
        return jsonify({"ok": True, "message": msg})
    except Exception as e:
        import traceback
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})
    finally:
        os.unlink(path)


@app.route("/api/exclusions", methods=["GET"])
def api_get_exclusions():
    return jsonify(db.get_exclusions())


@app.route("/api/exclusions", methods=["POST"])
def api_add_exclusion():
    data = request.get_json()
    db.add_exclusion(data["start"], data["end"], data.get("reason", ""))
    return jsonify({"ok": True})


@app.route("/api/exclusions/<int:exc_id>", methods=["DELETE"])
def api_delete_exclusion(exc_id):
    db.delete_exclusion(exc_id)
    return jsonify({"ok": True})


if __name__ == "__main__":
    print("\n  Glycles local dashboard")
    print("  ─────────────────────────")
    print("  http://localhost:5000")
    print("  Ctrl+C to stop\n")
    app.run(debug=False, port=5000)
