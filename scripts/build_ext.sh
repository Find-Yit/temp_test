#!/usr/bin/env bash
set -o pipefail
source /scratch/e1351071/zju_test_test/env.sh
echo "[build] setuptools downgrade to 69.5.1 (for torch cpp_extension)"
pip install "setuptools==69.5.1" 2>&1 | tail -2
echo "[build] CUDA_HOME=$CUDA_HOME ARCH=$TORCH_CUDA_ARCH_LIST MAX_JOBS=$MAX_JOBS nvcc=$(nvcc --version | tail -1)"
SUB=/scratch/e1351071/zju_test_test/repo/SuGaR/gaussian_splatting/submodules
echo "=== building simple-knn ==="
pip install --no-build-isolation --no-deps "$SUB/simple-knn" 2>&1
echo "SIMPLEKNN_DONE rc=${PIPESTATUS[0]}"
echo "=== building diff-gaussian-rasterization ==="
pip install --no-build-isolation --no-deps "$SUB/diff-gaussian-rasterization" 2>&1
echo "DGR_DONE rc=${PIPESTATUS[0]}"
echo "EXT_ALL_DONE"
