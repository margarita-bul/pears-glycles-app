"""
poller.py — Fetches glucose readings from LibreLinkUp every N minutes.

Run in a separate terminal:
  python poller.py

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

from db import init_db, upsert_reading, get_reading_count

EMAIL    = os.environ.get("LIBRE_EMAIL", "")
PASSWORD = os.environ.get("LIBRE_PASSWORD", "")
URL      = os.environ.get("LIBRE_URL", "https://api-eu2.libreview.io")
INTERVAL = int(os.environ.get("POLL_INTERVAL_MINUTES", 5)) * 60


def get_api_url(url_str: str):
    from pylibrelinkup.api_url import APIUrl
    mapping = {
        "api-eu.libreview.io":  APIUrl.EU,
        "api-eu2.libreview.io": APIUrl.EU2,
        "api-us.libreview.io":  APIUrl.US,
        "api-de.libreview.io":  APIUrl.DE,
        "api-fr.libreview.io":  APIUrl.FR,
        "api-ru.libreview.io":  APIUrl.RU,
        "api-au.libreview.io":  APIUrl.AU,
        "api-ca.libreview.io":  APIUrl.CA,
        "api-jp.libreview.io":  APIUrl.JP,
        "api-ap.libreview.io":  APIUrl.AP,
        "api-ae.libreview.io":  APIUrl.AE,
        "api-la.libreview.io":  APIUrl.LA,
    }
    for key, val in mapping.items():
        if key in url_str:
            return val
    log.warning(f"Unknown URL '{url_str}', defaulting to DE")
    return APIUrl.DE


def safe_trend(reading) -> int | None:
    td = getattr(reading, "trend_direction", None)
    if td is not None:
        try:
            return int(td.value)
        except Exception:
            try:
                return int(td)
            except Exception:
                pass
    ta = getattr(reading, "trend_arrow", None)
    if ta is not None:
        try:
            return int(ta)
        except Exception:
            pass
    return None


def safe_mmol(reading) -> float | None:
    vim = getattr(reading, "value_in_mmol", None)
    if vim is not None:
        try:
            return round(float(vim), 2)
        except Exception:
            pass
    v = getattr(reading, "value", None)
    if v is not None:
        try:
            fv = float(v)
            return round(fv / 18.016, 2) if fv > 30 else fv
        except Exception:
            pass
    return None


def safe_ts(reading) -> str | None:
    ts = getattr(reading, "timestamp", None)
    if ts is None:
        return None
    try:
        return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        return str(ts)[:19]


def store_readings(readings: list, label: str) -> int:
    """Store a list of reading objects, return count of new ones."""
    stored = 0
    for r in readings:
        ts  = safe_ts(r)
        val = safe_mmol(r)
        if ts and val:
            upsert_reading(ts=ts, value_mmol=val, trend=safe_trend(r))
            stored += 1
    if stored:
        log.info(f"  {label}: {stored} readings stored")
    return stored


def poll(client, patient_id) -> int:
    """Run one poll cycle. Returns total new readings stored."""
    total = 0

    # Latest single reading
    try:
        latest = client.latest(patient_identifier=patient_id)
        ts  = safe_ts(latest)
        val = safe_mmol(latest)
        if ts and val:
            upsert_reading(ts=ts, value_mmol=val, trend=safe_trend(latest))
            log.info(f"  Latest: {val} mmol/L @ {ts}")
            total += 1
    except Exception as e:
        log.warning(f"  latest() failed: {e}")

    # Graph — last ~12h at full 5-min resolution
    try:
        history = client.graph(patient_identifier=patient_id)
        total += store_readings(history, "graph (~12h)")
    except Exception as e:
        log.warning(f"  graph() failed: {e}")

    return total


def main():
    if not EMAIL or not PASSWORD:
        log.error("LIBRE_EMAIL and LIBRE_PASSWORD must be set in .env")
        return

    log.info(f"Glycles poller starting — polling every {INTERVAL // 60} min")
    log.info(f"Server: {URL}")
    init_db()

    from pylibrelinkup import PyLibreLinkUp

    api_url = get_api_url(URL)
    client  = PyLibreLinkUp(email=EMAIL, password=PASSWORD, api_url=api_url)

    # Authenticate once
    try:
        client.authenticate()
        log.info("Authenticated successfully")
    except Exception as e:
        log.error(f"Authentication failed: {e}")
        return

    # Get patient ID once
    try:
        patients = client.get_patients()
        if not patients:
            log.error("No patients found. Enable LibreLinkUp sharing in the Libre 3 app.")
            return
        patient_id = patients[0].patient_id
        log.info(f"Connected to patient: {patient_id}")
    except Exception as e:
        log.error(f"Could not get patient list: {e}")
        return

    log.info(f"Database has {get_reading_count()} readings so far.")

    # First poll immediately
    poll(client, patient_id)
    log.info(f"Database now has {get_reading_count()} readings total.")

    # Then loop
    while True:
        log.info(f"Sleeping {INTERVAL // 60} min…")
        time.sleep(INTERVAL)

        try:
            poll(client, patient_id)
        except Exception as e:
            log.warning(f"Poll failed ({e}) — re-authenticating…")
            try:
                client.authenticate()
                poll(client, patient_id)
            except Exception as e2:
                log.error(f"Re-auth also failed: {e2}")

        log.info(f"Database now has {get_reading_count()} readings total.")


if __name__ == "__main__":
    main()
