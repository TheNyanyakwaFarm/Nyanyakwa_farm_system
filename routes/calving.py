from flask import Blueprint, render_template, request, redirect, flash, session, url_for
from datetime import datetime
from database import get_db
from functools import wraps
from utils.status_updater import update_cattle_statuses  # ✅ NEW

calving_bp = Blueprint('calving', __name__, url_prefix='/calving')

# 🔐 Login required decorator
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return wrapper


@calving_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_calving():
    db = get_db()

    # ✅ Get dams (served females)
    dams = db.execute("""
        SELECT DISTINCT c.tag_number, c.name 
        FROM cattle c 
        JOIN breeding_records b ON c.cattle_id = b.cattle_id
        WHERE c.sex = 'F'
    """).fetchall()

    if request.method == 'POST':
        dam_tag = request.form['dam_tag_number']
        dam_name = request.form['dam_name']
        calf_name = request.form['calf_name']
        calf_sex = request.form['calf_sex']
        birth_date = request.form['birth_date']
        breed = request.form['breed']
        calf_condition = request.form['calf_condition']
        notes = request.form.get('notes', '')
        recorded_by = session.get('username', 'unknown')
        created_at = datetime.now()

        # ✅ Save calving record
        db.execute("""
            INSERT INTO calving (
                dam_tag_number, dam_name, calf_name, calf_sex, birth_date,
                breed, calf_condition, notes, recorded_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dam_tag, dam_name, calf_name, calf_sex, birth_date,
            breed, calf_condition, notes, recorded_by, created_at
        ))

        # 🐮 Insert calf into cattle table if alive
        if calf_condition.lower() == 'alive':
            prefix = "TNF"

            # ✅ Get last numeric part regardless of month/year
            last_tag = db.execute("""
                SELECT tag_number FROM cattle
                WHERE tag_number LIKE ? ORDER BY cattle_id DESC LIMIT 1
            """, (f"{prefix}%",)).fetchone()

            if last_tag:
                last_number = int(last_tag['tag_number'].split('/')[0][3:])
                next_number = last_number + 1
            else:
                next_number = 1

            # Month/year from birth date of calf
            month = datetime.strptime(birth_date, "%Y-%m-%d").strftime("%m")
            year = datetime.strptime(birth_date, "%Y-%m-%d").strftime("%Y")
            tag_number = f"{prefix}{next_number:04d}/{month}/{year}"

            # Insert with pending status (will be auto-updated)
            db.execute("""
                INSERT INTO cattle (
                    name, tag_number, breed, birth_date,
                    sex, status_category, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                calf_name, tag_number, breed, birth_date,
                calf_sex, "pending", "pending"
            ))

            db.commit()

            # 🔁 Recalculate all statuses
            from utils.status_updater import update_cattle_statuses
            update_cattle_statuses(db)

        # ✅ Update dam to lactating
        db.execute("""
            UPDATE cattle SET status = 'lactating'
            WHERE tag_number = ?
        """, (dam_tag,))
        db.commit()

        flash("✅ Calving record saved successfully!", "success")
        return redirect(url_for('calving.calving_list'))

    return render_template('calving/add_calving.html', dams=dams)


@calving_bp.route('/list', methods=['GET'])
@login_required
def calving_list():
    db = get_db()
    search = request.args.get('search', '').strip()

    if search:
        query = """
            SELECT * FROM calving
            WHERE calf_name LIKE ? OR dam_name LIKE ? OR dam_tag_number LIKE ?
            ORDER BY birth_date DESC
        """
        search_param = f"%{search}%"
        records = db.execute(query, (search_param, search_param, search_param)).fetchall()
    else:
        records = db.execute("""
            SELECT * FROM calving ORDER BY birth_date DESC
        """).fetchall()

    return render_template('calving/calving_list.html', records=records)


@calving_bp.route('/edit/<int:calving_id>', methods=['GET', 'POST'])
@login_required
def edit_calving(calving_id):
    db = get_db()

    record = db.execute("SELECT * FROM calving WHERE calving_id = ?", (calving_id,)).fetchone()

    if not record:
        flash("❌ Record not found.", "danger")
        return redirect(url_for('calving.calving_list'))

    dams = db.execute("""
        SELECT DISTINCT tag_number, name 
        FROM cattle 
        WHERE sex = 'F'
    """).fetchall()

    if request.method == 'POST':
        dam_tag = request.form['dam_tag_number']
        dam_name = request.form['dam_name']
        calf_name = request.form['calf_name']
        calf_sex = request.form['calf_sex']
        birth_date = request.form['birth_date']
        breed = request.form['breed']
        calf_status = request.form['calf_status']
        notes = request.form.get('notes', '')

        db.execute("""
            UPDATE calving SET 
                dam_tag_number = ?, dam_name = ?, calf_name = ?, calf_sex = ?, 
                birth_date = ?, breed = ?, calf_status = ?, notes = ?
            WHERE calving_id = ?
        """, (dam_tag, dam_name, calf_name, calf_sex, birth_date, breed, calf_status, notes, calving_id))

        db.commit()
        flash("✅ Calving record updated.", "success")
        return redirect(url_for('calving.calving_list'))

    return render_template('calving/edit_calving.html', record=record, dams=dams)


@calving_bp.route('/delete/<int:calving_id>', methods=['GET', 'POST'])
@login_required
def delete_calving(calving_id):
    if session.get('role') not in ['admin', 'manager']:
        flash("❌ You do not have permission to delete records.", "danger")
        return redirect(url_for('calving.calving_list'))

    db = get_db()
    record = db.execute("SELECT * FROM calving WHERE calving_id = ?", (calving_id,)).fetchone()

    if not record:
        flash("❌ Record not found.", "danger")
        return redirect(url_for('calving.calving_list'))

    if request.method == 'POST':
        db.execute("DELETE FROM calving WHERE calving_id = ?", (calving_id,))
        db.commit()
        flash("🗑️ Calving record deleted successfully.", "info")
        return redirect(url_for('calving.calving_list'))

    return render_template('calving/delete_calving.html', record=record)
