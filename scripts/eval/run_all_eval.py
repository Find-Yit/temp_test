#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_all_eval.py — 汇总执行 M1–M6, 支持 baseline 与多个 modified 变体的横向对比。

两种用法:
  1) 配置文件 (推荐, 做 baseline vs modified 对比):
       python run_all_eval.py --config 评测配置.json
  2) 命令行单变体:
       python run_all_eval.py --tag 基线 \
         --source_path data/tandt/truck --gs_output outputs/基线_truck/3dgs_7k \
         --mesh outputs/基线_truck/mesh/xxx.ply --coarse_pt outputs/基线_truck/coarse/xxx.pt \
         --ref_a outputs/基线_truck/3dgs_7k/point_cloud/iteration_7000/point_cloud.ply \
         --ref_b_colmap data/tandt/truck/sparse/0 \
         --cameras_json outputs/基线_truck/3dgs_7k/cameras.json \
         --out_dir report/评测 --metrics M1,M2,M3,M4,M5,M6

配置文件结构见 tests/示例_评测配置.json。
产物 (out_dir 下):
  各指标脚本自身的 <指标>_<tag>.json/.txt/.csv
  汇总_全部指标.json         机器可读嵌套结果
  汇总_对比表.csv            variant×关键指标 对比
  汇总_对比表.txt            中文对比表
"""
import os
import sys
import json
import time
import argparse
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import eval_common as ec

PY = sys.executable


def _run(cmd, log):
    ec.log_exec("run_all 调用: " + " ".join(str(c) for c in cmd), log)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("  [错误] 子进程失败, 返回码", r.returncode)
        print("  STDERR:", r.stderr[-1500:])
    return r.returncode


def _load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def run_variant(v, shared, metrics, out_dir, opts, log):
    """对一个变体运行所选指标; 返回 {metric: json_dict}。"""
    tag = v["tag"]
    got = {}
    repo = shared.get("repo_root", ec.DEFAULT_REPO_ROOT)

    # M1 渲染
    if "M1" in metrics and shared.get("source_path") and shared.get("gs_output"):
        cmd = [PY, os.path.join(HERE, "m1_render_metrics.py"),
               "--source_path", shared["source_path"], "--gs_output", shared["gs_output"],
               "--iteration", str(shared.get("iteration", 7000)),
               "--out_dir", out_dir, "--tag", tag, "--repo_root", repo,
               "--lpips", str(opts.get("lpips", 1)), "--log", log]
        if v.get("coarse_pt"):
            cmd += ["--coarse_pt", v["coarse_pt"]]
        if opts.get("save_renders"):
            cmd += ["--save_renders"]
        if _run(cmd, log) == 0:
            got["M1"] = _load_json(os.path.join(out_dir, f"渲染指标_{tag}.json"))

    # M2 几何
    if "M2" in metrics and v.get("mesh"):
        cmd = [PY, os.path.join(HERE, "m2_geometry.py"), "--mesh", v["mesh"],
               "--out_dir", out_dir, "--tag", tag, "--repo_root", repo,
               "--n_sample", str(opts.get("n_sample", 1_000_000)),
               "--fg_bbox_factor", str(opts.get("fg_bbox_factor", 1.0)),
               "--tau_ratios", opts.get("tau_ratios", "0.005,0.01,0.02"), "--log", log]
        if shared.get("ref_a"):
            cmd += ["--ref_a", shared["ref_a"]]
        if shared.get("ref_b_colmap"):
            cmd += ["--ref_b_colmap", shared["ref_b_colmap"]]
        if shared.get("cameras_json"):
            cmd += ["--cameras_json", shared["cameras_json"]]
        if _run(cmd, log) == 0:
            got["M2"] = _load_json(os.path.join(out_dir, f"几何指标_{tag}.json"))

    # M3 拓扑
    if "M3" in metrics and v.get("mesh"):
        cmd = [PY, os.path.join(HERE, "m3_topology.py"), "--mesh", v["mesh"],
               "--out_dir", out_dir, "--tag", tag, "--log", log]
        if opts.get("skip_self_intersect"):
            cmd += ["--skip_self_intersect"]
        if opts.get("self_intersect_timeout"):
            cmd += ["--self_intersect_timeout", str(opts["self_intersect_timeout"])]
        if _run(cmd, log) == 0:
            got["M3"] = _load_json(os.path.join(out_dir, f"拓扑指标_{tag}.json"))

    # M4 覆盖
    if "M4" in metrics and v.get("mesh") and shared.get("source_path") and shared.get("gs_output"):
        cmd = [PY, os.path.join(HERE, "m4_coverage.py"),
               "--source_path", shared["source_path"], "--gs_output", shared["gs_output"],
               "--iteration", str(shared.get("iteration", 7000)),
               "--mesh", v["mesh"], "--out_dir", out_dir, "--tag", tag,
               "--repo_root", repo, "--log", log]
        if opts.get("max_views"):
            cmd += ["--max_views", str(opts["max_views"])]
        if opts.get("save_masks"):
            cmd += ["--save_masks"]
        if _run(cmd, log) == 0:
            got["M4"] = _load_json(os.path.join(out_dir, f"覆盖指标_{tag}.json"))

    # M5 效率
    if "M5" in metrics:
        cmd = [PY, os.path.join(HERE, "m5_efficiency.py"),
               "--out_dir", out_dir, "--tag", tag, "--log", log]
        if v.get("mesh"):
            cmd += ["--mesh", v["mesh"]]
        if v.get("timing_json"):
            cmd += ["--timing_json"] + (v["timing_json"] if isinstance(v["timing_json"], list) else [v["timing_json"]])
        if v.get("extra_files"):
            cmd += ["--extra_files"] + v["extra_files"]
        if _run(cmd, log) == 0:
            got["M5"] = _load_json(os.path.join(out_dir, f"效率指标_{tag}.json"))

    # M6 可视化
    if "M6" in metrics and v.get("mesh"):
        cmd = [PY, os.path.join(HERE, "m6_visualize.py"), "--mode", "all",
               "--mesh", v["mesh"], "--out_dir", os.path.join(out_dir, "图"),
               "--tag", tag, "--repo_root", repo, "--log", log]
        if shared.get("ref_b_colmap"):
            cmd += ["--ref", shared["ref_b_colmap"]]
        elif shared.get("ref_a"):
            cmd += ["--ref", shared["ref_a"]]
        _run(cmd, log)
        got["M6"] = {"figures_dir": os.path.join(out_dir, "图")}

    return got


def flatten_for_table(tag, got):
    """把一个变体的结果压平成 {列名: 值}。"""
    row = {"变体": tag}
    m1 = got.get("M1")
    if m1:
        row["3DGS_PSNR"] = m1["vanilla_3dgs"]["psnr"]
        row["3DGS_SSIM"] = m1["vanilla_3dgs"]["ssim"]
        row["3DGS_LPIPS"] = m1["vanilla_3dgs"]["lpips"]
        if "coarse_sugar" in m1:
            row["coarse_PSNR"] = m1["coarse_sugar"]["psnr"]
            row["coarse_SSIM"] = m1["coarse_sugar"]["ssim"]
            row["coarse_LPIPS"] = m1["coarse_sugar"]["lpips"]
    m2 = got.get("M2")
    if m2:
        for rn, rd in m2.get("references", {}).items():
            if "chamfer_l1" in rd:
                short = "A" if "参考A" in rn else ("B" if "参考B" in rn else rn)
                row[f"Chamfer_{short}"] = rd["chamfer_l1"]
                row[f"完整度均值_{short}"] = rd["completeness_mesh_to_ref"]["mean"]
                row[f"精度均值_{short}"] = rd["accuracy_ref_to_mesh"]["mean"]
                f01 = rd.get("fscore", {}).get("tau_0.01", {})
                if f01:
                    row[f"F@0.01_{short}"] = f01["fscore"]
    m3 = got.get("M3")
    if m3:
        t = m3["topology"]
        row["V"] = t["V"]; row["F"] = t["F"]
        row["连通分量数"] = t["n_components"]
        row["最大分量占比"] = t["max_component_ratio"]
        row["边界边数"] = t["boundary_edges"]
        row["孔洞数"] = t["holes_boundary_loops"]
        row["非流形边"] = t["non_manifold_edges"]
        row["水密"] = t["is_watertight"]
        row["自交对数"] = t.get("self_intersecting_pairs")
    m4 = got.get("M4")
    if m4:
        row["网格覆盖率"] = m4["averaged"]["mesh_coverage"]
        row["漏洞率(前景)"] = m4["averaged"]["hole_rate_over_fg"]
    m5 = got.get("M5")
    if m5:
        row["总墙钟秒"] = m5.get("total_wall_seconds")
        row["峰值显存MiB"] = m5.get("peak_mem_process_group_MiB")
        if m5.get("mesh"):
            row["网格体积MiB"] = m5["mesh"].get("file_MiB")
    return row


def main():
    ap = argparse.ArgumentParser(description="汇总运行 M1–M6 并做变体对比")
    ap.add_argument("--config", default=None, help="JSON 配置 (多变体对比)")
    # 单变体 CLI
    ap.add_argument("--tag", default="基线")
    ap.add_argument("--source_path", default=None)
    ap.add_argument("--gs_output", default=None)
    ap.add_argument("--iteration", type=int, default=7000)
    ap.add_argument("--mesh", default=None)
    ap.add_argument("--coarse_pt", default=None)
    ap.add_argument("--ref_a", default=None)
    ap.add_argument("--ref_b_colmap", default=None)
    ap.add_argument("--cameras_json", default=None)
    ap.add_argument("--timing_json", nargs="*", default=None)
    ap.add_argument("--out_dir", default=None)
    ap.add_argument("--metrics", default="M1,M2,M3,M4,M5,M6")
    ap.add_argument("--repo_root", default=ec.DEFAULT_REPO_ROOT)
    ap.add_argument("--n_sample", type=int, default=1_000_000)
    ap.add_argument("--lpips", type=int, default=1)
    ap.add_argument("--save_renders", action="store_true")
    ap.add_argument("--save_masks", action="store_true")
    ap.add_argument("--max_views", type=int, default=0)
    ap.add_argument("--skip_self_intersect", action="store_true")
    ap.add_argument("--self_intersect_timeout", type=int, default=120)
    ap.add_argument("--log", default=ec.DEFAULT_EXEC_LOG)
    args = ap.parse_args()

    t0 = time.time()
    if args.config:
        cfg = _load_json(args.config)
        shared = cfg["shared"]
        variants = cfg["variants"]
        metrics = cfg.get("metrics", ["M1", "M2", "M3", "M4", "M5", "M6"])
        opts = cfg.get("options", {})
        out_dir = shared["out_dir"]
    else:
        if not args.out_dir:
            ap.error("单变体模式需要 --out_dir")
        shared = {"source_path": args.source_path, "gs_output": args.gs_output,
                  "iteration": args.iteration, "ref_a": args.ref_a,
                  "ref_b_colmap": args.ref_b_colmap, "cameras_json": args.cameras_json,
                  "out_dir": args.out_dir, "repo_root": args.repo_root}
        variants = [{"tag": args.tag, "mesh": args.mesh, "coarse_pt": args.coarse_pt,
                     "timing_json": args.timing_json}]
        metrics = [m.strip() for m in args.metrics.split(",") if m.strip()]
        opts = {"n_sample": args.n_sample, "lpips": args.lpips,
                "save_renders": args.save_renders, "save_masks": args.save_masks,
                "max_views": args.max_views, "skip_self_intersect": args.skip_self_intersect,
                "self_intersect_timeout": args.self_intersect_timeout}
        out_dir = args.out_dir

    os.makedirs(out_dir, exist_ok=True)
    log = shared.get("log", args.log) if args.config else args.log
    ec.log_exec(f"run_all 开始 变体数={len(variants)} 指标={metrics}", log)

    all_results = {}
    rows = []
    for v in variants:
        print(f"\n===== 变体: {v['tag']} =====")
        got = run_variant(v, shared, metrics, out_dir, opts, log)
        all_results[v["tag"]] = got
        rows.append(flatten_for_table(v["tag"], got))

    # 汇总 JSON
    summary = {"variants": list(all_results.keys()), "metrics": metrics,
               "shared": shared, "results": all_results,
               "elapsed_sec": time.time() - t0}
    with open(os.path.join(out_dir, "汇总_全部指标.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=ec._json_default)

    # 对比表 CSV (所有出现过的列)
    cols = ["变体"]
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    csv_rows = [[r.get(c, "") for c in cols] for r in rows]
    ec.write_csv(os.path.join(out_dir, "汇总_对比表.csv"), cols, csv_rows)

    # 对比表 txt (中文)
    txt_sections = []
    for r in rows:
        kvs = [(k, r[k]) for k in cols if k in r and k != "变体"]
        txt_sections.append((f"变体 {r['变体']}", kvs))
    ec.write_report(out_dir, "汇总_对比表", summary, "M1–M6 汇总对比", txt_sections)

    ec.log_exec(f"run_all 完成 变体数={len(variants)} 耗时={time.time()-t0:.1f}s -> {out_dir}", log)
    print(f"\n[run_all] 写出 {os.path.join(out_dir, '汇总_全部指标.json')}")
    print(f"[run_all] 写出 {os.path.join(out_dir, '汇总_对比表.csv')}")
    print(f"[run_all] 写出 {os.path.join(out_dir, '汇总_对比表.txt')}")


if __name__ == "__main__":
    main()
