from datetime import datetime

def determine_initial_status(sex, dob):
    """Determine the status and status category based on sex and age in months."""
    today = datetime.today().date()
    age_in_months = (today.year - dob.year) * 12 + (today.month - dob.month)

    if sex.lower() == 'male':
        if age_in_months <= 3:
            return 'bull', 'newborn calf'
        elif 4 <= age_in_months <= 10:
            return 'bull', 'weaned calf'
        elif 11 <= age_in_months < 24:
            return 'bull', 'yearling'
        else:
            return 'bull', 'mature bull'

    elif sex.lower() == 'female':
        if age_in_months <= 3:
            return 'young_stock', 'newborn calf'
        elif 4 <= age_in_months <= 10:
            return 'young_stock', 'weaned'
        else:
            # age >= 11 months: prompt user in frontend
            return None, None

    return None, None
