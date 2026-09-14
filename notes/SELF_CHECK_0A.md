# SELF_CHECK_0A.md — 阶段 0A（下载代码与数据）自检

- 执行者: opus48-executor (claude-opus-4-8[1m], effort max)
- 计划: /scratch/e1351071/zju_test_test/plans/SuGaR考核总计划.txt （阶段 0A）
- 工作目录: /scratch/e1351071/zju_test_test （所有产物仅在此目录内）
- 机器约束遵守: 无 conda / 无 curl / 无 unzip → 用 wget 下载、python zipfile 解压；未安装任何 python 包；未删除任何文件。
- 开始时间: 2026-09-14 11:08:17 (+0000)
- 结束时间: 2026-09-14 11:12:59 +0000
- **本阶段总耗时: 282 秒 (~4 分 42 秒)**（其中 git 递归 clone + 校验约 约 30-60s（含 2259 文件检出）；数据下载 51s（12.8 MB/s）；解压 8.7s）

---

## 1. 仓库路径与各 commit
- SuGaR 仓库路径: `/scratch/e1351071/zju_test_test/repo/SuGaR`
- SuGaR: remote=`https://github.com/Anttwo/SuGaR.git`, branch=`main`, commit=`7c10c4ae4a267dece512f5c7f40ed212a0a2ab44` (2024-09-24 12:14:40 -0400, "Minor fix.")
- 子模块结构说明: 该版本把 gaussian_splatting / diff-gaussian-rasterization / simple-knn / glm **全部内嵌为普通文件**（0 个 gitlink，无活跃 submodule），故各组件版本随 SuGaR commit 冻结；glm 内嵌版本 = GLM 0.9.9.9（.gitmodules 记录 url https://github.com/g-truc/glm.git）。详见 `/scratch/e1351071/zju_test_test/notes/COMMITS.md`。

## 2. 数据路径与每场景图像数
- 数据源: `https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/datasets/input/tandt_db.zip`（3DGS 官方，未触发切换到备用数据集）
- zip 路径: `/scratch/e1351071/zju_test_test/data/tandt_db.zip`（682,628,995 B ≈ 651 MiB，wget -c 完整下载，测试 testzip=None 无损坏）
- 解压方式: python zipfile extractall → `/scratch/e1351071/zju_test_test/data/`

| 场景 | 路径 | #images | sparse/0 | sparse/0 内容 |
|------|------|---------|----------|----------------|
| tandt/truck (计划要求) | `/scratch/e1351071/zju_test_test/data/tandt/truck` | 251 | 有 | cameras.bin, images.bin, points3D.bin, project.ini |
| db/playroom (计划要求) | `/scratch/e1351071/zju_test_test/data/db/playroom` | 225 | 有 | cameras.bin, images.bin, points3D.bin, project.ini |
| tandt/train (附带) | `/scratch/e1351071/zju_test_test/data/tandt/train` | 301 | 有 | cameras.bin, images.bin, points3D.bin, project.ini |
| db/drjohnson (附带) | `/scratch/e1351071/zju_test_test/data/db/drjohnson` | 263 | 有 | cameras.bin, images.bin, points3D.bin, project.ini |

图像格式: 均为 .jpg，位于各场景 `images/` 目录；每个场景均含 COLMAP 稀疏重建 `sparse/0`（含 cameras.bin/images.bin/points3D.bin），可直接用于 3DGS 训练。

---

## 3. 验收条目（逐条 PASS/FAIL + 复算命令）

| # | 验收条目 | 期望 | 实际 | 结果 | 复算命令 |
|---|----------|------|------|------|----------|
| A1 | SuGaR 仓库已 clone | 存在且 CLONE_EXIT=0 | 存在，exit 0 | PASS | `ls /scratch/e1351071/zju_test_test/repo/SuGaR/train.py` |
| A2 | 记录 SuGaR commit + URL | 有 hash+URL | 7c10c4ae..., Anttwo/SuGaR.git | PASS | `git -C /scratch/e1351071/zju_test_test/repo/SuGaR rev-parse HEAD; git -C /scratch/e1351071/zju_test_test/repo/SuGaR remote -v` |
| A3 | diff-gaussian-rasterization 源码齐全 | .cu+setup.py+cuda_rasterizer | 齐全 | PASS | `ls /scratch/e1351071/zju_test_test/repo/SuGaR/gaussian_splatting/submodules/diff-gaussian-rasterization/{setup.py,rasterize_points.cu,cuda_rasterizer}` |
| A4 | simple-knn 源码齐全 | .cu+setup.py | 齐全 | PASS | `ls /scratch/e1351071/zju_test_test/repo/SuGaR/gaussian_splatting/submodules/simple-knn/{setup.py,simple_knn.cu,spatial.cu}` |
| A5 | glm 头文件齐全（编译依赖） | glm.hpp 存在, .hpp>0 | glm.hpp 存在, 277 个 .hpp | PASS | `ls /scratch/e1351071/zju_test_test/repo/SuGaR/gaussian_splatting/submodules/diff-gaussian-rasterization/third_party/glm/glm/glm.hpp; find /scratch/e1351071/zju_test_test/repo/SuGaR/gaussian_splatting/submodules/diff-gaussian-rasterization/third_party/glm -name '*.hpp' | wc -l` |
| A6 | COMMITS.md 已写 | 存在 | 存在(56 行) | PASS | `cat /scratch/e1351071/zju_test_test/notes/COMMITS.md` |
| A7 | tandt_db.zip 完整无损 | testzip=None, 大小匹配日志 | None, 682628995 B (=日志 saved 值) | PASS | `python3 -c "import zipfile;print(zipfile.ZipFile('/scratch/e1351071/zju_test_test/data/tandt_db.zip').testzip())"` |
| A8 | data/tandt/truck 存在 | 目录存在 | 存在 | PASS | `ls -d /scratch/e1351071/zju_test_test/data/tandt/truck` |
| A9 | data/db/playroom 存在 | 目录存在 | 存在 | PASS | `ls -d /scratch/e1351071/zju_test_test/data/db/playroom` |
| A10 | truck 图像计数 | >0 | 251 | PASS | `ls /scratch/e1351071/zju_test_test/data/tandt/truck/images | wc -l` |
| A11 | playroom 图像计数 | >0 | 225 | PASS | `ls /scratch/e1351071/zju_test_test/data/db/playroom/images | wc -l` |
| A12 | truck 有 sparse/0 + COLMAP bins | cameras/images/points3D.bin | 三者齐全 | PASS | `ls /scratch/e1351071/zju_test_test/data/tandt/truck/sparse/0` |
| A13 | playroom 有 sparse/0 + COLMAP bins | cameras/images/points3D.bin | 三者齐全 | PASS | `ls /scratch/e1351071/zju_test_test/data/db/playroom/sparse/0` |
| A14 | 未安装任何 python 包 | 无 pip install | 未执行任何安装 | PASS | 本会话无 pip/安装命令（见执行日志） |
| A15 | 未删除任何文件 | 无删除 | 无删除 | PASS | 本会话无 rm/删除命令（见执行日志） |
| A16 | 所有产物在工作目录内 | 仅 /scratch/e1351071/zju_test_test | 是 | PASS | `ls /scratch/e1351071/zju_test_test/{repo,data,notes}` |

结论: 阶段 0A 全部条目 PASS（16/16）。

---

## 4. [DEVIATION] 列表
1. **子模块结构与计划假设不符（不影响进度）**: 计划假定 gaussian_splatting/diff-gaussian-rasterization/simple-knn 为 git submodule 并各有独立 commit；实际该 SuGaR 版本(7c10c4a)将其全部内嵌为普通文件（0 gitlink）。`--recursive` clone 已把全部源码（含 glm 0.9.9.9）拉全，编译所需文件 100% 就绪；`git submodule update --init --recursive` 无对象可更新、无需执行。COMMITS.md 已据实记录内嵌版本 + 可核实上游出处，替代"逐子模块 commit hash"。
2. 数据源无切换: 官方 tandt_db.zip 下载 51s 完成（12.8 MB/s），远快于计划的 10 分钟阈值，未触发切换到 Mip-NeRF360 garden 的备用方案。

## 5. 未做/交由后续阶段
- 未安装/未编译任何 python 包与 CUDA 扩展（按计划归属阶段 0B，由环境负责人处理）。本阶段仅确认源码齐备。
