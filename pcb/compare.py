#!/usr/bin/env python3
# DIY Omi PCB - board render next to a to-scale US quarter - acidvegas

import math
import os

try:
	from PIL import Image, ImageDraw, ImageFont
except ImportError:
	raise ImportError('missing pillow library (pip install pillow)')


HERE    = os.path.dirname(os.path.abspath(__file__))
BOARD_W = 26.0   # board width (mm)
QUARTER = 24.26  # US quarter diameter (mm)
OMI     = 25.5   # Omi pendant diameter (mm), from its docs
CASE    = 28.9   # this build's case outer diameter (mm), from the 3D viewer's wall and gap
FONT    = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'


def main():
	'''Write renders/compare.png: board, Omi and a US quarter to scale.'''

	board = Image.open(os.path.join(HERE, 'renders', 'top.png')).convert('RGBA')
	board = board.crop(board.getchannel('A').getbbox())
	px_mm = board.width / BOARD_W
	qd = round(QUARTER * px_mm)
	od = round(OMI * px_mm)
	gap = round(4 * px_mm)
	pad = round(3 * px_mm)
	label_h = round(5 * px_mm)
	w = pad + board.width + gap + od + gap + qd + pad
	h = pad + max(board.height, od, qd) + label_h * 2 + pad
	tall = max(board.height, od, qd)
	out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
	out.alpha_composite(board, (pad, pad + (tall - board.height) // 2))

	# Omi: plain disc at its published diameter
	o = Image.new('RGBA', (od, od), (0, 0, 0, 0))
	ImageDraw.Draw(o).ellipse((0, 0, od - 1, od - 1), fill=(120, 124, 132, 255), outline=(170, 174, 182, 255), width=max(2, od // 120))
	out.alpha_composite(o, (pad + board.width + gap, pad + (tall - od) // 2))

	# quarter: plain silver disc with a reeded rim, drawn to scale
	q = Image.new('RGBA', (qd, qd), (0, 0, 0, 0))
	d = ImageDraw.Draw(q)
	d.ellipse((0, 0, qd - 1, qd - 1), fill=(168, 170, 174, 255))
	rim = round(qd * 0.06)
	d.ellipse((rim, rim, qd - 1 - rim, qd - 1 - rim), fill=(196, 198, 202, 255), outline=(150, 152, 156, 255), width=max(1, rim // 4))
	for i in range(240):
		a = 2 * math.pi * i / 240
		r1, r2 = qd / 2 - 1, qd / 2 - rim * 0.55
		c = qd / 2
		d.line((c + r1 * math.cos(a), c + r1 * math.sin(a), c + r2 * math.cos(a), c + r2 * math.sin(a)), fill=(140, 142, 146, 255), width=1)
	f = ImageFont.truetype(FONT, round(qd * 0.16))
	d.text((qd / 2, qd / 2), '25¢', font=f, fill=(120, 122, 126, 255), anchor='mm')
	out.alpha_composite(q, (pad + board.width + gap + od + gap, pad + (tall - qd) // 2))

	d = ImageDraw.Draw(out)
	f = ImageFont.truetype(FONT, round(2.2 * px_mm))
	y = pad + tall + label_h // 2
	d.text((pad + board.width / 2, y), f'Board Ø{BOARD_W:g} mm', font=f, fill=(130, 134, 140, 255), anchor='mm')
	d.text((pad + board.width / 2, y + label_h * 0.8), f'(case ~Ø{CASE:g} mm)', font=f, fill=(160, 164, 170, 255), anchor='mm')
	d.text((pad + board.width + gap + od / 2, y), f'Omi Ø{OMI} mm', font=f, fill=(130, 134, 140, 255), anchor='mm')
	d.text((pad + board.width + gap + od + gap + qd / 2, y), f'US quarter Ø{QUARTER} mm', font=f, fill=(130, 134, 140, 255), anchor='mm')
	out.save(os.path.join(HERE, 'renders', 'compare.png'))
	print('wrote renders/compare.png', out.size)



if __name__ == '__main__':
	main()
