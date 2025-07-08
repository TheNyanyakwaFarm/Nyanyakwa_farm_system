from datetime import datetime
from dateutil.relativedelta import relativedelta

from datetime import datetime
from dateutil.relativedelta import relativedelta


def calculate_age_in_months(birth_date):
    return (datetime.today() - birth_date).days // 30


def update_cattle_statuses(db):
    all_cattle = db.execute("SELECT * FROM cattle").fetchall()

    for c in all_cattle:
        try:
            birth_date = datetime.strptime(c['birth_date'], "%Y-%m-%d")
        except Exception as e:
            print(f"[SKIP] Invalid birth_date for {c['tag_number']}: {e}")
            continue

        age_months = calculate_age_in_months(birth_date)
        status_category = c['status_category']
        current_status = c['status']
        sex = c['sex']

        new_status_category = status_category
        new_status = current_status

        if sex == 'F':
            last_breeding = db.execute("""
                SELECT * FROM breeding_records
                WHERE cattle_id = ? ORDER BY breeding_date DESC LIMIT 1
            """, (c['cattle_id'],)).fetchone()

            last_calving = db.execute("""
                SELECT * FROM calving
                WHERE dam_tag_number = ? ORDER BY birth_date DESC LIMIT 1
            """, (c['tag_number'],)).fetchone()

            if age_months <= 3:
                new_status_category = 'young_stock'
                new_status = 'newborn calf'
            elif 4 <= age_months <= 10:
                new_status_category = 'young_stock'
                new_status = 'weaned'
            elif age_months >= 11 and not last_breeding:
                new_status_category = 'young_stock'
                new_status = 'bullying heifer'

            if last_breeding:
                if not last_calving:
                    new_status_category = 'young_stock'
                    new_status = 'in_calf heifer'
                else:
                    new_status_category = 'mature_stock'
                    new_status = 'lactating in_calf'

                breeding_date = datetime.strptime(last_breeding['breeding_date'], "%Y-%m-%d")
                steaming_date = breeding_date + relativedelta(months=7)
                if datetime.today() >= steaming_date:
                    new_status = 'dry'

            if last_calving:
                new_status_category = 'mature_stock'
                new_status = 'lactating'

        elif sex == 'M':
            if age_months <= 3:
                new_status_category = 'bull'
                new_status = 'newborn calf'
            elif 4 <= age_months <= 10:
                new_status_category = 'bull'
                new_status = 'weaned calf'
            elif 10 < age_months < 24:
                new_status_category = 'bull'
                new_status = 'yearling'
            else:
                new_status_category = 'bull'
                new_status = 'mature bull'

        if new_status != current_status or new_status_category != status_category:
            tag = c['tag_number'] or 'NoTag'
            name = c['name'] or 'Unnamed'
            print(f"[STATUS UPDATE] {tag} - {name}: {status_category}/{current_status} → {new_status_category}/{new_status}")

            db.execute("""
                UPDATE cattle SET status_category = ?, status = ?
                WHERE cattle_id = ?
            """, (new_status_category, new_status, c['cattle_id']))
            db.commit()
