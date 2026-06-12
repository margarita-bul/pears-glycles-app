"""
poller.py — Fetches glucose readings from LibreLinkUp every N minutes.
Run this in a separate terminal: python poller.py

It will keep running and storing readings in glycles.db.
Press Ctrl+C to stop.
"""
import os
import time
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [poller] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

from db import init_db, upsert_reading, get_latest_reading

EMAIL    = os.environ.get("LIBRE_EMAIL", "")
PASSWORD = os.environ.get("LIBRE_PASSWORD", "")
URL      = os.environ.get("LIBRE_URL", "https://api-eu2.libreview.io")
INTERVAL = int(os.environ.get("POLL_INTERVAL_MINUTES", 5)) * 60  # seconds


def fetch_and_store():
    """Authenticate, fetch latest readings, store new ones."""
    try:
        from pylibrelinkup import PyLibreLinkUp
    except ImportError:
        log.error("pylibrelinkup not installed. Run: pip install -r requirements.txt")
        return 0

    try:
        client = PyLibreLinkUp(email=EMAIL, password=PASSWORD)
        client.authenticate()

        patients = client.get_patients()
        if not patients:
            log.warning("No patients/connections found in LibreLinkUp account.")
            return 0

        patient = patients[0]
        data = client.read(patient_identifier=patient.patient_id)

        new_count = 0

        # Store current reading
        if data.current:
            ts = data.current.timestamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
            upsert_reading(
                ts=ts,
                value_mmol=float(data.current.value),
                trend=int(data.current.trend_arrow) if data.current.trend_arrow else None
            )
            new_count += 1

        # Store history
        if data.history:
            for reading in data.history:
                ts = reading.timestamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
                upsert_reading(
                    ts=ts,
                    value_mmol=float(reading.value),
                    trend=int(reading.trend_arrow) if reading.trend_arrow else None
                )
                new_count += 1

        log.info(f"Fetched {new_count} readings (dupes silently skipped). "
                 f"Latest: {data.current.value:.1f} mmol/L" if data.current else "")
        return new_count

    except Exception as e:
        log.error(f"Fetch failed: {e}")
        return 0


def main():
    if not EMAIL or not PASSWORD:
        log.error("LIBRE_EMAIL and LIBRE_PASSWORD must be set in .env")
        return

    log.info(f"Starting poller — fetching every {INTERVAL // 60} min from {URL}")
    init_db()

    # Fetch immediately on start
    fetch_and_store()

    while True:
        log.info(f"Sleeping {INTERVAL // 60} min until next poll…")
        time.sleep(INTERVAL)
        fetch_and_store()


if __name__ == "__main__":
    main()
