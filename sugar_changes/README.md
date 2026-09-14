# 对 SuGaR（commit 7c10c4a）的改动文件

本目录集中呈现「改在哪」，便于审阅。

- **[`代码改动位置.md`](代码改动位置.md)** —— 逐处改动的**文件 / 函数 / 行号范围 / 改了什么 / 为什么**，
  以及 `mv_consistency_filter.py` 的**函数清单与一句话说明**（推荐先看这份）。
- **[`改动.patch`](改动.patch)** —— 对**已跟踪文件**的最新 `git diff`（`git -C repo/SuGaR diff` 生成）。
  按 git 语义只含 `extract_mesh.py` 与 `coarse_mesh.py` 的修改，**不含**新增文件。
- 三个被改/新增文件的**当前副本**（把它们覆盖到官方 SuGaR 仓库同名路径即可复现改动；默认 `--mv_filter False`，行为与原版一致）：
  - `extract_mesh.py`：新增 `--mv_*` 命令行参数并透传。
  - `sugar_extractors/coarse_mesh.py`：在表面点采样之后、前/背景分离与 Poisson 之前调用过滤器，并落盘剔点统计与剔点前后点云。
  - `sugar_extractors/mv_consistency_filter.py`：**新增文件（已在本目录 `sugar_extractors/` 内）**，多视角深度一致性投票过滤器（核心改动）。因是未跟踪新文件，不出现在 `改动.patch`，请直接查看此副本。
