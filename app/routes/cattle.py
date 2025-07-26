# ✅ cattle.py (Updated with pagination, filtering, admin control)
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime
from database import get_db, get_cursor
from app.utils.status_updater import update_cattle_statuses
from app.utils.status_logic import determine_initial_status
from app.utils.decorators import login_required, admin_required

cattle_bp = Blueprint('cattle', __name__, url_prefix='/cattle')


# ✅ List Cattle (with pagination, filtering)
@cattle_bp.route('/')
@login_required
def cattle_list():
    db = get_db()
    cursor = get_cursor()

    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page

    search = request.args.get('search', '').strip()
    sex = request.args.get('sex')
    status_category = request.args.get('status_category')

    query = "SELECT * FROM cattle WHERE is_active = TRUE"
    params = []

    if search:
        query += " AND (LOWER(name) LIKE %s OR LOWER(tag_number) LIKE %s OR LOWER(breed) LIKE %s)"
        keyword = f"%{search.lower()}%"
        params += [keyword, keyword, keyword]

    if sex:
        query += " AND sex = %s"
        params.append(sex)

    if status_category:
        query += " AND status_category = %s"
        params.append(status_category)

    count_query = f"SELECT COUNT(*) AS total FROM ({query}) AS filtered"
    cursor.execute(count_query, params)
    count_row = cursor.fetchone()
    total_records = count_row['total'] if count_row else 0
    total_pages = (total_records + per_page - 1) // per_page

    query += " ORDER BY cattle_id DESC LIMIT %s OFFSET %s"
    params += [per_page, offset]
    cursor.execute(query, params)
    cattle = cursor.fetchall()

    return render_template('cattle/cattle_list.html',
        cattle=cattle,
        current_page=page,
        total_pages=total_pages
    )


# ✅ Add Cattle
@cattle_bp.route('/add', methods=['POST'])
@login_required
def add_cattle():
    db = get_db()
    cursor = get_cursor()

    name = request.form['name']
    breed = request.form['breed']
    birth_date_str = request.form['birth_date']
    sex = request.form['sex'].strip().title()
    remark = request.form['remark']

    # Validate and parse birth date
    try:
        birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash("Invalid birth date format", "danger")
        return redirect(url_for('cattle.cattle_list'))

    # Generate tag number
    today = datetime.today()
    prefix = "TNF"
    month = today.strftime('%m')
    year = today.strftime('%Y')

    cursor.execute("SELECT tag_number FROM cattle WHERE tag_number LIKE 'TNF%' ORDER BY cattle_id DESC LIMIT 1")
    latest_tag = cursor.fetchone()

    if latest_tag:
        last_number = int(latest_tag['tag_number'].split('/')[0][3:])
        next_number = last_number + 1
    else:
        next_number = 1

    tag_number = f"{prefix}{str(next_number).zfill(4)}/{month}/{year}"

    # Determine status and category
    status = None
    status_category = None
    age_months = (datetime.today().year - birth_date.year) * 12 + (datetime.today().month - birth_date.month)

    if sex == 'Female':
        if age_months <= 10:
            status_category, status = determine_initial_status(sex, birth_date)
        else:
            # Expect user selection for 11+ month old females
            status_category = request.form.get('status_category')
            if status_category == 'young_stock':
                status = 'bullying heifer'
            elif status_category == 'mature_stock':
                status = request.form.get('status')
                if not status:
                    flash("Please select a valid status for mature stock cattle.", "danger")
                    return redirect(url_for('cattle.cattle_list'))
            else:
                flash("Invalid or missing status category for female cattle over 10 months old.", "danger")
                return redirect(url_for('cattle.cattle_list'))

    elif sex == 'Male':
        status_category, status = determine_initial_status(sex, birth_date)
        if not status_category or not status:
            flash("Unable to determine status for male cattle.", "danger")
            return redirect(url_for('cattle.cattle_list'))

    else:
        flash("Invalid sex value.", "danger")
        return redirect(url_for('cattle.cattle_list'))

    # Insert into database
    try:
        cursor.execute('''
            INSERT INTO cattle (
                name, tag_number, breed, birth_date, sex,
                status_category, status, recorded_by, is_active, remark
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s)
        ''', (
            name, tag_number, breed, birth_date, sex.upper(),
            status_category, status, session['user_id'], remark
        ))
        db.commit()
        update_cattle_statuses(db)
        flash(f"Cattle added successfully. Tag Number: {tag_number}", "success")
    except Exception as e:
        flash(f"Error adding cattle: {e}", "danger")

    return redirect(url_for('cattle.cattle_list'))


# ✅ Edit Cattle
@cattle_bp.route('/edit/<int:cattle_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_cattle(cattle_id):
    db = get_db()
    cursor = get_cursor()

    if request.method == 'POST':
        name = request.form['name']
        breed = request.form['breed']
        birth_date = request.form['birth_date']
        sex = request.form['sex']
        remark = request.form['remark']

        status_category = request.form.get('status_category')
        status = 'bullying heifer' if status_category == 'young_stock' else request.form.get('status')

        cursor.execute('''
            UPDATE cattle SET
                name=%s, breed=%s, birth_date=%s, sex=%s,
                status_category=%s, status=%s, remark=%s
            WHERE cattle_id=%s
        ''', (name, breed, birth_date, sex, status_category, status, remark, cattle_id))
        db.commit()
        flash("Cattle updated successfully", "success")
        return redirect(url_for('cattle.cattle_list'))

    cursor.execute("SELECT * FROM cattle WHERE cattle_id = %s", (cattle_id,))
    cattle = cursor.fetchone()
    return render_template('cattle/edit_cattle.html', cattle=cattle)


# ✅ Delete Cattle
@cattle_bp.route('/delete/<int:cattle_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def delete_cattle(cattle_id):
    db = get_db()
    cursor = get_cursor()

    if request.method == 'POST':
        cursor.execute("UPDATE cattle SET is_active = FALSE, remark = 'deleted' WHERE cattle_id = %s", (cattle_id,))
        db.commit()
        flash("Cattle deleted successfully", "success")
        return redirect(url_for('cattle.cattle_list'))

    cursor.execute("SELECT * FROM cattle WHERE cattle_id = %s", (cattle_id,))
    cattle = cursor.fetchone()
    return render_template('cattle/delete_cattle.html', cattle=cattle)


# ✅ Archive Cattle
@cattle_bp.route('/archive', methods=['POST'])
@login_required
@admin_required
def archive_cattle():
    db = get_db()
    cursor = get_cursor()

    cattle_id = request.form.get('cattle_id')
    remark = request.form.get('remark')
    cursor.execute("UPDATE cattle SET is_active = FALSE, remark = %s WHERE cattle_id = %s", (remark, cattle_id))
    db.commit()
    flash("Cattle archived as: " + remark, "success")
    return redirect(url_for('cattle.cattle_list'))
