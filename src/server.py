from bottle import Bottle, run, static_file, request, redirect, response, template
from beaker.middleware import SessionMiddleware # Added for session management
from pathlib import Path
from urllib.parse import unquote
import tester, json, os, storage, traceback, hashlib, secrets
from bottle import request as bottle_request
import dotenv
from math import erf, sqrt
import datetime # Added for date formatting
import csv # Added for CSV generation
from io import StringIO # Added for in-memory CSV generation
import threading
import time
from pathlib import Path

base_dir = Path(__file__).parent
webroot = base_dir / "webroot"

os.chdir(base_dir)
dotenv.load_dotenv()

session_opts = {
	'session.type': 'file',
	'session.cookie_expires': 86400,
	'session.data_dir': str(base_dir / 'session_data'),
	'session.auto': True
}

# Create a single Bottle app instance for all routes
main_app = Bottle()
app = SessionMiddleware(main_app, session_opts)

# Admin credentials
ADMIN_LOGIN = os.environ["ADMIN_LOGIN"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

# Session storage now handled by Beaker session middleware
def check_admin_session():
	session = bottle_request.environ.get('beaker.session')
	return session and session.get('is_admin') is True

def require_admin():
	session = bottle_request.environ.get('beaker.session')
	if not session or not session.get('is_admin'):
		redirect("/admin/login")

	session = bottle_request.environ.get('beaker.session')
	return session.get('is_admin') is True

@main_app.route("/result/<result_id>")
def show_result(result_id):
	return on_result_open(None, result_id)

@main_app.route("/result/tier-<tier:int>/<result_id>")
def show_result(tier, result_id):
	return on_result_open(tier, result_id)

@main_app.route("/cert/<result_id>")
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

@main_app.route("/check_email", method="POST")
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

@main_app.route("/admin/login")
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

@main_app.route("/admin/login", method="POST")
def admin_login():
	login = request.forms.get("login")
	password = request.forms.get("password")
	session = bottle_request.environ.get('beaker.session')
	if login == ADMIN_LOGIN and password == ADMIN_PASSWORD:
		session['is_admin'] = True
		session.save()
		redirect("/admin")
	else:
		redirect("/admin/login?error=1")

@main_app.route("/admin/logout")
def admin_logout():
	session = bottle_request.environ.get('beaker.session')
	session.delete()
	redirect("/admin/login")

@main_app.route("/admin/delete/<result_id>", method="POST")
def admin_delete_result(result_id):
	require_admin()
	try:
		storage.delete_result(result_id)
		return json.dumps({"success": True})
	except Exception:
		print(traceback.format_exc())
		return json.dumps({"success": False})

@main_app.route("/admin/campaigns/<slug>/toggle", method="POST")
def admin_toggle_campaign_enabled(slug):
	require_admin()
	response.content_type = "application/json"
	try:
		data = request.json
		enabled = int(data.get("enabled", 1))
		storage.set_campaign_enabled(slug, enabled)
		return json.dumps({"success": True})
	except Exception:
		print(traceback.format_exc())
		return json.dumps({"success": False, "message": "Internal error"})
# Global helper for CSV reuse (since local copy is kept in admin_panel)
def calculate_iq_percentile(iq_score):
    """Calculate percentile based on normal distribution of IQ scores"""
    mean = 100
    std_dev = 15
    
    # Calculate z-score
    z_score = (iq_score - mean) / std_dev
    
    # Calculate cumulative probability using error function
    percentile = 0.5 * (1 + erf(z_score / sqrt(2)))
    # Invert: 100% - percentile to show top percentage
    return 100 - (percentile * 100)

@main_app.route("/admin/download_csv")
def admin_download_csv():
	require_admin()

	campaign_filter_slug = request.query.get('campaign_slug')

	all_results = storage.get_all_results()
	campaigns = storage.get_campaigns()
	slug_to_name = {c['slug']: c['name'] for c in campaigns}
	slug_to_campaign = {c['slug']: c for c in campaigns}

	results = []
	for result in all_results:
		# Map campaign slug to name and add percentile
		campaign_slug = result.get("campaign_slug")
		campaign_name = slug_to_name.get(campaign_slug, "Direct/Untagged")
		
		# Filtering logic
		if campaign_filter_slug and campaign_filter_slug != "all":
			if campaign_filter_slug == "untagged":
				if campaign_name != "Direct/Untagged":
					continue
			elif campaign_slug != campaign_filter_slug:
				continue

		result["campaign_name"] = campaign_name

		if result["score"]:
			# Use the global helper
			percentile = calculate_iq_percentile(result["score"])
			result["percentile"] = round(percentile, 1)
		else:
			result["percentile"] = "N/A"
			
		# Format dates and durations
		result["date_time_formatted"] = datetime.datetime.fromtimestamp(
			result.get("submit_time", 0)
		).strftime("%Y-%m-%d %H:%M:%S") if result.get("submit_time") else "N/A"

		test_duration = result.get("test_duration")
		result["duration_formatted"] = f"{test_duration // 60}m {test_duration % 60}s" if test_duration else "N/A"

		result["correct_answers_formatted"] = f"{result.get('correct_answers', 'N/A')} from 60" if result.get('correct_answers') is not None else "N/A"

		results.append(result)

	# In-memory file for CSV generation
	output = StringIO()
	writer = csv.writer(output)

	# 1. Write Header
	header = [
		"ID", "Email", "Name", "Date & Time", "IQ Score", 
		"Test Duration (seconds)", "Correct Answers", "Campaign Name", 
		"Campaign Slug", "Percentile", "Result Tier"
	]
	writer.writerow(header)

	# 2. Write Data Rows
	for result in results:
		
		row = [
			# Ensure ID is always treated as a string
			str(result.get("id", "N/A")),
			result.get("email", "N/A"),
			result.get("user_name", "N/A"),
			result["date_time_formatted"],
			result.get("score", "N/A"),
			result.get("test_duration", "N/A"), # Raw seconds for easy analysis
			result["correct_answers_formatted"],
			result["campaign_name"],
			result.get("campaign_slug", "untagged"),
			result["percentile"],
			result.get("result_tier", "N/A")
		]
		writer.writerow(row)

	# Logic for filename generation
	if campaign_filter_slug and campaign_filter_slug != "all":
		if campaign_filter_slug == "untagged":
			campaign_name_for_file = "Direct_Untagged"
		elif campaign_filter_slug in slug_to_campaign:
			# Use the campaign name, replace spaces with underscores
			campaign_name = slug_to_campaign[campaign_filter_slug]['name']
			campaign_name_for_file = campaign_name.replace(" ", "_")
		else:
			campaign_name_for_file = "filtered_results"
	else:
		campaign_name_for_file = "all_results"

	response.content_type = 'text/csv'
	response.set_header(
		'Content-Disposition', 
		f'attachment; filename="test_results_{campaign_name_for_file}_{datetime.date.today()}.csv"'
	)

	return output.getvalue()


@main_app.route("/admin")
def admin_panel():
	require_admin()
	
	results = storage.get_all_results()
	
    # Fetch and map campaigns
	campaigns = storage.get_campaigns() # Assuming this function exists and returns [{"slug": "...", "name": "..."}]
	slug_to_name = {c['slug']: c['name'] for c in campaigns}
    
	# Calculate percentiles based on IQ distribution
	# IQ follows normal distribution: mean=100, std_dev=15
	
    # Local helper function is kept here, as requested not to change existing code
	def calculate_iq_percentile(iq_score):
		"""Calculate percentile based on normal distribution of IQ scores"""
		mean = 100
		std_dev = 15
		
		# Calculate z-score
		z_score = (iq_score - mean) / std_dev
		
		# Calculate cumulative probability using error function
		# This gives us the percentile
		percentile = 0.5 * (1 + erf(z_score / sqrt(2)))
		# Invert: 100% - percentile to show top percentage
		return 100 - (percentile * 100)
	
	for result in results:
		if result["score"]:
			# Calculate percentile based on IQ distribution statistics
			percentile = calculate_iq_percentile(result["score"])
			result["percentile"] = round(percentile, 1)
		else:
			result["percentile"] = "N/A"
            
        # Add campaign name to result dictionary
		campaign_slug = result.get("campaign_slug")
		if campaign_slug and campaign_slug in slug_to_name:
			result["campaign_name"] = slug_to_name[campaign_slug] # Display NAME
		else:
			result["campaign_name"] = "Direct/Untagged"
        
	# Sort results by Campaign Name for Grouping
	results.sort(key=lambda r: r["campaign_name"])

	# Generate HTML table
	rows_html = ""
	last_campaign_name = None # Variable to track grouping
    
	for result in results:
        # Add Grouping Header
		current_campaign_name = result["campaign_name"]
		if current_campaign_name != last_campaign_name:
            # colspan="9" because the table has 9 columns (Email to Actions)
			rows_html += f'''
            <tr class="campaign-group-header">
                <td colspan="9"><h2>Campaign: {current_campaign_name}</h2></td>
            </tr>
            '''
			last_campaign_name = current_campaign_name
        
		# import datetime # datetime is now imported globally
		date_time = datetime.datetime.fromtimestamp(result["submit_time"]).strftime("%Y-%m-%d %H:%M:%S") if result["submit_time"] else "N/A"
		test_duration_str = f"{result['test_duration'] // 60}m {result['test_duration'] % 60}s" if result["test_duration"] else "N/A"
		correct_answers_str = f"{result.get('correct_answers', 'N/A')} from 60" if result.get('correct_answers') is not None else "N/A"
		
        # Use the campaign_name we stored in the result dict
		campaign_display = result["campaign_name"] 
        
		rows_html += f'''
		<tr data-id="{result.get("id", "")}">
			<td>{result.get("email", "N/A")}</td>
			<td>{result.get("user_name", "N/A")}</td>
			<td>{date_time}</td>
			<td>{result.get("score", "N/A")}</td>
			<td>{test_duration_str}</td>
            <td>{correct_answers_str}</td>
            <td>{campaign_display}</td>  <td>{result.get("percentile", "N/A")}%</td>
			<td><button class="delete-btn" data-id="{result.get("id", "")}">Delete</button></td>
		</tr>
		'''
	
    # Campaign filter options for the UI
	campaign_options_html = '<option value="all">All Campaigns</option>'
	campaign_options_html += '<option value="untagged">Direct/Untagged</option>'
	
	for campaign in campaigns:
		campaign_options_html += f'<option value="{campaign["slug"]}">{campaign["name"]}</option>' 
        
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
            /* Campaign Grouping Style */
            .campaign-group-header td {{
                background: #e0e7ff !important; 
                font-weight: bold;
                padding: 15px 12px;
                border-top: 2px solid #667eea;
                border-bottom: none;
            }}
            .campaign-group-header h2 {{
                margin: 0;
                font-size: 1.2em;
                color: #333;
            }}
            /* CSV Download Section Styles */
            .csv-download-container {{
                background: white;
                padding: 15px 20px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                margin-bottom: 20px;
                display: flex;
                align-items: center;
                gap: 15px;
            }}
            .csv-download-container select, .csv-download-container button {{
                padding: 10px;
                border-radius: 5px;
                border: 1px solid #ddd;
            }}
            .csv-download-container select {{
                width: 300px;
            }}
            .csv-download-container button {{
                background: #4CAF50;
                color: white;
                cursor: pointer;
                border: none;
            }}
            .csv-download-container button:hover {{
                background: #45a049;
            }}
		</style>
	</head>
	<body>
		<div class="header">
			<h1>Test Results Dashboard</h1>
			<div>
				<a href="/admin/campaigns" class="logout-btn">Campaigns</a> <a href="/admin/logout" class="logout-btn">Logout</a>
			</div>
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
		
        <div class="csv-download-container">
            <h3>Download Results as CSV:</h3>
            <select id="campaign-select">
                {campaign_options_html}
            </select>
            <button id="download-csv-btn">Download CSV</button>
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
						<th>Campaign</th>
						<th>Percentile</th>
						<th>Actions</th>
					</tr>
				</thead>
				<tbody>
					{rows_html}
				</tbody>
			</table>
		</div>

		<div style="text-align:center; margin-bottom: 30px; padding-top: 32px;">
			<img src="/assets/img/iq_curve.png" alt="IQ Curve" style="max-width: 100%; height: auto; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.08);">
			<div style="color: #444; font-size: 15px; margin-top: 12px; font-style: italic; font-weight: 500; letter-spacing: 0.2px;">IQ distribution curve for reference</div>
		</div>

		<script>
            // CSV Download Script
            document.getElementById('download-csv-btn').addEventListener('click', function() {{
                const campaignSlug = document.getElementById('campaign-select').value;
                let url = '/admin/download_csv';
                
                if (campaignSlug && campaignSlug !== 'all') {{
                    url += `?campaign_slug=${{campaignSlug}}`;
                }}
                
                window.location.href = url;
            }});

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

@main_app.route("/")
def index_redirect():
	# Redirects all traffic from the root to a 404/not found page 
	# or an informational page, enforcing campaign-only access.
	response.status = 404
	return "Test link not found. Please use a valid campaign link."

# New route for campaign access
@main_app.route("/<campaign_slug>")
def campaign_access(campaign_slug):
	# Check if the slug is a campaign
	campaign = storage.get_campaign_by_slug(campaign_slug)
	if campaign:
		if not campaign.get("enabled", True):
			response.status = 403
			return "This campaign is currently disabled."
		# Redirect to the index page with the campaign slug
		return redirect(f"/index.html?campaign_slug={campaign_slug}")
	# Fallback for static files or non-campaign URLs
	# This should be handled by the generic static route, but adding a check here for clarity
	# Check if it's a known static file before returning 404
	if (webroot / campaign_slug).exists():
		return static_file(campaign_slug, root=webroot)
	response.status = 404
	return "Test link or page not found."

@main_app.route("/<filepath:path>")
def static(filepath):
	return static_file(filepath, root=webroot)

@main_app.route("/submit_result", method="POST")
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
	
@main_app.route("/admin/campaigns")
def admin_campaigns_panel():
	require_admin()
	
	campaigns = storage.get_campaigns() # Now returns {slug, name, enabled}
	campaigns_html = ""
	for campaign in campaigns:
		campaign_url = f"{request.urlparts.scheme}://{request.urlparts.netloc}/{campaign['slug']}"
		enabled = campaign.get("enabled", True)
		link_style = '' if enabled else 'style="pointer-events:none;opacity:0.5;text-decoration:line-through;"'
		btn_text = 'Disable' if enabled else 'Enable'
		btn_class = 'toggle-enable-btn' + ('' if enabled else ' disabled-campaign')
		campaigns_html += f'''
		<tr data-slug="{campaign['slug']}">
			<td>{campaign.get("name", "N/A")}</td>
			<td class="link-cell">
				<span id="link-{campaign['slug']}"><a href="{campaign_url}" target="_blank" {link_style}>{campaign_url}</a></span>
				<button class="copy-link-btn" data-link="{campaign_url}">Copy</button>
			</td>
			<td>
				<button class="{btn_class}" data-slug="{campaign['slug']}" data-enabled="{int(enabled)}">{btn_text}</button>
				<button class="delete-campaign-btn" data-slug="{campaign['slug']}">Delete</button>
			</td>
		</tr>
		'''
	
	return f'''
	<!DOCTYPE html>
	<html>
	<head>
		<title>Admin Panel - Campaigns</title>
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
				margin-bottom: 20px;
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
			.delete-campaign-btn {{
				padding: 6px 12px;
				background: #ff4444;
				color: white;
				border: none;
				border-radius: 4px;
				cursor: pointer;
				font-size: 12px;
			}}
			.delete-campaign-btn:hover {{
				background: #cc0000;
			}}
			.create-form input[type="text"] {{
				padding: 10px;
				margin-right: 10px;
				border: 1px solid #ddd;
				border-radius: 5px;
				width: 250px;
			}}
			.create-form button {{
				padding: 10px 20px;
				background: #4CAF50;
				color: white;
				border: none;
				border-radius: 5px;
				cursor: pointer;
			}}
			.create-form button:hover {{
				background: #45a049;
			}}
            /* Copy Button */
            .link-cell {{
                display: flex;
                align-items: center;
                gap: 10px;
            }}
            .copy-link-btn {{
				padding: 6px 12px;
				background: #667eea;
				color: white;
				border: none;
				border-radius: 4px;
				cursor: pointer;
				font-size: 12px;
                flex-shrink: 0;
            }}
            .copy-link-btn:hover {{
				background: #5568d3;
            }}
			.toggle-enable-btn {{
				padding: 6px 12px;
				background: #ffa500;
				color: white;
				border: none;
				border-radius: 4px;
				cursor: pointer;
				font-size: 12px;
				margin-right: 8px;
			}}
			.toggle-enable-btn.disabled-campaign {{
				background: #aaa;
			}}
			.link-cell a[style*="line-through"] {{
				text-decoration: line-through;
				color: #888;
			}}
		</style>
	</head>
	<body>
		<div class="header">
			<h1>Campaign Links</h1>
			<div>
				<a href="/admin" class="logout-btn">Results</a>
				<a href="/admin/logout" class="logout-btn">Logout</a>
			</div>
		</div>
		
		<div class="container">
			<h2>Create New Campaign</h2>
			<form id="create-campaign-form" class="create-form">
				<input type="text" name="campaign_name" placeholder="Campaign Name (e.g., Spring Hiring 2024)" required>
				<button type="submit">Create Link</button>
			</form>
		</div>

		<div class="container">
			<h2>Active Campaigns</h2>
			<table>
				<thead>
					<tr>
						<th>Name</th>
						<th>Link</th>
						<th>Actions</th>
					</tr>
				</thead>
				<tbody>
					{campaigns_html}
				</tbody>
			</table>
		</div>

		<script>
			// Handle Enable/Disable Campaign
			document.querySelectorAll('.toggle-enable-btn').forEach(btn => {{
				btn.addEventListener('click', async function() {{
					const slug = this.dataset.slug;
					const currentlyEnabled = this.dataset.enabled === '1';
					const newEnabled = currentlyEnabled ? 0 : 1;
					try {{
						const response = await fetch(`/admin/campaigns/${{slug}}/toggle`, {{
							method: 'POST',
							headers: {{ 'Content-Type': 'application/json' }},
							body: JSON.stringify({{ enabled: newEnabled }})
						}});
						const data = await response.json();
						if(data.success) {{
							location.reload();
						}} else {{
							alert('Failed to update campaign status');
						}}
					}} catch(e) {{
						alert('Error updating campaign: ' + e.message);
					}}
					}});
			}});
			
			// Handle Create Campaign
			document.getElementById('create-campaign-form').addEventListener('submit', async function(e) {{
				e.preventDefault();
				const campaignName = this.campaign_name.value;
				
				try {{
					const response = await fetch('/admin/campaigns', {{
						method: 'POST',
						headers: {{ 'Content-Type': 'application/json' }},
						body: JSON.stringify({{ name: campaignName }})
					}});
					const data = await response.json();
					
					if(data.success) {{
						alert('Campaign created successfully! Slug: ' + data.slug);
						location.reload();
					}} else {{
						alert('Failed to create campaign: ' + data.message);
					}}
				}} catch(e) {{
					alert('Error creating campaign: ' + e.message);
				}}
			}});

			// Handle Delete Campaign
			document.querySelectorAll('.delete-campaign-btn').forEach(btn => {{
				btn.addEventListener('click', async function() {{
					if(!confirm('Are you sure you want to delete this campaign? This will invalidate the link.')) {{
						return;
					}}
					
					const slug = this.dataset.slug;
					
					try {{
						const response = await fetch(`/admin/campaigns/${{slug}}`, {{
							method: 'DELETE'
						}});
						const data = await response.json();
						
						if(data.success) {{
							document.querySelector(`tr[data-slug="${{slug}}"]`).remove();
						}} else {{
							alert('Failed to delete campaign');
						}}
					}} catch(e) {{
						alert('Error deleting campaign: ' + e.message);
					}}
				}});
			}});

            // Handle Copy Link
			document.querySelectorAll('.copy-link-btn').forEach(btn => {{
				btn.addEventListener('click', function() {{
					const linkToCopy = this.dataset.link;
					
					// Use the modern navigator.clipboard API
					if (navigator.clipboard) {{
						navigator.clipboard.writeText(linkToCopy).then(() => {{
							// Provide visual feedback
							this.textContent = 'Copied!';
							setTimeout(() => {{
								this.textContent = 'Copy';
							}}, 1500);
						}}).catch(err => {{
							console.error('Failed to copy text: ', err);
							alert('Failed to copy link. Please copy it manually.');
						}});
					}} else {{
						// Fallback for older browsers
						const tempInput = document.createElement('input');
						tempInput.value = linkToCopy;
						document.body.appendChild(tempInput);
						tempInput.select();
						document.execCommand('copy');
						document.body.removeChild(tempInput);

						this.textContent = 'Copied!';
						setTimeout(() => {{
							this.textContent = 'Copy';
						}}, 1500);
					}}
				}});
			}});
		</script>
	</body>
	</html>
	'''

@main_app.route("/admin/campaigns", method="POST")
def admin_create_campaign():
	require_admin()
	response.content_type = "application/json"
	try:
		data = request.json
		name = data.get("name")
		slug = secrets.token_hex(4) # Generate a short unique slug
		created = storage.create_campaign(slug, name)
		if not created:
			return json.dumps({"success": False, "message": "Campaign name must be unique."})
		return json.dumps({"success": True, "slug": slug})
	except Exception:
		print(traceback.format_exc())
		return json.dumps({"success": False, "message": "Internal error"})

@main_app.route("/admin/campaigns/<slug>", method="DELETE")
def admin_delete_campaign(slug):
	require_admin()
	response.content_type = "application/json"
	try:
		storage.delete_campaign(slug) # Assume this deletes from DB
		return json.dumps({"success": True})
	except Exception:
		print(traceback.format_exc())
		return json.dumps({"success": False, "message": "Internal error"})

def run_local():
	run(app=app, host=os.environ["SERVER_HOST"], port=os.environ["SERVER_PORT"])

def cleanup_sessions_periodically(session_dir, max_age_seconds=86400):
	"""Delete session files older than max_age_seconds in session_dir once per day."""
	def cleanup():
		while True:
			now = time.time()
			if not session_dir.exists():
				time.sleep(86400)
				continue
			for f in (session_dir / 'container_file').iterdir():
				try:
					if f.is_file() and (now - f.stat().st_mtime) > max_age_seconds:
						f.unlink()
				except Exception:
					pass
			# Sleep for 24 hours
			time.sleep(86400)
	t = threading.Thread(target=cleanup, daemon=True)
	t.start()

# Start session cleanup thread at startup
cleanup_sessions_periodically(base_dir / 'session_data')