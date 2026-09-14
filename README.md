# SuGaR 6 小时考核：3DGS → Coarse SuGaR → Mesh（含「Poisson 前多视角深度一致性剔点」改动）

> 本仓库把 3D Gaussian Splatting 训练到 SuGaR 网格提取的完整基线跑通，并在提取主流程中加入一个进入主流程的改动——**在 Poisson 重建之前对表面采样点做多视角深度一致性投票剔点**，用于对比 baseline 与多个 τ 超参下的几何/渲染质量。
>
> 本 README 承载**代码差异、代码修改说明、实验环境**等全部工程细节（这些内容按项目约定不进入 `report/` 报告）。报告只保留方法与结果。
>
> **状态（2026-09-14）**：阶段1 基线、阶段2a 改动实现、阶段2c τ 扫描与 M1–M6 评测**均已完成**；本 README 原有的 **10 处【待补】已全部回填为落盘实测数字**（逐处回填 → 来源见 [`notes/SELF_CHECK_README回填.md`](notes/SELF_CHECK_README回填.md)）。文中所有数字均来自 `outputs/` 下的 CSV/JSON/TXT，可复算，不编造。

---

## 快速复现（5 条命令）

> 前置：已按 [§2.5 一键安装](#25-一键安装可直接复制执行) 装好 venv 与两个 CUDA 扩展。命令均在**工作目录**下、`source env.sh` 之后运行；seed 全链路固定 0。第 ⑤ 步须**在 `repo/SuGaR` 内运行**且 `-c` **带结尾斜杠**（见 §7.5）。各步详解见 [§5 逐步复现命令](#5-逐步复现命令)。

```bash
# ① 环境（venv + CUDA + 缓存重定向到本目录）；期望 check_env 7/7 PASS
cd /scratch/e1351071/zju_test_test && source env.sh && python scripts/check_env.py

# ② 3DGS 7000it → outputs/基线_truck/3dgs_7k/point_cloud/iteration_7000/point_cloud.ply  (墙钟≈119s)
python repo/SuGaR/gaussian_splatting/train.py -s data/tandt/truck -m outputs/基线_truck/3dgs_7k \
    --iterations 7000 --save_iterations 7000 --test_iterations 7000 --eval --quiet

# ③ coarse SuGaR dn_consistency（num_iterations=15000 → 真实约8000步）→ .../15000.pt  (墙钟≈951s)
python scripts/run_coarse_dn.py -s data/tandt/truck -c outputs/基线_truck/3dgs_7k -i 7000 \
    -o outputs/基线_truck/coarse --num_iterations 15000 --eval True

# ④ 基线提取 mesh（-l 0.3 -d 1e6）+ 另存表面采样点云 → mesh V=750841/F=1437272  (墙钟≈359s)
python scripts/run_extract_mesh.py -s data/tandt/truck -c outputs/基线_truck/3dgs_7k -i 7000 \
    -m outputs/基线_truck/coarse/sugarcoarse_3Dgs7000_densityestim02_sdfnorm02/15000.pt \
    -l 0.3 -d 1000000 -o outputs/基线_truck/mesh --surfpts_dir outputs/基线_truck/mesh --eval True

# ⑤ 改动 τ 扫描（在 repo/SuGaR 内运行、-c 尾斜杠；τ=0.02 示例，其余改 --mv_tau 与 -o）→ 剔除率 0.4494
( cd repo/SuGaR && python extract_mesh.py -s "$SUGAR_ROOT/data/tandt/truck" \
    -c "$SUGAR_ROOT/outputs/基线_truck/3dgs_7k/" -i 7000 \
    -m "$SUGAR_ROOT/outputs/基线_truck/coarse/sugarcoarse_3Dgs7000_densityestim02_sdfnorm02/15000.pt" \
    -l 0.3 -d 1000000 -o "$SUGAR_ROOT/outputs/改动_truck/改动_τ0.02" \
    --mv_filter True --mv_tau 0.02 --mv_seed 0 --seed 0 --eval True )
```

> 评测（M1–M6）与单测另见 §5.5：`python scripts/tests/test_mv_filter.py`（6/6 PASS）、`python scripts/eval/run_all_eval.py --config <评测配置.json>`。

---

## 目录

1. [项目简介与目录结构](#1-项目简介与目录结构)
2. [实验环境与安装](#2-实验环境与安装)
3. [数据](#3-数据)
4. [代码改动](#4-代码改动)
5. [逐步复现命令](#5-逐步复现命令)
6. [输出与交付物说明](#6-输出与交付物说明)
7. [失败记录与已知问题](#7-失败记录与已知问题)

---

## 1. 项目简介与目录结构

**一句话**：在单张 NVIDIA H200 上，用 `tandt/truck` 场景走通 `3DGS(7k) → coarse SuGaR dn_consistency(15k) → Mesh 提取` 的基线，并实现一个「Poisson 前多视角深度一致性剔点」的改动（默认关闭，关闭时与基线逐位一致），对比 baseline 与 τ∈{0.01, 0.02, 0.05} 消融。

工作根目录：`/scratch/e1351071/zju_test_test`（下文简称「工作目录」；venv、缓存、编译产物、数据、权重全部在此目录内，不触碰其他目录）。

```
zju_test_test/
├── README.md                     # 本文件（工程细节唯一入口）
├── CLAUDE.md                     # 协作/分工规则（非交付物）
├── env.sh                        # 环境激活脚本（venv + CUDA + 缓存重定向），source 即用
├── 李俊成老师组_6小时考核_3DGS到Mesh_v2.pdf   # 考核题目
│
├── repo/SuGaR/                   # SuGaR 源码（commit 7c10c4a）+ 本项目改动（见 §4）
│   ├── extract_mesh.py           # 【改】新增 --mv_* 参数并透传（默认关闭）
│   └── sugar_extractors/
│       ├── coarse_mesh.py            # 【改】表面点采样后、Poisson 前调用剔点（默认关闭）
│       └── mv_consistency_filter.py  # 【新增】多视角深度一致性剔点核心实现
│
├── data/                         # 数据集（3DGS 官方 tandt_db.zip 解压；见 §3）
│   ├── tandt/{truck,train}/
│   └── db/{playroom,drjohnson}/
│
├── scripts/                      # 全部为「只新增、不改仓库」的包装脚本（见 §4.4、§5）
│   ├── check_env.py              # 环境自检（7 项）
│   ├── check_rasterizer.py       # diff-gaussian-rasterizer GPU 冒烟
│   ├── build_ext.sh              # 编译 simple-knn / diff-gaussian-rasterization
│   ├── coarse_dn_trainer_param.py   # repo coarse trainer 的逐字副本，仅放开 num_iterations/save_milestones
│   ├── run_coarse_dn.py          # 驱动 coarse 训练的 wrapper（固定 seed，补尾斜杠）
│   ├── coarse_mesh_savepts.py    # repo coarse_mesh.py 逐字副本 + 另存表面采样点云
│   ├── run_extract_mesh.py       # 驱动 mesh 提取的 wrapper（基线用）
│   ├── _chain_coarse.sh / _watch_coarse_rate.sh   # 串联/监控辅助
│   ├── tests/test_mv_filter.py   # 改动单元测试（CPU，合成球面+漂浮点）
│   └── eval/                     # 评测脚本 M1–M6 + 计时封装（见 §5.5）
│       ├── m1_render_metrics.py  # PSNR/SSIM/LPIPS（测试视角）
│       ├── m2_geometry.py        # 双向点到面/Chamfer/F-score
│       ├── m3_topology.py        # 拓扑/网格质量（连通分量、非流形、孔洞…）
│       ├── m4_coverage.py        # 渲染覆盖率 / 漏洞率
│       ├── m5_efficiency.py      # 墙钟/显存/顶点面数/体积汇总
│       ├── m6_visualize.py       # 截图/误差热图/连通分量着色/对比拼图
│       ├── run_all_eval.py       # 汇总 M1–M6 并做 baseline vs 改动 对比
│       ├── eval_common.py        # 共享工具
│       └── 计时运行.sh           # 墙钟 + 峰值显存 计时封装
│
├── outputs/                      # 实验产物（中文命名；json+txt 双份；见 §6）
│   ├── 冒烟_truck/               # 冒烟全链路产物
│   ├── 基线_truck/              # 正式基线（3dgs_7k / coarse / mesh / 计时）
│   └── 改动开发_临时/           # 改动开发期临时产物
│
├── 考核提交/                     # 面向考核方的交付物（从 outputs 复制）：网格/ 指标/ 可视化/ 日志/（清单与计数见 §6.3）
├── report/                       # LaTeX 报告（report.pdf / report.tex / sections/）
│
├── notes/                        # 记录与自检
│   ├── ENV.md                    # 环境详录
│   ├── COMMITS.md                # 仓库/子模块 commit 记录
│   ├── pip_freeze.txt            # 完整依赖清单（116 包）
│   ├── RUNLOG_基线.md / RUNLOG_改动.md   # 逐阶段运行日志
│   ├── diffs/README_snapshot.patch       # §4 完整 diff 快照
│   └── SELF_CHECK_*.md / SURVEY.md / 评测方案调研.md / 先例核实.md
│
├── venv/                         # Python 3.10 虚拟环境
├── cache/                        # pip/hf/torch/xdg/tmp 缓存（由 env.sh 重定向到此）
├── logs/                         # 安装与运行日志
├── assets/  tools/tectonic/      # 报告字体与 LaTeX 引擎
```

---

## 2. 实验环境与安装

> 详录见 `notes/ENV.md`；环境自检结果见 `notes/env_check.json`（`scripts/check_env.py` **7/7 PASS**）。

### 2.1 机器 / 系统

| 项 | 值 |
|---|---|
| OS (userspace) | Ubuntu 22.04.3 LTS |
| Kernel | 5.14.0-427.13.1.el9_4.x86_64（RHEL9 内核） |
| CPU / 内存 | 12 核 / 2 TB |
| GPU | NVIDIA **H200**, 143771 MiB（约 143 GB），单卡 |
| GPU 架构 | sm_90（compute capability 9.0） |
| NVIDIA 驱动 | 575.57.08（最高支持 CUDA 12.9） |
| 系统 gcc | 11.4.0 |

### 2.2 CUDA / Python / 深度学习核心

| 项 | 值 | 来源 / 说明 |
|---|---|---|
| nvcc（系统） | 12.1, V12.1.105（`/usr/local/cuda`） | `CUDA_HOME=/usr/local/cuda` |
| 编译架构 | `TORCH_CUDA_ARCH_LIST=9.0`（H200） | 由 `env.sh` 导出 |
| Python | 3.10.12（`/usr/bin/python3`） | venv 在 `./venv` |
| pip / setuptools / wheel | 26.2.1 / **69.5.1** / 0.48.0 | setuptools 从 84.0.0 回退（见 §7） |
| torch | **2.4.1+cu121** | download.pytorch.org/whl/cu121 |
| torchvision | 0.19.1+cu121 | 同上 |
| pytorch3d | **0.7.8** | 预编译 wheel `py310_cu121_pyt241`（免源码编译） |
| diff_gaussian_rasterization | 0.0.0 | 本仓库源码编译（nvcc 12.1, arch 9.0） |
| simple_knn | 0.0.0 | 本仓库源码编译（nvcc 12.1, arch 9.0） |

**关键决策**：选 `torch 2.4.1 + cu121` 而非其他组合，因为存在与之精确匹配的 pytorch3d 预编译 wheel（`py310_cu121_pyt241` → 0.7.8），既满足 cu121（与系统 nvcc 12.1 对齐、扩展与 torch ABI 一致），又免去 pytorch3d 源码编译。

### 2.3 SuGaR 其它关键依赖

| 包 | 版本 | 包 | 版本 |
|---|---|---|---|
| numpy | **1.26.4（固定 <2）** | open3d | 0.18.0 |
| scipy | 1.15.3 | pymeshlab | 2025.7.post1 |
| plyfile | 1.1.3 | PyMCubes (mcubes) | 0.1.6 |
| opencv-python-headless | 4.11.0.86 | scikit-learn | 1.7.2 |
| matplotlib | 3.10.9 | plotly | 7.0.0 |
| rich | 15.0.0 | tqdm | 4.70.1 |
| pyquaternion | 0.9.9 | fvcore / iopath | 0.1.5.post20221221 / 0.1.10 |
| ninja | 1.13.2 | | |

- numpy **固定 `<2`**：pytorch3d / open3d / pymeshlab 均按 numpy 1.x ABI 构建。
- 完整清单（116 包）见 [`notes/pip_freeze.txt`](notes/pip_freeze.txt)。
- **未安装**（计划标注可选、阶段1核心不需要）：nvdiffrast、bpy(blender)、gsplat、nerfacc、lpips。

### 2.4 SuGaR 仓库版本

| 项 | 值 |
|---|---|
| 仓库 | Anttwo/SuGaR，`https://github.com/Anttwo/SuGaR.git`，分支 `main` |
| **起始 commit** | `7c10c4ae4a267dece512f5c7f40ed212a0a2ab44`（短号 **7c10c4a**，2024-09-24 "Minor fix."） |

> **子模块结构说明（重要）**：该 commit 把 `gaussian_splatting`、`diff-gaussian-rasterization`、`simple-knn`、`glm` **全部以普通文件内嵌（vendored）**进 SuGaR 仓库，**不存在活跃 git submodule**（无 `.gitmodules` 生效、`git submodule status` 为空、0 个 gitlink）。因此编译所需源码（含 glm 0.9.9.9）已全部在本地，**无需** `git submodule update --init --recursive`。详见 `notes/COMMITS.md`。

### 2.5 一键安装（可直接复制执行）

```bash
cd /scratch/e1351071/zju_test_test

# (0) 克隆 SuGaR（若尚未克隆）——vendored 结构，--recursive 亦可，无活跃子模块
#     git clone --recursive https://github.com/Anttwo/SuGaR.git repo/SuGaR
#     cd repo/SuGaR && git checkout 7c10c4ae4a267dece512f5c7f40ed212a0a2ab44 && cd ../..

# (1) venv + 环境变量（CUDA_HOME / arch 9.0 / 缓存重定向到本目录）
/usr/bin/python3 -m venv venv
source env.sh                       # 之后所有命令均在此环境下、于工作目录运行
pip install --upgrade pip setuptools wheel

# (2) torch / torchvision（cu121，与系统 nvcc 12.1 对齐）
pip install torch==2.4.1 torchvision==0.19.1 --index-url https://download.pytorch.org/whl/cu121

# (3) SuGaR 其它依赖（numpy 固定 1.26.4）
pip install ninja "numpy==1.26.4" scipy "open3d==0.18.0" pymeshlab plyfile rich tqdm plotly \
    opencv-python-headless PyMCubes matplotlib scikit-learn pyquaternion fvcore iopath

# (4) pytorch3d 预编译 wheel（免源码编译；--no-deps 避免带回 numpy>=2）
pip install --no-deps https://dl.fbaipublicfiles.com/pytorch3d/packaging/wheels/py310_cu121_pyt241/pytorch3d-0.7.8-cp310-cp310-linux_x86_64.whl

# (5) 编译两个 CUDA 扩展
#     setuptools 回退到 69.5.1（新版与 torch 2.4.1 的 cpp_extension 流程不兼容）
#     --no-build-isolation：子模块 setup.py 顶层 import torch，隔离环境会缺 torch
pip install "setuptools==69.5.1"
pip install --no-build-isolation --no-deps repo/SuGaR/gaussian_splatting/submodules/simple-knn
pip install --no-build-isolation --no-deps repo/SuGaR/gaussian_splatting/submodules/diff-gaussian-rasterization
#     （等价封装：bash scripts/build_ext.sh）

# (6) 验收
python scripts/check_env.py         # 期望 7/7 PASS, exit 0
python scripts/check_rasterizer.py  # 期望 RASTERIZER_GPU_OK, exit 0
```

`env.sh` 的作用：激活 venv；设 `CUDA_HOME=/usr/local/cuda`、`TORCH_CUDA_ARCH_LIST=9.0`、`FORCE_CUDA=1`、`MAX_JOBS=12`；把 pip/hf/torch/xdg/tmp **全部缓存重定向到 `./cache`**（不污染 HOME）。**运行任何实验前先 `source env.sh`。**

---

## 3. 数据

| 项 | 值 |
|---|---|
| 来源 URL | `https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/datasets/input/tandt_db.zip`（3DGS 官方） |
| 下载校验 | 682,628,995 B（约 651 MiB），`zipfile.testzip()=None`（无损坏） |
| 本地路径 | `data/tandt_db.zip`，解压至 `data/tandt/`、`data/db/` |

解压得到 4 个场景（图像数为 `images/` 下文件计数）：

| 场景 | 路径 | 图像数 |
|---|---|---|
| **truck（本项目主场景）** | `data/tandt/truck` | **251** |
| train | `data/tandt/train` | 301 |
| playroom | `data/db/playroom` | 225 |
| drjohnson | `data/db/drjohnson` | 263 |

**测试划分（`--eval` → llffhold=8，即 `idx % 8 == 0` 为测试）**：

| 场景 | 训练 | 测试 |
|---|---|---|
| **truck** | **219** | **32** |

> 首次运行 3DGS 会从 `data/tandt/truck/sparse/0/points3D.bin` 派生 `points3D.ply`（SuGaR trainer 需要）；该 `.ply` 为运行时缓存，非仓库文件。

---

## 4. 代码改动

**改动性质**：只改提取主流程（`extract_mesh.py` + `sugar_extractors/coarse_mesh.py`）+ 新增 1 个模块（`mv_consistency_filter.py`）。**默认 `mv_filter=False` 时，提取流程与基线（commit 7c10c4a）逐位一致**——`git diff -w`（忽略空白）显示对已跟踪文件为 **70 行纯新增、0 行删除/修改**，无任何既有逻辑行被删改。

> **快照时间**：以下 diff 于 **2026-09-14 13:57 (+0000)** 复核，**改动实现已完成、git diff 已稳定**（`repo/SuGaR` HEAD 仍为 `7c10c4a`；`mv_consistency_filter.py` md5=`33b356a66256fbad32b4bb8603a43437`，366 行未变）。本节内联 diff 与 [`notes/diffs/README_snapshot.patch`](notes/diffs/README_snapshot.patch) 的对应段落经 `diff` 复核**逐字一致**。

### 4.1 改动文件清单

| 文件 | 状态 | git diff --stat | 说明 |
|---|---|---|---|
| `repo/SuGaR/sugar_extractors/mv_consistency_filter.py` | **新增** | 366 行 | 多视角深度一致性剔点核心实现 |
| `repo/SuGaR/extract_mesh.py` | 修改 | +20 / −2（`-w` 忽略空白后 +18 / 0） | 新增 7 个 `--mv_*` argparse 参数并透传 |
| `repo/SuGaR/sugar_extractors/coarse_mesh.py` | 修改 | +54 / −2（`-w` 忽略空白后 +52 / 0） | Poisson 前调用剔点、落盘统计与前后点云 |

> `git diff --stat` 报告 `74 insertions(+), 4 deletions(-)`；4 处「删除」全部是**行尾空白字符**（如 `--use_vanilla_3dgs` 行的行尾空格、若干空行的尾随空格），无行为删除——`git diff -w` 复核为 0 删除。

### 4.2 各处改动说明

#### (A) 新增 `sugar_extractors/mv_consistency_filter.py`（366 行）

- **作用**：SuGaR 表面点是「沿各训练视角像素射线、密度首次跨越 `surface_level` 处」采样得到的，单视角自洽但漂浮几何/背景壳点换个视角会落进自由空间，进入 Poisson 后形成伪表面与膜状连接。本模块在 fg/bg 分离与 Poisson **之前**，用其它相机的渲染深度图对每个表面点投票剔点。
- **对外接口**：
  `multiview_depth_consistency_filter(sugar, points, colors, normals, cameras, *, n_ref_cams=30, n_votes=0, tau=0.02, min_consistent=2, max_conflict=1, seed=0, chunk_size=2_000_000, surface_level=None, save_ply_dir=None, ply_prefix="", verbose=True)` → `(keep_mask: BoolTensor(N,), stats: dict)`。
- **算法**（每个「有效」参考相机 c 对点 p 投一票）：
  - 深度为 PyTorch3D **视空间 z 坐标**（非欧氏距离；相机朝 +z，z 越大越远）；背景像素深度 = 0。
  - 有效 = `z_p > znear` 且 投影落在画幅内（自带 `in_bounds` 掩码，规避 `grid_sample` 的 `padding_mode='border'` 伪值）且 `z_map > eps`。
  - **一致票**：`|z_p − z_map| < tau · z_map`；**空域冲突票**：`z_p < z_map − tau · z_map`；被遮挡（`z_p > z_map·(1+tau)`）不计票。
  - **保留规则**：`一致票 ≥ min_consistent` 且 `空域冲突票 ≤ max_conflict`。
- **关键参数与默认值**：`tau=0.02`（COLMAP 默认 0.01）、`min_consistent=2`（ACMM 用 2）、`max_conflict=1`、`n_ref_cams(M)=30`、`n_votes(K)=0`（0 或 ≥M → 每点用全部 M 个参考相机；`0<K<M` → 每点固定 seed 随机抽 K 个）、`seed=0`。
- **可测试核心**：`accumulate_votes(...)`、`compute_keep_mask(...)`、`sample_reference_cameras(...)` 只依赖（相机、深度图、采样器），不需要完整 SuGaR 模型，供单元测试。
- **失败处理**：训练相机 ≤ M 用全部；N=0 返回空 keep + 平凡统计；被任何参考相机都看不到的点单列 `n_never_in_view`（作为 H2「弱覆盖区被误剔」的诊断）。
- **落盘**：`剔点统计.json` / `剔点统计.txt`（每个 surface_level 剔前/剔后点数、剔除率、一致票/冲突票直方图、参考相机索引）；`表面点_剔点前.ply` / `表面点_剔点后.ply`。
- **先例归属**（docstring 内注明）：判据源自 MVS 多视角几何一致性融合——COLMAP StereoFusion（相对深度差 0.01）、ACMM（相对深度差 <0.01 且 `num_consistent≥2` 投票）、GaussianPro（其 3DGS 版本，thre2=0.01）；与先例差异见 `plans/改动方案_多视角深度一致性剔点.txt` 与 `notes/先例核实.md`。

#### (B) `extract_mesh.py`（+18 行有效）

新增 7 个 argparse 参数并透传给 `extract_mesh_from_coarse_sugar(args)`，**默认值即基线行为**：

| 参数 | 类型 | 默认 | 含义 |
|---|---|---|---|
| `--mv_filter` | bool | **False** | 开启多视角深度一致性剔点（**默认关闭 → 与基线一致**） |
| `--mv_tau` | float | 0.02 | 相对深度容差 τ |
| `--mv_min_consistent` | int | 2 | 保留所需最少一致票 |
| `--mv_max_conflict` | int | 1 | 保留允许的最多空域冲突票 |
| `--mv_n_ref_cams` | int | 30 | 缓存深度图的参考相机数 M |
| `--mv_n_votes` | int | 0 | 每点投票相机数 K（0 或 ≥M 用全部 M） |
| `--mv_seed` | int | 0 | 参考相机抽样 seed |

#### (C) `sugar_extractors/coarse_mesh.py`（+52 行有效）

- 顶部 `from sugar_extractors.mv_consistency_filter import multiview_depth_consistency_filter, write_filter_stats`。
- 用 `_cfg(args, name, default)` 读取上述 mv 参数（**同时兼容 `argparse.Namespace`（extract_mesh.py）与 `AttrDict`/dict（train.py）**，缺省即基线行为）。
- 在每个 `surface_level` 拿到 `surface_points/colors/normals` **之后、fg/bg 分离与 Poisson 之前**：`if mv_filter:` 调用过滤器，用 `keep_mask` 切片三者，累积统计；循环结束后 `if mv_filter:` 统一 `write_filter_stats`。
- **`mv_filter=False` 时该分支完全不执行 → 输出与基线逐位一致**。

### 4.3 折叠的 git diff（已跟踪文件）

> 新增文件 `mv_consistency_filter.py`（366 行）未内联，见完整快照：**[`notes/diffs/README_snapshot.patch`](notes/diffs/README_snapshot.patch)**（含已跟踪修改 + 新增文件全文）。

<details>
<summary>展开 <code>git diff</code>（extract_mesh.py + sugar_extractors/coarse_mesh.py）</summary>

```diff
diff --git a/extract_mesh.py b/extract_mesh.py
index 8652751..3ba03b9 100644
--- a/extract_mesh.py
+++ b/extract_mesh.py
@@ -39,9 +39,27 @@ if __name__ == "__main__":
                         help='If True, just use centers of the gaussians to extract mesh.')
     parser.add_argument('--use_marching_cubes', type=str2bool, default=False, 
                         help='If True, use marching cubes to extract mesh.')
-    parser.add_argument('--use_vanilla_3dgs', type=str2bool, default=False, 
+    parser.add_argument('--use_vanilla_3dgs', type=str2bool, default=False,
                         help='If True, use vanilla 3DGS to extract mesh.')
-    
+
+    # ----- Multi-view depth-consistency point filtering (阶段2a 改动, 默认关闭) -----
+    # 在 fg/bg 分离与 Poisson 之前，对表面采样点做多视角深度一致性投票剔点。
+    # 关闭(mv_filter=False)时提取流程与基线逐位一致。详见 sugar_extractors/mv_consistency_filter.py。
+    parser.add_argument('--mv_filter', type=str2bool, default=False,
+                        help='If True, run multi-view depth-consistency point filtering before Poisson.')
+    parser.add_argument('--mv_tau', type=float, default=0.02,
+                        help='Relative depth tolerance for consistency vote (COLMAP default is 0.01).')
+    parser.add_argument('--mv_min_consistent', type=int, default=2,
+                        help='Keep a point only if consistent votes >= this (ACMM uses 2).')
+    parser.add_argument('--mv_max_conflict', type=int, default=1,
+                        help='Keep a point only if free-space conflict votes <= this.')
+    parser.add_argument('--mv_n_ref_cams', type=int, default=30,
+                        help='Number M of reference cameras whose depth maps are cached.')
+    parser.add_argument('--mv_n_votes', type=int, default=0,
+                        help='Per-point votes K: 0 or >=M means use all M reference cameras.')
+    parser.add_argument('--mv_seed', type=int, default=0,
+                        help='Seed for reference-camera sampling (and per-point K sampling).')
+
     args = parser.parse_args()
     
     # Call function
diff --git a/sugar_extractors/coarse_mesh.py b/sugar_extractors/coarse_mesh.py
index 414a0f2..9e0fc00 100644
--- a/sugar_extractors/coarse_mesh.py
+++ b/sugar_extractors/coarse_mesh.py
@@ -8,6 +8,9 @@ from sugar_scene.gs_model import GaussianSplattingWrapper
 from sugar_scene.sugar_model import SuGaR
 from sugar_utils.general_utils import str2bool
 from sugar_utils.spherical_harmonics import SH2RGB
+from sugar_extractors.mv_consistency_filter import (
+    multiview_depth_consistency_filter, write_filter_stats,
+)
 
 from rich.console import Console
 
@@ -105,7 +108,27 @@ def extract_mesh_from_coarse_sugar(args):
     use_centers_to_extract_mesh = args.use_centers_to_extract_mesh
     use_marching_cubes = args.use_marching_cubes
     use_vanilla_3dgs = args.use_vanilla_3dgs
-            
+
+    # ----- Multi-view depth-consistency filtering config (阶段2a 改动, 默认关闭) -----
+    # 兼容 argparse.Namespace(extract_mesh.py) 与 AttrDict(dict)(train.py); 缺省即基线行为。
+    def _cfg(a, name, default):
+        if isinstance(a, dict):
+            return a.get(name, default)
+        return getattr(a, name, default)
+    mv_filter = _cfg(args, 'mv_filter', False)
+    mv_tau = _cfg(args, 'mv_tau', 0.02)
+    mv_min_consistent = _cfg(args, 'mv_min_consistent', 2)
+    mv_max_conflict = _cfg(args, 'mv_max_conflict', 1)
+    mv_n_ref_cams = _cfg(args, 'mv_n_ref_cams', 30)
+    mv_n_votes = _cfg(args, 'mv_n_votes', 0)
+    mv_seed = _cfg(args, 'mv_seed', 0)
+    mv_filter_stats = []  # 每个 surface_level 的剔点统计, 循环后统一落盘
+    CONSOLE.print("Multi-view depth-consistency filter:", mv_filter)
+    if mv_filter:
+        CONSOLE.print(f"  mv_tau={mv_tau} mv_min_consistent={mv_min_consistent} "
+                      f"mv_max_conflict={mv_max_conflict} mv_n_ref_cams={mv_n_ref_cams} "
+                      f"mv_n_votes={mv_n_votes} mv_seed={mv_seed}")
+
     CONSOLE.print("-----Parameters-----")
     CONSOLE.print("Source path:", source_path)
     CONSOLE.print("Gaussian Splatting Checkpoint path:", gs_checkpoint_path)
@@ -337,6 +360,30 @@ def extract_mesh_from_coarse_sugar(args):
                 surface_colors = surface_levels_outputs[surface_level]['colors']
                 surface_normals = surface_levels_outputs[surface_level]['normals']
 
+                # ----- 阶段2a 改动: Poisson 前多视角深度一致性剔点 (默认关闭) -----
+                # 关闭(mv_filter=False)时本分支完全不执行, 输出与基线逐位一致。
+                if mv_filter:
+                    keep_mask, mv_stats = multiview_depth_consistency_filter(
+                        sugar, surface_points,
+                        colors=surface_colors, normals=surface_normals,
+                        cameras=nerfmodel.training_cameras,
+                        n_ref_cams=mv_n_ref_cams, n_votes=mv_n_votes, tau=mv_tau,
+                        min_consistent=mv_min_consistent, max_conflict=mv_max_conflict,
+                        seed=mv_seed, surface_level=surface_level,
+                        save_ply_dir=mesh_output_dir,
+                        ply_prefix=("" if len(surface_levels) == 1
+                                    else "level" + str(surface_level).replace('.', '')),
+                    )
+                    mv_filter_stats.append(mv_stats)
+                    surface_points = surface_points[keep_mask]
+                    surface_colors = surface_colors[keep_mask]
+                    surface_normals = surface_normals[keep_mask]
+                    CONSOLE.print(
+                        f"[mv_filter] surface_level {surface_level}: "
+                        f"{mv_stats['剔点前点数']} -> {mv_stats['剔点后点数']} points "
+                        f"(removed {mv_stats['剔除点数']}, rate {mv_stats['剔除率']:.4f})"
+                    )
+
                 if use_custom_bbox:
                     CONSOLE.print("Using provided bounding box.")
                     fg_bbox_min_tensor = torch.tensor(fg_bbox_min).to(sugar.device)
@@ -520,7 +567,12 @@ def extract_mesh_from_coarse_sugar(args):
                     o3d.io.write_triangle_mesh(sugar_mesh_path, decimated_o3d_mesh, write_triangle_uvs=True, write_vertex_colors=True, write_vertex_normals=True)
                     CONSOLE.print("Mesh saved at", sugar_mesh_path)
                     all_sugar_mesh_paths.append(sugar_mesh_path)
-                    
+
+            # ----- 阶段2a 改动: 落盘多视角剔点统计 (仅当开启) -----
+            if mv_filter and len(mv_filter_stats) > 0:
+                _stats_json, _stats_txt = write_filter_stats(mv_filter_stats, mesh_output_dir)
+                CONSOLE.print(f"[mv_filter] Stats saved at {_stats_json} and {_stats_txt}")
+
         else:
             CONSOLE.print("\nWARNING: Using centers of gaussians to extract mesh.")
             CONSOLE.print("Results will look bad, this is not the best way to extract a mesh.")
```

</details>

### 4.4 关于 `scripts/` 下的「基线副本」（不改仓库的另一条路径）

为在**不改动 SuGaR 仓库文件**的前提下复现基线，`scripts/` 下另有两份副本：

- `scripts/coarse_dn_trainer_param.py` = repo `sugar_trainers/coarse_density_and_dn_consistency.py` 的**逐字副本**，仅 2 处外科修改（`num_iterations`、`save_milestones` 改为可从 args 读；无该参数时行为与 repo 完全一致）。
- `scripts/coarse_mesh_savepts.py` = repo **原始** `sugar_extractors/coarse_mesh.py`（7c10c4a）的逐字副本 + 26 行纯 additive（`--surfpts_dir` 时另存表面采样点云）；`surfpts_dir=None` 时 mesh 输出与原始逐字节一致。

> 即：**基线**由 `scripts/` 副本产出（忠实于原始 7c10c4a）；**改动**（§4.1–4.3）由 `repo/SuGaR/extract_mesh.py --mv_filter True` 产出。两条路径在 `mv_filter=False` 时按设计一致（见 §5.4 说明）。

---

## 5. 逐步复现命令

**约定**：所有命令先 `cd /scratch/e1351071/zju_test_test && source env.sh`，随后用**相对路径**（相对工作目录）运行。`env.sh` 只激活环境、不 `cd`。seed 全链路固定 0（3DGS `safe_state` 内置 seed 0；wrapper 内 `torch/numpy/random/cuda manual_seed(0)`；`PYTHONHASHSEED=0`）。

### 5.1 冒烟（全链路连通性，`outputs/冒烟_truck/`）— 已 PASS

```bash
# (1) 3DGS 500 it
python repo/SuGaR/gaussian_splatting/train.py -s data/tandt/truck -m outputs/冒烟_truck/3dgs_500 \
    --iterations 500 --save_iterations 500 --test_iterations 500 --eval --quiet
# (2) coarse dn_consistency（num_iterations=7100 → 真实约 100 步，见 §7）
python scripts/run_coarse_dn.py -s data/tandt/truck -c outputs/冒烟_truck/3dgs_500 -i 500 \
    -o outputs/冒烟_truck/coarse --num_iterations 7100 --eval True
# (3) extract（surface_level 0.3, decim 20 万）+ 另存表面采样点云
python scripts/run_extract_mesh.py -s data/tandt/truck -c outputs/冒烟_truck/3dgs_500 -i 500 \
    -m outputs/冒烟_truck/coarse/sugarcoarse_3Dgs500_densityestim02_sdfnorm02/7100.pt \
    -l 0.3 -d 200000 -o outputs/冒烟_truck/mesh --surfpts_dir outputs/冒烟_truck/mesh --eval True
```

结果：三步 EXIT=0，产出可被 open3d 读取的 `.ply`（网格 V=174068 / F=326097）。全链路 PASS。

### 5.2 正式基线（`outputs/基线_truck/`）

```bash
# (1) 3DGS 7000 it —— 已完成（墙钟 118.6s；峰值显存 本进程组 6624 MiB / 全卡 6873 MiB）
python repo/SuGaR/gaussian_splatting/train.py -s data/tandt/truck -m outputs/基线_truck/3dgs_7k \
    --iterations 7000 --save_iterations 7000 --test_iterations 7000 --eval --quiet

# (2) coarse dn_consistency 15000 —— 已完成（墙钟 950.633s/15.84min；峰值显存 本组 10098 / 全卡 19726 MiB；末步 loss=0.0953，无 NaN）
#     num_iterations=15000 → 真实约 8000 步；dn_consistency 在 iter>9000 生效
python scripts/run_coarse_dn.py -s data/tandt/truck -c outputs/基线_truck/3dgs_7k -i 7000 \
    -o outputs/基线_truck/coarse --num_iterations 15000 --eval True
#   产物：outputs/基线_truck/coarse/sugarcoarse_3Dgs7000_densityestim02_sdfnorm02/15000.pt

# (3) extract mesh（surface_level 0.3；poisson_depth=10、vertices_density_quantile=0.1 为 repo 硬编码默认；
#     -d 为 decimation_target 目标顶点数，非 poisson_depth）+ 另存表面采样点云
#     —— 已完成（墙钟 359.079s/5.98min；峰值显存 本组 8274 / 全卡 15311 MiB）
python scripts/run_extract_mesh.py -s data/tandt/truck -c outputs/基线_truck/3dgs_7k -i 7000 \
    -m outputs/基线_truck/coarse/sugarcoarse_3Dgs7000_densityestim02_sdfnorm02/15000.pt \
    -l 0.3 -d 1000000 -o outputs/基线_truck/mesh --surfpts_dir outputs/基线_truck/mesh --eval True
```

> 计时封装（记录墙钟 + 峰值显存，产出 `计时_<阶段>.txt/.json`）：
> `bash scripts/eval/计时运行.sh <阶段名> <输出目录> --gpu 0 --interval 5 -- <上面的命令>`

**基线最终状态（2026-09-14，全部 EXIT=0；来源 `outputs/基线_truck/基线汇总.txt` 与 `notes/SELF_CHECK_阶段1.md` 11/11 PASS）**：

| 阶段 | 墙钟 | 峰值显存 本组/全卡 (MiB) | 产物 | 体积 |
|---|---|---|---|---|
| 3DGS 7000it | 118.633s (1.98min) | 6624 / 6873 | `3dgs_7k/point_cloud/iteration_7000/point_cloud.ply` | 437.85 MB |
| coarse dn 15000 | 950.633s (15.84min) | 10098 / 19726 | `coarse/sugarcoarse_3Dgs7000_densityestim02_sdfnorm02/`**`15000.pt`** | 286.41 MB |
| extract mesh | 359.079s (5.98min) | 8274 / 15311 | `mesh/sugarmesh_3Dgs7000_densityestim02_sdfnorm02_level03_decim1000000.ply` | 54.34 MB |
| **合计** | **1428.345s (23.81min)** | 全卡峰值 **19726** | 表面采样点云 全部/前景 | 486.38 / 360.17 MB |

- **基线 coarse ckpt**：`outputs/基线_truck/coarse/sugarcoarse_3Dgs7000_densityestim02_sdfnorm02/15000.pt`（286.41 MB；末步 `loss=0.0953`，无 NaN；num_iterations=15000 → 真实约 8000 步，dn_consistency 得约 6000 有效步）。
- **基线 mesh**：`outputs/基线_truck/mesh/sugarmesh_3Dgs7000_densityestim02_sdfnorm02_level03_decim1000000.ply`，**V=750841（trimesh 口径）/ 746704（open3d 口径，去未引用顶点，见 §7.5）**，**F=1437272**，连通分量 4851，最大分量面占比 0.4953，54.34 MB，open3d 可读、V>1e5、F>0。
- **表面采样点云**（供阶段2 改动对比）：全部 **10,000,197** 点（486.38 MB）、前景 **7,405,147** 点（360.17 MB）。
- **基线渲染指标（M1，32 测试视角，546×979）**：vanilla 3DGS(7k) PSNR **23.922** / SSIM **0.849** / LPIPS(vgg) **0.202**；coarse SuGaR（424177 高斯）PSNR **24.323** / SSIM **0.848** / LPIPS(vgg) **0.217**（来源 `outputs/基线_truck/评测/渲染指标_基线.txt`；LPIPS 用 SuGaR 内置 `lpipsPyTorch`(VGG)，非 pip `lpips`）。

### 5.3 改动：τ 扫描

改动通过**已修改的 `repo/SuGaR/extract_mesh.py`** 用 `--mv_filter True` 开启，**复用同一份 coarse 模型 `15000.pt`**（只重跑提取，无需重训）。实验矩阵（`plans/改动方案_多视角深度一致性剔点.txt`）——**三设置均已执行（阶段2c，EXIT=0）**：

| 设置 | `--mv_filter` | `--mv_tau` | 剔除率 | 状态 | 输出目录 |
|---|---|---|---|---|---|
| 基线 | False | —（等价 §5.2 提取或 §5.4） | —（未剔点） | 已完成 | `outputs/基线_truck/mesh/` |
| 改动-τ0.02 | True | 0.02 | 0.4494 | 已完成 | `outputs/改动_truck/改动_τ0.02/` |
| 改动-τ0.05 | True | 0.05 | 0.2549 | 已完成 | `outputs/改动_truck/改动_τ0.05/` |
| 改动-τ0.01 | True | 0.01 | 0.5920 | 已完成 | `outputs/改动_truck/改动_τ0.01/` |

其余提取参数（`surface_level=0.3`、`poisson_depth=10`、`vertices_density_quantile=0.1`、bbox）全部相同；剔点参数 `mv_min_consistent=2`、`mv_max_conflict=1`、`mv_n_ref_cams(M)=30`、`mv_n_votes(K)=0`（用全部 M）、`mv_seed=0`。

> **步骤1 先跑 filter-only 剔除率曲线**（不跑 Poisson，`outputs/改动_truck/τ曲线/`）：τ∈{0.005,0.01,0.02,0.05,0.10,0.20} → 剔除率 {0.7221, 0.5920, 0.4494, 0.2549, 0.1399, 0.0902}，**单调递减=是**（剪枝后高斯 280234，image_hw=(1070,1920)，参考相机索引 `[0,3,7,14,…,203,216]`，`n_never_in_view=27584`/0.28%）。判据「τ≤0.05 剔除率全部>60% 才追加第4个τ」实测仅 τ=0.005 超 60% → 不追加，按计划跑 τ=0.01/0.02/0.05。**全流程提取剔除率与该曲线逐位一致**（explorer=extraction）。

**命令模板**（`extract_mesh.py` 用仓库内相对导入，需在 `repo/SuGaR` 目录内运行；`-c` 因 `cameras.py` 字符串拼接需**结尾斜杠**，见 §7）：

```bash
# 以 τ=0.02 为例（其余 τ 改 --mv_tau 与输出目录即可）
( cd repo/SuGaR && python extract_mesh.py \
    -s "$SUGAR_ROOT/data/tandt/truck" \
    -c "$SUGAR_ROOT/outputs/基线_truck/3dgs_7k/" \
    -i 7000 \
    -m "$SUGAR_ROOT/outputs/基线_truck/coarse/sugarcoarse_3Dgs7000_densityestim02_sdfnorm02/15000.pt" \
    -l 0.3 -d 1000000 \
    -o "$SUGAR_ROOT/outputs/改动_truck/改动_τ0.02" \
    --mv_filter True --mv_tau 0.02 --mv_min_consistent 2 --mv_max_conflict 1 \
    --mv_n_ref_cams 30 --mv_n_votes 0 --mv_seed 0 --seed 0 --eval True )
#   产物：mesh .ply + 剔点统计.json/.txt + 表面点_剔点前.ply / 表面点_剔点后.ply + 计时_提取mesh_τ0.02.json/.txt
```

> **实际执行方式（`notes/RUNLOG_改动.md` 阶段2c 步骤2）**：三次全流程提取实际由等价 runner `scratchpad/run_extract_repo.py`（session scratchpad，未入项目）驱动——它与 `scripts/run_extract_mesh.py` **同 seeding、同自动补 `-c` 尾斜杠**，`import` 仓库改动版 `coarse_mesh.py` 并透传全部 `--mv_*`，效果等同上面的仓库原生命令。命令外套 `scripts/eval/计时运行.sh` 记录墙钟+峰值显存。`$SUGAR_ROOT` 由 `env.sh` 导出为工作目录绝对路径（因需在 `repo/SuGaR` 内运行，此处不用工作目录相对路径）。
>
> **τ 扫描实测结果（剔除率 / 剔点后点数 / mesh V/F / 提取墙钟；V 为 open3d 口径，见 §7.5）**：

| 设置 | τ | 剔除率 | 剔点前→剔点后点数 | mesh V | mesh F | 提取墙钟(s) | 峰值显存(本组/全卡 MiB) | 网格体积 |
|---|---|---|---|---|---|---|---|---|
| 基线 | — | —（未剔点） | 10,000,197 → —— | 746704 | 1437272 | 359.079 | 8274 / 15311 | 54.34 MB |
| 改动-τ0.05 | 0.05 | 0.2549 | 10,000,197 → 7,451,052 | 665745 | 1295321 | 287.621 | 8274 / 8283 | 48.56 MB |
| 改动-τ0.02 | 0.02 | 0.4494 | 10,000,197 → 5,506,389 | 574239 | 1121525 | 258.296 | 8274 / 8283 | 41.94 MB |
| 改动-τ0.01 | 0.01 | 0.5920 | 10,000,197 → 4,080,375 | 455839 | 890054 | 234.865 | 8274 / 8283 | 33.29 MB |

> 顶点/面数随剔除率单调下降；提取墙钟均 < 基线 359.079s（剔点后 fg/bg 点更少 → Poisson/decimation 更快，抵消过滤器一次性开销）。**过滤器额外耗时**（步骤1 explorer 实测）：一次性渲染 30 张深度图 0.3s + 单 τ 投票约 0.2s ≈ **0.5s**（占提取墙钟约 0.2%）。剔点统计（一致/冲突票直方图、参考相机索引）见各设置目录 `剔点统计.txt`。

### 5.4 基线 vs 改动 的公平对照

同一入口、`--mv_filter False` 可得到与基线逐位一致的提取（设计保证：改动全部在 `if mv_filter:` 内，关闭时该分支零执行、不消耗 RNG）。

**实测验证（阶段2a，`outputs/改动开发_临时/关_off*`；来源 `notes/RUNLOG_改动.md` 12:08/12:11、`notes/SELF_CHECK_阶段2a.md` 条目2/3 + 附录A）**：

- **表面点逐点一致**：`--mv_filter False` 的表面采样点（= 剔点前输入）与基线的 `表面采样点云_全部_level03.ply` 排序后 **`max_abs_diff=0.0`（value-identical=True）**，全部 **10,000,197** 点、前景 **6,185,860** 点计数完全相同 → 关闭时提取输入与基线**完全相同**。
- **mesh V/F 落在基线自身噪声地板内**：`--mv_filter False` mesh V=174079/F=326129 vs 基线 V=174068/F=326097，**ΔV=11(0.006%)/ΔF=32(0.010%)**；而「同码同 seed 跑两次 `--mv_filter False`」的 OFF#1 vs OFF#2 已达 **ΔV=10/ΔF=26** —— 该微差是 open3d Poisson/decimation **跨进程非确定性**的噪声地板（Poisson 前 fg/bg 顶点数三方完全一致 fg=1210595/bg=1017725；同点云 Poisson 跑两次 ΔV=ΔF=0），**非本改动引入**（详见 §7.5）。
- **基线（coarse 15k）模型上的佐证**：τ=0.01/0.02/0.05 三设置的 `表面点_剔点前.ply` 均为 **510,010,315 B、逐点相同**（同 seed 采样），与基线 `表面采样点云_全部_level03.ply` 同源同尺寸。

> 说明：README 原拟单独跑 `outputs/改动_truck/mesh_基线off/` 未执行；上述**等价验证已在阶段2a（冒烟流水线）完成并落盘**，因关闭分支与流水线无关（设计保证），结论对基线模型同样成立。

### 5.5 评测 M1–M6（`scripts/eval/`，产物 JSON + 中文键 txt + CSV）

单指标脚本（`--tag` 用于文件名，如 `基线` / `改动_tau0.02`）：

```bash
# M1 渲染指标（测试视角 PSNR/SSIM/LPIPS）
python scripts/eval/m1_render_metrics.py --source_path data/tandt/truck \
    --gs_output outputs/基线_truck/3dgs_7k --iteration 7000 \
    --coarse_pt outputs/基线_truck/coarse/sugarcoarse_3Dgs7000_densityestim02_sdfnorm02/15000.pt \
    --out_dir report/评测 --tag 基线 --save_renders

# M2 几何（mesh↔参考点云 双向距离 + Chamfer + F-score@τ）
python scripts/eval/m2_geometry.py \
    --mesh outputs/基线_truck/mesh/<基线 mesh>.ply \
    --ref_a outputs/基线_truck/3dgs_7k/point_cloud/iteration_7000/point_cloud.ply \
    --ref_b_colmap data/tandt/truck/sparse/0/points3D.bin \
    --cameras_json outputs/基线_truck/3dgs_7k/cameras.json \
    --out_dir report/评测 --tag 基线

# M3 拓扑/网格质量（V/F/E、连通分量、非流形边、边界边/孔洞、自交、水密…）
python scripts/eval/m3_topology.py --mesh outputs/基线_truck/mesh/<基线 mesh>.ply \
    --out_dir report/评测 --tag 基线

# M4 覆盖率 / 漏洞率（pytorch3d 光栅化 mesh vs 3DGS 前景）
python scripts/eval/m4_coverage.py --source_path data/tandt/truck \
    --gs_output outputs/基线_truck/3dgs_7k --iteration 7000 \
    --mesh outputs/基线_truck/mesh/<基线 mesh>.ply --out_dir report/评测 --tag 基线

# M5 效率（汇总计时 JSON + mesh V/F + 文件体积）
python scripts/eval/m5_efficiency.py \
    --timing_json outputs/基线_truck/计时/计时_训练3DGS_7k.json outputs/基线_truck/计时/计时_coarse_dn_15k.json \
    --mesh outputs/基线_truck/mesh/<基线 mesh>.ply \
    --extra_files outputs/基线_truck/3dgs_7k/point_cloud/iteration_7000/point_cloud.ply \
    --out_dir report/评测 --tag 基线

# M6 可视化（网格截图 / 误差热图 / 连通分量着色 / 渲染对比拼图；默认 matplotlib CPU 后端）
python scripts/eval/m6_visualize.py --mode all --mesh outputs/基线_truck/mesh/<基线 mesh>.ply \
    --ref data/tandt/truck/sparse/0/points3D.bin --out_dir report/评测/图 --tag 基线
```

一键汇总 + baseline vs 改动 对比（推荐用配置文件，结构见 `scripts/eval/tests/示例_评测配置.json`）：

```bash
python scripts/eval/run_all_eval.py --config <评测配置.json>
#   产物：汇总_全部指标.json、汇总_对比表.csv、汇总_对比表.txt + 各指标 <指标>_<tag>.{json,txt,csv}
```

单元测试（改动逻辑，CPU，不占 GPU）：

```bash
python scripts/tests/test_mv_filter.py      # 或 pytest scripts/tests/test_mv_filter.py -q
```

**评测已完成（M1–M6，基线 + 三个 τ；来源 `outputs/改动_truck/评测/汇总对照表.txt/.csv` 与 `outputs/基线_truck/评测/`）**。M2 参考点云同时用 3DGS 高斯中心（refA，同源）与 COLMAP 稀疏点（refB，干净但稀疏）两份；四变体同参数、同 `scene_scale=13.339236`、同 crop_bbox、refB=136029 点（公平性核验 PASS）。**V/F/连通分量等为 open3d 读入口径**（open3d 合并/去未引用顶点，故基线 V=746704 略小于 trimesh 的 750841；各行同口径可横向对比，见 §7.5）。

**M1–M6 数值汇总表**（M1 渲染四变体相同——coarse 未变、只重跑提取；其余按 τ 对比）：

| 指标 | 基线 | 改动 τ0.05 | 改动 τ0.02 | 改动 τ0.01 | 方向 |
|---|---|---|---|---|---|
| 剔除率 | —（未剔点） | 0.2549 | 0.4494 | 0.5920 | τ↓ 剔越多 |
| **M1** coarse PSNR / SSIM / LPIPS(vgg) | 24.323 / 0.848 / 0.217 | （同基线） | （同基线） | （同基线） | 恒等 |
| **M1** 3DGS(7k) PSNR / SSIM / LPIPS | 23.922 / 0.849 / 0.202 | （同基线） | （同基线） | （同基线） | 恒等 |
| **M2** Chamfer_A / _B | 0.032554 / 0.053072 | 0.028663 / 0.045498 | 0.024184 / 0.038975 | 0.023020 / 0.036104 | 单调↓（更好） |
| **M2** 完整度均值_A / _B | 0.049502 / 0.081905 | 0.038882 / 0.064770 | 0.028556 / 0.050015 | 0.024089 / 0.041887 | 单调↓（漂浮点被剔） |
| **M2** 精度均值_A / _B | 0.015605 / 0.024239 | 0.018445 / 0.026226 | 0.019812 / 0.027935 | 0.021951 / 0.030322 | 单调↑（真实点离网更远） |
| **M2** F@0.01_A / _B | 0.946422 / 0.887707 | 0.960590 / 0.920410 | 0.976476 / 0.949495 | 0.982014 / 0.963159 | 单调↑（更好） |
| **M3** 连通分量数 | 4851 | 3279 | 2690 | 2261 | 单调↓（更好） |
| **M3** 最大分量占比 | 0.4953 | 0.5812 | 0.4883 | 0.4728 | — |
| **M3** 边界边数 / 孔洞数 | 96544 / 7970 | 68205 / 6206 | 54647 / 5480 | 44848 / 4598 | 单调↓ |
| **M3** 非流形边 / 水密 | 0 / 否 | 0 / 否 | 0 / 否 | 0 / 否 | — |
| **M3** V / F（open3d） | 746704 / 1437272 | 665745 / 1295321 | 574239 / 1121525 | 455839 / 890054 | 单调↓ |
| **M4** 网格覆盖率 | 0.928911 | 0.814760 | 0.710219 | 0.633240 | 单调↓（过剔伤覆盖） |
| **M4** 漏洞率(前景) | 0.066585 | 0.180472 | 0.285647 | 0.363446 | 单调↑（过剔伤覆盖） |
| **M5** 提取墙钟(s) | 359.079 | 287.621 | 258.296 | 234.865 | 剔越多越快 |
| **M5** 峰值显存(提取, MiB) | 8274 | 8274 | 8274 | 8274 | — |
| **M5** 网格体积(MiB) | 54.338 | 48.559 | 41.938 | 33.286 | 单调↓ |

- **M6 可视化**：网格截图 / 误差热图（另含四变体**统一色标** `[0.0198,2.3958]`、同视角）/ 连通分量着色 / 渲染对比 / 覆盖掩码，见 `outputs/改动_truck/评测/图*` 与 `考核提交/可视化/`。
- **独立复算（盲验）**：不 import 评测代码，对 τ=0.02 mesh 复算 V/F/连通分量/最大分量占比/Chamfer_B/完整度_B/精度_B，与评测 JSON **相对误差 0.0000%（逐位一致）**。
- **完整列**（含 F@0.005/F@0.02、剔点后点数等）见 `outputs/改动_truck/评测/汇总对照表.csv`。

**单元测试 `scripts/tests/test_mv_filter.py` 通过记录**（`source env.sh && CUDA_VISIBLE_DEVICES="" python scripts/tests/test_mv_filter.py`，**6/6 PASS，EXIT=0**，纯 CPU 不占 GPU；环境未装 pytest → 用独立 runner）：

```
PASS  test_vote_arithmetic
PASS  test_compute_keep_mask
PASS  test_sample_reference_cameras_deterministic
PASS  test_sampler_matches_sugar          # 采样器与 SuGaR.get_points_depth_in_depth_map 逐元素 allclose
PASS  test_sphere_kept_floaters_removed    # sphere_keep_frac=1.0, f1_remove_frac=1.0, f2_remove_frac=1.0,
                                           # sphere_mean_consistent=8.3877, f1_mean_conflict=2.5053
PASS  test_conflict_vote_is_used
6/6 passed
```

（合成球面点保留 100%>95%、两组漂浮点剔除 100%>95%，均超断言阈值；仅一条 `grid_sample align_corners` 的无害 UserWarning。）

---

## 6. 输出与交付物说明

### 6.1 命名与格式约定（项目强制）

- **所有实验产物（目录、图片、网格、数据文件）一律中文命名**，如 `outputs/基线_truck/`、`表面点_剔点前.ply`、`渲染对比_基线_vs_改动.png`。
- **所有数值结果除 JSON/CSV 外，都另存一份 `.txt`（人类可读、中文键名）**，如计时 `计时_<阶段>.{json,txt}`、剔点 `剔点统计.{json,txt}`、评测 `<指标>_<tag>.{json,txt,csv}`。

### 6.2 `outputs/`（实验工作区）

| 子目录 | 内容 |
|---|---|
| `outputs/冒烟_truck/` | 冒烟全链路：`3dgs_500/`、`coarse/`、`mesh/`（含 `表面采样点云_全部/前景_level03.ply`）、`计时/` |
| `outputs/基线_truck/` | 正式基线：`3dgs_7k/`、`coarse/sugarcoarse_3Dgs7000_densityestim02_sdfnorm02/15000.pt`、`mesh/`（`sugarmesh_…_level03_decim1000000.ply` V=750841/F=1437272 + `表面采样点云_{全部,前景}_level03.ply`）、`计时/`、`评测/`（M1–M6 基线）、`基线汇总.{txt,json}` |
| `outputs/改动开发_临时/` | 改动开发期临时产物（阶段2a 冒烟：`关_off`、`关_off2`、`开_on`、`开_on_tau03`） |
| `outputs/改动_truck/` | τ 扫描（阶段2c）：`τ曲线/`（剔除率曲线）、`改动_τ{0.01,0.02,0.05}/`（各含 mesh + `剔点统计.{json,txt}` + `表面点_剔点{前,后}.ply` + `计时_提取mesh_τX.{json,txt}`）、`评测/`（M2–M6 + `汇总对照表.{json,csv,txt}` + `图/` + `图_统一色标/`）、`计时/` |

### 6.3 `考核提交/`（面向考核方的交付物）

从 `outputs/` **复制**（不移动、不删除），全部中文命名。**实际内容（`find 考核提交 -type f`，共 117 文件；快照 2026-09-14 14:11，打包仍在进行中，数量可能继续增长）**：

```
考核提交/
├── 网格/   (6)   # 基线_truck_coarse网格.ply；基线_truck_表面采样点云_{全部,前景}.ply；
│                 #   改动_truck_τ{0.01,0.02,0.05}_网格.ply
├── 指标/   (53)  # 渲染/几何/拓扑/覆盖/效率指标_{基线,改动_τ0.01,改动_τ0.02,改动_τ0.05}.{json,txt}；
│                 #   剔除率曲线.{json,txt}；基线汇总.{json,txt}；汇总对照表.{json,csv,txt}；
│                 #   汇总_对比表.{csv,json,txt}；汇总_全部指标.json；评测汇总_基线.{json,txt}；
│                 #   逐视角 CSV（渲染/覆盖）；评测日志.txt
├── 可视化/ (57)  # 网格截图/误差热图/连通分量着色_{基线,改动_τ*}.png；渲染对比_基线_视角*.png；
│                 #   图_统一色标/（基线+3改动，共享色标）；覆盖掩码_{基线,改动_τ*}/；剔除率_随τ变化.png；
│                 #   对比图/（阶段2e：网格渲染/点到面误差热图/连通分量着色_{基线,改动}_视角{1,2,3} + 指标对照表.{csv,json,txt}）
└── 日志/   (1)   # RUNLOG_基线.md
```

> **状态：已从 `outputs/` 复制填充**（快照 117 文件；基线交付于阶段1、改动 τ0.01/0.02/0.05 交付于阶段2c、`可视化/对比图/` 由阶段2e 补充）。因本节点有并发会话正在继续打包，`考核提交/` 文件数以运行时 `find 考核提交 -type f | wc -l` 为准。
> **两点如实说明**：① `考核提交/` 内**暂无 `report.pdf`**（报告在 `report/` 下，尚未复制入 `考核提交/`）；② `考核提交/日志/` 目前**仅含 `RUNLOG_基线.md`**（`RUNLOG_改动.md`、`ENV.md`/`COMMITS.md` 仍在 `notes/`，未复制入 `考核提交/日志/`）。二者按需在最终打包时补齐。

---

## 7. 失败记录与已知问题

> 均来自 `notes/RUNLOG_基线.md`、`notes/RUNLOG_改动.md` 与各 `SELF_CHECK`/stage 日志，如实记录，未隐藏。

### 7.1 环境 / 编译

1. **setuptools 必须回退到 69.5.1**：初装 84.0.0 与 torch 2.4.1 的 `torch.utils.cpp_extension` 编译流程不兼容，导致两个 CUDA 扩展无法编译。
2. **编译子模块须 `--no-build-isolation`**：`simple-knn` / `diff-gaussian-rasterization` 的 `setup.py` 顶层 `import torch`，构建隔离环境缺 torch 会失败。
3. **numpy 必须固定 `<2`（1.26.4）**：pytorch3d / open3d / pymeshlab 均按 numpy 1.x ABI 构建；装 pytorch3d wheel 时用 `--no-deps` 防止带回 numpy≥2。
4. **无活跃 git submodule（vendored）**：`gaussian_splatting` 等被内嵌为普通文件，`git submodule update --init --recursive` 无对象可更新（也无需执行）。各组件版本随 SuGaR commit 冻结（详见 `notes/COMMITS.md` 的 [DEVIATION]）。

### 7.2 SuGaR trainer 的行为陷阱（非 bug，是仓库设计）

5. **`num_iterations` 是「最终迭代计数器」而非「真实步数」**：coarse trainer 从 `iteration = 7000 − 1` 起计，主循环 `if iteration >= num_iterations: break`。故**真实优化步数 = `num_iterations − 7000`**（默认 15000 → 约 8000 步）。
   - `num_iterations` **必须 > 7000**，否则一步都不执行、`loss` 未赋值 → `UnboundLocalError`（冒烟第一次用 300 即撞此，非 bug）。
   - 正则起点均为**绝对迭代号**：entropy 7000→9000、dn_consistency **>9000** 才生效、sdf >9000。故 `num_iterations` 越接近 9000，dn_consistency 有效步数越少（9000 时≈0 步）；正式基线用 15000 使 dn_consistency 得约 6000 步。
6. **3DGS 输出目录路径需结尾斜杠**：`sugar_scene/cameras.py:34` 用 `open(gs_output_path + 'cameras.json')` 字符串拼接（唯一一处），路径无尾斜杠会得 `.../3dgs_7kcameras.json` 的 `FileNotFoundError`。
   - **基线经 `scripts/run_coarse_dn.py` / `run_extract_mesh.py` 已自动补尾斜杠**；**直接调用 `repo/SuGaR/extract_mesh.py`（τ 扫描）时 `-c` 必须自带结尾斜杠**（见 §5.3）。
7. **SuGaR 各 trainer 无随机 seed**：3DGS 的 `safe_state` 固定 seed 0，但 SuGaR trainer 本身不设 seed；wrapper 已固定 torch/numpy/random/cuda seed，但 CUDA `atomicAdd` 仍有轻微非确定性 → coarse 训练存在 run-to-run 微差（已在报告说明）。

### 7.3 与计划不符处（[DEVIATION]）

8. **`extract_mesh.py` 的 CLI 与计划初稿不符**：计划初稿写 `-d 10 -q 0.1`；实际 `extract_mesh.py` **无 `-q`**，且 `-d` 是 **decimation_target（目标顶点数）**——`-d 10` 会把网格抽简到 10 个顶点。计划**意图**的 `poisson_depth=10` 与 `vertices_density_quantile=0.1` 恰为 `coarse_mesh.py` 硬编码默认，无需 flag。替代：`-l 0.3` + `-d 1000000`（SuGaR high_poly 默认，>1e5 验收线）。
9. **仓库根 `metrics.py` 不可直接用**：硬编码 refined(mesh+gaussian) 模型 + vanilla 30k/7k 双 ckpt；本项目不跑 refine、3DGS 只到 7k，故自写 `scripts/eval/M1–M6`（仅复用 `psnr/ssim/lpips`）。
10. **题目所述「SuGaR 用 DTU Chamfer」不成立**：核对 arXiv 后，SuGaR 只报 PSNR/SSIM/LPIPS（Mip-NeRF360 + T&T + DeepBlending，无 DTU）。故几何评测改用「伪参考几何」（3DGS 高斯中心 / COLMAP 稀疏点）+ 网格拓扑统计。
11. **任务提到的 `cleaning_quantile` 在本 commit 不存在**：该参数属 Frosting（SuGaR 后续工作），非 7c10c4a。

### 7.4 运行 / 工具

12. **提取阶段较慢、前台易超时**：冒烟提取墙钟约 286s，前台 120s 超时后转后台完成（EXIT=0）。建议提取一律用 `nohup ... &` + 日志文件或计时封装后台运行。
13. **open3d `OffscreenRenderer` 在本节点（无 EGL）会硬崩溃**：M6 可视化默认改用 matplotlib CPU 后端（大网格先抽取到约 4 万面）；pytorch3d 后端可选但占显存，与训练竞争时慎用。
14. **冒烟表面采样点云体积巨大**：`表面采样点云_全部_level03.ply` 约 1000 万点 / 487 MB；正式基线同理，注意磁盘与后续读取内存。

### 7.5 工程层面已知问题（README 专属，不进 `report/`）

> 以下为工程/工具口径的事实性说明，只影响复现与数字口径、不影响方法与结论；按项目约定不写入报告，仅留此处备查。来源：`notes/RUNLOG_基线.md`、`notes/RUNLOG_改动.md`、`notes/SELF_CHECK_阶段{1,2a,2c}.md`、各 `评测/*.json`。

15. **open3d Poisson→抽简（decimation）存在跨进程微小非确定性（ΔV≈10）**：同一份表面点云、同代码、同 seed，两次 `--mv_filter False` 全流程提取得到的最终 mesh 顶点/面数并不逐位相等——实测 OFF#1 V=174079/F=326129 vs OFF#2 V=174069/F=326103，**ΔV=10、ΔF=26**（0.006%/0.008%，冒烟规模）。已定位：**Poisson 表面重建进程内确定**（同点云跑两次 ΔV=ΔF=0）、**表面点逐点相同**（`max_abs_diff=0.0`）、**Poisson 前 fg/bg 顶点数三方完全一致**（fg=1210595/bg=1017725），微差只出现在下游 open3d `simplify_quadric_decimation` 的多线程调度上。这是「`--mv_filter False` 与基线 V/F 的 ΔV≤11」的**噪声地板**，与本改动无关（改动在其上游、关闭时零执行）。**与条目7 不同**：条目7 是 coarse 训练期 CUDA `atomicAdd` 的非确定性，本条是提取期 open3d 的非确定性。
16. **`-c`（3DGS 输出目录）必须结尾带斜杠**（另见 §7.2 条目6）：`sugar_scene/cameras.py:34` 用 `open(gs_output_path + 'cameras.json')` 字符串拼接（全仓库唯一一处），无尾斜杠会得 `.../3dgs_7kcameras.json` 的 `FileNotFoundError`。基线走 `scripts/run_*` wrapper 已自动补 `os.sep`；**τ 扫描直接调用 `repo/SuGaR/extract_mesh.py` 时 `-c` 需自带尾斜杠**（如 `.../3dgs_7k/`），本项目 τ 扫描的等价 runner `run_extract_repo.py` 也内置补斜杠。
17. **coarse `num_iterations` 是「最终迭代计数器」，从 iter=7000 起算**（另见 §7.2 条目5）：主循环从 `iteration = 7000−1` 开始、`if iteration >= num_iterations: break`，故**真实优化步数 = `num_iterations − 7000`**（15000 → 约 8000 步）。`num_iterations` **必须 > 7000**（否则一步不跑、`loss` 未赋值 → `UnboundLocalError`）；且正则起点是**绝对迭代号**（entropy 7000→9000、dn_consistency/sdf **>9000**），故 15000 使 dn_consistency 得约 6000 有效步。读到「15000.pt」不要误解为 15000 个训练步。
18. **大网格自交检测会超时并跳过**：M3 拓扑评测的自交对数（self-intersection）用 `self_intersect_timeout=120`s 上限；本项目所有 mesh（基线 74 万顶点 + 各 τ）自交检测均**超时跳过 → 记为 `自交对数=None`**（`汇总对照表.csv`/`拓扑指标_*.json` 中 `自交对数=None`）。这是有意的时间预算保护，非检测失败；水密性（否）、非流形边（0）等其余拓扑量正常给出。
19. **本节点无 EGL，M6 可视化用 matplotlib CPU 后端**（另见 §7.4 条目13）：open3d `OffscreenRenderer` 在本机（无 EGL）硬崩溃，故网格截图/热图默认走 matplotlib CPU（大网格先抽取到约 4 万面）；误差热图另提供**统一色标** `[0.0198, 2.3958]` 版本（`图_统一色标/`，四变体同色标同视角 `[(20,−60),(15,60),(75,−90)]`）以便基线 vs 改动直接对比。pytorch3d 后端可选但占显存，与训练竞争时慎用。
20. **open3d 与 trimesh 的顶点计数口径不同**：同一 mesh，**trimesh 报原始顶点数、open3d 合并重复/去未引用顶点后计数更小**——基线 mesh **V=750841（trimesh）vs 746704（open3d），差 4137**；F 两者一致（1437272）。**§5.5 的 M1–M6 汇总表、`汇总对照表` 全部用 open3d 口径**（`m3_topology.py` 读入口径，各行同口径可横向对比）；**`基线汇总.txt`/`notes/RUNLOG_基线.md`/`SELF_CHECK_阶段1` 用 trimesh 口径**（750841）。独立复算 τ=0.02：open3d V=574239（与评测一致）、trimesh V=576377。引用顶点数时务必注明口径。

---

*本 README 由执行者按计划撰写，随实现推进更新；截至 2026-09-14 原有 10 处【待补】已全部回填（回填来源逐项见 `notes/SELF_CHECK_README回填.md`）。信息来源核对表见 `notes/SELF_CHECK_README.md`。*
