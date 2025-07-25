from flask import Blueprint, render_template, request, redirect, flash, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Message
from database import get_db, get_cursor
from datetime import datetime, timedelta
import secrets
from app.extensions import mail
from app.utils.status_updater import update_cattle_statuses
from app.utils.decorators import login_required

auth_bp = Blueprint('auth', __name__)


# ✅ Login
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    next_page = request.args.get('next')
    db = get_db()
    cursor = get_cursor()

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cursor.fetchone()

        if user and check_password_hash(user['password'], password):
            session.update({
                'user_id': user['id'],
                'username': user['username'],
                'role': user['role']
            })

            update_cattle_statuses(db)

            required_fields = [
                user.get('first_name'), user.get('last_name'), user.get('age'),
                user.get('national_id'), user.get('address'),
                user.get('qualification'), user.get('email'), user.get('phone')
            ]
            if any(field is None or str(field).strip() == '' for field in required_fields):
                flash("Please complete your profile before continuing.", "warning")
                return redirect(url_for('auth.complete_profile'))

            flash('Logged in successfully.', 'success')
            return redirect(next_page or url_for('dashboard.dashboard'))
        else:
            flash('Invalid credentials.', 'danger')

    return render_template("auth/login.html")


# ✅ Logout
@auth_bp.route('/logout')
@login_required
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


# ✅ Forgot Password
@auth_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip().lower()
        db = get_db()
        cursor = get_cursor()

        cursor.execute(
            'SELECT * FROM users WHERE LOWER(email) = %s OR phone = %s',
            (identifier, identifier)
        )
        user = cursor.fetchone()

        if user:
            token = secrets.token_urlsafe(32)
            expiry = datetime.now() + timedelta(hours=1)

            cursor.execute(
                'UPDATE users SET reset_token = %s, token_expiry = %s WHERE id = %s',
                (token, expiry, user['id'])
            )
            db.commit()

            reset_link = url_for('auth.reset_password', token=token, _external=True)

            if user.get('email'):
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


# ✅ Reset Password
@auth_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    db = get_db()
    cursor = get_cursor()

    cursor.execute('SELECT * FROM users WHERE reset_token = %s', (token,))
    user = cursor.fetchone()

    if not user:
        flash("Invalid or expired token.", "danger")
        return redirect(url_for('auth.login'))

    expiry_time = user.get('token_expiry')
    try:
        if isinstance(expiry_time, str):
            expiry_time = datetime.strptime(expiry_time, "%Y-%m-%d %H:%M:%S.%f")
    except Exception:
        flash("Invalid token expiry format.", "danger")
        return redirect(url_for('auth.forgot_password'))

    if datetime.now() > expiry_time:
        flash("Reset link has expired. Please request a new one.", "danger")
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(request.url)

        if len(password) < 6 or not any(char.isdigit() for char in password):
            flash("Password must be at least 6 characters and include a number.", "danger")
            return redirect(request.url)

        hashed_password = generate_password_hash(password)
        cursor.execute(
            'UPDATE users SET password = %s, reset_token = NULL, token_expiry = NULL WHERE id = %s',
            (hashed_password, user['id'])
        )
        db.commit()

        flash("Your password has been reset successfully. You can now log in.", "success")
        return redirect(url_for('auth.login'))

    return render_template("auth/reset_password.html")


# ✅ Complete Profile
@auth_bp.route('/complete_profile', methods=['GET', 'POST'])
@login_required
def complete_profile():
    user_id = session['user_id']
    db = get_db()
    cursor = get_cursor()

    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        age = request.form.get('age')
        national_id = request.form.get('national_id')
        address = request.form.get('address')
        qualification = request.form.get('academic_qualification')
        email = request.form.get('email')
        phone = request.form.get('phone')

        cursor.execute('''
            UPDATE users SET
                first_name = %s, last_name = %s, age = %s, national_id = %s,
                address = %s, qualification = %s, email = %s, phone = %s
            WHERE id = %s
        ''', (first_name, last_name, age, national_id, address,
              qualification, email, phone, user_id))
        db.commit()

        flash("Profile updated successfully.", "success")
        return redirect(url_for('dashboard.dashboard'))

    cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    user = cursor.fetchone()

    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('auth.logout'))

    return render_template("user/complete_profile.html", user=user)
