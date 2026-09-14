# 对 SuGaR（commit 7c10c4a）的改动文件

本目录是 `repo/SuGaR` 中被修改/新增的三个文件的副本，便于审阅；`改动.patch` 为对已跟踪文件的 git diff。
将本目录内容覆盖到官方 SuGaR 仓库同名路径即可复现改动（默认 `--mv_filter False`，行为与原版一致）。

- `extract_mesh.py`：新增 `--mv_*` 命令行参数并透传。
- `sugar_extractors/coarse_mesh.py`：在表面点采样之后、前/背景分离与 Poisson 之前调用过滤器，并落盘剔点统计与剔点前后点云。
- `sugar_extractors/mv_consistency_filter.py`：新增，多视角深度一致性投票过滤器（核心改动）。
