"""
importer.py — Import data from various sources into glycles.db

Usage:
  python importer.py glucose  path/to/LibreViewExport.csv
  python importer.py period   path/to/periods.txt
  python importer.py activity path/to/activity.csv
  python importer.py timezone Europe/Berlin

Run once per file. Safe to re-run — duplicates are skipped.
"""
import sys
import os
import csv
import sqlite3
from datetime import datetime, timezone, date
import db

db.init_db()


# ══════════════════════════════════════════════════════════════════════
#  TIMEZONE SETTING
# ══════════════════════════════════════════════════════════════════════

def set_timezone(tz_name: str):
    """Store user's local timezone in the database settings table."""
    with db.get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('timezone', ?)",
            (tz_name,)
        )
    print(f"[timezone] Set to {tz_name}")
    print(f"  Dashboard will now display times in {tz_name}")


# ══════════════════════════════════════════════════════════════════════
#  LIBRE CSV IMPORT
# ══════════════════════════════════════════════════════════════════════

def import_glucose_csv(filepath: str):
    """
    Import LibreView CSV export.

    LibreView CSV format:
      Row 1: Patient info (skip)
      Row 2: Column headers
      Rows 3+: Data

    Key columns:
      "Device Timestamp"          — local time string
      "Record Type"               — 0=historic auto, 1=manual scan, 6=note/event
      "Historic Glucose mmol/L"   — value for type 0
      "Scan Glucose mmol/L"       — value for type 1

    Timestamps in the file are LOCAL time (device time zone).
    We store them as-is in ISO format; the dashboard applies tz offset for display.
    """
    if not os.path.exists(filepath):
        print(f"[error] File not found: {filepath}")
        return

    new_count = 0
    skip_count = 0
    error_count = 0

    with open(filepath, encoding="utf-8-sig", errors="replace") as f:
        lines = f.readlines()

    # Skip first line (patient info), second line is headers
    if len(lines) < 3:
        print("[error] File too short — is this a LibreView export?")
        return

    # Find header row — it contains "Device Timestamp"
    header_idx = None
    for i, line in enumerate(lines):
        if "Device Timestamp" in line or "Gerätezeitstempel" in line:
            header_idx = i
            break

    if header_idx is None:
        print("[error] Could not find header row with 'Device Timestamp'")
        print("  Make sure your LibreView account is set to English")
        return

    reader = csv.DictReader(lines[header_idx:])

    # Normalise column names (strip whitespace, handle mmol/mg variants)
    def find_col(fieldnames, candidates):
        for name in fieldnames:
            for c in candidates:
                if c.lower() in name.lower():
                    return name
        return None

    fieldnames = reader.fieldnames or []
    ts_col   = find_col(fieldnames, ["Device Timestamp", "Gerätezeitstempel", "timestamp"])
    hist_col = find_col(fieldnames, ["Historic Glucose mmol", "Historische Glukose mmol"])
    scan_col = find_col(fieldnames, ["Scan Glucose mmol", "Scans Glukose mmol"])
    type_col = find_col(fieldnames, ["Record Type", "Aufzeichnungstyp"])

    if not ts_col:
        print("[error] Could not find timestamp column. Check CSV is in English format.")
        return

    print(f"[glucose] Reading: {filepath}")
    print(f"  Timestamp col : {ts_col}")
    print(f"  Historic col  : {hist_col}")
    print(f"  Scan col      : {scan_col}")

    for row in reader:
        try:
            raw_ts = row.get(ts_col, "").strip()
            if not raw_ts:
                continue

            # Parse timestamp — LibreView uses DD-MM-YYYY HH:MM or MM-DD-YYYY HH:MM
            ts = parse_libre_timestamp(raw_ts)
            if not ts:
                error_count += 1
                continue

            # Get value — prefer historic, fall back to scan
            value = None
            if hist_col:
                v = row.get(hist_col, "").strip().replace(",", ".")
                if v:
                    try:
                        value = float(v)
                    except ValueError:
                        pass
            if value is None and scan_col:
                v = row.get(scan_col, "").strip().replace(",", ".")
                if v:
                    try:
                        value = float(v)
                    except ValueError:
                        pass

            if value is None:
                continue  # No glucose value in this row (e.g. insulin/notes row)

            # Convert mg/dL to mmol/L if necessary
            if value > 30:
                value = round(value / 18.016, 2)

            db.upsert_reading(ts=ts, value_mmol=value, trend=None, source="libreview_csv")
            new_count += 1

        except Exception as e:
            error_count += 1
            if error_count <= 3:
                print(f"  [warn] Row error: {e} — row: {dict(list(row.items())[:3])}")

    print(f"[glucose] Done — {new_count} readings imported, {skip_count} skipped, {error_count} errors")
    print(f"  Database now has {db.get_reading_count()} readings total")


def parse_libre_timestamp(raw: str) -> str | None:
    """
    Parse LibreView timestamp into ISO format YYYY-MM-DDTHH:MM:SS.
    LibreView exports local device time (no timezone info).
    Handles formats: DD-MM-YYYY HH:MM, MM/DD/YYYY HH:MM, YYYY-MM-DD HH:MM, etc.
    """
    raw = raw.strip()
    formats = [
        "%d-%m-%Y %H:%M",
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
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue
    return None


# ══════════════════════════════════════════════════════════════════════
#  PERIOD TXT IMPORT
# ══════════════════════════════════════════════════════════════════════

def import_period_txt(filepath: str):
    """
    Import period start dates from a plain text file.

    Supported formats (one date per line):
      2024-01-15
      2024-01-15 28          (date + cycle length in days)
      2024-01-15 28 some notes
      15.01.2024
      15/01/2024
      Jan 15 2024

    Lines starting with # are treated as comments and ignored.
    """
    if not os.path.exists(filepath):
        print(f"[error] File not found: {filepath}")
        return

    added = 0
    skipped = 0
    errors = 0

    with open(filepath, encoding="utf-8-sig", errors="replace") as f:
        lines = f.readlines()

    print(f"[period] Reading: {filepath}")

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()
        date_str = parts[0]
        cycle_length = 28
        notes = ""

        if len(parts) >= 2:
            try:
                cycle_length = int(parts[1])
                notes = " ".join(parts[2:])
            except ValueError:
                notes = " ".join(parts[1:])

        # Parse date
        parsed = parse_date(date_str)
        if not parsed:
            print(f"  [warn] Could not parse date: '{date_str}'")
            errors += 1
            continue

        db.add_cycle(
            period_start=parsed,
            cycle_length=cycle_length,
            notes=notes
        )
        print(f"  Added: {parsed} (cycle {cycle_length}d){' — ' + notes if notes else ''}")
        added += 1

    print(f"[period] Done — {added} cycles added, {errors} errors")


def parse_date(raw: str) -> str | None:
    """Parse a date string into YYYY-MM-DD."""
    formats = [
        "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y",
        "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y",
        "%B %d %Y", "%b %d %Y", "%d %B %Y", "%d %b %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# ══════════════════════════════════════════════════════════════════════
#  ACTIVITY IMPORT
# ══════════════════════════════════════════════════════════════════════

ACTIVITY_SCHEMA = """
    CREATE TABLE IF NOT EXISTS activities (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        ts          TEXT NOT NULL,          -- ISO datetime (local)
        date        TEXT NOT NULL,          -- YYYY-MM-DD
        type        TEXT,                   -- e.g. 'Running', 'Gym', 'Cycling'
        duration_min INTEGER,
        intensity   TEXT,                   -- 'low', 'moderate', 'high'
        notes       TEXT,
        source      TEXT DEFAULT 'manual',
        UNIQUE(ts, type)
    );
    CREATE INDEX IF NOT EXISTS idx_activities_date ON activities(date);
"""

def ensure_activity_table():
    with db.get_conn() as conn:
        conn.executescript(ACTIVITY_SCHEMA)


def import_activity_csv(filepath: str):
    """
    Import activity data from a CSV file.

    Expected columns (flexible — we try to match by name):
      date / Date / timestamp / Timestamp / datetime
      type / Type / activity / Activity / sport / Sport
      duration / Duration / duration_min / minutes / Minutes
      intensity / Intensity  (optional: low / moderate / high)
      notes / Notes          (optional)

    Example minimal CSV:
      date,type,duration_min
      2024-01-15,Running,45
      2024-01-16,Gym,60

    Example with all columns:
      date,type,duration_min,intensity,notes
      2024-01-15,Running,45,high,morning run
      2024-01-16,Yoga,30,low,
    """
    if not os.path.exists(filepath):
        print(f"[error] File not found: {filepath}")
        return

    ensure_activity_table()

    added = 0
    errors = 0

    with open(filepath, encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []

        def find_col(candidates):
            for name in fieldnames:
                for c in candidates:
                    if c.lower() == name.lower().strip():
                        return name
            return None

        ts_col       = find_col(["date","Date","timestamp","Timestamp","datetime","DateTime"])
        type_col     = find_col(["type","Type","activity","Activity","sport","Sport","name","Name"])
        dur_col      = find_col(["duration","Duration","duration_min","minutes","Minutes","mins","Mins"])
        intens_col   = find_col(["intensity","Intensity"])
        notes_col    = find_col(["notes","Notes","comment","Comment"])

        if not ts_col:
            print("[error] Could not find date/timestamp column in activity CSV")
            return

        print(f"[activity] Reading: {filepath}")

        for row in reader:
            try:
                raw_ts = row.get(ts_col, "").strip()
                if not raw_ts:
                    continue

                # Parse timestamp
                ts_iso = parse_libre_timestamp(raw_ts) or parse_date(raw_ts)
                if not ts_iso:
                    errors += 1
                    continue

                date_str = ts_iso[:10]
                act_type   = row.get(type_col, "").strip() if type_col else ""
                duration   = None
                if dur_col:
                    try:
                        duration = int(float(row.get(dur_col, "").strip()))
                    except (ValueError, AttributeError):
                        pass
                intensity  = row.get(intens_col, "").strip().lower() if intens_col else ""
                notes      = row.get(notes_col, "").strip() if notes_col else ""

                with db.get_conn() as conn:
                    conn.execute(
                        """INSERT OR IGNORE INTO activities
                           (ts, date, type, duration_min, intensity, notes, source)
                           VALUES (?,?,?,?,?,?,'activity_csv')""",
                        (ts_iso, date_str, act_type, duration, intensity, notes)
                    )
                added += 1

            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"  [warn] Row error: {e}")

    print(f"[activity] Done — {added} activities imported, {errors} errors")


# ══════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════

def print_usage():
    print("""
Usage:
  python importer.py glucose  <LibreView_export.csv>
  python importer.py period   <periods.txt>
  python importer.py activity <activity.csv>
  python importer.py timezone <timezone_name>

Examples:
  python importer.py glucose  "C:/Downloads/MargaritaBulgacheva_glucose_2024.csv"
  python importer.py period   periods.txt
  python importer.py activity activity.csv
  python importer.py timezone Europe/Berlin

Period file format (periods.txt) — one entry per line:
  2024-01-15
  2024-02-12 29
  2024-03-13 28 heavy start

Activity CSV format (activity.csv):
  date,type,duration_min,intensity,notes
  2024-01-15,Running,45,high,morning run
  2024-01-16,Gym,60,moderate,
""")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print_usage()
        sys.exit(1)

    command  = sys.argv[1].lower()
    argument = sys.argv[2]

    if command == "glucose":
        import_glucose_csv(argument)
    elif command == "period":
        import_period_txt(argument)
    elif command == "activity":
        import_activity_csv(argument)
    elif command == "timezone":
        set_timezone(argument)
    else:
        print(f"Unknown command: {command}")
        print_usage()
        sys.exit(1)
