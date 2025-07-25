from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from database import get_cursor
from app.utils.decorators import login_required

dashboard_bp = Blueprint('dashboard', __name__)

# 🏠 Home route (no login required)
@dashboard_bp.route('/')
def home():
    with get_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS total FROM cattle WHERE is_active = TRUE")
        result = cursor.fetchone()
        count = result['total'] if result else 0
    return render_template('dashboard/home.html', count=count)


# 📊 Dashboard route (requires login)
@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    stats = {}

    with get_cursor() as cursor:
        # Total active cattle
        cursor.execute("SELECT COUNT(*) AS total FROM cattle WHERE is_active = TRUE")
        row = cursor.fetchone()
        stats['total_cattle'] = row['total'] if row else 0

        # Total staff
        cursor.execute("SELECT COUNT(*) AS total FROM users WHERE role = 'staff'")
        row = cursor.fetchone()
        stats['total_staff'] = row['total'] if row else 0

        # Pregnant cows
        cursor.execute("SELECT COUNT(*) AS total FROM breeding_records WHERE pregnancy_test_result = 'positive'")
        row = cursor.fetchone()
        stats['pregnant_cows'] = row['total'] if row else 0

        # Recent calvings in the last 30 days
        cursor.execute("""
            SELECT COUNT(*) AS total FROM calving 
            WHERE is_active = TRUE AND birth_date >= CURRENT_DATE - INTERVAL '30 days'
        """)
        row = cursor.fetchone()
        stats['recent_calvings'] = row['total'] if row else 0

        # Total milk records
        cursor.execute("SELECT COUNT(*) AS total FROM milk_production")
        row = cursor.fetchone()
        stats['total_milk_records'] = row['total'] if row else 0

        # Total breeding records
        cursor.execute("SELECT COUNT(*) AS total FROM breeding_records")
        row = cursor.fetchone()
        stats['total_breeding'] = row['total'] if row else 0

        # Total calvings (all time)
        cursor.execute("SELECT COUNT(*) AS total FROM calving WHERE is_active = TRUE")
        row = cursor.fetchone()
        stats['total_calvings'] = row['total'] if row else 0

    return render_template('dashboard/dashboard.html', stats=stats)
