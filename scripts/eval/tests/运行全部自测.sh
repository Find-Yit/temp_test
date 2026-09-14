#!/usr/bin/env bash
# 运行 M1–M6 的全部合成数据单元自测。
# 用法: cd /scratch/e1351071/zju_test_test && source env.sh && bash scripts/eval/tests/运行全部自测.sh
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-python}"
rc=0
echo "########## test_m2_m3 (几何/拓扑, CPU) ##########"
"$PY" "$HERE/test_m2_m3.py" 2>&1 | grep -vE "^\[Open3D" | grep -E "PASS|FAIL|结果|ALL_" || rc=1
echo ""
echo "########## test_m5_m6 (效率/可视化, CPU) ##########"
"$PY" "$HERE/test_m5_m6.py" 2>&1 | grep -vE "^\[Open3D" | grep -E "PASS|FAIL|结果|ALL_" || rc=1
echo ""
echo "########## test_m1_m4 (渲染/覆盖, GPU) ##########"
"$PY" "$HERE/test_m1_m4.py" 2>&1 | grep -vE "^\[Open3D|Using original|Found image|Removing|Warning|Binding|Initial|Use min|[0-9]+%\|" | grep -E "PASS|FAIL|结果|ALL_" || rc=1
echo ""
if [ "$rc" = "0" ]; then echo "===== 全部自测 ALL_PASS ====="; else echo "===== 存在失败, 请检查 ====="; fi
exit "$rc"
