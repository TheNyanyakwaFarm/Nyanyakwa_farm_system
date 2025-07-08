from flask import Flask
from routes import dashboard  # adjust if needed

def create_app():
    app = Flask(__name__)

    # Register blueprints
    app.register_blueprint(dashboard.dashboard_bp)

    return app
