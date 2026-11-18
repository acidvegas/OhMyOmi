// DIY Omi PCB - 3D view of the board inside a concept pendant case, with the magnetic charging dock - acidvegas

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

// stack heights (mm). The board is flipped: its blank face sits at y = 0 against the case front and every part hangs below it.
const BOARD_TOP = 0.8;
const PARTS_LOW = -BOARD_TOP - 3.25;  // lowest point of the parts: the USB-C socket, 3.25 mm below the component face
const FRONT_IN  = 0.05;
const FRONT_OUT = FRONT_IN + 1.0;
const BATT_TOP  = PARTS_LOW - 0.3;
const BATT_H    = 5.6;   // 1654 cell is 5.4 mm, plus tab
const BACK_IN   = BATT_TOP - BATT_H - 0.3;
const BACK_OUT  = BACK_IN - 1.0;
const WALL      = 1.2;
const GAP       = 0.25;                          // board-to-wall clearance
const BATTERY   = { r: 8, z: 4.0 };              // GRP1654M1 / LIR1654 round cell, 16 mm, centre 4 mm below the board centre
const MOTOR     = { r: 2.5, h: 2.5 };            // 5 x 2.5 mm coin vibration motor
const PORT      = { w: 9.6, h: 3.8 };             // case wall opening for the USB-C socket (8.94 x 3.16 body)
const QUARTER   = { d: 24.26, h: 1.75 };
const OMI       = { d: 25.5, h: 15 };              // Omi pendant, from its docs

const wrap     = document.getElementById('view');
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.localClippingEnabled = true;
wrap.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
const sun = new THREE.DirectionalLight(0xffffff, 1.4);
sun.position.set(30, 60, 40);
scene.add(sun);
const under = new THREE.DirectionalLight(0xffffff, 2.6);  // lights the bottom of the board
under.position.set(-20, -60, 30);
scene.add(under, new THREE.HemisphereLight(0xffffff, 0xdfe6f0, 0.9));

const camera   = new THREE.PerspectiveCamera(32, 1, 0.1, 1000);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

const cut      = new THREE.Plane(new THREE.Vector3(-1, 0, 0), 0);   // cutaway keeps the x < 0 half
const groups   = { board: new THREE.Group(), front: new THREE.Group(), back: new THREE.Group(), wall: new THREE.Group(), battery: new THREE.Group(), motor: new THREE.Group(), refs: new THREE.Group() };
Object.values(groups).forEach(g => scene.add(g));
let ledGlow    = null;
let mode       = 'case';

function resize() {
	const w = wrap.clientWidth, h = wrap.clientHeight;
	renderer.setSize(w, h);
	camera.aspect = w / h;
	camera.updateProjectionMatrix();
}

// board-shaped outline (circle with a flat top at z = flatZ) as a Shape in (x, -z); extrudes upward after rotateX
function outlinePoints(r, flatZ, segments = 160) {
	const pts = [];
	const half = Math.sqrt(Math.max(r * r - flatZ * flatZ, 0));
	for (let i = 0; i < segments; i++) {
		const a = (i / segments) * Math.PI * 2;
		let x = r * Math.cos(a), z = r * Math.sin(a);
		if (z < flatZ) { z = flatZ; x = Math.max(-half, Math.min(half, x)); }
		pts.push(new THREE.Vector2(x, -z));
	}
	return pts;
}

function rect(cx, cz, w, d) {
	return [new THREE.Vector2(cx - w / 2, -cz - d / 2), new THREE.Vector2(cx + w / 2, -cz - d / 2), new THREE.Vector2(cx + w / 2, -cz + d / 2), new THREE.Vector2(cx - w / 2, -cz + d / 2)];
}

function extrude(shape, y0, y1, mat) {
	const g = new THREE.ExtrudeGeometry(shape, { depth: y1 - y0, bevelEnabled: false, curveSegments: 48 });
	g.rotateX(-Math.PI / 2);
	const m = new THREE.Mesh(g, mat);
	m.position.y = y0;
	return m;
}

function caseMaterial(color) {
	const m = new THREE.MeshStandardMaterial({ color, roughness: 0.75, metalness: 0, side: THREE.DoubleSide });
	return m;
}

function label(group, text, x, y, z) {
	const c = document.createElement('canvas');
	const g = c.getContext('2d');
	g.font = '600 40px system-ui, sans-serif';
	c.width = Math.ceil(g.measureText(text).width) + 36;
	c.height = 64;
	g.font = '600 40px system-ui, sans-serif';
	g.fillStyle = 'rgba(15,17,21,0.88)';
	g.fillRect(0, 0, c.width, c.height);
	g.fillStyle = '#e6e8ec';
	g.fillText(text, 18, 45);
	const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c), depthTest: false, sizeAttenuation: false }));
	s.scale.set(c.width / 64 * 0.024, 0.024, 1);
	s.position.set(x, y, z);
	s.renderOrder = 10;
	s.userData.label = true;
	group.add(s);
}

function box(b) {
	const [w, d, h, z0, dx, dy, colour, opacity] = b;
	const metal = colour === '#c7c9d1' || colour === '#cccccc';
	const m = new THREE.MeshStandardMaterial({ color: colour, roughness: 0.55, metalness: metal ? 0.8 : 0.1, transparent: opacity < 1, opacity });
	const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m);
	mesh.position.set(dx, z0 + h / 2, dy);
	return mesh;
}

function batteryTexture() {
	const c = document.createElement('canvas');
	c.width = 512; c.height = 512;
	const g = c.getContext('2d');
	g.fillStyle = '#c9ccd2'; g.fillRect(0, 0, 512, 512);
	g.fillStyle = '#2a5db0'; g.beginPath(); g.arc(256, 256, 200, 0, Math.PI * 2); g.fill();
	g.fillStyle = '#ffffff'; g.textAlign = 'center'; g.font = '700 64px system-ui'; g.fillText('LIR1654', 256, 230);
	g.font = '500 44px system-ui'; g.fillText('3.7V 150mAh', 256, 300);
	return new THREE.CanvasTexture(c);
}

async function load() {
	const [gltf, info] = await Promise.all([
		new GLTFLoader().loadAsync('/renders/omi.glb'),
		fetch('/renders/parts3d.json').then(r => r.json()),
	]);
	const [cx, cy] = info.center;
	const R = info.radius, FLAT = -info.flat;

	// board: KiCad GLB is metres, Y up, KiCad Y -> +Z; recentre on the board circle
	const board = gltf.scene;
	board.scale.setScalar(1000);
	board.position.set(-cx, 0, -cy);
	groups.board.add(board);
	groups.board.rotation.z = Math.PI;  // flip: component side faces in, blank side faces out (also mirrors x, as seen from the front)
	for (const p of info.parts) {
		const g = new THREE.Group();
		for (const b of p.bodies) {
			const mesh = box(b);
			g.add(mesh);
			if (p.ref === 'LED1' && b[7] < 1) ledGlow = mesh;
		}
		g.position.set(p.x - cx, p.back ? 0 : BOARD_TOP, p.y - cy);
		if (p.back) g.scale.y = -1;  // parts on the back hang below the board
		g.rotation.y = THREE.MathUtils.degToRad(p.rot);
		groups.board.add(g);
	}
	// board coords -> scene coords after the flip (x mirrors, the component face is at y = -BOARD_TOP)
	const led = info.parts.find(p => p.ref === 'LED1');
	const ledX = -(led.x - cx), ledZ = led.y - cy;
	const ports = info.mic_ports.map(p => ({ x: -(p.x - cx), z: p.y - cy }));
	const usbX = -(info.usb.x - cx), usbZ = info.usb.y - cy, portY = -BOARD_TOP - 1.58;
	const motorX = -(info.motor.x - cx), motorZ = info.motor.y - cy;
	const ro = R + GAP + WALL, fo = FLAT - GAP - WALL, ri = R + GAP, fi = FLAT - GAP;

	// case wall ring
	const wallMat = caseMaterial('#ece8e0');
	const ring = new THREE.Shape(outlinePoints(ro, fo));
	ring.holes.push(new THREE.Path(outlinePoints(ri, fi)));
	groups.wall.add(extrude(ring, BACK_IN, portY - PORT.h / 2, wallMat), extrude(ring.clone(), portY + PORT.h / 2, FRONT_IN, wallMat));
	// beside the port the wall is full height: an arc of ring split at the opening
	const half = Math.asin(PORT.w / 2 / ro), mid = Math.atan2(usbZ, usbX);
	const arc = new THREE.Shape();
	arc.absarc(0, 0, ro, -mid + half, -mid - half + Math.PI * 2, false);
	arc.absarc(0, 0, ri, -mid - half + Math.PI * 2, -mid + half, true);
	groups.wall.add(extrude(arc, portY - PORT.h / 2, portY + PORT.h / 2, wallMat));

	// front cover sits right on the blank face: a hole over each mic sound port and over the LED slot
	const front = new THREE.Shape(outlinePoints(ro, fo));
	for (const p of ports) { const h = new THREE.Path(); h.absarc(p.x, -p.z, 0.55, 0, Math.PI * 2, true); front.holes.push(h); }
	const ledHole = new THREE.Path(); ledHole.absarc(ledX, -ledZ, 0.9, 0, Math.PI * 2, true);
	front.holes.push(ledHole);
	groups.front.add(extrude(front, FRONT_IN, FRONT_OUT, caseMaterial('#ece8e0')));

	// back cover
	groups.back.add(extrude(new THREE.Shape(outlinePoints(ro, fo)), BACK_OUT, BACK_IN, caseMaterial('#ece8e0')));

	// round cell, kept clear of the charging pocket
	const batZ = BATTERY.z;
	const pouch = new THREE.Mesh(new THREE.CylinderGeometry(BATTERY.r, BATTERY.r, BATT_H, 64), new THREE.MeshStandardMaterial({ color: '#cfd2d8', metalness: 0.8, roughness: 0.3 }));
	pouch.position.set(0, BATT_TOP - BATT_H / 2, batZ);
	const sticker = new THREE.Mesh(new THREE.CircleGeometry(BATTERY.r - 0.3, 64), new THREE.MeshStandardMaterial({ map: batteryTexture(), roughness: 0.8 }));
	sticker.rotation.x = Math.PI / 2;
	sticker.position.set(0, BATT_TOP - BATT_H - 0.01, batZ);
	groups.battery.add(pouch, sticker);

	// coin vibration motor under the M+ / M- pads
	const motor = new THREE.Mesh(new THREE.CylinderGeometry(MOTOR.r, MOTOR.r, MOTOR.h, 32), new THREE.MeshStandardMaterial({ color: '#b9bcc2', metalness: 0.85, roughness: 0.35 }));
	motor.position.set(motorX, BATT_TOP - MOTOR.h / 2, motorZ);
	groups.motor.add(motor);
	label(groups.motor, 'Vibration motor', motorX - 9, BATT_TOP - 2, motorZ);

	// size references beside the pendant: an Omi (plain puck at its published size) and a US quarter
	const omi = new THREE.Mesh(new THREE.CylinderGeometry(OMI.d / 2, OMI.d / 2, OMI.h, 64), new THREE.MeshStandardMaterial({ color: '#8d9099', roughness: 0.5 }));
	omi.position.set(-(ro + OMI.d / 2 + 6), BACK_OUT + OMI.h / 2, 0);
	const coin = new THREE.Mesh(new THREE.CylinderGeometry(QUARTER.d / 2, QUARTER.d / 2, QUARTER.h, 96), new THREE.MeshStandardMaterial({ color: '#c9ccd2', metalness: 0.9, roughness: 0.35 }));
	coin.position.set(ro + QUARTER.d / 2 + 6, BACK_OUT + QUARTER.h / 2, 0);
	groups.refs.add(omi, coin);
	const thick = (FRONT_OUT - BACK_OUT).toFixed(1), dia = (2 * ro).toFixed(1);
	label(groups.refs, `Omi: Ø${OMI.d} × ${OMI.h} mm`, omi.position.x, BACK_OUT + OMI.h + 3, 0);
	label(groups.refs, `This build: Ø${dia} × ${thick} mm`, 0, FRONT_OUT + 3, 0);
	label(groups.refs, `US quarter: Ø${QUARTER.d} mm`, coin.position.x, BACK_OUT + QUARTER.h + 3, 0);

	label(groups.front, 'Mic holes (2)', ports[1].x + 4, FRONT_OUT + 1, ports[1].z);
	label(groups.front, 'LED (shines through the board)', ledX, FRONT_OUT + 1, ledZ - 7);
	label(groups.battery, 'Battery: 150 mAh round cell', 13, BATT_TOP - 3, batZ);
	label(groups.wall, 'USB-C port', usbX + 12, portY, usbZ + 2);
	cut.constant = 0;  // cutaway slices down the middle, through the USB-C socket

	document.querySelectorAll('[data-mode]').forEach(b => b.addEventListener('click', () => setMode(b.dataset.mode)));
	setMode(new URLSearchParams(location.search).get('mode') || 'case');
	document.getElementById('status').hidden = true;
}

function setMode(m) {
	mode = m;
	document.querySelectorAll('[data-mode]').forEach(b => b.classList.toggle('on', b.dataset.mode === m));
	const ex = m === 'exploded' ? 1 : 0;
	const showCase = m !== 'board';
	groups.wall.visible = groups.front.visible = groups.back.visible = showCase;
	groups.battery.visible = groups.motor.visible = m !== 'board';
	groups.front.position.y = ex * 8;
	groups.back.position.y = -ex * 14;
	groups.battery.position.y = groups.motor.position.y = -ex * 6;
	groups.refs.visible = document.getElementById('sizes').checked && m === 'case';
	const planes = m === 'cutaway' ? [cut] : [];
	const labels = document.getElementById('labels').checked && m !== 'board' && m !== 'case';
	scene.traverse(o => {
		if (o.userData.label) { o.visible = o.parent === groups.refs ? true : labels; return; }
		if (!o.material) return;
		for (const mat of [].concat(o.material)) { mat.clippingPlanes = planes; mat.side = THREE.DoubleSide; mat.needsUpdate = true; }  // double-sided so cut solids don't look hollow
	});
	const views = { case: groups.refs.visible ? [0, 58, 118] : [24, 50, 38], cutaway: [46, 16, 14], exploded: [52, 14, 72], board: [26, 34, 36] };
	camera.position.set(...views[m]);
	controls.target.set(0, m === 'exploded' ? -7 : -1, 0);
	controls.update();
}

document.getElementById('sizes').addEventListener('change', () => setMode(mode));
document.getElementById('labels').addEventListener('change', () => setMode(mode));
document.getElementById('led').addEventListener('change', e => {
	if (!ledGlow) return;
	for (const mat of [ledGlow.material]) {
		mat.emissive = new THREE.Color(e.target.checked ? '#2fd0ff' : '#000000');
		mat.emissiveIntensity = e.target.checked ? 3 : 0;
	}
});
document.querySelectorAll('[data-view]').forEach(b => b.addEventListener('click', () => {
	const v = { top: [0, 55, 0.01], bottom: [0, -55, -0.01] }[b.dataset.view];
	camera.position.set(...v);
	controls.target.set(0, 0, 0);
	controls.update();
}));

window.addEventListener('resize', resize);
resize();
renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene, camera); });
load().catch(err => { const s = document.getElementById('status'); s.hidden = false; s.textContent = 'Failed to load model: ' + err; });
