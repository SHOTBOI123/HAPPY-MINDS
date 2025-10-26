from flask import Flask, render_template, request, redirect, url_for, jsonify
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

def fetch_recent_rows(limit: int = 20):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "SELECT timestamp, entry, mood, affirmation FROM journal ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        return cur.fetchall()

def fetch_all_rows():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "SELECT timestamp, entry, mood, affirmation FROM journal ORDER BY id DESC"
        )
        return cur.fetchall()

def fetch_latest_mood():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "SELECT timestamp, mood, affirmation FROM journal ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
        if not row:
            return None
        # row: (timestamp, mood, affirmation)
        return {"timestamp": row[0], "mood": row[1], "affirmation": row[2]}

# -----------------------------
# Routes (HTML)
# -----------------------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/entry")
def entry():
    return render_template("entry.html")

@app.route("/all-entries")
def all_entries():
    """
    Displays a list of all past journal entries.
    Template: templates/all-entries.html
    Passes: entries = [(timestamp, entry, mood, affirmation), ...]
    """
    try:
        entries = fetch_all_rows()
    except Exception as e:
        print("Error loading entries:", e)
        entries = []
    return render_template("all-entries.html", entries=entries)

@app.route("/mood-tracker")
def mood_tracker():
    try:
        entries = fetch_all_rows()  # [(timestamp, entry, mood, affirmation), ...]
    except Exception as e:
        print("Error loading entries:", e)
        entries = []
    return render_template("mood-tracker.html",
                           entries=entries,
                           analyze_url="/analyze-and-save")

# -----------------------------
# Routes (JSON APIs)
# -----------------------------
@app.get("/current-mood")
def current_mood():
    """Returns the most recent mood and affirmation (JSON)."""
    latest = fetch_latest_mood()
    if latest is None:
        return jsonify({"timestamp": None, "mood": "unknown", "affirmation": ""})
    return jsonify(latest)

@app.get("/log")
def get_log():
    rows = fetch_all_rows()  # [(timestamp, entry, mood, affirmation), ...]
    return jsonify([
        {"timestamp": ts, "entry": entry, "mood": mood, "affirmation": affirmation}
        for (ts, entry, mood, affirmation) in rows
    ])

# -----------------------------
# Submit (calls analyzer, stores one row)
# -----------------------------
@app.route("/submit", methods=["POST"])
def submit_entry():
    journal_entry = (request.form.get("journal-entry") or "").strip()
    if not journal_entry:
        return redirect(url_for("mood_tracker"))

    # ISO8601 UTC timestamp
    ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    # Call FastAPI analyzer
    try:
        r = requests.post(ANALYZE_URL, json={"text": journal_entry}, timeout=30)
        r.raise_for_status()
        data = r.json()
        mood = str(data.get("emotion", "unknown"))
        affirmation = str(data.get("affirmation", "")) or ""
    except Exception as e:
        print("Analyzer error:", e)
        mood = "unknown"
        affirmation = "Analysis unavailable right now."

    # Store in DB
    try:
        insert_row(ts, journal_entry, mood, affirmation)
    except Exception as e:
        print("DB insert error:", e)

    return redirect(url_for("mood_tracker"))

@app.post("/analyze-and-save")
def analyze_and_save():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    try:
        r = requests.post(ANALYZE_URL, json={"text": text}, timeout=30)
        r.raise_for_status()
        model = r.json()
        mood = str(model.get("emotion", "unknown"))
        affirmation = str(model.get("affirmation", "")) or ""
    except Exception as e:
        app.logger.exception("Analyzer error")
        mood = "unknown"
        affirmation = "Analysis unavailable right now."
        model = {"emotion": mood, "confidence": 0.0, "scores": {}, "top_words": [], "affirmation": affirmation}

    try:
        insert_row(ts, text, mood, affirmation)
    except Exception as e:
        app.logger.exception("DB insert error")

    # return the same shape your frontend expects
    return jsonify(model), 200

# -----------------------------
# App start
# -----------------------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5001)
