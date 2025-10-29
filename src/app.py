"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
from pathlib import Path
import sqlite3
from typing import Dict, Any, List

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

# SQLite DB path
DB_PATH = current_dir.parent.joinpath("data.db")

# Initial in-memory activities used to bootstrap the DB if empty
INITIAL_ACTIVITIES: Dict[str, Dict[str, Any]] = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


def get_db_conn():
    """Return a sqlite3 connection (creates DB file if necessary)."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables and bootstrap initial activities if empty."""
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS activities (
            name TEXT PRIMARY KEY,
            description TEXT,
            schedule TEXT,
            max_participants INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_name TEXT,
            email TEXT,
            UNIQUE(activity_name, email)
        )
        """
    )
    conn.commit()

    # If activities table is empty, insert initial activities
    cur.execute("SELECT COUNT(*) as c FROM activities")
    row = cur.fetchone()
    if row and row["c"] == 0:
        for name, data in INITIAL_ACTIVITIES.items():
            cur.execute(
                "INSERT INTO activities (name, description, schedule, max_participants) VALUES (?, ?, ?, ?)",
                (name, data["description"], data["schedule"], data["max_participants"]),
            )
            for email in data.get("participants", []):
                try:
                    cur.execute(
                        "INSERT INTO participants (activity_name, email) VALUES (?, ?)",
                        (name, email),
                    )
                except sqlite3.IntegrityError:
                    pass
        conn.commit()

    conn.close()


# Initialize DB on import/start
init_db()


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


def build_activity_dict(rows: List[sqlite3.Row]) -> Dict[str, Any]:
    """Helper to build activity dict from DB rows."""
    result: Dict[str, Any] = {}
    for r in rows:
        name = r["name"]
        result[name] = {
            "description": r["description"],
            "schedule": r["schedule"],
            "max_participants": r["max_participants"],
            "participants": []
        }
    return result


@app.get("/activities")
def get_activities():
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT name, description, schedule, max_participants FROM activities")
    activities = build_activity_dict(cur.fetchall())

    # Load participants
    cur.execute("SELECT activity_name, email FROM participants")
    for row in cur.fetchall():
        aname = row["activity_name"]
        if aname in activities:
            activities[aname]["participants"].append(row["email"])

    conn.close()
    return activities


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity (persisted to SQLite)."""
    conn = get_db_conn()
    cur = conn.cursor()

    # Validate activity exists
    cur.execute("SELECT max_participants FROM activities WHERE name = ?", (activity_name,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Activity not found")

    max_p = row["max_participants"]

    # Check if already signed up
    cur.execute("SELECT 1 FROM participants WHERE activity_name = ? AND email = ?", (activity_name, email))
    if cur.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Student is already signed up")

    # Enforce capacity
    cur.execute("SELECT COUNT(*) as c FROM participants WHERE activity_name = ?", (activity_name,))
    count = cur.fetchone()["c"]
    if max_p is not None and count >= max_p:
        conn.close()
        raise HTTPException(status_code=400, detail="Activity is full")

    # Insert participant
    try:
        cur.execute("INSERT INTO participants (activity_name, email) VALUES (?, ?)", (activity_name, email))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Student is already signed up")

    conn.close()
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str):
    """Unregister a student from an activity (persisted to SQLite)."""
    conn = get_db_conn()
    cur = conn.cursor()

    # Validate activity exists
    cur.execute("SELECT 1 FROM activities WHERE name = ?", (activity_name,))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Activity not found")

    # Validate student is signed up
    cur.execute("SELECT id FROM participants WHERE activity_name = ? AND email = ?", (activity_name, email))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=400, detail="Student is not signed up for this activity")

    cur.execute("DELETE FROM participants WHERE id = ?", (row["id"],))
    conn.commit()
    conn.close()
    return {"message": f"Unregistered {email} from {activity_name}"}
