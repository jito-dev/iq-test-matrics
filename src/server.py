from bottle import route, run, static_file, request, redirect, response, template
from pathlib import Path
from urllib.parse import unquote
import tester, json, os, storage, traceback, hashlib, secrets
import dotenv

base_dir = Path(__file__).parent
webroot = base_dir / "webroot"

os.chdir(base_dir)
dotenv.load_dotenv()

# Admin credentials
ADMIN_LOGIN = "root"
ADMIN_PASSWORD = "1111"

# Session storage (in production, use a proper session manager)
admin_sessions = set()

def generate_session_token():
	return secrets.token_hex(32)

def check_admin_session():
	session_token = request.get_cookie("admin_session")
	return session_token in admin_sessions

def require_admin():
	if not check_admin_session():
		redirect("/admin/login")

@route("/result/<result_id>")
def show_result(result_id):
	return on_result_open(None, result_id)

@route("/result/tier-<tier:int>/<result_id>")
def show_result(tier, result_id):
	return on_result_open(tier, result_id)

@route("/cert/<result_id>")
def generate_cert(result_id):
	result = storage.get_result(result_id)
	if result["result_tier"] != 3:
		response.status = 403
		return "Not allowed"
	
	response.content_type = "image/jpeg"
	return tester.gen_cert(result["id"], result["user_name"],
		result["score"], result["submit_time"])

def on_result_open(tier, result_id):
	result = storage.get_result(result_id)
	if result["result_tier"] != tier:
		return redirect(f"/result/tier-{result['result_tier']}/{result['id']}")
	
	domain = f"{request.urlparts.scheme}://{request.urlparts.netloc}"
	status, body = tester.get_result_page(result_id, domain)
	response.status = status
	return body

@route("/check_email", method="POST")
def check_email():
	response.content_type = "application/json"
	try:
		data = request.json
		email = data.get("email", "").lower().strip()
		exists = storage.email_exists(email)
		return json.dumps({"exists": exists})
	except Exception:
		print(traceback.format_exc())
		return json.dumps({"exists": False})

@route("/admin/login")
def admin_login_page():
	if check_admin_session():
		redirect("/admin")
	
	return '''
	<!DOCTYPE html>
	<html>
	<head>
		<title>Admin Login</title>
		<style>
			body {
				font-family: 'Roboto', 'Lato', sans-serif;
				display: flex;
				justify-content: center;
				align-items: center;
				height: 100vh;
				margin: 0;
				background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
			}
			.login-container {
				background: white;
				padding: 40px;
				border-radius: 10px;
				box-shadow: 0 10px 40px rgba(0,0,0,0.2);
				width: 300px;
			}
			h2 {
				text-align: center;
				color: #333;
				margin-bottom: 30px;
			}
			input {
				width: 100%;
				padding: 12px;
				margin: 10px 0;
				border: 1px solid #ddd;
				border-radius: 5px;
				box-sizing: border-box;
				font-size: 14px;
			}
			button {
				width: 100%;
				padding: 12px;
				background: #667eea;
				color: white;
				border: none;
				border-radius: 5px;
				cursor: pointer;
				font-size: 16px;
				margin-top: 20px;
			}
			button:hover {
				background: #5568d3;
			}
			.error {
				color: red;
				text-align: center;
				margin-top: 10px;
			}
		</style>
	</head>
	<body>
		<div class="login-container">
			<h2>Admin Login</h2>
			<form method="POST" action="/admin/login">
				<input type="text" name="login" placeholder="Login" required>
				<input type="password" name="password" placeholder="Password" required>
				<button type="submit">Login</button>
			</form>
			<div class="error" id="error"></div>
		</div>
		<script>
			const urlParams = new URLSearchParams(window.location.search);
			if(urlParams.get('error') === '1') {
				document.getElementById('error').textContent = 'Invalid credentials';
			}
		</script>
	</body>
	</html>
	'''

@route("/admin/login", method="POST")
def admin_login():
	login = request.forms.get("login")
	password = request.forms.get("password")
	
	if login == ADMIN_LOGIN and password == ADMIN_PASSWORD:
		session_token = generate_session_token()
		admin_sessions.add(session_token)
		response.set_cookie("admin_session", session_token, max_age=86400, httponly=True)
		redirect("/admin")
	else:
		redirect("/admin/login?error=1")

@route("/admin/logout")
def admin_logout():
	session_token = request.get_cookie("admin_session")
	if session_token in admin_sessions:
		admin_sessions.remove(session_token)
	response.delete_cookie("admin_session")
	redirect("/admin/login")

@route("/admin/delete/<result_id>", method="POST")
def admin_delete_result(result_id):
	require_admin()
	try:
		storage.delete_result(result_id)
		return json.dumps({"success": True})
	except Exception:
		print(traceback.format_exc())
		return json.dumps({"success": False})

@route("/admin")
def admin_panel():
	require_admin()
	
	results = storage.get_all_results()
	
	# Calculate percentiles based on IQ distribution
	# IQ follows normal distribution: mean=100, std_dev=15
	import math
	
	def calculate_iq_percentile(iq_score):
		"""Calculate percentile based on normal distribution of IQ scores"""
		mean = 100
		std_dev = 15
		
		# Calculate z-score
		z_score = (iq_score - mean) / std_dev
		
		# Calculate cumulative probability using error function
		# This gives us the percentile
		percentile = 0.5 * (1 + math.erf(z_score / math.sqrt(2)))
		# Invert: 100% - percentile to show top percentage
		return 100 - (percentile * 100)
	
	for result in results:
		if result["score"]:
			# Calculate percentile based on IQ distribution statistics
			percentile = calculate_iq_percentile(result["score"])
			result["percentile"] = round(percentile, 1)
		else:
			result["percentile"] = "N/A"
	
	# Generate HTML table
	rows_html = ""
	for result in results:
		import datetime
		date_time = datetime.datetime.fromtimestamp(result["submit_time"]).strftime("%Y-%m-%d %H:%M:%S") if result["submit_time"] else "N/A"
		test_duration_str = f"{result['test_duration'] // 60}m {result['test_duration'] % 60}s" if result["test_duration"] else "N/A"
		correct_answers_str = f"{result.get('correct_answers', 'N/A')} из 60" if result.get('correct_answers') is not None else "N/A"
		
		rows_html += f'''
		<tr data-id="{result.get("id", "")}">
			<td>{result.get("email", "N/A")}</td>
			<td>{result.get("user_name", "N/A")}</td>
			<td>{date_time}</td>
			<td>{result.get("score", "N/A")}</td>
			<td>{test_duration_str}</td>
			<td>{correct_answers_str}</td>
			<td>{result.get("percentile", "N/A")}%</td>
			<td><button class="delete-btn" data-id="{result.get("id", "")}">Удалить</button></td>
		</tr>
		'''
	
	return f'''
	<!DOCTYPE html>
	<html>
	<head>
		<title>Admin Panel - Test Results</title>
		<style>
			body {{
				font-family: 'Roboto', 'Lato', sans-serif;
				margin: 0;
				padding: 20px;
				background: #f5f5f5;
			}}
			.header {{
				background: white;
				padding: 20px;
				margin-bottom: 20px;
				border-radius: 10px;
				box-shadow: 0 2px 10px rgba(0,0,0,0.1);
				display: flex;
				justify-content: space-between;
				align-items: center;
			}}
			h1 {{
				margin: 0;
				color: #333;
			}}
			.logout-btn {{
				padding: 10px 20px;
				background: #667eea;
				color: white;
				border: none;
				border-radius: 5px;
				cursor: pointer;
				text-decoration: none;
			}}
			.logout-btn:hover {{
				background: #5568d3;
			}}
			.container {{
				background: white;
				padding: 20px;
				border-radius: 10px;
				box-shadow: 0 2px 10px rgba(0,0,0,0.1);
				overflow-x: auto;
			}}
			table {{
				width: 100%;
				border-collapse: collapse;
			}}
			th {{
				background: #667eea;
				color: white;
				padding: 12px;
				text-align: left;
				font-weight: 500;
			}}
			td {{
				padding: 12px;
				border-bottom: 1px solid #eee;
			}}
			tr:hover {{
				background: #f9f9f9;
			}}
			.delete-btn {{
				padding: 6px 12px;
				background: #ff4444;
				color: white;
				border: none;
				border-radius: 4px;
				cursor: pointer;
				font-size: 12px;
			}}
			.delete-btn:hover {{
				background: #cc0000;
			}}
			.stats {{
				display: grid;
				grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
				gap: 20px;
				margin-bottom: 20px;
			}}
			.stat-card {{
				background: white;
				padding: 20px;
				border-radius: 10px;
				box-shadow: 0 2px 10px rgba(0,0,0,0.1);
			}}
			.stat-card h3 {{
				margin: 0 0 10px 0;
				color: #666;
				font-size: 14px;
			}}
			.stat-card .value {{
				font-size: 32px;
				font-weight: bold;
				color: #667eea;
			}}
		</style>
	</head>
	<body>
		<div class="header">
			<h1>Test Results Dashboard</h1>
			<a href="/admin/logout" class="logout-btn">Logout</a>
		</div>
		
		<div class="stats">
			<div class="stat-card">
				<h3>Total Tests</h3>
				<div class="value">{len(results)}</div>
			</div>
			<div class="stat-card">
				<h3>Average IQ Score</h3>
				<div class="value">{round(sum(r["score"] for r in results if r["score"]) / len([r for r in results if r["score"]]) if [r for r in results if r["score"]] else 0, 1)}</div>
			</div>
			<div class="stat-card">
				<h3>Avg. Test Duration</h3>
				<div class="value">{round(sum(r["test_duration"] for r in results if r["test_duration"]) / len([r for r in results if r["test_duration"]]) / 60 if [r for r in results if r["test_duration"]] else 0, 1)}m</div>
			</div>
		</div>
		
		<div class="container">
			<table>
				<thead>
					<tr>
						<th>Email</th>
						<th>Name</th>
						<th>Date & Time</th>
						<th>IQ Score</th>
						<th>Test Duration</th>
						<th>Correct Answers</th>
						<th>Percentile</th>
						<th>Actions</th>
					</tr>
				</thead>
				<tbody>
					{rows_html}
				</tbody>
			</table>
		</div>
		<script>
			document.querySelectorAll('.delete-btn').forEach(btn => {{
				btn.addEventListener('click', async function() {{
					if(!confirm('Are you sure you want to delete this record?')) {{
						return;
					}}
					
					const resultId = this.dataset.id;
					const row = document.querySelector(`tr[data-id="${{resultId}}"]`);
					
					try {{
						const response = await fetch(`/admin/delete/${{resultId}}`, {{
							method: 'POST'
						}});
						const data = await response.json();
						
						if(data.success) {{
							row.remove();
							// Refresh the page to update statistics
							setTimeout(() => location.reload(), 500);
						}} else {{
							alert('Failed to delete record');
						}}
					}} catch(e) {{
						alert('Error deleting record: ' + e.message);
					}}
				}});
			}});
		</script>
	</body>
	</html>
	'''

@route("/")
def index():
	return static_file("index.html", root=webroot)

@route("/<filepath:path>")
def static(filepath):
	return static_file(filepath, root=webroot)

@route("/submit_result", method="POST")
def submit_result():
	tester_data_str = unquote(request.get_cookie("tester_data"))
	tester_data = json.loads(tester_data_str)
	result = None
	try:
		result = tester.create_result(tester_data)
	except Exception:
		print(traceback.format_exc())
	if result:
		# Show thank you page instead of results
		return '''
		<!DOCTYPE html>
		<html>
		<head>
			<title>Thank You</title>
			<style>
				body {
					font-family: 'Roboto', 'Lato', sans-serif;
					display: flex;
					justify-content: center;
					align-items: center;
					height: 100vh;
					margin: 0;
					background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
				}
				.container {
					text-align: center;
					background: white;
					padding: 60px;
					border-radius: 20px;
					box-shadow: 0 10px 40px rgba(0,0,0,0.2);
					max-width: 500px;
				}
				h1 {
					color: #333;
					margin-bottom: 20px;
					font-size: 2.5em;
				}
				p {
					color: #666;
					font-size: 1.2em;
					line-height: 1.6;
				}
				.checkmark {
					width: 80px;
					height: 80px;
					border-radius: 50%;
					display: block;
					margin: 0 auto 30px;
					background: #4CAF50;
					position: relative;
				}
				.checkmark::after {
					content: '';
					position: absolute;
					width: 20px;
					height: 40px;
					border: solid white;
					border-width: 0 5px 5px 0;
					top: 15px;
					left: 30px;
					transform: rotate(45deg);
				}
			</style>
		</head>
		<body>
			<div class="container">
				<div class="checkmark"></div>
				<h1>Thank You!</h1>
				<p>Your test has been completed and your results have been saved successfully.</p>
				<p>We appreciate your participation.</p>
			</div>
		</body>
		</html>
		'''
	else:
		error_msg = "Unable to create result, try to reload page later."
		admin_contact = os.getenv("ADMIN_CONTACT")
		if admin_contact:
			error_msg += f" If error persists, contact <b>{admin_contact}</b>"
		return error_msg

def run_local():
	run(host=os.environ["SERVER_HOST"], port=os.environ["SERVER_PORT"])
