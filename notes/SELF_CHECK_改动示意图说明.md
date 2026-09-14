# SELF_CHECK：改动示意图说明.md

- **状态**：完成
- **产物**：`/scratch/e1351071/zju_test_test/report/改动示意图说明.md`
- **数据行**：所有参数默认值取自 `plans/改动方案_多视角深度一致性剔点.txt`（tau 扫描 {0.01,0.02,0.05}、k=2、v=1、M=30、seed=0）和 `notes/SURVEY.md` 第二节（surface_level=0.3、poisson_depth=10、vertices_density_quantile=0.1、fg_bbox_factor=1.0、bg_bbox_factor=4.0）。
- **先例数值**：COLMAP max_depth_error=0.01（先例核实.md §一.B）、ACMM num_consistent>=2（同上）、GaussianPro thre2=0.01（同上）。
- **公式**：一致票 |z_p-z_map|<tau*z_map、空域冲突票 z_p<z_map-tau*z_map（取自 plans/阶段2a_改动实现.txt 判据段落）。
- **代码文件引用**：sugar_extractors/coarse_mesh.py（流程位置）、mv_consistency_filter.py（尚未创建，引用自计划）。
- **未覆盖现有文件，未删除文件，未改动代码，未跑实验**。
