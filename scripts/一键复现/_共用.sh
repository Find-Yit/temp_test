#!/usr/bin/env bash
# 一键复现 · 共用配置与工具（被 02/03/04 source）。
# 提供: log()/ts() 时间戳日志; SMOKE 模式的迭代数与输出目录切换; 场景路径。
# 不单独执行。所有路径均为绝对路径(基于 SUGAR_ROOT)。

ROOT="${SUGAR_ROOT:-/scratch/e1351071/zju_test_test}"

ts()  { date "+%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(ts)] $*"; }

SMOKE="${SMOKE:-0}"
if [ "$SMOKE" = "1" ]; then
  MODE="SMOKE"
  GS_ITERS=500          # 3DGS 训练迭代
  COARSE_ITERS=7100     # coarse num_iterations (=真实约100步; 见 README §7 迭代计数语义)
  DECIM=200000          # decimation_target
  GS_SUBDIR="3dgs_500"; GS_LABEL="500"; COARSE_LABEL="7100"
  N_SAMPLE=200000       # 几何评测采样点数 (SMOKE 减小)
  SELF_INT=60           # 自交检测超时(s)
  BASE_OUT="$ROOT/outputs/一键冒烟/基线"
  MOD_OUT="$ROOT/outputs/一键冒烟/改动"
  SUB_OUT="$ROOT/outputs/一键冒烟/考核提交"
else
  MODE="FULL"
  GS_ITERS=7000
  COARSE_ITERS=15000
  DECIM=1000000
  GS_SUBDIR="3dgs_7k"; GS_LABEL="7k"; COARSE_LABEL="15k"
  N_SAMPLE=1000000
  SELF_INT=120
  BASE_OUT="$ROOT/outputs/基线_truck"
  MOD_OUT="$ROOT/outputs/改动_truck"
  SUB_OUT="$ROOT/考核提交"
fi

# 说明: SuGaR@7c10c4a 的 poisson_depth 硬编码为 10 (coarse_mesh.py, 非 CLI 参数),
#       无法在不改 repo 的前提下于 SMOKE 设为 7; SMOKE 通过 3DGS/coarse 小迭代 + 小 decimation 提速。

SCENE="$ROOT/data/tandt/truck"
COLMAP="$SCENE/sparse/0"
GS_DIR="$BASE_OUT/$GS_SUBDIR"          # 3DGS 输出目录
COARSE_DIR="$BASE_OUT/coarse"          # coarse 输出根
MESH_DIR="$BASE_OUT/mesh"              # 基线 mesh 输出
BASE_EVAL="$BASE_OUT/评测"
BASE_TIMING="$BASE_OUT/计时"
MOD_EVAL="$MOD_OUT/评测"
TIMER="$ROOT/scripts/eval/计时运行.sh"
TAUS="0.02 0.05 0.01"                  # τ 三设置 (先跑 0.02, 其 表面点_剔点前.ply 供 τ曲线)

# 解析 coarse .pt 完整路径 (dir 名内嵌 3DGS 迭代, 文件名=coarse num_iterations; glob 最稳)
coarse_pt_path() {
  ls -t "$COARSE_DIR"/sugarcoarse_*/*.pt 2>/dev/null | head -1
}
# 解析主 mesh (排除 表面采样点云, 取体积最大)
main_mesh_path() {
  ls -S "$1"/sugarmesh_*.ply 2>/dev/null | grep -v 表面采样点云 | head -1
}
