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
        cursor.execute("SELECT COUNT(*) FROM cattle WHERE is_active = TRUE")
        stats['total_cattle'] = cursor.fetchone()[0]

        # Total staff
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'staff'")
        stats['total_staff'] = cursor.fetchone()[0]

        # Pregnant cows
        cursor.execute("SELECT COUNT(*) FROM breeding WHERE pregnancy_test_result = 'positive'")
        stats['pregnant_cows'] = cursor.fetchone()[0]

        # Recent calvings in the last 30 days
        cursor.execute("""
            SELECT COUNT(*) FROM calving 
            WHERE is_active = TRUE AND calving_date >= CURRENT_DATE - INTERVAL '30 days'
        """)
        stats['recent_calvings'] = cursor.fetchone()[0]

        # Total milk records
        cursor.execute("SELECT COUNT(*) FROM milk")
        stats['total_milk_records'] = cursor.fetchone()[0]

        # Total breeding records
        cursor.execute("SELECT COUNT(*) FROM breeding")
        stats['total_breeding'] = cursor.fetchone()[0]

        # Total calvings (all time)
        cursor.execute("SELECT COUNT(*) FROM calving WHERE is_active = TRUE")
        stats['total_calvings'] = cursor.fetchone()[0]

    return render_template('dashboard/dashboard.html', stats=stats)
