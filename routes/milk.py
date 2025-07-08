from flask import Blueprint, render_template, request, redirect, flash, session, url_for
from database import get_db
from functools import wraps

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
    cattle_list = db.execute('SELECT cattle_id, tag_number FROM cattle').fetchall()

    if request.method == 'POST':
        cattle_id = request.form['cattle_id']
        date = request.form['date']
        session_input = request.form['session']
        notes = request.form['notes']
        morning = mid_day = evening = None

        if session_input == 'morning':
            morning = request.form['morning_milk']
        elif session_input == 'mid_day':
            mid_day = request.form['mid_day_milk']
        elif session_input == 'evening':
            evening = request.form['evening_milk']

        existing = db.execute(
            'SELECT * FROM milk_production WHERE cattle_id = ? AND date = ?',
            (cattle_id, date)
        ).fetchone()

        if existing:
            if session_input == 'morning':
                db.execute('UPDATE milk_production SET morning_milk = ?, notes = ? WHERE cattle_id = ? AND date = ?', (morning, notes, cattle_id, date))
            elif session_input == 'mid_day':
                db.execute('UPDATE milk_production SET mid_day_milk = ?, notes = ? WHERE cattle_id = ? AND date = ?', (mid_day, notes, cattle_id, date))
            elif session_input == 'evening':
                db.execute('UPDATE milk_production SET evening_milk = ?, notes = ? WHERE cattle_id = ? AND date = ?', (evening, notes, cattle_id, date))
        else:
            db.execute('''
                INSERT INTO milk_production 
                (cattle_id, date, morning_milk, mid_day_milk, evening_milk, notes) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (cattle_id, date, morning, mid_day, evening, notes))

        db.commit()
        flash("Milk data recorded successfully.", "success")
        return redirect(url_for('milk.record_milk'))

    return render_template("milk/record_milk.html", cattle_list=cattle_list)


@milk_bp.route('/milk_records', methods=['GET', 'POST'])
@login_required
def milk_records():
    db = get_db()
    query = '''
        SELECT m.*, c.name, c.tag_number
        FROM milk_production m
        JOIN cattle c ON m.cattle_id = c.cattle_id
    '''
    filters = []

    if request.method == 'POST':
        cow_id = request.form.get('cow_id')
        date = request.form.get('date')
        if cow_id:
            filters.append(f"m.cattle_id = {cow_id}")
        if date:
            filters.append(f"m.date = '{date}'")
        if filters:
            query += ' WHERE ' + ' AND '.join(filters)

    records = db.execute(query).fetchall()
    cows = db.execute('SELECT cattle_id, name, tag_number FROM cattle').fetchall()

    return render_template("milk/milk_records.html", records=records, cows=cows)


@milk_bp.route('/edit_milk/<int:record_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def edit_milk_record(record_id):
    db = get_db()
    record = db.execute('SELECT * FROM milk_production WHERE id = ?', (record_id,)).fetchone()

    if request.method == 'POST':
        morning = request.form['morning_milk']
        mid_day = request.form['mid_day_milk']
        evening = request.form['evening_milk']

        db.execute('''
            UPDATE milk_production
            SET morning_milk = ?, mid_day_milk = ?, evening_milk = ?
            WHERE id = ?
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
        if password == 'admin123':  # ✅ Replace with hashed admin check for security in future
            db = get_db()
            db.execute('DELETE FROM milk_production WHERE id = ?', (record_id,))
            db.commit()
            flash("Milk record deleted successfully.", "success")
        else:
            flash("Incorrect password. Record not deleted.", "danger")

        return redirect(url_for('milk.milk_records'))

    return render_template("user/confirm_delete.html", record_id=record_id)
