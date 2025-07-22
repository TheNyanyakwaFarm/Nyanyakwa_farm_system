from flask import Blueprint, render_template, request, redirect, flash, session, url_for
from database import get_db, get_cursor
from functools import wraps
from datetime import datetime

milk_bp = Blueprint('milk', __name__)

# 🔐 Login-required decorator
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return wrapper

# 🔐 Role-required decorator
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                flash("Please log in to access this page.", "warning")
                return redirect(url_for('auth.login', next=request.url))
            if session.get('role') not in roles:
                flash("You do not have permission to perform this action.", "danger")
                return redirect(url_for('dashboard.dashboard'))
            return f(*args, **kwargs)
        return wrapper
    return decorator

@milk_bp.route('/record_milk', methods=['GET', 'POST'])
@login_required
def record_milk():
    db = get_db()
    cursor = get_cursor()

    # Selected date logic
    selected_date = request.args.get('date') or request.form.get('date') or datetime.today().strftime('%Y-%m-%d')

    # Fetch lactating and lactating in-calf cows
    cursor.execute('''
        SELECT cattle_id, tag_number, name FROM cattle
        WHERE sex = 'F' AND status IN ('lactating', 'lactating in_calf')
        ORDER BY cattle_id
    ''')
    cattle_list = cursor.fetchall()
    saved_ids = []

    if request.method == 'POST':
        cattle_id = request.form['cattle_id']
        session_input = request.form['session']
        date = selected_date
        milk_value = request.form.get('milk_value')
        notes = request.form.get('notes', '')

        # Check for existing record
        cursor.execute('SELECT * FROM milk_production WHERE cattle_id = %s AND date = %s', (cattle_id, date))
        existing = cursor.fetchone()

        if existing:
            cursor.execute(f'''
                UPDATE milk_production
                SET {session_input}_milk = %s, notes = %s
                WHERE cattle_id = %s AND date = %s
            ''', (milk_value, notes, cattle_id, date))
        else:
            morning = milk_value if session_input == 'morning' else None
            mid_day = milk_value if session_input == 'mid_day' else None
            evening = milk_value if session_input == 'evening' else None
            cursor.execute('''
                INSERT INTO milk_production (cattle_id, date, morning_milk, mid_day_milk, evening_milk, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (cattle_id, date, morning, mid_day, evening, notes))

        db.commit()
        saved_ids.append(int(cattle_id))
        flash(f"{session_input.replace('_', ' ').capitalize()} session saved.", "success")
        return redirect(url_for('milk.record_milk', date=selected_date))

    # Determine session status per cow for selected date
    cursor.execute('''
        SELECT cattle_id, morning_milk, mid_day_milk, evening_milk
        FROM milk_production
        WHERE date = %s
    ''', (selected_date,))
    milk_data = cursor.fetchall()

    status_labels = {}
    for row in milk_data:
        cid = row['cattle_id']
        count = sum(1 for x in [row['morning_milk'], row['mid_day_milk'], row['evening_milk']] if x is not None)

        if count == 1:
            label = "✅ One session saved"
        elif count == 2:
            label = "✅ Two sessions saved"
        elif count == 3:
            label = "✅ All three sessions saved"
        else:
            label = "🔲 No session yet"

        status_labels[cid] = label

    return render_template("milk/record_milk.html", cattle_list=cattle_list, selected_date=selected_date, saved_ids=saved_ids, status_labels=status_labels)

@milk_bp.route('/milk_records', methods=['GET', 'POST'])
@login_required
def milk_records():
    db = get_db()
    cursor = get_cursor()
    query = '''
        SELECT m.*, c.name, c.tag_number,
               COALESCE(morning_milk, 0) + COALESCE(mid_day_milk, 0) + COALESCE(evening_milk, 0) AS total_milk
        FROM milk_production m
        JOIN cattle c ON m.cattle_id = c.cattle_id
    '''
    params = []
    filters = []

    if request.method == 'POST':
        cow_id = request.form.get('cow_id')
        date = request.form.get('date')
        if cow_id:
            filters.append('m.cattle_id = %s')
            params.append(cow_id)
        if date:
            filters.append('m.date = %s')
            params.append(date)

    if filters:
        query += ' WHERE ' + ' AND '.join(filters)
    query += ' ORDER BY m.date DESC'

    cursor.execute(query, params)
    records = cursor.fetchall()

    cursor.execute('SELECT cattle_id, name, tag_number FROM cattle')
    cows = cursor.fetchall()

    # Weekly and Monthly totals
    cursor.execute('''
        SELECT
            SUM(
                CASE WHEN m.date >= CURRENT_DATE - INTERVAL '7 days'
                THEN COALESCE(m.morning_milk, 0) + COALESCE(m.mid_day_milk, 0) + COALESCE(m.evening_milk, 0)
                ELSE 0 END
            ) AS weekly_total,
            SUM(
                CASE WHEN date_trunc('month', m.date) = date_trunc('month', CURRENT_DATE)
                THEN COALESCE(m.morning_milk, 0) + COALESCE(m.mid_day_milk, 0) + COALESCE(m.evening_milk, 0)
                ELSE 0 END
            ) AS monthly_total
        FROM milk_production m
    ''')
    totals = cursor.fetchone()

    return render_template("milk/milk_records.html", records=records, cows=cows, totals=totals)

@milk_bp.route('/edit_milk/<int:record_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def edit_milk_record(record_id):
    db = get_db()
    cursor = get_cursor()

    cursor.execute('SELECT * FROM milk_production WHERE id = %s', (record_id,))
    record = cursor.fetchone()

    if request.method == 'POST':
        morning = request.form['morning_milk']
        mid_day = request.form['mid_day_milk']
        evening = request.form['evening_milk']

        cursor.execute('''
            UPDATE milk_production
            SET morning_milk = %s, mid_day_milk = %s, evening_milk = %s
            WHERE id = %s
        ''', (morning, mid_day, evening, record_id))
        db.commit()

        flash("Milk record updated successfully.", "success")
        return redirect(url_for('milk.milk_records'))

    return render_template("milk/edit_milk_record.html", record=record)

@milk_bp.route('/delete_milk/<int:record_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def delete_milk_record(record_id):
    if request.method == 'POST':
        password = request.form['password']
        if password == 'admin123':  # TODO: Replace with hashed password check in production
            db = get_db()
            cursor = db.cursor()
            cursor.execute('DELETE FROM milk_production WHERE id = %s', (record_id,))
            db.commit()
            flash("Milk record deleted successfully.", "success")
        else:
            flash("Incorrect password. Record not deleted.", "danger")

        return redirect(url_for('milk.milk_records'))

    return render_template("user/confirm_delete.html", record_id=record_id)
