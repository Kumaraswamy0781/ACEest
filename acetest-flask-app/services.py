"""Validation and client operations shared by the browser and JSON API."""
import math
import secrets
from datetime import date
from db import get_db

PROGRAMS = {
    'Fat Loss': {'factor': 22, 'templates': ['Full Body HIIT', 'Circuit Training', 'Cardio + Weights'],
                 'diet': 'Egg whites and oats; grilled chicken with brown rice; fish curry with millet roti.'},
    'Muscle Gain': {'factor': 35, 'templates': ['Push/Pull/Legs', 'Upper/Lower Split', 'Full Body Strength'],
                    'diet': 'Eggs and peanut butter oats; chicken biryani; mutton curry and rice.'},
    'Beginner': {'factor': 26, 'templates': ['Full Body 3x/week', 'Light Strength + Mobility'],
                 'diet': 'Balanced meals including idli, rice with dal, and chapati.'},
}


class ValidationError(ValueError):
    pass


class MissingClient(LookupError):
    pass


def number(value, label, minimum=0, maximum=None, integer=False, optional=False):
    if optional and (value is None or value == ''):
        return None
    try:
        if isinstance(value, bool):
            raise ValueError
        parsed = float(value)
        if not math.isfinite(parsed) or parsed < minimum or (maximum is not None and parsed > maximum):
            raise ValueError
        if integer and not parsed.is_integer():
            raise ValueError
    except (ValueError, TypeError, OverflowError):
        raise ValidationError(f'{label} must be a {"whole number" if integer else "number"} {"from " + str(minimum) + " to " + str(maximum) if maximum is not None else "of at least " + str(minimum)}.')
    return int(parsed) if integer else parsed


def text(value, label, maximum=200, optional=False):
    if optional and value is None:
        return ''
    if not isinstance(value, str) or (not value.strip() and not optional) or len(value) > maximum:
        raise ValidationError(f'{label} is required and must be at most {maximum} characters.')
    return value.strip()


def iso_date(value, label, optional=False):
    if optional and (value is None or value == ''):
        return None
    try:
        if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
            raise ValueError
    except (ValueError, TypeError):
        raise ValidationError(f'{label} must be a date in YYYY-MM-DD format.')
    return value


def client_profile(data):
    program = data.get('program')
    if not isinstance(program, str) or program not in PROGRAMS:
        raise ValidationError('Choose Fat Loss, Muscle Gain, or Beginner.')
    weight = number(data.get('weight'), 'Weight', 0.1)
    status = data.get('membership_status', 'Active')
    if status not in ('Active', 'Paused', 'Expired'):
        raise ValidationError('Choose Active, Paused, or Expired for membership status.')
    return {
        'name': text(data.get('name'), 'Name', 100),
        'age': number(data.get('age'), 'Age', 1, 130, integer=True),
        'height': number(data.get('height'), 'Height', 0.1),
        'weight': weight, 'program': program,
        'calories': int(weight * PROGRAMS[program]['factor']),
        'target_weight': number(data.get('target_weight'), 'Target weight', 0.1, optional=True),
        'target_adherence': number(data.get('target_adherence'), 'Target adherence', 0, 100, integer=True, optional=True),
        'membership_status': status,
        'membership_end': iso_date(data.get('membership_end'), 'Membership end', optional=True),
    }


def save_client(data, client_id=None):
    profile = client_profile(data)
    db = get_db()
    if client_id is not None:
        get_client(client_id)
    with db:
        if client_id is None:
            names = ','.join(profile)
            placeholders = ','.join('?' for _ in profile)
            cursor = db.execute(f'INSERT INTO clients ({names}) VALUES ({placeholders})', tuple(profile.values()))
            client_id = cursor.lastrowid
        else:
            db.execute('UPDATE clients SET ' + ','.join(f'{key}=?' for key in profile) + ', generated_program=NULL WHERE id=?',
                       (*profile.values(), client_id))
    return get_client(client_id)


def get_client(client_id):
    row = get_db().execute('SELECT * FROM clients WHERE id=?', (client_id,)).fetchone()
    if row is None:
        raise MissingClient('Client not found.')
    result = dict(row)
    result['bmi'] = round(result['weight'] / (result['height'] / 100) ** 2, 1)
    result['effective_membership_status'] = result['membership_status']
    if result['membership_status'] == 'Active' and result['membership_end'] and result['membership_end'] < date.today().isoformat():
        result['effective_membership_status'] = 'Expired'
    return result


def history(client_id, kind):
    get_client(client_id)
    if kind not in ('progress', 'workouts', 'metrics'):
        raise ValidationError('Unknown history type.')
    order = 'id' if kind == 'progress' else 'date, id'
    result = [dict(row) for row in get_db().execute(f'SELECT * FROM {kind} WHERE client_id=? ORDER BY {order}', (client_id,))]
    if kind == 'workouts':
        for workout in result:
            workout['exercises'] = [dict(row) for row in get_db().execute('SELECT * FROM exercises WHERE workout_id=? ORDER BY id', (workout['id'],))]
    return result


def add_record(client_id, kind, data):
    get_client(client_id)
    if kind == 'progress':
        year, week, _ = date.today().isocalendar()
        record = {'client_id': client_id, 'week': data.get('week') or f'{year}-W{week:02}',
                  'adherence': number(data.get('adherence'), 'Adherence', 0, 100, integer=True)}
        record['week'] = text(record['week'], 'Week', 40)
    elif kind == 'metrics':
        record = {'client_id': client_id, 'date': iso_date(data.get('date'), 'Date'),
                  'weight': number(data.get('weight'), 'Weight', 0.1),
                  'waist': number(data.get('waist'), 'Waist', 0.1, optional=True),
                  'bodyfat': number(data.get('bodyfat'), 'Body fat', 0, 100, optional=True)}
    elif kind == 'workouts':
        record = {'client_id': client_id, 'date': iso_date(data.get('date'), 'Date'),
                  'workout_type': text(data.get('workout_type'), 'Workout type', 100),
                  'duration_min': number(data.get('duration_min'), 'Duration', 1, integer=True),
                  'notes': text(data.get('notes', ''), 'Notes', 2000, optional=True)}
    else:
        raise ValidationError('Unknown record type.')
    exercises = []
    if kind == 'workouts':
        raw = data.get('exercises', [])
        if not isinstance(raw, list):
            raise ValidationError('Exercises must be a list.')
        for item in raw:
            if not isinstance(item, dict):
                raise ValidationError('Each exercise must be an object.')
            exercises.append((text(item.get('name'), 'Exercise name', 100),
                              number(item.get('sets'), 'Sets', 1, integer=True),
                              number(item.get('reps'), 'Reps', 1, integer=True),
                              number(item.get('weight', 0), 'Exercise weight', 0)))
    db = get_db()
    with db:
        cursor = db.execute(f'INSERT INTO {kind} ({",".join(record)}) VALUES ({",".join("?" for _ in record)})', tuple(record.values()))
        record['id'] = cursor.lastrowid
        if kind == 'workouts':
            db.executemany('INSERT INTO exercises (workout_id,name,sets,reps,weight) VALUES (?,?,?,?,?)',
                           [(record['id'], *exercise) for exercise in exercises])
    return record


def generate_program(client_id):
    client = get_client(client_id)
    generated = secrets.choice(PROGRAMS[client['program']]['templates'])
    db = get_db()
    with db:
        db.execute('UPDATE clients SET generated_program=? WHERE id=?', (generated, client_id))
    return get_client(client_id)
