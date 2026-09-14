# SELF_CHECK_README.md — README.md 信息来源核对表

- 撰写对象：`/scratch/e1351071/zju_test_test/README.md`
- 核对时间：2026-09-14 12:05 (+0000)
- 原则：README 每条事实性陈述都能追溯到本目录内的来源文件或可复算命令；未产出的结果一律标 **【待补】**，不编造。
- 范围与约束：只在 `/scratch/e1351071/zju_test_test` 内读写；未改任何代码、未改 `report/`、未删文件、未 git commit。

## A. 逐节来源核对

| # | README 条目 | 来源 / 复算 | 结果 |
|---|---|---|---|
| 1 | 项目一句话简介、目录结构 | 顶层 `ls`；`plans/SuGaR考核总计划.txt`；`plans/改动方案_多视角深度一致性剔点.txt` | PASS（目录树逐项对照实际 `find` 输出） |
| 2 | 机器/系统表（H200、驱动 575.57.08、sm_90、nvcc 12.1、gcc 11.4、12 核/2TB） | `notes/ENV.md` §1–2 | PASS（逐字取自 ENV.md） |
| 2 | torch 2.4.1+cu121 / torchvision 0.19.1 / pytorch3d 0.7.8 / 两个 CUDA 扩展 | `notes/ENV.md` §4；`notes/pip_freeze.txt`；`notes/env_check.json` | PASS |
| 2 | numpy 1.26.4(<2)、open3d 0.18.0、pymeshlab 2025.7.post1 等 | `notes/ENV.md` §5；`notes/pip_freeze.txt` | PASS |
| 2 | 环境自检 7/7 PASS、光栅化 GPU OK | `notes/env_check.json`（pass=7,total=7,all_pass=true）；`notes/ENV.md` §6 | PASS |
| 2 | 起始 commit `7c10c4ae…`（短 7c10c4a），vendored 无活跃 submodule | `notes/COMMITS.md`；`git rev-parse HEAD` = 7c10c4ae4a267dece512f5c7f40ed212a0a2ab44 | PASS（HEAD 实测一致） |
| 2 | 安装步骤（venv/torch cu121/扩展编译/pytorch3d wheel/setuptools 回退/--no-build-isolation） | `notes/ENV.md` §7；`scripts/build_ext.sh` | PASS（命令逐条对照 ENV.md §7 与 build_ext.sh） |
| 3 | 数据 URL `repo-sam.inria.fr/.../tandt_db.zip`、682628995 B、testzip=None | `notes/SELF_CHECK_0A.md` L19–20,44；`data/tandt_db_download.log` L1,末行 | PASS |
| 3 | truck 251 图；train 301；playroom 225；drjohnson 263 | `ls data/*/*/images | wc -l` 实测 | PASS（本次实测：251/301/225/263） |
| 3 | truck llffhold=8 → 219 训 / 32 测 | `notes/RUNLOG_基线.md` §3-A；`notes/_stage0D_log.txt`（truck 251/219/32）；算术 251−⌈251/8⌉=219,32 | PASS |
| 4 | 改动文件清单（3 个）+ git status | `git status --short`（M extract_mesh.py, M coarse_mesh.py, ?? mv_consistency_filter.py） | PASS（实测一致） |
| 4 | numstat：extract +20/−2（-w +18/0）、coarse +54/−2（-w +52/0） | `git diff --numstat` 与 `--numstat -w` 实测 | PASS（已据实测修正初稿的 22/56） |
| 4 | mv_consistency_filter.py 366 行 | `wc -l` 实测 = 366 | PASS |
| 4 | 4 处「删除」均为行尾空白、无行为删除 | `git diff | grep '^-'` 全为空白行；`git diff -w` = 0 删除 | PASS |
| 4 | 各处改动说明（接口/算法/参数/默认关闭/落盘/先例） | `repo/SuGaR/sugar_extractors/mv_consistency_filter.py`（docstring 与实现）；`extract_mesh.py`、`coarse_mesh.py` diff | PASS（逐条对照源码与 diff） |
| 4 | 内联 git diff（extract+coarse）+ 链接 README_snapshot.patch | `git diff` 输出 verbatim；`notes/diffs/README_snapshot.patch`（本次生成，505 行/28K） | PASS（内联块与实测 diff 逐字一致） |
| 4.4 | scripts/ 基线副本（trainer 2 处外科改、coarse_mesh 逐字+26 additive） | `notes/RUNLOG_基线.md` §1.3；`scripts/coarse_dn_trainer_param.py`、`scripts/coarse_mesh_savepts.py` 头部 docstring | PASS |
| 5.1 | 冒烟命令 + 结果（EXIT0，mesh V=174068/F=326097） | `notes/RUNLOG_基线.md` §步骤2 冒烟结果；`outputs/冒烟_truck/计时/*.json` | PASS |
| 5.2 | 3DGS 7k 命令 + 118.6s/6624/6873MiB | `outputs/基线_truck/计时/计时_训练3DGS_7k.json` 实测 | PASS |
| 5.2 | coarse 15k 命令、真实约 8000 步、dn_consistency>9000 | `notes/RUNLOG_基线.md` §1.4,§2[关键发现-1] | PASS（命令与语义一致） |
| 5.2 | 基线 extract 命令（-l 0.3 -d 1000000 + surfpts） | `notes/RUNLOG_基线.md` §1.4；`scripts/run_extract_mesh.py` argparse | PASS（命令依赖 15000.pt，标【待补】） |
| 5.2 | 基线现状：3DGS 完成/coarse 进行中(≈iter10000)/mesh 待补 | 本次 `ps`+`logs/基线_coarse_15k.log`（末行 Iteration:10000）+ `find …coarse -name '*.pt'`（空） | PASS（如实标注进行中 + 待补） |
| 5.3 | τ 扫描矩阵与命令模板、需在 repo 内运行、-c 结尾斜杠 | `plans/改动方案_…txt` 实验矩阵；`repo/SuGaR/extract_mesh.py` argparse（mv_* 实测存在）；`notes/RUNLOG_基线.md`[关键发现-2] | PASS（明确标注「命令为计划形式，尚未执行；指标待补」） |
| 5.5 | M1–M6 与 run_all 用法（--tag/--mesh/--ref_* 等） | `scripts/eval/m1..m6_*.py`、`run_all_eval.py` 的 docstring 与 argparse 实读 | PASS（参数逐一对照脚本 argparse） |
| 5.5 | 单元测试 test_mv_filter.py（球面>95%/漂浮>95%） | `scripts/tests/test_mv_filter.py` 断言实读（L194–196） | PASS（存在性/断言；**通过记录未见 → 结果标【待补】**） |
| 6 | 中文命名 + json/txt 双份约定 | `plans/SuGaR考核总计划.txt`【用户补充规则】；实际产物（计时/剔点/评测）双份 | PASS |
| 6 | outputs/ 子目录内容 | `find outputs` 实测 | PASS |
| 6 | 考核提交/ 结构约定 + 当前为空 | `plans/SuGaR考核总计划.txt`【用户决定】；`ls 考核提交/`（空） | PASS（标【待补】） |
| 7 | 失败/已知问题 14 条 | `notes/RUNLOG_基线.md`、`notes/RUNLOG_改动.md`、`notes/COMMITS.md`、`notes/_stage0C_log.txt`、`notes/_stage0D_log.txt`、`notes/SELF_CHECK_0B.md` | PASS（每条可溯源，见下 §B） |

## B. §7 失败记录逐条溯源

| 条 | 来源 |
|---|---|
| 1 setuptools 84→69.5.1 | `notes/ENV.md` §3 备注 |
| 2 --no-build-isolation | `notes/ENV.md` §3 备注 / §7 |
| 3 numpy 固定 <2 | `notes/ENV.md` §5 |
| 4 无活跃 submodule | `notes/COMMITS.md` [DEVIATION] |
| 5 num_iterations 语义/UnboundLocalError/正则阈值 | `notes/RUNLOG_基线.md` §2[关键发现-1] |
| 6 cameras.py:34 结尾斜杠 | `notes/RUNLOG_基线.md` §2[关键发现-2]；`run_coarse_dn.py`/`run_extract_mesh.py` 修复说明 |
| 7 SuGaR trainer 无 seed / atomicAdd 非确定性 | `notes/_stage0D_log.txt`；`scripts/run_coarse_dn.py` docstring |
| 8 extract CLI -d/-q 不符 | `notes/RUNLOG_基线.md` §1.2 [DEVIATION-1-1] |
| 9 metrics.py 不可直接用 | `notes/_stage0D_log.txt` [DEVIATION-0D-2]；`scripts/eval/m1_render_metrics.py` docstring |
| 10 SuGaR 未用 DTU Chamfer | `notes/_stage0D_log.txt` [DEVIATION-0D-1] |
| 11 cleaning_quantile 属 Frosting | `notes/_stage0C_log.txt` [DEVIATION] |
| 12 提取慢/前台超时转后台 | `notes/RUNLOG_基线.md` §2 extract(smoke)；`outputs/冒烟_truck/计时/计时_冒烟_extract.json`（286.286s） |
| 13 open3d OffscreenRenderer 崩溃→matplotlib | `scripts/eval/m6_visualize.py` docstring |
| 14 表面采样点云体积大（约1000万点/487MB） | `notes/RUNLOG_基线.md` §2 冒烟结果 |

## C. 交付物

| 文件 | 状态 |
|---|---|
| `README.md`（中文，7 节，含折叠 diff + 待补标注） | 已完成 |
| `notes/diffs/README_snapshot.patch`（完整 diff：已跟踪修改 + 新增文件全文，505 行/28K，标快照时间） | 已生成（未改 git 状态） |
| `notes/SELF_CHECK_README.md`（本表） | 已完成 |

## D. 待补清单（README 中已显式标注 `【待补】` 的项）

1. 基线 coarse `15000.pt`（进行中，≈iter10000/15000）。
2. 基线 mesh 提取产物（顶点/面数）。
3. τ 扫描（0.01/0.02/0.05）实际运行、各设置剔除率与 mesh V/F。
4. 基线 vs 改动 `--mv_filter False` 逐位一致性的实际验证。
5. 基线与改动的 M1–M6 评测数值与对比表。
6. `test_mv_filter.py` 的实际通过记录。
7. `考核提交/` 目录填充。

## E. 未做 / 边界声明

- 未运行任何训练/提取/评测/测试（本任务仅撰写 README + 核对表 + 生成 diff 快照）；未干扰正在运行的基线 coarse 进程。
- 未修改 `repo/SuGaR` 下任何代码、未修改 `report/`、未删除任何文件、未执行 git add/commit。
- README 内 τ 扫描命令为「计划形式」，其中 `extract_mesh.py --mv_*` 参数已在源码 argparse 中实测存在，但该命令本身尚未执行。
