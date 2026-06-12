"""
poller.py — Fetches glucose readings from LibreLinkUp every N minutes.

Run in a separate terminal:
  Windows:  python poller.py
  Mac/Linux: python3 poller.py

Press Ctrl+C to stop.
"""
import os
import time
import logging
from datetime import timezone
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [poller] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

from db import init_db, upsert_reading

EMAIL    = os.environ.get("LIBRE_EMAIL", "")
PASSWORD = os.environ.get("LIBRE_PASSWORD", "")
URL      = os.environ.get("LIBRE_URL", "https://api-eu2.libreview.io")
INTERVAL = int(os.environ.get("POLL_INTERVAL_MINUTES", 5)) * 60


# Map the LibreLinkUp URL string to the APIUrl enum
def get_api_url(url_str: str):
    from pylibrelinkup.api_url import APIUrl
    mapping = {
        "api-eu.libreview.io":   APIUrl.EU,
        "api-eu2.libreview.io":  APIUrl.EU2,
        "api-us.libreview.io":   APIUrl.US,
        "api-de.libreview.io":   APIUrl.DE,
        "api-fr.libreview.io":   APIUrl.FR,
        "api-ru.libreview.io":   APIUrl.RU,
        "api-au.libreview.io":   APIUrl.AU,
        "api-ca.libreview.io":   APIUrl.CA,
        "api-jp.libreview.io":   APIUrl.JP,
        "api-ap.libreview.io":   APIUrl.AP,
        "api-ae.libreview.io":   APIUrl.AE,
        "api-la.libreview.io":   APIUrl.LA,
    }
    for key, val in mapping.items():
        if key in url_str:
            return val
    log.warning(f"Unknown URL '{url_str}', defaulting to EU2")
    return APIUrl.EU2


def safe_trend(reading) -> int | None:
    """
    Extract integer trend value from a reading object robustly.
    Newer pylibrelinkup uses trend_direction (a Trend enum with .value),
    older versions used trend_arrow. Falls back gracefully.
    """
    # Try trend_direction first (current API)
    td = getattr(reading, "trend_direction", None)
    if td is not None:
        try:
            return int(td.value)
        except Exception:
            try:
                return int(td)
            except Exception:
                pass
    # Fallback: trend_arrow (older API)
    ta = getattr(reading, "trend_arrow", None)
    if ta is not None:
        try:
            return int(ta)
        except Exception:
            pass
    return None


def safe_mmol(reading) -> float | None:
    """
    Extract glucose value in mmol/L robustly.
    Newer API uses value_in_mmol, older uses value directly.
    """
    # Try value_in_mmol first (current API)
    vim = getattr(reading, "value_in_mmol", None)
    if vim is not None:
        try:
            return float(vim)
        except Exception:
            pass
    # Fallback: value (may be mg/dL or mmol/L depending on account)
    v = getattr(reading, "value", None)
    if v is not None:
        try:
            fv = float(v)
            # Heuristic: if value > 30 it's almost certainly mg/dL
            return round(fv / 18.016, 2) if fv > 30 else fv
        except Exception:
            pass
    return None


def safe_ts(reading) -> str | None:
    """Extract UTC ISO timestamp string."""
    ts = getattr(reading, "timestamp", None)
    if ts is None:
        return None
    try:
        return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        return str(ts)[:19]


def fetch_and_store():
    try:
        from pylibrelinkup import PyLibreLinkUp
    except ImportError:
        log.error("pylibrelinkup not installed. Run: pip install -r requirements.txt")
        return 0

    try:
        api_url = get_api_url(URL)
        client = PyLibreLinkUp(email=EMAIL, password=PASSWORD, api_url=api_url)
        client.authenticate()

        patients = client.get_patients()
        if not patients:
            log.warning("No patients/connections found. Enable sharing in the Libre 3 app.")
            return 0

        patient = patients[0]
        new_count = 0

        # ── Latest reading ─────────────────────────────────────
        try:
            latest = client.latest(patient_identifier=patient.patient_id)
            ts = safe_ts(latest)
            val = safe_mmol(latest)
            if ts and val:
                upsert_reading(ts=ts, value_mmol=val, trend=safe_trend(latest))
                new_count += 1
                log.info(f"Latest: {val} mmol/L @ {ts}")
        except Exception as e:
            log.warning(f"Could not fetch latest reading: {e}")

        # ── Graph history (~12h) ───────────────────────────────
        try:
            history = client.graph(patient_identifier=patient.patient_id)
            for r in history:
                ts = safe_ts(r)
                val = safe_mmol(r)
                if ts and val:
                    upsert_reading(ts=ts, value_mmol=val, trend=safe_trend(r))
                    new_count += 1
        except Exception as e:
            log.warning(f"Could not fetch graph history: {e}")

        # ── Logbook (~14 days) ────────────────────────────────
        try:
            logbook = client.logbook(patient_identifier=patient.patient_id)
            for r in logbook:
                ts = safe_ts(r)
                val = safe_mmol(r)
                if ts and val:
                    upsert_reading(ts=ts, value_mmol=val, trend=safe_trend(r))
                    new_count += 1
        except Exception as e:
            log.warning(f"Could not fetch logbook: {e}")

        log.info(f"Done — {new_count} readings processed (dupes silently skipped)")
        return new_count

    except Exception as e:
        log.error(f"Fetch failed: {e}")
        import traceback
        traceback.print_exc()
        return 0


def main():
    if not EMAIL or not PASSWORD:
        log.error("LIBRE_EMAIL and LIBRE_PASSWORD must be set in .env")
        log.error("Copy .env.example to .env and fill in your credentials.")
        return

    log.info(f"Glycles poller starting — polling every {INTERVAL // 60} min")
    log.info(f"Server: {URL}")
    init_db()

    # Fetch immediately on start
    fetch_and_store()

    while True:
        log.info(f"Sleeping {INTERVAL // 60} min…")
        time.sleep(INTERVAL)
        fetch_and_store()


if __name__ == "__main__":
    main()
