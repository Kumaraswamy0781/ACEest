"""Flask version 1.1 of the ACEest fitness program viewer."""

import math
import os
import sqlite3
from datetime import date

from flask import Flask, abort, jsonify, redirect, render_template, request


# Content carried over from Aceestver-1.0.py. There are no client records in v1.
PROGRAMS = {
    "fat-loss": {
        "name": "Fat Loss (FL)",
        "workout": (
            "Mon: 5x5 Back Squat + AMRAP\n"
            "Tue: EMOM 20min Assault Bike\n"
            "Wed: Bench Press + 21-15-9\n"
            "Thu: 10RFT Deadlifts/Box Jumps\n"
            "Fri: 30min Active Recovery"
        ),
        "diet": (
            "B: 3 Egg Whites + Oats Idli\n"
            "L: Grilled Chicken + Brown Rice\n"
            "D: Fish Curry + Millet Roti\n"
            "Target: 2,000 kcal"
        ),
        "color": "#e74c3c",
        "calorie_factor": 22,
    },
    "muscle-gain": {
        "name": "Muscle Gain (MG)",
        "workout": (
            "Mon: Squat 5x5\n"
            "Tue: Bench 5x5\n"
            "Wed: Deadlift 4x6\n"
            "Thu: Front Squat 4x8\n"
            "Fri: Incline Press 4x10\n"
            "Sat: Barbell Rows 4x10"
        ),
        "diet": (
            "B: 4 Eggs + PB Oats\n"
            "L: Chicken Biryani (250g Chicken)\n"
            "D: Mutton Curry + Jeera Rice\n"
            "Target: 3,200 kcal"
        ),
        "color": "#2ecc71",
        "calorie_factor": 35,
    },
    "beginner": {
        "name": "Beginner (BG)",
        "workout": (
            "Circuit Training: Air Squats, Ring Rows, Push-ups.\n"
            "Focus: Technique Mastery & Form (90% Threshold)"
        ),
        "diet": (
            "Balanced Tamil Meals: Idli-Sambar, Rice-Dal, Chapati.\n"
            "Protein: 120g/day"
        ),
        "color": "#3498db",
        "calorie_factor": 26,
    },
}


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.environ.get("ACEEST_DATABASE", os.path.join(app.instance_path, "aceest_fitness.db")),
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    def connect_db():
        connection = sqlite3.connect(app.config["DATABASE"])
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize_db():
        with connect_db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS clients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    age INTEGER NOT NULL CHECK (age > 0),
                    weight REAL NOT NULL CHECK (weight > 0),
                    program TEXT NOT NULL,
                    calories INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                    week TEXT NOT NULL,
                    adherence INTEGER NOT NULL CHECK (adherence BETWEEN 0 AND 100),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            """)

    initialize_db()

    @app.get("/")
    def index():
        program_id = request.args.get("program")
        if program_id and program_id not in PROGRAMS:
            abort(404)
        with connect_db() as db:
            clients = db.execute("SELECT * FROM clients ORDER BY name").fetchall()
            selected_client = None
            history = []
            client_id = request.args.get("client_id", type=int)
            if client_id:
                selected_client = db.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
                if selected_client:
                    history = db.execute(
                        "SELECT week, adherence FROM progress WHERE client_id = ? ORDER BY id DESC",
                        (client_id,),
                    ).fetchall()
        return render_template(
            "index.html",
            programs=PROGRAMS,
            selected_id=program_id,
            selected=PROGRAMS.get(program_id),
            values={},
            client=None,
            errors={},
            clients=clients,
            selected_client=selected_client,
            history=history,
            message=request.args.get("message"),
        )

    @app.post("/")
    def save_client():
        values = {
            "name": request.form.get("name", "").strip(),
            "age": request.form.get("age", "").strip(),
            "weight": request.form.get("weight", "").strip(),
            "program": request.form.get("program", "").strip(),
            "adherence": request.form.get("adherence", "0").strip(),
        }
        errors = {}

        if not values["name"]:
            errors["name"] = "Enter the client's name."
        if values["program"] not in PROGRAMS:
            errors["program"] = "Choose one of the listed programs."

        age = None
        try:
            age = int(values["age"])
            if age < 1:
                errors["age"] = "Age must be a positive whole number."
        except ValueError:
            errors["age"] = "Enter age as a positive whole number."

        weight = None
        try:
            weight = float(values["weight"])
            if not math.isfinite(weight) or weight <= 0:
                errors["weight"] = "Weight must be a positive number."
        except ValueError:
            errors["weight"] = "Enter weight as a positive number."

        adherence = None
        try:
            adherence = int(values["adherence"])
            if not 0 <= adherence <= 100:
                errors["adherence"] = "Adherence must be between 0 and 100."
        except ValueError:
            errors["adherence"] = "Enter adherence as a whole number from 0 to 100."

        selected = PROGRAMS.get(values["program"])
        client = None
        if not errors:
            calories = int(weight * selected["calorie_factor"])
            with connect_db() as db:
                db.execute("""
                    INSERT INTO clients (name, age, weight, program, calories)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        age = excluded.age, weight = excluded.weight,
                        program = excluded.program, calories = excluded.calories
                """, (values["name"], age, weight, selected["name"], calories))
                saved = db.execute("SELECT * FROM clients WHERE name = ?", (values["name"],)).fetchone()
                db.execute(
                    "INSERT INTO progress (client_id, week, adherence) VALUES (?, ?, ?)",
                    (saved["id"], date.today().strftime("Week %U - %Y"), adherence),
                )
                client = dict(saved)
                client.update(adherence=adherence)
                clients = db.execute("SELECT * FROM clients ORDER BY name").fetchall()
                history = db.execute(
                    "SELECT week, adherence FROM progress WHERE client_id = ? ORDER BY id DESC",
                    (saved["id"],),
                ).fetchall()
        else:
            clients, history = [], []

        return render_template(
            "index.html",
            programs=PROGRAMS,
            selected_id=values["program"],
            selected=selected,
            values=values,
            client=client,
            errors=errors,
            clients=clients,
            selected_client=client,
            history=history,
            message=None,
        ), (400 if errors else 200)

    @app.post("/progress")
    def save_progress():
        client_id = request.form.get("client_id", type=int)
        try:
            adherence = int(request.form.get("adherence", ""))
        except ValueError:
            abort(400)
        if not 0 <= adherence <= 100:
            abort(400)
        with connect_db() as db:
            exists = db.execute("SELECT id FROM clients WHERE id = ?", (client_id,)).fetchone()
            if not exists:
                abort(404)
            db.execute(
                "INSERT INTO progress (client_id, week, adherence) VALUES (?, ?, ?)",
                (client_id, date.today().strftime("Week %U - %Y"), adherence),
            )
        return redirect(f"/?client_id={client_id}&message=Progress+saved")

    @app.get("/api/clients")
    def list_clients():
        with connect_db() as db:
            rows = db.execute("SELECT * FROM clients ORDER BY name").fetchall()
        return jsonify([dict(row) for row in rows])

    @app.get("/api/clients/<int:client_id>/progress")
    def client_progress(client_id):
        with connect_db() as db:
            exists = db.execute("SELECT id FROM clients WHERE id = ?", (client_id,)).fetchone()
            if not exists:
                abort(404)
            rows = db.execute(
                "SELECT week, adherence, created_at FROM progress WHERE client_id = ? ORDER BY id",
                (client_id,),
            ).fetchall()
        return jsonify([dict(row) for row in rows])

    @app.get("/api/programs")
    def list_programs():
        return jsonify([
            {"id": program_id, "name": program["name"]}
            for program_id, program in PROGRAMS.items()
        ])

    @app.get("/api/programs/<program_id>")
    def get_program(program_id):
        program = PROGRAMS.get(program_id)
        if program is None:
            abort(404)
        return jsonify({"id": program_id, **program})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
