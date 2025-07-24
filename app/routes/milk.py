from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import date as dt_date
from database import get_db, get_cursor
from app.utils.decorators import login_required, admin_required 
from app.utils.status_updater import update_cattle_statuses

milk_bp = Blueprint('milk', __name__)

@milk_bp.route('/milk', methods=['GET', 'POST'])
@login_required
def milk_list():
    db = get_db()
    cursor = get_cursor()

    update_cattle_statuses(db)

    search_query = request.args.get('search', '')
    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page

    base_query = '''SELECT mp.id, mp.date, mp.cattle_id, c.name AS cattle_name,
                           mp.morning_milk, mp.mid_day_milk, mp.evening_milk,
                           u.username AS recorded_by, mp.notes
                    FROM milk_production mp
                    JOIN cattle c ON mp.cattle_id = c.id
                    LEFT JOIN users u ON mp.recorded_by = u.id
                    WHERE c.is_active = TRUE'''

    params = []
    if search_query:
        base_query += " AND (c.name ILIKE %s OR u.username ILIKE %s)"
        params.extend([f"%{search_query}%", f"%{search_query}%"])

    count_query = f"SELECT COUNT(*) FROM ({base_query}) AS count_query"
    cursor.execute(count_query, params)
    total_records = cursor.fetchone()[0]

    base_query += " ORDER BY mp.date DESC, mp.id DESC LIMIT %s OFFSET %s"
    params.extend([per_page, offset])
    cursor.execute(base_query, params)
    records = cursor.fetchall()

    total_pages = (total_records + per_page - 1) // per_page

    # Get all active cattle and include their status info
    cursor.execute("""
        SELECT id, name, status, status_category
        FROM cattle
        WHERE is_active = TRUE
        ORDER BY name ASC
    """)
    all_cattle = cursor.fetchall()

    # Weekly Summary
    cursor.execute('''
        SELECT DATE_TRUNC('week', date) AS week_start,
               SUM(COALESCE(morning_milk, 0) + COALESCE(mid_day_milk, 0) + COALESCE(evening_milk, 0)) AS total_milk
        FROM milk_production
        GROUP BY week_start
        ORDER BY week_start DESC
        LIMIT 4
    ''')
    weekly_summary = cursor.fetchall()

    # Monthly Summary
    cursor.execute('''
        SELECT DATE_TRUNC('month', date) AS month,
               SUM(COALESCE(morning_milk, 0) + COALESCE(mid_day_milk, 0) + COALESCE(evening_milk, 0)) AS total_milk
        FROM milk_production
        GROUP BY month
        ORDER BY month DESC
        LIMIT 6
    ''')
    monthly_summary = cursor.fetchall()

    return render_template('milk/milk_list.html',
                           records=records,
                           page=page,
                           total_pages=total_pages,
                           search_query=search_query,
                           all_cattle=all_cattle,
                           weekly_summary=weekly_summary,
                           monthly_summary=monthly_summary)

@milk_bp.route('/milk/add', methods=['POST'])
@login_required
def record_milk():
    db = get_db()
    cursor = get_cursor()

    today = dt_date.today()
    cattle_id = request.form['cattle_id']
    session_type = request.form['session_type']
    quantity = request.form['quantity']
    notes = request.form.get('notes')
    recorded_by = session['user_id']

    cursor.execute("SELECT id FROM milk_production WHERE cattle_id = %s AND date = %s", (cattle_id, today))
    existing = cursor.fetchone()

    if existing:
        update_field = {
            'morning': 'morning_milk',
            'mid_day': 'mid_day_milk',
            'evening': 'evening_milk'
        }.get(session_type)

        if update_field:
            cursor.execute(f"""
                UPDATE milk_production SET {update_field} = %s, recorded_by = %s, notes = %s
                WHERE id = %s
            """, (quantity, recorded_by, notes, existing[0]))
    else:
        cursor.execute("""INSERT INTO milk_production (cattle_id, date, recorded_by, notes, {}) VALUES (%s, %s, %s, %s, %s)""".format({
            'morning': 'morning_milk',
            'mid_day': 'mid_day_milk',
            'evening': 'evening_milk'
        }[session_type]), (cattle_id, today, recorded_by, notes, quantity))

    db.commit()
    flash('Milk record saved successfully!', 'success')
    return redirect(url_for('milk.milk_list'))

@milk_bp.route('/milk/edit/<int:record_id>', methods=['POST'])
@login_required
@admin_required
def edit_milk(record_id):
    db = get_db()
    cursor = get_cursor()

    morning = request.form.get('morning_milk') or 0
    mid_day = request.form.get('mid_day_milk') or 0
    evening = request.form.get('evening_milk') or 0
    notes = request.form.get('notes')

    cursor.execute("""
        UPDATE milk_production
        SET morning_milk = %s, mid_day_milk = %s, evening_milk = %s, notes = %s
        WHERE id = %s
    """, (morning, mid_day, evening, notes, record_id))

    db.commit()
    flash('Milk record updated successfully!', 'success')
    return redirect(url_for('milk.milk_list'))

@milk_bp.route('/milk/delete/<int:record_id>', methods=['POST'])
@login_required
@admin_required
def delete_milk(record_id):
    db = get_db()
    cursor = get_cursor()
    cursor.execute("DELETE FROM milk_production WHERE id = %s", (record_id,))
    db.commit()
    flash('Milk record deleted successfully.', 'success')
    return redirect(url_for('milk.milk_list'))
