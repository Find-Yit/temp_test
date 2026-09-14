# SELF_CHECK 阶段1 基线复现（tandt/truck）— 最终

执行者: opus48-executor。环境: `cd /scratch/e1351071/zju_test_test && source env.sh`。
SuGaR commit **7c10c4a**；seed=0（PYTHONHASHSEED=0 + torch/np/random/cuda manual_seed(0)；SuGaR trainer 本身无 seed，CUDA atomicAdd 仍有轻微非确定性，已在报告注明）。
流水线: 3DGS 7000it → coarse dn_consistency（num_iterations=15000，真实步≈8000）→ extract_mesh（surface_level=0.3, poisson_depth=10默认, vertices_density_quantile=0.1默认, decimation_target=1e6）。**不跑 refine。**
总墙钟 **1428.35s (23.81min)**，各阶段 EXIT 均=0。

## 验收条目（计划阶段1验收 + 任务交付）

| # | 条目 | 期望 | 实测 | 判定 | 复算命令 |
|---|------|------|------|------|----------|
| 1 | 命令链记录（只 coarse 不 refine） | RUNLOG 步骤1 完整 | RUNLOG 步骤1.4 三条命令链 + 源码依据 | **PASS** | `sed -n '/## 步骤 1/,/## 步骤 2/p' notes/RUNLOG_基线.md` |
| 2 | 冒烟全链路 | 得可读 .ply | 3DGS500→coarse7100→extract, mesh V=174068 F=326097, open3d可读 | **PASS** | `ls outputs/冒烟_truck/mesh/` |
| 3 | 3DGS 7k ckpt 存在 | iteration_7000/point_cloud.ply | 存在, 437.85 MB | **PASS** | `ls -lh outputs/基线_truck/3dgs_7k/point_cloud/iteration_7000/point_cloud.ply` |
| 4 | coarse .pt 存在 | 15000.pt | 存在, 286.41 MB | **PASS** | `ls -lh outputs/基线_truck/coarse/sugarcoarse_3Dgs7000_densityestim02_sdfnorm02/15000.pt` |
| 5 | 训练日志无 NaN | nan 计数=0 | 3DGS=0, coarse=0; coarse 末 loss=0.0953(有限) | **PASS** | `grep -aci nan logs/基线_3dgs_7k.log logs/基线_coarse_15k.log` |
| 6 | mesh open3d可读 & V>1e5 & F>0 | V>100000, F>0 | **V=750841, F=1437272**, 连通分量4851, 最大分量占比0.4953 | **PASS** | `python scripts/校验_基线mesh.py` |
| 7 | 表面采样点云已存(.ply) | 全部+前景各一 | 全部10,000,197点(486MB), 前景7,405,147点(360MB) | **PASS** | `ls -lh outputs/基线_truck/mesh/表面采样点云_*.ply` |
| 8 | 各阶段墙钟+峰值显存落盘(+双份) | 3计时json/txt+基线汇总txt/json | 计时_{3阶段}.{txt,json} + 基线汇总.{txt,json} 齐全 | **PASS** | `cat outputs/基线_truck/基线汇总.txt; ls outputs/基线_truck/计时/` |
| 9 | 墙钟与日志时间戳一致 | 计时END≈log mtime, 链无矛盾 | coarse END12:15:53/log mtime12:15:56; extract END12:21:54/mtime12:21:56; 顺序链一致 | **PASS** | 见 RUNLOG "条目9" |
| 10 | 考核提交副本(cp) | 网格/指标/日志三处 | 6 文件已复制(见下) | **PASS** | `find 考核提交 -type f` |
| 11 | 未改 repo 现有文件(基线路径忠实) | 基线脚本=7c10c4a原始+additive | extractor副本 0删改+26增; trainer副本 仅2处外科替换; 我方未改任何repo文件 | **PASS** | `git -C repo/SuGaR show HEAD:sugar_extractors/coarse_mesh.py \| diff - scripts/coarse_mesh_savepts.py` |

**总判定: 11/11 PASS。**

## 各阶段实测（墙钟 / 峰值显存本组·全卡 / 退出码）
- 训练3DGS_7k: 118.633s (1.98min) / 6624·6873 MiB / 0
- coarse_dn_15k: 950.633s (15.84min) / 10098·19726 MiB / 0
- 提取mesh: 359.079s (5.98min) / 8274·15311 MiB / 0
- 合计: 1428.345s (23.81min)，全卡峰值 19726 MiB

## 产物路径（绝对）
- 3DGS: /scratch/e1351071/zju_test_test/outputs/基线_truck/3dgs_7k/point_cloud/iteration_7000/point_cloud.ply
- coarse: /scratch/e1351071/zju_test_test/outputs/基线_truck/coarse/sugarcoarse_3Dgs7000_densityestim02_sdfnorm02/15000.pt
- mesh: /scratch/e1351071/zju_test_test/outputs/基线_truck/mesh/sugarmesh_3Dgs7000_densityestim02_sdfnorm02_level03_decim1000000.ply
- 表面采样点云: /scratch/e1351071/zju_test_test/outputs/基线_truck/mesh/表面采样点云_{全部,前景}_level03.ply
- 汇总: /scratch/e1351071/zju_test_test/outputs/基线_truck/基线汇总.{txt,json}
- 计时: /scratch/e1351071/zju_test_test/outputs/基线_truck/计时/计时_{训练3DGS_7k,coarse_dn_15k,提取mesh}.{txt,json}

## 考核提交副本（cp，非移动）
- /scratch/e1351071/zju_test_test/考核提交/网格/基线_truck_coarse网格.ply (55M)
- /scratch/e1351071/zju_test_test/考核提交/网格/基线_truck_表面采样点云_全部.ply (487M)
- /scratch/e1351071/zju_test_test/考核提交/网格/基线_truck_表面采样点云_前景.ply (361M)
- /scratch/e1351071/zju_test_test/考核提交/指标/基线汇总.txt
- /scratch/e1351071/zju_test_test/考核提交/指标/基线汇总.json
- /scratch/e1351071/zju_test_test/考核提交/日志/RUNLOG_基线.md

## DEVIATION / 环境事件汇总
- **[DEVIATION-1-1]** 计划 extract flag `-d 10 -q 0.1`（当作 poisson_depth/quantile）与实际 CLI 不符：`extract_mesh.py` 无 `-q`，`-d`=decimation_target（`-d 10` 会抽简到10顶点）；意图值 poisson_depth=10 / vertices_density_quantile=0.1 **已是 coarse_mesh.py 硬编码默认**（L43/L44），无需 flag。基线改用 `-l 0.3 -d 1000000`（high_poly 1M 目标顶点），poisson/quantile 走默认。**影响：无（意图完全达成）**。
- **[关键发现-1]** coarse trainer `num_iterations` 是"最终迭代计数器"（迭代从6999起，真实步=num_iterations−7000），且必须>7000。默认15000→约8000真实步，dn_consistency(>9000)约6000有效步。冒烟据此用7100。
- **[关键发现-2/已修复]** SuGaR `cameras.py` 用 `gs_output_path+'cameras.json'` 需尾斜杠；wrapper 已对 checkpoint_path 补 `os.sep`（仅改 scripts/，未碰 repo）。
- **[DEVIATION 步骤5] 未触发**：前正则期≈30it/s、post-9000(dn+sdf)≈6it/s，coarse 实测 950.6s(15.8min)≪60min，num_iterations 保持 15000。
- **[环境-非我方]** 外部 session 并行改 repo `extract_mesh.py`/`coarse_mesh.py` + 新增 `mv_consistency_filter.py`（stage-2a），并跑 mv_filter 对照/ M3 评测（读我方冒烟产物）。**我方基线走 scripts/ 副本，依赖 sugar_scene/·sugar_utils/ 均未被改动，完全隔离**；未回退、未干预他方进程。
- **[环境观察]** 共享节点，各阶段墙钟如实含轻度 GPU/CPU 争用；峰值显存"本组"口径经 PGID 归集只计我方。

## 复算入口
```
cd /scratch/e1351071/zju_test_test && source env.sh
python scripts/校验_基线mesh.py         # 期望 OVERALL: PASS, V=750841 F=1437272
python scripts/生成基线汇总.py           # 重生成 基线汇总.txt/.json
grep -aci nan logs/基线_3dgs_7k.log logs/基线_coarse_15k.log   # 期望 0 0
git -C repo/SuGaR show HEAD:sugar_trainers/coarse_density_and_dn_consistency.py | diff - scripts/coarse_dn_trainer_param.py  # 期望仅2处
```
