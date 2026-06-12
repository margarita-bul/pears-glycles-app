"""
db.py — SQLite database layer for Glycles local app.
"""
import sqlite3
import os
from datetime import datetime, date, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "glycles.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS glucose_readings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          TEXT NOT NULL UNIQUE,
                value_mmol  REAL NOT NULL,
                trend       INTEGER,
                source      TEXT DEFAULT 'libre'
            );
            CREATE TABLE IF NOT EXISTS cycles (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                period_start    TEXT NOT NULL UNIQUE,
                cycle_length    INTEGER DEFAULT 28,
                notes           TEXT
            );
            CREATE TABLE IF NOT EXISTS activities (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ts           TEXT NOT NULL,
                date         TEXT NOT NULL,
                type         TEXT,
                duration_min INTEGER,
                intensity    TEXT,
                notes        TEXT,
                source       TEXT DEFAULT 'manual',
                UNIQUE(ts, type)
            );
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_glucose_ts   ON glucose_readings(ts);
            CREATE INDEX IF NOT EXISTS idx_cycles_start ON cycles(period_start);
            CREATE INDEX IF NOT EXISTS idx_act_date     ON activities(date);
        """)
    print(f"[db] Initialized at {DB_PATH}")


# ── Settings ───────────────────────────────────────────────

def get_setting(key: str, default: str = "") -> str:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)",
            (key, value)
        )


def get_timezone() -> str:
    return get_setting("timezone", "UTC")


# ── Glucose ────────────────────────────────────────────────

def upsert_reading(ts: str, value_mmol: float, trend: int = None, source: str = "libre"):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO glucose_readings (ts, value_mmol, trend, source) VALUES (?,?,?,?)",
            (ts, value_mmol, trend, source)
        )


def get_readings(start: str = None, end: str = None):
    with get_conn() as conn:
        if start and end:
            rows = conn.execute(
                "SELECT * FROM glucose_readings WHERE ts >= ? AND ts <= ? ORDER BY ts",
                (start, end)
            ).fetchall()
        elif start:
            rows = conn.execute(
                "SELECT * FROM glucose_readings WHERE ts >= ? ORDER BY ts",
                (start,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM glucose_readings ORDER BY ts DESC LIMIT 5000"
            ).fetchall()
        return [dict(r) for r in rows]


def get_latest_reading():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM glucose_readings ORDER BY ts DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def get_reading_count():
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM glucose_readings").fetchone()[0]


# ── Cycles ─────────────────────────────────────────────────

def add_cycle(period_start: str, cycle_length: int = 28, notes: str = ""):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO cycles (period_start, cycle_length, notes) VALUES (?,?,?)",
            (period_start, cycle_length, notes)
        )


def delete_cycle(period_start: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM cycles WHERE period_start = ?", (period_start,))


def get_cycles():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM cycles ORDER BY period_start DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# ── Activities ─────────────────────────────────────────────

def get_activities(start: str = None, end: str = None):
    with get_conn() as conn:
        if start and end:
            rows = conn.execute(
                "SELECT * FROM activities WHERE date >= ? AND date <= ? ORDER BY ts",
                (start[:10], end[:10])
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM activities ORDER BY ts DESC LIMIT 500"
            ).fetchall()
        return [dict(r) for r in rows]


def add_activity(ts: str, act_type: str, duration_min: int = None,
                 intensity: str = "", notes: str = "", source: str = "manual"):
    with get_conn() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO activities
               (ts, date, type, duration_min, intensity, notes, source)
               VALUES (?,?,?,?,?,?,?)""",
            (ts, ts[:10], act_type, duration_min, intensity, notes, source)
        )


def delete_activity(activity_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM activities WHERE id = ?", (activity_id,))


# ── Phase calculation ──────────────────────────────────────

PHASE_COLORS = {
    "menstrual":  "#c0392b",
    "follicular": "#e67e22",
    "ovulatory":  "#27ae60",
    "luteal":     "#8e44ad",
    "unknown":    "#95a5a6",
}

PHASE_ORDER = ["menstrual", "follicular", "ovulatory", "luteal"]


def get_phase_for_date(d: date, cycles: list) -> str:
    best = None
    best_start = None
    for c in cycles:
        start = date.fromisoformat(c["period_start"])
        if start <= d:
            if best_start is None or start > best_start:
                best_start = start
                best = c
    if best is None:
        return "unknown"
    day_of_cycle = (d - date.fromisoformat(best["period_start"])).days + 1
    length = best.get("cycle_length", 28)
    if day_of_cycle > length:
        return "unknown"
    if day_of_cycle <= 5:
        return "menstrual"
    elif day_of_cycle <= 13:
        return "follicular"
    elif day_of_cycle <= 16:
        return "ovulatory"
    else:
        return "luteal"


def annotate_readings_with_phase(readings: list, cycles: list) -> list:
    for r in readings:
        d = date.fromisoformat(r["ts"][:10])
        phase = get_phase_for_date(d, cycles)
        r["phase"] = phase
        r["phase_color"] = PHASE_COLORS[phase]
    return readings


def compute_phase_stats(readings: list) -> dict:
    import statistics
    buckets = {p: [] for p in PHASE_ORDER + ["unknown"]}
    for r in readings:
        phase = r.get("phase", "unknown")
        buckets.setdefault(phase, []).append(r["value_mmol"])

    stats = {}
    for phase, values in buckets.items():
        if not values:
            stats[phase] = None
            continue
        in_range = [v for v in values if 3.9 <= v <= 10.0]
        stats[phase] = {
            "count":             len(values),
            "mean":              round(statistics.mean(values), 2),
            "std":               round(statistics.stdev(values), 2) if len(values) > 1 else 0,
            "min":               round(min(values), 2),
            "max":               round(max(values), 2),
            "time_in_range_pct": round(len(in_range) / len(values) * 100, 1),
            "color":             PHASE_COLORS.get(phase, "#95a5a6"),
        }
    return stats


def compute_cycle_trend(cycles: list, readings: list) -> list:
    import statistics
    result = []
    sorted_cycles = sorted(cycles, key=lambda c: c["period_start"])
    for i, c in enumerate(sorted_cycles):
        start  = date.fromisoformat(c["period_start"])
        length = c.get("cycle_length", 28)
        end    = start + timedelta(days=length)
        cycle_readings = [
            r for r in readings
            if start <= date.fromisoformat(r["ts"][:10]) < end
        ]
        annotated  = annotate_readings_with_phase(cycle_readings, [c])
        phase_vals = {p: [] for p in PHASE_ORDER}
        for r in annotated:
            if r["phase"] in phase_vals:
                phase_vals[r["phase"]].append(r["value_mmol"])
        row = {"cycle_label": f"Cycle {i+1} ({c['period_start']})"}
        for p in PHASE_ORDER:
            vals = phase_vals[p]
            row[p] = round(statistics.mean(vals), 2) if vals else None
        result.append(row)
    return result
