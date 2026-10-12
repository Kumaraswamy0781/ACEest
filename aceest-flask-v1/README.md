# ACEest Fitness Flask Version 1

This is a Flask web version of the supplied `Aceestver-1.0.py` desktop application. It lets a visitor choose Fat Loss, Muscle Gain, or Beginner and view the matching workout and diet plan. The program text and site reference metrics are carried over from that version.

Version 1 has no client accounts, database, calorie calculation, GitHub Actions workflow, or Jenkins integration. Those can be added in later increments.

## Run locally

Use Python 3.12 or later:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
flask --app app run --debug
```

Open <http://127.0.0.1:5000/> and select a program. The page reloads with its workout and diet plan. Stop the server with Ctrl+C.

## JSON endpoints

- `GET /api/programs` lists the available programs.
- `GET /api/programs/fat-loss` returns a program and its plan. Replace `fat-loss` with `muscle-gain` or `beginner`.

These endpoints return HTTP 404 for an unknown program.

## Run tests

Pytest checks the home page, all three program selections, the JSON endpoints,
unknown-program responses, and the stylesheet. Run it from the project folder:

```bash
python -m pytest -q
```

## Build and run with Docker

From this project directory, build the image. The final `.` tells Docker to use
the current directory, which contains the Dockerfile, as its build context.

```bash
docker build -t aceest:local .
docker run --rm aceest:local python -m pytest -q
docker run --rm -p 8000:8000 aceest:local
```

Open <http://127.0.0.1:8000/> after the last command starts the server.
The image runs the app as a non-root user. Stop the running container with Ctrl+C.

