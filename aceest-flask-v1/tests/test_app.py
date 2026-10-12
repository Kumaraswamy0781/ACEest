"""Behavior checks for ACEest Flask version 1.1."""

from html import unescape

import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_home_prompts_for_program_selection(client):
    response = client.get("/")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Client profile" in page
    assert "Select a fitness program to view its workout and diet plan." in page


@pytest.mark.parametrize(
    "program_id, name, workout, diet",
    [
        ("fat-loss", "Fat Loss (FL)", "5x5 Back Squat + AMRAP", "3 Egg Whites + Oats Idli"),
        ("muscle-gain", "Muscle Gain (MG)", "Squat 5x5", "Chicken Biryani (250g Chicken)"),
        ("beginner", "Beginner (BG)", "Air Squats, Ring Rows, Push-ups", "Idli-Sambar"),
    ],
)
def test_selected_program_shows_its_plan(client, program_id, name, workout, diet):
    response = client.get("/", query_string={"program": program_id})

    assert response.status_code == 200
    page = unescape(response.get_data(as_text=True))
    assert name in page
    assert workout in page
    assert diet in page


def test_program_list_api(client):
    response = client.get("/api/programs")

    assert response.status_code == 200
    assert response.json == [
        {"id": "fat-loss", "name": "Fat Loss (FL)"},
        {"id": "muscle-gain", "name": "Muscle Gain (MG)"},
        {"id": "beginner", "name": "Beginner (BG)"},
    ]


@pytest.mark.parametrize(
    "program_id, name, workout, diet",
    [
        ("fat-loss", "Fat Loss (FL)", "5x5 Back Squat + AMRAP", "3 Egg Whites + Oats Idli"),
        ("muscle-gain", "Muscle Gain (MG)", "Squat 5x5", "Chicken Biryani (250g Chicken)"),
        ("beginner", "Beginner (BG)", "Air Squats, Ring Rows, Push-ups", "Idli-Sambar"),
    ],
)
def test_program_detail_api(client, program_id, name, workout, diet):
    response = client.get(f"/api/programs/{program_id}")

    assert response.status_code == 200
    assert response.json["id"] == program_id
    assert response.json["name"] == name
    assert workout in response.json["workout"]
    assert diet in response.json["diet"]


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
def test_valid_client_submission_shows_calorie_estimate(client, program_id, expected_calories):
    response = client.post("/", data={
        "name": "Asha",
        "age": "30",
        "weight": "70",
        "program": program_id,
        "adherence": "85",
    })

    page = unescape(response.get_data(as_text=True))
    assert response.status_code == 200
    assert "Client summary" in page
    assert "Asha" in page
    assert "85%" in page
    assert f"{expected_calories} kcal/day" in page


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
def test_invalid_client_submission_shows_validation_error(client, overrides):
    data = {
        "name": "Asha",
        "age": "30",
        "weight": "70",
        "program": "fat-loss",
        "adherence": "85",
    }
    data.update(overrides)

    response = client.post("/", data=data)

    assert response.status_code == 400
    assert b"field-error" in response.data
    assert b"Client summary" not in response.data


def test_submitted_profile_is_not_persisted_between_requests(client):
    client.post("/", data={
        "name": "Asha",
        "age": "30",
        "weight": "70",
        "program": "fat-loss",
        "adherence": "85",
    })

    response = client.get("/")
    assert b"Asha" not in response.data
    assert b"Client summary" not in response.data
