from dotenv import load_dotenv
load_dotenv()  # ✅ Load environment variables from .env

from app import create_app
from scheduler import start_scheduler  # ✅ Starts automated background tasks

# ✅ Create Flask app instance
app = create_app()

# ✅ Start any background jobs (e.g., updating statuses)
start_scheduler()

# ✅ Development-only run block
if __name__ == '__main__':
    # 👇 Use environment config if needed (optional improvement)
    import os
    debug_mode = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'

    app.run(
        debug=debug_mode,
        host='0.0.0.0',  # Allows access from other devices (good for testing)
        port=int(os.environ.get('PORT', 5000))  # Render uses PORT from env
    )
