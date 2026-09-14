#!/usr/bin/env bash
# 一键复现 · 02 基线 (3DGS → coarse SuGaR → 提取[mv_filter 关] → M1–M6 评测)
# ------------------------------------------------------------------
# 复用 scripts/ 现有 wrapper (基线路径, import repo 原始逻辑副本, 不改 repo)。
# 计时/显存由 scripts/eval/计时运行.sh 记录。全链路 seed=0。
# SMOKE=1: 3DGS 500 / coarse num_iterations 7100 / decim 200000 / n_sample 200000 → outputs/一键冒烟/基线。
#   (poisson_depth 在 SuGaR 中硬编码 10, 非 CLI, 不改 repo 则 SMOKE 不改它; 见 _共用.sh 注释)
# 用法: [SMOKE=1] bash scripts/一键复现/02_基线.sh
set -euo pipefail

ROOT="${SUGAR_ROOT:-/scratch/e1351071/zju_test_test}"
cd "$ROOT"
# shellcheck disable=SC1091
source "$ROOT/env.sh"
# shellcheck disable=SC1091
source "$ROOT/scripts/一键复现/_共用.sh"

mkdir -p logs "$BASE_OUT" "$BASE_TIMING" "$BASE_EVAL"
LOG="$ROOT/logs/一键_02基线_${MODE}_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1
T0=$(date +%s)
log "==== 02 基线 [$MODE] 开始 (3DGS=$GS_ITERS coarse=$COARSE_ITERS decim=$DECIM) 日志: $LOG ===="
log "输出根: $BASE_OUT"

# ---- (1) 3DGS ----
log "[1] 3DGS 训练 $GS_ITERS it -> $GS_DIR"
bash "$TIMER" "训练3DGS_${GS_LABEL}" "$BASE_TIMING" --gpu 0 --interval 5 -- \
  python "$ROOT/repo/SuGaR/gaussian_splatting/train.py" -s "$SCENE" -m "$GS_DIR" \
    --iterations "$GS_ITERS" --save_iterations "$GS_ITERS" --test_iterations "$GS_ITERS" --eval --quiet
log "[1] 3DGS 完成: $GS_DIR/point_cloud/iteration_$GS_ITERS/point_cloud.ply"

# ---- (2) coarse SuGaR dn_consistency ----
log "[2] coarse dn_consistency num_iterations=$COARSE_ITERS -> $COARSE_DIR"
bash "$TIMER" "coarse_dn_${COARSE_LABEL}" "$BASE_TIMING" --gpu 0 --interval 5 -- \
  python "$ROOT/scripts/run_coarse_dn.py" -s "$SCENE" -c "$GS_DIR" -i "$GS_ITERS" \
    -o "$COARSE_DIR" --num_iterations "$COARSE_ITERS" --eval True
COARSE_PT="$(coarse_pt_path)"
[ -n "$COARSE_PT" ] || { log "[2] !! 未找到 coarse .pt"; exit 1; }
log "[2] coarse 完成: $COARSE_PT"

# ---- (3) 提取 mesh (mv_filter 关) + 表面采样点云 ----
log "[3] 提取 mesh (surface_level 0.3, decim $DECIM, mv_filter 关) -> $MESH_DIR"
bash "$TIMER" "提取mesh" "$BASE_TIMING" --gpu 0 --interval 5 -- \
  python "$ROOT/scripts/run_extract_mesh.py" -s "$SCENE" -c "$GS_DIR" -i "$GS_ITERS" \
    -m "$COARSE_PT" -l 0.3 -d "$DECIM" -o "$MESH_DIR" --surfpts_dir "$MESH_DIR" --eval True
MESH="$(main_mesh_path "$MESH_DIR")"
[ -n "$MESH" ] || { log "[3] !! 未找到基线 mesh"; exit 1; }
log "[3] 提取完成: $MESH"

# ---- (4) 评测 M1–M6 ----
log "[4] 评测 M1–M6 (n_sample=$N_SAMPLE) -> $BASE_EVAL"
python "$ROOT/scripts/eval/run_all_eval.py" --tag 基线 \
  --source_path "$SCENE" --gs_output "$GS_DIR" --iteration "$GS_ITERS" \
  --mesh "$MESH" --coarse_pt "$COARSE_PT" \
  --ref_a "$GS_DIR/point_cloud/iteration_$GS_ITERS/point_cloud.ply" \
  --ref_b_colmap "$COLMAP" --cameras_json "$GS_DIR/cameras.json" \
  --timing_json "$BASE_TIMING" \
  --out_dir "$BASE_EVAL" --metrics M1,M2,M3,M4,M5,M6 \
  --n_sample "$N_SAMPLE" --lpips 1 --save_renders --save_masks --self_intersect_timeout "$SELF_INT"
log "[4] 评测完成: $BASE_EVAL/汇总_对比表.txt"

log "==== 02 基线 [$MODE] 完成, 耗时 $(( $(date +%s) - T0 ))s ===="
log "关键产物: mesh=$MESH ; coarse=$COARSE_PT ; 评测=$BASE_EVAL"
