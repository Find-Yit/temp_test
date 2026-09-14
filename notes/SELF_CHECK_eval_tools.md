# SELF_CHECK_eval_tools.md — 评测工具集 M1–M6 自检

工作目录: `/scratch/e1351071/zju_test_test` ｜ 日期: 2026-09-14 ｜ 执行者: opus48-executor
约束遵守: 只新增文件；未改动 `repo/SuGaR` 内任何现有文件（仅 import）；未删除任何文件；未 git commit；未触碰其他目录。

## TL;DR
- 6 个指标脚本 + 汇总脚本 + 计时包装器 + 共享库 + 5 个测试文件全部写好, 均 `argparse`, 输入/输出路径可指定, seed 固定=0。
- 输出规范满足: 每脚本同时写 `JSON + 中文键名 .txt`；逐视角写 `CSV`；图/掩码用中文命名。
- 合成数据单元自测: **test_m2_m3 20/20, test_m5_m6 14/14, test_m1_m4 17/17 全 PASS（共 51 条）**。
- 真实数据(冒烟 truck 场景, 真实 3DGS-500 + coarse 7100.pt + 326097 面 mesh)上 **M1–M6 全部实测通过**。
- 一处工程性偏离见 [DEVIATION-0E-1]（自交检测限时子进程化）。

---

## 目录与文件

`scripts/eval/`
| 文件 | 作用 |
|---|---|
| `eval_common.py` | 共享: sys.path 装配 / seed / JSON+中文txt 落盘 / 相机中心场景尺度 / 稳健裁剪 bbox / 距离统计 / CJK 字体 |
| `m1_render_metrics.py` | M1 渲染 PSNR/SSIM/LPIPS（vanilla 3DGS + coarse SuGaR, llffhold=8） |
| `m2_geometry.py` | M2 几何 双向点到面/点到点 + Chamfer + F-score@τ（参考A=3DGS点云, 参考B=COLMAP） |
| `m3_topology.py` | M3 拓扑 V/F/E/欧拉/连通分量/最大分量占比/非流形边/边界边/孔洞/自交/水密 |
| `m4_coverage.py` | M4 覆盖率 + 漏洞率（pytorch3d 光栅化 mesh；3DGS override_color=白→alpha） |
| `m5_efficiency.py` | M5 效率 解析计时 JSON + 网格 V/F/体积 |
| `m6_visualize.py` | M6 可视化 网格截图/误差热图/连通分量/渲染对比拼图（matplotlib CPU） |
| `run_all_eval.py` | 汇总 M1–M6, baseline vs modified 对比表（配置文件或 CLI 单变体） |
| `计时运行.sh` | M5 计时/显存包装器（墙钟、退出码、峰值显存: 本进程组 + 全卡） |
| `tests/synthetic_data.py` | 合成 mesh/点云/相机 生成器 |
| `tests/make_synthetic_gs.py` | 合成最小 3DGS 场景（相机+高斯ply+GT图）与 coarse.pt, 供 M1/M4 |
| `tests/test_m2_m3.py` | M2/M3 单元自测（CPU） |
| `tests/test_m1_m4.py` | M1/M4 单元自测（GPU, 需<1GB 显存） |
| `tests/test_m5_m6.py` | M5/M6 单元自测（CPU） |
| `tests/运行全部自测.sh` | 一键跑全部自测 |
| `tests/示例_评测配置.json` | run_all_eval 配置示例 |

输出约定: 文件名 `<指标中文>_<tag>.{json,txt}`（如 `渲染指标_基线.txt`, `几何指标_基线.json`）;
逐视角 CSV `<指标>_逐视角_<tag>.csv`; 图 `网格截图_<tag>.png / 误差热图_<tag>.png / 连通分量着色_<tag>.png / 渲染对比_<tag>.png`。

---

## 复现命令

```bash
cd /scratch/e1351071/zju_test_test && source env.sh
# 全部合成单元自测（约 3–4 分钟, 末尾 GPU 测试）
bash scripts/eval/tests/运行全部自测.sh
# 期望: 三个测试各 ALL_PASS, 末尾 "全部自测 ALL_PASS"
```

单脚本示例见各脚本首部 docstring。汇总:
```bash
python scripts/eval/run_all_eval.py --config scripts/eval/tests/示例_评测配置.json
```

---

## 逐 M 自检

### M1 渲染指标 — `m1_render_metrics.py`
- 定义: 测试视角(llffhold=8, idx%8==0)对 (a) vanilla 3DGS、(b) coarse SuGaR 渲染, 算 PSNR/SSIM/LPIPS(vgg)。
  复用 `gaussian_splatting.utils.{image_utils.psnr, loss_utils.ssim}` 与 `gaussian_splatting.lpipsPyTorch`(默认, 与仓库 metrics.py 一致；`--lpips_backend lpips` 可切换 pip 包)。
  coarse 入口严格照调研笔记: `SuGaR(..., surface_mesh_to_bind=None).render_image_gaussian_rasterizer(nerf_cameras=test_cameras, ...)`；GT 用 `nerfmodel.get_test_gt_image(i)`。LPIPS 权重缓存到 `scripts/eval/cache/`。
- 用法:
  ```bash
  python scripts/eval/m1_render_metrics.py --source_path data/tandt/truck \
    --gs_output outputs/基线_truck/3dgs_7k --iteration 7000 \
    --coarse_pt outputs/基线_truck/coarse/.../15000.pt \
    --out_dir outputs/基线_truck/评测 --tag 基线 --save_renders
  ```
- 合成自测: **PASS**。GT=高斯自渲染 → 3DGS PSNR=67.2/SSIM≈1/LPIPS≈4e-6；coarse PSNR=67.2；测试视角=2（12//8）。
- 真实(冒烟 truck, iter=500)验证: **PASS**。3DGS PSNR=19.95 SSIM=0.681 LPIPS=0.416；coarse PSNR=20.39 SSIM=0.703 LPIPS=0.397（500迭代低质属正常）。

### M2 几何指标 — `m2_geometry.py`
- 定义: mesh 表面均匀采样 N=1e6(seed固定) → 参考点云 KDTree 最近点距离(completeness 方向)；
  参考点 → mesh 表面 `o3d.t.geometry.RaycastingScene.compute_distance`(accuracy 方向)。
  报 mean/median/RMSE/P90、Chamfer(对称均值+RMSE)、F-score@τ(τ=0.005/0.01/0.02×场景尺度)；
  场景尺度=相机中心包围盒对角线；统一裁剪到相机中心 bbox×fg_bbox_factor(默认1.0)。参考 A=3DGS 高斯中心 ply, 参考 B=COLMAP `sparse/0/points3D.bin`(用 `gaussian_splatting.scene.colmap_loader`)。
- 用法:
  ```bash
  python scripts/eval/m2_geometry.py --mesh <mesh.ply> \
    --ref_a outputs/基线_truck/3dgs_7k/point_cloud/iteration_7000/point_cloud.ply \
    --ref_b_colmap data/tandt/truck/sparse/0 \
    --cameras_json outputs/基线_truck/3dgs_7k/cameras.json \
    --out_dir outputs/基线_truck/评测 --tag 基线 --n_sample 1000000
  ```
- 合成自测: **PASS**。同面参考 chamfer≈0/F@0.02≈1；偏移0.1 → accuracy≈0.10/chamfer≈0.10；裁剪有效；固定seed可复现。
- 真实(冒烟 truck)验证: **PASS**。Chamfer_A=0.0528, Chamfer_B=0.0594（两参考一致）；accuracy 0.031 < completeness 0.074；F@0.01 A=0.897 B=0.866；COLMAP 读 136029 点正常。

### M3 拓扑指标 — `m3_topology.py`
- 定义: V/F/唯一边E/欧拉数; 连通分量数、最大分量面数占比、前5大分量、小分量数(<0.1%F);
  非流形边(`get_non_manifold_edges(allow_boundary_edges=True)`, >2面); 边界边(True/False 差集, 恰好1面);
  非流形顶点; 孔洞数(边界边并查集数环); 退化三角形(面积≈0); 自交三角形(相交对数+涉及三角形数); 水密性。
  可选 trimesh 交叉验证(欧拉数/边界环)。
- 用法:
  ```bash
  python scripts/eval/m3_topology.py --mesh <mesh.ply> --out_dir outputs/基线_truck/评测 --tag 基线 \
    --self_intersect_timeout 120   # 自交超时则标记跳过
  ```
- 合成自测: **PASS**。球 euler=2/1分量/水密/边界0/自交0；带洞球 边界>0/孔洞≥1/非水密；两球 2分量/最大占比≈0.5。
- 真实(冒烟 truck)验证: **PASS**。V=173043 F=326097 欧拉=-3299 分量=1145(小分量1057) 最大占比0.433 非流形边0 边界边26587 孔洞1259 非水密; trimesh 欧拉=-3299 一致; 自交40s超时被优雅跳过。

### M4 覆盖指标 — `m4_coverage.py`
- 定义: pytorch3d 光栅化 mesh 到测试视角, 覆盖率=`(pix_to_face>=0)` 像素占比;
  3DGS 前景=对 vanilla 3DGS 用 `gs_render(override_color=白, bg=黑)` 得累积 alpha, `alpha>0.5`;
  漏洞率=(前景∧mesh无覆盖)/前景像素(主口径), 另报占全图口径。大网格分箱溢出自动退回 naive 光栅化。
- 用法:
  ```bash
  python scripts/eval/m4_coverage.py --source_path data/tandt/truck \
    --gs_output outputs/基线_truck/3dgs_7k --iteration 7000 --mesh <mesh.ply> \
    --out_dir outputs/基线_truck/评测 --tag 基线 --save_masks
  ```
- 合成自测: **PASS**。覆盖率∈(0,1)、漏洞率∈[0,1]；掩码 mesh 覆盖与 3DGS 前景 **concentric 对齐** → 证明 pytorch3d↔3DGS 相机约定一致(M4 最大风险点已排除)。
- 真实(冒烟 truck)验证: **PASS**。覆盖率=0.734, 前景占比=0.9999(500迭代floater多), 漏洞率(前景)=0.266。

### M5 效率指标 — `m5_efficiency.py` + `计时运行.sh`
- 定义: `计时运行.sh <阶段> <输出目录> [--gpu N] -- <命令>` 记录开始/结束/墙钟/退出码, 采样峰值显存(本进程组按 PGID 归集 + 全卡)。
  `m5_efficiency.py` 汇总多个计时 JSON + 网格 V/F/文件体积。
- 用法:
  ```bash
  bash scripts/eval/计时运行.sh 训练3DGS_7k outputs/基线_truck/计时 --gpu 0 -- python .../train.py ...
  python scripts/eval/m5_efficiency.py --timing_json outputs/基线_truck/计时 --mesh <mesh.ply> \
    --out_dir outputs/基线_truck/评测 --tag 基线
  ```
- 合成自测: **PASS**。计时墙钟>=1s、退出码0；M5 解析计时+网格1520面/体积>0。
- 真实(冒烟 truck)验证: **PASS**。解析真实计时 冒烟_extract 286.3s/7022MiB；网格 12.5MiB。

### M6 可视化 — `m6_visualize.py`
- 定义: matplotlib(Poly3DCollection) 纯 CPU 渲染 —— 网格截图(3视角, 画家算法排序)/点到面误差热图/连通分量着色/渲染对比拼图(GT|3DGS|coarse)。
  大网格先抽取到 `--face_budget`(默认4万面)。**说明: open3d OffscreenRenderer 在本节点无 EGL 且硬崩溃, 故用 matplotlib 兜底**(题目允许)。
- 用法:
  ```bash
  python scripts/eval/m6_visualize.py --mode all --mesh <mesh.ply> --ref data/tandt/truck/sparse/0 \
    --out_dir outputs/基线_truck/评测/图 --tag 基线
  # montage: --mode montage --gt_img .. --gs_img .. --sugar_img ..
  ```
- 合成自测: **PASS**。四类图均有效; 误差热图语义正确(近参考=蓝, 远=红)。
- 真实(冒烟 truck)验证: **PASS**。3 张图 59s; 误差热图正确显示漂浮碎块=高误差(红)。

---

## 单元自测汇总表

| 测试文件 | 覆盖 | 结果 | 数据 |
|---|---|---|---|
| `tests/test_m2_m3.py` | M2, M3 | 20/20 PASS | 合成 (open3d 球/带洞球/双球) |
| `tests/test_m5_m6.py` | M5, M6 | 14/14 PASS | 合成 (计时命令 + 球 mesh) |
| `tests/test_m1_m4.py` | M1, M4 | 17/17 PASS | 合成最小 3DGS 场景 (GPU<1GB) |

复算: `bash scripts/eval/tests/运行全部自测.sh`

---

## DEVIATION / 说明
- **[DEVIATION-0E-1]** open3d `get_self_intersecting_triangles` 在大网格极慢(326097面 >4.5min, 1520面也~8s)。
  处理(不改指标定义): 自交计算放入**带超时子进程**, 小网格精确算出, 大网格超 `--self_intersect_timeout`(默认120s) 标记“已跳过/超时”并在 txt/JSON 如实注明, 避免 run_all 卡死。单元测试(inline)仍精确计算。
- **[说明]** M3 孔洞数(并查集边界环=真实冒烟 1259) 与 trimesh `outline().entities`(=3742) 定义不同: 后者在非流形边界顶点处把环拆成多段。欧拉数二者一致(-3299), 证明 V/E/F 正确。**以并查集环数为准**。
- **[说明]** M6 用 matplotlib 而非 open3d 离屏(本节点无 EGL, OffscreenRenderer 硬崩溃)。题目已允许兜底。
- **[记录]** 额外 `pip install --no-deps trimesh(5.1.0)`(纯 python, numpy 保持 1.26.4), 仅供 M3 交叉验证, 非必需。
- **[记录]** LPIPS 默认用仓库 `gaussian_splatting.lpipsPyTorch`(vgg, 与 SuGaR metrics.py 一致), 无需 pip lpips。
- **[记录]** M6 可视化前把大网格抽取到 `--face_budget`(默认4万面), 故“连通分量着色”图标题里的分量数(基线图=538)是**抽取后网格**的, 与 M3 权威值(全网格=4851)不同, 属预期。M3 的 JSON/txt 为准。
- **[记录]** repo/SuGaR 当前 `git status` 显示 extract_mesh.py / coarse_mesh.py 被改、新增 sugar_extractors/mv_consistency_filter.py —— **这些是另一执行者实现 改动方案 的改动, 非本评测工具所为**; 本工具仅 import gs_model/sugar_model/cameras/colmap_loader/lpipsPyTorch/gaussian_renderer 等未改动模块, 行为不受影响。

---

## 基线评测（阶段 1b）— 已完成

对基线 truck 完整跑 M1–M6（真实数据, 非合成）。输入:
- 3DGS 7k: `outputs/基线_truck/3dgs_7k`（cameras.json + iteration_7000/point_cloud.ply, 424177/? 高斯）
- coarse .pt: `outputs/基线_truck/coarse/sugarcoarse_3Dgs7000_densityestim02_sdfnorm02/15000.pt`
- 基线 mesh: `outputs/基线_truck/mesh/sugarmesh_3Dgs7000_densityestim02_sdfnorm02_level03_decim1000000.ply`（V=750841, F=1437272）
- 源/测试集: `data/tandt/truck`（llffhold=8, 32 测试视角）
- 参考 A=3DGS 高斯中心, 参考 B=COLMAP `sparse/0`（136029 点）

一键复现: `cd /scratch/e1351071/zju_test_test && source env.sh && bash scripts/eval/跑基线评测.sh`
产物目录: `outputs/基线_truck/评测/`（每项 json + 中文 txt + 逐视角 csv；`评测汇总_基线.{json,txt}`；`图/` 可视化）。
已复制(非移动)到 `考核提交/指标/`(21 文件) 与 `考核提交/可视化/`(截图/热图/分量图/2 张渲染对比/覆盖掩码)。

| 指标 | 关键实测值 | 耗时 | 结果 |
|---|---|---|---|
| M1 渲染 | 3DGS-7k: PSNR=23.92 SSIM=0.849 LPIPS=0.202 ; coarse SuGaR: PSNR=24.32 SSIM=0.848 LPIPS=0.217（32 测试视角） | ~43s | PASS |
| M2 几何 | 参考A(3DGS): Chamfer=0.0326, completeness=0.0495, accuracy=0.0156, F@0.01=0.946 ; 参考B(COLMAP): Chamfer=0.0531, comp=0.0819, acc=0.0242, F@0.01=0.888（两参考结论一致: 精度优于完整度, A 优于 B） | ~11s | PASS |
| M3 拓扑 | V=746704 F=1437272 E=2204180 欧拉=-20204 连通分量=4851(小分量4823) 最大分量占比=0.495 非流形边=0 边界边=96544 非流形顶点=15001 孔洞=7970 退化面=0 非水密 | ~200s(含120s自交超时) | PASS（自交按 DEVIATION-0E-1 超时跳过, 已注明） |
| M4 覆盖 | 网格渲染覆盖率=0.929, 3DGS前景占比=0.9916, 漏洞率(前景)=0.0666, 网格覆盖前景=0.933（32 视角, 掩码已存） | ~50s | PASS |
| M5 效率 | 训练3DGS_7k 118.6s/6624MiB ; coarse_dn_15k 950.6s/10098MiB ; 提取mesh 359.1s/8274MiB ; 总墙钟 1428.3s(23.8min) ; 网格 750841顶点/1437272面/54.34MiB | ~5s | PASS |
| M6 可视化 | 网格截图_基线.png / 误差热图_基线.png / 连通分量着色_基线.png / 渲染对比_基线_视角000/001.png(GT|3DGS|coarse) 全部产出且有效 | ~90s | PASS |

汇总: `outputs/基线_truck/评测/评测汇总_基线.txt`（及 `.json`）。

真实数据结论: **M1–M6 全部在基线真实数据上 PASS, 无失败项**。
数字自洽性抽查: M4 覆盖率 0.929 明显高于 500 迭代冒烟场景的 0.734（7k 模型几何更贴合高斯, 漏洞率 0.067≪0.266）；
M3 连通分量 4851 与 M2 completeness 偏大共同印证“coarse mesh 存在大量漂浮碎块/背景壳”——正是 改动方案 H1 要改善的对象。
所有数值可由上述一键命令复算。
