import sqlite3
from pathlib import Path

db_path = Path(__file__).parent / "tester.db"

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
		"correct_answers": row[9] if len(row) > 9 else None
	}

def save_result(result_row):
	with DBAccess() as db:
		db.cursor.execute(
			"INSERT INTO results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", result_row)

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
			self.cursor.execute(
				"CREATE TABLE results (id text, score integer, " \
				"age integer, submit_time integer, payment_id text, " \
				"user_name text, result_tier integer, email text, " \
				"test_duration integer, correct_answers integer)")
		else:
			# Migration: add new columns if they don't exist
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
	
	def close(self):
		self.conn.commit()
		self.conn.close()
	
	def __enter__(self):
		return self
	
	def __exit__(self, type, value, traceback):
		self.close()
