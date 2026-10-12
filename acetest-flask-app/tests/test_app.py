"""Tests for the ACEest Flask app version 2.0.1."""

import sqlite3

import pytest

from app import create_app


@pytest.fixture

def client(tmp_path):
    """Create a test client backed by a fresh database for each test."""
    database = tmp_path / "test_aceest.db"
    app = create_app({"TESTING": True, "DATABASE": str(database)})
    with app.test_client() as test_client:
        yield test_client


def valid_profile(**overrides):
    profile = {
        "name": "Asha",
        "age": "30",
        "weight": "70",
        "program": "fat-loss",
        "adherence": "85",
    }
    profile.update(overrides)
    return profile


def create_profile(client, **overrides):
    return client.post("/", data=valid_profile(**overrides))


def test_home_page_loads_with_client_management_form(client):
    response = client.get("/")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Client management" in page


@pytest.mark.parametrize(
    "program_id, expected_name, expected_workout, expected_diet",
    [
        ("fat-loss", "Fat Loss (FL)", "5x5 Back Squat + AMRAP", "3 Egg Whites + Oats Idli"),
        ("muscle-gain", "Muscle Gain (MG)", "Squat 5x5", "Chicken Biryani (250g Chicken)"),
        ("beginner", "Beginner (BG)", "Air Squats, Ring Rows, Push-ups", "Idli-Sambar"),
    ],
)
def test_selected_program_displays_workout_and_diet(
    client, program_id, expected_name, expected_workout, expected_diet
):
    response = client.get("/", query_string={"program": program_id})
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert expected_name in page
    assert expected_workout in page
    assert expected_diet in page


def test_program_list_api_returns_programs(client):
    response = client.get("/api/programs")

    assert response.status_code == 200
    assert response.json == [
        {"id": "fat-loss", "name": "Fat Loss (FL)"},
        {"id": "muscle-gain", "name": "Muscle Gain (MG)"},
        {"id": "beginner", "name": "Beginner (BG)"},
    ]


@pytest.mark.parametrize(
    "program_id, expected_name, expected_workout, expected_diet",
    [
        ("fat-loss", "Fat Loss (FL)", "5x5 Back Squat + AMRAP", "3 Egg Whites + Oats Idli"),
        ("muscle-gain", "Muscle Gain (MG)", "Squat 5x5", "Chicken Biryani (250g Chicken)"),
        ("beginner", "Beginner (BG)", "Air Squats, Ring Rows, Push-ups", "Idli-Sambar"),
    ],
)
def test_program_detail_api_returns_selected_program(
    client, program_id, expected_name, expected_workout, expected_diet
):
    response = client.get(f"/api/programs/{program_id}")

    assert response.status_code == 200
    assert response.json["id"] == program_id
    assert response.json["name"] == expected_name
    assert expected_workout in response.json["workout"]
    assert expected_diet in response.json["diet"]


@pytest.mark.parametrize("url", ["/?program=unknown", "/api/programs/unknown"])
def test_unknown_program_returns_404(client, url):
    assert client.get(url).status_code == 404


def test_stylesheet_is_served(client):
    response = client.get("/static/style.css")

    assert response.status_code == 200
    assert b".site-header" in response.data


@pytest.mark.parametrize(
    "program_id, expected_calories",
    [("fat-loss", 1540), ("muscle-gain", 2450), ("beginner", 1820)],
)
def test_valid_profile_is_saved_with_calorie_estimate(client, program_id, expected_calories):
    response = create_profile(client, program=program_id)
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Client summary" in page
    assert "Asha" in page
    assert "85%" in page
    assert f"{expected_calories} kcal/day" in page
    assert "local SQLite database" in page


def test_saved_client_remains_available_after_next_request(client):
    create_profile(client)

    response = client.get("/")
    assert response.status_code == 200
    assert "Asha" in response.get_data(as_text=True)
    assert len(client.get("/api/clients").json) == 1


def test_client_list_api_returns_saved_profile_fields(client):
    create_profile(client)

    response = client.get("/api/clients")

    assert response.status_code == 200
    assert len(response.json) == 1
    saved = response.json[0]
    assert saved["name"] == "Asha"
    assert saved["age"] == 30
    assert saved["weight"] == 70
    assert saved["program"] == "Fat Loss (FL)"
    assert saved["calories"] == 1540


def test_profile_submission_saves_initial_adherence(client):
    create_profile(client)
    saved_client = client.get("/api/clients").json[0]

    response = client.get(f"/api/clients/{saved_client['id']}/progress")

    assert response.status_code == 200
    assert len(response.json) == 1
    assert response.json[0]["adherence"] == 85


def test_client_can_save_another_weekly_progress_record(client):
    create_profile(client)
    saved_client = client.get("/api/clients").json[0]

    response = client.post(
        "/progress",
        data={"client_id": str(saved_client["id"]), "adherence": "92"},
    )

    assert response.status_code == 302
    history = client.get(f"/api/clients/{saved_client['id']}/progress").json
    assert [entry["adherence"] for entry in history] == [85, 92]


def test_saving_existing_name_updates_profile_without_duplicate(client):
    create_profile(client, age="30")
    create_profile(client, age="31", weight="72", adherence="90")

    profiles = client.get("/api/clients").json

    assert len(profiles) == 1
    assert profiles[0]["age"] == 31
    assert profiles[0]["weight"] == 72
    history = client.get(f"/api/clients/{profiles[0]['id']}/progress").json
    assert [entry["adherence"] for entry in history] == [85, 90]


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": "   "},
        {"age": "zero"},
        {"age": "0"},
        {"weight": "-5"},
        {"weight": "nan"},
        {"program": "unknown"},
        {"adherence": "101"},
    ],
)
def test_invalid_profile_submission_is_rejected(client, overrides):
    response = create_profile(client, **overrides)

    assert response.status_code == 400
    assert b"field-error" in response.data
    assert client.get("/api/clients").json == []


def test_progress_for_unknown_client_returns_404(client):
    response = client.get("/api/clients/999/progress")

    assert response.status_code == 404


def test_progress_submission_for_unknown_client_returns_404(client):
    response = client.post("/progress", data={"client_id": "999", "adherence": "50"})

    assert response.status_code == 404


@pytest.mark.parametrize("adherence", ["-1", "101", "not-a-number", ""])
def test_invalid_progress_submission_returns_400(client, adherence):
    create_profile(client)
    client_id = client.get("/api/clients").json[0]["id"]

    response = client.post(
        "/progress", data={"client_id": str(client_id), "adherence": adherence}
    )

    assert response.status_code == 400


def test_database_has_client_and_progress_tables(client):
    database = client.application.config["DATABASE"]
    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert {"clients", "progress"}.issubset(tables)

