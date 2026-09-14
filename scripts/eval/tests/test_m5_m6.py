#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M5 (效率) 与 M6 (可视化) 的合成数据单元自测 (CPU only)。

运行: python tests/test_m5_m6.py
"""
import os
import sys
import json
import glob
import tempfile
import subprocess
import numpy as np
import open3d as o3d

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.dirname(HERE)
sys.path.insert(0, EVAL)
sys.path.insert(0, HERE)
import eval_common as ec
import synthetic_data as sd

PY = sys.executable
TIMER = os.path.join(EVAL, "计时运行.sh")
PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")


def _valid_png(path):
    if not os.path.isfile(path) or os.path.getsize(path) < 1000:
        return False
    try:
        import matplotlib.pyplot as plt
        a = plt.imread(path)
        return a.ndim == 3 and a.shape[0] > 10 and a.shape[1] > 10
    except Exception:
        return False


def test_m5(work):
    # 计时运行.sh 包装一个 1s CPU 命令
    tdir = os.path.join(work, "计时")
    r = subprocess.run(["bash", TIMER, "自测阶段", tdir, "--interval", "1", "--",
                        PY, "-c", "import time; time.sleep(1)"],
                       capture_output=True, text=True)
    check("计时运行.sh 退出码0", r.returncode == 0, r.stderr[-200:] if r.returncode else "")
    tj = os.path.join(tdir, "计时_自测阶段.json")
    check("计时 JSON 存在", os.path.isfile(tj))
    if os.path.isfile(tj):
        d = json.load(open(tj))
        check("计时 墙钟>=1s", d["wall_seconds"] >= 1.0, f"(={d['wall_seconds']})")
        check("计时 退出码字段=0", d["return_code"] == 0)

    # 网格 + m5 汇总
    mesh = sd.make_sphere_mesh(1.0, 20)
    mp = os.path.join(work, "球.ply"); o3d.io.write_triangle_mesh(mp, mesh)
    out = os.path.join(work, "out")
    r = subprocess.run([PY, os.path.join(EVAL, "m5_efficiency.py"),
                        "--timing_json", tdir, "--mesh", mp,
                        "--out_dir", out, "--tag", "自测", "--log", os.path.join(work, "log.txt")],
                       capture_output=True, text=True)
    check("M5 CLI 退出码0", r.returncode == 0, r.stderr[-200:] if r.returncode else "")
    j = os.path.join(out, "效率指标_自测.json")
    check("M5 JSON/txt 存在", os.path.isfile(j) and os.path.isfile(os.path.join(out, "效率指标_自测.txt")))
    if os.path.isfile(j):
        d = json.load(open(j))
        check("M5 总墙钟>=1s", d["total_wall_seconds"] >= 1.0, f"(={d['total_wall_seconds']})")
        check("M5 网格面数=1520", d["mesh"]["faces"] == 1520, f"(={d['mesh']['faces']})")
        check("M5 网格体积>0", d["mesh"]["file_MiB"] > 0)


def test_m6(work):
    # 带洞 + 双分量的合成网格 -> 四类图都能出
    mesh = sd.make_two_disjoint_spheres(1.0, 12, 4.0)
    mp = os.path.join(work, "两球.ply"); o3d.io.write_triangle_mesh(mp, mesh)
    ref = sd.sample_points_on_sphere(1.05, 20000, 0)
    p = o3d.geometry.PointCloud(); p.points = o3d.utility.Vector3dVector(ref)
    rp = os.path.join(work, "参考.ply"); o3d.io.write_point_cloud(rp, p)
    # montage 输入图
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    imgs = {}
    for nm, c in [("gt", [0.2, 0.5, 0.8]), ("gs", [0.8, 0.4, 0.2]), ("sugar", [0.3, 0.7, 0.3])]:
        im = np.ones((48, 64, 3)); im[10:40, 10:54] = c
        pth = os.path.join(work, nm + ".png"); plt.imsave(pth, im); imgs[nm] = pth
    out = os.path.join(work, "图")
    r = subprocess.run([PY, os.path.join(EVAL, "m6_visualize.py"), "--mode", "all",
                        "--mesh", mp, "--ref", rp,
                        "--gt_img", imgs["gt"], "--gs_img", imgs["gs"], "--sugar_img", imgs["sugar"],
                        "--out_dir", out, "--tag", "自测", "--log", os.path.join(work, "log.txt")],
                       capture_output=True, text=True)
    check("M6 CLI 退出码0", r.returncode == 0, r.stderr[-200:] if r.returncode else "")
    for fn in ["网格截图_自测.png", "误差热图_自测.png", "连通分量着色_自测.png", "渲染对比_自测.png"]:
        check(f"M6 产物有效: {fn}", _valid_png(os.path.join(out, fn)))


def main():
    work = tempfile.mkdtemp(prefix="test_m5_m6_")
    print("工作目录:", work)
    print("===== M5 效率 =====")
    test_m5(work)
    print("\n===== M6 可视化 =====")
    test_m6(work)
    print(f"\n结果: PASS={len(PASS)} FAIL={len(FAIL)}")
    if FAIL:
        print("FAILED:", FAIL); sys.exit(1)
    print("ALL_PASS"); sys.exit(0)


if __name__ == "__main__":
    main()
