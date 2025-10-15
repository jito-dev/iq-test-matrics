import sqlite3
from pathlib import Path

db_path = Path(__file__).parent / "tester.db"

# --- Campaign Management Functions (New) ---

def create_campaign(slug, name):
    """Creates a new campaign link/tag. Returns True if created, False if duplicate name."""
    with DBAccess() as db:
        try:
            db.cursor.execute(
                "INSERT INTO campaigns VALUES (?, ?, 1)", (slug, name)
            )
            return True
        except sqlite3.IntegrityError:
            return False

def get_campaigns():
    """Fetches all campaigns."""
    with DBAccess() as db:
        dbres = db.cursor.execute(
            "SELECT slug, name, enabled FROM campaigns ORDER BY name ASC")
        rows = dbres.fetchall()
        return [{"slug": row[0], "name": row[1], "enabled": bool(row[2])} for row in rows]

def get_campaign_by_slug(slug):
    """Fetches a single campaign by its slug."""
    with DBAccess() as db:
        dbres = db.cursor.execute(
            "SELECT slug, name, enabled FROM campaigns WHERE slug = ?", (slug,)
        )
        row = dbres.fetchone()
        if row:
            return {"slug": row[0], "name": row[1], "enabled": bool(row[2])}
        return None

def delete_campaign(slug):
    """Deletes a campaign by its slug."""
    with DBAccess() as db:
        db.cursor.execute("DELETE FROM campaigns WHERE slug = ?", (slug,))

# Set campaign enabled/disabled
def set_campaign_enabled(slug, enabled):
    """Set the enabled status of a campaign by slug."""
    with DBAccess() as db:
        db.cursor.execute("UPDATE campaigns SET enabled = ? WHERE slug = ?", (int(enabled), slug))


# --- Existing Result Functions (Modified) ---

def cert_id_exists(cert_id):
    with DBAccess() as db:
        dbres = db.cursor.execute(
            "SELECT 1 FROM results WHERE id = ?", (cert_id,))
        search = dbres.fetchone()
        return bool(search)

def email_exists(email):
    with DBAccess() as db:
        dbres = db.cursor.execute(
            "SELECT 1 FROM results WHERE email = ?", (email,))
        search = dbres.fetchone()
        return bool(search)


def get_result(result_id):
    with DBAccess() as db:
        dbres = db.cursor.execute(
            "SELECT * FROM results WHERE id = ?", (result_id,))
        row = dbres.fetchone()
        if row:
            return result_row_to_dict(row)

def result_row_to_dict(row):
    # Updated to handle 11 columns for the new 'campaign_slug'
    return {
        "id": row[0],
        "score": row[1],
        "age": row[2],
        "submit_time": row[3],
        "payment_id": row[4],
        "user_name": row[5],
        "result_tier": row[6],
        "email": row[7] if len(row) > 7 else None,
        "test_duration": row[8] if len(row) > 8 else None,
        "correct_answers": row[9] if len(row) > 9 else None,
        "campaign_slug": row[10] if len(row) > 10 else None # NEW COLUMN INDEX 10
    }

def save_result(result_row):
    # Updated SQL statement for 11 columns
    with DBAccess() as db:
        db.cursor.execute(
            "INSERT INTO results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", result_row) # 11 question marks

def get_all_results():
    with DBAccess() as db:
        dbres = db.cursor.execute(
            "SELECT * FROM results ORDER BY submit_time DESC")
        rows = dbres.fetchall()
        return [result_row_to_dict(row) for row in rows]

def delete_result(result_id):
    with DBAccess() as db:
        db.cursor.execute("DELETE FROM results WHERE id = ?", (result_id,))

class DBAccess():
    def __init__(self):
        init_needed = not db_path.exists()
        
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        if init_needed:
            # Create results table with new campaign_slug column
            self.cursor.execute(
                "CREATE TABLE results (id text, score integer, " \
                "age integer, submit_time integer, payment_id text, " \
                "user_name text, result_tier integer, email text, " \
                "test_duration integer, correct_answers integer, " \
                "campaign_slug text)") # New column
            
            # Create the campaigns table
            self.cursor.execute(
                "CREATE TABLE campaigns (slug text PRIMARY KEY, name text UNIQUE, enabled integer DEFAULT 1)")
        else:
            # Migration: add new columns if they don't exist in results
            try:
                self.cursor.execute("ALTER TABLE results ADD COLUMN email text")
            except:
                pass
            try:
                self.cursor.execute("ALTER TABLE results ADD COLUMN test_duration integer")
            except:
                pass
            try:
                self.cursor.execute("ALTER TABLE results ADD COLUMN correct_answers integer")
            except:
                pass
            
            # NEW MIGRATION: add campaign_slug column to results
            try:
                self.cursor.execute("ALTER TABLE results ADD COLUMN campaign_slug text")
            except:
                pass
            
            # NEW MIGRATION: create campaigns table if it doesn't exist, and add unique constraint to name
            try:
                self.cursor.execute("CREATE TABLE campaigns (slug text PRIMARY KEY, name text UNIQUE, enabled integer DEFAULT 1)")
            except:
                pass
            # Migration: add enabled column if missing
            try:
                self.cursor.execute("ALTER TABLE campaigns ADD COLUMN enabled integer DEFAULT 1")
            except:
                pass
            # Try to add unique constraint to name if missing (for legacy DBs)
            try:
                self.cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_campaign_name_unique ON campaigns(name)")
            except:
                pass
    
    def close(self):
        self.conn.commit()
        self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, type, value, traceback):
        self.close()