"""
importer.py — Import data from various sources into glycles.db

Usage:
  python importer.py glucose  path/to/LibreViewExport.csv
  python importer.py period   path/to/periods.txt
  python importer.py activity path/to/activity.csv
  python importer.py timezone Europe/Berlin
"""
import sys, os, csv, sqlite3
from datetime import datetime, timezone, date
import db

db.init_db()


# ══════════════════════════════════════════════════════════════════
#  TIMEZONE SETTING
# ══════════════════════════════════════════════════════════════════

def set_timezone(tz_name: str):
    with db.get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY, value TEXT
            )
        """)
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('timezone', ?)",
            (tz_name,)
        )
    print(f"[timezone] Set to {tz_name}")


# ══════════════════════════════════════════════════════════════════
#  LIBRE CSV IMPORT
# ══════════════════════════════════════════════════════════════════

def import_glucose_csv(filepath: str):
    """
    Import LibreView CSV export.

    Row 1: patient info (skip)
    Row 2: column headers
    Rows 3+: data

    Handles both mmol/L and mg/dL exports.
    Timestamps are local device time — stored as-is (no UTC conversion).
    """
    if not os.path.exists(filepath):
        print(f"[error] File not found: {filepath}")
        return

    with open(filepath, encoding="utf-8-sig", errors="replace") as f:
        lines = f.readlines()

    if len(lines) < 3:
        print("[error] File too short")
        return

    # Row 2 (index 1) is the header row
    header_line = lines[1]
    data_lines  = lines[2:]

    reader = csv.DictReader([header_line] + data_lines)
    fieldnames = reader.fieldnames or []

    print(f"[glucose] Columns found: {fieldnames[:6]}")

    # ── Find columns by substring match (case-insensitive) ─────────
    def find_col(*candidates):
        for col in fieldnames:
            col_l = col.lower().strip()
            for c in candidates:
                if c.lower() in col_l:
                    return col
        return None

    ts_col   = find_col("device timestamp", "timestamp", "gerätezeitstempel", "time")
    hist_col = find_col("historic glucose")   # matches both mg/dL and mmol/L
    scan_col = find_col("scan glucose")
    type_col = find_col("record type", "aufzeichnungstyp")

    print(f"[glucose] Timestamp col : {ts_col}")
    print(f"[glucose] Historic col  : {hist_col}")
    print(f"[glucose] Scan col      : {scan_col}")
    print(f"[glucose] Record type   : {type_col}")

    if not ts_col:
        print("[error] Cannot find timestamp column. Is this a LibreView CSV export?")
        return

    # Detect unit from column name
    is_mg = hist_col and "mg" in hist_col.lower()
    unit_label = "mg/dL" if is_mg else "mmol/L"
    print(f"[glucose] Unit detected : {unit_label}")

    new_count = skipped = errors = 0

    for row in reader:
        try:
            raw_ts = row.get(ts_col, "").strip()
            if not raw_ts:
                continue

            # Only import historic (type 0) and scan (type 1) records
            rec_type = row.get(type_col, "0").strip() if type_col else "0"
            if rec_type not in ("0", "1"):
                continue

            # Get value
            value = None
            col_to_try = hist_col if rec_type == "0" else scan_col
            if col_to_try:
                raw_v = row.get(col_to_try, "").strip().replace(",", ".")
                if raw_v:
                    try:
                        value = float(raw_v)
                    except ValueError:
                        pass

            # Fallback: try the other column
            if value is None:
                for col in [hist_col, scan_col]:
                    if col:
                        raw_v = row.get(col, "").strip().replace(",", ".")
                        if raw_v:
                            try:
                                value = float(raw_v)
                                break
                            except ValueError:
                                pass

            if value is None:
                skipped += 1
                continue

            # Convert mg/dL → mmol/L
            if is_mg or value > 30:
                value = round(value / 18.016, 2)

            # Parse timestamp
            ts = parse_libre_timestamp(raw_ts)
            if not ts:
                errors += 1
                if errors <= 3:
                    print(f"  [warn] Could not parse timestamp: '{raw_ts}'")
                continue

            db.upsert_reading(ts=ts, value_mmol=value, trend=None, source="libreview_csv")
            new_count += 1

        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  [warn] Row error: {e}")

    print(f"[glucose] Done — {new_count} readings imported, {skipped} skipped (no value), {errors} errors")
    print(f"[glucose] Database now has {db.get_reading_count()} readings total")
    return new_count


def parse_libre_timestamp(raw: str) -> str | None:
    """Parse LibreView timestamp to ISO YYYY-MM-DDTHH:MM:SS."""
    raw = raw.strip()
    formats = [
        "%d-%m-%Y %H:%M",   # 13-05-2026 21:00  ← your format
        "%d/%m/%Y %H:%M",
        "%m-%d-%Y %H:%M",
        "%m/%d/%Y %H:%M",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M",
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue
    return None


# ══════════════════════════════════════════════════════════════════
#  PERIOD TXT IMPORT
# ══════════════════════════════════════════════════════════════════

def import_period_txt(filepath: str):
    """
    One date per line:
      2024-01-15
      2024-01-15 28
      2024-01-15 28 some notes
    Lines starting with # are comments.
    """
    if not os.path.exists(filepath):
        print(f"[error] File not found: {filepath}")
        return

    added = errors = 0
    with open(filepath, encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            date_str     = parts[0]
            cycle_length = 28
            notes        = ""
            if len(parts) >= 2:
                try:
                    cycle_length = int(parts[1])
                    notes = " ".join(parts[2:])
                except ValueError:
                    notes = " ".join(parts[1:])
            parsed = parse_date(date_str)
            if not parsed:
                print(f"  [warn] Cannot parse date: '{date_str}'")
                errors += 1
                continue
            db.add_cycle(period_start=parsed, cycle_length=cycle_length, notes=notes)
            print(f"  Added: {parsed} ({cycle_length}d){' — '+notes if notes else ''}")
            added += 1

    print(f"[period] Done — {added} cycles added, {errors} errors")
    return added


def parse_date(raw: str) -> str | None:
    for fmt in ["%Y-%m-%d","%d.%m.%Y","%d/%m/%Y","%m/%d/%Y",
                "%d-%m-%Y","%m-%d-%Y","%B %d %Y","%b %d %Y"]:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# ══════════════════════════════════════════════════════════════════
#  ACTIVITY CSV IMPORT
# ══════════════════════════════════════════════════════════════════

def import_activity_csv(filepath: str):
    if not os.path.exists(filepath):
        print(f"[error] File not found: {filepath}")
        return

    # Ensure table exists
    with db.get_conn() as conn:
        conn.executescript("""
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
            CREATE INDEX IF NOT EXISTS idx_act_date ON activities(date);
        """)

    added = errors = 0
    with open(filepath, encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []

        def find_col(*candidates):
            for col in fieldnames:
                for c in candidates:
                    if c.lower() == col.lower().strip():
                        return col
            return None

        ts_col     = find_col("date","Date","timestamp","datetime","DateTime")
        type_col   = find_col("type","Type","activity","Activity","sport","Sport","name","Name")
        dur_col    = find_col("duration","duration_min","minutes","mins","Duration","Minutes")
        intens_col = find_col("intensity","Intensity")
        notes_col  = find_col("notes","Notes","comment","Comment")

        if not ts_col:
            print("[error] Cannot find date column in activity CSV")
            return

        for row in reader:
            try:
                raw_ts = row.get(ts_col, "").strip()
                if not raw_ts:
                    continue
                ts_iso = parse_libre_timestamp(raw_ts) or (parse_date(raw_ts) + "T00:00:00" if parse_date(raw_ts) else None)
                if not ts_iso:
                    errors += 1
                    continue
                duration = None
                if dur_col:
                    try:
                        duration = int(float(row.get(dur_col,"").strip()))
                    except (ValueError, AttributeError):
                        pass
                with db.get_conn() as conn:
                    conn.execute(
                        """INSERT OR IGNORE INTO activities
                           (ts,date,type,duration_min,intensity,notes,source)
                           VALUES (?,?,?,?,?,?,'activity_csv')""",
                        (ts_iso, ts_iso[:10],
                         row.get(type_col,"").strip() if type_col else "",
                         duration,
                         row.get(intens_col,"").strip().lower() if intens_col else "",
                         row.get(notes_col,"").strip() if notes_col else "")
                    )
                added += 1
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"  [warn] {e}")

    print(f"[activity] Done — {added} activities imported, {errors} errors")
    return added


# ══════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════

def print_usage():
    print("""
Usage:
  python importer.py glucose  <LibreView_export.csv>
  python importer.py period   <periods.txt>
  python importer.py activity <activity.csv>
  python importer.py timezone <timezone_name>

Period file (one line per cycle):
  2024-01-15
  2024-02-12 29
  2024-03-13 28 heavy start

Activity CSV columns: date, type, duration_min, intensity, notes
""")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print_usage()
        sys.exit(1)
    cmd = sys.argv[1].lower()
    arg = sys.argv[2]
    if cmd == "glucose":
        import_glucose_csv(arg)
    elif cmd == "period":
        import_period_txt(arg)
    elif cmd == "activity":
        import_activity_csv(arg)
    elif cmd == "timezone":
        set_timezone(arg)
    else:
        print(f"Unknown command: {cmd}")
        print_usage()
