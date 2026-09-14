# SELF_CHECK_0B.md — 阶段 0B（环境安装）自检

工作目录: `/scratch/e1351071/zju_test_test`  | 日期: 2026-09-14
结论: **全部 PASS**（12/12 条），`check_env.py` 7/7 + 额外光栅化 GPU 冒烟测试 PASS。
总墙钟: 约 23 分钟（11:07 → 11:30 UTC），< 计划阶段0 的 40 min 预算。
说明: 所有 venv / 缓存 / 编译产物均位于工作目录内，未查看或改动 `/scratch/e1351071` 下其它目录；未删除任何文件；未 git commit。

复算入口（一次跑完两条即可复核核心结论）:
```bash
cd /scratch/e1351071/zju_test_test && source env.sh
python scripts/check_env.py         # 期望: RESULT 7/7 passed, exit 0
python scripts/check_rasterizer.py  # 期望: RASTERIZER_GPU_OK, exit 0
```

| # | 验收条目 | 实际值 | 结果 | 耗时 | 复算命令 |
|---|---|---|---|---|---|
| 1 | venv 建于 `./venv`，Python 3.10 | Python 3.10.12，`./venv/bin/python` | PASS | ~5s | `./venv/bin/python --version` |
| 2 | `env.sh`：activate + CUDA_HOME + TORCH_CUDA_ARCH_LIST=9.0 + MAX_JOBS=12 + 缓存指向本目录 | source 输出 `CUDA_HOME=/usr/local/cuda ARCH=9.0 MAX_JOBS=12`；PIP_CACHE_DIR/HF_HOME/TORCH_HOME/TMPDIR 均在本目录 | PASS | — | `source env.sh` |
| 3 | torch + torchvision (cu121, 匹配 nvcc 12.1) | torch 2.4.1+cu121 / torchvision 0.19.1+cu121，cuda_build=12.1 | PASS | ~6min | `python -c "import torch,torchvision;print(torch.__version__,torchvision.__version__,torch.version.cuda)"` |
| 4 | torch CUDA 可用 + GPU 识别 | avail=True, gpu=NVIDIA H200, cap=(9,0) | PASS | — | `python -c "import torch;print(torch.cuda.is_available(),torch.cuda.get_device_name(0),torch.cuda.get_device_capability(0))"` |
| 5 | ninja 安装 | ninja 1.13.2（二进制可执行）| PASS | ~5s | `ninja --version` |
| 6 | pytorch3d 安装 | 0.7.8（预编译 wheel py310_cu121_pyt241，无源码编译）| PASS | ~30s | `python -c "import pytorch3d;print(pytorch3d.__version__)"` |
| 7 | diff_gaussian_rasterization 编译+安装 | 0.0.0，`_C.cpython-310-x86_64-linux-gnu.so` 加载正常（nvcc12.1/arch9.0）| PASS | ~60s | `python -c "import diff_gaussian_rasterization._C as c;print(c.__file__)"` |
| 8 | simple_knn 编译+安装 | 0.0.0，`from simple_knn._C import distCUDA2` 正常 | PASS | ~40s | `python -c "from simple_knn._C import distCUDA2;print('ok')"` |
| 9 | pytorch3d GPU knn 调用 | knn_points idx=(1,128,5) dists=(1,128,5) | PASS | <1s | `python scripts/check_env.py`（含此项）|
| 10 | check_env.py 全导入通过（torch/pytorch3d/dgr/simple_knn/open3d/pymeshlab/plyfile）+ GPU 调用 | **7/7 PASS**，见 `notes/env_check.json`（open3d 0.18.0 / pymeshlab 2025.7.post1 / plyfile 1.1.3；simple_knn GPU distCUDA2 mean=0.003876）| PASS | 8.67s | `python scripts/check_env.py; echo $?` |
| 11 | ENV.md 写出（系统/Python/PyTorch/CUDA runtime+nvcc/GPU/驱动/关键依赖）| `notes/ENV.md`（102 行，含全部字段）| PASS | — | `cat notes/ENV.md` |
| 12 | pip freeze 落盘 | `notes/pip_freeze.txt`（116 包）| PASS | — | `wc -l notes/pip_freeze.txt` |
| + | （额外）光栅化 GPU 前向冒烟测试 | 渲染 500 高斯→128x128，radii>0=500/500，img.sum=8330.36，`RASTERIZER_GPU_OK` | PASS | ~5s | `python scripts/check_rasterizer.py; echo $?` |

## 关键决策与偏离
- **[决策] torch 2.4.1 + cu121**：计划首选组合可行（cu121 索引在 download.pytorch.org 完整可用，torch 2.1.0–2.5.1 均在），
  且恰好存在精确匹配的 pytorch3d 预编译 wheel `py310_cu121_pyt241`（pytorch3d 0.7.8），因此 **pytorch3d 免源码编译**。
  nvcc 12.1 与 cu121 运行时精确匹配，两个 CUDA 扩展编译顺利。故未触发计划中“cu121 下线则改 cu126”的备选路径。
- **[决策] numpy 固定 1.26.4（<2）**：pytorch3d 0.7.8 / open3d 0.18.0 / pymeshlab 按 numpy 1.x ABI 构建；
  torch 默认拉入 numpy 2.2.6，已回退为 1.26.4，验证全部导入正常。
- **[决策] setuptools 回退 69.5.1 + `--no-build-isolation` 编译子模块**：新版 setuptools 84 与 torch 2.4.1 的
  cpp_extension 构建不兼容；子模块 setup.py 顶层 `import torch`，必须关闭构建隔离用 venv 内 torch 编译。
- **无阻断性偏离（DEVIATION）**：未遇到无法解决的问题。可选依赖 nvdiffrast/bpy/gsplat/nerfacc/lpips 未装（计划标注可选，
  阶段1核心 3DGS→coarse SuGaR→mesh 不需要），如后续需要再按需补装并记入执行日志。
