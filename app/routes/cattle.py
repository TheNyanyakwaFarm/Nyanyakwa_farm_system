from flask import Blueprint, render_template, request, redirect, flash, session, url_for
from database import get_cursor, get_db
from datetime import datetime
from functools import wraps
from app.utils.status_updater import update_cattle_statuses  # ✅ Existing logic
from app.utils.status_logic import determine_initial_status  # ✅ NEW logic

cattle_bp = Blueprint('cattle', __name__, url_prefix='/cattle')

# 🔐 Login required decorator
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return wrapper

# ✅ Route: Add Cattle
@cattle_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_cattle():
    db = get_db()
    cursor = get_cursor()

    if request.method == 'POST':
        name = request.form['name']
        breed = request.form['breed']
        birth_date_str = request.form['birth_date']
        sex = request.form['sex']

        # ✅ Convert birth_date string to date object
        try:
            birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid birth date format", "danger")
            return redirect(url_for('cattle.add_cattle'))

        # ✅ Generate new tag number
        today = datetime.today()
        month = today.strftime('%m')
        year = today.strftime('%Y')
        prefix = "TNF"

        cursor.execute("""
            SELECT tag_number FROM cattle
            WHERE tag_number LIKE 'TNF%' ORDER BY cattle_id DESC LIMIT 1
        """)
        latest_tag = cursor.fetchone()

        if latest_tag:
            last_tag = latest_tag['tag_number']
            last_number = int(last_tag.split('/')[0][3:])
            next_number = last_number + 1
        else:
            next_number = 1

        padded_number = str(next_number).zfill(4)
        tag_number = f"{prefix}{padded_number}/{month}/{year}"

        # ✅ Determine status using logic
        status_category, status = determine_initial_status(sex, birth_date)

        if not status_category:
            # Fallback to form-based selection for females ≥11 months
            status_category = request.form.get('status_category')
            if status_category == 'young_stock':
                status = 'bullying heifer'
            elif status_category == 'mature_stock':
                status = request.form.get('status')

        try:
            cursor.execute('''
                INSERT INTO cattle (
                    name, tag_number, breed, birth_date, sex,
                    status_category, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (name, tag_number, breed, birth_date, sex, status_category, status))
            db.commit()

            update_cattle_statuses(db)

            flash(f'Cattle added successfully. Tag Number: {tag_number}', 'success')
        except Exception as e:
            flash(f'⚠️ Error saving cattle: {e}', 'danger')

        return redirect(url_for('cattle.cattle_list'))

    return render_template('cattle/add_cattle.html')

# ✅ Route: View Cattle List
@cattle_bp.route('/list', methods=['GET'])
@login_required
def cattle_list():
    cursor = get_cursor()
    search = request.args.get('search', '').strip()

    if search:
        query = """
            SELECT * FROM cattle
            WHERE name ILIKE %s OR tag_number ILIKE %s OR breed ILIKE %s
            ORDER BY birth_date DESC
        """
        param = f"%{search}%"
        cursor.execute(query, (param, param, param))
    else:
        cursor.execute("SELECT * FROM cattle ORDER BY birth_date DESC")

    cattle = cursor.fetchall()
    return render_template('cattle/cattle_list.html', cattle=cattle)

# ✅ Route: Edit Cattle
@cattle_bp.route('/edit/<int:cattle_id>', methods=['GET', 'POST'])
@login_required
def edit_cattle(cattle_id):
    db = get_db()
    cursor = get_cursor()

    cursor.execute("SELECT * FROM cattle WHERE cattle_id = %s", (cattle_id,))
    cattle = cursor.fetchone()

    if not cattle:
        flash("Cattle record not found.", "danger")
        return redirect(url_for('cattle.cattle_list'))

    if request.method == 'POST':
        name = request.form['name']
        breed = request.form['breed']
        birth_date = request.form['birth_date']
        sex = request.form['sex']
        status_category = request.form.get('status_category', '')
        status = request.form.get('status', '')

        cursor.execute("""
            UPDATE cattle
            SET name=%s, breed=%s, birth_date=%s, sex=%s,
                status_category=%s, status=%s
            WHERE cattle_id=%s
        """, (name, breed, birth_date, sex, status_category, status, cattle_id))

        db.commit()
        update_cattle_statuses(db)
        flash("Cattle record updated.", "success")
        return redirect(url_for('cattle.cattle_list'))

    return render_template('cattle/edit_cattle.html', cattle=cattle)

# ✅ Route: Delete Cattle
@cattle_bp.route('/delete/<int:cattle_id>', methods=['GET', 'POST'])
@login_required
def delete_cattle(cattle_id):
    if session.get('role') not in ['admin', 'manager']:
        flash("You do not have permission to delete cattle.", "danger")
        return redirect(url_for('cattle.cattle_list'))

    db = get_db()
    cursor = get_cursor()

    cursor.execute("SELECT * FROM cattle WHERE cattle_id = %s", (cattle_id,))
    cattle = cursor.fetchone()

    if not cattle:
        flash("Cattle not found.", "danger")
        return redirect(url_for('cattle.cattle_list'))

    if request.method == 'POST':
        cursor.execute("DELETE FROM cattle WHERE cattle_id = %s", (cattle_id,))
        db.commit()
        flash("Cattle deleted successfully.", "info")
        return redirect(url_for('cattle.cattle_list'))

    return render_template('cattle/delete_cattle.html', cattle=cattle)
