# SELF_CHECK 报告改动结果节

写作者 opus46-writer | 日期 2026-09-14

## 一、数字→来源核对表

### 摘要 (abstract.tex)

| 报告数字 | 值 | 来源文件 | 字段/位置 |
|---|---|---|---|
| 场景名 | truck | 计划 / 数据目录 | data/tandt/truck |
| 3DGS 迭代 | ≤7,000 | plans/SuGaR考核总计划.txt | 阶段1 |
| Coarse 迭代 | ≤15,000 | plans/SuGaR考核总计划.txt | 阶段1 |
| 运行次数 | 4 次提取 | 汇总对照表.json | 4 rows (基线+3改动) |
| Chamfer(B) 基线 | 0.0531 | 汇总对照表.json | rows[0].Chamfer_B = 0.053072 |
| Chamfer(B) τ=0.02 | 0.0390 | 汇总对照表.json | rows[2].Chamfer_B = 0.038975 |
| 连通分量 基线 | 4,851 | 汇总对照表.json | rows[0].连通分量数 = 4851 |
| 连通分量 τ=0.02 | 2,690 | 汇总对照表.json | rows[2].连通分量数 = 2690 |
| 覆盖率 基线 | 92.9% | 汇总对照表.json | rows[0].网格覆盖率 = 0.928911 |
| 覆盖率 τ=0.02 | 71.0% | 汇总对照表.json | rows[2].网格覆盖率 = 0.710219 |
| PSNR | 24.32 dB | sec3 原有渲染表 | Coarse SuGaR 行 |
| SSIM | 0.848 | sec3 原有渲染表 | Coarse SuGaR 行 |

### 几何指标表 (sec3, tab:geo-refA)

| 报告数字 | 值 | 来源 JSON | 字段路径 |
|---|---|---|---|
| Chamfer_A 基线 | 0.0326 | 汇总对照表.json rows[0] | Chamfer_A=0.032554 |
| Chamfer_A τ=0.05 | 0.0287 | 汇总对照表.json rows[3] | Chamfer_A=0.028663 |
| Chamfer_A τ=0.02 | 0.0242 | 汇总对照表.json rows[2] | Chamfer_A=0.024184 |
| Chamfer_A τ=0.01 | 0.0230 | 汇总对照表.json rows[1] | Chamfer_A=0.023020 |
| Acc均值_A 基线 | 0.0156 | 几何指标_基线.json | 参考A.accuracy_ref_to_mesh.mean=0.015605 |
| Acc均值_A τ=0.05 | 0.0184 | 几何指标_改动_τ0.05.json | 参考A.accuracy_ref_to_mesh.mean=0.018445 |
| Acc均值_A τ=0.02 | 0.0198 | 几何指标_改动_τ0.02.json | 参考A.accuracy_ref_to_mesh.mean=0.019812 |
| Acc均值_A τ=0.01 | 0.0220 | 几何指标_改动_τ0.01.json | 参考A.accuracy_ref_to_mesh.mean=0.021951 |
| AccP90_A 基线 | 0.0291 | 几何指标_基线.json | 参考A.accuracy_ref_to_mesh.p90=0.029122 |
| AccP90_A τ=0.05 | 0.0327 | 几何指标_改动_τ0.05.json | 参考A.accuracy_ref_to_mesh.p90=0.032665 |
| AccP90_A τ=0.02 | 0.0343 | 几何指标_改动_τ0.02.json | 参考A.accuracy_ref_to_mesh.p90=0.034305 |
| AccP90_A τ=0.01 | 0.0366 | 几何指标_改动_τ0.01.json | 参考A.accuracy_ref_to_mesh.p90=0.036602 |
| Comp均值_A 基线 | 0.0495 | 几何指标_基线.json | 参考A.completeness_mesh_to_ref.mean=0.049502 |
| Comp均值_A τ=0.05 | 0.0389 | 几何指标_改动_τ0.05.json | 参考A.completeness_mesh_to_ref.mean=0.038882 |
| Comp均值_A τ=0.02 | 0.0286 | 几何指标_改动_τ0.02.json | 参考A.completeness_mesh_to_ref.mean=0.028556 |
| Comp均值_A τ=0.01 | 0.0241 | 几何指标_改动_τ0.01.json | 参考A.completeness_mesh_to_ref.mean=0.024089 |
| CompP90_A 基线 | 0.1317 | 几何指标_基线.json | 参考A.completeness_mesh_to_ref.p90=0.131664 |
| CompP90_A τ=0.05 | 0.0995 | 几何指标_改动_τ0.05.json | 参考A.completeness_mesh_to_ref.p90=0.099542 |
| CompP90_A τ=0.02 | 0.0593 | 几何指标_改动_τ0.02.json | 参考A.completeness_mesh_to_ref.p90=0.059270 |
| CompP90_A τ=0.01 | 0.0490 | 几何指标_改动_τ0.01.json | 参考A.completeness_mesh_to_ref.p90=0.048968 |
| F@0.5%_A 基线 | 0.864 | 几何指标_基线.json | 参考A.fscore.tau_0.005.fscore=0.863886 |
| F@1%_A 基线 | 0.946 | 几何指标_基线.json | 参考A.fscore.tau_0.01.fscore=0.946422 |
| F@2%_A 基线 | 0.990 | 几何指标_基线.json | 参考A.fscore.tau_0.02.fscore=0.990296 |

（参考 B 表同理，数字均取自对应 JSON 文件的 参考B_COLMAP稀疏点 分支，此处略去逐行列举。）

### 拓扑/覆盖/效率表 (sec3, tab:topo-cov-eff)

| 报告数字 | 来源 |
|---|---|
| V/F/连通分量/边界边/孔洞 (基线) | sec3 原有值，与 汇总对照表.json rows[0] 一致 |
| V 665,745 / F 1,295,321 / 连通3,279 (τ=0.05) | 汇总对照表.json rows[3] |
| V 574,239 / F 1,121,525 / 连通2,690 (τ=0.02) | 汇总对照表.json rows[2] |
| V 455,839 / F 890,054 / 连通2,261 (τ=0.01) | 汇总对照表.json rows[1] |
| 覆盖率 81.5%/71.0%/63.3% | 汇总对照表.json 网格覆盖率列 |
| 漏洞率 18.0%/28.6%/36.3% | 汇总对照表.json 漏洞率(前景)列 |
| 提取墙钟 4.79/4.30/3.91 min | 计时_提取mesh_τ*.txt: 287.621/258.296/234.865 秒 ÷60 |
| 总墙钟 22.62/22.13/21.74 min | 基线共享时间(23.81-5.98=17.83) + 提取时间 |
| 峰值显存 8,274 MiB | 汇总对照表.json 峰值显存MiB=8274 |
| 网格体积 48.56/41.94/33.29 MiB | 汇总对照表.json 网格体积MiB列 |

### 超参敏感性与分析节 (sec3)

| 报告数字 | 来源 |
|---|---|
| 剔除率 72.2%(τ=0.005)~9.0%(τ=0.2) | 剔除率曲线.txt |
| 剔除率 25.5%/44.9%/59.2% | 汇总对照表.json 剔除率列 |
| 过滤器耗时 ~0.5s (渲染0.3s+投票0.2s) | 剔除率曲线.txt (渲染30深度图0.3s, 单τ投票0.2s) |
| Chamfer(B) 降幅27% | (0.0531-0.0390)/0.0531=0.2656≈27% |
| 连通分量降幅45% | (4851-2690)/4851=0.4453≈45% |
| 孔洞降幅31% | (7970-5480)/7970=0.3124≈31% |
| Completeness(A)降幅42% | (0.0495-0.0286)/0.0495=0.4222≈42% |
| AccP90(B) 变差29% | (0.0258-0.0200)/0.0200=0.29=29% |
| 提取快28% | (5.98-4.30)/5.98=0.2809≈28% |

### 结论节 (sec4)

| 报告数字 | 来源 |
|---|---|
| Chamfer 0.0531→0.0390 | 同上 |
| 连通分量 4,851→2,690 | 同上 |
| 提取缩短28% | 同上 |
| 覆盖率 92.9%→71.0% | 同上 |

## 二、编译结果

- 编译工具: tectonic (XeTeX)
- 编译命令: `cd report && bash build.sh`
- 编译状态: **成功**，生成 report.pdf (4.47 MiB)
- 警告:
  - algorithm2e.sty UTF-8 字节警告 (预先存在，非本次改动引起)
  - sec1_method 第129行 overfull hbox 0.79pt (预先存在)
  - bibtex 内部一致性警告导致多次重跑 (预先存在的 bibtex 配置问题)
- 错误: **无**
- undefined reference (??): **无** (PyPDF2 逐页扫描确认全 11 页无 "??")

## 三、页数

- **总页数: 11**

## 四、写入的文件清单

| 文件 | 操作 | 说明 |
|---|---|---|
| report/sections/abstract.tex | 重写 | 替换所有 \placeholder 为真实数字 |
| report/sections/sec3_results.tex | 重写 | 填入3τ列、新增超参/分析小节 |
| report/sections/sec4_conclusion.tex | 重写 | 结论+局限+下一步 (15行内) |
| report/figures/剔除率_随τ变化.png | 复制 | 从 outputs/改动_truck/τ曲线/ |
| report/figures/误差热图_统一色标_基线.png | 复制 | 从 outputs/改动_truck/评测/图_统一色标/ |
| report/figures/误差热图_统一色标_改动_τ0.02.png | 复制 | 从 outputs/改动_truck/评测/图_统一色标/ |
| notes/SELF_CHECK_报告改动结果.md | 新建 | 本文件 |

## 五、用户规则合规

- [x] 全中文，术语首次出现附英文
- [x] 失败案例只写方法/超参层面（τ过小→覆盖率下降/漏洞率上升/P90变差；τ过大→漏剔漂浮物），未涉及代码/工程现象
- [x] 未加回用户手动删减的 sec1_method.tex 内容
- [x] 所有数字仅来自指定数据文件（汇总对照表.json/txt、几何指标*.json、剔除率曲线.txt、计时*.txt）
- [x] 未删除任何文件
- [x] 未修改代码文件
- [x] 未执行实验
- [x] 未 git commit
