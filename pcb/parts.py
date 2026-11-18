#!/usr/bin/env python3
# DIY Omi PCB - part list, netlist and custom footprints - acidvegas

# Each part: ref, value, symbol (omi:<name> generated or Device:<name> copied), footprint, LCSC, side, pins {pin: net|None}
# Net None = no connect

PARTS = [
	# --- radio module ---
	dict(ref='U1', value='ISP1807-LR-RS', sym='omi:ISP1807', fp='omi:ISP1807', lcsc='C5264268', pins={
		'1': 'GND', '7': 'GND', '14': 'GND', '16': 'GND', '18': 'GND', '21': 'GND', '23': 'GND', '24': 'GND', '25': 'GND', '31': 'GND',
		'26': '+3V3', '12': 'VBUS', '8': 'USB_DP', '10': 'USB_DN', '28': 'SWDIO', '30': 'SWDCLK',
		'20': 'RF', '22': 'RF',
		'36': 'PDM_CLK', '34': 'PDM_DAT',
		'32': 'SD_SCK', '6': 'SD_MOSI', '35': 'SD_MISO', '33': 'SD_CS',
		'37': 'I2C_SDA', '39': 'I2C_SCL', '40': 'IMU_INT1',
		'48': 'VBAT_SENSE', '38': 'MOTOR_GATE',
		'29': 'LED_R', '27': 'LED_G', '5': 'LED_B',  # high-drive capable pins (P0.13/P0.17/P0.14)
		'42': 'CHG_STAT', '44': 'SD_EN_N',  # static signals on low-frequency pins (P0.31/P0.30)
	}),

	# --- USB-C charging/data at the bottom edge, 5.1k CC pull-downs so any USB-C charger supplies 5V ---
	dict(ref='J1', value='TYPE-C-31-M-12', sym='omi:USB_C_16P', fp='Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12', lcsc='C165948', pins={
		'A1': 'GND', 'B1': 'GND', 'A12': 'GND', 'B12': 'GND', 'S1': 'GND',
		'A4': 'VBUS', 'B4': 'VBUS', 'A9': 'VBUS', 'B9': 'VBUS',
		'A5': 'CC1', 'B5': 'CC2', 'A6': 'USB_DP', 'B6': 'USB_DP', 'A7': 'USB_DN', 'B7': 'USB_DN', 'A8': None, 'B8': None,
	}),
	dict(ref='R1', value='5.1k', sym='Device:R', fp='Resistor_SMD:R_0402_1005Metric', lcsc='C25905', pins={'1': 'CC1', '2': 'GND'}),
	dict(ref='R2', value='5.1k', sym='Device:R', fp='Resistor_SMD:R_0402_1005Metric', lcsc='C25905', pins={'1': 'CC2', '2': 'GND'}),
	# ESD clamp on D+/D-/VBUS (flow-through: pins 1/6 = I/O1, 3/4 = I/O2)
	dict(ref='U6', value='USBLC6-2P6', sym='omi:USBLC6', fp='Package_TO_SOT_SMD:SOT-666', lcsc='C15999', pins={'1': 'USB_DP', '6': 'USB_DP', '3': 'USB_DN', '4': 'USB_DN', '2': 'GND', '5': 'VBUS'}),

	# --- charger: MCP73832 (open-drain STAT), I = 1000V / RPROG -> 15k = 66mA (~0.5C for a 120-150mAh CP1654 cell) ---
	dict(ref='U4', value='MCP73832T-2ACI/OT', sym='omi:MCP73832', fp='Package_TO_SOT_SMD:SOT-23-5', lcsc='C38066', pins={'1': 'CHG_STAT', '2': 'GND', '3': 'VBAT', '4': 'VBUS', '5': 'CHG_PROG'}),
	dict(ref='R17', value='100k', sym='Device:R', fp='Resistor_SMD:R_0402_1005Metric', lcsc='C25741', pins={'1': '+3V3', '2': 'CHG_STAT'}),
	dict(ref='R3', value='15k', sym='Device:R', fp='Resistor_SMD:R_0402_1005Metric', lcsc='C25756', pins={'1': 'CHG_PROG', '2': 'GND'}),
	dict(ref='C1', value='10uF', sym='Device:C', fp='Capacitor_SMD:C_0603_1608Metric', lcsc='C19702', pins={'1': 'VBUS', '2': 'GND'}),
	dict(ref='C2', value='10uF', sym='Device:C', fp='Capacitor_SMD:C_0402_1005Metric', lcsc='C15525', pins={'1': 'VBAT', '2': 'GND'}),

	# --- 3.3V LDO ---
	dict(ref='U5', value='TPS7A0233PDQNR', sym='omi:TPS7A02', fp='Package_SON:Texas_X2SON-4_1x1mm_P0.65mm', lcsc='C2860046', pins={'1': '+3V3', '2': 'GND', '3': 'VBAT', '4': 'VBAT', '5': 'GND'}),
	dict(ref='C3', value='1uF', sym='Device:C', fp='Capacitor_SMD:C_0402_1005Metric', lcsc='C52923', pins={'1': 'VBAT', '2': 'GND'}),
	dict(ref='C4', value='1uF', sym='Device:C', fp='Capacitor_SMD:C_0402_1005Metric', lcsc='C52923', pins={'1': '+3V3', '2': 'GND'}),
	dict(ref='C5', value='4.7uF', sym='Device:C', fp='Capacitor_SMD:C_0402_1005Metric', lcsc='C23733', pins={'1': '+3V3', '2': 'GND'}),

	# --- battery sense divider (VBAT/2 on P0.28 = AIN4, sample with TACQ = 40 us) ---
	dict(ref='R4', value='1M', sym='Device:R', fp='Resistor_SMD:R_0402_1005Metric', lcsc='C26083', pins={'1': 'VBAT', '2': 'VBAT_SENSE'}),
	dict(ref='R5', value='1M', sym='Device:R', fp='Resistor_SMD:R_0402_1005Metric', lcsc='C26083', pins={'1': 'VBAT_SENSE', '2': 'GND'}),
	dict(ref='C10', value='100nF', sym='Device:C', fp='Capacitor_SMD:C_0402_1005Metric', lcsc='C1525', pins={'1': 'VBAT_SENSE', '2': 'GND'}),

	# --- SD NAND 4 Gbit / 512 MB (SPI mode), on its own switched rail so standby drops ~50 uA -> 0 ---
	dict(ref='U2', value='MKDV4GCL-ABB', sym='omi:SDNAND', fp='omi:SDNAND_LGA8_8x6', lcsc='C7500178', pins={'1': 'SD_DAT2', '2': 'SD_CS', '3': 'SD_SCK', '4': 'GND', '5': 'SD_MOSI', '6': 'SD_MISO', '7': 'SD_DAT1', '8': 'SD_3V3'}),
	dict(ref='Q2', value='DMG1013T-7', sym='omi:PMOS_GSD', fp='Package_TO_SOT_SMD:SOT-523', lcsc='C96676', pins={'1': 'SD_EN_N', '2': '+3V3', '3': 'SD_3V3'}),
	dict(ref='R18', value='100k', sym='Device:R', fp='Resistor_SMD:R_0402_1005Metric', lcsc='C25741', pins={'1': '+3V3', '2': 'SD_EN_N'}),
	dict(ref='C6', value='2.2uF', sym='Device:C', fp='Capacitor_SMD:C_0402_1005Metric', lcsc='C12530', pins={'1': 'SD_3V3', '2': 'GND'}),
	dict(ref='R6', value='47k', sym='Device:R', fp='Resistor_SMD:R_0402_1005Metric', lcsc='C25792', pins={'1': 'SD_3V3', '2': 'SD_CS'}),
	dict(ref='R7', value='47k', sym='Device:R', fp='Resistor_SMD:R_0402_1005Metric', lcsc='C25792', pins={'1': 'SD_3V3', '2': 'SD_MOSI'}),
	dict(ref='R8', value='47k', sym='Device:R', fp='Resistor_SMD:R_0402_1005Metric', lcsc='C25792', pins={'1': 'SD_3V3', '2': 'SD_MISO'}),
	dict(ref='R9', value='47k', sym='Device:R', fp='Resistor_SMD:R_0402_1005Metric', lcsc='C25792', pins={'1': 'SD_3V3', '2': 'SD_DAT1'}),
	dict(ref='R10', value='47k', sym='Device:R', fp='Resistor_SMD:R_0402_1005Metric', lcsc='C25792', pins={'1': 'SD_3V3', '2': 'SD_DAT2'}),

	# --- accelerometer for motion wake (I2C, CS and SA0 tied high so their internal pull-ups draw nothing, addr 0x19) ---
	dict(ref='U3', value='LIS2DW12TR', sym='omi:LIS2DW12', fp='Package_LGA:LGA-12_2x2mm_P0.5mm', lcsc='C189624', pins={
		'1': 'I2C_SCL', '2': '+3V3', '3': '+3V3', '4': 'I2C_SDA', '5': None, '6': 'GND', '7': 'GND', '8': 'GND', '9': '+3V3', '10': '+3V3', '11': None, '12': 'IMU_INT1'}),
	dict(ref='C7', value='100nF', sym='Device:C', fp='Capacitor_SMD:C_0402_1005Metric', lcsc='C1525', pins={'1': '+3V3', '2': 'GND'}),
	dict(ref='C8', value='100nF', sym='Device:C', fp='Capacitor_SMD:C_0402_1005Metric', lcsc='C1525', pins={'1': '+3V3', '2': 'GND'}),
	dict(ref='R11', value='10k', sym='Device:R', fp='Resistor_SMD:R_0402_1005Metric', lcsc='C25744', pins={'1': '+3V3', '2': 'I2C_SDA'}),
	dict(ref='R12', value='10k', sym='Device:R', fp='Resistor_SMD:R_0402_1005Metric', lcsc='C25744', pins={'1': '+3V3', '2': 'I2C_SCL'}),

	# --- 2x bottom-port PDM mics on the component side, listening through 0.8 mm board holes straight out the front face; shared clock/data, LR selects the edge ---
	dict(ref='MK1', value='IM73D122V01', sym='omi:IM73D122', fp='omi:IM73D122_LGA5_4x3', lcsc='C5563886', pins={'1': 'PDM_DAT', '2': '+3V3', '3': 'PDM_CLK', '4': 'GND', '5': 'GND'}),
	dict(ref='MK2', value='IM73D122V01', sym='omi:IM73D122', fp='omi:IM73D122_LGA5_4x3', lcsc='C5563886', pins={'1': 'PDM_DAT', '2': '+3V3', '3': 'PDM_CLK', '4': '+3V3', '5': 'GND'}),
	dict(ref='C9', value='1uF', sym='Device:C', fp='Capacitor_SMD:C_0402_1005Metric', lcsc='C52923', pins={'1': '+3V3', '2': 'GND'}),
	dict(ref='C11', value='1uF', sym='Device:C', fp='Capacitor_SMD:C_0402_1005Metric', lcsc='C52923', pins={'1': '+3V3', '2': 'GND'}),

	# --- vibration motor driver (motor solders to M+ / M- pads) ---
	dict(ref='Q1', value='DMG1012T-7', sym='omi:NMOS_GSD', fp='Package_TO_SOT_SMD:SOT-523', lcsc='C20512', pins={'1': 'MOTOR_GATE', '2': 'GND', '3': 'MOTOR_N'}),
	dict(ref='D1', value='RB521S30T1G', sym='Device:D_Schottky', fp='Diode_SMD:D_SOD-523', lcsc='C145179', pins={'1': 'VBAT', '2': 'MOTOR_N'}),
	dict(ref='R13', value='100k', sym='Device:R', fp='Resistor_SMD:R_0402_1005Metric', lcsc='C25741', pins={'1': 'MOTOR_GATE', '2': 'GND'}),

	# --- RGB LED, reverse mount: sits on the inner side and shines out through a slot in the board (common anode on VBAT, GPIO sinks) ---
	dict(ref='LED1', value='MHT151RGBCT', sym='omi:LED_RGB_CA', fp='omi:LED_RGB_REV_1206', lcsc='C409782', pins={'1': 'VBAT', '2': 'LED_BK', '3': 'LED_GK', '4': 'LED_RK'}),
	dict(ref='R14', value='1k', sym='Device:R', fp='Resistor_SMD:R_0402_1005Metric', lcsc='C11702', pins={'1': 'LED_RK', '2': 'LED_R'}),
	dict(ref='R15', value='330', sym='Device:R', fp='Resistor_SMD:R_0402_1005Metric', lcsc='C25104', pins={'1': 'LED_GK', '2': 'LED_G'}),
	dict(ref='R16', value='330', sym='Device:R', fp='Resistor_SMD:R_0402_1005Metric', lcsc='C25104', pins={'1': 'LED_BK', '2': 'LED_B'}),

	# --- solder pads (not assembled): SWD test pads on the blank front face, battery and motor wire pads on the component side ---
	dict(ref='TP1', value='IO', sym='omi:PAD', fp='TestPoint:TestPoint_Pad_D1.0mm', lcsc=None, side='B', pins={'1': 'SWDIO'}),
	dict(ref='TP2', value='CK', sym='omi:PAD', fp='TestPoint:TestPoint_Pad_D1.0mm', lcsc=None, side='B', pins={'1': 'SWDCLK'}),
	dict(ref='TP3', value='3V', sym='omi:PAD', fp='TestPoint:TestPoint_Pad_D1.0mm', lcsc=None, side='B', pins={'1': '+3V3'}),
	dict(ref='TP4', value='G', sym='omi:PAD', fp='TestPoint:TestPoint_Pad_D1.0mm', lcsc=None, side='B', pins={'1': 'GND'}),
	dict(ref='BT1', value='B+', sym='omi:PAD', fp='TestPoint:TestPoint_Pad_1.0x1.0mm', lcsc=None, pins={'1': 'VBAT'}),
	dict(ref='BT2', value='B-', sym='omi:PAD', fp='TestPoint:TestPoint_Pad_1.0x1.0mm', lcsc=None, pins={'1': 'GND'}),
	dict(ref='M1', value='M+', sym='omi:PAD', fp='TestPoint:TestPoint_Pad_1.0x1.0mm', lcsc=None, pins={'1': 'VBAT'}),
	dict(ref='M2', value='M-', sym='omi:PAD', fp='TestPoint:TestPoint_Pad_1.0x1.0mm', lcsc=None, pins={'1': 'MOTOR_N'}),
]

# ISP1807 pad table in datasheet top-view coords (mm from top-left corner): num -> (x, y, w, h)
ISP_PADS = {}
_xs9 = [4 + k * 0.65 for k in range(-4, 5)]
_xs8 = [4 + (k + 0.5) * 0.65 for k in range(-4, 4)]
for _x, _n in zip(_xs9, [48, 46, 44, 42, 40, 38, 36, 34, 32]):
	ISP_PADS[_n] = (_x, 0.3125, 0.4, 0.375)
for _x, _n in zip(_xs8, [47, 45, 43, 41, 39, 37, 35, 33]):
	ISP_PADS[_n] = (_x, 0.9625, 0.4, 0.4)
for _x, _n in zip([0.95] + _xs8 + [7.05], [3, 56, 55, 54, 53, 52, 51, 50, 49, 29]):
	ISP_PADS[_n] = (_x, 1.725, 0.4, 0.4)
for _x, _n in zip([0.95] + _xs8 + [7.05], [5, 64, 63, 62, 61, 60, 59, 58, 57, 27]):
	ISP_PADS[_n] = (_x, 2.375, 0.4, 0.4)
for _x, _n in zip(_xs8, [9, 11, 13, 15, 17, 19, 21, 23]):
	ISP_PADS[_n] = (_x, 3.15, 0.4, 0.4)
for _x, _n in zip(_xs9, [8, 10, 12, 14, 16, 18, 20, 22, 24]):
	ISP_PADS[_n] = (_x, 3.8, 0.4, 0.4)
for _y, _l, _r in [(1.4, 2, 30), (2.05, 4, 28), (2.7, 6, 26), (4.55, 65, 78), (5.55, 66, 77), (6.55, 67, 76)]:
	ISP_PADS[_l] = (0.3125, _y, 0.375, 0.4)
	ISP_PADS[_r] = (7.6875, _y, 0.375, 0.4)
ISP_PADS[1]  = (0.5125, 0.5125, 0.775, 0.775)
ISP_PADS[31] = (7.4875, 0.5125, 0.775, 0.775)
ISP_PADS[7]  = (0.5125, 3.6, 0.775, 0.8)
ISP_PADS[25] = (7.4875, 3.6, 0.775, 0.8)
ISP_PADS[68] = (0.5125, 7.4875, 0.775, 0.775)
ISP_PADS[75] = (7.4875, 7.4875, 0.775, 0.775)
for _i, _n in enumerate(range(69, 75)):
	ISP_PADS[_n] = (1.5 + _i, 7.6875, 0.4, 0.375)

ISP_NAMES = {
	1: 'VSS', 2: 'P0.09', 3: 'P0.12', 4: 'P0.10', 5: 'P0.14', 6: 'P0.26', 7: 'VSS', 8: 'D+', 9: 'P0.16', 10: 'D-',
	11: 'P0.21', 12: 'VBUS', 13: 'P0.18_RST', 14: 'VSS', 15: 'P0.20', 16: 'VSS', 17: 'P0.22', 18: 'VSS', 19: 'P0.24', 20: 'OUT_ANT',
	21: 'VSS', 22: 'OUT_MOD', 23: 'VSS', 24: 'VSS', 25: 'VSS', 26: 'VCC', 27: 'P0.17', 28: 'SWDIO', 29: 'P0.13', 30: 'SWDCLK',
	31: 'VSS', 32: 'P0.08', 33: 'P0.07', 34: 'P0.06', 35: 'P0.04', 36: 'P0.05', 37: 'P0.15', 38: 'P0.03', 39: 'P0.27', 40: 'P0.02',
	41: 'P0.25', 42: 'P0.31', 43: 'P0.11', 44: 'P0.30', 45: 'P0.19', 46: 'P0.29', 47: 'P0.23', 48: 'P0.28', 49: 'P1.02', 50: 'P1.06',
	51: 'P1.15', 52: 'P1.14', 53: 'P1.13', 54: 'P1.05', 55: 'P1.08', 56: 'P1.09', 57: 'P1.00', 58: 'P1.03', 59: 'P1.12', 60: 'P1.10',
	61: 'P1.11', 62: 'P1.07', 63: 'P1.04', 64: 'P1.01',
}
for _n in range(65, 79):
	ISP_NAMES[_n] = 'NC'

# Generated symbol pin definitions: name -> list of (pin, label, side)
SYMBOLS = {
	'ISP1807': [(str(n), ISP_NAMES[n], 'L' if ISP_NAMES[n] in ('VSS', 'VCC', 'VBUS', 'D+', 'D-', 'SWDIO', 'SWDCLK', 'OUT_ANT', 'OUT_MOD', 'NC') else 'R') for n in range(1, 79)],
	'MCP73832':  [('4', 'VDD', 'L'), ('5', 'PROG', 'L'), ('2', 'VSS', 'L'), ('3', 'VBAT', 'R'), ('1', 'STAT', 'R')],
	'USBLC6':    [('5', 'VBUS', 'L'), ('2', 'GND', 'L'), ('1', 'I/O1', 'R'), ('6', 'I/O1', 'R'), ('3', 'I/O2', 'R'), ('4', 'I/O2', 'R')],
	'PMOS_GSD':  [('1', 'G', 'L'), ('2', 'S', 'R'), ('3', 'D', 'R')],
	'TPS7A02':   [('4', 'IN', 'L'), ('3', 'EN', 'L'), ('2', 'GND', 'L'), ('5', 'EP', 'L'), ('1', 'OUT', 'R')],
	'SDNAND':    [('8', 'VCC', 'L'), ('4', 'VSS', 'L'), ('2', 'CS/DAT3', 'R'), ('3', 'SCLK', 'R'), ('5', 'DI/CMD', 'R'), ('6', 'DO/DAT0', 'R'), ('7', 'DAT1', 'R'), ('1', 'DAT2', 'R')],
	'LIS2DW12':  [('9', 'VDD', 'L'), ('10', 'VDD_IO', 'L'), ('6', 'GND', 'L'), ('8', 'GND', 'L'), ('7', 'RES', 'L'), ('5', 'NC', 'L'), ('2', 'CS', 'R'), ('3', 'SDO/SA0', 'R'), ('1', 'SCL', 'R'), ('4', 'SDA', 'R'), ('12', 'INT1', 'R'), ('11', 'INT2', 'R')],
	'IM73D122':  [('2', 'VDD', 'L'), ('4', 'LR', 'L'), ('5', 'GND', 'L'), ('3', 'CLOCK', 'R'), ('1', 'DATA', 'R')],
	'NMOS_GSD':  [('1', 'G', 'L'), ('3', 'D', 'R'), ('2', 'S', 'R')],
	'LED_RGB_CA': [('1', 'A', 'L'), ('4', 'RK', 'R'), ('3', 'GK', 'R'), ('2', 'BK', 'R')],
	'PAD':       [('1', 'PAD', 'L')],
	'USB_C_16P': [('A4', 'VBUS', 'L'), ('B4', 'VBUS', 'L'), ('A9', 'VBUS', 'L'), ('B9', 'VBUS', 'L'), ('A5', 'CC1', 'L'), ('B5', 'CC2', 'L'), ('A1', 'GND', 'L'), ('B1', 'GND', 'L'), ('A12', 'GND', 'L'), ('B12', 'GND', 'L'), ('S1', 'SHIELD', 'L'),
	              ('A6', 'D+', 'R'), ('B6', 'D+', 'R'), ('A7', 'D-', 'R'), ('B7', 'D-', 'R'), ('A8', 'SBU1', 'R'), ('B8', 'SBU2', 'R')],
}

# every ISP1807 pad not listed above is left unconnected
for _n in range(1, 79):
	PARTS[0]['pins'].setdefault(str(_n), None)
