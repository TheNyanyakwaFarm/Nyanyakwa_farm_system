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

admin_required = role_required('admin')

# 🟢 Show complete profile popup flag (triggered after login)
@user_bp.before_app_request
def check_profile_completion():
    if 'user_id' in session and 'show_complete_profile_popup' not in session:
        cursor = get_cursor()
        cursor.execute("SELECT first_name, last_name, email, phone FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        if not all([user['first_name'], user['last_name'], user['email'], user['phone']]):
            session['show_complete_profile_popup'] = True

# 👤 View own profile
@user_bp.route('/profile')
@login_required
def profile():
    cursor = get_cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    return render_template('user/profile.html', user=user)

# ⚙️ Change password
@user_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    db = get_db()
    cursor = get_cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()

    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if not check_password_hash(user['password'], current_password):
            flash('Current password is incorrect.', 'danger')
        elif new_password != confirm_password:
            flash('New passwords do not match.', 'danger')
        else:
            hashed = generate_password_hash(new_password)
            cursor.execute("UPDATE users SET password = %s WHERE id = %s", (hashed, session['user_id']))
            db.commit()
            flash('Password updated successfully.', 'success')
            return redirect(url_for('user.settings'))

    return render_template('user/settings.html', user=user)

# 👥 Manage Users (uses user_list.html)
@user_bp.route('/manage_users', methods=['GET'])
@login_required
@admin_required
def manage_users():
    cursor = get_cursor()
    search = request.args.get('search', '').strip()
    role = request.args.get('role', '')
    page = int(request.args.get('page', 1))
    per_page = 10

    query = "SELECT * FROM users WHERE 1=1"
    params = []

    if search:
        query += " AND (username ILIKE %s OR email ILIKE %s OR first_name ILIKE %s OR last_name ILIKE %s)"
        term = f"%{search}%"
        params.extend([term, term, term, term])

    if role:
        query += " AND role = %s"
        params.append(role)

    query += " ORDER BY id DESC LIMIT %s OFFSET %s"
    params.extend([per_page, (page - 1) * per_page])
    cursor.execute(query, tuple(params))
    users = cursor.fetchall()

    # Count total users for pagination
    count_query = "SELECT COUNT(*) FROM users WHERE 1=1"
    count_params = params[:-2] if len(params) >= 2 else params
    cursor.execute(count_query + query[23:query.find("ORDER")], tuple(count_params))
    total_users = cursor.fetchone()[0]
    total_pages = (total_users + per_page - 1) // per_page

    return render_template('user/user_list.html', users=users, current_page=page, total_pages=total_pages)

# ➕ Add user
@user_bp.route('/add_user', methods=['POST'])
@login_required
@admin_required
def add_user():
    db = get_db()
    cursor = get_cursor()

    username = request.form['username']
    password = generate_password_hash(request.form['password'])
    role = request.form['role']
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    age = request.form.get('age')
    national_id = request.form.get('national_id')
    address = request.form.get('address')
    qualification = request.form.get('qualification')
    email = request.form.get('email')
    phone = request.form.get('phone')

    cursor.execute("""
        INSERT INTO users (username, password, role, first_name, last_name, age,
                           national_id, address, qualification, email, phone)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (username, password, role, first_name, last_name, age, national_id,
          address, qualification, email, phone))
    db.commit()
    flash('User added successfully.', 'success')
    return redirect(url_for('user.manage_users'))

# ✏️ Edit user
@user_bp.route('/edit_user', methods=['POST'])
@login_required
@admin_required
def edit_user():
    db = get_db()
    cursor = get_cursor()

    user_id = request.form['id']
    username = request.form['username']
    role = request.form['role']
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    age = request.form.get('age')
    national_id = request.form['national_id']
    address = request.form['address']
    qualification = request.form['qualification']
    email = request.form['email']
    phone = request.form['phone']

    try:
        age = int(age) if age.strip() else None
    except ValueError:
        flash('Invalid age. Please enter a number.', 'danger')
        return redirect(url_for('user.manage_users'))

    cursor.execute("""
        UPDATE users SET username = %s, role = %s, first_name = %s, last_name = %s,
                         age = %s, national_id = %s, address = %s, qualification = %s,
                         email = %s, phone = %s
        WHERE id = %s
    """, (username, role, first_name, last_name, age, national_id, address,
          qualification, email, phone, user_id))
    db.commit()
    flash('User updated successfully.', 'success')
    return redirect(url_for('user.manage_users'))

# 🗑️ Delete user with password confirmation
@user_bp.route('/confirm_delete', methods=['POST'])
@login_required
@admin_required
def confirm_delete():
    user_id = request.form['id']
    password = request.form['password']

    cursor = get_cursor()
    cursor.execute("SELECT password FROM users WHERE id = %s", (session['user_id'],))
    admin = cursor.fetchone()

    if not check_password_hash(admin['password'], password):
        flash("Incorrect admin password. Deletion aborted.", "danger")
        return redirect(url_for('user.manage_users'))

    db = get_db()
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    db.commit()
    flash("User deleted successfully.", "success")
    return redirect(url_for('user.manage_users'))

# 👤 Edit own profile
@user_bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    db = get_db()
    cursor = get_cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()

    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        phone = request.form['phone']
        address = request.form['address']
        qualification = request.form['qualification']

        cursor.execute("""
            UPDATE users
            SET first_name = %s, last_name = %s, email = %s, phone = %s,
                address = %s, qualification = %s
            WHERE id = %s
        """, (first_name, last_name, email, phone, address, qualification, session['user_id']))
        db.commit()

        session.pop('show_complete_profile_popup', None)
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('user.profile'))

    return render_template('user/edit_profile.html', user=user)
