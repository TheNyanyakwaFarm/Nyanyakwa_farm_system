from flask import Flask

def create_app():
    app = Flask(__name__)

    # Register blueprints here
     app.register_blueprint(dashboard.dashboard_bp)
    return app
