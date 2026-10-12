"""Flask version 1.1 of the ACEest fitness program viewer."""

import math

from flask import Flask, abort, jsonify, render_template, request


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


def create_app():
    app = Flask(__name__)

    @app.get("/")
    def index():
        program_id = request.args.get("program")
        if program_id and program_id not in PROGRAMS:
            abort(404)
        return render_template(
            "index.html",
            programs=PROGRAMS,
            selected_id=program_id,
            selected=PROGRAMS.get(program_id),
            values={},
            client=None,
            errors={},
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
            client = {
                "name": values["name"],
                "age": age,
                "weight": weight,
                "program": selected["name"],
                "adherence": adherence,
                "calories": int(weight * selected["calorie_factor"]),
            }

        return render_template(
            "index.html",
            programs=PROGRAMS,
            selected_id=values["program"],
            selected=selected,
            values=values,
            client=client,
            errors=errors,
        ), (400 if errors else 200)

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

