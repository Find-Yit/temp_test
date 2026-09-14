#!/usr/bin/env bash
# 一键复现 · 03 对照实验 (τ 曲线 + τ∈{0.02,0.05,0.01} 提取[mv_filter 开] + M2–M6 + 汇总对照表 + 对比图)
# ------------------------------------------------------------------
# 复用同一份基线 coarse 模型 (来自 02), 只重跑提取; scratchpad runner 已正式化进 scripts/:
#   scripts/run_extract_repo.py (提取, import repo 改动版 coarse_mesh + mv_filter)
#   scripts/mv_tau_curve.py     (τ 剔除率曲线, filter-only)
#   scripts/eval/汇总对照表.py   (基线 vs 各 τ 横向对照表)
# 依赖 02 已产出基线 (coarse .pt / mesh / 评测)。SMOKE=1 读写 outputs/一键冒烟/*, 跳过阶段2e对比图。
# 用法: [SMOKE=1] bash scripts/一键复现/03_对照实验.sh
set -euo pipefail

ROOT="${SUGAR_ROOT:-/scratch/e1351071/zju_test_test}"
cd "$ROOT"
# shellcheck disable=SC1091
source "$ROOT/env.sh"
# shellcheck disable=SC1091
source "$ROOT/scripts/一键复现/_共用.sh"

mkdir -p logs "$MOD_OUT" "$MOD_EVAL"
LOG="$ROOT/logs/一键_03对照_${MODE}_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1
T0=$(date +%s)
log "==== 03 对照 [$MODE] 开始 (τ=$TAUS decim=$DECIM) 日志: $LOG ===="

# ---- 依赖检查: 基线产物 (来自 02) ----
COARSE_PT="$(coarse_pt_path)"
BASE_MESH="$(main_mesh_path "$MESH_DIR")"
if [ -z "$COARSE_PT" ] || [ -z "$BASE_MESH" ] || [ ! -f "$BASE_EVAL/几何指标_基线.json" ]; then
  log "!! 缺少基线产物 (coarse .pt / mesh / 评测)。请先运行: [SMOKE=$SMOKE] bash scripts/一键复现/02_基线.sh"
  exit 1
fi
log "基线 coarse=$COARSE_PT"
log "基线 mesh=$BASE_MESH"
FIRST_TAU="$(echo "$TAUS" | awk '{print $1}')"

# ---- (1) 三个 τ 全流程提取 (mv_filter 开) ----
for tau in $TAUS; do
  OUT="$MOD_OUT/改动_τ${tau}"
  mkdir -p "$OUT"
  log "[1] τ=$tau 提取 (mv_filter 开) -> $OUT"
  bash "$TIMER" "提取mesh_τ${tau}" "$OUT" --gpu 0 --interval 5 -- \
    python "$ROOT/scripts/run_extract_repo.py" -s "$SCENE" -c "$GS_DIR" -i "$GS_ITERS" \
      -m "$COARSE_PT" -l 0.3 -d "$DECIM" -o "$OUT" \
      --mv_filter True --mv_tau "$tau" --mv_min_consistent 2 --mv_max_conflict 1 \
      --mv_n_ref_cams 30 --mv_n_votes 0 --mv_seed 0 --seed 0 --eval True
  log "[1] τ=$tau 剔除率: $(python3 -c "import json;print(json.load(open('$OUT/剔点统计.json'))[0]['剔除率'])" 2>/dev/null || echo '?')"
done

# ---- (2) τ 剔除率曲线 (filter-only; 复用某次提取的 表面点_剔点前.ply, 保证 explorer==extraction) ----
SURF_PLY="$MOD_OUT/改动_τ${FIRST_TAU}/表面点_剔点前.ply"
log "[2] τ 曲线 (filter-only) 源点云=$SURF_PLY -> $MOD_OUT/τ曲线"
python "$ROOT/scripts/mv_tau_curve.py" -s "$SCENE" -c "$GS_DIR" -i "$GS_ITERS" \
  -m "$COARSE_PT" --surface_points_ply "$SURF_PLY" \
  --taus 0.005,0.01,0.02,0.05,0.10,0.20 -l 0.3 \
  --mv_min_consistent 2 --mv_max_conflict 1 --mv_n_ref_cams 30 --mv_n_votes 0 --mv_seed 0 \
  -o "$MOD_OUT/τ曲线" --gpu 0

# ---- (3) 各 τ 评测 M2–M6 (与基线同参数; M1 与基线相同因 coarse 未变, 跳过) ----
for tau in $TAUS; do
  OUT="$MOD_OUT/改动_τ${tau}"
  MESH_TAU="$(main_mesh_path "$OUT")"
  [ -n "$MESH_TAU" ] || { log "[3] !! τ=$tau 未找到 mesh"; exit 1; }
  log "[3] τ=$tau 评测 M2–M6 -> $MOD_EVAL"
  python "$ROOT/scripts/eval/run_all_eval.py" --tag "改动_τ${tau}" \
    --source_path "$SCENE" --gs_output "$GS_DIR" --iteration "$GS_ITERS" \
    --mesh "$MESH_TAU" \
    --ref_a "$GS_DIR/point_cloud/iteration_$GS_ITERS/point_cloud.ply" \
    --ref_b_colmap "$COLMAP" --cameras_json "$GS_DIR/cameras.json" \
    --timing_json "$OUT" \
    --out_dir "$MOD_EVAL" --metrics M2,M3,M4,M5,M6 \
    --n_sample "$N_SAMPLE" --save_masks --self_intersect_timeout "$SELF_INT"
done

# ---- (4) 汇总对照表 (基线 + 三 τ) ----
log "[4] 汇总对照表 -> $MOD_EVAL/汇总对照表.{json,csv,txt}"
python "$ROOT/scripts/eval/汇总对照表.py" \
  --base_eval_dir "$BASE_EVAL" --base_tag 基线 \
  --base_extract_timing "$BASE_TIMING/计时_提取mesh.json" \
  --mod_eval_dir "$MOD_EVAL" --mod_root "$MOD_OUT" \
  --mod_tags 改动_τ0.01,改动_τ0.02,改动_τ0.05 \
  --out_dir "$MOD_EVAL"

# ---- (5) 对比图 (阶段2e; 仅 FULL, 该脚本对正式产物路径硬编码) ----
if [ "$SMOKE" = "1" ]; then
  log "[5] SMOKE 跳过阶段2e对比图 (其路径为正式产物硬编码; SMOKE 仅验证 τ曲线/提取/评测/汇总 连通)"
else
  log "[5] 阶段2e 对比图 -> 考核提交/可视化/对比图"
  python "$ROOT/scripts/eval/阶段2e_对比图.py"
fi

log "==== 03 对照 [$MODE] 完成, 耗时 $(( $(date +%s) - T0 ))s ===="
log "关键产物: $MOD_EVAL/汇总对照表.txt ; $MOD_OUT/τ曲线/剔除率曲线.txt"
