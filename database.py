import psycopg2
import os
from flask import g

# Get the PostgreSQL URL from the Render environment
DATABASE_URL = os.environ.get("DATABASE_URL", "dbname=dairy_farm user=postgres password=localpass")

def get_db():
    """
    Opens a new PostgreSQL connection if one does not exist for the current app context.
    """
    if 'db' not in g:
        g.db = psycopg2.connect(DATABASE_URL)
    return g.db

def close_db(e=None):
    """
    Closes the PostgreSQL connection at the end of the request or app context.
    """
    db = g.pop('db', None)
    if db is not None:
        db.close()
