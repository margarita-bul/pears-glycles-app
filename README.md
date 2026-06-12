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

Open PowerShell or Command Prompt in the project folder, then:

```powershell
# 1. Create a virtual environment
python -m venv venv

# 2. Activate it (Windows PowerShell)
venv\Scripts\Activate.ps1

# If you get a permissions error, run this first:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Then try again:
venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy the example env file
copy .env.example .env
# Open .env in Notepad and fill in your LibreLinkUp email + password
notepad .env
```

---

## Running

You need **two PowerShell windows** open at the same time, both in the project folder.

**Window 1 — Glucose poller** (fetches data every 5 min, runs forever):
```powershell
venv\Scripts\Activate.ps1
python poller.py
```

**Window 2 — Dashboard**:
```powershell
venv\Scripts\Activate.ps1
python app.py
```

Then open **http://localhost:5000** in your browser.

---

## First use

1. Start the poller — it fetches your latest readings + ~14 days of history immediately
2. Open the dashboard at localhost:5000
3. Add your period start dates in the **Cycle dates** section at the bottom
4. Charts update automatically every 5 minutes

---

## EU server note

Germany uses `https://api-eu2.libreview.io` — already set as default in `.env.example`.
If you get authentication errors, try changing to `https://api-eu.libreview.io`.

---

## Data

All data is stored in `glycles.db` (SQLite) in this folder.
To export as CSV at any time, install SQLite tools or use DB Browser for SQLite (free GUI).

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `source not recognized` | Use `venv\Scripts\Activate.ps1` on Windows, not `source` |
| `ExecutionPolicy` error | Run `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` once |
| `No patients found` | In Libre 3 app → Connected Apps → enable LibreLinkUp sharing |
| Auth failed | Check email/password in `.env`. Log into librelinkup.com manually to verify |
| Wrong glucose values | If values look like 80–200 instead of 4–12, try `api-eu.libreview.io` |
| No data on dashboard | Wait for poller to complete one run, then refresh the browser |
| `Module not found` | Make sure venv is activated: you should see `(venv)` in the prompt |
