# ----------------------
# Standard Library Imports
# ----------------------
import secrets
from datetime import datetime, timedelta
import sqlite3
from dateutil.relativedelta import relativedelta

# ----------------------
# Flask Core Imports
# ----------------------
from flask import Flask, Blueprint, session, redirect, url_for, flash, request, render_template
from flask_login import login_required
from functools import wraps

# ----------------------
# Security
# ----------------------
from werkzeug.security import generate_password_hash, check_password_hash

# ----------------------
# Application-Specific Imports
# ----------------------
from extensions import mail  # ✅ Imported from extensions now
from database import get_db, close_db
from config.status_config import status_by_category

# ✅ Import the blueprint modules
from routes.cattle import cattle_bp
from routes.calving import calving_bp
from routes.breeding import breeding_bp
from routes.milk import milk_bp
from routes.user import user_bp
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp


# ✅ Flask App Factory Function
def create_app():
    app = Flask(__name__)

    # ✅ Secret Key
    app.secret_key = '1523371568ad78fd95100d7c43a7e63a93ee0ce277892c5463ed8ff9f9a06d29'

    # ✅ Mail Configuration
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = 'kibettkipz@gmail.com'
    app.config['MAIL_PASSWORD'] = 'vvmbtkxteniddmfu'
    app.config['MAIL_DEFAULT_SENDER'] = 'kibettkipz@gmail.com'

    # ✅ Initialize extensions
    mail.init_app(app)

    # ✅ Register Blueprints
    app.register_blueprint(breeding_bp, url_prefix='/breeding')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(user_bp, url_prefix='/users')
    app.register_blueprint(cattle_bp, url_prefix='/cattle')
    app.register_blueprint(milk_bp, url_prefix='/milk')
    app.register_blueprint(calving_bp, url_prefix='/calving')
    app.register_blueprint(dashboard_bp)

    # ✅ Error Handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("500.html"), 500

    return app


# ✅ Custom Admin Decorator (can be moved to utils if reused widely)
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function
