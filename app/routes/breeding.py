from flask import Blueprint, render_template, request, redirect, flash, session, url_for
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from database import get_db, get_cursor
from functools import wraps
from app.utils.status_updater import update_cattle_statuses

breeding_bp = Blueprint('breeding', __name__, url_prefix='/breeding')

# 🔐 Decorators
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return wrapper

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            if session.get('role') not in roles:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('dashboard.dashboard'))
            return f(*args, **kwargs)
        return wrapper
    return decorator




# ➕ Add Breeding Record
@breeding_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_breeding():
    db = get_db()
    cursor = get_cursor()

    if request.method == 'POST':
        cattle_id = request.form.get('cattle_id')
        method = request.form.get('method')
        breeding_date = request.form.get('breeding_date')
        breeding_attempt_number = request.form.get('breeding_attempt_number')
        notes = request.form.get('notes')

        if not all([cattle_id, method, breeding_date, breeding_attempt_number]):
            flash("⚠️ Please fill in all required fields.", "danger")
            return redirect(url_for('breeding.add_breeding'))

        # ✅ Cattle eligibility
        cursor.execute("""
            SELECT sex, status, status_category, birth_date
            FROM cattle WHERE cattle_id = %s
        """, (cattle_id,))
        cattle = cursor.fetchone()

        if not cattle or cattle['sex'] != 'F':
            flash("❌ Breeding can only be recorded for female cattle.", "danger")
            return redirect(url_for('breeding.add_breeding'))

        try:
            birth_date = cattle['birth_date']
            birth_date = birth_date if isinstance(birth_date, datetime) else datetime.strptime(str(birth_date), "%Y-%m-%d")
            age_in_months = (datetime.now() - birth_date).days // 30
        except Exception:
            flash("⚠️ Invalid or missing birth date for this animal.", "danger")
            return redirect(url_for('breeding.add_breeding'))

        if cattle['status_category'] == 'young_stock':
            if cattle['status'] != 'bullying heifer' or age_in_months < 12:
                flash("❌ Young stock must be 'bullying heifer' and at least 12 months old.", "danger")
                return redirect(url_for('breeding.add_breeding'))
        elif cattle['status_category'] == 'mature_stock':
            if cattle['status'] != 'lactating':
                flash("❌ Mature stock must be 'lactating' to breed.", "danger")
                return redirect(url_for('breeding.add_breeding'))

        # ✅ Check 21-day gap
        cursor.execute("""
            SELECT breeding_date FROM breeding_records 
            WHERE cattle_id = %s ORDER BY breeding_date DESC LIMIT 1
        """, (cattle_id,))
        last_breeding = cursor.fetchone()

        try:
            current_date = datetime.strptime(breeding_date, "%Y-%m-%d")
        except ValueError:
            flash("⚠️ Invalid breeding date format.", "danger")
            return redirect(url_for('breeding.add_breeding'))

        if last_breeding:
            last_date = last_breeding['breeding_date']
            last_date = last_date if isinstance(last_date, datetime) else datetime.strptime(str(last_date), "%Y-%m-%d")
            if (current_date - last_date).days < 21:
                flash(f"❌ This cow was served { (current_date - last_date).days } days ago.", "danger")
                return redirect(url_for('breeding.add_breeding'))

        # 🧬 AI-specific fields
        semen_type = semen_price = semen_batch_number = sire_name = None
        if method == 'AI':
            semen_type = request.form.get('semen_type')
            semen_price = request.form.get('semen_price')
            semen_batch_number = request.form.get('semen_batch_number')
            sire_name = request.form.get('sire_name')

            if not all([semen_type, semen_price, semen_batch_number, sire_name]):
                flash("⚠️ All AI fields must be filled.", "danger")
                return redirect(url_for('breeding.add_breeding'))

            try:
                semen_price = float(semen_price)
            except ValueError:
                flash("⚠️ Semen price must be a number.", "danger")
                return redirect(url_for('breeding.add_breeding'))

        # 📅 Auto-calculate
        pregnancy_check_date = (current_date + timedelta(days=42)).strftime("%Y-%m-%d")
        steaming_date = (current_date + relativedelta(months=7)).strftime("%Y-%m-%d")

        try:
            cursor.execute("""
                INSERT INTO breeding_records (
                    cattle_id, method, semen_type, semen_price,
                    semen_batch_number, sire_name,
                    breeding_date, breeding_attempt_number, notes,
                    steaming_date, pregnancy_check_date, pregnancy_test_result
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                cattle_id, method, semen_type, semen_price,
                semen_batch_number, sire_name,
                breeding_date, breeding_attempt_number, notes,
                steaming_date, pregnancy_check_date, None
            ))
            db.commit()

            # ✅ Update cattle status based on latest event
            update_cattle_statuses(db)

            flash("✅ Breeding record added successfully.", "success")
        except Exception as e:
            flash(f"❌ Failed to add breeding record: {e}", "danger")

        return redirect(url_for('breeding.add_breeding'))

    # 📥 GET: Eligible cattle
    cursor.execute("""
        SELECT cattle_id, tag_number, name
        FROM cattle
        WHERE sex = 'F'
          AND (
              (status_category = 'young_stock' AND status = 'bullying heifer' AND
               birth_date <= CURRENT_DATE - INTERVAL '12 months')
              OR
              (status_category = 'mature_stock' AND status = 'lactating')
          )
    """)
    cattle_list = cursor.fetchall()

    return render_template("breeding/add_breeding.html", cattle_list=cattle_list)


# ✏️ Edit (placeholder)
@breeding_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def edit_breeding(id):
    cursor = get_cursor()

    cursor.execute("""
        SELECT br.*, c.tag_number, c.name AS cattle_name
        FROM breeding_records br
        JOIN cattle c ON br.cattle_id = c.cattle_id
        WHERE br.id = %s
    """, (id,))
    record = cursor.fetchone()

    if not record:
        flash("❌ Record not found.", "danger")
        return redirect(url_for('breeding.breeding_records'))

    return render_template("breeding/edit_breeding.html", record=record)


# 📋 List breeding records
@breeding_bp.route('/records')
@login_required
def breeding_records():
    cursor = get_cursor()

    cursor.execute("""
        SELECT br.*, c.name AS cattle_name, c.tag_number
        FROM breeding_records br
        JOIN cattle c ON br.cattle_id = c.cattle_id
        WHERE c.sex = 'F'
        ORDER BY br.breeding_date DESC
    """)
    records = cursor.fetchall()

    return render_template("breeding/breeding_records.html", records=records)



# ✅ Update pregnancy test
@breeding_bp.route('/update_status/<int:id>', methods=['POST'])
@login_required
def update_pregnancy_status(id):
    status = request.form.get('status')
    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute("""
            UPDATE breeding_records
            SET pregnancy_test_result = %s, pregnancy_check_date = CURRENT_DATE
            WHERE id = %s
        """, (status, id))
        db.commit()
        flash(f"✅ Status updated to: {status}", "success")
    except Exception as e:
        flash(f"❌ Failed to update: {e}", "danger")

    return redirect(url_for('breeding.breeding_records'))
