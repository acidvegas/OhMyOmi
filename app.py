#!/usr/bin/env python3
# DIY Omi wiring preview - acidvegas

try:
	from flask import Flask, render_template
except ImportError:
	raise ImportError('missing flask library (pip install flask)')


HOST = '100.125.210.117' # tailscale
PORT = 20004

app = Flask(__name__)


@app.route('/')
def index() -> str:
	'''Render the wiring preview page.'''

	return render_template('index.html')



if __name__ == '__main__':
	app.run(host=HOST, port=PORT)
