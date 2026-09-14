# COMMITS.md — 阶段 0A 代码仓库与子模块记录

生成时间: 2026-09-14 11:11 (+0000)
克隆命令: `cd /scratch/e1351071/zju_test_test/repo && git clone --recursive https://github.com/Anttwo/SuGaR.git`
克隆结果: 成功 (CLONE_EXIT=0)，`--recursive` 正常返回。

## 仓库路径
- SuGaR 根: `/scratch/e1351071/zju_test_test/repo/SuGaR`

## 主仓库
| 项目 | 值 |
|------|----|
| 名称 | SuGaR (Anttwo/SuGaR) |
| 远程 URL | https://github.com/Anttwo/SuGaR.git |
| 分支 | main |
| commit hash | `7c10c4ae4a267dece512f5c7f40ed212a0a2ab44` |
| 提交日期 | 2024-09-24 12:14:40 -0400 |
| 提交信息 | "Minor fix." |

## 关于"子模块"的重要结构说明（与计划假设不同，见下方 [DEVIATION]）
本次 clone 的 Anttwo/SuGaR@7c10c4a 中，`gaussian_splatting`、
`gaussian_splatting/submodules/diff-gaussian-rasterization`、
`gaussian_splatting/submodules/simple-knn` 以及
`.../diff-gaussian-rasterization/third_party/glm`
**全部以普通文件形式直接提交进 SuGaR 仓库（vendored / 内嵌）**，
并非活跃的 git submodule。

证据:
- SuGaR 根目录**没有** `.gitmodules`。
- `git submodule status --recursive` 返回空。
- `git ls-files -s | awk '$1==160000'` 的 gitlink(mode 160000) 数量 = **0**（无任何子模块链接）。
- 这些目录的源码都被 SuGaR 直接跟踪，例如 glm 有 **1529** 个文件由 SuGaR 直接 track；
  diff-gaussian-rasterization/cuda_rasterizer/*.cu、simple-knn/*.cu 均被直接 track。
- 唯一存在的 `.gitmodules` 位于 `.../diff-gaussian-rasterization/.gitmodules`（内容仅是
  指向 glm 的历史声明），但该子模块并未以链接形式生效，glm 内容已内嵌。

因此: 各"子模块"没有独立于 SuGaR 的 commit hash——它们的版本即随 SuGaR
commit `7c10c4ae...` 一起冻结。以下记录各组件的**内嵌版本 + 可核实的上游出处**。

## 内嵌组件（版本随 SuGaR@7c10c4a 冻结）
| 组件 | 仓内路径(相对 SuGaR 根) | 上游出处 | 出处核实方式 |
|------|------|----------|--------------|
| gaussian_splatting | `gaussian_splatting/` | https://github.com/graphdeco-inria/gaussian-splatting | SuGaR README.md 明确引用该 URL |
| diff-gaussian-rasterization | `gaussian_splatting/submodules/diff-gaussian-rasterization/` | 标准 3DGS 光栅化器 (upstream: graphdeco-inria/diff-gaussian-rasterization) | setup.py 包名 `diff_gaussian_rasterization`；仓内未 pin 上游 URL（无生效 .gitmodules），上游为业界公认出处 |
| simple-knn | `gaussian_splatting/submodules/simple-knn/` | 标准 3DGS simple-knn (upstream: gitlab.inria.fr/bkerbl/simple-knn) | setup.py 包名 `simple_knn`；仓内未 pin 上游 URL，上游为业界公认出处 |
| glm | `gaussian_splatting/submodules/diff-gaussian-rasterization/third_party/glm/` | https://github.com/g-truc/glm.git | `.../diff-gaussian-rasterization/.gitmodules` 记录该 URL；内嵌版本 **GLM 0.9.9.9**（`glm/detail/setup.hpp`: `GLM_VERSION_MESSAGE "GLM: version 0.9.9.9"`） |

## 编译所需源码就绪确认（供阶段 0B）
- diff-gaussian-rasterization: `setup.py`、`ext.cpp`、`rasterize_points.cu`、`cuda_rasterizer/{forward,backward,rasterizer_impl}.cu` 等齐全。
- simple-knn: `setup.py`、`ext.cpp`、`simple_knn.cu`、`spatial.cu` 齐全。
- glm 头文件: `third_party/glm/glm/glm.hpp` 存在，共 277 个 .hpp（被 SuGaR track 的 glm 文件 1529 个）。

## [DEVIATION] 计划假设 vs 现实
- 计划(0A)写: "确保 gaussian_splatting 子模块及其 submodules diff-gaussian-rasterization/simple-knn 全部拉下来；若递归失败则 git submodule update --init --recursive"。
- 现实: 该仓库版本已把上述所有依赖**内嵌为普通文件**，不存在活跃 submodule，故 `git submodule update --init --recursive` 无对象可更新（也无需执行）。
- 影响: **无负面影响**。计划意图（编译所需全部源码——含 glm——都在本地）已 100% 满足。仅"记录各子模块独立 commit hash"这一条在物理上不适用，改为记录内嵌版本 + 上游出处（见上表）。
