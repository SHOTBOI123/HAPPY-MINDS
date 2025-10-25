from flask import Flask, render_template, request, redirect, url_for
import os
import sqlite3
import requests
from datetime import datetime

# -----------------------------
# Config
# -----------------------------
ANALYZE_URL = os.getenv("ANALYZE_URL", "http://127.0.0.1:8000/analyze")
DB_PATH = os.path.join("db", "app.db")

app = Flask(__name__)

# -----------------------------
# DB helpers
# -----------------------------
def init_db():
    os.makedirs("db", exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                entry TEXT NOT NULL,
                mood TEXT NOT NULL,
                affirmation TEXT NOT NULL
            )
        """)
        conn.commit()

def insert_row(ts: str, entry: str, mood: str, affirmation: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO journal (timestamp, entry, mood, affirmation) VALUES (?, ?, ?, ?)",
            (ts, entry, mood, affirmation)
        )
        conn.commit()

# -----------------------------
# Routes
# -----------------------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/entry")
def entry():
    return render_template("entry.html")

@app.route("/mood-tracker")
def mood_tracker():
    # optional: show recent rows
    rows = []
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute(
                "SELECT timestamp, entry, mood, affirmation FROM journal ORDER BY id DESC LIMIT 20"
            )
            rows = cur.fetchall()
    except Exception:
        pass
    return render_template("mood-tracker.html", rows=rows)

@app.route("/submit", methods=["POST"])
def submit_entry():
    journal_entry = (request.form.get("journal-entry") or "").strip()
    if not journal_entry:
        return redirect(url_for("mood_tracker"))

    # ISO8601 UTC timestamp (e.g., 2025-10-25T17:55:03Z)
    ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    # Call FastAPI analyzer
    try:
        r = requests.post(ANALYZE_URL, json={"text": journal_entry}, timeout=30)
        r.raise_for_status()
        data = r.json()
        mood = str(data.get("emotion", "unknown"))
        affirmation = str(data.get("affirmation", ""))
    except Exception:
        mood = "unknown"
        affirmation = "Analysis unavailable right now."

    # Store one row: timestamp, entry, mood, affirmation
    insert_row(ts, journal_entry, mood, affirmation)

    return redirect(url_for("mood_tracker"))

# -----------------------------
# App start
# -----------------------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5001)
