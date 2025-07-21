from datetime import datetime
from dateutil.relativedelta import relativedelta
from database import get_cursor  # Make sure this works with PostgreSQL


def calculate_age_in_months(birth_date):
    return (datetime.today() - birth_date).days // 30


def update_cattle_statuses(db):
    cursor = get_cursor()
    cursor.execute("SELECT * FROM cattle")
    all_cattle = cursor.fetchall()

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
        cattle_id = c['cattle_id']
        tag_number = c['tag_number'] or 'NoTag'
        name = c['name'] or 'Unnamed'

        new_status_category = status_category
        new_status = current_status

        # 🐄 FEMALES
        if sex == 'F':
            # Get latest breeding record
            cursor.execute("""
                SELECT * FROM breeding_records
                WHERE cattle_id = %s
                ORDER BY breeding_date DESC LIMIT 1
            """, (cattle_id,))
            last_breeding = cursor.fetchone()

            # Get latest calving record
            cursor.execute("""
                SELECT * FROM calving
                WHERE dam_tag_number = %s
                ORDER BY birth_date DESC LIMIT 1
            """, (tag_number,))
            last_calving = cursor.fetchone()

            # Step 1: Age-based defaults
            if age_months <= 3:
                new_status_category = 'young_stock'
                new_status = 'newborn calf'
            elif 4 <= age_months <= 10:
                new_status_category = 'young_stock'
                new_status = 'weaned'
            elif age_months >= 11 and not last_breeding:
                new_status_category = 'young_stock'
                new_status = 'bullying heifer'

            # Step 2: Reproduction status
            if last_breeding:
                try:
                    breeding_date = datetime.strptime(last_breeding['breeding_date'], "%Y-%m-%d")
                except:
                    breeding_date = None
                if not last_calving:
                    new_status_category = 'young_stock'
                    new_status = 'in_calf heifer'
                else:
                    try:
                        calving_date = datetime.strptime(last_calving['birth_date'], "%Y-%m-%d")
                        if breeding_date and breeding_date > calving_date:
                            new_status_category = 'mature_stock'
                            new_status = 'lactating in_calf'
                            steaming_date = breeding_date + relativedelta(months=7)
                            if datetime.today().date() >= steaming_date.date():
                                new_status = 'dry'
                        else:
                            new_status_category = 'mature_stock'
                            new_status = 'lactating'
                    except:
                        pass
            elif last_calving:
                new_status_category = 'mature_stock'
                new_status = 'lactating'

        # 🐂 MALES
        elif sex == 'M':
            if age_months <= 3:
                new_status_category = 'bull'
                new_status = 'newborn calf'
            elif 4 <= age_months <= 10:
                new_status_category = 'bull'
                new_status = 'weaned calf'
            elif 11 <= age_months < 24:
                new_status_category = 'bull'
                new_status = 'yearling'
            else:
                new_status_category = 'bull'
                new_status = 'mature bull'

        # 🔄 Save changes
        if new_status != current_status or new_status_category != status_category:
            print(f"[STATUS UPDATE] {tag_number} - {name}: {status_category}/{current_status} → {new_status_category}/{new_status}")
            cursor.execute("""
                UPDATE cattle SET status_category = %s, status = %s
                WHERE cattle_id = %s
            """, (new_status_category, new_status, cattle_id))
            db.commit()
