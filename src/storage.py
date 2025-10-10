import sqlite3
from pathlib import Path

db_path = Path(__file__).parent / "tester.db"

def cert_id_exists(cert_id):
	with DBAccess() as db:
		dbres = db.cursor.execute(
			"SELECT 1 FROM results WHERE id = ?", (cert_id,))
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
		"result_tier": row[6]
	}

def save_result(result_row):
	with DBAccess() as db:
		db.cursor.execute(
			"INSERT INTO results VALUES (?, ?, ?, ?, ?, ?, ?)", result_row)

class DBAccess():
	def __init__(self):
		init_needed = not db_path.exists()
		
		self.conn = sqlite3.connect(db_path)
		self.cursor = self.conn.cursor()
		
		if init_needed:
			self.cursor.execute(
				"CREATE TABLE results (id text, score integer, " \
				"age integer, submit_time integer, payment_id text, " \
				"user_name text, result_tier integer)")
	
	def close(self):
		self.conn.commit()
		self.conn.close()
	
	def __enter__(self):
		return self
	
	def __exit__(self, type, value, traceback):
		self.close()
