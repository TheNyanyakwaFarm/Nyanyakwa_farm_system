from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import get_cursor
from app.utils.decorators import login_required
from datetime import datetime, timedelta

breeding_bp = Blueprint("breeding", __name__, template_folder="../templates/breeding")

@login_required
def calculate_steaming_date(breeding_date):
    return breeding_date + timedelta(days=213)  # 7 months

def calculate_expected_calving_date(steaming_date):
    return steaming_date + timedelta(days=60)  # 2 months after steaming

@breeding_bp.route("/breeding")
@login_required
def breeding_list():
    cursor = get_cursor()
    cursor.execute("""
        SELECT b.*, c.tag_number, u.username
        FROM breeding_records b
        JOIN cattle c ON b.cattle_id = c.cattle_id
        JOIN users u ON b.recorded_by = u.id
        WHERE b.remark IS DISTINCT FROM 'deleted'
        ORDER BY b.breeding_date DESC
    """)
    records = cursor.fetchall()
    return render_template("breeding/breeding_list.html", records=records)

@breeding_bp.route("/breeding/add", methods=["GET", "POST"])
@login_required
def add_breeding():
    cursor = get_cursor()

    if request.method == "POST":
        cattle_id = request.form["cattle_id"]
        method = request.form["method"]
        semen_type = request.form.get("semen_type") or None
        semen_price = request.form.get("semen_price") or None
        semen_batch_number = request.form.get("semen_batch_number") or None
        sire_name = request.form.get("sire_name") or None
        breeding_date = request.form["breeding_date"]
        breeding_attempt_number = request.form["breeding_attempt_number"]
        notes = request.form.get("notes") or None
        pregnancy_check_date = request.form.get("pregnancy_check_date") or None
        pregnancy_test_result = request.form.get("pregnancy_test_result") or None
        breeding_outcome = request.form.get("breeding_outcome") or None
        remark = request.form.get("remark") or None
        recorded_by = session.get("user_id")

        try:
            breeding_date_obj = datetime.strptime(breeding_date, "%Y-%m-%d").date()
            steaming_date = calculate_steaming_date(breeding_date_obj)
            expected_calving_date = calculate_expected_calving_date(steaming_date)
        except ValueError:
            flash("Invalid breeding date format.", "danger")
            return redirect(url_for("breeding.add_breeding"))

        cursor.execute("""
            INSERT INTO breeding_records (
                cattle_id, recorded_by, method, semen_type, semen_price, semen_batch_number,
                sire_name, breeding_date, breeding_attempt_number, notes, steaming_date,
                pregnancy_check_date, pregnancy_test_result, created_at, breeding_outcome, remark,
                expected_calving_date
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s)
        """, (
            cattle_id, recorded_by, method, semen_type, semen_price, semen_batch_number,
            sire_name, breeding_date, breeding_attempt_number, notes, steaming_date,
            pregnancy_check_date, pregnancy_test_result, breeding_outcome, remark,
            expected_calving_date
        ))

        flash("✅ Breeding record added successfully.", "success")
        return redirect(url_for("breeding.breeding_list"))

    # Get only lactating or bullying heifer cattle
    cursor.execute("""
        SELECT id, tag_number FROM cattle
        WHERE is_active = TRUE AND (status = 'lactating' OR status = 'bullying_heifer')
    """)
    cattle = cursor.fetchall()
    return render_template("breeding/add_breeding.html", cattle=cattle)
