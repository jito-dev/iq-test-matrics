from bottle import route, run, static_file, request, redirect, response
from pathlib import Path
from urllib.parse import unquote
import tester, json, os, storage, traceback
import dotenv

base_dir = Path(__file__).parent
webroot = base_dir / "webroot"

os.chdir(base_dir)
dotenv.load_dotenv()

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

@route("/")
def index():
	return static_file("index.html", root=webroot)

@route("/<filepath:path>")
def static(filepath):
	return static_file(filepath, root=webroot)

@route("/payment_options.json")
def payment_options():
	response.content_type = "application/json"
	return json.dumps([
		{"url": os.getenv("TIER1_LINK")},
		{"url": os.getenv("TIER2_LINK")},
		{"url": os.getenv("TIER3_LINK")},
	])


@route("/accept_payment")
def accept_payment():
	params = request.query.__dict__.get("dict") or {}
	payment_id = params.get("stripe_session_token")[0]
	
	tester_data_str = unquote(request.get_cookie("tester_data"))
	tester_data = json.loads(tester_data_str)
	result = None
	try:
		result = tester.accept_payment(tester_data, payment_id)
	except Exception:
		print(traceback.format_exc())
	if result:
		return redirect(f"/result/tier-{result['result_tier']}/{result['id']}")
	else:
		error_msg = "Unable to accept payment, try to reload page later."
		admin_contact = os.getenv("ADMIN_CONTACT")
		if admin_contact:
			error_msg += f" If error persists, contact <b>{admin_contact}</b>"
		return error_msg

def run_local():
	run(host=os.environ["SERVER_HOST"], port=os.environ["SERVER_PORT"])
