# SELF_CHECK: 报告方法节（sec1_method.tex 改动方案部分）

撰写时间：2026-09-14

## 修改的文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `report/sections/sec1_method.tex` | 替换占位 | 原 73-100 行占位内容替换为 8 个小节，约 430 行 |
| `report/refs.bib` | 追加 | 新增 8 条参考文献条目 |
| `report/report.tex` | 插入 1 行 | 加载 `algorithm2e` 宏包 |
| `notes/SELF_CHECK_报告方法节.md` | 新建 | 本文件 |

## 引用的数据来源

本节为纯方法描述，**未引用任何实验数值**（CSV/JSON）。
所有超参数默认值均来自以下计划文件与先例核实笔记（逐条可追溯）：

| 数据 | 来源文件 |
|------|----------|
| COLMAP `max_depth_error=0.01`, `min_num_pixels=5` | `notes/先例核实.md` §一.B（COLMAP 行） |
| ACMM `reproj_error<2.0`, `relative_depth_diff<0.01`, `num_consistent>=2` | `notes/先例核实.md` §一.B（ACMM 行） |
| GaussianPro `thre1=2`, `thre2=0.01`, `cost>=2` | `notes/先例核实.md` §一.B（GaussianPro 行） |
| Gaussian Surfels 占据栅格 `grid_dim_max=512` | `notes/先例核实.md` §一.A |
| Frosting `cluster_visibility_threshold=0.001` | `notes/先例核实.md` §一.A / §二 |
| 本方法超参默认值 `tau=0.02`, `min_consistent=2`, `max_conflict=1`, `M=30` | `plans/改动方案_多视角深度一致性剔点.txt` 实现要点 |
| 预注册假设 H1/H2/H3 | `plans/改动方案_多视角深度一致性剔点.txt` 预注册假设 |
| tau 扫描范围 {0.01, 0.02, 0.05} | `plans/改动方案_多视角深度一致性剔点.txt` tau 扫描 |

## 引用的公式

| 公式 | 位置 | 说明 |
|------|------|------|
| 保留条件 Eq. (1) | `sssec:method-detail` | 一致票 >= k_min 且 冲突票 <= v_max |
| 一致票判据 | `sssec:method-detail` | |z_p - z_map| < tau * z_map |
| 空域冲突票判据 | `sssec:method-detail` | z_p < z_map - tau * z_map |

## 引用的代码文件

| 代码文件 | 用途 | 行号占位 |
|----------|------|----------|
| `sugar_extractors/coarse_mesh.py` | 基线提取流程、改动插入位置 | `{{L:sugar_extractors/coarse_mesh.py:extract_mesh_from_coarse_sugar}}`, `{{L:sugar_extractors/coarse_mesh.py:surface_level_loop}}` |
| `sugar_extractors/mv_consistency_filter.py` | 核心过滤函数（尚未实现，代码片段为示意） | `{{L:sugar_extractors/mv_consistency_filter.py:multiview_depth_consistency_filter}}` |
| `extract_mesh.py` | 命令行参数透传 | `{{L:extract_mesh.py:argparse}}` |

## 新增参考文献条目（refs.bib）

1. `schoenberger2016sfm` — COLMAP SfM (CVPR 2016)
2. `schoenberger2016mvs` — COLMAP MVS (ECCV 2016)
3. `xu2019acmm` — ACMM (CVPR 2019)
4. `cheng2024gaussianpro` — GaussianPro (ICML 2024)
5. `dai2024gaussian_surfels` — Gaussian Surfels (SIGGRAPH 2024)
6. `guedon2024frosting` — Frosting (ECCV 2024)
7. `huang20242dgs` — 2DGS (SIGGRAPH 2024)
8. `chen2024pgsr` — PGSR (TVCG 2024)

## 先例归属核实

- Gaussian Surfels volumetric cutting：准确描述为"占据栅格剔点"，**非**深度投票 ✓
- COLMAP StereoFusion：相对深度差 0.01 ✓
- ACMM：num_consistent >= 2 投票 ✓
- GaussianPro：check_geometric_consistency，3DGS 版本 ✓
- Frosting：Poisson 之后按连通分量可见性删除 ✓
- 与先例的两处差异：(1) 单向投影 vs 前向-后向重投影；(2) 过滤对象与插入位置 ✓

## 编译结果

- 编译工具：tectonic（`tools/tectonic/tectonic`）
- 编译命令：`cd report && bash build.sh`
- 编译状态：**通过**（无错误，有 Overfull hbox 警告，均为长 `\texttt{}` 路径所致，最大 76pt 在算法环境中）
- 输出文件：`report/report.pdf`，3.32 MiB
- 页数：**13 页**
- sec1_method.tex 行数：**509 行**

## 未编造的数据

本节全部内容为方法描述与先例归属，**没有引入任何实验数字**。
代码片段标注为"示意代码"，注脚明确说明"待实际实现完成后以仓库代码为准同步"。
`mv_consistency_filter.py` 在撰写时尚不存在（`FILE_NOT_FOUND`）。

## 未删除 / 未覆盖的文件

- 未删除任何文件
- 未覆盖已有内容文件（sec1_method.tex 中替换的是 `\todo{}` 与 `\placeholder{}` 占位符）
- refs.bib 为追加模式，原有 5 条条目完整保留
