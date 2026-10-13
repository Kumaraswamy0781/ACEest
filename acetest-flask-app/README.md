# ACEest Fitness — Final Flask Application 3.2.4

A complete standalone web application adapted from the supplied final ACEest desktop version. Open this folder as a new project and use a fresh database.

## Features

- Login/logout with hashed passwords and Admin, Coach, and Viewer roles.
- Client creation and editing: age, height, weight, category, calorie estimate, BMI, and goals.
- Membership status and end date, including automatic expiry checks.
- Program generation using the original category-specific templates and nutrition plans.
- Weekly adherence records and a browser chart.
- Workouts with exercise sets, reps, and weights.
- Body metric history for weight, waist, and body fat.
- Downloadable PDF client reports with profile details and history.
- JSON endpoints and pytest tests in a separate `tests/` folder.

The program generator selects a template from the chosen category. It does not call an external AI service. Admin and Coach accounts can edit gym records; Viewer accounts can read them and download reports. All authorized users access the same gym client directory.

## Install on the remote machine

Use Python 3.10 or newer. Extract the project into a new folder, then run:

```bash
cd aceest-final-v3.2.4
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Create your first login account. The command prompts for a password and its confirmation (at least eight characters):

```bash
python -m flask --app app create-user admin --role Admin
```

Start the development server:

```bash
python -m flask --app app run --host 0.0.0.0 --port 5000
```

Open `http://REMOTE_MACHINE_IP:5000` where the machine's port 5000 is accessible. Sign in using the account you created. Add a client, then open their profile to record progress, workouts, metrics, and membership details.

Use Ctrl+C to stop the server. For a Gunicorn process instead:

```bash
gunicorn --bind 0.0.0.0:8000 --workers 2 app:app
```

Additional accounts can be created the same way:

```bash
python -m flask --app app create-user coach --role Coach
python -m flask --app app create-user reader --role Viewer
```

## Database and sessions

On first run the application creates `instance/aceest.sqlite` and a private session key in `instance/.session-key`. Reuse this folder across restarts to retain data and login sessions. Neither file belongs in Git. `ACEEST_DATABASE` and `ACEEST_SECRET_KEY` environment variables can override their defaults.

This release creates its own database; it is not a migration package for earlier assignment schemas.

## Run tests

```bash
python -m pytest -q
```

Tests create temporary databases and accounts. They do not use your saved clients or login account.

## Project structure

```text
app.py                 Flask routes, login, roles, CSRF checks, and account CLI
db.py                  SQLite connections and schema
services.py            Validation, profiles, memberships, programs, and records
reports.py             Paginated PDF generation
requirements.txt       Python dependencies
templates/             Browser pages and forms
static/style.css       Responsive dark/gold interface
tests/test_app.py       Isolated behavior tests
```

## JSON API

`GET /health` and `GET /api/programs` are public. Other endpoints require the logged-in session. Fetch `GET /api/session` to obtain a CSRF token, and send it as `X-CSRF-Token` for POST/PUT requests using the same session cookies.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/session` | Login identity, role, and CSRF token |
| GET, POST | `/api/clients` | List or create clients |
| GET, PUT | `/api/clients/<id>` | Fetch or replace a client profile |
| GET, POST | `/api/clients/<id>/progress` | Read or record weekly adherence |
| GET, POST | `/api/clients/<id>/workouts` | Read or log workouts and exercises |
| GET, POST | `/api/clients/<id>/metrics` | Read or log body metrics |
| POST | `/api/clients/<id>/generate-program` | Generate a plan in the client's category |
| GET | `/api/clients/<id>/membership` | Effective membership status and end date |
| GET | `/clients/<id>/report.pdf` | Download PDF report |

A client JSON object requires `name`, `age`, `height` (cm), `weight` (kg), and `program` (`Fat Loss`, `Muscle Gain`, or `Beginner`). Optional fields are `target_weight`, `target_adherence`, `membership_status`, and `membership_end` (YYYY-MM-DD).

Workout JSON requires `date`, `workout_type`, and `duration_min`. Optional `exercises` is a list of objects containing `name`, `sets`, `reps`, and `weight`; `notes` is optional.

## Suggested commit

After testing this fresh project, stage its source files and commit:

```text
feat: implement final ACEest Flask application v3.2.4
```
