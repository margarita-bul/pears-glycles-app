"""
app.py — Local Glycles dashboard.
Run: python app.py
Then open: http://localhost:5000
"""
import os
from datetime import datetime, date, timedelta
from flask import Flask, render_template_string, jsonify, request, redirect, url_for
from dotenv import load_dotenv
import db

load_dotenv()
db.init_db()

app = Flask(__name__)

# ── HTML template ──────────────────────────────────────────────────────────────
HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Glycles — Local</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/chartjs-plugin-annotation/3.0.1/chartjs-plugin-annotation.min.js"></script>
<style>
:root {
  --bg:#0f1117; --bg2:#181c27; --bg3:#1e2235;
  --border:#2a2f45; --text:#e8eaf6; --muted:#7a8099;
  --red:#c0392b; --orange:#e67e22; --green:#27ae60; --purple:#8e44ad; --grey:#7f8c8d;
  --accent:#aa0a28;
}
* { box-sizing:border-box; margin:0; padding:0; }
body { background:var(--bg); color:var(--text); font-family:'Inter',system-ui,sans-serif; font-size:14px; }
nav { background:var(--bg2); border-bottom:1px solid var(--border); padding:.75rem 1.5rem;
      display:flex; align-items:center; gap:1rem; }
nav h1 { font-size:1rem; font-weight:700; letter-spacing:-.02em; }
nav h1 span { color:var(--accent); }
.nav-status { font-size:.75rem; color:var(--muted); margin-left:auto; }
.nav-status b { color:var(--green); }

.container { max-width:1200px; margin:0 auto; padding:1.5rem; }

/* Status bar */
.status-bar { display:flex; gap:1rem; margin-bottom:1.5rem; flex-wrap:wrap; }
.stat-card { background:var(--bg2); border:1px solid var(--border); border-radius:12px;
             padding:1rem 1.25rem; flex:1; min-width:140px; }
.stat-card .label { font-size:.72rem; color:var(--muted); text-transform:uppercase;
                    letter-spacing:.06em; margin-bottom:.3rem; }
.stat-card .value { font-size:1.6rem; font-weight:700; }
.stat-card .sub { font-size:.75rem; color:var(--muted); margin-top:.2rem; }

/* Section titles */
h2 { font-size:.8rem; font-weight:700; letter-spacing:.1em; text-transform:uppercase;
     color:var(--muted); margin-bottom:1rem; margin-top:1.75rem; }

/* Chart containers */
.chart-wrap { background:var(--bg2); border:1px solid var(--border); border-radius:12px;
              padding:1.25rem; margin-bottom:1.5rem; }
.chart-wrap canvas { width:100% !important; }

/* Phase legend */
.phase-legend { display:flex; gap:1rem; flex-wrap:wrap; margin-bottom:1rem; }
.phase-pill { display:flex; align-items:center; gap:.4rem; font-size:.75rem; color:var(--muted); }
.phase-dot { width:10px; height:10px; border-radius:50%; flex-shrink:0; }

/* Stats grid */
.stats-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:1rem; margin-bottom:1.5rem; }
.phase-stat { background:var(--bg2); border:1px solid var(--border); border-radius:12px; padding:1rem; }
.phase-stat .phase-name { font-size:.72rem; font-weight:700; text-transform:uppercase;
                           letter-spacing:.08em; margin-bottom:.6rem; }
.phase-stat .metric { display:flex; justify-content:space-between; font-size:.8rem;
                       padding:.2rem 0; border-bottom:1px solid var(--border); }
.phase-stat .metric:last-child { border:none; }
.phase-stat .metric span { color:var(--muted); }

/* Cycle form */
.cycle-section { display:grid; grid-template-columns:1fr 1fr; gap:1.5rem; }
@media(max-width:700px) { .cycle-section { grid-template-columns:1fr; } }

.form-card { background:var(--bg2); border:1px solid var(--border); border-radius:12px; padding:1.25rem; }
.form-row { display:flex; gap:.75rem; align-items:flex-end; flex-wrap:wrap; margin-bottom:.75rem; }
.form-field { display:flex; flex-direction:column; gap:.3rem; flex:1; min-width:120px; }
.form-field label { font-size:.72rem; color:var(--muted); }
input[type=date], input[type=number], input[type=text] {
  background:var(--bg3); border:1px solid var(--border); border-radius:8px;
  padding:.5rem .75rem; color:var(--text); font-size:.85rem; outline:none; width:100%;
}
input:focus { border-color:var(--accent); }
.btn { background:var(--accent); color:#fff; border:none; border-radius:8px;
       padding:.5rem 1rem; font-size:.82rem; font-weight:600; cursor:pointer; white-space:nowrap; }
.btn:hover { opacity:.85; }
.btn-ghost { background:transparent; border:1px solid var(--border); color:var(--muted); }
.btn-ghost:hover { color:var(--text); border-color:var(--text); }

/* Cycle list */
.cycle-list { display:flex; flex-direction:column; gap:.5rem; max-height:300px; overflow-y:auto; }
.cycle-item { display:flex; justify-content:space-between; align-items:center;
              background:var(--bg3); border-radius:8px; padding:.6rem .85rem; font-size:.82rem; }
.cycle-item .date { font-weight:600; }
.cycle-item .meta { color:var(--muted); font-size:.75rem; }
.cycle-item .del { color:var(--muted); cursor:pointer; font-size:.85rem; background:none;
                   border:none; color:#e74c3c; }
.cycle-item .del:hover { opacity:.7; }

.empty { color:var(--muted); font-size:.82rem; padding:.5rem 0; }

/* Days selector */
.days-selector { display:flex; gap:.5rem; margin-bottom:1rem; flex-wrap:wrap; }
.days-btn { padding:.3rem .7rem; border-radius:6px; border:1px solid var(--border);
            background:transparent; color:var(--muted); font-size:.75rem; cursor:pointer; }
.days-btn.active, .days-btn:hover { background:var(--accent); color:#fff; border-color:var(--accent); }

#loading { color:var(--muted); padding:2rem; text-align:center; }
</style>
</head>
<body>
<nav>
  <h1>gl<span>y</span>cles <span style="color:var(--muted);font-weight:400">local</span></h1>
  <span class="nav-status" id="nav-status">Loading…</span>
</nav>

<div class="container">
  <div id="loading">Loading data…</div>
  <div id="main" style="display:none">

    <!-- Status cards -->
    <div class="status-bar" id="status-cards"></div>

    <!-- Timeline chart -->
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

    <!-- Phase stats -->
    <h2>Stats by cycle phase</h2>
    <div class="stats-grid" id="stats-grid"></div>

    <!-- Multi-cycle trend -->
    <h2>Trend across cycles</h2>
    <div class="chart-wrap"><canvas id="trendChart" height="80"></canvas></div>

    <!-- Cycle management -->
    <h2>Cycle dates</h2>
    <div class="cycle-section">
      <div class="form-card">
        <div style="font-size:.82rem;font-weight:600;margin-bottom:.85rem;">Add period start date</div>
        <div class="form-row">
          <div class="form-field">
            <label>Period start date</label>
            <input type="date" id="cycleDate">
          </div>
          <div class="form-field" style="max-width:110px">
            <label>Cycle length (days)</label>
            <input type="number" id="cycleLen" value="28" min="20" max="45">
          </div>
        </div>
        <div class="form-row">
          <div class="form-field">
            <label>Notes (optional)</label>
            <input type="text" id="cycleNotes" placeholder="e.g. spotting, late…">
          </div>
        </div>
        <button class="btn" onclick="addCycle()">Add cycle</button>
      </div>

      <div class="form-card">
        <div style="font-size:.82rem;font-weight:600;margin-bottom:.85rem;">Saved cycles</div>
        <div class="cycle-list" id="cycle-list">
          <div class="empty">No cycles added yet.</div>
        </div>
      </div>
    </div>

  </div><!-- /main -->
</div><!-- /container -->

<script>
// ── State ──────────────────────────────────────────────────────────────
let timelineChart = null;
let trendChart = null;
let currentDays = 1;
const PHASES = ['menstrual','follicular','ovulatory','luteal'];
const PHASE_COLORS = {
  menstrual:'#c0392b', follicular:'#e67e22', ovulatory:'#27ae60',
  luteal:'#8e44ad', unknown:'#7f8c8d'
};

// ── Bootstrap ──────────────────────────────────────────────────────────
async function init() {
  await Promise.all([loadDashboard(), loadCycles()]);
  document.getElementById('loading').style.display = 'none';
  document.getElementById('main').style.display = 'block';
}

// ── Dashboard load ─────────────────────────────────────────────────────
async function loadDashboard(days = currentDays) {
  currentDays = days;
  const res = await fetch(`/api/dashboard?days=${days}`);
  const d = await res.json();

  // Nav status
  const ns = document.getElementById('nav-status');
  if (d.latest) {
    ns.innerHTML = `Latest: <b>${d.latest.value_mmol} mmol/L</b> &nbsp;·&nbsp; ${formatTime(d.latest.ts)} &nbsp;·&nbsp; ${d.total_readings} readings stored`;
  } else {
    ns.innerHTML = `<span style="color:#e67e22">No data yet — is the poller running?</span>`;
  }

  renderStatusCards(d);
  renderTimeline(d.readings, d.cycles);
  renderStats(d.phase_stats);
  renderTrend(d.cycle_trend);
}

// ── Status cards ──────────────────────────────────────────────────────
function renderStatusCards(d) {
  const el = document.getElementById('status-cards');
  const latest = d.latest;
  const cards = [
    { label:'Current glucose', value: latest ? `${latest.value_mmol}` : '—',
      sub: latest ? `mmol/L · ${trendArrow(latest.trend)}` : 'No data' },
    { label:'Total readings', value: d.total_readings, sub:'in database' },
    { label:'Cycles logged', value: d.cycles.length, sub:'period start dates' },
    { label:'Time in range', value: d.overall_tir ? `${d.overall_tir}%` : '—',
      sub:'3.9–10.0 mmol/L (all data)' },
  ];
  el.innerHTML = cards.map(c => `
    <div class="stat-card">
      <div class="label">${c.label}</div>
      <div class="value">${c.value}</div>
      <div class="sub">${c.sub}</div>
    </div>`).join('');
}

// ── Timeline chart ────────────────────────────────────────────────────
function renderTimeline(readings, cycles) {
  // Phase legend
  const leg = document.getElementById('phase-legend');
  leg.innerHTML = Object.entries(PHASE_COLORS).filter(([p]) => p !== 'unknown').map(([p,c]) =>
    `<div class="phase-pill"><div class="phase-dot" style="background:${c}"></div>${p}</div>`
  ).join('');

  const labels = readings.map(r => r.ts);
  const values = readings.map(r => r.value_mmol);
  const colors = readings.map(r => PHASE_COLORS[r.phase] || '#7f8c8d');

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
        pointRadius: readings.length > 200 ? 0 : 3,
        pointBackgroundColor: colors,
        pointBorderColor: colors,
        tension: 0.3,
        fill: false,
      }]
    },
    options: {
      responsive: true,
      animation: false,
      plugins: {
        legend: { display: false },
        annotation: {
          annotations: {
            low:  { type:'line', yMin:3.9, yMax:3.9, borderColor:'rgba(231,76,60,.4)', borderWidth:1, borderDash:[4,4] },
            high: { type:'line', yMin:10,  yMax:10,  borderColor:'rgba(231,76,60,.4)', borderWidth:1, borderDash:[4,4] },
          }
        },
        tooltip: {
          callbacks: {
            title: ctx => formatTime(ctx[0].label),
            label: ctx => {
              const r = readings[ctx.dataIndex];
              return `${ctx.raw} mmol/L · ${r.phase} · ${trendArrow(r.trend)}`;
            }
          }
        }
      },
      scales: {
        x: {
          ticks: { color:'#7a8099', maxTicksLimit:10,
                   callback: (v,i) => formatTime(labels[i]).slice(0,10) },
          grid: { color:'rgba(255,255,255,.05)' }
        },
        y: {
          min: 2, max: 16,
          ticks: { color:'#7a8099' },
          grid: { color:'rgba(255,255,255,.05)' }
        }
      }
    }
  });
}

// ── Phase stats ───────────────────────────────────────────────────────
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
      <div class="metric"><span>Avg</span> ${s.mean} mmol/L</div>
      <div class="metric"><span>Std dev</span> ±${s.std}</div>
      <div class="metric"><span>Min / Max</span> ${s.min} / ${s.max}</div>
      <div class="metric"><span>Time in range</span> ${s.time_in_range_pct}%</div>
      <div class="metric"><span>Readings</span> ${s.count}</div>
    </div>`;
  }).join('');
}

// ── Trend chart ───────────────────────────────────────────────────────
function renderTrend(trend) {
  const ctx = document.getElementById('trendChart').getContext('2d');
  if (trendChart) trendChart.destroy();
  if (!trend || trend.length < 2) {
    ctx.canvas.parentElement.innerHTML = '<div style="color:var(--muted);padding:1rem;font-size:.82rem">Need at least 2 cycles with glucose data to show trend.</div>';
    return;
  }
  const labels = trend.map(t => t.cycle_label);
  trendChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: PHASES.map(phase => ({
        label: phase,
        data: trend.map(t => t[phase]),
        borderColor: PHASE_COLORS[phase],
        backgroundColor: PHASE_COLORS[phase] + '22',
        borderWidth: 2,
        pointRadius: 5,
        tension: 0.3,
        spanGaps: true,
      }))
    },
    options: {
      responsive: true,
      plugins: {
        legend: { labels: { color:'#7a8099', boxWidth:12 } },
        tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${ctx.raw ?? '—'} mmol/L` } }
      },
      scales: {
        x: { ticks: { color:'#7a8099' }, grid: { color:'rgba(255,255,255,.05)' } },
        y: { min:3, ticks: { color:'#7a8099' }, grid: { color:'rgba(255,255,255,.05)' },
             title: { display:true, text:'mmol/L', color:'#7a8099' } }
      }
    }
  });
}

// ── Cycles ────────────────────────────────────────────────────────────
async function loadCycles() {
  const res = await fetch('/api/cycles');
  const cycles = await res.json();
  renderCycleList(cycles);
}

function renderCycleList(cycles) {
  const el = document.getElementById('cycle-list');
  if (!cycles.length) { el.innerHTML = '<div class="empty">No cycles added yet.</div>'; return; }
  el.innerHTML = cycles.map(c => `
    <div class="cycle-item">
      <div>
        <div class="date">${c.period_start}</div>
        <div class="meta">${c.cycle_length}d cycle${c.notes ? ' · ' + c.notes : ''}</div>
      </div>
      <button class="del" onclick="deleteCycle('${c.period_start}')">✕</button>
    </div>`).join('');
}

async function addCycle() {
  const d = document.getElementById('cycleDate').value;
  const l = parseInt(document.getElementById('cycleLen').value) || 28;
  const n = document.getElementById('cycleNotes').value;
  if (!d) { alert('Please pick a date.'); return; }
  await fetch('/api/cycles', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ period_start:d, cycle_length:l, notes:n })
  });
  document.getElementById('cycleDate').value = '';
  document.getElementById('cycleNotes').value = '';
  await loadCycles();
  await loadDashboard();
}

async function deleteCycle(dateStr) {
  if (!confirm(`Delete cycle starting ${dateStr}?`)) return;
  await fetch(`/api/cycles/${dateStr}`, { method:'DELETE' });
  await loadCycles();
  await loadDashboard();
}

// ── Days buttons ──────────────────────────────────────────────────────
function setDays(n) {
  currentDays = n;
  document.querySelectorAll('.days-btn').forEach((b,i) => {
    b.classList.toggle('active', [1,3,7,14,30,90][i] === n);
  });
  loadDashboard(n);
}

// ── Helpers ───────────────────────────────────────────────────────────
function formatTime(ts) {
  if (!ts) return '—';
  return ts.replace('T', ' ').slice(0, 16);
}

function trendArrow(t) {
  const arrows = ['↑↑','↑↑','↑','↗','→','↘','↓','↓↓'];
  return (t !== null && t !== undefined && arrows[t]) ? arrows[t] : '—';
}

// ── Auto-refresh every 5 min ──────────────────────────────────────────
setInterval(() => loadDashboard(currentDays), 5 * 60 * 1000);

init();
</script>
</body>
</html>
"""

# ── API routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/dashboard")
def api_dashboard():
    days = int(request.args.get("days", 1))
    start = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")

    readings = db.get_readings(start=start)
    all_readings = db.get_readings()  # for TIR calculation
    cycles = db.get_cycles()
    latest = db.get_latest_reading()
    total = db.get_reading_count()

    # Annotate with phase
    readings = db.annotate_readings_with_phase(readings, cycles)
    all_annotated = db.annotate_readings_with_phase(all_readings, cycles)

    # Overall time in range
    in_range = [r for r in all_annotated if 3.9 <= r["value_mmol"] <= 10.0]
    overall_tir = round(len(in_range) / len(all_annotated) * 100, 1) if all_annotated else None

    # Phase stats (from all data, not just window)
    phase_stats = db.compute_phase_stats(all_annotated) if cycles else None

    # Cycle trend
    cycle_trend = db.compute_cycle_trend(cycles, all_annotated) if cycles else []

    return jsonify({
        "readings":     readings,
        "cycles":       cycles,
        "latest":       latest,
        "total_readings": total,
        "phase_stats":  phase_stats,
        "cycle_trend":  cycle_trend,
        "overall_tir":  overall_tir,
    })


@app.route("/api/cycles", methods=["GET"])
def api_get_cycles():
    return jsonify(db.get_cycles())


@app.route("/api/cycles", methods=["POST"])
def api_add_cycle():
    data = request.get_json()
    db.add_cycle(
        period_start=data["period_start"],
        cycle_length=int(data.get("cycle_length", 28)),
        notes=data.get("notes", "")
    )
    return jsonify({"ok": True})


@app.route("/api/cycles/<date_str>", methods=["DELETE"])
def api_delete_cycle(date_str):
    db.delete_cycle(date_str)
    return jsonify({"ok": True})


if __name__ == "__main__":
    print("\n  Glycles local dashboard")
    print("  ─────────────────────────────")
    print("  Open http://localhost:5000 in your browser")
    print("  Run poller.py in a separate terminal to fetch glucose data")
    print("  Press Ctrl+C to stop\n")
    app.run(debug=False, port=5000)
