# Shared Database Support for ACEest 3.4.0

## Purpose

This increment lets multiple Flask instances use one PostgreSQL database and
one session signing key. It retains SQLite for local development and isolated
tests. The application uses SQLAlchemy Core and the Psycopg 3 driver.

PostgreSQL starts with its own tables and accounts. Existing SQLite records
remain in the SQLite file; this increment does not automatically copy them to
PostgreSQL. Create a PostgreSQL login account before using its dashboard.

## Configuration

| Setting | Purpose |
| --- | --- |
| ACEEST_DATABASE | SQLite file path, used when no PostgreSQL URL is configured |
| ACEEST_DATABASE_URL | PostgreSQL connection URL; accepts postgresql:// or postgresql+psycopg:// |
| ACEEST_SECRET_KEY | Required shared signing key in PostgreSQL mode |
| ACEEST_TEST_DATABASE_URL | Separate connection setting for explicit PostgreSQL integration tests |

Use the same database URL and signing key for every instance in one deployment.
Different session keys invalidate cookies when requests move between instances.
Keep credentials and session keys outside Git. Kubernetes will supply these
values through Secrets in a later increment.

Release metadata defaults to version 3.4.0. The metadata settings introduced in
3.3.0 remain configurable. GET /health remains a process health and metadata
endpoint, not a database readiness check.

## PostgreSQL on the remote machine

The existing development database uses:

- Container: aceest-postgres
- Image: postgres:17
- Database and user: aceest
- Host address: 127.0.0.1:15432
- Persistent Docker volume: aceest-postgres-data
- Private configuration: ~/.config/aceest-a2/postgres.env

For a fresh setup, create the private environment file:

```bash
python - <<'PY'
from pathlib import Path
import os
import secrets

folder = Path.home() / '.config' / 'aceest-a2'
folder.mkdir(parents=True, exist_ok=True, mode=0o700)
path = folder / 'postgres.env'
if not path.exists():
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as file:
        file.write('POSTGRES_DB=aceest\nPOSTGRES_USER=aceest\n')
        file.write('POSTGRES_PASSWORD=' + secrets.token_hex(32) + '\n')
PY

docker volume create aceest-postgres-data
docker run -d --name aceest-postgres \
  --env-file "$HOME/.config/aceest-a2/postgres.env" \
  --mount type=volume,source=aceest-postgres-data,target=/var/lib/postgresql/data \
  -p 127.0.0.1:15432:5432 \
  --health-cmd="pg_isready -U aceest -d aceest" \
  --health-interval=5s --health-timeout=3s --health-retries=12 \
  postgres:17
```

For the already-running database, continue with verification:

```bash
docker exec aceest-postgres pg_isready -U aceest -d aceest
docker exec aceest-postgres psql -U aceest -d aceest -c 'SELECT current_database(), current_user;'
```

## Install dependencies and test

From acetest-flask-app with the Python 3.12 virtual environment activated:

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

Expected: 51 passed. The default suite uses temporary SQLite databases.

Run the complete behavior suite on both database engines:

```bash
python scripts/with_postgres.py --tests -- python -m pytest -q --postgres
```

Expected: 85 passed. Tests create uniquely named aceest_test_* schemas and drop
only those schemas afterward. They do not erase the application's tables.
The configured test account needs permission to create and drop its schemas;
the development account initialized by this image has that permission.
An explicitly requested PostgreSQL run fails when no test URL is supplied.

The helper reads the private postgres.env file and passes settings to its child
process without printing the URL or password. In test mode it clears the
application PostgreSQL URL, so importing app.py cannot initialize deployment
tables before the isolated test schemas are created.

## Create an account and run the application

```bash
python scripts/with_postgres.py -- python -m flask --app app create-user admin --role Admin
```

Enter the new account password at the prompts. The helper creates a persistent
private ~/.config/aceest-a2/session.key file on the first non-test run. Reusing
that file supplies the same session key to each locally launched instance.

Start the application on the remote machine:

```bash
python scripts/with_postgres.py -- python -m flask --app app run --host 127.0.0.1 --port 5000
```

Use another remote terminal for curl or a browser on that machine for /login.

## Docker verification

From acetest-flask-app:

```bash
docker build -t aceest:3.4.0 .
docker run --rm aceest:3.4.0 python -m pytest -q
```

Expected: 51 passed. For PostgreSQL tests inside the application container,
create a user-defined Docker network once and attach the database:

```bash
docker network create aceest-a2
docker network connect aceest-a2 aceest-postgres
```

If that network already exists and the database is already attached, proceed
to the test command. The container hostname and port differ from the host's
loopback port:

```bash
python scripts/with_postgres.py --tests --host aceest-postgres --port 5432 -- \
  docker run --rm --network aceest-a2 \
  -e ACEEST_TEST_DATABASE_URL \
  aceest:3.4.0 python -m pytest -q --postgres
```

Expected: 85 passed. Docker reads the test URL from the helper's environment.
The command itself contains no password.

For a running application container using the same PostgreSQL data and key:

```bash
python scripts/with_postgres.py --host aceest-postgres --port 5432 -- \
  docker run --rm --network aceest-a2 \
  -p 127.0.0.1:8000:8000 \
  -e ACEEST_DATABASE_URL -e ACEEST_SECRET_KEY \
  -e ACEEST_INSTANCE_ID=aceest-remote-1 \
  aceest:3.4.0
```

## Implementation and compatibility

Queries bind named parameters instead of inserting user values into SQL.
Database operations return mapping rows consistently on both backends.
Generated IDs use SQLAlchemy's inserted_primary_key API, compatible with older SQLite. Case-insensitive unique
indexes preserve username and client-name uniqueness on fresh databases.

PostgreSQL schema creation uses a transaction-scoped advisory lock so workers
starting together cannot race to create the initial tables. PostgreSQL and
file-based SQLite use NullPool: startup does not retain open connections that
could be inherited by Gunicorn's preloaded workers. Each request closes its
connection at application-context teardown.

The tests cover authentication, roles, CSRF, profiles, training records, PDF
reports, metadata, shared data and cookies, rollback, foreign keys and legacy
SQLite login compatibility. Schema creation adds missing tables; it is not a
general schema migration system. Future database-changing releases must use
explicit migrations and remain compatible with overlapping app versions.
