from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from database import get_cursor
from functools import wraps

dashboard_bp = Blueprint('dashboard', __name__)

# 🔐 Login required decorator
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return wrapper

# 🏠 Root route
@dashboard_bp.route('/')
def home():
    cursor = get_cursor()
    cursor.execute("SELECT COUNT(*) AS total FROM cattle")
    result = cursor.fetchone()
    count = result['total'] if result else 0  # ✅ Safe access for both PostgreSQL and SQLite
    return render_template('dashboard/home.html', count=count)

# 📊 Dashboard route (requires login)
@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard/dashboard.html')
