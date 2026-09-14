#!/usr/bin/env bash
# 阶段 1b: 对基线完整跑 M1–M6, 汇总, 出可视化, 复制到 考核提交/。
# 用法: cd /scratch/e1351071/zju_test_test && source env.sh && bash scripts/eval/跑基线评测.sh
set -u
ROOT=/scratch/e1351071/zju_test_test
EVAL=$ROOT/scripts/eval
SRC=$ROOT/data/tandt/truck
GS=$ROOT/outputs/基线_truck/3dgs_7k
ITER=7000
CPT=$ROOT/outputs/基线_truck/coarse/sugarcoarse_3Dgs7000_densityestim02_sdfnorm02/15000.pt
REFA=$GS/point_cloud/iteration_$ITER/point_cloud.ply
CAMJSON=$GS/cameras.json
COLMAP=$SRC/sparse/0
OUT=$ROOT/outputs/基线_truck/评测
TIMING=$ROOT/outputs/基线_truck/计时
TAG=基线
PY=python

# 自动选主网格 (排除 表面采样点云_*), 优先 decim 最大的
MESH=$(ls -S $ROOT/outputs/基线_truck/mesh/sugarmesh_*.ply 2>/dev/null | grep -v 表面采样点云 | head -1)
if [ -z "$MESH" ]; then echo "错误: 未找到 sugarmesh_*.ply"; exit 1; fi
echo "[基线评测] 主网格: $MESH"
mkdir -p "$OUT"

# --- run_all: M1–M6 ---
$PY $EVAL/run_all_eval.py --tag "$TAG" \
  --source_path "$SRC" --gs_output "$GS" --iteration $ITER \
  --mesh "$MESH" --coarse_pt "$CPT" \
  --ref_a "$REFA" --ref_b_colmap "$COLMAP" --cameras_json "$CAMJSON" \
  --timing_json "$TIMING" \
  --out_dir "$OUT" --metrics M1,M2,M3,M4,M5,M6 \
  --n_sample 1000000 --lpips 1 --save_renders --save_masks \
  --log "$OUT/评测日志.txt"

# --- M6 渲染对比拼图 (从 M1 保存的渲染图取 2 个测试视角) ---
RDIR="$OUT/渲染图_$TAG"
if [ -d "$RDIR" ]; then
  idx=0
  for gt in $(ls "$RDIR"/GT_*.png 2>/dev/null | head -2); do
    base=$(basename "$gt"); suffix=${base#GT_}       # 003_000024.png
    gs="$RDIR/3DGS_$suffix"; su="$RDIR/coarseSuGaR_$suffix"
    [ -f "$gs" ] && [ -f "$su" ] && \
      $PY $EVAL/m6_visualize.py --mode montage --gt_img "$gt" --gs_img "$gs" --sugar_img "$su" \
        --out_dir "$OUT/图" --tag "${TAG}_视角${suffix%.png}" --log "$OUT/评测日志.txt"
    idx=$((idx+1))
  done
fi

# --- 汇总重命名为 评测汇总_基线 ---
[ -f "$OUT/汇总_全部指标.json" ] && cp -f "$OUT/汇总_全部指标.json" "$OUT/评测汇总_基线.json"
[ -f "$OUT/汇总_对比表.txt" ] && cp -f "$OUT/汇总_对比表.txt" "$OUT/评测汇总_基线.txt"

# --- 复制到 考核提交/ (复制, 不移动) ---
SUB=$ROOT/考核提交
mkdir -p "$SUB/指标" "$SUB/可视化"
cp -f "$OUT"/*.json "$OUT"/*.txt "$OUT"/*.csv "$SUB/指标/" 2>/dev/null
cp -rf "$OUT/图/." "$SUB/可视化/" 2>/dev/null
[ -d "$OUT/覆盖掩码_$TAG" ] && cp -rf "$OUT/覆盖掩码_$TAG" "$SUB/可视化/" 2>/dev/null

echo "[基线评测] 完成。产物: $OUT ; 已复制到 $SUB/{指标,可视化}"
ls "$OUT"
