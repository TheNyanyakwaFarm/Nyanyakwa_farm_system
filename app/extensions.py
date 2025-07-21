# extensions.py
from flask_mail import Mail
from flask_wtf import CSRFProtect  # ✅ Add this

mail = Mail()
csrf = CSRFProtect()  # ✅ Add this
