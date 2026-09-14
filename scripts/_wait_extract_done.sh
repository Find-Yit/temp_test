#!/usr/bin/env bash
cd /scratch/e1351071/zju_test_test
ET=outputs/基线_truck/计时/计时_提取mesh.txt
ELOG=logs/基线_extract.log
n=0
until [ -f "$ET" ] || grep -qaE 'Traceback|RuntimeError' "$ELOG" 2>/dev/null || [ $n -ge 600 ]; do sleep 10; n=$((n+1)); done
echo "[extract-done] waited=$((n*10))s"
echo "===== coarse timing ====="; cat outputs/基线_truck/计时/计时_coarse_dn_15k.txt 2>/dev/null
echo "===== extract timing ====="; cat "$ET" 2>/dev/null
echo "===== extract error? ====="; grep -aE 'Traceback|RuntimeError' "$ELOG" 2>/dev/null | head -3
echo "===== mesh dir ====="; ls -lh outputs/基线_truck/mesh/ 2>/dev/null
echo "===== extract log tail ====="; grep -aE 'Mesh saved|SURFPTS|Final point cloud|Foreground mesh:|Background mesh:' "$ELOG" 2>/dev/null | tail -8
