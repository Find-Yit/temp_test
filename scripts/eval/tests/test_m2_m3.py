#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M2 (几何) 与 M3 (拓扑) 的合成数据单元自测。

运行: python tests/test_m2_m3.py
成功打印 ALL_PASS 并 exit 0; 任一断言失败 exit 1。
"""
import os
import sys
import tempfile
import numpy as np
import open3d as o3d

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # scripts/eval
sys.path.insert(0, HERE)                     # tests
import eval_common as ec
import m2_geometry as m2
import m3_topology as m3
import synthetic_data as sd

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")


def test_m2():
    tmp = tempfile.mkdtemp(prefix="m2_")
    mesh = sd.make_sphere_mesh(radius=1.0, resolution=20)
    scene_scale = 8.0  # 假定的相机中心对角线
    tau_ratios = [0.005, 0.01, 0.02]

    # 情形1: 参考点就在球面上 -> 双向距离都很小, F-score ~ 1
    ref_on = sd.sample_points_on_sphere(radius=1.0, n=20000, seed=0)
    info, _ = m2.eval_one_reference(mesh, ref_on.copy(), "on_surface", scene_scale,
                                    tau_ratios, n_sample=100000, seed=0, crop_bbox=None)
    cm = info["completeness_mesh_to_ref"]["mean"]
    ac = info["accuracy_ref_to_mesh"]["mean"]
    check("M2 同面参考: completeness mean 很小", cm < 0.02, f"(={cm:.4f})")
    check("M2 同面参考: accuracy mean 很小", ac < 0.02, f"(={ac:.4f})")
    f = info["fscore"]["tau_0.02"]["fscore"]
    check("M2 同面参考: F-score@0.02 ~ 1", f > 0.95, f"(={f:.4f})")

    # 情形2: 参考点在半径 1.1 的球面上 -> 距离 ~ 0.1
    ref_off = sd.sample_points_on_sphere(radius=1.1, n=20000, seed=1)
    info2, _ = m2.eval_one_reference(mesh, ref_off.copy(), "offset", scene_scale,
                                     tau_ratios, n_sample=100000, seed=0, crop_bbox=None)
    ac2 = info2["accuracy_ref_to_mesh"]["mean"]
    check("M2 偏移0.1参考: accuracy mean ≈ 0.1", abs(ac2 - 0.1) < 0.02, f"(={ac2:.4f})")
    ch2 = info2["chamfer_l1"]
    check("M2 偏移0.1参考: chamfer ≈ 0.1", abs(ch2 - 0.1) < 0.02, f"(={ch2:.4f})")

    # 情形3: 裁剪 bbox 只保留 x>0 半球, 面数应减少但仍能算
    amin = np.array([0.0, -2.0, -2.0]); amax = np.array([2.0, 2.0, 2.0])
    info3, _ = m2.eval_one_reference(mesh, ref_on.copy(), "cropped", scene_scale,
                                     tau_ratios, n_sample=50000, seed=0, crop_bbox=(amin, amax))
    check("M2 裁剪半球: bbox 内面数 < 全网格面数",
          0 < info3["n_faces_in_bbox"] < len(mesh.triangles),
          f"({info3['n_faces_in_bbox']}/{len(mesh.triangles)})")

    # 情形4: 确定性 —— 同 seed 两次结果一致
    infoA, _ = m2.eval_one_reference(mesh, ref_off.copy(), "det", scene_scale,
                                     tau_ratios, n_sample=50000, seed=7, crop_bbox=None)
    infoB, _ = m2.eval_one_reference(mesh, ref_off.copy(), "det", scene_scale,
                                     tau_ratios, n_sample=50000, seed=7, crop_bbox=None)
    same = abs(infoA["chamfer_l1"] - infoB["chamfer_l1"]) < 1e-9
    check("M2 固定 seed 可复现", same,
          f"(A={infoA['chamfer_l1']:.6f} B={infoB['chamfer_l1']:.6f})")


def test_m3():
    # 球: 1 分量, 0 边界边, 水密, euler=2
    sphere = sd.make_sphere_mesh(radius=1.0, resolution=20)
    t = m3.compute_topology(sphere)
    check("M3 球: 连通分量=1", t["n_components"] == 1, f"(={t['n_components']})")
    check("M3 球: 边界边=0", t["boundary_edges"] == 0, f"(={t['boundary_edges']})")
    check("M3 球: 水密", t["is_watertight"] is True)
    check("M3 球: 欧拉数=2", t["euler"] == 2, f"(={t['euler']})")
    check("M3 球: 孔洞=0", t["holes_boundary_loops"] == 0, f"(={t['holes_boundary_loops']})")
    check("M3 球: 非流形边=0", t["non_manifold_edges"] == 0, f"(={t['non_manifold_edges']})")
    check("M3 球: 最大分量占比=1", abs(t["max_component_ratio"] - 1.0) < 1e-9,
          f"(={t['max_component_ratio']:.4f})")

    # 带洞球: 边界边>0, 至少1个孔洞, 不水密
    hole = sd.make_sphere_with_hole(radius=1.0, resolution=20)
    th = m3.compute_topology(hole)
    check("M3 带洞球: 边界边>0", th["boundary_edges"] > 0, f"(={th['boundary_edges']})")
    check("M3 带洞球: 孔洞>=1", th["holes_boundary_loops"] >= 1, f"(={th['holes_boundary_loops']})")
    check("M3 带洞球: 不水密", th["is_watertight"] is False)

    # 两个不相连球: 2 分量
    two = sd.make_two_disjoint_spheres(radius=1.0, resolution=12, gap=5.0)
    t2 = m3.compute_topology(two)
    check("M3 两球: 连通分量=2", t2["n_components"] == 2, f"(={t2['n_components']})")
    check("M3 两球: 最大分量占比≈0.5", abs(t2["max_component_ratio"] - 0.5) < 0.05,
          f"(={t2['max_component_ratio']:.4f})")

    # 自交检测能在小网格上跑通 (球无自交)
    check("M3 球: 自交对数=0", t["self_intersecting_pairs"] == 0,
          f"(={t['self_intersecting_pairs']})")


def main():
    print("===== M2 几何指标 单元自测 =====")
    test_m2()
    print("\n===== M3 拓扑指标 单元自测 =====")
    test_m3()
    print(f"\n结果: PASS={len(PASS)} FAIL={len(FAIL)}")
    if FAIL:
        print("FAILED:", FAIL)
        sys.exit(1)
    print("ALL_PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
