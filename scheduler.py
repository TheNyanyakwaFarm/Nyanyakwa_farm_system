# scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from database import get_db
from app.utils.status_updater import update_cattle_statuses

def start_scheduler():
    scheduler = BackgroundScheduler()

    @scheduler.scheduled_job('interval', days=1)
    def daily_status_check():
        print(f"[SCHEDULER] ✅ Running cattle status update at {datetime.now()}")
        db = get_db()
        update_cattle_statuses(db)

    scheduler.start()
