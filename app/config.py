import os

class Config:
    # 🔐 General
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_secret_key')

    # 🔒 Session Security
    SESSION_COOKIE_SECURE = True           # Only send cookies over HTTPS
    SESSION_COOKIE_HTTPONLY = True         # Prevent access to cookies via JavaScript
    SESSION_COOKIE_SAMESITE = 'Lax'        # Mitigate CSRF risk

    # 📧 Email Configuration (for Flask-Mail)
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')  # e.g. your_email@gmail.com
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')  # App-specific password
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')  # e.g. same as MAIL_USERNAME

    # 🛢️ Database: Overridden by environment-specific subclasses
    DATABASE = None


class DevelopmentConfig(Config):
    DEBUG = True
    DATABASE = os.environ.get('DEV_DATABASE_URL')  # e.g. postgresql://user:pass@localhost:5432/your_db


class ProductionConfig(Config):
    DEBUG = False
    DATABASE = os.environ.get('DATABASE_URL')  # e.g. Render’s PostgreSQL URI
