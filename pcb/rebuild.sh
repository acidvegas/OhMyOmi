#!/bin/bash
# from the routed raw board: finish (restore pads, pours), auto-fix leftovers, DRC
cd /home/acidvegas/dev/projects/embedded/omi/pcb
cp omi_routed_raw.kicad_pcb omi.kicad_pcb
python3 build_pcb.py finish 2>&1 | grep -v Debug
python3 fixup.py omi.kicad_pcb auto 2>&1 | grep -v Debug
kicad-cli pcb drc --severity-all --schematic-parity -o drc_all.rpt omi.kicad_pcb >/dev/null 2>&1
grep -E '^\[' drc_all.rpt | sed 's/;.*//; s/(.*//' | sort | uniq -c | sort -rn; grep -E 'Found' drc_all.rpt
