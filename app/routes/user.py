from flask import Blueprint, render_template, request, redirect, flash, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db, get_cursor
from functools import wraps

user_bp = Blueprint('user', __name__)

# 🔐 Login-required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# 🔐 Role-required decorator
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash("Please log in to access this page.", "warning")
                return redirect(url_for('auth.login', next=request.url))
            if session.get('role') not in roles:
                flash("You do not have permission to perform this action.", "danger")
                return redirect(url_for('dashboard.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ✅ Admin shortcut
admin_required = role_required('admin')


# 👤 User Profile
@user_bp.route('/profile')
@login_required
def profile():
    cursor = get_cursor()
    cursor.execute('SELECT * FROM users WHERE id = %s', (session['user_id'],))
    user = cursor.fetchone()
    return render_template('user/profile.html', user=user)


# ⚙️ User Settings Page (Password Change)
@user_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    db = get_db()
    cursor = get_cursor()
    cursor.execute('SELECT * FROM users WHERE id = %s', (session['user_id'],))
    user = cursor.fetchone()

    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if not check_password_hash(user['password'], current_password):
            flash('Current password is incorrect.', 'danger')
            return render_template('user/settings.html', user=user)

        if new_password != confirm_password:
            flash('New passwords do not match.', 'danger')
            return render_template('user/settings.html', user=user)

        hashed = generate_password_hash(new_password)
        cursor.execute('UPDATE users SET password = %s WHERE id = %s', (hashed, session['user_id']))
        db.commit()
        flash('Password updated successfully.', 'success')
        return redirect(url_for('user.settings'))

    return render_template('user/settings.html', user=user)


# 👥 Manage Users (Admin Only)
@user_bp.route('/manage_users')
@login_required
@admin_required
def manage_users():
    cursor = get_cursor()
    cursor.execute('SELECT * FROM users')
    users = cursor.fetchall()
    return render_template('manage_users.html', users=users)


# ✏️ Edit User
@user_bp.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    db = get_db()
    cursor = get_cursor()
    cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    user = cursor.fetchone()

    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('user.manage_users'))

    if request.method == 'POST':
        username = request.form['username']
        role = request.form['role']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        age = request.form['age']
        national_id = request.form['national_id']
        address = request.form['address']
        qualification = request.form['qualification']

        try:
            age = int(age) if age.strip() else None
        except ValueError:
            flash('Invalid age. Please enter a number.', 'danger')
            return render_template("user/edit_user.html", user=user)

        cursor.execute("""
            UPDATE users 
            SET username = %s, role = %s, first_name = %s, last_name = %s, 
                age = %s, national_id = %s, address = %s, qualification = %s
            WHERE id = %s
        """, (username, role, first_name, last_name, age, national_id, address, qualification, user_id))
        db.commit()
        flash('User updated successfully.', 'success')
        return redirect(url_for('user.manage_users'))

    return render_template("user/edit_user.html", user=user)


# ❌ Delete User
@user_bp.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    db = get_db()
    cursor = get_cursor()
    cursor.execute('DELETE FROM users WHERE id = %s', (user_id,))
    db.commit()
    flash('User deleted successfully.', 'success')
    return redirect(url_for('user.manage_users'))


# ➕ Add User
@user_bp.route('/add_user', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
    if request.method == 'POST':
        username = request.form['username']
        raw_password = request.form['password']
        password = generate_password_hash(raw_password)
        role = request.form['role']
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        age = request.form.get('age')
        national_id = request.form.get('national_id')
        address = request.form.get('address')
        qualification = request.form.get('qualification')
        email = request.form.get('email')
        phone = request.form.get('phone')

        db = get_db()
        cursor = get_cursor()
        cursor.execute('''
            INSERT INTO users (
                username, password, role,
                first_name, last_name, age, national_id, address, qualification,
                email, phone
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            username, password, role,
            first_name, last_name, age, national_id, address, qualification,
            email, phone
        ))
        db.commit()

        flash('User added successfully.', 'success')
        return redirect(url_for('user.manage_users'))

    return render_template("user/add_user.html")


# 👤 Edit Own Profile
@user_bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    db = get_db()
    cursor = get_cursor()
    cursor.execute('SELECT * FROM users WHERE id = %s', (session['user_id'],))
    user = cursor.fetchone()

    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        phone = request.form['phone']
        address = request.form['address']
        qualification = request.form['qualification']

        cursor.execute('''
            UPDATE users
            SET first_name = %s, last_name = %s, email = %s, phone = %s, address = %s, qualification = %s
            WHERE id = %s
        ''', (first_name, last_name, email, phone, address, qualification, session['user_id']))
        db.commit()

        flash('Profile updated successfully.', 'success')
        return redirect(url_for('user.profile'))

    return render_template('user/edit_profile.html', user=user)
