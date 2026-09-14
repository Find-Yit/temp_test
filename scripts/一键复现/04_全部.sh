#!/usr/bin/env bash
# 一键复现 · 04 全部 (依次 02 基线 → 03 对照, 再把产物复制到 考核提交/)
# ------------------------------------------------------------------
# 复制(不移动、不删除)到 SUB_OUT: 网格/ 指标/ 可视化/ 日志/。全部中文命名。
# SMOKE=1 时全程走小迭代, SUB_OUT=outputs/一键冒烟/考核提交。
# 用法: [SMOKE=1] bash scripts/一键复现/04_全部.sh
set -euo pipefail

ROOT="${SUGAR_ROOT:-/scratch/e1351071/zju_test_test}"
cd "$ROOT"
# shellcheck disable=SC1091
source "$ROOT/env.sh"
# shellcheck disable=SC1091
source "$ROOT/scripts/一键复现/_共用.sh"

mkdir -p logs
LOG="$ROOT/logs/一键_04全部_${MODE}_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1
T0=$(date +%s)
log "==== 04 全部 [$MODE] 开始 日志: $LOG ===="

# ---- 依次运行 02 / 03 (透传 SMOKE) ----
log "[A] 运行 02 基线 ..."
SMOKE="$SMOKE" bash "$ROOT/scripts/一键复现/02_基线.sh"
log "[B] 运行 03 对照 ..."
SMOKE="$SMOKE" bash "$ROOT/scripts/一键复现/03_对照实验.sh"

# ---- 复制到 考核提交 ----
log "[C] 复制产物 -> $SUB_OUT"
mkdir -p "$SUB_OUT/网格" "$SUB_OUT/指标" "$SUB_OUT/可视化" "$SUB_OUT/日志"

# 网格
BASE_MESH="$(main_mesh_path "$MESH_DIR")"
[ -n "$BASE_MESH" ] && cp -f "$BASE_MESH" "$SUB_OUT/网格/基线_truck_coarse网格.ply"
for f in "$MESH_DIR"/表面采样点云_全部*.ply; do [ -f "$f" ] && cp -f "$f" "$SUB_OUT/网格/基线_truck_表面采样点云_全部.ply"; done
for f in "$MESH_DIR"/表面采样点云_前景*.ply; do [ -f "$f" ] && cp -f "$f" "$SUB_OUT/网格/基线_truck_表面采样点云_前景.ply"; done
for tau in $TAUS; do
  m="$(main_mesh_path "$MOD_OUT/改动_τ${tau}")"
  [ -n "$m" ] && cp -f "$m" "$SUB_OUT/网格/改动_truck_τ${tau}_网格.ply"
done

# 指标
cp -f "$BASE_EVAL"/*.json "$BASE_EVAL"/*.txt "$BASE_EVAL"/*.csv "$SUB_OUT/指标/" 2>/dev/null || true
cp -f "$MOD_EVAL"/*.json "$MOD_EVAL"/*.txt "$MOD_EVAL"/*.csv "$SUB_OUT/指标/" 2>/dev/null || true
cp -f "$MOD_OUT"/τ曲线/*.json "$MOD_OUT"/τ曲线/*.txt "$SUB_OUT/指标/" 2>/dev/null || true
cp -f "$BASE_OUT"/基线汇总.* "$SUB_OUT/指标/" 2>/dev/null || true
for tau in $TAUS; do
  cp -f "$MOD_OUT/改动_τ${tau}"/剔点统计.* "$SUB_OUT/指标/剔点统计_改动_τ${tau}."* 2>/dev/null || true
done

# 可视化
cp -rf "$BASE_EVAL/图/." "$SUB_OUT/可视化/" 2>/dev/null || true
cp -rf "$MOD_EVAL/图/." "$SUB_OUT/可视化/" 2>/dev/null || true
[ -d "$MOD_EVAL/图_统一色标" ] && cp -rf "$MOD_EVAL/图_统一色标" "$SUB_OUT/可视化/" 2>/dev/null || true
cp -f "$MOD_OUT"/τ曲线/*.png "$SUB_OUT/可视化/" 2>/dev/null || true
for d in "$BASE_EVAL"/覆盖掩码_* "$MOD_EVAL"/覆盖掩码_*; do [ -d "$d" ] && cp -rf "$d" "$SUB_OUT/可视化/" 2>/dev/null || true; done
# 阶段2e 对比图 (仅 FULL, 2e 直接写入真实 考核提交/可视化/对比图)
if [ "$SMOKE" != "1" ] && [ -d "$ROOT/考核提交/可视化/对比图" ]; then
  cp -rf "$ROOT/考核提交/可视化/对比图" "$SUB_OUT/可视化/" 2>/dev/null || true
fi

# 日志
cp -f "$ROOT"/notes/RUNLOG_*.md "$ROOT"/notes/ENV.md "$ROOT"/notes/COMMITS.md "$SUB_OUT/日志/" 2>/dev/null || true

N=$(find "$SUB_OUT" -type f | wc -l)
log "[C] 复制完成: $SUB_OUT (共 $N 文件)"
log "==== 04 全部 [$MODE] 完成, 耗时 $(( $(date +%s) - T0 ))s ===="
