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

## GitHub Actions and Jenkins

The workflow lives at the repository root in `.github/workflows/main.yml` and runs on every push and pull request. Each run creates a fresh virtual environment, installs dependencies, compiles the Python source, runs pytest, builds a Docker image without using build-layer cache, runs pytest inside it, and checks that the Gunicorn container serves `/health` and `/api/programs`.

The root `Jenkinsfile` implements the same quality gates. Jenkins clears the workspace before checking out GitHub, rebuilds the virtual environment, and publishes the pytest JUnit report. A failed command fails the pipeline. SCM polling checks for new commits every five minutes; a GitHub webhook can also be configured later.

To configure Jenkins when the server is available:

1. Use a Linux agent with Git, Python 3.10 or newer (3.12 recommended), `venv`, pip, and Docker. Its Jenkins service account must be able to run Docker.
2. Install the Pipeline, Git, and JUnit plugins.
3. Create a **Pipeline** job named `ACEest-Build`.
4. Choose **Pipeline script from SCM**, then **Git**.
5. Set the repository URL to `https://github.com/Kumaraswamy0781/ACEest.git` and the branch to `*/main`.
6. Set **Script Path** to `Jenkinsfile` (at the repository root).
7. Save and click **Build Now**. Review the console output and published test results. Once the first run loads the Jenkinsfile, subsequent commits are detected by SCM polling.

You can run the container checks yourself from the repository root:

```bash
docker build --pull --no-cache -t aceest:ci acetest-flask-app
sh ci/test-image.sh aceest:ci
```

These pipelines validate and build the app. They do not publish an image or deploy a server.

### Jenkins Python and Docker prerequisites

The Jenkinsfile selects the first supported executable from `python3.12`, `python3.11`, `python3.10`, and `python3`. It leaves the operating system's default interpreter in place. On a Rocky/RHEL 9 system with Python 3.12 packages available, install them with:

```bash
sudo dnf install -y python3.12 python3.12-pip
```

For a Jenkins service installed directly on a Linux machine using the standard Docker socket, allow the service account to access Docker and restart Jenkins so its new group membership takes effect:

```bash
sudo usermod -aG docker jenkins
sudo systemctl restart jenkins
sudo -u jenkins -H python3.12 --version
sudo -u jenkins -H docker info
```

Membership in the Docker group gives Jenkins administrative control of Docker on that machine. If these checks fail, correct the agent's Python installation or Docker access before running the job again.
