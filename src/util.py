

def sanitize_html(text):
	text = text.replace("&", "&amp;")
	text = text.replace("<", "&lt;")
	text = text.replace(">", "&gt;")
	return text