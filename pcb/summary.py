#!/usr/bin/env python3
# DIY Omi PCB - preview summary: live JLCPCB prices/stock, DRC counts, cost estimate - acidvegas

import json
import os
import re
import subprocess
import urllib.request

from parts import PARTS


HERE = os.path.dirname(os.path.abspath(__file__))
UA   = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36'
API  = 'https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList'
QTY  = 2  # boards assembled


def jlc(code: str) -> dict:
	'''Look up one LCSC code in the JLCPCB parts library.'''

	body = json.dumps({'keyword': code, 'currentPage': 1, 'pageSize': 5}).encode()
	req = urllib.request.Request(API, data=body, headers={'User-Agent': UA, 'Content-Type': 'application/json'})
	with urllib.request.urlopen(req, timeout=10) as r:
		data = json.load(r)
	for c in data['data']['componentPageInfo']['list'] or []:
		if c['componentCode'] == code:
			return c
	return {}


def price_at(c: dict, qty: int) -> float:
	'''Unit price for a quantity from the price breaks.'''

	best = None
	for p in c.get('componentPrices') or []:
		if p['startNumber'] <= qty:
			best = p['productPrice']
	return best


def drc() -> tuple:
	'''Run DRC with schematic parity and return (errors, unrouted, report text).'''

	rpt = os.path.join(HERE, 'drc.rpt')
	subprocess.run(['kicad-cli', 'pcb', 'drc', '--schematic-parity', '--severity-error', '-o', rpt, os.path.join(HERE, 'omi.kicad_pcb')], stdout=subprocess.DEVNULL)
	text = open(rpt).read()
	errors = len(re.findall(r'^\[', text, re.M))
	unrouted = int(re.search(r'Found (\d+) unconnected', text).group(1)) if re.search(r'Found (\d+) unconnected', text) else 0
	return errors, unrouted, text


def main():
	'''Write preview/summary.json.'''

	groups = {}
	for p in PARTS:
		if p.get('lcsc'):
			groups.setdefault(p['lcsc'], {'value': p['value'], 'refs': []})['refs'].append(p['ref'])
	bom, parts_cost, ext = [], 0.0, 0
	for code, g in groups.items():
		c = jlc(code)
		n = len(g['refs'])
		price = price_at(c, n * QTY) if c else None
		stock = c.get('stockCount', 0) if c else 0
		if c and c.get('componentLibraryType') != 'base':
			ext += 1
		if price is not None and code != 'C5264268':
			parts_cost += price * n * QTY
		bom.append({'value': g['value'], 'refs': ','.join(g['refs']), 'lcsc': code, 'price': price, 'stock': stock, 'warn': stock < n * QTY})
	isp = 13.65  # ISP1807 via Global Sourcing (DigiKey/Mouser list price), not in JLC stock
	errors, unrouted, _ = drc()
	# Economic PCBA, one side: every assembled part is on the inner side (JLC fee table, Sep 2026)
	setup, stencil, ext_fee = 8.18, 1.53, 3.07 * ext
	pcb_note = 'quote on order (6-layer 0.8 mm, 5 pcs)'
	total = parts_cost + isp * QTY + setup + stencil + ext_fee
	summary = {
		'size': 'Ø26 mm round',
		'layers': '6 layers',
		'thickness': '0.8 mm',
		'parts_top': sum(1 for p in PARTS if p.get('lcsc')),
		'drc_errors': errors,
		'unrouted': unrouted,
		'bom': bom,
		'cost_per_board': total / QTY,
		'cost_lines': [
			('JLC parts, 2 boards', f'${parts_cost:.2f}'),
			('ISP1807 ×2 via Global Sourcing (~$13.65 ea)', f'${isp * QTY:.2f}'),
			(f'Extended-part loading fees ({ext} × $3.07)', f'${ext_fee:.2f}'),
			('Economic PCBA setup + stencil', f'${setup + stencil:.2f}'),
			('Total before PCB fab and shipping', f'${total:.2f}'),
			('6-layer PCB fab', pcb_note),
			('Battery and vibration motor (not on board)', 'separate'),
		],
		'todo': [
			'ISP1807-LR-RS is out of stock at JLC, DigiKey and Mouser right now (500 due at DigiKey ~16 Dec 2026, 10k at Mouser ~14 Dec). Order it through JLC Global Sourcing once it lands.',
			'In JLC\'s placement preview, check every part\'s rotation and pin 1 (especially U1, U2, U3, U4, U5, U6, MK1, MK2, LED1, Q1, Q2, D1). KiCad and JLC disagree on zero-rotation for some packages, and I did not apply any corrections.',
			'PCB order: 6 layers, 0.8 mm, ENIG, via-in-pad filled and capped (6-layer default), tented vias, min via 0.2/0.4 mm.',
			'Battery: a CP1654 A3 Li-ion cell (Ø16 × 5.4 mm, ~120 mAh, 4.2 V) with wire leads and a protection circuit, e.g. amazon.com/dp/B0F8BLXYPJ. It sits under the board, offset away from the antenna; solder its red lead to B+ and black to B−. Charge current is 66 mA (R3 = 15k), about 0.5C.',
			'Charging/USB: USB-C socket (HRO TYPE-C-31-M-12, C165948) at the bottom edge, with 5.1k CC pull-downs so any USB-C charger or computer supplies 5V. The case needs a port opening in its side wall there.',
			'Motor: a 5 × 2.5 mm 3 V coin vibration motor (like Omi\'s), soldered to M+ / M−.',
			'First flash: touch a programmer (J-Link, or a Pico running debugprobe) to the IO/CK/3V/G pads, load an nRF52840 UF2 bootloader, then use USB-C.',
			'Front face: all parts are on the inner side; the blank side of the board sits flat against the inside of the case front. Each mic listens through a 0.8 mm hole in the board: put a 1.0-1.2 mm hole in the case front directly over each (15.4 mm apart) and seal board to case around it (a thin adhesive gasket ring or a dab of soft sealant). The RGB LED shines out through a 1.8 × 1.7 mm slot in the board: give the case a matching hole or a thin (≤0.5 mm) translucent spot there. The 4 SWD test pads are also on the front face, reachable before the case goes on.',
			'Assembly: one-sided Economic PCBA (every machine-placed part is on the inner side). Battery and motor wires solder to the B+/B−/M+/M− pads on the inner side; the battery sits above the parts, offset away from the antenna.',
			'Firmware settings the hardware relies on: PDM clock 1.280 MHz with ratio 80 (16 kHz), stereo, MK1 = falling-edge channel, MK2 = rising; LED pins P0.13/P0.17/P0.14 in high-drive mode; drive P0.30 low to power the SD NAND (and float its SPI pins before turning it off); read charge status on P0.31 (low = charging); battery ADC on AIN4 with TACQ = 40 us; enable the nRF DC/DC (DCDCEN, inductors are inside the module); PWM the motor at ~70% duty from a full cell and keep it at or below 10 kHz; stop recording below ~3.4 V.',
			'Rev 1 is unverified: the RF performance, mic land pattern orientation and SD NAND footprint come from datasheets and have not been tested on hardware.',
		],
		'project_path': HERE,
	}
	json.dump(summary, open(os.path.join(HERE, 'preview', 'summary.json'), 'w'), indent=1)
	print(json.dumps({k: summary[k] for k in ('drc_errors', 'unrouted', 'cost_per_board')}))



if __name__ == '__main__':
	main()
