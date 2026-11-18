#!/usr/bin/env python3
# DIY Omi PCB - post-autoroute fixups: grid A* for leftover connections, GND stitching vias - acidvegas

import heapq
import os
import re
import subprocess
import sys

try:
	import pcbnew
except ImportError:
	raise ImportError('missing pcbnew (run with the system python that ships with KiCad)')


from build_pcb import KEEP_H


OX, OY = 100.0, 100.0
STEP   = 0.05  # grid step (mm)
TRACK  = 0.1   # track width (mm)
CLEAR  = 0.1   # copper clearance (mm)
KEEP_Y = KEEP_H  # antenna keepout depth (mm)


def mm(v: float) -> int:
	'''mm to internal units.'''

	return pcbnew.FromMM(v)


def obstacles(board: 'pcbnew.BOARD', layer: int, net: str) -> list:
	'''Copper shapes on a layer that belong to other nets.'''

	shapes = []
	for t in board.GetTracks():
		if t.GetNetname() != net and t.IsOnLayer(layer):
			shapes.append(t.GetEffectiveShape(layer))
	for fp in board.GetFootprints():
		for p in fp.Pads():
			if p.GetNetname() != net and p.IsOnLayer(layer):
				shapes.append(p.GetEffectiveShape(layer))
			if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) and p.GetNetname() != net:
				shapes.append(p.GetEffectiveHoleShape())
	return shapes


def blocked(shapes: list, x: float, y: float, r: float) -> bool:
	'''True if a circle of radius r (mm) at board (x, y) hits any shape with clearance.'''

	pt = pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))
	c = mm(r + CLEAR + 0.02)
	return any(s.Collide(pt, c) for s in shapes)


def astar(board: 'pcbnew.BOARD', layer: int, net: str, start: tuple, box: tuple) -> list:
	'''Route from start to any existing copper of net on layer, inside box (x1, y1, x2, y2).'''

	shapes = obstacles(board, layer, net)
	goal = [t.GetEffectiveShape(layer) for t in board.GetTracks() if t.GetNetname() == net and t.IsOnLayer(layer)]
	x1, y1, x2, y2 = box
	nx, ny = int((x2 - x1) / STEP), int((y2 - y1) / STEP)
	free, done = {}, {}

	def ok(i: int, j: int) -> bool:
		if (i, j) not in free:
			x, y = x1 + i * STEP, y1 + j * STEP
			free[(i, j)] = 0 <= i <= nx and 0 <= j <= ny and y > KEEP_Y + 0.3 and not blocked(shapes, x, y, TRACK / 2)
		return free[(i, j)]

	def at_goal(i: int, j: int) -> bool:
		p = pcbnew.VECTOR2I(mm(OX + x1 + i * STEP), mm(OY + y1 + j * STEP))
		return any(g.Collide(p, 0) for g in goal)

	si, sj = round((start[0] - x1) / STEP), round((start[1] - y1) / STEP)
	heap = [(0, 0, si, sj, None)]
	parent = {}
	while heap:
		f, g, i, j, par = heapq.heappop(heap)
		if (i, j) in done:
			continue
		done[(i, j)] = True
		parent[(i, j)] = par
		if at_goal(i, j):
			path = []
			node = (i, j)
			while node:
				path.append((x1 + node[0] * STEP, y1 + node[1] * STEP))
				node = parent[node]
			return path[::-1]
		for di, dj, cost in ((1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)):
			ni, nj = i + di, j + dj
			if (ni, nj) not in done and ok(ni, nj):
				heapq.heappush(heap, (g + cost, g + cost, ni, nj, (i, j)))
	return []


def simplify(path: list) -> list:
	'''Drop collinear points.'''

	out = [path[0]]
	for a, b in zip(path[1:], path[2:] + [None]):
		if b is None:
			out.append(a)
			continue
		d1 = (round((a[0] - out[-1][0]) / STEP), round((a[1] - out[-1][1]) / STEP))
		d2 = (round((b[0] - a[0]) / STEP), round((b[1] - a[1]) / STEP))
		n1 = (d1[0] // max(1, abs(d1[0])) if d1[0] else 0, d1[1] // max(1, abs(d1[1])) if d1[1] else 0)
		n2 = (d2[0] // max(1, abs(d2[0])) if d2[0] else 0, d2[1] // max(1, abs(d2[1])) if d2[1] else 0)
		if n1 != n2:
			out.append(a)
	return out


def add_track_path(board: 'pcbnew.BOARD', path: list, layer: int, net: str):
	'''Lay a polyline of tracks.'''

	ni = board.FindNet(net)
	for a, b in zip(path, path[1:]):
		t = pcbnew.PCB_TRACK(board)
		t.SetStart(pcbnew.VECTOR2I(mm(OX + a[0]), mm(OY + a[1])))
		t.SetEnd(pcbnew.VECTOR2I(mm(OX + b[0]), mm(OY + b[1])))
		t.SetWidth(mm(TRACK))
		t.SetLayer(layer)
		t.SetNet(ni)
		board.Add(t)


def add_via(board: 'pcbnew.BOARD', x: float, y: float, net: str):
	'''0.4/0.2 via at board coords (skipped when a same-net via already sits within 0.45 mm).'''

	p = pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))
	if any(t.GetClass() == 'PCB_VIA' and t.GetNetname() == net and (t.GetPosition() - p).EuclideanNorm() < mm(0.45) for t in board.GetTracks()):
		return
	v = pcbnew.PCB_VIA(board)
	v.SetPosition(pcbnew.VECTOR2I(mm(OX + x), mm(OY + y)))
	v.SetWidth(mm(0.4))
	v.SetDrill(mm(0.2))
	v.SetNet(board.FindNet(net))
	board.Add(v)


def route_pad(board: 'pcbnew.BOARD', ref: str, pad_num: str, layer: int, box: tuple) -> bool:
	'''Drop a via in an SMD pad and A*-route it on an inner layer to the rest of its net.'''

	pad = next(p for p in board.FindFootprintByReference(ref).Pads() if p.GetNumber() == pad_num)
	x, y = pcbnew.ToMM(pad.GetPosition().x) - OX, pcbnew.ToMM(pad.GetPosition().y) - OY
	net = pad.GetNetname()
	path = astar(board, layer, net, (x, y), box)
	if not path:
		print(f'no path for {ref}.{pad_num} ({net})')
		return False
	add_via(board, x, y, net)
	add_track_path(board, simplify(path), layer, net)
	print(f'routed {ref}.{pad_num} ({net}) on {board.GetLayerName(layer)}: {len(path)} steps')
	return True


def goal_shapes(board: 'pcbnew.BOARD', net: str, start: tuple, start_layer: int, layers: list) -> dict:
	'''Per-layer shapes of net copper NOT already connected to the item at start (tracks, vias and pads).'''

	items = [t for t in board.GetTracks() if t.GetNetname() == net]
	items += [p for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetname() == net]
	cu = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu]
	sp = pcbnew.VECTOR2I(mm(OX + start[0]), mm(OY + start[1]))
	seed = [i for i in items if i.IsOnLayer(start_layer) and i.GetEffectiveShape(start_layer).Collide(sp, 0)]
	cluster = set(id(i) for i in seed)
	todo = list(seed)
	while todo:
		a = todo.pop()
		for b in items:
			if id(b) in cluster:
				continue
			for l in cu:
				if a.IsOnLayer(l) and b.IsOnLayer(l) and a.GetEffectiveShape(l).Collide(b.GetEffectiveShape(l), 0):
					cluster.add(id(b))
					todo.append(b)
					break
	return {l: [i.GetEffectiveShape(l) for i in items if id(i) not in cluster and i.IsOnLayer(l)] for l in layers}


def astar3d(board: 'pcbnew.BOARD', net: str, start: tuple, start_layer: int, box: tuple, step: float = 0.1, goal: dict = None) -> list:
	'''Multi-layer grid A* (F, In2, In3, B) from start to any copper of net; returns [(x, y, layer)].'''

	layers = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.B_Cu]
	shapes = {l: obstacles(board, l, net) for l in layers}
	planes = {l: obstacles(board, l, net) for l in (pcbnew.In1_Cu, pcbnew.In4_Cu)}
	goal = goal or goal_shapes(board, net, start, start_layer, layers)
	x1, y1, x2, y2 = box
	cache, vcache = {}, {}

	def xy(i, j):
		return x1 + i * step, y1 + j * step

	def ok(i, j, li):
		k = (i, j, li)
		if k not in cache:
			x, y = xy(i, j)
			cache[k] = x1 <= x <= x2 and y1 <= y <= y2 and y > KEEP_Y + 0.3 and not blocked(shapes[layers[li]], x, y, TRACK / 2)
		return cache[k]

	def via_ok(i, j):
		if (i, j) not in vcache:
			x, y = xy(i, j)
			vcache[(i, j)] = all(not blocked(s, x, y, 0.2) for s in list(shapes.values()) + list(planes.values()))
		return vcache[(i, j)]

	def at_goal(i, j, li):
		x, y = xy(i, j)
		p = pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))
		return any(g.Collide(p, 0) for g in goal[layers[li]])

	s = (round((start[0] - x1) / step), round((start[1] - y1) / step), layers.index(start_layer))
	heap = [(0, s, None)]
	parent = {}
	while heap:
		g, node, par = heapq.heappop(heap)
		if node in parent:
			continue
		parent[node] = par
		i, j, li = node
		if par is not None and at_goal(i, j, li):
			out = []
			while node:
				x, y = xy(node[0], node[1])
				out.append((x, y, layers[node[2]]))
				node = parent[node]
			return out[::-1]
		for di, dj, c in ((1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)):
			n = (i + di, j + dj, li)
			if n not in parent and ok(*n):
				heapq.heappush(heap, (g + c, n, node))
		if via_ok(i, j):
			for lj in range(len(layers)):
				if lj != li and ok(i, j, lj):
					n = (i, j, lj)
					if n not in parent:
						heapq.heappush(heap, (g + 12, n, node))
	return []


def lay_path3d(board: 'pcbnew.BOARD', path: list, net: str):
	'''Turn a 3D grid path into tracks (runs of 2+ points per layer) and one via per layer-change spot.'''

	runs = [[path[0]]]
	vias = []
	for p in path[1:]:
		if p[2] != runs[-1][-1][2]:
			if (p[0], p[1]) not in vias:
				vias.append((p[0], p[1]))
			runs.append([p])
		else:
			runs[-1].append(p)
	for run in runs:
		if len(run) > 1:
			add_track_path(board, simplify([(q[0], q[1]) for q in run]), run[0][2], net)
	for x, y in vias:
		add_via(board, x, y, net)


def stitch(board: 'pcbnew.BOARD', pitch: float = 1.2) -> int:
	'''GND stitching vias wherever a via fits clear of every other net and every pad.'''

	all_layers = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu]
	per_layer = {l: obstacles(board, l, 'GND') for l in all_layers}
	pads = [p.GetEffectiveShape(pcbnew.F_Cu) for fp in board.GetFootprints() for p in fp.Pads() if p.IsOnLayer(pcbnew.F_Cu)]
	pads += [p.GetEffectiveShape(pcbnew.B_Cu) for fp in board.GetFootprints() for p in fp.Pads() if p.IsOnLayer(pcbnew.B_Cu)]
	vias = [t for t in board.GetTracks() if t.GetClass() == 'PCB_VIA']
	holes = [p.GetEffectiveHoleShape() for fp in board.GetFootprints() for p in fp.Pads() if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)]
	outline = pcbnew.SHAPE_POLY_SET()
	board.GetBoardPolygonOutlines(outline)
	bb = outline.BBox()
	count = 0
	y = KEEP_Y + 0.8
	while y < pcbnew.ToMM(bb.GetBottom()) - OY:
		x = pcbnew.ToMM(bb.GetLeft()) - OX
		while x < pcbnew.ToMM(bb.GetRight()) - OX:
			p = pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))
			inside = outline.Contains(p) and not outline.Outline(0).PointOnEdge(p, mm(0.6))
			near_via = any((v.GetPosition() - p).EuclideanNorm() < mm(0.6) for v in vias)
			if inside and not near_via and not any(h.Collide(p, mm(0.45)) for h in holes) and not any(blocked(per_layer[l], x, y, 0.2) for l in all_layers) and not any(s.Collide(p, mm(0.3)) for s in pads):
				add_via(board, x, y, 'GND')
				vias = [t for t in board.GetTracks() if t.GetClass() == 'PCB_VIA']
				count += 1
			x += pitch
		y += pitch
	return count


def gnd_route(board: 'pcbnew.BOARD', pad: 'pcbnew.PAD') -> bool:
	'''Multi-layer A* from a stranded GND pad to the nearest GND via or through pad (both reach the planes).'''

	layers = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.B_Cu]
	targets = [t for t in board.GetTracks() if t.GetClass() == 'PCB_VIA' and t.GetNetname() == 'GND']
	targets += [p for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetname() == 'GND' and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
	goal = {l: [i.GetEffectiveShape(l) for i in targets] for l in layers}
	x, y = pcbnew.ToMM(pad.GetPosition().x) - OX, pcbnew.ToMM(pad.GetPosition().y) - OY
	path = astar3d(board, 'GND', (x, y), pcbnew.F_Cu, (x - 4, y - 4, x + 4, y + 4), goal=goal)
	print('gnd route from', pad.GetParentFootprint().GetReference(), pad.GetNumber(), 'path', len(path))
	if path:
		lay_path3d(board, path, 'GND')
		return True
	return False


def island_vias(board: 'pcbnew.BOARD') -> int:
	'''Drop a GND via into every filled GND pour island that has no via in it.'''

	all_layers = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu]
	per_layer = {l: obstacles(board, l, 'GND') for l in all_layers}
	pads = [p.GetEffectiveShape(l) for fp in board.GetFootprints() for p in fp.Pads() for l in (pcbnew.F_Cu, pcbnew.B_Cu) if p.IsOnLayer(l) and p.GetNetname() != 'GND']
	added = 0
	for z in board.Zones():
		if z.GetIsRuleArea() or z.GetNetname() != 'GND':
			continue
		layer = z.GetLayer()
		fill = z.GetFilledPolysList(layer)
		for k in range(fill.OutlineCount()):
			poly = pcbnew.SHAPE_POLY_SET()
			poly.AddOutline(fill.Outline(k))
			vias = [t for t in board.GetTracks() if t.GetClass() == 'PCB_VIA' and t.GetNetname() == 'GND']
			gnd_pth = [p for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetname() == 'GND' and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
			if any(poly.Contains(v.GetPosition()) for v in vias) or any(poly.Contains(p.GetPosition()) for p in gnd_pth):
				continue
			bb = poly.BBox()
			done = False
			yy = bb.GetTop()
			while yy < bb.GetBottom() and not done:
				xx = bb.GetLeft()
				while xx < bb.GetRight() and not done:
					p = pcbnew.VECTOR2I(xx, yy)
					x, y = pcbnew.ToMM(xx) - OX, pcbnew.ToMM(yy) - OY
					if poly.Contains(p) and poly.Outline(0).PointInside(p, mm(0.25)) and not any(blocked(per_layer[l], x, y, 0.2) for l in all_layers) and not any(s.Collide(p, mm(0.3)) for s in pads):
						add_via(board, x, y, 'GND')
						added += 1
						done = True
					xx += mm(0.05)
				yy += mm(0.05)
			if not done:
				print('no via spot for island on', board.GetLayerName(layer), 'at', round(pcbnew.ToMM(bb.Centre().x) - OX, 2), round(pcbnew.ToMM(bb.Centre().y) - OY, 2))
				for fp in board.GetFootprints():
					for pad in fp.Pads():
						if pad.GetNetname() == 'GND' and pad.IsOnLayer(layer) and poly.Contains(pad.GetPosition()):
							if gnd_escape(board, fp.GetReference(), pad.GetNumber()) or gnd_route(board, pad):
								added += 1
								done = True
								break
					if done:
						break
	return added


def gnd_escape(board: 'pcbnew.BOARD', ref: str, num: str) -> bool:
	'''Connect a stranded GND pad with a short F.Cu track to the nearest spot a via fits.'''

	pad = next(p for p in board.FindFootprintByReference(ref).Pads() if p.GetNumber() == num)
	sx, sy = pcbnew.ToMM(pad.GetPosition().x) - OX, pcbnew.ToMM(pad.GetPosition().y) - OY
	all_layers = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu]
	per_layer = {l: obstacles(board, l, 'GND') for l in all_layers}
	front = per_layer[pcbnew.F_Cu]
	pads = [p.GetEffectiveShape(pcbnew.F_Cu) for fp in board.GetFootprints() for p in fp.Pads() if p.IsOnLayer(pcbnew.F_Cu) and p != pad]
	step = 0.05
	seen = {(0, 0): None}
	q = [(0, 0)]
	while q:
		nq = []
		for i, j in q:
			x, y = sx + i * step, sy + j * step
			p = pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))
			if (i or j) and not any(blocked(per_layer[l], x, y, 0.2) for l in all_layers) and not any(s.Collide(p, mm(0.25)) for s in pads):
				path = []
				node = (i, j)
				while node is not None:
					path.append((sx + node[0] * step, sy + node[1] * step))
					node = seen[node]
				add_track_path(board, simplify(path[::-1]), pcbnew.F_Cu, 'GND')
				add_via(board, x, y, 'GND')
				print(f'gnd escape {ref}.{num} -> via at {x:.2f},{y:.2f}')
				return True
			for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
				n = (i + di, j + dj)
				if n in seen or abs(n[0]) > 30 or abs(n[1]) > 30:
					continue
				nx, ny = sx + n[0] * step, sy + n[1] * step
				if blocked(front, nx, ny, TRACK / 2):
					continue
				seen[n] = (i, j)
				nq.append(n)
		q = nq
	shape = pad.GetEffectiveShape(pcbnew.F_Cu)
	for dx in [i * 0.05 for i in range(-6, 7)]:
		for dy in [i * 0.05 for i in range(-6, 7)]:
			x, y = sx + dx, sy + dy
			if shape.Collide(pcbnew.VECTOR2I(mm(OX + x), mm(OY + y)), 0) and not any(blocked(per_layer[l], x, y, 0.2) for l in all_layers if l != pcbnew.F_Cu) and not blocked(front, x, y, 0.2):
				add_via(board, x, y, 'GND')
				print(f'gnd escape {ref}.{num} -> via in pad at {x:.2f},{y:.2f}')
				return True
	print(f'no gnd escape for {ref}.{num}')
	return False


def drc_unconnected(fname: str) -> list:
	'''Run DRC; for each unconnected pair return both ends as (x, y, layer, net), zones skipped.'''

	rpt = fname + '.drc'
	subprocess.run(['kicad-cli', 'pcb', 'drc', '--severity-error', '-o', rpt, fname], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
	text = open(rpt).read()
	os.remove(rpt)
	pairs = []
	for block in text.split('[unconnected_items]')[1:]:
		ends = []
		for m in re.finditer(r'@\(([-0-9.]+) mm, ([-0-9.]+) mm\): (Pad|Track|Via|Zone)[^\[]*\[([^\]]+)\][^\n]*? on ([A-Za-z0-9.]+)', block.split('\n[')[0]):
			if m.group(3) == 'Zone':
				continue
			layer = 'F.Cu' if m.group(3) == 'Via' else m.group(5)
			ends.append((m.group(3) != 'Pad', float(m.group(1)) - OX, float(m.group(2)) - OY, layer, m.group(4)))
		if ends:
			pairs.append([e[1:] for e in sorted(ends, key=lambda e: e[0])])  # start from pads (clean, centred) before track ends
	return pairs


def drop_bad_gnd(fname: str) -> int:
	'''Run DRC and delete GND tracks/vias flagged for clearance or keepout areas (the pours and planes carry GND anyway).'''

	rpt = fname + '.drc'
	subprocess.run(['kicad-cli', 'pcb', 'drc', '--severity-error', '-o', rpt, fname], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
	text = open(rpt).read()
	os.remove(rpt)
	spots = []
	for kind in ('[clearance]', '[items_not_allowed]'):
		for block in text.split(kind)[1:]:
			spots += [(float(m.group(1)), float(m.group(2))) for m in re.finditer(r'@\(([-0-9.]+) mm, ([-0-9.]+) mm\): (?:Track|Via) \[GND\]', block.split('\n[')[0])]
	board = pcbnew.LoadBoard(fname)
	bad = []
	for t in board.GetTracks():
		if t.GetNetname() != 'GND':
			continue
		pts = [t.GetPosition()] if t.GetClass() == 'PCB_VIA' else [t.GetStart(), t.GetEnd()]
		if any(abs(pcbnew.ToMM(p.x) - x) < 0.02 and abs(pcbnew.ToMM(p.y) - y) < 0.02 for p in pts for x, y in spots):
			bad.append(t)
	for t in bad:
		board.Remove(t)
	pcbnew.SaveBoard(fname, board)
	return len(bad)


def refill(fname: str):
	'''Reload, refill every zone and save.'''

	board = pcbnew.LoadBoard(fname)
	pcbnew.ZONE_FILLER(board).Fill(board.Zones())
	pcbnew.SaveBoard(fname, board)


def auto(fname: str):
	'''Route leftover unconnected pads, stitch GND, fill islands, refill.'''

	refill(fname)
	board = pcbnew.LoadBoard(fname)
	print('island vias (pre)', island_vias(board))
	pcbnew.SaveBoard(fname, board)
	board = pcbnew.LoadBoard(fname)
	outline = pcbnew.SHAPE_POLY_SET()
	board.GetBoardPolygonOutlines(outline)
	bb = outline.BBox()
	box = (pcbnew.ToMM(bb.GetLeft()) - OX + 0.3, KEEP_Y + 0.3, pcbnew.ToMM(bb.GetRight()) - OX - 0.3, pcbnew.ToMM(bb.GetBottom()) - OY - 0.3)
	for ends in drc_unconnected(fname):
		for x, y, lname, net in ends:
			layer = board.GetLayerID(lname)
			if net == 'GND':
				break
			path = astar3d(board, net, (x, y), layer, box)
			if not path:
				fine = (max(box[0], x - 5), max(box[1], y - 5), min(box[2], x + 5), min(box[3], y + 5))
				path = astar3d(board, net, (x, y), layer, fine, step=0.05)
			print(net, 'from', round(x, 2), round(y, 2), lname, 'path', len(path))
			if path:
				lay_path3d(board, path, net)
				break
	print('stitch vias', stitch(board))
	pcbnew.SaveBoard(fname, board)
	refill(fname)
	board = pcbnew.LoadBoard(fname)
	print('island vias', island_vias(board))
	pcbnew.SaveBoard(fname, board)
	refill(fname)
	print('bad gnd removed', drop_bad_gnd(fname))
	refill(fname)


def main():
	'''Apply fixups to the given board file in place.'''

	fname = sys.argv[1]
	board = pcbnew.LoadBoard(fname)
	if len(sys.argv) > 2 and sys.argv[2] == 'auto':
		auto(fname)
		return
	if len(sys.argv) > 2 and sys.argv[2] == 'islands':
		print('island vias', island_vias(board))
		pcbnew.SaveBoard(fname, board)
		return
	for ref, num, box in [('MK1', '4', (0.3, 4.3, 16.0, 13.0))]:
		pad = next(p for p in board.FindFootprintByReference(ref).Pads() if p.GetNumber() == num)
		x, y = pcbnew.ToMM(pad.GetPosition().x) - OX, pcbnew.ToMM(pad.GetPosition().y) - OY
		path = astar3d(board, pad.GetNetname(), (x, y), pcbnew.F_Cu, box)
		print(ref, num, 'path', len(path), 'vias', sum(1 for a, b in zip(path, path[1:]) if a[2] != b[2]))
		if path:
			lay_path3d(board, path, pad.GetNetname())
	gnd_escape(board, 'C7', '2')
	print('stitch vias', stitch(board))
	pcbnew.SaveBoard(fname, board)



if __name__ == '__main__':
	main()
