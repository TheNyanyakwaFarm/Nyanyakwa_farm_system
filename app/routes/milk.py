from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import date as dt_date
from database import get_db, get_cursor
from app.utils.decorators import login_required, admin_required
from app.utils.status_updater import update_cattle_statuses
from datetime import datetime  # ✅ add at the top if not already present


milk_bp = Blueprint('milk', __name__)

@milk_bp.route('/milk', methods=['GET', 'POST'])
@login_required
def milk_list():
    db = get_db()
    cursor = get_cursor()
    update_cattle_statuses(db)

    search_query = request.args.get('search', '')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page

    # ✅ Prepare filters
    where_clauses = ["c.is_active = TRUE"]
    params = []

    if start_date:
        where_clauses.append("mp.date >= %s")
        params.append(start_date)

    if end_date:
        where_clauses.append("mp.date <= %s")
        params.append(end_date)

    if search_query:
        where_clauses.append("(c.name ILIKE %s OR u.username ILIKE %s)")
        params.extend([f"%{search_query}%", f"%{search_query}%"])

    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    
    # Sanitize where_sql: remove leading WHERE if accidentally included
    if where_sql.strip().lower().startswith("where "):
        where_sql = where_sql.strip()[6:]

    # ✅ Base query with filters
    base_query = f'''
        SELECT 
            mp.id,
            mp.date,
            mp.cattle_id,
            c.tag_number,
            c.name AS cattle_name,
            c.status,
            c.status_category,
            mp.morning_milk,
            mp.mid_day_milk,
            mp.evening_milk,
            u.username AS recorded_by,
            mp.notes,
            lc.latest_calving_date
        FROM milk_production mp
        JOIN cattle c ON mp.cattle_id = c.cattle_id
        LEFT JOIN users u ON mp.recorded_by = u.id

        -- Latest calving date per cow
        LEFT JOIN (
            SELECT 
                dam_id, 
                MAX(calving_date) AS latest_calving_date
            FROM calving
            WHERE is_active = TRUE
            GROUP BY dam_id
        ) lc ON lc.dam_id = c.cattle_id

        -- Latest breeding date per cow
        LEFT JOIN (
            SELECT 
                cattle_id,
                MAX(breeding_date) AS latest_breeding_date
            FROM breeding
            WHERE is_active = TRUE
            GROUP BY cattle_id
        ) lb ON lb.cattle_id = c.cattle_id

        WHERE 
            c.status IN ('lactating', 'lactating in_calf')
            AND (
                c.status != 'lactating in_calf' OR
                (
                    lb.latest_breeding_date IS NOT NULL AND 
                    CURRENT_DATE <= lb.latest_breeding_date + INTERVAL '7 months'
                )
            )
            AND c.is_active = TRUE
            {f"AND {where_sql}" if where_sql else ""}
        ORDER BY 
            lc.latest_calving_date DESC NULLS LAST,
            mp.date DESC,
            mp.id DESC
    '''



    # ✅ Count total matching records for pagination
    count_query = f"SELECT COUNT(*) AS total FROM ({base_query}) AS count_query"
    cursor.execute(count_query, params)
    total_records = cursor.fetchone()['total']

    # ✅ Apply pagination
    paginated_query = base_query + " LIMIT %s OFFSET %s"
    cursor.execute(paginated_query, params + [per_page, offset])
    records = cursor.fetchall()

    total_pages = (total_records + per_page - 1) // per_page

    # ✅ Get all active cattle
    cursor.execute("""
        SELECT id, name, status, status_category
        FROM cattle
        WHERE is_active = TRUE
        ORDER BY name ASC
    """)
    all_cattle = cursor.fetchall()

    # ✅ Filter only lactating cows for the Add Milk modal
    lactating_statuses = ('lactating', 'lactating_incalf')
    cows = [cow for cow in all_cattle if cow['status'] in lactating_statuses]

    # ✅ Weekly summary
    cursor.execute('''
        SELECT DATE_TRUNC('week', mp.date) AS week_start,
               SUM(COALESCE(mp.morning_milk, 0) + COALESCE(mp.mid_day_milk, 0) + COALESCE(mp.evening_milk, 0)) AS total_milk
        FROM milk_production mp
        JOIN cattle c ON mp.cattle_id = c.cattle_id
        WHERE c.is_active = TRUE
        GROUP BY DATE_TRUNC('week', mp.date)
        ORDER BY week_start DESC
        LIMIT 4
    ''')
    weekly_summary = cursor.fetchall()
    weekly_total = sum(row['total_milk'] for row in weekly_summary)

    # ✅ Monthly summary
    cursor.execute('''
        SELECT DATE_TRUNC('month', mp.date) AS month,
               SUM(COALESCE(mp.morning_milk, 0) + COALESCE(mp.mid_day_milk, 0) + COALESCE(mp.evening_milk, 0)) AS total_milk
        FROM milk_production mp
        JOIN cattle c ON mp.cattle_id = c.cattle_id
        WHERE c.is_active = TRUE
        GROUP BY DATE_TRUNC('month', mp.date)
        ORDER BY month DESC
        LIMIT 6
    ''')
    monthly_summary = cursor.fetchall()
    monthly_total = sum(row['total_milk'] for row in monthly_summary)

    return render_template('milk/milk_list.html',
        milk_records=records,
        page=page,
        total_pages=total_pages,
        search_query=search_query,
        start_date=start_date,
        end_date=end_date,
        cows=cows,
        weekly_summary=weekly_summary,
        monthly_summary=monthly_summary,
        weekly_total=weekly_total,
        monthly_total=monthly_total,
        daily_chart_data={},  # Placeholder
        cattle_chart_data={},  # Placeholder
        pagination=None  # Optional: use a helper to render if needed
    )

@milk_bp.route('/milk/add', methods=['POST'])
@login_required
def record_milk():
    db = get_db()
    cursor = get_cursor()

   
    today_str = request.form.get('date')
    today = datetime.strptime(today_str, '%Y-%m-%d').date() if today_str else dt_date.today()
    session_type = request.form.get('session')
    recorded_by = session['user_id']

    update_field = {
        'morning': 'morning_milk',
        'mid_day': 'mid_day_milk',
        'evening': 'evening_milk'
    }.get(session_type)

    if not update_field:
        flash("Invalid session type.", "danger")
        return redirect(url_for('milk.milk_list'))

    cattle_ids = request.form.getlist('cattle_ids')
    for cid in cattle_ids:
        try:
            quantity = float(request.form.get(f'milk_{cid}', 0))
        except (ValueError, TypeError):
            quantity = 0
        notes = request.form.get(f'notes_{cid}', '')

        # Check if already exists
        cursor.execute("SELECT id FROM milk_production WHERE cattle_id = %s AND date = %s", (cid, today))
        existing = cursor.fetchone()

        if existing:
            cursor.execute(f"""
                UPDATE milk_production
                SET {update_field} = %s, notes = %s, recorded_by = %s
                WHERE id = %s
            """, (quantity, notes, recorded_by, existing['id']))
        else:
            cursor.execute(f"""
                INSERT INTO milk_production (cattle_id, date, recorded_by, notes, {update_field})
                VALUES (%s, %s, %s, %s, %s)
            """, (cid, today, recorded_by, notes, quantity))

    db.commit()
    flash("Milk records saved successfully.", "success")
    return redirect(url_for('milk.milk_list'))


@milk_bp.route('/milk/edit/<int:record_id>', methods=['POST'])
@login_required
@admin_required
def edit_milk(record_id):
    db = get_db()
    cursor = get_cursor()

    try:
        morning = float(request.form.get('morning_milk') or 0)
        mid_day = float(request.form.get('mid_day_milk') or 0)
        evening = float(request.form.get('evening_milk') or 0)
    except ValueError:
        flash("Invalid input. Please enter valid milk quantities.", "danger")
        return redirect(url_for('milk.milk_list'))

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
