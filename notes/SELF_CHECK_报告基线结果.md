# SELF_CHECK: 报告基线结果（sec2_dataset.tex + sec3_results.tex）

写作者：opus46-writer
日期：2026-09-14

---

## 编译结果

- 编译命令：`cd report/ && bash build.sh`
- 编译状态：**通过**（无 error，sec3 无 overfull 警告）
- 页数：**10 页**
- 产物：`report/report.pdf`（4.14 MiB）

---

## 文件变更

| 文件 | 操作 |
|------|------|
| report/sections/sec2_dataset.tex | 重写（填入数据集信息） |
| report/sections/sec3_results.tex | 重写（填入基线结果，保留分析 TODO） |
| report/figures/网格截图_基线.png | 新增（从 outputs/基线_truck/评测/图/ 复制） |
| report/figures/误差热图_基线.png | 新增（同上） |
| report/figures/连通分量着色_基线.png | 新增（同上） |
| report/figures/渲染对比_基线_视角000_000001.png | 新增（同上） |
| notes/SELF_CHECK_报告基线结果.md | 新增（本文件） |

未删除任何文件，未修改任何代码文件，未 git commit。

---

## 数据核对表

### sec2_dataset.tex

| 报告中的数字 | 值 | 来源文件 | JSON 字段路径 |
|-------------|-----|---------|--------------|
| 图像总数 | 251 | `ls data/tandt/truck/images/` 实际计数 | — |
| 训练视角 | 219 | notes/RUNLOG_基线.md | "219训练/32测试" |
| 测试视角 | 32 | 渲染指标_基线.json | `.n_test_views` = 32 |
| COLMAP 稀疏点数 | 136,029 | 几何指标_基线.json | `.references.参考B_COLMAP稀疏点.n_ref_points_before_crop` = 136029 |
| 3DGS 迭代 | 7,000 | 效率指标_基线.json | `.stages[2].command` 含 `--iterations 7000` |
| Coarse num_iterations | 15,000 | 效率指标_基线.json | `.stages[0].command` 含 `--num_iterations 15000` |
| surface_level | 0.3 | 效率指标_基线.json | `.stages[1].command` 含 `-l 0.3` |
| Poisson 深度 | 10 | notes/RUNLOG_基线.md | "poisson_depth=10默认" |
| 分位数阈值 | 0.1 | notes/RUNLOG_基线.md | "vertices_density_quantile=0.1默认" |
| 抽简目标 | 1,000,000 | 效率指标_基线.json | `.stages[1].command` 含 `-d 1000000` |
| 参考A裁剪后点数 | 284,309 | 几何指标_基线.json | `.references.参考A_3DGS高斯中心.n_ref_points_in_bbox` = 284309 |
| 参考B裁剪后点数 | 56,988 | 几何指标_基线.json | `.references.参考B_COLMAP稀疏点.n_ref_points_in_bbox` = 56988 |
| 场景对角线 | 13.34 | 几何指标_基线.json | `.scene_scale_diagonal` = 13.339236... ≈ 13.34 |

### sec3_results.tex — 渲染指标（表 tab:render-metrics）

| 报告中的数字 | 值 | 来源文件 | JSON 字段路径 | 原始值 |
|-------------|-----|---------|--------------|--------|
| 3DGS PSNR | 23.92 | 渲染指标_基线.json | `.vanilla_3dgs.psnr` | 23.922265768... |
| 3DGS SSIM | 0.849 | 渲染指标_基线.json | `.vanilla_3dgs.ssim` | 0.849422886... |
| 3DGS LPIPS | 0.202 | 渲染指标_基线.json | `.vanilla_3dgs.lpips` | 0.201636141... |
| Coarse PSNR | 24.32 | 渲染指标_基线.json | `.coarse_sugar.psnr` | 24.322837114... |
| Coarse SSIM | 0.848 | 渲染指标_基线.json | `.coarse_sugar.ssim` | 0.848214052... |
| Coarse LPIPS | 0.217 | 渲染指标_基线.json | `.coarse_sugar.lpips` | 0.217011549... |

### sec3_results.tex — 几何指标 参考A（表 tab:geo-refA）

| 报告中的数字 | 值 | 来源文件 | JSON 字段路径 | 原始值 |
|-------------|-----|---------|--------------|--------|
| Chamfer L1 | 0.0326 | 几何指标_基线.json | `.references.参考A_3DGS高斯中心.chamfer_l1` | 0.032553693... |
| Accuracy 均值 | 0.0156 | 几何指标_基线.json | `.references.参考A_3DGS高斯中心.accuracy_ref_to_mesh.mean` | 0.015605280... |
| Accuracy 中位数 | 0.0098 | 几何指标_基线.json | `.references.参考A_3DGS高斯中心.accuracy_ref_to_mesh.median` | 0.009847715... |
| Accuracy P90 | 0.0291 | 几何指标_基线.json | `.references.参考A_3DGS高斯中心.accuracy_ref_to_mesh.p90` | 0.029122227... |
| Completeness 均值 | 0.0495 | 几何指标_基线.json | `.references.参考A_3DGS高斯中心.completeness_mesh_to_ref.mean` | 0.049502105... |
| Completeness 中位数 | 0.0233 | 几何指标_基线.json | `.references.参考A_3DGS高斯中心.completeness_mesh_to_ref.median` | 0.023298634... |
| Completeness P90 | 0.1317 | 几何指标_基线.json | `.references.参考A_3DGS高斯中心.completeness_mesh_to_ref.p90` | 0.131664465... |
| F@0.5% | 0.864 | 几何指标_基线.json | `.references.参考A_3DGS高斯中心.fscore.tau_0.005.fscore` | 0.863885757... |
| F@1% | 0.946 | 几何指标_基线.json | `.references.参考A_3DGS高斯中心.fscore.tau_0.01.fscore` | 0.946421655... |
| F@2% | 0.990 | 几何指标_基线.json | `.references.参考A_3DGS高斯中心.fscore.tau_0.02.fscore` | 0.990296331... |

### sec3_results.tex — 几何指标 参考B（表 tab:geo-refB）

| 报告中的数字 | 值 | 来源文件 | JSON 字段路径 | 原始值 |
|-------------|-----|---------|--------------|--------|
| Chamfer L1 | 0.0531 | 几何指标_基线.json | `.references.参考B_COLMAP稀疏点.chamfer_l1` | 0.053072344... |
| Accuracy 均值 | 0.0242 | 几何指标_基线.json | `.references.参考B_COLMAP稀疏点.accuracy_ref_to_mesh.mean` | 0.024239490... |
| Accuracy 中位数 | 0.0033 | 几何指标_基线.json | `.references.参考B_COLMAP稀疏点.accuracy_ref_to_mesh.median` | 0.003312646... |
| Accuracy P90 | 0.0200 | 几何指标_基线.json | `.references.参考B_COLMAP稀疏点.accuracy_ref_to_mesh.p90` | 0.019963808... |
| Completeness 均值 | 0.0819 | 几何指标_基线.json | `.references.参考B_COLMAP稀疏点.completeness_mesh_to_ref.mean` | 0.081905197... |
| Completeness 中位数 | 0.0480 | 几何指标_基线.json | `.references.参考B_COLMAP稀疏点.completeness_mesh_to_ref.median` | 0.047985881... |
| Completeness P90 | 0.2005 | 几何指标_基线.json | `.references.参考B_COLMAP稀疏点.completeness_mesh_to_ref.p90` | 0.200477605... |
| F@0.5% | 0.751 | 几何指标_基线.json | `.references.参考B_COLMAP稀疏点.fscore.tau_0.005.fscore` | 0.750619326... |
| F@1% | 0.888 | 几何指标_基线.json | `.references.参考B_COLMAP稀疏点.fscore.tau_0.01.fscore` | 0.887706922... |
| F@2% | 0.963 | 几何指标_基线.json | `.references.参考B_COLMAP稀疏点.fscore.tau_0.02.fscore` | 0.962966590... |

### sec3_results.tex — 拓扑/覆盖/效率（表 tab:topo-cov-eff）

| 报告中的数字 | 值 | 来源文件 | JSON 字段路径 | 原始值 |
|-------------|-----|---------|--------------|--------|
| V | 750,841 | 效率指标_基线.json | `.mesh.vertices` | 750841 |
| F | 1,437,272 | 拓扑指标_基线.json | `.topology.F` | 1437272 |
| 连通分量数 | 4,851 | 拓扑指标_基线.json | `.topology.n_components` | 4851 |
| 最大分量占比 | 49.5% | 拓扑指标_基线.json | `.topology.max_component_ratio` | 0.49530360... |
| 边界边数 | 96,544 | 拓扑指标_基线.json | `.topology.boundary_edges` | 96544 |
| 孔洞数 | 7,970 | 拓扑指标_基线.json | `.topology.holes_boundary_loops` | 7970 |
| 水密 | 否 | 拓扑指标_基线.json | `.topology.is_watertight` | false |
| 网格覆盖率 | 92.9% | 覆盖指标_基线.json | `.averaged.mesh_coverage` | 0.928910577... |
| 前景漏洞率 | 6.7% | 覆盖指标_基线.json | `.averaged.hole_rate_over_fg` | 0.066585144... |
| 3DGS 训练墙钟 | 1.98 min | 效率指标_基线.json | `.stages[2].wall_seconds` | 118.633 → 118.633/60=1.977... |
| Coarse 训练墙钟 | 15.84 min | 效率指标_基线.json | `.stages[0].wall_seconds` | 950.633 → 950.633/60=15.843... |
| Mesh 提取墙钟 | 5.98 min | 效率指标_基线.json | `.stages[1].wall_seconds` | 359.079 → 359.079/60=5.984... |
| 总墙钟 | 23.81 min | 效率指标_基线.json | `.total_wall_seconds` | 1428.345 → 1428.345/60=23.805... |
| 峰值显存 | 10,098 MiB | 效率指标_基线.json | `.peak_mem_process_group_MiB` | 10098 |
| 网格文件体积 | 54.34 MiB | 效率指标_基线.json | `.mesh.file_MiB` | 54.3382 |

### 脚注数字

| 报告中的数字 | 值 | 来源文件 | JSON 字段路径 |
|-------------|-----|---------|--------------|
| Open3D V | 746,704 | 拓扑指标_基线.json | `.topology.V` = 746704 |

---

## 图片核对

| 报告引用路径 | 源文件 | 复制确认 |
|-------------|--------|---------|
| figures/网格截图_基线.png | outputs/基线_truck/评测/图/网格截图_基线.png | OK (159,102 bytes) |
| figures/误差热图_基线.png | outputs/基线_truck/评测/图/误差热图_基线.png | OK (184,916 bytes) |
| figures/连通分量着色_基线.png | outputs/基线_truck/评测/图/连通分量着色_基线.png | OK (187,424 bytes) |
| figures/渲染对比_基线_视角000_000001.png | outputs/基线_truck/评测/图/渲染对比_基线_视角000_000001.png | OK (501,778 bytes) |

---

## 使用的公式

- 无自创公式。所有指标定义引用自评测协议（几何指标_基线.json 中的 Chamfer L1、Accuracy/Completeness/F-score 等标准定义）。
- F-score 阈值 τ 取自场景对角线的 0.5%/1%/2%（即 0.0667/0.1334/0.2668 场景坐标单位），记录在 几何指标_基线.json 的 `.fscore.tau_0.005.tau_abs` 等字段。

---

## 代码文件引用

报告中未引用任何代码行号（无 `{{L:...}}` 占位符需要回填）。
sec1_method.tex 中已有的代码行号占位符保持不变。

---

## 遵守用户规则确认

- [x] 环境细节不进报告（仅在 README 中）
- [x] 代码差异/修改细节不进报告
- [x] sec1_method.tex 未被修改（用户手动删减后的版本保持原样）
- [x] 失败案例 TODO 注明"仅讨论方法与超参层面"
- [x] 全中文行文，术语首次出现附英文
- [x] 所有数字可追溯至指定 JSON/txt 文件
- [x] 不编造任何数字或估计值
- [x] 未删除任何文件
- [x] 未修改任何代码
- [x] 未 git commit
