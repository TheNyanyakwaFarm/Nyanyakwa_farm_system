from flask import Blueprint, render_template, request, redirect, flash, session, url_for
from datetime import datetime
from database import get_db, get_cursor
from app.utils.decorators import login_required, admin_required
from app.utils.status_updater import update_cattle_statuses

calving_bp = Blueprint('calving', __name__, url_prefix='/calving')


@calving_bp.route('/')
@login_required
def calving_list():
    cursor = get_cursor()

    # Fetch active calving records
    cursor.execute("""
        SELECT c.calving_id, c.dam_id, dam.tag_number, dam.name AS dam_name,
               c.calf_name, c.calf_sex, c.birth_date, c.breed, c.calf_condition,
               c.notes, c.recorded_by, c.created_at, c.updated_at, c.remark
        FROM calving c
        JOIN cattle dam ON c.dam_id = dam.cattle_id
        WHERE c.is_active = TRUE
        ORDER BY c.birth_date DESC
    """)
    records = cursor.fetchall()

    # Fetch eligible dams for modal dropdown
    cursor.execute("""
        SELECT DISTINCT ca.cattle_id, ca.tag_number, ca.name
        FROM cattle ca
        JOIN breeding b ON ca.cattle_id = b.cattle_id
        WHERE b.steaming_date <= CURRENT_DATE
          AND ca.is_active = TRUE
        ORDER BY ca.tag_number
    """)
    eligible_dams = cursor.fetchall()

    return render_template('calving/calving_list.html', records=records, eligible_dams=eligible_dams)


@calving_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_calving():
    db = get_db()
    cursor = get_cursor()

    if request.method == 'POST':
        dam_id = request.form.get('dam_id')
        calf_name = request.form.get('calf_name')
        calf_sex = request.form.get('calf_sex')
        birth_date = request.form.get('birth_date')
        breed = request.form.get('breed')
        calf_condition = request.form.get('calf_condition')
        notes = request.form.get('notes')

        # Validate dam
        cursor.execute("""
            SELECT ca.tag_number, ca.name
            FROM cattle ca
            JOIN breeding b ON ca.cattle_id = b.cattle_id
            WHERE ca.cattle_id = %s AND b.steaming_date IS NOT NULL
              AND b.steaming_date <= CURRENT_DATE
              AND ca.is_active = TRUE
            ORDER BY b.breeding_date DESC
            LIMIT 1
        """, (dam_id,))
        dam = cursor.fetchone()

        if not dam:
            flash('Selected dam is not eligible for calving (must have a breeding record and be past steaming date).', 'danger')
            return redirect(url_for('calving.calving_list'))

        dam_tag_number = dam.get('tag_number')
        dam_name = dam.get('name')
        recorded_by = session.get('username', 'unknown')

        # Insert into calving table
        cursor.execute("""
            INSERT INTO calving (
                dam_id, dam_tag_number, dam_name, calf_name, calf_sex,
                birth_date, breed, calf_condition, notes, recorded_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING calving_id
        """, (dam_id, dam_tag_number, dam_name, calf_name, calf_sex, birth_date,
              breed, calf_condition, notes, recorded_by))

        # Generate unique calf tag
        tag_prefix = 'CLF'
        cursor.execute("""
            SELECT MAX(CAST(SUBSTRING(tag_number FROM '[0-9]+') AS INTEGER))
            FROM cattle WHERE tag_number LIKE %s
        """, (f'{tag_prefix}%',))
        row = cursor.fetchone()
        max_tag = row[0] if row and row[0] is not None else 0
        next_tag_number = f"{tag_prefix}{(max_tag + 1) if max_tag else 1:04}"

        # Insert calf into cattle table
        cursor.execute("""
            INSERT INTO cattle (
                tag_number, name, sex, birth_date, breed,
                status_category, status, is_active, remark, recorded_by
            )
            VALUES (%s, %s, %s, %s, %s,
                    'young stock', 'newborn calf', TRUE, 'active', %s)
        """, (next_tag_number, calf_name, calf_sex, birth_date, breed, recorded_by))

        db.commit()
        update_cattle_statuses(db)

        flash(f'Calving record added. New calf tag: {next_tag_number}', 'success')
        return redirect(url_for('calving.calving_list'))

    # GET method: show form
    cursor.execute("""
        SELECT DISTINCT ca.cattle_id, ca.tag_number, ca.name
        FROM cattle ca
        JOIN breeding b ON ca.cattle_id = b.cattle_id
        WHERE b.steaming_date <= CURRENT_DATE
          AND ca.is_active = TRUE
        ORDER BY ca.tag_number
    """)
    eligible_dams = cursor.fetchall()
    return render_template('calving/calving_form.html', eligible_dams=eligible_dams)


@calving_bp.route('/delete/<int:calving_id>', methods=['POST'])
@login_required
@admin_required
def soft_delete_calving(calving_id):
    db = get_db()
    cursor = get_cursor()
    remark = request.form.get('remark', 'soft deleted')

    cursor.execute("""
        UPDATE calving
        SET is_active = FALSE, remark = %s
        WHERE calving_id = %s
    """, (remark, calving_id))
    db.commit()
    flash('Calving record archived.', 'info')
    return redirect(url_for('calving.calving_list'))


@calving_bp.route('/hard_delete/<int:calving_id>', methods=['POST'])
@login_required
@admin_required
def hard_delete_calving(calving_id):
    db = get_db()
    cursor = get_cursor()

    cursor.execute("DELETE FROM calving WHERE calving_id = %s", (calving_id,))
    db.commit()
    flash('Calving record permanently deleted.', 'danger')
    return redirect(url_for('calving.calving_list'))
