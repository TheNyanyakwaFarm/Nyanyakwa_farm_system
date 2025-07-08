from flask import Blueprint, render_template, request, redirect, flash, session, url_for
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from database import get_db
from functools import wraps
from flask_login import login_required
from utils.status_updater import update_cattle_statuses



breeding_bp = Blueprint('breeding', __name__, url_prefix='/breeding')

# 🔐 Decorator to protect routes
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
            role = session.get('role')
            if role not in roles:
                flash(f'You do not have permission to access this page as {role}.', 'danger')
                return redirect(url_for('dashboard.dashboard'))
            return f(*args, **kwargs)
        return wrapper
    return decorator

# ➕ Add Breeding Record

@breeding_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_breeding():
    db = get_db()

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
        cattle = db.execute("""
            SELECT sex, status, status_category, birth_date
            FROM cattle WHERE cattle_id = ?
        """, (cattle_id,)).fetchone()

        if not cattle or cattle['sex'] != 'F':
            flash("❌ Breeding can only be recorded for female cattle.", "danger")
            return redirect(url_for('breeding.add_breeding'))

        try:
            birth_date = datetime.strptime(cattle['birth_date'], "%Y-%m-%d")
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
        last_breeding = db.execute("""
            SELECT breeding_date FROM breeding_records 
            WHERE cattle_id = ? ORDER BY breeding_date DESC LIMIT 1
        """, (cattle_id,)).fetchone()

        try:
            current_date = datetime.strptime(breeding_date, "%Y-%m-%d")
        except ValueError:
            flash("⚠️ Invalid breeding date format.", "danger")
            return redirect(url_for('breeding.add_breeding'))

        if last_breeding:
            last_date = datetime.strptime(last_breeding['breeding_date'], "%Y-%m-%d")
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

        # 📅 Auto-calculate dates
        pregnancy_check_date = (current_date + timedelta(days=42)).strftime("%Y-%m-%d")
        steaming_date = (current_date + relativedelta(months=7)).strftime("%Y-%m-%d")

        try:
            db.execute("""
                INSERT INTO breeding_records (
                    cattle_id, method, semen_type, semen_price,
                    semen_batch_number, sire_name,
                    breeding_date, breeding_attempt_number, notes,
                    steaming_date, pregnancy_check_date, pregnancy_test_result
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cattle_id, method, semen_type, semen_price,
                semen_batch_number, sire_name,
                breeding_date, breeding_attempt_number, notes,
                steaming_date, pregnancy_check_date, None
            ))
            db.commit()

            # ✅ Update status based on new event
            update_cattle_statuses(db)

            flash("✅ Breeding record added successfully.", "success")
        except Exception as e:
            flash(f"❌ Failed to add breeding record: {e}", "danger")

        return redirect(url_for('breeding.add_breeding'))

    # 📥 GET: Show eligible females
    today = datetime.today().strftime("%Y-%m-%d")
    cattle_list = db.execute("""
        SELECT cattle_id, tag_number, name
        FROM cattle
        WHERE sex = 'F'
          AND (
              (status_category = 'young_stock' AND status = 'bullying heifer' AND 
               (julianday(?) - julianday(birth_date)) / 30 >= 12)
              OR
              (status_category = 'mature_stock' AND status = 'lactating')
          )
    """, (today,)).fetchall()

    return render_template("breeding/add_breeding.html", cattle_list=cattle_list)

# ✏️ Edit breeding record
@breeding_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def edit_breeding(id):
    db = get_db()

    record = db.execute("""
        SELECT br.*, c.tag_number, c.name AS cattle_name
        FROM breeding_records br
        JOIN cattle c ON br.cattle_id = c.cattle_id
        WHERE br.id = ?
    """, (id,)).fetchone()

    if not record:
        flash("❌ Record not found.", "danger")
        return redirect(url_for('breeding.breeding_records'))

    if request.method == 'POST':
        # Same field logic as add_breeding (copy same checks here)
        # ...
        pass  # You can reuse the earlier edit logic here

    return render_template("breeding/edit_breeding.html", record=record)

# 📋 View records
@breeding_bp.route('/records')
@login_required
def breeding_records():
    db = get_db()
    records = db.execute("""
        SELECT br.*, c.name AS cattle_name, c.tag_number
        FROM breeding_records br
        JOIN cattle c ON br.cattle_id = c.cattle_id
        WHERE c.sex = 'F'
        ORDER BY br.breeding_date DESC
    """).fetchall()

    return render_template("breeding/breeding_records.html", records=records)

# ✅ Update pregnancy test
@breeding_bp.route('/update_status/<int:id>', methods=['POST'])
@login_required
def update_pregnancy_status(id):
    status = request.form.get('status')
    db = get_db()

    try:
        db.execute("""
            UPDATE breeding_records
            SET pregnancy_test_result = ?, pregnancy_check_date = CURRENT_DATE
            WHERE id = ?
        """, (status, id))
        db.commit()
        flash(f"✅ Status updated to: {status}", "success")
    except Exception as e:
        flash(f"❌ Failed to update: {e}", "danger")

    return redirect(url_for('breeding.breeding_records'))
