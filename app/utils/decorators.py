from functools import wraps
from flask import session, redirect, url_for, flash


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def profile_completed_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('profile_completed'):
            flash('Please complete your profile to continue.', 'info')
            return redirect(url_for('auth.complete_profile'))
        return f(*args, **kwargs)
    return decorated_function
