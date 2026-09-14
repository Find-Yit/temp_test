# 阶段 0C 调研：SuGaR 之后的 3DGS→Mesh 开源工作 / 官方仓库要点 / 3 个候选改动

调研时间 2026-09-14。本地 SuGaR commit `7c10c4ae4a267dece512f5c7f40ed212a0a2ab44`（2024-09-24，含 `dn_consistency`）。
所有 URL 见文末「参考链接」。

---

## 一、SuGaR 之后基于/对比 SuGaR 的开源 3DGS→Mesh 工作

| 方法 | 核心思想（1-2 句） | 相对 SuGaR 改哪一步 | 移植到 SuGaR 的成本 |
|---|---|---|---|
| **2DGS** (SIGGRAPH'24) | 把 3D 椭球退化成 2D 圆盘基元精确求交；训练加 depth-distortion + normal-consistency 两个正则；提取用 TSDF 融合 median depth。 | 表示 + 训练 + 提取（全换） | **高**：需替换 CUDA 栅格化器；两个正则的思想可单独借鉴。 |
| **Gaussian Surfels** (SIGGRAPH'24) | 把 z-scale 置 0 得到 surfel，提升优化稳定性与表面贴合；自监督 normal-depth consistency loss；提取时先做 *volumetric cutting* 剔除深度图中的错误点，再 screened Poisson。 | 训练（表示+loss）+ 提取（剔点） | **中**：normal-depth 一致性已被 `dn_consistency` 吸收；**volumetric cutting 可低成本移植**。 |
| **GOF** (SIGGRAPH Asia'24 / TOG) | 沿射线取最小 opacity 定义"不透明度场"，直接取其 level set；用 Gaussian 诱导的 Delaunay 四面体 + Marching Tetrahedra 自适应提网格。 | 提取为主（也改栅格化器求交） | **高**：依赖 CGAL + 自定义 CUDA。 |
| **RaDe-GS** | 不压扁 Gaussian，用闭式解析方式栅格化深度/法向图，兼顾精度与速度；正则借鉴 2DGS/PGSR，滤波借鉴 Mip-Splatting。 | 训练（渲染 + 正则） | **中高**：核心在 rasterizer。 |
| **PGSR** (TVCG'24) | 平面化 Gaussian + 无偏深度（相机到 Gaussian 平面的距离 ÷ 法向图）+ 多视角几何/光度一致性约束。 | 训练 | **高**（完整 patch-warp）；但"多视角一致性"思想可简化移植。 |
| **GaussianPro** (ICML'24) | 借 MVS patch-match 做渐进传播来指导致密化，生成位置/朝向更准的新 Gaussian，并加平面损失。 | 训练（致密化策略） | **中高**：需引入 patch-match 传播。 |
| **Frosting** (ECCV'24 Oral，同作者) | 先取 base mesh，再在其周围建**可变厚度**的 Gaussian "糖霜"层，兼顾毛发/草等体积效果与可编辑性。 | 提取之后的表示 + refine | **中**。其清理参数 `cleaning_quantile`、`connected_components_vis_th`（去掉不可见连通分量）值得借鉴——**SuGaR 里没有连通分量清理**。 |
| **MILo** (SIGGRAPH Asia'25 / TOG，同作者) | 训练每一步都**可微地**从 Gaussian 参数抽出 mesh（Gaussian 作 Delaunay pivot + 由 Gaussian 算 SDF），让 mesh 梯度回流到 Gaussian，实现体/面双向一致。 | 训练与提取耦合 | **高**。 |
| **GS2Mesh** (ECCV'24) | 完全不改 3DGS 训练：渲染立体像对，用预训练立体匹配网络 DLNR 得深度，再用 Open3D TSDF 融合成网格。 | 只改提取 | **中**：需外部预训练权重。 |

---

## 二、SuGaR 官方仓库要点（README + issues + 本地源码核对）

**两种正则的差别**（README「Tips 3」+ `sugar_trainers/`，coarse 均 `num_iterations = 15_000`）：
- `sdf`（`coarse_sdf.py`，`sdf_estimation_mode='sdf'`）：约束更强，尤其在背景区域；论文中 Mip-NeRF 360 这类带复杂背景的场景用它，标准数据集指标更高。
- `density`（`coarse_density.py`，`sdf_estimation_mode='density'`）：最简单，适合物体居中、环绕拍摄的场景，此时 mesh 常优于 sdf。
- `dn_consistency`（`coarse_density_and_dn_consistency.py`）：= density 正则 **＋** 深度图梯度导出的法向与 Gaussian 渲染法向的一致性损失（`dn_consistency_factor=0.05`，从第 9000 步起）。官方推荐，网格质量最好。Gaussian 的法向定义为协方差最短轴。

**常见失败与官方对策**：
1. **Poisson 孔洞**：清理过于激进 → 降低 `coarse_mesh.py:44` 的 `vertices_density_quantile`（0.1 → 0.）。
2. **表面椭球状凸包/噪点**：Poisson 分辨率相对 Gaussian 尺寸过细 → 降低 `coarse_mesh.py:43` 的 `poisson_depth`（10 → 7 或 6）。
3. **背景/分割物体伪面**：单色背景会被当成单色曲面重建出来（issue #198）；fg/bg bbox 不合适时前景或背景 mesh 会为空（issue #186）。
4. **漂浮物**：SuGaR 仓库本身没给正式对策；同作者的 MAtCha README 里对应建议是加强对齐/稠密深度正则（`--alignment_config strong`、`--dense_regul`）。

**关键参数含义**（`sugar_extractors/coarse_mesh.py` 第 27-47 行）：
- `surface_level`（默认 `train.py` 取 0.3，`extract_mesh.py` 不指定时扫 [0.1, 0.3, 0.5]）：密度场等值面阈值，沿像素射线找密度首次跨越该值的位置作为表面点。值越小表面越"外扩"。
- `poisson_depth = 10`：Poisson 八叉树深度，控制网格分辨率。
- `vertices_density_quantile = 0.1`：按 Poisson 输出的顶点密度分位数剔除低置信顶点（fg/bg 各做一次）。
- `fg_bbox_factor = 1. / bg_bbox_factor = 4.`：前/背景分离——以相机中心范围为尺度的**各向同性立方体**，盒内为前景、盒外且在 4 倍范围内为背景，分别跑一次 Poisson。
- `n_gaussians_per_surface_triangle`（`-g`，refine 阶段）：每个三角形绑几个 Gaussian，high_poly=1 配 1M 顶点，low_poly=6 配 200k 顶点。
- `cleaning_quantile`：**注意，本 commit 的 SuGaR 里并不存在这个参数**（它属于 Frosting）；SuGaR 中功能最接近的是 `vertices_density_quantile`，以及 refine 阶段的 `--postprocess_density_threshold`。

---

## 三、3 个候选改动

三者都满足：进入训练或提取主流程、≤100 行、有可检验假设、有一个可扫超参。

### 候选 A（推荐）｜Poisson 之前的多视角深度一致性剔点
- **位置**：`sugar_extractors/coarse_mesh.py` 第 333 行「Processing surface levels」之后、构建 `fg_pcd/bg_pcd` 之前。
- **做法**：预先对 M≈30 个抽样训练相机缓存 `render_depth_and_normal()` 深度图；每个表面点投影到随机 K≈8 个相机，用已有的 `get_points_depth_in_depth_map()` 取该像素渲染深度 z_map，与点的相机空间深度 z_p 比较：|z_p − z_map| < τ·z_map 记一票"一致"，z_p < z_map − τ·z_map 记一票"空域冲突"。保留一致票 ≥ k 且空域票 ≤ v 的点。（借鉴 Gaussian Surfels 的 volumetric cutting 与 PGSR 的多视角一致性）
- **假设 H1**：漂浮几何与背景球壳上的点只在生成它们的那一个视角自洽，换视角就会落入空域 → 剔除后 mesh 连通分量数 ↓、Chamfer ↓、前景三角形数 ↓。
- **可扫超参**：τ ∈ {0.01, 0.02, 0.05}（相对深度容差）。
- **预期**：Chamfer（accuracy 方向）↓；孤立小块/连通分量数显著 ↓；PSNR 基本不变（不重训 coarse）。
- **风险**：τ 太小会剔掉弱覆盖的薄结构与物体边界 → 出现新的孔洞、completeness 变差；额外 M 次深度渲染（分钟级）。
- **代码量**：约 70-90 行（含深度图缓存、投票、统计落盘）。

### 候选 B｜coarse 训练中加"扁平化（各向异性）正则"
- **位置**：`sugar_trainers/coarse_density_and_dn_consistency.py` 的 loss 累加处。
- **做法**：`L_flat = mean(s_min / (s_mid + eps))`（`sugar.scaling` 排序后的最小/中间轴），第 7000 步起以权重 λ_flat 加入。等于把 2DGS / Gaussian Surfels 的"压扁成盘"作为**软约束**引入，而不动栅格化器。
- **假设 H2**：Gaussian 越扁，其最短轴（SuGaR 用作法向）越稳定 → Poisson 输入法向噪声 ↓ → 表面更光滑、Chamfer ↓。
- **可扫超参**：λ_flat ∈ {0.01, 0.1}。
- **预期**：几何 ↑，但渲染 PSNR 可能小幅 ↓（表达能力受限），需如实报告 trade-off。
- **风险**：λ 过大导致退化/训练不稳；**每个取值都要重跑 coarse 训练**，2 个取值约 1.5h，时间紧。
- **代码量**：约 20-30 行。

### 候选 C｜自适应前景包围盒（前背景分离）
- **位置**：`coarse_mesh.py` 第 340-362 行 fg/bg mask 计算处。
- **做法**：现有 fg bbox 只由相机中心范围决定、与场景内容无关。改为用表面点云在各轴取 [q, 1−q] 分位数得到 data-driven bbox，再与相机 bbox 取交；bg 不变。
- **假设 H3**：更贴合内容的 fg bbox 让 1M 顶点预算更多落在真正的前景 → 前景 Chamfer ↓、前景三角形密度 ↑，并减少背景壳被误纳入 fg Poisson 形成的膜状连接。
- **可扫超参**：q ∈ {0.005, 0.02, 0.05}。
- **预期**：前景几何 ↑；整场景 Chamfer 可能中性。
- **风险**：q 太大会削掉前景边缘；对 object-centric 场景收益大，对 360° 大场景可能无效甚至变差。
- **代码量**：约 30-40 行。

### 推荐：**候选 A**
1. 直击 SuGaR 最常被报告的失败模式（漂浮物 / 背景壳 / 单视角自洽的伪表面），而题目正好把"减少漂浮几何"列为合格动机示例；
2. 作用在 **Poisson 之前**，属于"表面采样 + 前背景分离"主流程，不是题目明确排除的"最后一层后处理"；
3. 只有一个干净的标量超参 τ，天然适合做敏感性扫描，而且它的两端失败模式（τ 大→漏剔、τ 小→孔洞）本身就是好的分析素材；
4. **只需重跑提取阶段**，一次 coarse 训练即可支撑 baseline + 2~3 个 τ，在 6h 预算内能做出真正的消融；
5. 完全复用已有的 `render_depth_and_normal` / `get_points_depth_in_depth_map`，不改 CUDA，≤100 行；且有明确学术出处（Gaussian Surfels、PGSR），报告里 motivation 讲得通。

若时间有余，可把候选 B 作为第二组对照（几何 vs 渲染 trade-off 的正例）。

---

## 参考链接

- SuGaR 论文 https://arxiv.org/abs/2311.12775 ｜代码 https://github.com/Anttwo/SuGaR ｜项目页 https://anttwo.github.io/sugar/
- 3DGS https://github.com/graphdeco-inria/gaussian-splatting
- SuGaR README（Tips 3/4/5） https://github.com/Anttwo/SuGaR/blob/main/README.md
- SuGaR issues：#198 https://github.com/Anttwo/SuGaR/issues/198 ｜#194 https://github.com/Anttwo/SuGaR/issues/194 ｜#186 https://github.com/Anttwo/SuGaR/issues/186 ｜#168 https://github.com/Anttwo/SuGaR/issues/168 ｜#20 https://github.com/Anttwo/SuGaR/issues/20
- 2DGS https://arxiv.org/abs/2403.17888 ｜ https://github.com/hbb1/2d-gaussian-splatting
- Gaussian Surfels https://arxiv.org/abs/2404.17774 ｜ https://github.com/turandai/gaussian_surfels ｜ https://turandai.github.io/projects/gaussian_surfels/
- GOF https://arxiv.org/abs/2404.10772 ｜ https://github.com/autonomousvision/gaussian-opacity-fields ｜ https://niujinshuchong.github.io/gaussian-opacity-fields/
- RaDe-GS https://arxiv.org/abs/2406.01467 ｜ https://github.com/HKUST-SAIL/RaDe-GS ｜ https://baowenz.github.io/radegs/
- PGSR https://arxiv.org/abs/2406.06521 ｜ https://github.com/zju3dv/PGSR ｜ https://zju3dv.github.io/pgsr/
- GaussianPro https://github.com/kcheng1021/GaussianPro ｜ https://kcheng1021.github.io/gaussianpro.github.io/
- Frosting https://github.com/Anttwo/Frosting
- MILo https://arxiv.org/abs/2506.24096 ｜ https://github.com/Anttwo/MILo ｜ https://anttwo.github.io/milo/
- GS2Mesh https://github.com/yanivw12/gs2mesh
- MAtCha（同作者，漂浮物建议出处） https://github.com/Anttwo/MAtCha
