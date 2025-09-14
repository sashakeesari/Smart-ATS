# scripts/patch_schema.py
import os
import sqlite3

DB_URL = os.getenv("DATABASE_URL", "sqlite:///ats.db")
if DB_URL.startswith("sqlite:///"):
    DB_PATH = DB_URL.replace("sqlite:///", "")
else:
    raise SystemExit("This patch script only supports sqlite:/// URLs.")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

def has_column(table: str, col: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == col for row in cur.fetchall())

def add_col(table: str, col_def: str):
    col_name = col_def.split()[0]
    if not has_column(table, col_name):
        print(f"Adding {table}.{col_name} ...")
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
    else:
        print(f"{table}.{col_name} already exists")

# Patch candidates.created_at
add_col("candidates", 'created_at DATETIME DEFAULT CURRENT_TIMESTAMP')

# Patch applications columns used by the app
add_col("applications", 'created_at DATETIME DEFAULT CURRENT_TIMESTAMP')
add_col("applications", 'match_pct FLOAT DEFAULT 0.0')
add_col("applications", 'missing_keywords TEXT DEFAULT "[]"')
add_col("applications", 'profile_summary TEXT DEFAULT ""')

# If you just added Interview model later, ensure table exists:
# (If you’re not using Alembic, easiest is to call init_db once after this.)

conn.commit()
conn.close()
print("Schema patch complete.")
    