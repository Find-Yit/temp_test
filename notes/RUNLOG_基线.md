# RUNLOG 阶段1 基线复现 — SuGaR (tandt/truck)

工作目录: /scratch/e1351071/zju_test_test
执行者: opus48-executor (claude-opus-4-8[1m], max)
环境: `cd /scratch/e1351071/zju_test_test && source env.sh`
SuGaR commit: `7c10c4ae4a267dece512f5c7f40ed212a0a2ab44` (short 7c10c4a, 2024-09-24 "Minor fix.")
GPU: NVIDIA H200 143GB 单卡（gpu=0）; seed 全链路固定 0（见下）。

---

## 步骤 1：命令链分析（阅读 repo/SuGaR 源码后确定的"只跑 coarse 不跑 refine"最短链）

### 1.1 关键源码事实
- **repo 根目录没有 `train_coarse_density_and_dn_consistency.py`**；只有 `train_coarse_density.py`、`train_coarse_sdf.py`、`train.py`（全流程，含 refine，不用）。dn_consistency 只能通过 trainer 函数
  `sugar_trainers/coarse_density_and_dn_consistency.py::coarse_training_with_density_regularization_and_dn_consistency(args)` 调用。→ 我在 `scripts/` 下写 wrapper（见步骤 1.3），不改仓库文件。
- trainer 关键**硬编码**（`sugar_trainers/coarse_density_and_dn_consistency.py`）：
  - L138 `num_iterations = 15_000`（不从 args 读）
  - L315 `save_milestones = [15_000]`（不从 args 读；另有 `save_model_every_n_iterations=1_000_000` 基本不触发）
  - L189 `start_dn_consistency_from = 9000`（dn_consistency 正则在 **iter>9000** 才生效）
  - L195-196 entropy: start 7000 → end 9000；L203 sdf 正则 start 9000；sdf estimation start 9000
  - → 冒烟用极小 num_iterations 时，以上正则都不会触发（阈值>迭代数），冒烟只验证"训练→存 .pt→提取→.ply"链路连通，可接受。
  - trainer 读取的 args 字段：checkpoint_path, scene_path, iteration_to_load, output_dir, eval, estimation_factor, normal_factor, gpu, white_background。**无 seed、无 num_iterations 入参**。
- trainer .pt 保存路径：`<output_dir>/sugarcoarse_3Dgs{iter}_densityestim{XX}_sdfnorm{YY}/{iteration}.pt`
  其中 XX=estimation_factor 去点（0.2→"02"），YY=normal_factor 去点（0.2→"02"）。
  → 默认 estimation=normal=0.2 时目录为 `sugarcoarse_3Dgs7000_densityestim02_sdfnorm02/`，文件名 `15000.pt`（或降迭代后的迭代数.pt）。
- extractor `sugar_extractors/coarse_mesh.py::extract_mesh_from_coarse_sugar(args)`：
  - **poisson_depth=10 (L43)、vertices_density_quantile=0.1 (L44) 均为硬编码默认值**，恰好等于计划目标值 → 无需任何 CLI flag。
  - fg_bbox_factor=1.0 (L41), bg_bbox_factor=4.0 (L42)。
  - `-l` surface_level, `-d` **decimation_target（目标顶点数，非 poisson_depth！）**, `-m` coarse .pt **完整路径**, `-c` 3DGS 输出目录, `-i` 7000, `-o` 输出目录。
  - **不保存"表面采样点云"**（只在 L520 存 mesh）。计划要求另存表面采样点云 → 需 additive 副本（见步骤 1.3）。
- extractor `-m` 传 .pt 完整路径（`torch.load(args.coarse_model_path)`）；`-c` 传 3DGS 输出目录（`GaussianSplattingWrapper(output_path=...)` 读 `point_cloud/iteration_7000/point_cloud.ply`）。
- 3DGS `gaussian_splatting/train.py`：`-s` source, `-m` model_out, `--iterations`, `--save_iterations`, `--test_iterations`, `--eval`；`safe_state()` 固定 seed=0；首次运行会从 `sparse/0/points3D.bin` 生成 `sparse/0/points3D.ply`（trainer L415 fetchPly 需要它）。

### 1.2 [DEVIATION-1-1] 计划 extract flag 与实际 CLI 不符
计划阶段1 L15 写 `extract_mesh.py ... -l 0.3 -d 10 -q 0.1 (poisson_depth 10, vertices_density_quantile 0.1)`。
**实际**：`extract_mesh.py` 无 `-q`；`-d` 是 decimation_target（目标顶点数），`-d 10` 会把网格抽简到 10 个顶点（错误）。
计划**意图**的 poisson_depth=10 与 vertices_density_quantile=0.1 **已是 coarse_mesh.py 硬编码默认**，无需任何 flag。
**替代方案（不改计划意图）**：extract 命令用 `-l 0.3`（surface_level），decimation_target 用 SuGaR high_poly 默认 `-d 1000000`（1M 目标顶点，>1e5 验收线），poisson_depth/quantile 走硬编码默认 10/0.1。已在总计划/Fable 处以 [DEVIATION] 报告。

### 1.3 新增脚本（只在 scripts/ 下新增，不改 repo 文件）
- `scripts/coarse_dn_trainer_param.py` = `coarse_density_and_dn_consistency.py` 逐字副本，仅 2 处外科修改：
  `num_iterations` 与 `save_milestones` 改为从 args 读（`getattr(args,...,原默认)`）。args 无 num_iterations 时行为与 repo **完全一致**（可 diff 核验）。
- `scripts/run_coarse_dn.py` = 驱动上面 trainer 的 wrapper：固定 seed（torch/np/random/cuda manual_seed(0)），argparse 传参，调用 trainer。
- `scripts/coarse_mesh_savepts.py` = `coarse_mesh.py` 逐字副本 + additive：当 `args.surfpts_dir` 非空时，额外把 surface_points（全部）与 fg_points（前景）存为 .ply。surfpts_dir=None 时 mesh 输出与 repo **逐字节一致**（可 diff 核验）。
- `scripts/run_extract_mesh.py` = 驱动上面 extractor 的 wrapper（镜像 extract_mesh.py 参数 + `--surfpts_dir`）。
- `scripts/eval/计时运行.sh` = 墙钟(date +%s 差) + 后台 nvidia-smi 轮询峰值显存 的通用计时封装。

### 1.4 最短命令链（只 coarse、不 refine）
```
# (1) 3DGS 7k
python repo/SuGaR/gaussian_splatting/train.py -s data/tandt/truck -m outputs/基线_truck/3dgs_7k \
    --iterations 7000 --save_iterations 7000 --test_iterations 7000 --eval --quiet
# (2) coarse dn_consistency 15k
python scripts/run_coarse_dn.py -s data/tandt/truck -c outputs/基线_truck/3dgs_7k -i 7000 \
    -o outputs/基线_truck/coarse --num_iterations 15000 --eval True
# (3) extract mesh (surface_level 0.3, poisson_depth 10 默认, quantile 0.1 默认, decim 1M) + 存表面采样点云
python scripts/run_extract_mesh.py -s data/tandt/truck -c outputs/基线_truck/3dgs_7k -i 7000 \
    -m outputs/基线_truck/coarse/sugarcoarse_3Dgs7000_densityestim02_sdfnorm02/15000.pt \
    -l 0.3 -d 1000000 -o outputs/基线_truck/mesh --surfpts_dir outputs/基线_truck/mesh --eval True
```

---
（后续每阶段状态在此文件追加）

---

## 步骤 2：冒烟（outputs/冒烟_truck/）

冒烟场景 truck，3DGS 500 it → coarse num_iterations=7100（=100 真实步，见下 [关键发现]）→ extract（surface_level 0.3, decim 200k）。

### [关键发现-1] coarse trainer 的 num_iterations 是"最终迭代计数器"而非"真实步数"
`coarse_density_and_dn_consistency.py` L562-563：`if initialize_from_trained_3dgs: iteration = 7000 - 1`。
训练主循环 `for batch...: if iteration >= num_iterations: break`，迭代计数从 **6999** 起。
- 因此 **真实优化步数 = num_iterations − 7000**。默认 num_iterations=15000 → **约 8000 真实步**。
- num_iterations **必须 > 7000**，否则循环一次都不执行，`loss` 未赋值 → `UnboundLocalError`（冒烟第一次用 300 就是此错，非 bug，是 repo 设计）。
- 正则起点均为绝对迭代号：entropy 7000→9000、dn_consistency >9000、sdf >9000。所以 num_iterations 越接近 9000，dn_consistency 生效步数越少（9000 时≈0 步）。正式基线用 15000（dn_consistency 得约 6000 步），符合计划意图。
- 对 [DEVIATION 阶段1-步骤5] 的影响：墙钟外推要按真实步数(约8000)算；若需降迭代，num_iterations 应显著 > 9000 才能让 dn_consistency 有效（例如 ≥ 12000）。

### [关键发现-2 / 已修复] 3DGS 输出目录需尾斜杠
`sugar_scene/cameras.py:34` 用 `open(gs_output_path + 'cameras.json')` 字符串拼接（唯一一处需尾斜杠；source_path 用 os.path.join 不受影响）。
我的 wrapper 用 os.path.abspath 会去掉尾斜杠 → `3dgs_500cameras.json` FileNotFoundError。
**修复（仅改 scripts/ wrapper，不碰 repo）**：run_coarse_dn.py / run_extract_mesh.py 对 checkpoint_path 补 `os.sep`。

### [环境变更-非我方] 外部对 repo 的 stage-2a 预置改动（我方基线已隔离）
执行期间检测到外部（Fable/协调方）改动 repo 文件：`M extract_mesh.py`、`M sugar_extractors/coarse_mesh.py`、新增 `?? sugar_extractors/mv_consistency_filter.py`（多视角深度一致性剔点，默认关闭）。
- **非本执行者所为，未回退**（遵循系统提示"take as current state"）。
- **对阶段1基线无影响**：基线提取走 `scripts/coarse_mesh_savepts.py`（我方副本，源自 7c10c4a 原始 coarse_mesh.py）与 `scripts/run_extract_mesh.py`，不 import 被改动的 repo 文件。
- 已核验：`scripts/coarse_mesh_savepts.py` vs `git show HEAD:sugar_extractors/coarse_mesh.py`（原始7c10c4a）= 0 处删除/修改 + 26 行纯 additive（PARAM+表面点云保存）；`scripts/coarse_dn_trainer_param.py` vs HEAD 原始 = 仅 2 处外科替换。基线脚本对 7c10c4a 忠实。

### 冒烟结果
- 3DGS 500it: EXIT=0, ~8s(500步)/墙钟~27s(含数据加载), 产物 point_cloud/iteration_500/point_cloud.ply。
- coarse 7100(=100步): EXIT=0, 墙钟 24.6s, 峰值显存(本组) 3280 MiB, loss=0.1397(有限, 无 NaN), 触发 entropy 正则; 产物 sugarcoarse_3Dgs500_densityestim02_sdfnorm02/7100.pt。
- extract: 见下（正在跑）。
- extract(smoke): EXIT=0, 墙钟约115s(前台120s超时转后台, 后台完成 exit0), FG mesh 1.21M→decim, BG 1.02M→decim。
  产物: sugarmesh_3Dgs500_..._level03_decim200000.ply (V=174068, F=326097, 13MB);
  表面采样点云_全部_level03.ply (10,000,197 点, 487MB); 表面采样点云_前景_level03.ply (6,185,860 点, 301MB)。
  open3d 可读, F>0。**冒烟全链路 PASS**。

---

## 步骤 3：正式基线（outputs/基线_truck/）

### 3-A. 3DGS 7000 it（outputs/基线_truck/3dgs_7k）
- 命令: `python repo/SuGaR/gaussian_splatting/train.py -s data/tandt/truck -m outputs/基线_truck/3dgs_7k --iterations 7000 --save_iterations 7000 --test_iterations 7000 --eval --quiet`
- 墙钟 118.633s；退出码 0；峰值显存 本进程组 6624 MiB / 全卡 6873 MiB（计时_训练3DGS_7k.txt/.json）。
- 产物: point_cloud/iteration_7000/point_cloud.ply（含 cameras.json, cfg_args, input.ply）。--eval → llffhold=8 划分（truck 219 train / 32 test）。
- seed: 3DGS safe_state 固定 0；PYTHONHASHSEED=0。首次运行已在 data/tandt/truck/sparse/0/ 生成 points3D.ply（3DGS 从 .bin 派生的缓存, 非 repo 文件）。
- 训练日志无 NaN；末步 Loss=0.062。

### 3-B. coarse dn_consistency 15000（进行中）
- 命令: `python scripts/run_coarse_dn.py -s data/tandt/truck -c outputs/基线_truck/3dgs_7k -i 7000 -o outputs/基线_truck/coarse --num_iterations 15000 --eval True`
- num_iterations=15000 → 真实步 ≈ 8000（迭代 7000→15000）；dn_consistency 在 9000 后生效（约 6000 步有效）。
- 速度外推与 [DEVIATION 步骤5] 决策见下。

### [DEVIATION 步骤5 判定] 不触发降迭代
前 7 个 200-迭代区间(iter 7200→8400, 均为 dn/sdf 生效前)自报时间: 约 {0.180, 0.051, 0.177, 0.051, 0.177, 0.050, 0.050} 分钟(重/轻交替, 重区间疑为周期性 Resetting neighbors)。
平均 ≈ 0.105 分/200 迭代 ≈ **30 it/s**(前正则期)。8000 真实步的乐观外推 ≈ 4.2 分钟；即便 dn_consistency+sdf(iter>9000, 6000 步)带来 3–4× 减速, 总墙钟外推 ≈ 12–15 分钟, **远 < 60 分钟阈值**。→ **保持 num_iterations=15000, 不降迭代**(post-9000 实测速率将在完成时复核并记录)。

### [DEVIATION 步骤5 复核] post-9000 实测速率 → 仍不触发
dn_consistency+sdf 在 iter>9000 生效后, 200-迭代区间自报时间跃升至约 {9200:0.44, 9400:0.56, 9600:0.60, 9800:0.56} 分钟(≈6 it/s, 较前正则期慢约 4–10×, 属正则化开销, 非 bug)。
剩余 5200 迭代外推 ≈ 15 min；coarse 总墙钟外推 ≈ 20 min < 60 min → **确认不降迭代, num_iterations=15000 到底**。

### [环境观察] 机器为共享节点, 存在他方并行进程(非本执行者)
执行期间 `ps`/`nvidia-smi` 显示他方 session 在本项目内并行跑 stage-2a: `scratchpad/run_extract_repo.py --mv_filter False`(读我方冒烟输出, 写 outputs/<改动对照>/<off>) 与 `m3_topology.py`(评我方冒烟 mesh)。
- 这些进程**只读我方冒烟产物、写到不同目录**, 与 outputs/基线_truck/ 无文件冲突; 未干预、未 kill。
- 影响: GPU/CPU 存在轻度并行争用, 我方各阶段墙钟(计时运行 date 差)会**如实包含争用开销**(已在汇总注明"共享节点实测")。峰值显存"本进程组"口径经 PGID 归集, 只计我方进程, 不受他方影响。

### 3-B/3-C. 正式基线最终结果（全部 EXIT=0）
| 阶段 | 命令(见汇总) | 墙钟 | 峰值显存 本组/全卡(MiB) | 退出码 |
|---|---|---|---|---|
| 3DGS 7000it | gaussian_splatting/train.py ... --eval --quiet | 118.633s (1.98min) | 6624 / 6873 | 0 |
| coarse dn_consistency 15000 | scripts/run_coarse_dn.py ... --num_iterations 15000 | 950.633s (15.84min) | 10098 / 19726 | 0 |
| extract_mesh (l0.3 d1e6) +表面点云 | scripts/run_extract_mesh.py ... --surfpts_dir | 359.079s (5.98min) | 8274 / 15311 | 0 |
| **合计** | | **1428.345s (23.81min)** | 全卡峰值 19726 | |

- coarse 训练结束: `Training finished after 15000 iterations with loss=0.0953274592757225.`（有限, 无 NaN）。3DGS/coarse 日志 nan 计数均=0。
- 产物路径:
  - 3DGS ckpt: outputs/基线_truck/3dgs_7k/point_cloud/iteration_7000/point_cloud.ply (437.85 MB)
  - coarse .pt: outputs/基线_truck/coarse/sugarcoarse_3Dgs7000_densityestim02_sdfnorm02/15000.pt (286.41 MB)
  - mesh: outputs/基线_truck/mesh/sugarmesh_3Dgs7000_densityestim02_sdfnorm02_level03_decim1000000.ply
    **V=750841, F=1437272**, 连通分量 4851, 最大分量面占比 0.4953, 54.34 MB, open3d 可读, F>0 ✓ V>1e5 ✓。
  - 表面采样点云: 全部 10,000,197 点 (486.38MB); 前景 7,405,147 点 (360.17MB)。
- 汇总落盘: outputs/基线_truck/基线汇总.txt 与 .json（双份, 中文键）。
- 计时/显存落盘: outputs/基线_truck/计时/计时_{训练3DGS_7k,coarse_dn_15k,提取mesh}.{txt,json}。

### 条目9 墙钟-时间戳一致性核对（PASS）
- 3DGS 计时 11:57:34→11:59:33 (118.6s)；coarse 12:00:02→12:15:53 (950.6s), coarse.log mtime 12:15:56（与 END 差~3s, 末次保存）；extract 12:15:55→12:21:54 (359.1s), extract.log mtime 12:21:56。
- 顺序链: 3DGS结束11:59:33 → coarse开始12:00:02 → coarse结束12:15:53 → extract开始12:15:55 → extract结束12:21:54，无重叠/矛盾。一致。

### 步骤4 记录清单（完成）
命令、commit 7c10c4a、seed 0、迭代数(3DGS 7000 / coarse num_iterations=15000≈8000真实步 / extract l0.3 d1e6)、各阶段墙钟、峰值显存、输出路径、mesh V/F、文件体积 —— 均已落盘于 RUNLOG(本文件) + outputs/基线_truck/基线汇总.txt/.json。

### 考核提交副本（cp, 未移动）
- 考核提交/网格/基线_truck_coarse网格.ply (55M) ← mesh
- 考核提交/网格/基线_truck_表面采样点云_全部.ply (487M) ← 表面采样点云_全部_level03.ply
- 考核提交/网格/基线_truck_表面采样点云_前景.ply (361M) ← 表面采样点云_前景_level03.ply
- 考核提交/指标/基线汇总.txt 与 基线汇总.json ← outputs/基线_truck/基线汇总.*
- 考核提交/日志/RUNLOG_基线.md ← 本文件（本节写入后重新复制）
