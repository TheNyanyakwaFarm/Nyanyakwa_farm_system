from flask import Blueprint, render_template, request, redirect, flash, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from database import get_db, get_cursor
from app.utils.decorators import login_required, admin_required
import os

user_bp = Blueprint('user', __name__)

# ✅ Profile completeness popup
@user_bp.before_app_request
def check_profile_completion():
    if 'user_id' in session and 'show_complete_profile_popup' not in session:
        cursor = get_cursor()
        cursor.execute("SELECT first_name, last_name, email, phone FROM users WHERE id = %s", (session['user_id'],))
        row = cursor.fetchone()
        user = row if row else {}
        if not all([user.get('first_name'), user.get('last_name'), user.get('email'), user.get('phone')]):
            session['show_complete_profile_popup'] = True

# 👤 View Profile
@user_bp.route('/profile')
@login_required
def profile():
    cursor = get_cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone() or {}
    return render_template('user/profile.html', user=user)

# 👤 Edit Profile
@user_bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    db = get_db()
    cursor = get_cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone() or {}

    if request.method == 'POST':
        form = request.form
        profile_pic = request.files.get('profile_pic')

        updates = {
            "first_name": form['first_name'],
            "last_name": form['last_name'],
            "email": form['email'],
            "phone": form['phone'],
            "address": form['address'],
            "qualification": form['qualification']
        }

        if profile_pic and profile_pic.filename:
            filename = secure_filename(profile_pic.filename)
            profile_pic.save(os.path.join('app', 'static', 'profile_pics', filename))
            updates['profile_pic'] = filename

        set_clause = ', '.join([f"{key} = %s" for key in updates])
        values = list(updates.values()) + [session['user_id']]
        cursor.execute(f"UPDATE users SET {set_clause} WHERE id = %s", values)
        db.commit()

        session.pop('show_complete_profile_popup', None)
        flash("Profile updated successfully.", "success")
        return redirect(url_for('user.profile'))

    return render_template('user/edit_profile.html', user=user)

# ⚙️ Change Password
@user_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    db = get_db()
    cursor = get_cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone() or {}

    if request.method == 'POST':
        current = request.form['current_password']
        new = request.form['new_password']
        confirm = request.form['confirm_password']

        if not check_password_hash(user['password'], current):
            flash("Current password is incorrect.", "danger")
        elif new != confirm:
            flash("New passwords do not match.", "danger")
        else:
            hashed = generate_password_hash(new)
            cursor.execute("UPDATE users SET password = %s WHERE id = %s", (hashed, session['user_id']))
            db.commit()
            flash("Password updated successfully.", "success")
            return redirect(url_for('user.settings'))

    return render_template('user/settings.html', user=user)

# 👥 Manage Users
@user_bp.route('/manage_users', methods=['GET'])
@login_required
@admin_required
def manage_users():
    cursor = get_cursor()
    search = request.args.get('search', '').strip()
    role = request.args.get('role', '')
    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page

    base_query = "FROM users WHERE 1=1"
    filters = []
    params = []

    if search:
        filters.append("(username ILIKE %s OR email ILIKE %s OR first_name ILIKE %s OR last_name ILIKE %s)")
        params.extend([f"%{search}%"] * 4)

    if role:
        filters.append("role = %s")
        params.append(role)

    if filters:
        base_query += " AND " + " AND ".join(filters)

    cursor.execute(f"SELECT * {base_query} ORDER BY id DESC LIMIT %s OFFSET %s", (*params, per_page, offset))
    users = cursor.fetchall()

    cursor.execute(f"SELECT COUNT(*) AS total {base_query}", params)
    row = cursor.fetchone()
    total_users = row['total'] if row else 0
    total_pages = (total_users + per_page - 1) // per_page

    return render_template('user/user_list.html', users=users, current_page=page, total_pages=total_pages)

# ➕ Add User
@user_bp.route('/add_user', methods=['POST'])
@login_required
@admin_required
def add_user():
    db = get_db()
    cursor = get_cursor()
    form = request.form

    username = form['username']
    email = form.get('email')

    # 🔒 Check if username/email already exists
    cursor.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
    if cursor.fetchone():
        flash("Username or email already exists.", "danger")
        return redirect(url_for('user.manage_users'))

    # ✅ Hash password
    hashed_password = generate_password_hash(form['password'])

    # ✅ Helper function for safe integer conversion
    def safe_int(value):
        return int(value) if value and value.isdigit() else None

    # ✅ Extract and sanitize form inputs
    first_name = form.get('first_name')
    last_name = form.get('last_name')
    age = safe_int(form.get('age'))
    national_id = safe_int(form.get('national_id'))
    address = form.get('address')
    qualification = form.get('qualification')
    phone = safe_int(form.get('phone'))
    role = form.get('role')

    # ✅ Insert user into database
    cursor.execute("""
        INSERT INTO users (
            username, password, role, first_name, last_name, age,
            national_id, address, qualification, email, phone
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        username, hashed_password, role, first_name, last_name, age,
        national_id, address, qualification, email, phone
    ))
    db.commit()

    flash("User added successfully.", "success")
    return redirect(url_for('user.manage_users'))


# ✏️ Edit User
@user_bp.route('/edit_user', methods=['POST'])
@login_required
@admin_required
def edit_user():
    db = get_db()
    cursor = get_cursor()
    form = request.form

    user_id = form['id']
    age = form.get('age')
    try:
        age = int(age) if age.strip() else None
    except ValueError:
        flash('Invalid age format.', 'danger')
        return redirect(url_for('user.manage_users'))

    cursor.execute("""
        UPDATE users SET username=%s, role=%s, first_name=%s, last_name=%s,
            age=%s, national_id=%s, address=%s, qualification=%s, email=%s, phone=%s
        WHERE id=%s
    """, (
        form['username'], form['role'], form['first_name'], form['last_name'],
        age, form['national_id'], form['address'], form['qualification'],
        form['email'], form['phone'], user_id
    ))
    db.commit()
    flash("User updated successfully.", "success")
    return redirect(url_for('user.manage_users'))

# 🗑️ Confirm Delete
@user_bp.route('/confirm_delete', methods=['POST'])
@login_required
@admin_required
def confirm_delete():
    user_id = request.form['id']
    password = request.form['password']

    cursor = get_cursor()
    cursor.execute("SELECT password FROM users WHERE id = %s", (session['user_id'],))
    row = cursor.fetchone()
    admin = row if row else {}

    if not check_password_hash(admin['password'], password):
        flash("Incorrect admin password. Deletion aborted.", "danger")
        return redirect(url_for('user.manage_users'))

    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    get_db().commit()
    flash("User deleted successfully.", "success")
    return redirect(url_for('user.manage_users'))
