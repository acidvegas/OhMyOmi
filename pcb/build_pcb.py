#!/usr/bin/env python3
# DIY Omi PCB - board placement, keepouts, zones, DSN export and SES import - acidvegas

import math
import os
import sys

try:
	import pcbnew
except ImportError:
	raise ImportError('missing pcbnew (run with the system python that ships with KiCad)')

from gen_lib import uid
from parts import PARTS, ISP_PADS, SYMBOLS


HERE   = os.path.dirname(os.path.abspath(__file__))
PCB    = os.path.join(HERE, 'omi.kicad_pcb')
OX, OY = 100.0, 100.0  # board origin offset (mm)
R      = 13.0          # board radius (mm), a plain circle
W      = 2 * R
CY     = R                                     # circle centre y
H      = 2 * R
MOD_Y0 = R - ((R - 0.25) ** 2 - 4.0 ** 2) ** 0.5  # ISP1807 antenna edge: module corners 0.25 mm inside the circle
KEEP_H = MOD_Y0 + 4.0   # antenna keepout rule area depth from the top (mm), the module's whole 4 mm antenna section
ZONE_T = MOD_Y0 + 4.0   # copper pours start where the module antenna section ends
LIBS   = {'omi': os.path.join(HERE, 'omi.pretty')}

# ref -> (x, y, rotation) in board mm (origin top-left, y down)
PLACE = {
	'U1':   (13.0, MOD_Y0 + 4.0, 180),
	# RGB LED in the middle
	'LED1': (13, 12.9, 0),
	# USB-C at the bottom edge, mouth just past the outline so it lines up with the case wall
	'J1':   (13, 22.1, 0),
	# SD NAND down the left side
	'U2':   (4.9, 12.48, 90),
	# LDO left of the LED
	'U5':   (9.75, 10.8, 0),
	'C3':   (9.75, 12.2, 0),
	'C4':   (9.75, 13.25, 0),
	# LED resistors right of the LED
	'R14':  (15.8, 12.4, 90),
	'R15':  (16.85, 12.4, 90),
	'R16':  (17.9, 12.4, 90),
	# two rows between the LED and the USB-C
	'C5':   (9.7, 14.65, 0),
	'C6':   (11.7, 14.65, 0),
	'R6':   (13.7, 14.65, 0),
	'R7':   (15.7, 14.65, 0),
	'R8':   (9.7, 15.75, 0),
	'R1':   (11.7, 15.75, 0),
	'R2':   (13.7, 15.75, 0),
	'R9':   (15.7, 15.75, 0),
	# accelerometer left of the module
	'U3':   (7.3, 6.7, 0),
	# charger right
	'U4':   (20.55, 12.1, 0),
	'C1':   (23.6, 12.1, 90),
	'C2':   (18.4, 14.5, 0),
	'R3':   (20.4, 14.5, 0),
	'R4':   (18.4, 15.6, 0),
	'R5':   (20.4, 15.6, 0),
	# 2 mics either side of the USB-C, ~15 mm apart; they listen through the board out of the blank front face
	'MK1':  (5.3, 18.9, 90),
	'MK2':  (20.7, 18.9, 90),
	# small parts packed into the remaining space (greedy fit next to the part each one serves)
	'U6':   (13, 10.55, 0),
	'C9':   (5.35, 21.2, 0),
	'C11':  (20.65, 21.2, 0),
	'C7':   (5.5, 6.7, 90),
	'C8':   (4.45, 6.7, 90),
	'R11':  (3.4, 6.7, 90),
	'R12':  (1.05, 10.7, 90),
	'Q2':   (15.75, 10.3, 0),
	'R18':  (1.05, 12.65, 90),
	'R10':  (1.05, 14.6, 90),
	'R17':  (20, 9.8, 0),
	'C10':  (21.9, 15.6, 90),
	'Q1':   (18.4, 8.05, 90),
	'R13':  (2.0, 17.3, 0),
	'D1':   (18.6, 6.1, 0),
	'M1':   (20.55, 8.2, 0),
	'M2':   (20.95, 6.1, 0),
	'BT1':  (22.65, 9.3, 0),
	'BT2':  (23.6, 15.0, 0),
	# SWD test pads on the blank front face
	'TP1':  (9.6, 15.9, 0),
	'TP2':  (11.7, 15.9, 0),
	'TP3':  (14.3, 15.9, 0),
	'TP4':  (16.4, 15.9, 0),
}


# U1 pads that get a filled via in the pad (inner pads that cannot escape on the top layer)
VIA_IN_PAD = [1, 7, 8, 10, 12, 14, 16, 18, 21, 23, 24, 25, 27, 31, 33, 35, 37, 39]
POWER_NETS = ['GND', 'VBAT', 'VBUS', '+3V3', 'MOTOR_N']


def mm(v: float) -> int:
	'''mm to KiCad internal units.'''

	return pcbnew.FromMM(v)


def pt(x: float, y: float) -> 'pcbnew.VECTOR2I':
	'''Board coordinate (mm, top-left origin) to internal point.'''

	return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))


def load_fp(fpid: str) -> 'pcbnew.FOOTPRINT':
	'''Load a footprint by lib:name from the project or stock libraries.'''

	lib, name = fpid.split(':')
	path = LIBS.get(lib, f'/usr/share/kicad/footprints/{lib}.pretty')
	fp = pcbnew.FootprintLoad(path, name)
	if fp is None:
		raise SystemExit(f'footprint not found: {fpid}')
	return fp


def outline(board: 'pcbnew.BOARD'):
	'''Circular outline on Edge.Cuts.'''

	c = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_CIRCLE)
	c.SetCenter(pt(R, CY))
	c.SetEnd(pt(R, CY + R))
	c.SetLayer(pcbnew.Edge_Cuts)
	c.SetWidth(mm(0.05))
	board.Add(c)


def rect_poly(x1: float, y1: float, x2: float, y2: float) -> 'pcbnew.SHAPE_LINE_CHAIN':
	'''Closed rectangle outline.'''

	chain = pcbnew.SHAPE_LINE_CHAIN()
	for x, y in [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]:
		chain.Append(pt(x, y))
	chain.SetClosed(True)
	return chain


def add_zone(board: 'pcbnew.BOARD', net: str, layer: int, priority: int = 0):
	'''Copper pour over the board below the antenna keepout.'''

	z = pcbnew.ZONE(board)
	z.SetLayer(layer)
	z.SetNet(board.FindNet(net))
	z.Outline().AddOutline(rect_poly(0, ZONE_T, W, H))
	z.SetLocalClearance(mm(0.15))
	z.SetMinThickness(mm(0.15))
	z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
	z.SetThermalReliefGap(mm(0.2))
	z.SetThermalReliefSpokeWidth(mm(0.25))
	z.SetAssignedPriority(priority)
	z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
	board.Add(z)


def add_keepout(board: 'pcbnew.BOARD'):
	'''Antenna metal exclusion zone: no copper on any layer across the top edge.'''

	z = pcbnew.ZONE(board)
	z.SetIsRuleArea(True)
	z.SetLayerSet(pcbnew.LSET.AllCuMask())
	z.Outline().AddOutline(rect_poly(-0.5, -0.5, W + 0.5, KEEP_H))
	z.SetDoNotAllowTracks(True)
	z.SetDoNotAllowVias(True)
	z.SetDoNotAllowCopperPour(True)
	z.SetDoNotAllowPads(False)
	z.SetDoNotAllowFootprints(False)
	z.SetZoneName('ANTENNA_KEEPOUT')
	board.Add(z)


def add_edge_keepout(board: 'pcbnew.BOARD', inset: float = 0.3):
	'''No tracks or vias within inset of the board edge (the autorouter ignores the edge-clearance rule).'''

	outline_set = pcbnew.SHAPE_POLY_SET()
	board.GetBoardPolygonOutlines(outline_set)
	inner = outline_set.CloneDropTriangulation()
	inner.Deflate(mm(inset), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, mm(0.01))
	ring = outline_set.CloneDropTriangulation()
	ring.BooleanSubtract(inner)
	z = pcbnew.ZONE(board)
	z.SetIsRuleArea(True)
	z.SetLayerSet(pcbnew.LSET.AllCuMask())
	ring.thisown = False  # the zone takes ownership of the polygon
	z.SetOutline(ring)
	z.SetDoNotAllowTracks(True)
	z.SetDoNotAllowVias(True)
	z.SetDoNotAllowCopperPour(False)
	z.SetDoNotAllowPads(False)
	z.SetDoNotAllowFootprints(False)
	z.SetZoneName('EDGE_KEEPOUT')
	board.Add(z)


def add_hole_keepouts(board: 'pcbnew.BOARD', margin: float = 0.35):
	'''No tracks or vias near the mic sound ports and the LED slot (NPTH holes count as board edge for clearance).'''

	for fp in board.GetFootprints():
		for pad in fp.Pads():
			if pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
				continue
			c = pad.GetPosition()
			r = max(pcbnew.ToMM(pad.GetSize().x), pcbnew.ToMM(pad.GetSize().y)) / 2 + margin
			chain = pcbnew.SHAPE_LINE_CHAIN()
			for k in range(32):
				a = 2 * math.pi * k / 32
				chain.Append(pcbnew.VECTOR2I(c.x + mm(r * math.cos(a)), c.y + mm(r * math.sin(a))))
			chain.SetClosed(True)
			z = pcbnew.ZONE(board)
			z.SetIsRuleArea(True)
			z.SetLayerSet(pcbnew.LSET.AllCuMask())
			z.Outline().AddOutline(chain)
			z.SetDoNotAllowTracks(True)
			z.SetDoNotAllowVias(True)
			z.SetDoNotAllowCopperPour(False)
			z.SetDoNotAllowPads(False)
			z.SetDoNotAllowFootprints(False)
			z.SetZoneName(f'HOLE_KEEPOUT_{fp.GetReference()}')
			board.Add(z)


def setup_rules(board: 'pcbnew.BOARD'):
	'''JLCPCB 6-layer friendly rules and net classes.'''

	board.SetCopperLayerCount(6)
	ds = board.GetDesignSettings()
	ds.SetBoardThickness(mm(0.8))
	ds.m_TrackMinWidth = mm(0.09)
	ds.m_MinClearance = mm(0.09)
	ds.m_ViasMinSize = mm(0.4)
	ds.m_MinThroughDrill = mm(0.2)
	ds.m_ViasMinAnnularWidth = mm(0.1)
	ds.m_HoleToHoleMin = mm(0.2)
	ds.m_HoleClearance = mm(0.2)
	ds.m_CopperEdgeClearance = mm(0.25)
	ds.m_SolderMaskMinWidth = mm(0)
	ns = ds.m_NetSettings
	dflt = ns.GetDefaultNetclass()
	dflt.SetClearance(mm(0.1))
	dflt.SetTrackWidth(mm(0.1))
	dflt.SetViaDiameter(mm(0.4))
	dflt.SetViaDrill(mm(0.2))
	pwr = pcbnew.NETCLASS('Power')
	pwr.SetClearance(mm(0.1))
	pwr.SetTrackWidth(mm(0.25))
	pwr.SetViaDiameter(mm(0.4))
	pwr.SetViaDrill(mm(0.2))
	ns.SetNetclass('Power', pwr)
	for net in POWER_NETS:
		ns.SetNetclassPatternAssignment(net, 'Power')
	board.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)
	board.SetLayerType(pcbnew.In4_Cu, pcbnew.LT_POWER)


def place(board: 'pcbnew.BOARD'):
	'''Create nets, load, place and wire up every footprint.'''

	nets = {}
	for part in PARTS:
		for net in part['pins'].values():
			if net and net not in nets:
				ni = pcbnew.NETINFO_ITEM(board, net)
				board.Add(ni)
				nets[net] = ni
	for part in PARTS:
		ref = part['ref']
		fp = load_fp(part['fp'])
		fp.SetReference(ref)
		fp.SetValue(part['value'])
		fp.SetPath(pcbnew.KIID_PATH(f'/{uid("sym", ref)}'))
		fp.SetSheetname('Root')
		fp.SetSheetfile('omi.kicad_sch')
		fp.SetFPIDAsString(part['fp'])
		if part.get('lcsc'):
			field = pcbnew.PCB_FIELD(fp, fp.GetNextFieldId(), 'LCSC')
			field.SetText(part['lcsc'])
			field.SetVisible(False)
			fp.AddField(field)
		board.Add(fp)
		x, y, rot = PLACE[ref]
		fp.SetPosition(pt(x, y))
		if part.get('side') == 'B':
			fp.Flip(pt(x, y), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
			if not part.get('lcsc'):  # hand-solder pads; the mics and their caps on the back are machine placed
				fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
		fp.SetOrientationDegrees(rot)
		fp.Reference().SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
		fp.Reference().SetTextThickness(mm(0.15))
		fp.Reference().SetVisible(False)
		if not part.get('lcsc'):
			label_bottom(fp)
		for pad in fp.Pads():
			net = part['pins'].get(pad.GetNumber())
			if net:
				pad.SetNet(nets[net])


def name_unconnected(board: 'pcbnew.BOARD'):
	'''Give no-connect pads the same unconnected-(REF-PIN-PadN) nets the schematic netlist uses.'''

	for part in PARTS:
		name = part['sym'].split(':')[1]
		labels = {n: l for n, l, _ in SYMBOLS.get(name, [])} if part['sym'].startswith('omi:') else {}
		fp = board.FindFootprintByReference(part['ref'])
		for pad in fp.Pads():
			num = pad.GetNumber()
			if num in part['pins'] and part['pins'][num] is None:
				net = f'unconnected-({part["ref"]}-{labels.get(num, num)}-Pad{num})'
				ni = board.FindNet(net)
				if ni is None:
					ni = pcbnew.NETINFO_ITEM(board, net)
					board.Add(ni)
				pad.SetNet(ni)


MODELS = {
	'U1':   'ISP1807',
	'MK1':  'IM73D122',
	'MK2':  'IM73D122',
	'U3':   'LIS2DW12',
	'U6':   'SOT666',
	'Q2':   'SOT523',
	'U2':   'SDNAND',
	'LED1': 'LED_RGB_REV',
	'U5':   'X2SON4_1x1',
	'Q1':   'SOT523',
}

# vendor STEP models: ref -> (file, offset, rotation); the USB-C one is LCSC/EasyEDA's C165948 model, lined up on the footprint's shell legs
VENDOR_MODELS = {
	'J1': ('vendor/USB_C_HRO_TYPE-C-31-M-12.step', (0, -1.05, 0), (0, 0, 180)),
}


def set_models(board: 'pcbnew.BOARD'):
	'''Attach the simple project VRML bodies to parts KiCad ships no 3D model for.'''

	for ref, name in MODELS.items():
		fp = board.FindFootprintByReference(ref)
		fp.Models().clear()
		m = pcbnew.FP_3DMODEL()
		m.m_Filename = '${KIPRJMOD}/omi.3dshapes/' + name + '.wrl'
		fp.Models().push_back(m)
	for ref, (name, offset, rotation) in VENDOR_MODELS.items():
		fp = board.FindFootprintByReference(ref)
		fp.Models().clear()
		m = pcbnew.FP_3DMODEL()
		m.m_Filename = '${KIPRJMOD}/omi.3dshapes/' + name
		m.m_Offset = pcbnew.VECTOR3D(*offset)
		m.m_Rotation = pcbnew.VECTOR3D(*rotation)
		fp.Models().push_back(m)


def label_bottom(fp: 'pcbnew.FOOTPRINT'):
	'''Show the pad's value (B+, M-, IO...) on the silkscreen of the side the pad is on.'''

	v = fp.Value()
	v.SetLayer(pcbnew.B_SilkS if fp.IsFlipped() else pcbnew.F_SilkS)
	v.SetVisible(True)
	v.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
	v.SetTextThickness(mm(0.15))
	ref = fp.GetReference()
	dx, dy = {'J1': (0, 99), 'M1': (2.0, -0.3), 'M2': (2.0, 0), 'BT1': (1.55, 0)}.get(ref, (0, 1.3))
	if ref == 'J1':
		v.SetVisible(False)
		return
	v.SetPosition(fp.GetPosition() + pcbnew.VECTOR2I(mm(dx), mm(dy)))
	v.SetTextAngleDegrees(0)


def prefab_copper(board: 'pcbnew.BOARD'):
	'''Turn ISP1807 inner pads into through pads for routing (become SMD + filled via later) and bridge the antenna pins.'''

	u1 = board.FindFootprintByReference('U1')
	pads = {int(p.GetNumber()): p for p in u1.Pads() if p.GetNumber().isdigit()}
	for num in VIA_IN_PAD:
		pad = pads[num]
		pad.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
		pad.SetDrillSize(pcbnew.VECTOR2I(mm(0.2), mm(0.2)))
		ls = pcbnew.LSET.AllCuMask()
		ls.AddLayer(pcbnew.F_Mask)
		pad.SetLayerSet(ls)
	t = pcbnew.PCB_TRACK(board)
	t.SetStart(pads[20].GetPosition())
	t.SetEnd(pads[22].GetPosition())
	t.SetWidth(mm(0.3))
	t.SetLayer(pcbnew.F_Cu)
	t.SetNet(pads[20].GetNet())
	t.SetLocked(True)
	board.Add(t)


def gnd_fanout(board: 'pcbnew.BOARD'):
	'''Pre-place a GND via next to every top-side GND pad (outside U1) so pours can never strand them.'''

	others = [(fp, p) for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetname() != 'GND']
	outline = pcbnew.SHAPE_POLY_SET()
	board.GetBoardPolygonOutlines(outline)
	placed = []
	for fp in board.GetFootprints():
		if fp.GetReference() == 'U1' or fp.IsFlipped():
			continue
		c = fp.GetPosition()
		for pad in fp.Pads():
			if pad.GetNetname() != 'GND' or pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
				continue
			pc = pad.GetPosition()
			d = pc - c
			n = (d.x ** 2 + d.y ** 2) ** 0.5
			cands = []
			if n < mm(0.05):
				cands.append(pc)
			else:
				ux, uy = d.x / n, d.y / n
				bb = pad.GetBoundingBox()
				ext = abs(ux) * bb.GetWidth() / 2 + abs(uy) * bb.GetHeight() / 2
				for extra in (0.3, 0.4, 0.55):
					cands.append(pcbnew.VECTOR2I(int(pc.x + ux * (ext + mm(extra))), int(pc.y + uy * (ext + mm(extra)))))
				for vx, vy in ((-uy, ux), (uy, -ux)):
					e2 = abs(vx) * bb.GetWidth() / 2 + abs(vy) * bb.GetHeight() / 2
					for extra in (0.3, 0.45):
						cands.append(pcbnew.VECTOR2I(int(pc.x + vx * (e2 + mm(extra))), int(pc.y + vy * (e2 + mm(extra)))))
			for v in cands:
				if pcbnew.ToMM(v.y) - OY < KEEP_H + 0.5 or not outline.Contains(v) or outline.Outline(0).PointOnEdge(v, mm(0.45)):
					continue
				if any(p.GetEffectiveShape(l).Collide(v, mm(0.32)) for _, p in others for l in (pcbnew.F_Cu, pcbnew.B_Cu) if p.IsOnLayer(l)):
					continue
				if any(p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) and p.GetEffectiveHoleShape().Collide(v, mm(0.45)) for _, p in others):
					continue
				if any((q - v).EuclideanNorm() < mm(0.5) for q in placed):
					continue
				via = pcbnew.PCB_VIA(board)
				via.SetPosition(v)
				via.SetWidth(mm(0.4))
				via.SetDrill(mm(0.2))
				via.SetNet(pad.GetNet())
				via.SetLocked(True)
				board.Add(via)
				if v != pc:
					tr = pcbnew.PCB_TRACK(board)
					tr.SetStart(pc)
					tr.SetEnd(v)
					tr.SetWidth(mm(0.2))
					tr.SetLayer(pcbnew.F_Cu)
					tr.SetNet(pad.GetNet())
					tr.SetLocked(True)
					board.Add(tr)
				placed.append(v)
				break


def widen_neckdowns(board: 'pcbnew.BOARD'):
	'''Widen autorouter neck-downs to 0.09 mm, keeping the original width where that would break 0.1 mm clearance.'''

	for t in list(board.GetTracks()):
		if t.GetClass() != 'PCB_TRACK' or t.GetWidth() >= mm(0.09):
			continue
		old = t.GetWidth()
		t.SetWidth(mm(0.09))
		layer = t.GetLayer()
		shape = t.GetEffectiveShape(layer)
		near = [o.GetEffectiveShape(layer) for o in board.GetTracks() if o.GetNetCode() != t.GetNetCode() and o.IsOnLayer(layer)]
		near += [p.GetEffectiveShape(layer) for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetCode() != t.GetNetCode() and p.IsOnLayer(layer)]
		if any(shape.Collide(s, mm(0.1) - 1) for s in near):
			board.Remove(t)  # leftover gap is re-routed by fixup.py auto


def restore_via_in_pad(board: 'pcbnew.BOARD'):
	'''Convert the routing-only through pads back to SMD pads with a filled via in each.'''

	u1 = board.FindFootprintByReference('U1')
	for pad in u1.Pads():
		if pad.GetAttribute() != pcbnew.PAD_ATTRIB_PTH:
			continue
		v = pcbnew.PCB_VIA(board)
		v.SetPosition(pad.GetPosition())
		v.SetWidth(mm(0.4))
		v.SetDrill(mm(0.2))
		v.SetNet(pad.GetNet())
		v.SetLocked(True)
		board.Add(v)
		pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
		pad.SetDrillSize(pcbnew.VECTOR2I(0, 0))
		pad.SetShape(pcbnew.PAD_SHAPE_ROUNDRECT)
		pad.SetRoundRectRadiusRatio(0.05)
		x, y, w, h = ISP_PADS[int(pad.GetNumber())]
		pad.SetSize(pcbnew.VECTOR2I(mm(w), mm(h)))
		ls = pcbnew.LSET()
		for l in (pcbnew.F_Cu, pcbnew.F_Paste, pcbnew.F_Mask):
			ls.AddLayer(l)
		pad.SetLayerSet(ls)


def stage_place():
	'''Build the unrouted board and export Specctra DSN for the autorouter.'''

	board = pcbnew.CreateEmptyBoard()
	setup_rules(board)
	outline(board)
	place(board)
	prefab_copper(board)
	gnd_fanout(board)
	add_keepout(board)
	add_zone(board, 'GND', pcbnew.In1_Cu)
	add_zone(board, 'GND', pcbnew.In4_Cu)
	board.Save(PCB)
	board = pcbnew.LoadBoard(PCB)
	add_edge_keepout(board)  # needs a loaded board, a fresh one returns a bounding-box outline
	add_hole_keepouts(board)
	board.Save(PCB)
	board = pcbnew.LoadBoard(PCB)
	pcbnew.ZONE_FILLER(board).Fill(board.Zones())
	board.Save(PCB)
	ok = pcbnew.ExportSpecctraDSN(board, os.path.join(HERE, 'omi.dsn'))
	print('placed, dsn export', ok)


def stage_import():
	'''Import a routed SES into the board.'''

	board = pcbnew.LoadBoard(PCB)
	ok = pcbnew.ImportSpecctraSES(board, os.path.join(HERE, 'omi.ses'))
	board.Save(PCB)
	print('ses import', ok)


def stage_export():
	'''Re-export DSN from the current (partly routed) board for another autorouter run.'''

	board = pcbnew.LoadBoard(PCB)
	print('dsn export', pcbnew.ExportSpecctraDSN(board, os.path.join(HERE, 'omi.dsn')))


def stage_finish():
	'''Widen autorouter neck-downs, add GND pours on the signal layers, refill and save.'''

	board = pcbnew.LoadBoard(PCB)
	restore_via_in_pad(board)
	for part in PARTS:
		fp = board.FindFootprintByReference(part['ref']) or board.FindFootprintByReference(part['value'])
		fp.SetReference(part['ref'])
		fp.Reference().SetVisible(False)
		if not part.get('lcsc'):
			fp.SetValue(part['value'])
			label_bottom(fp)
	for part in PARTS:
		board.FindFootprintByReference(part['ref']).SetValue(part['value'])
		if part.get('lcsc'):
			board.FindFootprintByReference(part['ref']).SetField('LCSC', part['lcsc'])
	name_unconnected(board)
	set_models(board)
	widen_neckdowns(board)
	for layer in (pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu):
		add_zone(board, 'GND', layer)
	board.Save(PCB)
	board = pcbnew.LoadBoard(PCB)
	pcbnew.ZONE_FILLER(board).Fill(board.Zones())
	board.Save(PCB)
	print('saved')


def main():
	'''Run the requested stage.'''

	stage = sys.argv[1] if len(sys.argv) > 1 else 'place'
	{'place': stage_place, 'import': stage_import, 'export': stage_export, 'finish': stage_finish}[stage]()



if __name__ == '__main__':
	main()
