
from flask import Flask

app = Flask(__name__)

@app.route("/")
def index():
	return "<b>Tähän tulee ruokareseptit!</b>"
