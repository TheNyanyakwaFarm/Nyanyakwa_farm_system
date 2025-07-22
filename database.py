import sqlite3
import psycopg2
import psycopg2.extras
import os
from flask import g, current_app

def get_db():
    if 'db' not in g:
        db_url = current_app.config.get('DATABASE_URL') or os.getenv('DATABASE_URL')
        if db_url.startswith('postgresql'):
            g.db = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            g.db = sqlite3.connect(db_url)
            g.db.row_factory = sqlite3.Row
    return g.db

def get_cursor():
    db = get_db()
    return db.cursor()

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()
