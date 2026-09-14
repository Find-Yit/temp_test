#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M1 (渲染) 与 M4 (覆盖) 的合成数据 GPU 单元自测。

构造最小合成 3DGS 场景 (GT 图由高斯自身渲染, 故 3DGS 渲染≈GT), 通过 CLI 调用
m1/m4 脚本, 断言指标落在合理范围并有产物落盘。需要 GPU (<1GB 显存)。

运行: python tests/test_m1_m4.py
"""
import os
import sys
import json
import glob
import tempfile
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.dirname(HERE)
sys.path.insert(0, EVAL)
sys.path.insert(0, HERE)
import eval_common as ec
import make_synthetic_gs as mgs

PY = sys.executable
PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")


def main():
    work = tempfile.mkdtemp(prefix="test_m1_m4_")
    print("工作目录:", work)
    info = mgs.build(os.path.join(work, "syn"), n_cams=12, n_gauss=2500, render_gt=True)
    coarse_pt = mgs.build_coarse_pt(info, os.path.join(work, "syn", "coarse", "合成coarse.pt"))
    out = os.path.join(work, "out")

    # ---- M1 ----
    cmd = [PY, os.path.join(EVAL, "m1_render_metrics.py"),
           "--source_path", info["source_path"], "--gs_output", info["gs_output"],
           "--iteration", str(info["iteration"]), "--coarse_pt", coarse_pt,
           "--out_dir", out, "--tag", "自测", "--lpips", "1", "--log", os.path.join(work, "log.txt")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    check("M1 CLI 退出码0", r.returncode == 0, r.stderr[-300:] if r.returncode else "")
    j = os.path.join(out, "渲染指标_自测.json")
    check("M1 JSON 存在", os.path.isfile(j))
    check("M1 txt 存在", os.path.isfile(os.path.join(out, "渲染指标_自测.txt")))
    check("M1 逐视角CSV 存在", os.path.isfile(os.path.join(out, "渲染指标_逐视角_自测.csv")))
    if os.path.isfile(j):
        d = json.load(open(j))
        # GT==高斯渲染 -> 3DGS 与 coarse 的 PSNR 应很高
        check("M1 3DGS PSNR>40", d["vanilla_3dgs"]["psnr"] > 40, f"(={d['vanilla_3dgs']['psnr']:.2f})")
        check("M1 3DGS SSIM>0.99", d["vanilla_3dgs"]["ssim"] > 0.99, f"(={d['vanilla_3dgs']['ssim']:.4f})")
        check("M1 3DGS LPIPS<0.01", d["vanilla_3dgs"]["lpips"] < 0.01, f"(={d['vanilla_3dgs']['lpips']:.2e})")
        check("M1 coarse PSNR>40", d["coarse_sugar"]["psnr"] > 40, f"(={d['coarse_sugar']['psnr']:.2f})")
        check("M1 测试视角数=2 (12//8)", d["n_test_views"] == 2, f"(={d['n_test_views']})")

    # ---- M4 ----
    cmd = [PY, os.path.join(EVAL, "m4_coverage.py"),
           "--source_path", info["source_path"], "--gs_output", info["gs_output"],
           "--iteration", str(info["iteration"]), "--mesh", info["mesh"],
           "--out_dir", out, "--tag", "自测", "--save_masks", "--log", os.path.join(work, "log.txt")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    check("M4 CLI 退出码0", r.returncode == 0, r.stderr[-300:] if r.returncode else "")
    j4 = os.path.join(out, "覆盖指标_自测.json")
    check("M4 JSON 存在", os.path.isfile(j4))
    check("M4 逐视角CSV 存在", os.path.isfile(os.path.join(out, "覆盖指标_逐视角_自测.csv")))
    if os.path.isfile(j4):
        d = json.load(open(j4))
        a = d["averaged"]
        check("M4 覆盖率∈(0,1)", 0 < a["mesh_coverage"] < 1, f"(={a['mesh_coverage']:.4f})")
        check("M4 前景占比>0", a["fg_fraction"] > 0, f"(={a['fg_fraction']:.4f})")
        check("M4 漏洞率(前景)∈[0,1]", 0 <= a["hole_rate_over_fg"] <= 1, f"(={a['hole_rate_over_fg']:.4f})")
        check("M4 网格覆盖前景比例∈[0,1]", 0 <= a["mesh_covers_fg"] <= 1, f"(={a['mesh_covers_fg']:.4f})")
        check("M4 掩码图已保存", len(glob.glob(os.path.join(out, "覆盖掩码_自测", "*.png"))) > 0)

    print(f"\n结果: PASS={len(PASS)} FAIL={len(FAIL)}")
    if FAIL:
        print("FAILED:", FAIL); sys.exit(1)
    print("ALL_PASS"); sys.exit(0)


if __name__ == "__main__":
    main()
