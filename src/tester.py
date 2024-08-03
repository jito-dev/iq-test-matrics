import stripe, time, os, random, storage, io, datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from util import sanitize_html

base_dir = Path(__file__).parent
CORRECT_ANSWERS = [4, 5, 1, 2, 6, 3, 6, 2, 1, 3, 4, 5, 2, 6, 1, 2, 1, 3, 5,
	6, 4, 3, 4, 5, 8, 2, 3, 8, 7, 4, 5, 1, 7, 6, 1, 2, 3, 4, 3, 7, 8, 6, 5,
	4, 1, 2, 5, 6, 7, 6, 8, 2, 1, 5, 1, 6, 3, 2, 4, 5]
SCORE_TO_IQ_MAP = [None] * 15 + [62, 65, 65, 66, 67, 69, 70, 71, 72, 73, 75,
	76, 77, 79, 80, 82, 83, 84, 86, 87, 88, 90, 91, 92, 94, 95, 96, 98, 99,
	100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 120, 122, 124, 126, 128,
	130, 140]

def get_iq_score(answers, age):
	answered_correctly = 0
	for i, answ in enumerate(answers):
		if answ + 1 == CORRECT_ANSWERS[i]:
			answered_correctly += 1
	
	base_score = SCORE_TO_IQ_MAP[answered_correctly] or 60
	
	age_quotient = 100
	if age > 30:
		age_quotient = 97
	if age > 35:
		age_quotient = 93
	if age > 40:
		age_quotient = 88
	if age > 45:
		age_quotient = 82
	if age > 50:
		age_quotient = 76
	if age > 55:
		age_quotient = 70
	score = int(base_score / 100 * age_quotient)
	
	return score

def accept_payment(tester_data, payment_id):
	previous_result = storage.get_payment_result(payment_id)
	if(previous_result):
		print(f"Payment {payment_id} is already registered, skipping")
		return previous_result
	
	stripe.api_key = os.environ["STRIPE_API_KEY"]
	checkout_session = stripe.checkout.Session.retrieve(payment_id)
	
	if checkout_session["status"] != "complete":
		print("Session status is not 'complete', aborting payment")
		return False
	if checkout_session["payment_status"] != "paid":
		print("Session payment status is not 'paid', aborting payment")
		return False
	
	result_id = get_new_cert_id()
	age = tester_data["age"]
	score = get_iq_score(tester_data["answers"], age)
	submit_time = int(time.time())
	user_name = tester_data["user_name"]
	result_tier = get_payment_tier(checkout_session["payment_link"])
	
	result_row = (result_id, score, age, submit_time,
		payment_id, user_name, result_tier)
	storage.save_result(result_row)
	
	return storage.get_payment_result(payment_id)
	
def get_payment_tier(payment_link_id):
	if payment_link_id == os.getenv("TIER1_LINK_ID"):
		return 1
	elif payment_link_id == os.getenv("TIER2_LINK_ID"):
		return 2
	elif payment_link_id == os.getenv("TIER3_LINK_ID"):
		return 3
	else:
		return None


def get_new_cert_id():
	while True:
		digits = 12
		cert_id = str(random.randint(10 ** (digits - 1), 10 ** digits - 1))
		if not storage.cert_id_exists(cert_id):
			return cert_id



def get_result_page(result_id, domain):
	result_tpl_path = base_dir / "result_template.html"
	
	result = storage.get_result(result_id)
	if not result:
		return (404, "Result not found")
	
	user_name = sanitize_html(result["user_name"])
	title = f"{user_name}'s IQ Test Result"
	og_meta_html = f"""
		<meta property="og:title" content="{title}" />
		<meta property="og:type" content="website" />
		<meta property="og:url" content="{domain}/result/{result['result_tier']}/{result['id']}" />
		<meta property="og:description" content="{user_name} scored {result['score']} in Raven's IQ Test" />
		<meta property="og:site_name" content="Raven's IQ Test" />
	"""
	
	if result["result_tier"] == 1:
		result_duration_hours = int(os.getenv("TEMP_LINK_LIFETIME_HOURS"))
		result_duration = result_duration_hours * 60 * 60
		now = int(time.time())
		expired = result["submit_time"] + result_duration < now
		if expired:
			main_html = f"""
				<div class="result expired">
					<div class="desc">Result expired</div>
					<button onclick="document.location='/';" class='main-page'>Main page</button>
				</div>
			"""
			
			page_html = result_tpl_path.read_text().replace(
				"%title%", "Result expired").replace(
				"%sharethis%", "").replace(
				"%og_meta%", "").replace(
				"%main%", main_html)
			return (200, page_html)
		
	if result["result_tier"] in (1, 2):
		main_html = f"""
			<div class="result plain">
				<div class="name">{user_name}</div>
				<div class="desc">Your Raven's test IQ score:</div>
				<div class="score">{result['score']}</div>
			</div>
		"""
	else:
		img_url = f"../../cert/{result['id']}"
		main_html = f"""
			<div class="result cert">
				<a class="cert-wrapper" href="{img_url}" download="Certificate.jpg">
					<img src="{img_url}" alt="{user_name}'s IQ certificate">
				</a>
			</div>
		"""
		cert_url = f"{domain}/cert/{result['id']}"
		og_meta_html += f"\n<meta property=\"og:image\" " \
			f"content=\"{cert_url}\" />"
	
	
	page_html = result_tpl_path.read_text(encoding="utf-8").replace(
		"%title%", title).replace(
		"%sharethis%", os.getenv("SHARETHIS_ADDIN")).replace(
		"%og_meta%", og_meta_html).replace(
		"%main%", main_html)
	
	return (200, page_html)

def gen_cert(cert_id, user_name, user_score, submit_time):
	ASSETS_PATH = base_dir / "cert_assets"
	FONTS_PATH = ASSETS_PATH / "fonts"
	CERT_TPL_PATH = ASSETS_PATH / "cert_tpl.jpg"
	
	name_font = ImageFont.truetype(
		str(FONTS_PATH / "Lato-Light.ttf"), 160)
	serial_font = ImageFont.truetype(
		str(FONTS_PATH / "Lato-Regular.ttf"), 55)
	score_font = ImageFont.truetype(
		str(FONTS_PATH / "Lato-Black.ttf"), 200)
	date_font = ImageFont.truetype(
		str(FONTS_PATH / "Lato-Light.ttf"), 75)
	
	img = Image.open(str(CERT_TPL_PATH))
	cert_width  = img.width
	cert_height = img.height
	
	draw = ImageDraw.Draw(img)
	
	_, _, w, h = draw.textbbox((0, 0), user_name, font=name_font)
	draw.text(
		((cert_width-w)/2, 740),
		user_name, font=name_font, fill="black")
	
	cert_id_formatted = " ".join((cert_id[:4], cert_id[4:8], cert_id[8:]))
	draw.text((495, 1580), cert_id_formatted, font=serial_font, fill="black")
	
	_, _, w, h = draw.textbbox((0, 0), str(user_score), font=score_font)
	draw.text(
		((cert_width-w)/2, 1150),
		str(user_score), font=score_font, fill="black")
	
	date_formatted = datetime.datetime.fromtimestamp(
		submit_time).strftime("%B %d, %Y")
	_, _, w, h = draw.textbbox((0, 0), date_formatted, font=date_font)
	draw.text(
		((cert_width-w)/2, 1410),
		date_formatted, font=date_font, fill="black")
	
	img_bytesio = io.BytesIO()
	img.save(img_bytesio, "jpeg")
	return img_bytesio.getvalue()