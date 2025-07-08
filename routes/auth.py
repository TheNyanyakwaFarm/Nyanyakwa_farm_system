from flask import Blueprint, render_template, request, redirect, flash, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Message
from database import get_db
from datetime import datetime, timedelta
import secrets
from functools import wraps

from extensions import mail  # ✅ Make sure this is imported

auth_bp = Blueprint('auth', __name__)


# 🔐 Decorator to protect routes
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return wrapper


# ✅ Route: Login
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    next_page = request.args.get('next')
    db = get_db()

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']

            # ✅ Automatically update cattle statuses
            from utils.status_updater import update_cattle_statuses
            update_cattle_statuses(db)

            # 🚨 Check profile completeness
            required_fields = [
                user['first_name'], user['last_name'], user['age'],
                user['national_id'], user['address'], user['qualification'],
                user['email'], user['phone']
            ]
            if any(field is None or str(field).strip() == '' for field in required_fields):
                flash("Please complete your profile before continuing.", "warning")
                return redirect(url_for('auth.complete_profile'))

            flash('Logged in successfully.', 'success')
            return redirect(next_page or url_for('dashboard.dashboard'))
        else:
            flash('Invalid credentials.', 'danger')

    return render_template("auth/login.html")


# ✅ Route: Logout
@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


# ✅ Route: Forgot Password (request reset)
@auth_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip().lower()
        db = get_db()

        user = db.execute(
            'SELECT * FROM users WHERE LOWER(email) = ? OR phone = ?',
            (identifier, identifier)
        ).fetchone()

        if user:
            token = secrets.token_urlsafe(32)
            expiry = datetime.now() + timedelta(hours=1)

            db.execute(
                'UPDATE users SET reset_token = ?, token_expiry = ? WHERE id = ?',
                (token, expiry, user['id'])
            )
            db.commit()

            reset_link = url_for('auth.reset_password', token=token, _external=True)

            # Send via email if available
            if user['email']:
                try:
                    msg = Message(
                        "Password Reset - Dairy Farm System",
                        recipients=[user['email']]
                    )
                    msg.body = f"""Hello {user['first_name']},

We received a request to reset your password.

Click below to reset your password (valid for 1 hour):
{reset_link}

If you didn't request this, you can ignore this message.

- Nyanyakwa Dairy Farm System
"""
                    mail.send(msg)
                    flash("A reset link has been sent to your email.", "success")
                except Exception as e:
                    print(f"Email send error: {e}")
                    flash("Error sending email. Please try again later.", "danger")
            else:
                print(f"Simulated Reset Link (no email): {reset_link}")
                flash("No email found. Reset link shown in console.", "info")
        else:
            flash("No account found with that email or phone.", "danger")

        return redirect(url_for('auth.forgot_password'))

    return render_template("auth/forgot_password.html")


# ✅ Route: Reset Password (form via token)

@auth_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    db = get_db()

    # ✅ Find user by token
    user = db.execute(
        'SELECT * FROM users WHERE reset_token = ?', (token,)
    ).fetchone()

    if not user:
        flash("Invalid or expired token.", "danger")
        return redirect(url_for('auth.login'))

    # ✅ Validate token expiry
    try:
        expiry_time = datetime.strptime(user['token_expiry'], "%Y-%m-%d %H:%M:%S.%f")
    except Exception:
        flash("Invalid token expiry format.", "danger")
        return redirect(url_for('auth.forgot_password'))

    if datetime.now() > expiry_time:
        flash("Reset link has expired. Please request a new one.", "danger")
        return redirect(url_for('auth.forgot_password'))

    # ✅ Handle form submission
    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        # ✅ Check if passwords match
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(request.url)

        # ✅ Enforce password strength
        if len(password) < 6 or not any(char.isdigit() for char in password):
            flash("Password must be at least 6 characters and include a number.", "danger")
            return redirect(request.url)

        # ✅ Hash and save
        hashed_password = generate_password_hash(password)
        db.execute(
            'UPDATE users SET password = ?, reset_token = NULL, token_expiry = NULL WHERE id = ?',
            (hashed_password, user['id'])
        )
        db.commit()

        flash("Your password has been reset successfully. You can now log in.", "success")
        return redirect(url_for('auth.login'))

    return render_template("auth/reset_password.html")


# ✅ Route: Complete Profile
@auth_bp.route('/complete_profile', methods=['GET', 'POST'])
@login_required
def complete_profile():
    user_id = session['user_id']
    db = get_db()

    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        age = request.form.get('age')
        national_id = request.form.get('national_id')
        address = request.form.get('address')
        qualification = request.form.get('academic_qualification')
        email = request.form.get('email')
        phone = request.form.get('phone')

        db.execute('''
            UPDATE users SET
                first_name = ?, last_name = ?, age = ?, national_id = ?,
                address = ?, qualification = ?, email = ?, phone = ?
            WHERE id = ?
        ''', (first_name, last_name, age, national_id, address, qualification, email, phone, user_id))
        db.commit()

        flash("Profile updated successfully.", "success")
        return redirect(url_for('dashboard.dashboard'))

    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    return render_template("user/complete_profile.html", user=user)
