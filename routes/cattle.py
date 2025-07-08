from flask import Blueprint, render_template, request, redirect, flash, session, url_for
from database import get_db
from datetime import datetime
import sqlite3
from functools import wraps

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

# ✅ Route: List Cattle
@cattle_bp.route('/')
@login_required
def cattle_list():
    db = get_db()
    sex_filter = request.args.get('sex')
    category_filter = request.args.get('status_category')

    query = "SELECT * FROM cattle WHERE 1=1"
    params = []

    if sex_filter:
        query += " AND sex = ?"
        params.append(sex_filter)

    if category_filter:
        query += " AND status_category = ?"
        params.append(category_filter)

    cattle = db.execute(query, params).fetchall()
    return render_template("cattle/cattle_list.html", cattle=cattle)

# ✅ Route: Add Cattle
@cattle_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_cattle():
    db = get_db()

    if request.method == 'POST':
        name = request.form['name']
        breed = request.form['breed']
        birth_date = request.form['birth_date']
        sex = request.form['sex']

        today = datetime.today()
        month = today.strftime('%m')
        year = today.strftime('%Y')
        prefix = "TNF"

        # ✅ NEW: Get the max number ever used from any tag
        latest_tag = db.execute("""
            SELECT tag_number FROM cattle
            WHERE tag_number LIKE 'TNF%' ORDER BY cattle_id DESC LIMIT 1
        """).fetchone()

        if latest_tag:
            last_tag = latest_tag['tag_number']
            last_number = int(last_tag.split('/')[0][3:])  # Extract number from TNFXXXX
            next_number = last_number + 1
        else:
            next_number = 1

        padded_number = str(next_number).zfill(4)
        tag_number = f"{prefix}{padded_number}/{month}/{year}"

        try:
            # Insert with placeholder status
            db.execute('''
                INSERT INTO cattle (
                    name, tag_number, breed, birth_date, sex,
                    status_category, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, tag_number, breed, birth_date, sex, "pending", "pending"))

            db.commit()

            # Update statuses automatically
            from utils.status_updater import update_cattle_statuses
            update_cattle_statuses(db)

            flash(f'Cattle added successfully. Tag Number: {tag_number}', 'success')
        except sqlite3.IntegrityError:
            flash('⚠️ Tag number already exists. Please try again.', 'danger')

        return redirect(url_for('cattle.cattle_list'))

    return render_template('cattle/add_cattle.html')

# ✅ Route: Edit Cattle
@cattle_bp.route('/edit/<int:cattle_id>', methods=['GET', 'POST'])
@login_required
def edit_cattle(cattle_id):
    db = get_db()
    cattle = db.execute("SELECT * FROM cattle WHERE cattle_id = ?", (cattle_id,)).fetchone()

    if not cattle:
        flash("❌ Cattle not found.", "danger")
        return redirect(url_for('cattle.cattle_list'))

    if request.method == 'POST':
        breed = request.form['breed']
        birth_date = request.form['birth_date']
        sex = request.form['sex']

        try:
            db.execute("""
                UPDATE cattle 
                SET breed = ?, birth_date = ?, sex = ?
                WHERE cattle_id = ?
            """, (breed, birth_date, sex, cattle_id))
            db.commit()
            from utils.status_updater import update_cattle_statuses
            update_cattle_statuses(db)

            flash("✅ Cattle updated successfully.", "success")
        except Exception as e:
            flash(f"❌ Failed to update cattle: {e}", "danger")

        return redirect(url_for('cattle.cattle_list'))

    return render_template('cattle/edit_cattle.html', cattle=cattle)

# ✅ Route: Delete Cattle
@cattle_bp.route('/delete/<int:cattle_id>')
@login_required
def delete_cattle(cattle_id):
    db = get_db()
    db.execute("DELETE FROM cattle WHERE cattle_id = ?", (cattle_id,))
    db.commit()
    flash("Cattle deleted successfully.", "info")
    return redirect(url_for('cattle.cattle_list'))
