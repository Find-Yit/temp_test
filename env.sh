#!/usr/bin/env bash
# SuGaR 考核环境 (Stage 0B) — /scratch/e1351071/zju_test_test
# 用法: source /scratch/e1351071/zju_test_test/env.sh
export SUGAR_ROOT=/scratch/e1351071/zju_test_test

# ---- venv ----
source "$SUGAR_ROOT/venv/bin/activate"

# ---- CUDA (系统 nvcc 12.1) ----
export CUDA_HOME=/usr/local/cuda
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"

# ---- 编译设置 (H200 = sm_90) ----
export TORCH_CUDA_ARCH_LIST="9.0"
export FORCE_CUDA=1
export MAX_JOBS=12

# ---- 所有缓存指向本目录 (不污染 HOME / 其他目录) ----
export PIP_CACHE_DIR="$SUGAR_ROOT/cache/pip"
export HF_HOME="$SUGAR_ROOT/cache/hf"
export HUGGINGFACE_HUB_CACHE="$SUGAR_ROOT/cache/hf"
export TORCH_HOME="$SUGAR_ROOT/cache/torch"
export XDG_CACHE_HOME="$SUGAR_ROOT/cache/xdg"
export TMPDIR="$SUGAR_ROOT/cache/tmp"
mkdir -p "$PIP_CACHE_DIR" "$HF_HOME" "$TORCH_HOME" "$XDG_CACHE_HOME" "$TMPDIR"

echo "[env.sh] venv=$(command -v python) CUDA_HOME=$CUDA_HOME ARCH=$TORCH_CUDA_ARCH_LIST MAX_JOBS=$MAX_JOBS"
