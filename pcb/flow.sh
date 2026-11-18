#!/bin/bash
# full route flow from omi_unrouted.kicad_pcb: autoroute, import, finish, auto-fix, DRC
cd /home/acidvegas/dev/projects/embedded/omi/pcb
T=/home/acidvegas/dev/projects/embedded/omi/tools
cp omi_unrouted.kicad_pcb omi.kicad_pcb
python3 build_pcb.py export 2>&1 | grep -v Debug
rm -f omi.ses
sudo unshare -n sudo -u acidvegas env HOME=$T/frhome $T/jre25/usr/lib/jvm/java-25-openjdk-amd64/bin/java -Djava.awt.headless=true -jar $T/freerouting-2.5.0.jar --gui.enabled=false -de omi.dsn -do omi.ses --router.autorouter.max_passes=${1:-12} --router.optimizer.enabled=false -is ${2:-sequential} -mt 6 > route.log 2>&1
grep -E 'pass #[0-9]+ ' route.log | grep -v Fanout | grep -oE 'pass #[0-9]+.*\(([0-9]+) unrouted' | awk '{print $2, $(NF-1)}' | tr -d '(' | tr '\n' ' '; echo
python3 build_pcb.py import 2>&1 | grep -v Debug
cp omi.kicad_pcb omi_routed_raw.kicad_pcb
python3 build_pcb.py finish 2>&1 | grep -v Debug
python3 -u fixup.py omi.kicad_pcb auto 2>&1 | grep -v Debug
kicad-cli pcb drc --severity-all --schematic-parity -o drc_all.rpt omi.kicad_pcb >/dev/null 2>&1
grep -E '^\[' drc_all.rpt | sed 's/;.*//; s/(.*//' | sort | uniq -c | sort -rn; grep -E 'Found' drc_all.rpt
