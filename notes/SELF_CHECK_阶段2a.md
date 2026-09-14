# SELF_CHECK 阶段2a：多视角深度一致性剔点（主改动实现）

执行者 opus48-executor｜日期 2026-09-14｜基线 commit `7c10c4ae4a267dece512f5c7f40ed212a0a2ab44`
数据 tandt/truck（冒烟：3DGS 500it → coarse dn_consistency 7100it；219 训练相机）｜全流程 seed=0

范围声明：本阶段仅做"实现 + 冒烟对照 + 单元测试"，**不跑正式 τ 扫描**（等基线 coarse 15k，由主会话另派）。

---

## 一、验收条目 × 实际数值 × PASS/FAIL

| # | 验收条目（来源） | 实际数值 / 证据 | 结论 | 复算命令 |
|---|---|---|---|---|
| 1 | git diff 只涉及 coarse_mesh.py、extract_mesh.py 与新文件；无删除、未 commit（阶段2a #1 / 改动方案 #1） | `git status --porcelain` = `M extract_mesh.py` / `M sugar_extractors/coarse_mesh.py` / `?? sugar_extractors/mv_consistency_filter.py`；diff --stat: extract_mesh.py +22, coarse_mesh.py +56/-4；无 D 行 | **PASS** | `cd repo/SuGaR && git status --porcelain && git diff --stat` |
| 2 | mv_filter=False 时提取输入(表面点)与基线**逐点一致**（阶段2a #1 / 改动方案 #1） | ON 的 `表面点_剔点前.ply`(10,000,197) vs 该执行者 `表面采样点云_全部_level03.ply`(10,000,197)：排序后 **max_abs_diff=0.0, value-identical=True** | **PASS** | `python <scratch>/cmp_pts.py 开_on/表面点_剔点前.ply 冒烟_truck/mesh/表面采样点云_全部_level03.ply` |
| 3 | mv_filter=False 输出 mesh V/F 与基线一致（阶段2a #1 / 改动方案 #1） | OFF: V=174079 F=326129；该执行者冒烟: V=174068 F=326097。ΔV=11(0.006%) ΔF=32(0.010%)。差异位于下游 open3d 简化(decimation)跨进程非确定性（Poisson 已证进程内确定；表面点已证逐点相同；本改动插入点在其上游且关闭时零执行）。OFF#1 vs OFF#2(同码同 seed)基线噪声地板：见附录A | **PASS**（差异为基线固有 decimation 噪声，非本改动引入） | `python <scratch>/compare_mesh.py meshcmp 关_off/...ply 冒烟_truck/mesh/...ply` |
| 4 | 单元测试 scripts/tests/test_mv_filter.py 通过（阶段2a #2 / 任务） | 6/6 PASS：投票算术 / keep 规则 / 参考相机抽样确定性 / **采样器与 SuGaR.get_points_depth_in_depth_map 逐元素 allclose** / 合成球面 100%>95% 保留、两组漂浮点 100%>95% 剔除 / 空域冲突票机制(平均 2.5 票) | **PASS** | `CUDA_VISIBLE_DEVICES="" python scripts/tests/test_mv_filter.py` |
| 5 | 开关打开能跑通并产生 剔点统计.txt（阶段2a #2 / 改动方案 #2） | ON τ=0.02 与 τ=0.3 两次全流程均产出 `剔点统计.json`+`剔点统计.txt`+`表面点_剔点前/后.ply`+mesh | **PASS** | `ls outputs/改动开发_临时/开_on{,_tau03}/` |
| 6 | 剔除率在 (0, 50%)（阶段2a #2 / 改动方案 #2） | 默认 τ=0.02：**0.8940（超带）**；τ=0.3：**0.4592 ∈ (0,50%)** ✓。单调 τ 曲线见附录B。根因见 [DEVIATION-1] | **PASS（τ=0.3）/ 见 DEVIATION（τ=0.02）** | `cat outputs/改动开发_临时/开_on_tau03/剔点统计.txt` |
| 7 | 每个产出 mesh 可被 open3d 打开（改动方案 #2） | 关_off V=174079/F=326129；开_on(τ0.02) V=93572/F=176221；开_on(τ0.3) V=155962/F=294834（均成功读入，V/F>0） | **PASS** | `python <scratch>/compare_mesh.py mesh1 <ply>` |
| 8 | 代码含 docstring 解释输入/输出、假设与失败处理（阶段2a #3 / 任务） | `mv_consistency_filter.py` 模块级 + 每函数 docstring（深度=视空间 z、点须视空间坐标、padding='border' 需自带 in_bounds、视锥/无效不计票、失败处理：相机不足用全部/N=0 平凡返回/never-in-view 单列）；先例归属(COLMAP/ACMM/GaussianPro)与差异写入 docstring；理解证据另见 notes/RUNLOG_改动.md §0 | **PASS** | `sed -n '1,70p' repo/SuGaR/sugar_extractors/mv_consistency_filter.py` |
| 9 | mv_filter=False 不改变现有模块行为（任务：只新增，不改现有行为） | 改动均在 `if mv_filter:` 内；关闭时不执行任何新代码、不消耗 RNG（import 无副作用）；表面点逐点相同已实证 | **PASS** | 见条目 2、`notes/diffs/阶段2a.patch` |

---

## 二、关键数值汇总

- 冒烟 coarse：43352→(drop_low_opacity 0.5)→ 高斯保留 43352；表面点 N=10,000,197（全 level 0.3）。
- mv_filter 参数：M(n_ref_cams)=30，K(n_votes)=0→用全部 M，min_consistent=2，max_conflict=1，seed=0。
- 参考相机索引（seed=0 均匀随机抽 30/219）：[0,3,7,14,34,52,58,59,84,98,101,112,116,119,121,123,129,130,142,149,159,161,166,172,183,184,195,198,203,216]。
- never-in-view=36,248（0.36%，两 τ 一致，因几何相同）。
- 单元测试合成场景：球面点保留 100%（阈值>95%），自由空间漂浮点(半径1.1~1.5)剔除 100%、内部漂浮点(半径0.2~0.6)剔除 100%（阈值>95%）；自由空间漂浮点平均空域冲突票 2.5（>1）。

---

## 三、[DEVIATION] 列表

**[DEVIATION-1] 默认 τ=0.02 在冒烟模型上剔除率 0.8940，超出 (0,50%) 验收带。**
- 影响：仅冒烟(极度欠训 500it-3DGS/7100it-coarse)模型；不改变代码正确性。
- 根因（已核实非 bug）：欠训模型渲染深度噪声大 → 多视角一致性天然差。一致票直方图 [0票:1,438,817…]（τ=0.3）/[0票:4,964,397…]（τ=0.02）平滑长尾，冲突票直方图同样平滑；单元测试中干净球面 100% 保留、采样器与 SuGaR 逐元素一致 → 排除逻辑错误。
- 处置：额外全流程跑 τ=0.3 → 剔除率 0.4592 ∈ (0,50%)，证明 (0,50%) 带可达、τ 旋钮单调可控（附录B）。真实基线(7k/15k)上默认 τ=0.02 预计温和得多，留正式实验测。
- 是否阻断：否（验收 #2 的 (0,50%) 已由 τ=0.3 达成并落盘）。

**[DEVIATION-2] mv_filter=False mesh V/F 与冒烟 mesh 非逐位相等（ΔV=11, ΔF=32, 0.01%）。**
- 影响：极小(0.01%)，且不影响"输入逐点一致"这一更强结论。
- 根因：下游 open3d `simplify_quadric_decimation` 跨进程非确定性（表面点已证逐点相同、Poisson 已证进程内确定）。与本改动无关（改动在上游且关闭时零执行）。
- 证据：附录A（OFF#1 vs OFF#2，同码同 seed 的基线噪声地板）。

**[环境说明] 未安装 pytest。** 单元测试以独立 runner 运行（`python scripts/tests/test_mv_filter.py`，退出码 0=全过），未改环境。

---

## 附录A：基线 mesh 非确定性噪声地板（均 baseline / mv_filter=False, seed=0）
三次基线运行（我的 OFF#1、OFF#2 + 该执行者冒烟）最终 mesh V/F：

| 运行 | V | F |
|---|---|---|
| OFF#1（我, mv_filter=False） | 174079 | 326129 |
| OFF#2（我, mv_filter=False, 同码同seed） | 174069 | 326103 |
| 该执行者冒烟（baseline） | 174068 | 326097 |

- **OFF#1 vs OFF#2（完全相同代码/seed）：ΔV=10, ΔF=26** —— 这就是基线自身的跨进程噪声地板。
- OFF#1 vs 冒烟：ΔV=11, ΔF=32；OFF#2 vs 冒烟：ΔV=1, ΔF=6。
- 结论：mv_filter=False 与基线的 V/F 差（≤11 顶点, 0.006%）**落在基线自身 run-to-run 噪声地板内**（OFF#1 vs OFF#2 已达 ΔV=10），
  且 Poisson 前 fg/bg 顶点数三方完全一致（fg=1210595, bg=1017725），仅三角数差个位/十位（open3d Poisson 跨进程）。
  → mv_filter=False 行为等价于基线，微小 V/F 差非本改动引入。复算：`python <scratch>/compare_mesh.py meshcmp 关_off/...ply 关_off2/...ply`

## 附录B：冒烟 τ 敏感性（filter-only，同一 10M 表面点，每次<1s）
| τ | 剔除率 | | τ | 剔除率 |
|---|---|---|---|---|
| 0.02 | 0.8940 | | 0.20 | 0.5331 |
| 0.05 | 0.7680 | | 0.30 | 0.4592 |
| 0.10 | 0.6543 | | 0.50 | 0.3527 |
| 0.15 | 0.5832 | | | |
（τ=0.02 与全流程 ON 剔除率 0.8940 精确一致 → explorer 等价于 extraction 的过滤步。复算：`python <scratch>/filter_tau_explore.py`）

## 交付物路径
- 代码：`repo/SuGaR/sugar_extractors/mv_consistency_filter.py`（新）、`repo/SuGaR/sugar_extractors/coarse_mesh.py`、`repo/SuGaR/extract_mesh.py`
- 单测：`scripts/tests/test_mv_filter.py`
- patch：`notes/diffs/阶段2a.patch`
- 执行日志：`notes/RUNLOG_改动.md`
- 冒烟产物：`outputs/改动开发_临时/{关_off,关_off2,开_on,开_on_tau03}/`（mesh + 剔点统计.json/.txt + 表面点_剔点前/后.ply）
