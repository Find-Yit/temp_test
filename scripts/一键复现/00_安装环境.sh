#!/usr/bin/env bash
# 一键复现 · 00 从零安装环境
# ------------------------------------------------------------------
# venv + torch(cu121) + 依赖 + pytorch3d 预编译 wheel + 编译两个 CUDA 扩展, 最后自检。
# 命令与 notes/ENV.md §7 复现命令 / logs/pip_*.log 实际成功命令一致。
# 幂等: venv 已存在则跳过创建; pip install 可重复执行。
# 用法: bash scripts/一键复现/00_安装环境.sh
set -euo pipefail

ROOT="${SUGAR_ROOT:-/scratch/e1351071/zju_test_test}"
cd "$ROOT"
mkdir -p logs
LOG="$ROOT/logs/一键_00安装_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1
ts(){ date "+%Y-%m-%d %H:%M:%S"; }
log(){ echo "[$(ts)] $*"; }
T0=$(date +%s)

log "==== 00 安装环境 开始 (ROOT=$ROOT) 日志: $LOG ===="

# (0) SuGaR 源码 (vendored, 已含全部编译源码; 若缺失才克隆)
if [ ! -d "$ROOT/repo/SuGaR/gaussian_splatting/submodules/simple-knn" ]; then
  log "[0] 克隆 SuGaR@7c10c4a (--recursive; 无活跃 submodule, 源码已内嵌)"
  git clone --recursive https://github.com/Anttwo/SuGaR.git "$ROOT/repo/SuGaR"
  ( cd "$ROOT/repo/SuGaR" && git checkout 7c10c4ae4a267dece512f5c7f40ed212a0a2ab44 )
else
  log "[0] repo/SuGaR 已存在, 跳过克隆"
fi

# (1) venv + 环境变量
if [ ! -d "$ROOT/venv" ]; then
  log "[1] 创建 venv (/usr/bin/python3 -m venv venv)"
  /usr/bin/python3 -m venv "$ROOT/venv"
else
  log "[1] venv 已存在, 跳过创建"
fi
log "[1] source env.sh (激活 venv + CUDA_HOME + arch 9.0 + 缓存重定向)"
# shellcheck disable=SC1091
source "$ROOT/env.sh"
pip install --upgrade pip setuptools wheel

# (2) torch / torchvision (cu121, 对齐系统 nvcc 12.1)
log "[2] 安装 torch 2.4.1 + torchvision 0.19.1 (cu121)"
pip install torch==2.4.1 torchvision==0.19.1 --index-url https://download.pytorch.org/whl/cu121

# (3) SuGaR 其它依赖 (numpy 固定 1.26.4)
log "[3] 安装 SuGaR 依赖 (numpy==1.26.4 等)"
pip install ninja "numpy==1.26.4" scipy "open3d==0.18.0" pymeshlab plyfile rich tqdm plotly \
    opencv-python-headless PyMCubes matplotlib scikit-learn pyquaternion fvcore iopath

# (4) pytorch3d 预编译 wheel (免源码编译; --no-deps 防带回 numpy>=2)
log "[4] 安装 pytorch3d 0.7.8 预编译 wheel (py310_cu121_pyt241)"
pip install --no-deps https://dl.fbaipublicfiles.com/pytorch3d/packaging/wheels/py310_cu121_pyt241/pytorch3d-0.7.8-cp310-cp310-linux_x86_64.whl

# (5) 编译两个 CUDA 扩展 (setuptools 回退 69.5.1; --no-build-isolation)
log "[5] 编译 simple-knn / diff-gaussian-rasterization (arch 9.0)"
pip install "setuptools==69.5.1"
pip install --no-build-isolation --no-deps "$ROOT/repo/SuGaR/gaussian_splatting/submodules/simple-knn"
pip install --no-build-isolation --no-deps "$ROOT/repo/SuGaR/gaussian_splatting/submodules/diff-gaussian-rasterization"
#   (等价封装: bash scripts/build_ext.sh)

# (6) 验收
log "[6] 环境自检 scripts/check_env.py (期望 7/7 PASS)"
python "$ROOT/scripts/check_env.py"
log "[6] 光栅化 GPU 自检 scripts/check_rasterizer.py (期望 RASTERIZER_GPU_OK)"
python "$ROOT/scripts/check_rasterizer.py"

log "==== 00 安装环境 完成, 耗时 $(( $(date +%s) - T0 ))s ===="
