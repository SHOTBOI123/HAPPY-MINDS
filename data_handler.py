# data_handler.py
"""
Handles all database logic for the Happy Minds backend.


Database columns:
- timestamp
- entry
- mood
- affirmation
"""


import sqlite3
from datetime import datetime


DB_PATH = "db/app.db"




# -------------------------------------------------
#  Database Setup
# -------------------------------------------------
def init_db():
   """
   Creates the 'entries' table if it doesn't already exist.
   No ID column — just timestamp, entry, mood, and affirmation.
   """
   con = sqlite3.connect(DB_PATH)
   con.execute("""
       CREATE TABLE IF NOT EXISTS entries (
           timestamp TEXT,
           entry TEXT,
           mood TEXT,
           affirmation TEXT
       )
   """)
   con.commit()
   con.close()




# -------------------------------------------------
#  Return Current Mood for UI
# -------------------------------------------------
def get_current_mood():
   """
   Returns the most recent mood and affirmation.
   Example output:
   {
       "mood": "anxiety",
       "affirmation": "You’ve handled hard things before—this is another step.",
       "timestamp": "Oct 25, 2025 05:40 PM"
   }
   """
   con = sqlite3.connect(DB_PATH)
   cur = con.execute("SELECT mood, affirmation, timestamp FROM entries ORDER BY timestamp DESC LIMIT 1")
   row = cur.fetchone()
   con.close()


   if not row:
       return {"mood": "none", "affirmation": "No entries yet!", "timestamp": None}


   mood, affirmation, timestamp = row
   # Format timestamp nicely
   try:
       formatted_time = datetime.fromisoformat(timestamp).strftime("%b %d, %Y %I:%M %p")
   except:
       formatted_time = timestamp


   return {
       "mood": mood,
       "affirmation": affirmation,
       "timestamp": formatted_time
   }




# -------------------------------------------------
#  Return Entire Log for UI
# -------------------------------------------------
def get_log_entries():
   """
   Returns all journal entries, formatted for the UI.
   Example output:
   [
       {
           "timestamp": "Oct 25, 2025 05:40 PM",
           "mood": "anxiety",
           "entry": "I'm nervous about the exam but hopeful.",
           "affirmation": "You’ve handled hard things before—this is another step."
       },
       ...
   ]
   """
   con = sqlite3.connect(DB_PATH)
   cur = con.execute("SELECT timestamp, mood, entry, affirmation FROM entries ORDER BY timestamp DESC")
   rows = cur.fetchall()
   con.close()


   formatted = []
   for r in rows:
       timestamp, mood, entry, affirmation = r
       try:
           formatted_time = datetime.fromisoformat(timestamp).strftime("%b %d, %Y %I:%M %p")
       except:
           formatted_time = timestamp


       formatted.append({
           "timestamp": formatted_time,
           "mood": mood,
           "entry": entry,
           "affirmation": affirmation
       })
   return formatted

# -------------------------------------------------
#  Clear Data for Testing
# -------------------------------------------------
def clear_entries():
   """
   Deletes all data in the entries table.
   Use this only for testing or resetting the demo database.
   """
   con = sqlite3.connect(DB_PATH)
   con.execute("DELETE FROM entries")
   con.commit()
   con.close()
