#!/usr/bin/env python3
# DIY Omi PCB preview - acidvegas

import csv
import json
import os

try:
	from flask import Flask, render_template, send_from_directory
except ImportError:
	raise ImportError('missing flask library (pip install flask)')


HOST    = '100.125.210.117' # tailscale
PORT    = 20005
PCB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # renders change on every rebuild, always revalidate


@app.route('/')
def index() -> str:
	'''Render the PCB preview page.'''

	with open(os.path.join(PCB_DIR, 'jlcpcb', 'omi-bom.csv')) as f:
		bom = list(csv.DictReader(f))
	with open(os.path.join(PCB_DIR, 'preview', 'summary.json')) as f:
		summary = json.load(f)
	return render_template('index.html', bom=bom, s=summary)


@app.route('/3d')
def viewer() -> str:
	'''Interactive 3D view of the assembled board.'''

	return render_template('viewer.html')


@app.route('/renders/<path:name>')
def renders(name: str):
	'''Serve generated renders.'''

	return send_from_directory(os.path.join(PCB_DIR, 'renders'), name)


@app.route('/files/<path:name>')
def files(name: str):
	'''Serve JLCPCB output files for download.'''

	return send_from_directory(os.path.join(PCB_DIR, 'jlcpcb'), name, as_attachment=True)



if __name__ == '__main__':
	app.run(host=HOST, port=PORT)
