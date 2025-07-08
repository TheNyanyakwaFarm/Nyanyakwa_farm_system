from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from database import get_db
from functools import wraps

dashboard_bp = Blueprint('dashboard', __name__)

# 🔐 Login required decorator (if not imported from app.py)
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
    db = get_db()
    count = db.execute("SELECT COUNT(*) FROM cattle").fetchone()[0]
    return render_template('dashboard/home.html', count=count)  # 👈 adjust template path as needed

# 📊 Dashboard route (requires login)
@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard/dashboard.html')  # 👈 adjust path if moved to subfolder
