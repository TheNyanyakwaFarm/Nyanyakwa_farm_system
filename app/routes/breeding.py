from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime
from dateutil.relativedelta import relativedelta
from db import get_db
from auth import login_required
from app.utils.status_updater import update_cattle_statuses

breeding_bp = Blueprint('breeding', __name__, url_prefix='/breeding')

@breeding_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_breeding():
    db = get_db()
    cursor = db.cursor()

    if request.method == 'POST':
        cattle_id = request.form.get('cattle_id')
        method = request.form.get('method')
        semen_type = request.form.get('semen_type')
        semen_price = request.form.get('semen_price') or None
        semen_batch_number = request.form.get('semen_batch_number')
        sire_name = request.form.get('sire_name')
        breeding_date_str = request.form.get('breeding_date')
        breeding_attempt_number = request.form.get('breeding_attempt_number')
        notes = request.form.get('notes')
        pregnancy_check_date = request.form.get('pregnancy_check_date') or None
        pregnancy_test_result = request.form.get('pregnancy_test_result') or None
        breeding_outcome = request.form.get('breeding_outcome') or 'pending'
        remark = request.form.get('remark') or notes
        recorded_by = session.get('user_id')
        created_at = datetime.now()

        try:
            breeding_date = datetime.strptime(breeding_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid breeding date format.", "danger")
            return redirect(request.url)

        steaming_date = breeding_date + relativedelta(months=+7)
        expected_calving_date = breeding_date + relativedelta(months=+9)

        # ✅ Check cattle status before allowing breeding
        cursor.execute("SELECT status FROM cattle WHERE id = %s", (cattle_id,))
        status_result = cursor.fetchone()

        if not status_result:
            flash("Cattle not found.", "danger")
            return redirect(request.url)

        cattle_status = status_result[0].lower()
        if cattle_status not in ('lactating', 'bullying heifer'):
            flash(f"Breeding not allowed. This cow is currently '{cattle_status.title()}'.", "danger")
            return redirect(request.url)

        # ✅ Enforce 21-day interval rule (unless last outcome was 'failed')
        cursor.execute("""
            SELECT breeding_date, breeding_outcome
            FROM breeding_records
            WHERE cattle_id = %s
            ORDER BY breeding_date DESC
            LIMIT 1
        """, (cattle_id,))
        last_record = cursor.fetchone()

        if last_record:
            last_breeding_date, last_outcome = last_record
            days_since_last = (breeding_date - last_breeding_date).days

            if days_since_last < 21 and last_outcome != 'failed':
                flash(f"Cow was bred {days_since_last} days ago (Outcome: {last_outcome}). Minimum interval is 21 days.", "danger")
                return redirect(request.url)

        # ✅ Insert breeding record
        cursor.execute("""
            INSERT INTO breeding_records (
                cattle_id, recorded_by, method, semen_type, semen_price,
                semen_batch_number, sire_name, breeding_date,
                breeding_attempt_number, notes, steaming_date,
                pregnancy_check_date, pregnancy_test_result,
                created_at, breeding_outcome, remark
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            cattle_id, recorded_by, method, semen_type, semen_price,
            semen_batch_number, sire_name, breeding_date,
            breeding_attempt_number, notes, steaming_date,
            pregnancy_check_date, pregnancy_test_result,
            created_at, breeding_outcome, remark
        ))

        db.commit()
        flash("✅ Breeding record added successfully.", "success")
        return redirect(url_for('breeding.list_breeding'))

    # GET: Show add form with active cattle list
    cursor.execute("SELECT id, tag_number FROM cattle WHERE is_active = TRUE ORDER BY tag_number")
    cattle = cursor.fetchall()

    return render_template('breeding/add_breeding.html', cattle=cattle)


@breeding_bp.route('/records')
@login_required
def list_breeding():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT br.id, c.tag_number, br.method, br.semen_type, br.semen_price,
               br.semen_batch_number, br.sire_name, br.breeding_date,
               br.breeding_attempt_number, br.notes, br.steaming_date,
               br.pregnancy_check_date, br.pregnancy_test_result,
               br.created_at, br.breeding_outcome, br.remark,
               u.full_name AS recorded_by_name
        FROM breeding_records br
        JOIN cattle c ON br.cattle_id = c.id
        LEFT JOIN users u ON br.recorded_by = u.id
        ORDER BY br.breeding_date DESC
    """)
    records = cursor.fetchall()

    return render_template('breeding/breeding_list.html', records=records)
