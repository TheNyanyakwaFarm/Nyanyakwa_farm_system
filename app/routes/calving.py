from flask import Blueprint, render_template, request, redirect, flash, session, url_for
from datetime import datetime
from database import get_db, get_cursor
from functools import wraps
from app.utils.status_updater import update_cattle_statuses

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
    cursor = get_cursor()

    # ✅ Get dams (served females)
    cursor.execute("""
        SELECT DISTINCT c.tag_number, c.name 
        FROM cattle c 
        JOIN breeding_records b ON c.cattle_id = b.cattle_id
        WHERE c.sex = 'F'
    """)
    dams = cursor.fetchall()

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

        cursor.execute("""
            INSERT INTO calving (
                dam_tag_number, dam_name, calf_name, calf_sex, birth_date,
                breed, calf_condition, notes, recorded_by, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            dam_tag, dam_name, calf_name, calf_sex, birth_date,
            breed, calf_condition, notes, recorded_by, created_at
        ))

        # 🐮 Insert calf into cattle table if alive
        if calf_condition.lower() == 'alive':
            prefix = "TNF"
            cursor.execute("""
                SELECT tag_number FROM cattle
                WHERE tag_number LIKE %s
                ORDER BY cattle_id DESC LIMIT 1
            """, (f"{prefix}%",))
            last_tag = cursor.fetchone()

            if last_tag:
                last_number = int(last_tag['tag_number'].split('/')[0][3:])
                next_number = last_number + 1
            else:
                next_number = 1

            birth_dt = datetime.strptime(birth_date, "%Y-%m-%d")
            month = birth_dt.strftime("%m")
            year = birth_dt.strftime("%Y")
            tag_number = f"{prefix}{next_number:04d}/{month}/{year}"

            cursor.execute("""
                INSERT INTO cattle (
                    name, tag_number, breed, birth_date,
                    sex, status_category, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                calf_name, tag_number, breed, birth_date,
                calf_sex, "young_stock", "newborn calf"
            ))

        # ✅ Update dam to lactating
        cursor.execute("""
            UPDATE cattle SET status_category = 'mature_stock', status = 'lactating'
            WHERE tag_number = %s
        """, (dam_tag,))

        db.commit()
        update_cattle_statuses(db)

        flash("✅ Calving record saved successfully!", "success")
        return redirect(url_for('calving.calving_list'))

    return render_template('calving/add_calving.html', dams=dams)

@calving_bp.route('/list', methods=['GET'])
@login_required
def calving_list():
    cursor = get_cursor()
    search = request.args.get('search', '').strip()

    if search:
        query = """
            SELECT * FROM calving
            WHERE calf_name ILIKE %s OR dam_name ILIKE %s OR dam_tag_number ILIKE %s
            ORDER BY birth_date DESC
        """
        search_param = f"%{search}%"
        cursor.execute(query, (search_param, search_param, search_param))
    else:
        cursor.execute("SELECT * FROM calving ORDER BY birth_date DESC")

    records = cursor.fetchall()
    return render_template('calving/calving_list.html', records=records)

@calving_bp.route('/edit/<int:calving_id>', methods=['GET', 'POST'])
@login_required
def edit_calving(calving_id):
    db = get_db()
    cursor = get_cursor()

    cursor.execute("SELECT * FROM calving WHERE calving_id = %s", (calving_id,))
    record = cursor.fetchone()

    if not record:
        flash("❌ Record not found.", "danger")
        return redirect(url_for('calving.calving_list'))

    cursor.execute("""
        SELECT DISTINCT tag_number, name 
        FROM cattle 
        WHERE sex = 'F'
    """)
    dams = cursor.fetchall()

    if request.method == 'POST':
        dam_tag = request.form['dam_tag_number']
        dam_name = request.form['dam_name']
        calf_name = request.form['calf_name']
        calf_sex = request.form['calf_sex']
        birth_date = request.form['birth_date']
        breed = request.form['breed']
        calf_status = request.form['calf_status']
        notes = request.form.get('notes', '')

        cursor.execute("""
            UPDATE calving SET 
                dam_tag_number = %s, dam_name = %s, calf_name = %s, calf_sex = %s, 
                birth_date = %s, breed = %s, calf_condition = %s, notes = %s
            WHERE calving_id = %s
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
    cursor = get_cursor()

    cursor.execute("SELECT * FROM calving WHERE calving_id = %s", (calving_id,))
    record = cursor.fetchone()

    if not record:
        flash("❌ Record not found.", "danger")
        return redirect(url_for('calving.calving_list'))

    if request.method == 'POST':
        cursor.execute("DELETE FROM calving WHERE calving_id = %s", (calving_id,))
        db.commit()
        flash("🗑️ Calving record deleted successfully.", "info")
        return redirect(url_for('calving.calving_list'))

    return render_template('calving/delete_calving.html', record=record)
