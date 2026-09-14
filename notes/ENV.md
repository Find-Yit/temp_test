# ENV.md — SuGaR 考核环境 (阶段 0B)

工作目录: `/scratch/e1351071/zju_test_test`（venv / cache / 编译产物全部在此目录内，未触碰其他目录）
日期: 2026-09-14  |  验收: `scripts/check_env.py` 7/7 PASS + 光栅化 GPU 冒烟测试 PASS

## 1. 机器 / 系统
| 项 | 值 |
|---|---|
| OS (userspace) | Ubuntu 22.04.3 LTS |
| Kernel | 5.14.0-427.13.1.el9_4.x86_64 (RHEL9 内核) |
| CPU / 内存 | 12 核 / 2 TB |
| /scratch 可用 | ~3.2 PB (充足) |
| GPU | NVIDIA H200, 143771 MiB (~143 GB) |
| GPU 架构 | sm_90 (compute capability 9.0) |
| NVIDIA 驱动 | 575.57.08 (最高支持 CUDA 12.9) |
| 系统 gcc | 11.4.0 (Ubuntu 11.4.0-1ubuntu1~22.04) |

## 2. CUDA
| 项 | 值 |
|---|---|
| nvcc (系统) | 12.1, V12.1.105 (`/usr/local/cuda`) |
| CUDA_HOME | `/usr/local/cuda` |
| PyTorch 运行时 CUDA | 12.1 (torch.version.cuda) |
| 编译架构 | `TORCH_CUDA_ARCH_LIST=9.0` (H200) |
| 说明 | nvcc 12.1 与 torch cu121 运行时**精确匹配**，两个 CUDA 扩展与 torch ABI 完全一致。 |

## 3. Python / venv
| 项 | 值 |
|---|---|
| 解释器 | Python 3.10.12 (`/usr/bin/python3`) |
| venv | `/scratch/e1351071/zju_test_test/venv` |
| pip / setuptools / wheel | pip 26.2.1 / setuptools 69.5.1 / wheel 0.48.0 |
| 环境脚本 | `env.sh`（source 后：激活 venv + CUDA_HOME + TORCH_CUDA_ARCH_LIST=9.0 + MAX_JOBS=12 + 全部缓存指向本目录）|

> 备注：setuptools 从初装的 84.0.0 **回退到 69.5.1**，因为新版 setuptools 与 torch 2.4.1 的
> `torch.utils.cpp_extension` 编译流程不兼容；编译两个子模块时使用 `--no-build-isolation`
> （子模块 setup.py 顶层 `import torch`，若用构建隔离会因隔离环境缺 torch 而失败）。

## 4. 深度学习核心
| 包 | 版本 | 来源 |
|---|---|---|
| torch | 2.4.1+cu121 | download.pytorch.org/whl/cu121 |
| torchvision | 0.19.1+cu121 | download.pytorch.org/whl/cu121 |
| pytorch3d | 0.7.8 | 预编译 wheel `py310_cu121_pyt241`（无需源码编译）|
| diff_gaussian_rasterization | 0.0.0 | 本仓库源码编译 (nvcc 12.1, arch 9.0) |
| simple_knn | 0.0.0 | 本仓库源码编译 (nvcc 12.1, arch 9.0) |

> 关键决策：选 torch **2.4.1 + cu121** 而非其他组合，因为存在与之精确匹配的 pytorch3d 预编译
> wheel（`py310_cu121_pyt241` → pytorch3d 0.7.8），既满足计划建议的 cu121（与 nvcc 12.1 对齐），
> 又**免去 pytorch3d 的源码编译**。cu121 索引在 download.pytorch.org 仍完整可用（torch 2.1.0–2.5.1）。

## 5. SuGaR 其它依赖
| 包 | 版本 |
|---|---|
| numpy | 1.26.4 (**固定 <2**，因 pytorch3d/open3d/pymeshlab 均按 numpy 1.x ABI 构建) |
| scipy | 1.15.3 |
| open3d | 0.18.0 |
| pymeshlab | 2025.7.post1 |
| plyfile | 1.1.3 |
| PyMCubes (mcubes) | 0.1.6 |
| opencv-python-headless (cv2) | 4.11.0.86 |
| scikit-learn | 1.7.2 |
| matplotlib | 3.10.9 |
| plotly | 7.0.0 |
| rich | 15.0.0 |
| tqdm | 4.70.1 |
| pyquaternion | 0.9.9 |
| fvcore / iopath | 0.1.5.post20221221 / 0.1.10 (pytorch3d 运行时依赖) |
| ninja | 1.13.2 (加速 CUDA 扩展编译) |

完整清单见 `notes/pip_freeze.txt`（116 个包）。

未安装（计划标注可选 / 非核心路径，阶段1核心不需要）：nvdiffrast、bpy(blender)、gsplat、nerfacc、lpips。
如后续做“带纹理网格提取 / blender 渲染”再按需补装（写入执行日志）。

## 6. 验证结果
`scripts/check_env.py` → **7/7 PASS**（详见 `notes/env_check.json`）：
- import torch (+cuda avail): torch=2.4.1+cu121, cuda_build=12.1, avail=True, gpu=NVIDIA H200, cap=(9,0)
- import diff_gaussian_rasterization: 编译 `_C.cpython-310-x86_64-linux-gnu.so` 正常加载
- simple_knn._C GPU distCUDA2(2000x3): 输出有限值, mean=0.003876（sm_90 CUDA 核实测执行）
- pytorch3d GPU knn_points: pytorch3d=0.7.8, idx=(1,128,5), dists=(1,128,5)
- import open3d 0.18.0 / pymeshlab 2025.7.post1 / plyfile 1.1.3

额外去风险：`scripts/check_rasterizer.py` → **RASTERIZER_GPU_OK**（渲染 500 高斯到 128x128，
radii>0=500/500，img.sum=8330.36，非黑图）——证明 diff-gaussian-rasterizer 的前向 CUDA 核在 H200 上正确执行。

## 7. 复现命令
```bash
cd /scratch/e1351071/zju_test_test
/usr/bin/python3 -m venv venv
source env.sh
pip install --upgrade pip setuptools wheel
pip install torch==2.4.1 torchvision==0.19.1 --index-url https://download.pytorch.org/whl/cu121
pip install ninja "numpy==1.26.4" scipy "open3d==0.18.0" pymeshlab plyfile rich tqdm plotly \
    opencv-python-headless PyMCubes matplotlib scikit-learn pyquaternion fvcore iopath
pip install --no-deps https://dl.fbaipublicfiles.com/pytorch3d/packaging/wheels/py310_cu121_pyt241/pytorch3d-0.7.8-cp310-cp310-linux_x86_64.whl
pip install "setuptools==69.5.1"
pip install --no-build-isolation --no-deps repo/SuGaR/gaussian_splatting/submodules/simple-knn
pip install --no-build-isolation --no-deps repo/SuGaR/gaussian_splatting/submodules/diff-gaussian-rasterization
python scripts/check_env.py            # 期望 7/7 PASS, exit 0
python scripts/check_rasterizer.py     # 期望 RASTERIZER_GPU_OK, exit 0
```
