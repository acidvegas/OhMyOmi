#!/usr/bin/env python3
# DIY Omi PCB - JLCPCB fabrication/assembly outputs and preview renders - acidvegas

import csv
import json
import os
import shutil
import subprocess
import zipfile

from parts import PARTS


HERE   = os.path.dirname(os.path.abspath(__file__))
PCB    = os.path.join(HERE, 'omi.kicad_pcb')
OUT    = os.path.join(HERE, 'jlcpcb')
RENDER = os.path.join(HERE, 'renders')
LAYERS = 'F.Cu,In1.Cu,In2.Cu,In3.Cu,In4.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts'


def cli(*args: str):
	'''Run kicad-cli and fail loudly.'''

	subprocess.run(['kicad-cli', *args], check=True, stdout=subprocess.DEVNULL)


def fab():
	'''Gerbers + drill zipped, BOM and CPL in JLCPCB column format.'''

	gdir = os.path.join(OUT, 'gerbers')
	shutil.rmtree(OUT, ignore_errors=True)
	os.makedirs(gdir)
	cli('pcb', 'export', 'gerbers', '--output', gdir + '/', '--layers', LAYERS, '--subtract-soldermask', PCB)
	cli('pcb', 'export', 'drill', '--output', gdir + '/', '--format', 'excellon', '--excellon-separate-th', '--generate-map', '--map-format', 'gerberx2', PCB)
	with zipfile.ZipFile(os.path.join(OUT, 'omi-gerbers.zip'), 'w', zipfile.ZIP_DEFLATED) as z:
		for f in sorted(os.listdir(gdir)):
			z.write(os.path.join(gdir, f), f)

	# BOM grouped by LCSC part
	groups = {}
	for p in PARTS:
		if not p.get('lcsc'):
			continue
		key = p['lcsc']
		groups.setdefault(key, {'value': p['value'], 'fp': p['fp'].split(':')[1], 'refs': []})['refs'].append(p['ref'])
	with open(os.path.join(OUT, 'omi-bom.csv'), 'w', newline='') as f:
		w = csv.writer(f)
		w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
		for lcsc, g in groups.items():
			w.writerow([g['value'], ','.join(g['refs']), g['fp'], lcsc])

	# CPL from KiCad positions, both sides (the mics and their caps are on the back), hand-solder pads excluded
	assembled = {p['ref'] for p in PARTS if p.get('lcsc')}
	pos = os.path.join(OUT, 'pos.csv')
	cli('pcb', 'export', 'pos', '--output', pos, '--format', 'csv', '--units', 'mm', '--side', 'both', '--use-drill-file-origin', PCB)
	with open(pos) as f, open(os.path.join(OUT, 'omi-cpl.csv'), 'w', newline='') as g:
		w = csv.writer(g)
		w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
		for row in csv.DictReader(f):
			if row['Ref'] in assembled:
				w.writerow([row['Ref'], row['PosX'] + 'mm', row['PosY'] + 'mm', 'Bottom' if row['Side'] == 'bottom' else 'Top', row['Rot']])
	os.remove(pos)


# simple bodies for parts with no STEP model (KiCad's GLB export skips VRML), footprint frame mm: (w, d, h, z0, dx, dy, colour, opacity)
BODIES = {
	'ISP1807':    [(8, 8, 0.95, 0.05, 0, 0, '#202124', 1)],
	'IM73D122':   [(3, 4, 0.2, 0.05, 0, 0, '#d9bf59', 1), (3, 4, 0.95, 0.25, 0, 0, '#c7c9d1', 1)],
	'LIS2DW12':   [(2, 2, 0.7, 0.03, 0, 0, '#1a1a1a', 1)],
	'SOT666':     [(1.2, 1.6, 0.55, 0.03, 0, 0, '#1a1a1a', 1)],
	'SDNAND':     [(8, 6, 0.7, 0.05, 0, 0, '#1a1a1a', 1)],
	'LED_RGB_REV':  [(3.2, 1.25, 0.48, 0.0, 0, 0, '#f2f2f2', 1), (1.4, 1.25, 0.62, -0.62, 0, 0, '#e8f2ff', 0.6)],  # lens hangs into the board slot
	'X2SON4_1x1': [(1, 1, 0.37, 0.03, 0, 0, '#1a1a1a', 1)],
	'SOT523':     [(0.8, 1.6, 0.7, 0.05, 0, 0, '#1a1a1a', 1), (0.35, 0.3, 0.15, 0, -0.6, -0.5, '#cccccc', 1), (0.35, 0.3, 0.15, 0, -0.6, 0.5, '#cccccc', 1), (0.35, 0.3, 0.15, 0, 0.6, 0, '#cccccc', 1)],
}


def parts3d():
	'''Positions of the parts that need hand-made bodies in the web 3D viewer.'''

	import pcbnew
	from build_pcb import MODELS, OX, OY, R, CY
	board = pcbnew.LoadBoard(PCB)
	out = {'parts': [], 'center': [OX + R, OY + CY], 'radius': R, 'flat': CY}
	for ref, name in MODELS.items():
		fp = board.FindFootprintByReference(ref)
		out['parts'].append({'ref': ref, 'x': pcbnew.ToMM(fp.GetPosition().x), 'y': pcbnew.ToMM(fp.GetPosition().y), 'rot': fp.GetOrientationDegrees(), 'back': fp.IsFlipped(), 'bodies': BODIES[name]})
	m = board.FindFootprintByReference('M1').GetPosition(), board.FindFootprintByReference('M2').GetPosition()
	out['motor'] = {'x': pcbnew.ToMM(m[0].x + m[1].x) / 2, 'y': pcbnew.ToMM(m[0].y + m[1].y) / 2}
	m = board.FindFootprintByReference('M1').GetPosition(), board.FindFootprintByReference('M2').GetPosition()
	out['motor'] = {'x': pcbnew.ToMM(m[0].x + m[1].x) / 2, 'y': pcbnew.ToMM(m[0].y + m[1].y) / 2}
	out['mic_ports'] = [{'x': pcbnew.ToMM(p.GetPosition().x), 'y': pcbnew.ToMM(p.GetPosition().y)} for r in ('MK1', 'MK2') for p in board.FindFootprintByReference(r).Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH]
	j1 = board.FindFootprintByReference('J1').GetPosition()
	out['usb'] = {'x': pcbnew.ToMM(j1.x), 'y': pcbnew.ToMM(j1.y) + 3.65}  # mouth of the USB-C socket
	json.dump(out, open(os.path.join(RENDER, 'parts3d.json'), 'w'), indent=1)


def renders():
	'''3D renders and layer SVGs for the preview page.'''

	os.makedirs(RENDER, exist_ok=True)
	for side in ('top', 'bottom'):
		cli('pcb', 'render', '--side', side, '--quality', 'high', '--width', '1400', '--height', '1400', '--zoom', '1.0', '--background', 'transparent', '-o', os.path.join(RENDER, f'{side}.png'), PCB)
	cli('pcb', 'render', '--side', 'top', '--quality', 'high', '--width', '1400', '--height', '1000', '--rotate', '-45,0,30', '--background', 'transparent', '-o', os.path.join(RENDER, 'iso.png'), PCB)
	for name, layers in [('copper_top', 'F.Cu,F.Silkscreen,Edge.Cuts'), ('copper_in2', 'In2.Cu,Edge.Cuts'), ('copper_in3', 'In3.Cu,Edge.Cuts'), ('copper_bottom', 'B.Cu,B.Silkscreen,Edge.Cuts')]:
		cli('pcb', 'export', 'svg', '--layers', layers, '--mode-single', '--page-size-mode', '2', '--exclude-drawing-sheet', '--fit-page-to-board', '-o', os.path.join(RENDER, f'{name}.svg'), PCB)
	cli('sch', 'export', 'svg', '--exclude-drawing-sheet', '-o', RENDER, os.path.join(HERE, 'omi.kicad_sch'))
	# exits 2 because it can't read the VRML bodies (the web viewer draws those from parts3d.json), the GLB is still written
	subprocess.run(['kicad-cli', 'pcb', 'export', 'glb', '--subst-models', '--include-tracks', '--include-pads', '--include-zones', '--include-silkscreen', '--include-soldermask', '-f', '-o', os.path.join(RENDER, 'omi.glb'), PCB], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
	parts3d()


def main():
	'''Build every output.'''

	fab()
	renders()
	print('outputs written')



if __name__ == '__main__':
	main()
