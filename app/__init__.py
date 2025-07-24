import os
from flask import Flask, render_template, session, redirect, url_for, flash, request
from dotenv import load_dotenv

# Load environment variables from .env (only locally)
load_dotenv()

# Configuration classes
from app.config import DevelopmentConfig, ProductionConfig

# Extensions
from app.extensions import mail, csrf

# Blueprints
from app.routes.dashboard import dashboard_bp
from app.routes.auth import auth_bp
from app.routes.user import user_bp
from app.routes.cattle import cattle_bp
from app.routes.breeding import breeding_bp
from app.routes.calving import calving_bp
from app.routes.milk import milk_bp


def create_app():
    app = Flask(
        __name__,
        template_folder='templates',
        static_folder='static'
    )

    # Select environment config
    if os.environ.get("FLASK_ENV") == "production":
        app.config.from_object(ProductionConfig)
    else:
        app.config.from_object(DevelopmentConfig)

    # Warn if using insecure SECRET_KEY in production
    if app.config["SECRET_KEY"] == "dev_secret_key" and not app.config.get("DEBUG"):
        print("⚠️ WARNING: You are using the default secret key in production! Set a secure SECRET_KEY.")

    # Initialize Flask extensions
    mail.init_app(app)
    csrf.init_app(app)

    # Register blueprints
    register_blueprints(app)

    # Custom error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template("500.html"), 500

    # ✅ Health check route (important for Render deployment)
    @app.route('/healthz')
    def health_check():
        return "OK", 200

    # Optional: Debug logging for requests
    if app.config.get("DEBUG"):
        @app.before_request
        def log_request_info():
            print(f"➡️ {request.method} {request.url}")

    return app


def register_blueprints(app):
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(user_bp, url_prefix='/users')
    app.register_blueprint(cattle_bp, url_prefix='/cattle')
    app.register_blueprint(breeding_bp, url_prefix='/breeding')
    app.register_blueprint(calving_bp, url_prefix='/calving')
    app.register_blueprint(milk_bp, url_prefix='/milk')


