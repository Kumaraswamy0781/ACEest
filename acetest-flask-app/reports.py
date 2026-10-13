"""Paginated PDF reports for client profiles and history."""
from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from services import get_client, history


def client_pdf(client_id):
    client = get_client(client_id)
    output = BytesIO()
    styles = getSampleStyleSheet()
    story = [Paragraph('ACEest Client Report', styles['Title'])]
    fields = [('Name', 'name'), ('Age', 'age'), ('Height (cm)', 'height'), ('Weight (kg)', 'weight'),
              ('BMI', 'bmi'), ('Program', 'program'), ('Generated plan', 'generated_program'),
              ('Calories (kcal/day)', 'calories'), ('Target weight (kg)', 'target_weight'),
              ('Target adherence (%)', 'target_adherence'), ('Membership', 'effective_membership_status'),
              ('Membership end', 'membership_end')]
    for label, key in fields:
        value = client[key] if client[key] is not None else 'Not set'
        story.append(Paragraph(f'<b>{label}:</b> {escape(str(value))}', styles['BodyText']))
    for kind, heading, columns in (
        ('progress', 'Weekly adherence', ('week', 'adherence')),
        ('metrics', 'Body metrics', ('date', 'weight', 'waist', 'bodyfat')),
        ('workouts', 'Workout history', ('date', 'workout_type', 'duration_min', 'notes')),
    ):
        story.extend([Spacer(1, 16), Paragraph(heading, styles['Heading2'])])
        rows = history(client_id, kind)
        if not rows:
            story.append(Paragraph('No records yet.', styles['BodyText']))
            continue
        data = [[Paragraph(escape(column.replace('_', ' ').title()), styles['BodyText']) for column in columns]]
        for row in rows:
            data.append([Paragraph(escape(str(row[column] if row[column] is not None else '')), styles['BodyText']) for column in columns])
        table = Table(data, repeatRows=1, colWidths=[480 / len(columns)] * len(columns))
        table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eadba4')),
                                   ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
                                   ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
        story.append(table)
        if kind == 'workouts':
            for row in rows:
                for exercise in row['exercises']:
                    line = f"{row['date']} — {exercise['name']}: {exercise['sets']} sets × {exercise['reps']} reps, {exercise['weight']} kg"
                    story.append(Paragraph(escape(line), styles['BodyText']))
    SimpleDocTemplate(output, title=f"ACEest report: {client['name']}").build(story)
    return output.getvalue()
