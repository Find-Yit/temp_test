# RUNLOG 改动（阶段 2a：多视角深度一致性剔点）

执行者：opus48-executor。开始时间 2026-09-14 11:47。
只在 /scratch/e1351071/zju_test_test 内操作；不删文件；不 git commit。
基线 commit：`7c10c4ae4a267dece512f5c7f40ed212a0a2ab44`（提取前 `git status` 干净）。

---

## 0. 精读源码后的关键假设（实现前先写清，作为"能解释输入输出与关键假设"的证据）

### 0.1 深度是 z 还是距离？—— 是**相机视空间的 z 坐标**（不是欧氏距离）

`sugar_scene/sugar_model.py: render_depth_and_normal`（2343-2387）返回
`depth_img, normal_img`。其中深度通道来自：

```python
dn_features[..., 0] = p3d_camera.get_world_to_view_transform().transform_points(self.points)[..., 2:3]
...
depth_img = dn_img[..., 0]
```

即把每个高斯中心变换到 PyTorch3D 视空间后取 **z 分量**作为"颜色"用高斯光栅化器渲染。
所以 `depth_img[u,v]` = 在该像素处、沿视线累积渲染出的**视空间 z**（PyTorch3D 约定：相机朝 +z 看，
z 越大越远）。**不是相机到点的欧氏距离**。背景（无高斯覆盖）像素 = `bg_color[0]`，本函数默认 `bg_color=[0,0,0]`，
故背景深度 = 0 → 可用 `z_map > eps` 判无效。

同一约定在 trainer 中复用：`sugar_trainers/coarse_density_and_dn_consistency.py:689,703,725` 都用
`get_world_to_view_transform().transform_points(pts)[..., 2]` 当深度。

### 0.2 `get_points_depth_in_depth_map(fov_camera, depth, points_in_camera_space)` 的输入输出与像素索引顺序

源码（`sugar_model.py` 1349-1364）：

```python
depth_view = depth.unsqueeze(0).unsqueeze(-1).permute(0, 3, 1, 2)   # (1,1,H,W)
pts_projections = fov_camera.get_projection_transform().transform_points(points_in_camera_space)  # NDC
factor = -1 * min(H, W)
pts_projections[...,0] = factor / W * pts_projections[...,0]   # -> grid_sample x (对应宽 W)
pts_projections[...,1] = factor / H * pts_projections[...,1]   # -> grid_sample y (对应高 H)
grid = pts_projections[...,:2].view(1,-1,1,2)
map_z = grid_sample(depth_view, grid, mode='bilinear', padding_mode='border')[0,0,:,0]
```

- **输入 `points_in_camera_space`**：世界点经 `fov_camera.get_world_to_view_transform().transform_points(points)`
  得到的**视空间坐标**（注意：不是世界坐标；trainer 里 `gaussian_centers_in_camera_space` 就是这么算的，
  见 723-726 行）。
- **输入 `depth`**：形如 (H,W) 的渲染深度图（视空间 z）。
- **输出 `map_z`**：形如 (N,) 的每点在其投影像素处采样到的渲染深度（视空间 z）。
- **像素索引顺序**：grid_sample 的 grid 最后一维是 (x, y)=(宽方向, 高方向)；代码把投影 x→宽、y→高，
  与 depth (H,W) 的 permute 对齐。`padding_mode='border'` → **落在视锥/画幅外的点会采样到边界值**，
  因此本改动必须自行加"在画幅内"掩码，否则画幅外的点会拿到伪深度而误投票。

### 0.3 一点 p 相对相机 c 的自身深度 z_p 与投影像素

```python
pcs = fov_camera.get_world_to_view_transform().transform_points(points)  # (N,3) 视空间
z_p = pcs[..., 2]                                                        # (N,) 视空间 z
z_map = sugar.get_points_depth_in_depth_map(fov_camera, depth_c, pcs)    # (N,) 渲染深度
```

投影到画幅内的判据（复刻 0.2 的投影公式，仅为求"是否在画幅内"）：
`u = -min(H,W)/W * proj_x`, `v = -min(H,W)/H * proj_y`；in_bounds = |u|<=1 且 |v|<=1。

### 0.4 视锥外 / 无效深度不计票

点 p 对相机 c **有效**当且仅当：
`z_p > fov_camera.znear`（在相机前方；znear 默认 1e-4，见 cameras.py:226,244）
且 in_bounds（投影落在画幅内）
且 `z_map > eps`（该像素确有高斯渲染，背景深度=0 视为无效）。
只有有效的相机才对该点计票。

### 0.5 投票判据（相对深度差 + 投票，出处 COLMAP/ACMM/GaussianPro，见 notes/先例核实.md §一.B）

对每个有效相机 c：
- **一致票**：`|z_p - z_map| < tau * z_map`（相对深度差 < tau，等价 COLMAP `max_depth_error`）。
- **空域冲突票**：`z_p < z_map - tau*z_map`（点浮在已观测表面之前的自由空间里 → 漂浮物/背景壳特征）。
- 其余（`z_p > z_map*(1+tau)`，被遮挡/在表面之后）：不计票（该相机看不到它，属正常遮挡，不惩罚）。
- 一致票与空域冲突票互斥（若 z_p < z_map*(1-tau) 则 |z_p-z_map| > tau*z_map，必不一致）。

**保留规则**：`一致票 >= mv_min_consistent(默认2)` 且 `空域冲突票 <= mv_max_conflict(默认1)`。

### 0.6 参考相机抽样

从全部训练相机中用固定 seed 均匀随机抽 M=mv_n_ref_cams(默认30) 个（`numpy.random.default_rng(seed).choice(ncam, M, replace=False)` 后排序）。
若 ncam<=M 则用全部。默认 `mv_n_votes=0` → 每点用全部 M 个参考相机投票；
若 0<mv_n_votes<M → 每点用固定 seed 逐点随机抽 mv_n_votes 个参考相机的票（可选模式）。

### 0.7 插入位置（不破坏默认行为）

`sugar_extractors/coarse_mesh.py`：在每个 surface_level 拿到
`surface_points/surface_colors/surface_normals`（336-338 行）之后、fg/bg 包围盒分离（340 行起）之前，
`if mv_filter:` 内调用过滤器，得到 keep_mask，对上述三者切片。**mv_filter=False 时该分支完全不执行 → 输出与基线逐位一致。**
参数经 `extract_mesh.py` argparse 透传，coarse_mesh.py 用 `_cfg(args,name,default)` 读取（兼容 argparse.Namespace 与 train.py 的 AttrDict(dict)，缺省即基线行为）。

### 0.8 规模与内存

单个 surface_level 的表面点 N ≈ n_total_points(1e7) / 训练相机数 × 相机数 ≈ 1e7（fg/bg 分离与统计离群点剔除之前）。
投票对点分块（默认 2e6/块），深度图先渲染缓存到 CPU（30 张 (H,W) float ≈ 60MB），投票时逐相机搬回 GPU。
GPU 峰值 = 模型 + 1 张深度图 + 1 块点投影，远 < 15GB，不干扰同机基线训练。

---

## 1. 执行步骤日志

### 11:47 提取前 git 审计
- `cd repo/SuGaR && git status` 干净；HEAD=7c10c4ae4a267dece512f5c7f40ed212a0a2ab44。
- 已备份原始 coarse_mesh.py（git show HEAD）用于对拍。

### 11:48-11:53 实现
- 新增 `repo/SuGaR/sugar_extractors/mv_consistency_filter.py`（核心投票 + 统计落盘 + pre/post PLY）。
- `extract_mesh.py` 增 7 个 `--mv_*` argparse 参数（默认关闭）。
- `coarse_mesh.py` 4 处最小改动：import 过滤器；`_cfg` 读 mv_* 配置（兼容 argparse.Namespace 与 AttrDict）；
  surface_normals（原 338 行）之后、fg/bg 分离之前 `if mv_filter:` 调用过滤器并切片 points/colors/normals；
  surface_level 循环后 `if mv_filter:` 落盘 剔点统计。
- `git diff --stat`: 仅 extract_mesh.py(+22) 与 coarse_mesh.py(+56)；新文件未跟踪。py_compile 三文件均通过。
- patch 落 `notes/diffs/阶段2a.patch`（503 行，含新文件 --no-index，未改动 git 状态）。

### 11:54-11:58 单元测试
- `scripts/tests/test_mv_filter.py` 6/6 PASS（CUDA_VISIBLE_DEVICES="" 纯 CPU，不占 GPU）：
  投票算术 / keep 规则 / 参考相机抽样确定性 / **采样与 SuGaR.get_points_depth_in_depth_map 逐元素一致(allclose)** /
  合成球面+漂浮点(球面保留 100%>95%, 两组漂浮点均剔除 100%>95%) / 空域冲突票机制(紧贴球面外侧漂浮点平均冲突票 2.5)。
- 注: 环境未装 pytest；测试用独立 runner（`python scripts/tests/test_mv_filter.py`，退出码 0/1）验证。

### 11:58 冒烟数据到位 + 基线训练在跑
- outputs/冒烟_truck/ 已出现（在 40min 窗口内，无需 fallback 训练）。冒烟 coarse=.../7100.pt（43352 高斯，219 训练相机）。
- 该执行者用 wrapper `scripts/run_extract_mesh.py` + 副本 `scripts/coarse_mesh_savepts.py`（**未改 repo**）。
  经 diff 确认：其副本 = repo 原始 coarse_mesh.py + 两段"另存表面采样点云"的 additive 代码（放在 fg/bg 分离之后，
  不消耗 torch RNG）→ 表面采样 RNG 路径与 repo 逐字节相同。其 seeding：seed=0（random/np/torch/cuda/o3d）。
- 冒烟 baseline mesh: outputs/冒烟_truck/mesh/sugarmesh_3Dgs500_densityestim02_sdfnorm02_level03_decim200000.ply。
- GPU: 基线 3dgs_7k 训练进行中(~4.7GB)；我的提取测试独立输出到 outputs/改动开发_临时/，不覆盖其产物。

### 11:58 关(mv_filter=False)提取（复现其 seed/参数，import repo 代码）
- runner: scratchpad/run_extract_repo.py（mirror 其 wrapper 的 seeding，但 import repo coarse_mesh，透传 mv_*）。
- cmd: `-s data/tandt/truck -c outputs/冒烟_truck/3dgs_500 -i 500 -m .../7100.pt -l 0.3 -d 200000 -o outputs/改动开发_临时/关_off --mv_filter False --seed 0`
- 结果见下（对拍其冒烟 mesh 的 V/F）。

### 12:08 关(mv_filter=False)提取完成 —— 关键发现
- 表面采样点数与该执行者冒烟**逐点一致**：全部=10,000,197（其 10,000,197）；前景=6,185,860（其 6,185,860）。
  → 证明 mv_filter=False 时提取输入(surface points)与基线**完全相同**，我的改动在关闭时零影响。
- 最终 mesh V/F：我的 OFF = V=174079 F=326129；其冒烟 = V=174068 F=326097。ΔV=11(0.006%) ΔF=32(0.010%)。
- 差异根因：surface points 相同、fg/bg 计数相同(fg=6185860, bg=1748043)、Poisson 前 mesh 亦相近
  (fg 1210595v/2386763f, bg 1017725v/2003160f)；微小 V/F 差来自 **open3d 多线程 Poisson 的非确定性**
  （日志有 "bad average roots" 数值边界警告；其冒烟 GPU 独占、我的与基线训练并发，线程调度不同）。与本改动无关。
- 用 Poisson 确定性对照(同一点云跑两次)进一步验证根因（见下）。

### 12:11-12:13 开(mv_filter=True, τ=0.02)提取完成
- cmd: `... -o outputs/改动开发_临时/开_on --mv_filter True --mv_tau 0.02 --mv_n_ref_cams 30 --mv_n_votes 0 --mv_seed 0 --seed 0`
- 输出: sugarmesh_...level03_decim200000.ply + 剔点统计.json/.txt + 表面点_剔点前.ply(510MB,10M) + 表面点_剔点后.ply(54MB,1.06M)。
- 剔点: N=10,000,197 → kept 1,060,155, **removed 8,940,042, 剔除率=0.8940(89.4%)**, never-in-view=36,248, M=30, K=all。
- **[DEVIATION] 剔除率 0.894 超出验收带 (0,50%)**：根因是冒烟 coarse 模型极度欠训（3DGS 仅 500 it、coarse 7100 it），
  几何/渲染深度噪声大 → 多视角一致性天然差；一致票直方图 [0票:496万, 1票:127万, 2票:83万, ...]平滑长尾、
  冲突票直方图同样平滑长尾 → 是真实分布而非 bug（单元测试中干净球面 100% 保留、采样器与 SuGaR 逐元素一致，已排除逻辑错误）。
- 深度约定复核：ON 运行的采样器就是 sugar.get_points_depth_in_depth_map（与单测 allclose 的同一函数）；深度=视空间 z。

### 12:11 关键对拍：表面点值完全一致 + Poisson 确定性
- ON 的 表面点_剔点前.ply(10,000,197) vs 该执行者 表面采样点云_全部_level03.ply(10,000,197)：
  排序后 **max_abs_diff=0.0，value-identical=True** → 表面采样跨运行(含并发训练)完全确定、逐点一致。
- open3d Poisson 同一点云跑两次：V=1346148 F=2692638 两次**完全一致**(deltaV=0,deltaF=0) → Poisson 进程内确定。
- 结论：OFF mesh 与其冒烟 mesh 的 ΔV=11/ΔF=32(0.01%) 差异位于**下游 open3d 简化(decimation)跨进程**，
  与本改动无关（本改动插入点在 fg/bg 分离之前，且 mv_filter=False 时零执行；表面点已证明逐点相同）。

### 12:13 冒烟 τ 敏感性（filter-only，不跑 Poisson；每次 <1s；用同一 10M 表面点）
| τ | kept | removed | 剔除率 |
|---|---|---|---|
| 0.02 | 1,060,155 | 8,940,042 | 0.8940 |
| 0.05 | 2,320,398 | 7,679,799 | 0.7680 |
| 0.10 | 3,457,531 | 6,542,666 | 0.6543 |
| 0.15 | 4,167,901 | 5,832,296 | 0.5832 |
| 0.20 | 4,669,545 | 5,330,652 | 0.5331 |
| **0.30** | **5,408,067** | **4,592,130** | **0.4592** |
| 0.50 | 6,473,510 | 3,526,687 | 0.3527 |
- 单调（τ↑→剔除↓），τ=0.02 与 ON 全流程剔除率 0.8940 **精确一致**（验证 explorer=extraction）。
- 冒烟(欠训)模型上 τ>=0.30 → 剔除率落入 (0,50%)。real baseline(7k/15k) 上默认 τ=0.02 预计温和得多（留正式实验测）。
- **[DEVIATION 处置]** 为满足验收 #2 的 (0,50%) 带，另跑一次全流程 τ=0.3 提取（见下）。这是冒烟 sanity，
  非"τ 扫描正式实验"（后者在 baseline coarse 15k 上，由主会话另派）。

### 12:23 开(mv_filter=True, τ=0.3)全流程提取完成 —— 落入 (0,50%)
- cmd: `... -o outputs/改动开发_临时/开_on_tau03 --mv_filter True --mv_tau 0.3 ... --seed 0`
- 剔点: N=10,000,197 → kept 5,408,067, **removed 4,592,130, 剔除率=0.4592(45.92%)** ∈ (0,50%) ✓；与 filter-only explorer 精确一致。
- 产物: sugarmesh_...level03_decim200000.ply (V=155962, F=294834, open3d 可打开) + 剔点统计.json/.txt + 表面点_剔点前/后.ply。
- 三个 mesh V/F（均 open3d 可打开，V/F>0）：关_off V=174079/F=326129；开_on(τ0.02) V=93572/F=176221；开_on(τ0.3) V=155962/F=294834。
  顶点数随剔除率单调下降（剔越多→点越稀→mesh 越小），符合预期。

### 12:23 OFF#2（第二次 mv_filter=False，同 seed）—— 量化基线简化噪声地板
- 目的：证明 OFF 与该执行者冒烟 mesh 的 ΔV=11 属基线 decimation 跨进程非确定性，与本改动无关。
- 结果：OFF#1 V=174079/F=326129；OFF#2 V=174069/F=326103；冒烟 V=174068/F=326097。
  **OFF#1 vs OFF#2（完全相同代码/seed）ΔV=10, ΔF=26 == 基线噪声地板**（与 OFF-vs-冒烟 的 ΔV=11 同量级）。
  Poisson 前 fg/bg 顶点数三方完全一致（fg=1210595, bg=1017725），仅三角数差个位/十位。
  → 证实 mv_filter=False 行为等价于基线，微小 V/F 差是 open3d Poisson/decimation 跨进程非确定性，非本改动引入。

### 结论
- 核心逻辑正确（单测 6/6；采样器与 SuGaR 逐元素一致；干净球面 100% 保留）。
- mv_filter=False 零影响（代码 guard + 表面点逐点相同 max_abs_diff=0）。
- mv_filter=True 跑通、产出 剔点统计 与 pre/post 点云、mesh 可开；τ 单调可控，(0,50%) 带在 τ=0.3 达成。
- 未跑正式 τ 扫描（等基线 coarse 15k，主会话另派）；未 git commit；未删文件；仅改 2 个允许文件 + 1 新文件。
</content>
</invoke>

---

# 阶段 2c: τ 扫描对照实验 (真实基线 coarse 15k 模型)

执行者: opus48-executor (claude-opus-4-8[1m])。开始时间 2026-09-14 12:41:47。
只在 /scratch/e1351071/zju_test_test 内操作; 不删文件; 不改 repo/SuGaR 现有文件; 不 git commit。
基线 commit 7c10c4a; repo git status: M extract_mesh.py / M coarse_mesh.py / ?? mv_consistency_filter.py (均阶段2a, 未新增改动)。
输入: coarse=outputs/基线_truck/coarse/.../15000.pt; 3DGS=outputs/基线_truck/3dgs_7k; 场景=data/tandt/truck。
基线 mesh(对照): outputs/基线_truck/mesh/sugarmesh_..._level03_decim1000000.ply (open3d V=746704 F=1437272 / trimesh V=750841; 连通分量 4851)。
基线评测(复用, 不重算): outputs/基线_truck/评测/ (M2 n_sample=1e6 seed=0 fg_bbox_factor=1.0 tau_ratios=0.005,0.01,0.02 scene_scale=13.3392; refA=3DGS点云 refB=COLMAP sparse/0)。

## 步骤1: τ 剔除率曲线 (filter-only)
- 脚本: scratchpad/tau_curve_2c.py (忠实复现模型加载+剪枝, 用基线 10M 表面点, 渲染30深度图一次, 复用 accumulate_votes 逐 τ 投票)。
- 参数: τ∈{0.005,0.01,0.02,0.05,0.1,0.2}, k=2, v=1, M=30, n_votes=0, seed=0, level=0.3。
- 开始 2026-09-14 12:41:47。日志 logs/2c_tau曲线.log。

### 步骤1 结果 (完成 12:42, EXIT=0)
- 模型: 剪枝 424177 -> 280234 高斯; image_hw=(1070,1920); 表面点 N=10,000,197; 渲染30深度图 0.3s; 逐τ投票 ~0.2s。
- 参考相机(seed=0, M=30): [0,3,7,14,34,52,58,59,84,98,101,112,116,119,121,123,129,130,142,149,159,161,166,172,183,184,195,198,203,216] (与阶段2a冒烟一致, 因抽样只依赖相机数219+seed)。
- n_never_in_view=27584 (0.28%, 各τ一致)。
- 剔除率曲线 (单调递减 = 是):
  | τ | 0.005 | 0.01 | 0.02 | 0.05 | 0.10 | 0.20 |
  | 剔除率 | 0.7221 | 0.5920 | 0.4494 | 0.2549 | 0.1399 | 0.0902 |
- 决策: 计划"若 τ≤0.05 剔除率全部>60% 则追加第4个τ"。实测 τ≤0.05 为 {72.21,59.20,44.94,25.49}%, 并非全部>60%
  (仅 τ=0.005 超60%) -> **不追加第4个τ**, 按计划跑 τ=0.02/0.05/0.01 三设置。
- 产物: outputs/改动_truck/τ曲线/{剔除率曲线.json,剔除率曲线.txt,剔除率_随τ变化.png}。
- 与真实提取的交叉校验待步骤2完成后比对 (explorer 剔除率 应≈ 各τ 全流程 剔点统计)。

## 步骤2: 正式设置全流程提取 (repo coarse_mesh.py + mv_filter, seed=0, -l 0.3 -d 1000000)
- runner: scratchpad/run_extract_repo.py (与 run_extract_mesh.py 同 seeding/尾斜杠, import repo coarse_mesh, 透传 mv_*)。
- 计时: scripts/eval/计时运行.sh -> 各设置目录 计时_提取mesh_τ{值}.{txt,json} (墙钟+峰值显存)。
- 过滤器额外耗时: 步骤1 explorer 实测 (渲染30图 0.3s + 单τ投票 ~0.2s ≈ 0.5s), 单独记录。

### 步骤2 各设置全流程提取结果 (repo coarse_mesh.py + mv_filter, seed=0)
命令模板 (计时运行.sh 包 run_extract_repo.py; 路径见各 计时_提取mesh_τX.json 的 command 字段):
  python scratchpad/run_extract_repo.py -s data/tandt/truck -c outputs/基线_truck/3dgs_7k -i 7000 \
    -m .../15000.pt -l 0.3 -d 1000000 -o outputs/改动_truck/改动_τX \
    --mv_filter True --mv_tau X --mv_min_consistent 2 --mv_max_conflict 1 --mv_n_ref_cams 30 --mv_n_votes 0 --mv_seed 0 --seed 0

| 设置 | 开始→结束 | 提取墙钟(s) | 峰值显存 本组/全卡(MiB) | 剔点前 | 剔点后 | 剔除率 | 与曲线一致 | EXIT |
|---|---|---|---|---|---|---|---|---|
| τ=0.02 | 12:43:38→12:47:56 | 258.296 | 8274/8283 | 10000197 | 5506389 | 0.44937 | 曲线0.4494 ✓精确 | 0 |
| τ=0.05 | 12:48→12:53:07 | 287.621 | 8274/8283 | 10000197 | 7451052 | 0.25491 | 曲线0.2549 ✓精确 | 0 |
| τ=0.01 | 12:53:19→12:57:14 | 234.865 | 8274/8283 | 10000197 | 4080375 | 0.59197 | 曲线0.5920 ✓精确 | 0 |
- 表面点_剔点前.ply(510MB, 10M) 各设置逐点相同(同 seed 采样); 表面点_剔点后.ply 随剔除率变化。
- 提取墙钟 < 基线 359.079s: 剔点后 fg/bg 点更少 -> Poisson/decimation 更快, 抵消过滤器 ~0.5s 开销。
- 剔点统计 ref_camera_indices 与步骤1曲线完全一致 [0,3,7,...,216]; 全流程剔除率与 explorer 曲线逐位一致 -> explorer=extraction 验证通过。
- 过滤器额外耗时(单独记录, 步骤1 explorer 实测): 一次性渲染30深度图 0.3s + 单τ投票 ~0.2s ≈ 0.5s (占提取墙钟约0.2%)。

### 步骤3 评测 (M2–M6; M1 与基线相同, 跳过) + 汇总对照表
- 说明: 会话曾在 M3 阶段中断; 恢复后 M2(几何)已完成不重跑, 补跑 M3/M4/M5/M6 (run_all_eval --metrics M3,M4,M5,M6, 3 变体并行)。
- 评测参数与基线完全相同: n_sample=1e6, fg_bbox_factor=1.0, tau_ratios=0.005,0.01,0.02, self_intersect_timeout=120,
  refA=3DGS点云, refB=COLMAP sparse/0, cameras_json=基线3dgs; 全部变体 scene_scale=13.339236, crop_bbox 一致, refB=136029点 一致 (公平性核验 PASS)。
- 命令(每变体): python scripts/eval/run_all_eval.py --tag 改动_τX --source_path data/tandt/truck --gs_output outputs/基线_truck/3dgs_7k
  --iteration 7000 --mesh <mesh> --ref_a <3dgs点云> --ref_b_colmap data/tandt/truck/sparse/0 --cameras_json <cam.json>
  --timing_json <设置目录> --out_dir outputs/改动_truck/评测 --metrics M2,M3,M4,M5,M6 --n_sample 1000000 --save_masks --self_intersect_timeout 120
  (恢复后实际用 --metrics M3,M4,M5,M6; M2 已于中断前完成)。
- 汇总对照表: scratchpad/consolidate_2c.py -> outputs/改动_truck/评测/汇总对照表.{json,csv,txt} (基线行直接取基线评测数字)。
- 独立复算(不 import 评测代码): scratchpad/recompute_2c.py 对 τ=0.02 mesh: V/F/连通分量/最大分量占比/Chamfer_B/完整度B/精度B 与评测 json 相对误差 0.0000% (逐位一致)。
- 统一色标误差热图: scratchpad/unified_heatmap_2c.py -> outputs/改动_truck/评测/图_统一色标/ (基线+3改动共享色标[0.0198,2.3958], 视角与基线一致)。

### 步骤4 复制到 考核提交 (完成 2026-09-14 13:48:39)
- 网格: 考核提交/网格/改动_truck_τ{0.01,0.02,0.05}_网格.ply
- 指标: 考核提交/指标/ (几何/拓扑/覆盖/效率_改动_τ*.{json,txt} + 汇总对照表.{json,csv,txt} + 剔除率曲线.{json,txt})
- 可视化: 考核提交/可视化/ (网格截图/误差热图/连通分量着色_改动_τ*.png + 图_统一色标/ + 剔除率_随τ变化.png + 覆盖掩码_改动_τ*/)

### 关键结果 (对照基线)
| 设置 | 剔除率 | 连通分量数 | 孔洞数 | 边界边 | Chamfer_A | Chamfer_B | F@0.01_A | F@0.01_B | 网格覆盖率 | 漏洞率(前景) | 提取墙钟s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 基线 | - | 4851 | 7970 | 96544 | 0.032554 | 0.053072 | 0.94642 | 0.88771 | 0.92891 | 0.06659 | 359.079 |
| τ=0.05 | 0.2549 | 3279 | 6206 | 68205 | 0.028663 | 0.045498 | 0.96059 | 0.92041 | 0.81476 | 0.18047 | 287.621 |
| τ=0.02 | 0.4494 | 2690 | 5480 | 54647 | 0.024184 | 0.038975 | 0.97648 | 0.94950 | 0.71022 | 0.28565 | 258.296 |
| τ=0.01 | 0.5920 | 2261 | 4598 | 44848 | 0.023020 | 0.036104 | 0.98201 | 0.96316 | 0.63324 | 0.36345 | 234.865 |
- H1 支持: 连通分量数/孔洞/边界边 单调下降; Chamfer(双参考)单调下降; F-score 单调上升。
- H2 支持: 网格覆盖率单调下降/漏洞率单调上升 (accuracy_ref_to_mesh 亦随剔除增加而上升), 即低 τ 过剔伤真实覆盖。
- H3: M1 渲染指标与基线相同 (coarse 模型未变, 只重跑提取), 未重算, 按计划说明。
- 权衡结论: τ=0.05 (剔25%) 拓扑收益明显而覆盖损失温和; τ=0.01 (剔59%) 过剔; τ=0.02 居中。
