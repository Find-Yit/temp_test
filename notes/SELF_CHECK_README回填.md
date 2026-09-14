# SELF_CHECK_README回填.md — README.md 10 处【待补】回填核对表

- 对象：`/scratch/e1351071/zju_test_test/README.md`
- 回填时间：2026-09-14（+0000）
- 范围与约束：只在 `/scratch/e1351071/zju_test_test` 内读写；**未改任何代码、未改 `report/`、未删文件、未 git commit**。本次仅改 `README.md`、更新 `notes/diffs/README_snapshot.patch` 快照、新增本核对表。
- 原则：每处回填的数字都可追溯到本目录内的落盘文件（CSV/JSON/TXT）或可复算命令；不编造。

---

## A. 逐处回填 → 来源（README 原有 10 处【待补】）

> 说明：`grep -o 待补 README.md` 原为 11 处 = 1 处「约定描述」（顶部说明"凡尚未产出结果标【待补】"）+ **10 处真实占位**。下表覆盖这 10 处；顶部描述句已改写为"10 处已全部回填"。

| # | README 位置（回填前） | 回填内容（要点） | 主来源 | 复算 / 证据 |
|---|---|---|---|---|
| 1 | §1 目录树 `考核提交/ …【待补】` | 改为引用 §6.3 清单（网格/指标/可视化/日志） | `find 考核提交 -type f` | 计数以运行时 `find 考核提交 -type f \| wc -l` 为准（并发会话仍在打包） |
| 2 | §5.2 (3) extract 命令注释 `【待补，依赖 .pt】` | 已完成：提取墙钟 359.079s、峰值 8274/15311 MiB | `outputs/基线_truck/基线汇总.txt`、`计时/计时_提取mesh.json` | `grep 提取mesh outputs/基线_truck/基线汇总.txt` |
| 3 | §5.2 基线状态块 `15000.pt、基线 mesh、基线指标 均【待补】` | coarse `15000.pt`(286.41MB)、mesh V=750841(trimesh)/746704(o3d) F=1437272、表面点 1000万/740万、M1 PSNR/SSIM/LPIPS、三阶段墙钟/显存表 | `基线汇总.txt`、`notes/RUNLOG_基线.md` §3、`notes/SELF_CHECK_阶段1.md`(11/11)、`评测/渲染指标_基线.txt` | `cat outputs/基线_truck/基线汇总.txt` |
| 4 | §5.3 τ 扫描 `命令为计划形式尚未执行 … 均【待补】` | 三设置已执行；命令模板(在 repo/SuGaR 内运行、`-c` 尾斜杠)+实际 runner 说明+剔除率曲线+剔除率/剔点后/V/F/墙钟/显存/体积表 | `notes/RUNLOG_改动.md` 阶段2c、`outputs/改动_truck/τ曲线/剔除率曲线.txt`、`outputs/改动_truck/评测/汇总对照表.{txt,csv}` | `cat outputs/改动_truck/评测/汇总对照表.csv` |
| 5 | §5.4 `--mv_filter False … 验证结果【待补】` | 表面点逐点一致(max_abs_diff=0.0, 10,000,197)、mesh ΔV=11/ΔF=32 落在噪声地板(OFF#1 vs OFF#2 ΔV=10)、基线模型佐证(剔点前 510,010,315 B 逐点相同) | `notes/RUNLOG_改动.md` 12:08/12:11、`notes/SELF_CHECK_阶段2a.md` 条目2/3+附录A | `sed -n '/12:08/,/12:13/p' notes/RUNLOG_改动.md` |
| 6a | §5.5 `基线 M1–M6 与改动对比 均【待补】` | M1–M6 数值汇总表(基线+τ0.05/0.02/0.01)+M6 图说明+独立复算 0.0000% | `outputs/改动_truck/评测/汇总对照表.{txt,csv}`、`outputs/基线_truck/评测/评测汇总_基线.txt` | `cat outputs/改动_truck/评测/汇总对照表.txt` |
| 6b | §5.5 `test_mv_filter.py 未见通过记录 结果【待补】` | 6/6 PASS、EXIT=0（6 条测试名 + sphere/floater 数值） | 本次实跑：`CUDA_VISIBLE_DEVICES="" python scripts/tests/test_mv_filter.py` | 同左（输出 `6/6 passed`, exit 0） |
| 7 | §6.2 `outputs/基线_truck/ … mesh/【待补】` | mesh 文件名+V/F、表面采样点云、评测/、基线汇总 | `ls outputs/基线_truck/`、`基线汇总.txt` | `ls outputs/基线_truck/mesh/` |
| 8 | §6.2 `outputs/改动_truck/ … 【待补】` | τ曲线/、改动_τ{0.01,0.02,0.05}/(各7文件)、评测/、计时/ | `ls -R outputs/改动_truck/` | `find outputs/改动_truck -maxdepth 2 -type d` |
| 9 | §6.3 `考核提交/ 为空【待补】` | 已复制（快照 117 文件：网格6/指标53/可视化57/日志1，含阶段2e `对比图/`）+ 如实说明无 report.pdf、日志仅 RUNLOG_基线；标注并发打包中、计数以运行时为准 | `find 考核提交 -type f` | `find 考核提交 -type f \| wc -l`（快照 117） |
| 10 | 顶部说明句「凡尚未产出结果标【待补】」 | 改写为「10 处【待补】已全部回填为落盘实测数字」 | 本核对表 | `grep -c 待补 README.md`（仅剩 1 处为此描述句） |

（§5.5 一行含 2 个【待补】，拆为 6a/6b；连同其余 8 处 = 10 处。）

## B. 关键回填数字（抽样，均逐位取自落盘文件）

- **基线三阶段**（`基线汇总.txt`）：3DGS 7k 118.633s(6624/6873)；coarse 15k 950.633s(10098/19726)；extract 359.079s(8274/15311)；合计 1428.345s，全卡峰值 19726 MiB。
- **基线 mesh**：`sugarmesh_3Dgs7000_densityestim02_sdfnorm02_level03_decim1000000.ply`，V=**750841**(trimesh)/**746704**(open3d)，F=**1437272**，连通分量 4851，最大分量占比 0.4953，54.34 MB。
- **表面采样点云**：全部 10,000,197 点(486.38MB)、前景 7,405,147 点(360.17MB)。
- **M1（四变体相同）**：3DGS(7k) 23.922/0.849/0.202；coarse SuGaR(424177 高斯) 24.323/0.848/0.217（LPIPS 用 lpipsPyTorch/VGG）。
- **τ 扫描**（`汇总对照表.csv`，V 为 open3d 口径）：

  | 设置 | 剔除率 | 剔点后 | V | F | 提取墙钟s | 体积MiB |
  |---|---|---|---|---|---|---|
  | 基线 | — | — | 746704 | 1437272 | 359.079 | 54.338 |
  | τ0.05 | 0.2549 | 7451052 | 665745 | 1295321 | 287.621 | 48.559 |
  | τ0.02 | 0.4494 | 5506389 | 574239 | 1121525 | 258.296 | 41.938 |
  | τ0.01 | 0.5920 | 4080375 | 455839 | 890054 | 234.865 | 33.286 |

- **剔除率曲线（filter-only）**：τ 0.005/0.01/0.02/0.05/0.10/0.20 → 0.7221/0.5920/0.4494/0.2549/0.1399/0.0902（单调递减=是）。
- **单测**：6/6 PASS、EXIT=0（`test_vote_arithmetic`/`test_compute_keep_mask`/`test_sample_reference_cameras_deterministic`/`test_sampler_matches_sugar`/`test_sphere_kept_floaters_removed`(sphere_keep=1.0,f1_remove=1.0,f2_remove=1.0,sphere_mean_consistent=8.3877,f1_mean_conflict=2.5053)/`test_conflict_vote_is_used`）。

## C. `notes/diffs/README_snapshot.patch` 更新为最新快照（并核对与 README 内联 diff 一致）

- 重新从 `repo/SuGaR` 当前 `git diff` 生成（HEAD=`7c10c4a` 未变；`git status`：`M extract_mesh.py` / `M sugar_extractors/coarse_mesh.py` / `?? mv_consistency_filter.py`）。
- `git diff --numstat`：extract_mesh.py +20/−2、coarse_mesh.py +54/−2（`-w` 后 +18/0、+52/0）；共 74 insertions / 4 deletions（4 处删除全为行尾空白）。与 README §4.1 表一致。
- 新文件 `mv_consistency_filter.py`：366 行，md5=`33b356a66256fbad32b4bb8603a43437`（未变）。
- **一致性核对（byte-level）**：
  - README §4.3 内联折叠 diff（extract+coarse，122 行）`diff` 新快照对应段 → **逐字一致（无差异）**。
  - README §4.3 内联 diff `diff` 当前 `git diff`（tracked）→ **逐字一致**。
  - 快照新文件段 `+` 内容 `diff` 当前文件 → **逐字一致**。
- 快照头时间戳更新为 `2026-09-14 13:57 (+0000)`，并注明"实现已完成、git diff 稳定"。README §4 快照说明句同步更新。

## D. §7.5「工程层面已知问题」新增 6 条 → 来源（README 专属，不进 report）

| 条 | 事实 | 来源 |
|---|---|---|
| 15 | open3d Poisson→抽简跨进程微小非确定性 ΔV≈10（OFF#1 174079/326129 vs OFF#2 174069/326103；Poisson 前 fg/bg 三方一致；同点云 Poisson 两次 Δ=0） | `notes/SELF_CHECK_阶段2a.md` 附录A、`notes/RUNLOG_改动.md` 12:11/12:23 |
| 16 | `-c` 尾斜杠（`cameras.py:34` 字符串拼接，唯一一处） | `notes/RUNLOG_基线.md` §2[关键发现-2]；另见 §7.2 条目6 |
| 17 | coarse `num_iterations` 从 7000 起算（真实步=num−7000，须>7000，正则阈值为绝对迭代号） | `notes/RUNLOG_基线.md` §2[关键发现-1]；另见 §7.2 条目5 |
| 18 | 大网格自交检测超时跳过 → `自交对数=None`（`self_intersect_timeout=120`） | `outputs/改动_truck/评测/汇总对照表.csv`(非流形边=0/自交=None)、`拓扑指标_*.json`、`notes/SELF_CHECK_阶段2c.md` §二 |
| 19 | 无 EGL → matplotlib CPU 渲染；统一色标 [0.0198,2.3958] | `scripts/eval/m6_visualize.py` docstring、`notes/SELF_CHECK_阶段2c.md` §五[M6色标]；另见 §7.4 条目13 |
| 20 | open3d vs trimesh 顶点计数口径（746704 vs 750841，差 4137；F 同 1437272） | `outputs/改动_truck/评测/汇总对照表.txt` 表头说明、`notes/SELF_CHECK_阶段2c.md` §五[口径说明] |

## E. 验证 / 审计记录

- `grep -c 待补 README.md` = 1（仅剩顶部"已全部回填"描述句），10 处真实占位已清零。
- 单测本次实跑：`6/6 passed`、退出码 0（纯 CPU）。
- 快照 diff 与 README 内联 diff、当前 git diff 三方 byte-level 一致（见 §C）。
- 数字抽样复算：基线 mesh V/F、τ 扫描 V/F/剔除率/墙钟/体积、M1、三阶段墙钟/显存均与源文件逐位一致（见 §B）。

## F. 边界声明（未做 / 未改）

- **未改任何代码**（`repo/SuGaR` 现有文件、`scripts/`、`hyvideo/` 等均未动；HEAD=7c10c4a 未变，无新 git 提交）。
- **未改 `report/`**、**未删除任何文件**。
- 本次只：改 `README.md`（回填 10 处 + 新增 §7.5 + 更新 §4 快照说明 + 顶部快速复现，见 README 顶部）、重生成 `notes/diffs/README_snapshot.patch`（内容与旧快照 diff 体一致，仅刷新头部时间戳/说明）、新增本文件。
- τ 扫描的实际执行 runner 为 session scratchpad 内 `run_extract_repo.py`（未入项目）；README 记录的是其等价的仓库原生命令（`cd repo/SuGaR && python extract_mesh.py … -c ".../3dgs_7k/"`），并已注明实际 runner 与等价性来源（`notes/RUNLOG_改动.md` 阶段2c）。
- README 原拟单独目录 `outputs/改动_truck/mesh_基线off/` 未生成；`--mv_filter False` 逐位一致的等价验证已在阶段2a 冒烟完成并落盘，README §5.4 如实标注。
- `考核提交/` 内暂无 `report.pdf`、`日志/` 仅 `RUNLOG_基线.md`，README §6.3 如实标注（未替考核方补齐打包）。
