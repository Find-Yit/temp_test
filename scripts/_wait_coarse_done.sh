#!/usr/bin/env bash
cd /scratch/e1351071/zju_test_test
CT=outputs/基线_truck/计时/计时_coarse_dn_15k.txt
LOG=logs/基线_coarse_15k.log
n=0
until [ -f "$CT" ] || grep -qaE 'Traceback|Error:' "$LOG" 2>/dev/null || [ $n -ge 720 ]; do sleep 5; n=$((n+1)); done
echo "[coarse-done] waited=$((n*5))s"
if grep -qaE 'Traceback|Error:' "$LOG" 2>/dev/null; then echo "[coarse-done] ERROR:"; grep -aE 'Traceback|Error:' "$LOG" | head; fi
echo "===== coarse timing ====="; cat "$CT" 2>/dev/null
echo "===== post-9000 interval times (dn+sdf active) ====="
grep -aE 'computed in' "$LOG" | sed -E 's/.*\[(.*)\] computed in ([0-9.]+) minutes.*/iter=\1 min=\2/' | awk -F'[= ]' '$3>=9000' | head -40
echo "===== NaN check ====="; grep -aci nan "$LOG"
echo "===== .pt saved ====="; ls -lh outputs/基线_truck/coarse/sugarcoarse_3Dgs7000_densityestim02_sdfnorm02/*.pt 2>/dev/null
