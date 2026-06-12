# Glycles — Local Testing App

A local-only glucose + cycle dashboard pulling data from LibreLinkUp.
Everything runs on your machine. No accounts, no cloud, no deployment.

---

## Requirements

- Python 3.9+
- A LibreLinkUp account (free) with your Libre 3 connected to it
- Your FreeStyle Libre 3 app must already be sharing to LibreLinkUp

---

## Setup (one time)

```bash
# 1. Create a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy the example env file and fill in your credentials
cp .env.example .env
# Open .env in any text editor and add your LibreLinkUp email + password
```

---

## Running

You need **two terminals** running at the same time:

**Terminal 1 — Glucose poller** (fetches data every 5 min):
```bash
source venv/bin/activate
python poller.py
```

**Terminal 2 — Dashboard**:
```bash
source venv/bin/activate
python app.py
```

Then open **http://localhost:5000** in your browser.

---

## First use

1. Start the poller — it immediately fetches your latest readings + ~12h of history
2. Open the dashboard at localhost:5000
3. Go to **Cycle dates** at the bottom and add your period start dates
4. The timeline, phase stats, and trend charts update automatically

---

## EU server note

Germany uses `https://api-eu2.libreview.io` — already set as default in `.env.example`.
If you get authentication errors, try `https://api-eu.libreview.io`.

---

## Data

All data is stored in `glycles.db` (SQLite) in this folder.
- `glucose_readings` table: timestamp, mmol/L value, trend arrow
- `cycles` table: period start dates and cycle lengths

To export your data as CSV at any time:
```bash
sqlite3 -csv -header glycles.db "SELECT * FROM glucose_readings ORDER BY ts;" > glucose.csv
```

---

## Stopping

Press `Ctrl+C` in each terminal.

---

## Privacy

Everything stays local. No data is sent anywhere except to LibreLinkUp's API
(which is Abbott's own cloud — same as the LibreLinkUp app itself uses).
Your credentials are only in the `.env` file on your machine.
Never commit `.env` to git.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `No patients found` | In the Libre 3 app, go to Connected Apps → make sure LibreLinkUp sharing is enabled |
| `Authentication failed` | Double-check email/password in `.env`. Try logging into librelinkup.com manually |
| `Module not found` | Make sure you activated the venv: `source venv/bin/activate` |
| EU server error | Try changing `LIBRE_URL` in `.env` to `https://api-eu.libreview.io` |
| No data on dashboard | Wait for the poller to run once, then refresh |
