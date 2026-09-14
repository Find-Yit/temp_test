#!/usr/bin/env bash
cd /scratch/e1351071/zju_test_test
LOG=logs/基线_coarse_15k.log
# wait until at least 4 "computed in" progress lines OR error OR 12 min
n=0
until [ "$(grep -ac 'computed in' $LOG 2>/dev/null)" -ge 4 ] || grep -qaE 'Traceback|Error' $LOG 2>/dev/null || [ $n -ge 144 ]; do sleep 5; n=$((n+1)); done
echo "[rate] waited=$((n*5))s"
if grep -qaE 'Traceback|Error' $LOG 2>/dev/null; then echo "[rate] ERROR DETECTED"; grep -aE 'Traceback|Error' $LOG | head; exit 1; fi
echo "[rate] first progress lines (iter / computed-in-minutes):"
grep -aE 'computed in' $LOG | head -6
