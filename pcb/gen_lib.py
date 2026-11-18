#!/usr/bin/env python3
# DIY Omi PCB - writes custom footprints, symbol library and schematic - acidvegas

import math
import os
import uuid

from parts import ISP_PADS, PARTS, SYMBOLS


HERE    = os.path.dirname(os.path.abspath(__file__))
PROJECT = 'omi'
NS      = uuid.UUID('6f6d692d-7063-6200-0000-000000000000')
FONT    = '(effects (font (size 1.27 1.27)))'
HIDE    = '(effects (font (size 1.27 1.27)) (hide yes))'


def uid(*key) -> str:
	'''Deterministic UUID so rebuilds keep stable IDs.'''

	return str(uuid.uuid5(NS, '/'.join(key)))


def sexp_block(text: str, start: int) -> str:
	'''Return the balanced s-expression starting at index start.'''

	depth = 0
	in_str = False
	i = start
	while True:
		c = text[i]
		if in_str:
			if c == '\\':
				i += 1
			elif c == '"':
				in_str = False
		elif c == '"':
			in_str = True
		elif c == '(':
			depth += 1
		elif c == ')':
			depth -= 1
			if depth == 0:
				return text[start:i + 1]
		i += 1


def tokenize(text: str) -> list:
	'''Tokenize an s-expression into a nested list.'''

	stack = [[]]
	i = 0
	while i < len(text):
		c = text[i]
		if c == '(':
			stack.append([])
		elif c == ')':
			done = stack.pop()
			stack[-1].append(done)
		elif c == '"':
			j = i + 1
			while text[j] != '"':
				j += 2 if text[j] == '\\' else 1
			stack[-1].append(text[i + 1:j])
			i = j
		elif not c.isspace():
			j = i
			while j < len(text) and not text[j].isspace() and text[j] not in '()':
				j += 1
			stack[-1].append(text[i:j])
			i = j - 1
		i += 1
	return stack[0][0]


def walk(node: list, tag: str):
	'''Yield every sub-list with the given head tag.'''

	if isinstance(node, list):
		if node and node[0] == tag:
			yield node
		for child in node:
			yield from walk(child, tag)


def device_symbol(name: str) -> tuple:
	'''Copy a symbol from the stock Device library, returning (text, pins {num: (x, y, angle)}).'''

	text = open('/usr/share/kicad/symbols/Device.kicad_sym').read()
	start = text.find(f'(symbol "{name}"')
	block = sexp_block(text, start)
	tree = tokenize(block)
	pins = {}
	for pin in walk(tree, 'pin'):
		at = next(p for p in pin if isinstance(p, list) and p[0] == 'at')
		num = next(p for p in pin if isinstance(p, list) and p[0] == 'number')[1]
		pins[num] = (float(at[1]), float(at[2]), float(at[3]))
	return block.replace(f'(symbol "{name}"', f'(symbol "Device:{name}"', 1), pins


def gen_symbol(name: str, full_name: str) -> tuple:
	'''Build a box symbol from the SYMBOLS table, returning (text, pins {num: (x, y, angle)}).'''

	pins = SYMBOLS[name]
	left = [p for p in pins if p[2] == 'L']
	right = [p for p in pins if p[2] == 'R']
	rows = max(len(left), len(right))
	longest = max(len(p[1]) for p in pins)
	half_w = round(max(5.08, (longest * 1.27 + 2.54)) / 2.54) * 2.54
	top = rows * 2.54 / 2
	top = round(top / 2.54) * 2.54 + 2.54
	pin_pos = {}
	pin_txt = []
	for side, group in (('L', left), ('R', right)):
		for i, (num, label, _) in enumerate(group):
			y = top - 2.54 - i * 2.54
			x = -half_w - 2.54 if side == 'L' else half_w + 2.54
			ang = 0 if side == 'L' else 180
			pin_pos[num] = (x, y, ang)
			pin_txt.append(f'(pin passive line (at {x:.2f} {y:.2f} {ang}) (length 2.54) (name "{label}" {FONT}) (number "{num}" {FONT}))')
	bottom = top - (rows + 1) * 2.54
	body = (
		f'(symbol "{full_name}" (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes)\n'
		f'  (property "Reference" "{ref_prefix(name)}" (at 0 {top + 1.27:.2f} 0) {FONT})\n'
		f'  (property "Value" "{name}" (at 0 {bottom - 1.27:.2f} 0) {FONT})\n'
		f'  (property "Footprint" "" (at 0 0 0) {HIDE})\n'
		f'  (property "Datasheet" "" (at 0 0 0) {HIDE})\n'
		f'  (property "Description" "" (at 0 0 0) {HIDE})\n'
		f'  (symbol "{name}_0_1" (rectangle (start {-half_w:.2f} {top:.2f}) (end {half_w:.2f} {bottom:.2f}) (stroke (width 0.254) (type default)) (fill (type background))))\n'
		f'  (symbol "{name}_1_1"\n    ' + '\n    '.join(pin_txt) + '\n  )\n)'
	)
	return body, pin_pos


def ref_prefix(name: str) -> str:
	'''Reference prefix for a generated symbol.'''

	return {'USB_C_16P': 'J', 'IM73D122': 'MK', 'NMOS_GSD': 'Q', 'PMOS_GSD': 'Q', 'LED_RGB_CA': 'LED', 'PAD': 'TP'}.get(name, 'U')


def fp_header(name: str, descr: str) -> str:
	'''Common footprint header with reference/value fields.'''

	return (
		f'(footprint "{name}"\n  (version 20241229)\n  (generator "omi_build")\n  (layer "F.Cu")\n  (descr "{descr}")\n  (attr smd)\n'
		f'  (property "Reference" "REF**" (at 0 0 0) (layer "F.SilkS") (effects (font (size 0.6 0.6) (thickness 0.1))))\n'
		f'  (property "Value" "{name}" (at 0 0 0) (layer "F.Fab") (effects (font (size 0.6 0.6) (thickness 0.1))))\n'
	)


def fp_rect(layer: str, x1: float, y1: float, x2: float, y2: float, width: float) -> str:
	'''Rectangle graphic on a layer.'''

	return f'  (fp_rect (start {x1:.4f} {y1:.4f}) (end {x2:.4f} {y2:.4f}) (stroke (width {width}) (type solid)) (fill no) (layer "{layer}"))\n'


def fp_pad(num: str, x: float, y: float, w: float, h: float, rr: float = 0.1) -> str:
	'''Rounded-rect SMD pad.'''

	return f'  (pad "{num}" smd roundrect (at {x:.4f} {y:.4f}) (size {w:.4f} {h:.4f}) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio {rr}))\n'


def write_footprints():
	'''Write the custom footprint library omi.pretty.'''

	lib = os.path.join(HERE, 'omi.pretty')
	os.makedirs(lib, exist_ok=True)

	# ISP1807: datasheet top view, origin at body centre, antenna half at +y
	t = fp_header('ISP1807', 'Insight SiP ISP1807 nRF52840 module, 8x8x1mm LGA, pads per datasheet R19 section 4.1')
	for num, (x, y, w, h) in sorted(ISP_PADS.items()):
		t += fp_pad(str(num), x - 4, y - 4, w, h, 0.05)
	t += fp_rect('F.Fab', -4, -4, 4, 4, 0.1)
	t += fp_rect('F.CrtYd', -4.25, -4.25, 4.25, 4.25, 0.05)
	t += '  (fp_line (start -4.1 -4.1) (end -3.0 -4.1) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))\n'
	t += '  (fp_line (start -4.1 -4.1) (end -4.1 -3.0) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))\n'
	t += '  (fp_text user "ANT" (at 0 2 0) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))\n)\n'
	open(os.path.join(lib, 'ISP1807.kicad_mod'), 'w').write(t)

	# Infineon IM73D122V01 bottom-port mic, LGA 4x3, land pattern per datasheet figure 13 (top view): sound port up, pin 1 bottom-left.
	# GND ring is 0.6-1.04 mm radius (datasheet 0.58, widened 0.02 for the 0.2 mm hole clearance rule) around a 0.8 mm NPTH sound port.
	t = fp_header('IM73D122_LGA5_4x3', 'Infineon IM73D122V01 bottom-port PDM microphone, 4x3x1.2mm, datasheet figure 13, 0.8 mm sound port')
	port = -0.68
	for num, x, y in (('1', -0.85, 1.5), ('2', -0.85, 0.8), ('3', 0.85, 1.5), ('4', 0.85, 0.8)):
		t += fp_pad(num, x, y, 0.75, 0.45, 0.2)
	t += (f'  (pad "5" smd custom (at 0 {port - 0.82:.4f}) (size 0.4 0.4) (layers "F.Cu" "F.Mask") (options (clearance outline) (anchor circle))\n'
	      f'    (primitives (gr_circle (center 0 0.82) (end 0.82 0.82) (width 0.44) (fill no))))\n')
	for k in range(6):
		a = math.radians(30 + 60 * k)
		t += f'  (pad "" smd roundrect (at {0.82 * math.cos(a):.4f} {port + 0.82 * math.sin(a):.4f} {-(90 + 30 + 60 * k) % 360}) (size 0.5 0.32) (layers "F.Paste") (roundrect_rratio 0.5))\n'
	t += f'  (pad "" np_thru_hole circle (at 0 {port}) (size 0.8 0.8) (drill 0.8) (layers "*.Cu" "*.Mask"))\n'
	t += fp_rect('F.Fab', -1.5, -2, 1.5, 2, 0.1)
	t += fp_rect('F.CrtYd', -1.75, -2.25, 1.75, 2.25, 0.05)
	t += f'  (fp_circle (center 0 {port}) (end 0.7 {port}) (stroke (width 0.05) (type solid)) (fill no) (layer "B.CrtYd"))\n'  # keeps parts on the other side clear of the sound port
	t += '  (fp_circle (center -1.75 2.0) (end -1.65 2.0) (stroke (width 0.12) (type solid)) (fill no) (layer "F.SilkS"))\n)\n'
	open(os.path.join(lib, 'IM73D122_LGA5_4x3.kicad_mod'), 'w').write(t)

	# SD NAND LGA-8 8x6 (CSNP / MKDV families): device pad centres 7.0 mm apart, land 1.0x0.8 at +-3.45 covers both
	t = fp_header('SDNAND_LGA8_8x6', 'SD NAND LGA-8 8x6x0.75mm, P1.27 (CSNP1GCR01 / MKDV4GCL)')
	ys = [-1.905, -0.635, 0.635, 1.905]
	for i, y in enumerate(ys):
		t += fp_pad(str(i + 1), -3.45, y, 1.0, 0.8)
		t += fp_pad(str(8 - i), 3.45, y, 1.0, 0.8)
	t += fp_rect('F.Fab', -4, -3, 4, 3, 0.1)
	t += fp_rect('F.CrtYd', -4.25, -3.25, 4.25, 3.25, 0.05)
	t += '  (fp_circle (center -2.3 -2.2) (end -2.1 -2.2) (stroke (width 0.12) (type solid)) (fill no) (layer "F.SilkS"))\n)\n'
	open(os.path.join(lib, 'SDNAND_LGA8_8x6.kicad_mod'), 'w').write(t)

	# MEIHUA MHT151RGBCT reverse-mount RGB LED (3.2x1.25, lens down through the board). Pad numbering from JLC/EasyEDA's footprint
	# for C409782 (component-side view): 3 TL, 2 TR, 4 BL, 1 BR; pads 0.8x0.7 per datasheet p2. 1.8x1.7 NPTH slot for the lens (EasyEDA).
	t = fp_header('LED_RGB_REV_1206', 'MHT151RGBCT common-anode reverse-mount RGB LED 3.2x1.25mm, shines through a 1.8x1.7mm board slot')
	for num, x, y in (('1', 1.55, 0.55), ('2', 1.55, -0.55), ('3', -1.55, -0.55), ('4', -1.55, 0.55)):
		t += fp_pad(num, x, y, 0.8, 0.7, 0.15)
	t += '  (pad "" np_thru_hole oval (at 0 0) (size 1.8 1.7) (drill oval 1.8 1.7) (layers "*.Cu" "*.Mask"))\n'
	t += fp_rect('F.Fab', -1.6, -0.625, 1.6, 0.625, 0.1)
	t += fp_rect('F.CrtYd', -2.2, -1.15, 2.2, 1.15, 0.05)
	t += '  (fp_line (start 2.3 0.3) (end 2.3 0.9) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))\n)\n'
	open(os.path.join(lib, 'LED_RGB_REV_1206.kicad_mod'), 'w').write(t)



def write_symbol_lib() -> dict:
	'''Write omi.kicad_sym and return symbol texts/pins keyed by lib_id.'''

	syms = {}
	lib_txt = []
	for name in SYMBOLS:
		body, pins = gen_symbol(name, name)
		lib_txt.append(body)
		syms[f'omi:{name}'] = gen_symbol(name, f'omi:{name}')
	for name in ('R', 'C', 'D_Schottky'):
		syms[f'Device:{name}'] = device_symbol(name)
	open(os.path.join(HERE, 'omi.kicad_sym'), 'w').write('(kicad_symbol_lib (version 20241209) (generator "omi_build") (generator_version "9.0")\n' + '\n'.join(lib_txt) + '\n)\n')
	return syms


def write_schematic(syms: dict):
	'''Place every part on one sheet with a net label on each pin.'''

	root = uid('sch-root')
	used = sorted({p['sym'] for p in PARTS})
	out = [
		f'(kicad_sch (version 20250114) (generator "eeschema") (generator_version "9.0") (uuid "{root}") (paper "A2")',
		'(title_block (title "DIY Omi wearable") (rev "1") (comment 1 "ISP1807 nRF52840 + 2x PDM mic + SD NAND + IMU") (comment 2 "acidvegas"))',
		'(lib_symbols',
	]
	for lib_id in used:
		out.append(syms[lib_id][0])
	out.append(')')

	# grid placement
	col_x = [40.64, 121.92, 203.2, 284.48, 365.76, 447.04, 528.32]
	x_i, y = 0, 30.48
	col_max = 0
	labels, ncs, inst = [], [], []
	big = [p for p in PARTS if p['sym'].startswith('omi:') and p['sym'] != 'omi:PAD']
	small = [p for p in PARTS if p not in big]
	for part in big + small:
		_, pins = syms[part['sym']]
		ys = [v[1] for v in pins.values()]
		h = (max(ys) - min(ys)) + 15.24
		if y + h > 400:
			x_i += 1
			y = 30.48
		sx = col_x[x_i]
		sy = round((y + max(ys) + 5.08) / 2.54) * 2.54
		y += h + 5.08
		sym_uuid = uid('sym', part['ref'])
		part['sym_uuid'] = sym_uuid
		fp = part['fp']
		props = [
			f'(property "Reference" "{part["ref"]}" (at {sx:.2f} {sy - max(ys) - 3.81:.2f} 0) {FONT})',
			f'(property "Value" "{part["value"]}" (at {sx:.2f} {sy - min(ys) + 3.81:.2f} 0) {FONT})',
			f'(property "Footprint" "{fp}" (at {sx:.2f} {sy:.2f} 0) {HIDE})',
			f'(property "Datasheet" "" (at {sx:.2f} {sy:.2f} 0) {HIDE})',
			f'(property "Description" "" (at {sx:.2f} {sy:.2f} 0) {HIDE})',
		]
		if part.get('lcsc'):
			props.append(f'(property "LCSC" "{part["lcsc"]}" (at {sx:.2f} {sy:.2f} 0) {HIDE})')
		pin_uuids = ' '.join(f'(pin "{n}" (uuid "{uid("pin", part["ref"], n)}"))' for n in pins)
		in_bom = 'yes' if part.get('lcsc') else 'no'  # hand-solder pads stay out of the BOM
		inst.append(
			f'(symbol (lib_id "{part["sym"]}") (at {sx:.2f} {sy:.2f} 0) (unit 1) (exclude_from_sim no) (in_bom {in_bom}) (on_board yes) (dnp no) (uuid "{sym_uuid}")\n  '
			+ '\n  '.join(props) + f'\n  {pin_uuids}\n  (instances (project "{PROJECT}" (path "/{root}" (reference "{part["ref"]}") (unit 1)))))'
		)
		for num, (px, py, ang) in pins.items():
			ex, ey = sx + px, sy - py
			net = part['pins'].get(num, 'MISSING')
			if net == 'MISSING':
				raise SystemExit(f'{part["ref"]} pin {num} not in netlist')
			if net is None:
				ncs.append(f'(no_connect (at {ex:.2f} {ey:.2f}) (uuid "{uid("nc", part["ref"], num)}"))')
				continue
			# label text points away from the symbol body
			if ang == 0:
				l_ang, just = 180, 'right bottom'
			elif ang == 180:
				l_ang, just = 0, 'left bottom'
			elif ang == 90:
				l_ang, just = 270, 'right bottom'
			else:
				l_ang, just = 90, 'left bottom'
			labels.append(f'(global_label "{net}" (shape passive) (at {ex:.2f} {ey:.2f} {l_ang}) (fields_autoplaced yes) (effects (font (size 1.27 1.27)) (justify {just.split()[0]})) (uuid "{uid("lbl", part["ref"], num)}") (property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {ex:.2f} {ey:.2f} 0) {HIDE}))')
		for num in part['pins']:
			if num not in pins:
				raise SystemExit(f'{part["ref"]} netlist pin {num} missing on symbol')

	out += labels + ncs + inst
	out.append('(sheet_instances (path "/" (page "1")))')
	out.append(')')
	open(os.path.join(HERE, f'{PROJECT}.kicad_sch'), 'w').write('\n'.join(out) + '\n')


def write_project_files():
	'''Library tables and a minimal project file.'''

	open(os.path.join(HERE, 'sym-lib-table'), 'w').write('(sym_lib_table (version 7)\n  (lib (name "omi") (type "KiCad") (uri "${KIPRJMOD}/omi.kicad_sym") (options "") (descr "DIY Omi parts"))\n  (lib (name "Device") (type "KiCad") (uri "/usr/share/kicad/symbols/Device.kicad_sym") (options "") (descr "KiCad stock"))\n)\n')
	open(os.path.join(HERE, 'fp-lib-table'), 'w').write('(fp_lib_table (version 7)\n  (lib (name "omi") (type "KiCad") (uri "${KIPRJMOD}/omi.pretty") (options "") (descr "DIY Omi footprints"))\n)\n')
	pro = os.path.join(HERE, f'{PROJECT}.kicad_pro')
	if not os.path.exists(pro):
		open(pro, 'w').write('{"meta": {"filename": "omi.kicad_pro", "version": 1}}\n')


def main():
	'''Generate footprints, symbols and schematic.'''

	write_footprints()
	syms = write_symbol_lib()
	write_schematic(syms)
	write_project_files()
	print('wrote footprints, symbols, schematic')



if __name__ == '__main__':
	main()
