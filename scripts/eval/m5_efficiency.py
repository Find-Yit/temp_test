#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M5 效率指标 — 汇总各阶段墙钟/峰值显存 (来自 计时运行.sh 的 JSON), 以及
网格顶点/面数与文件体积。

用法:
  python m5_efficiency.py \
    --timing_json outputs/基线_truck/计时/计时_训练3DGS_7k.json outputs/.../计时_coarse.json \
    --mesh outputs/基线_truck/mesh/xxx.ply \
    --extra_files outputs/基线_truck/3dgs_7k/point_cloud/iteration_7000/point_cloud.ply \
    --out_dir report/效率 --tag 基线
"""
import os
import sys
import time
import json
import glob
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_common as ec


def _file_size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return None


def _mb(n):
    return None if n is None else round(n / (1024 * 1024), 4)


def mesh_stats(mesh_path):
    """网格顶点/面数 + 文件体积。"""
    import open3d as o3d
    mesh = o3d.io.read_triangle_mesh(mesh_path)
    n_v = len(mesh.vertices)
    n_f = len(mesh.triangles)
    size = _file_size(mesh_path)
    return {
        "path": os.path.abspath(mesh_path),
        "vertices": n_v,
        "faces": n_f,
        "file_bytes": size,
        "file_MiB": _mb(size),
    }


def parse_timing(paths):
    """读取 计时运行.sh 产生的 JSON。支持 glob 与目录。"""
    stages = []
    expanded = []
    for p in paths:
        if os.path.isdir(p):
            expanded += sorted(glob.glob(os.path.join(p, "计时_*.json")))
        elif any(ch in p for ch in "*?["):
            expanded += sorted(glob.glob(p))
        else:
            expanded.append(p)
    for p in expanded:
        try:
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
            d["_source"] = os.path.abspath(p)
            stages.append(d)
        except Exception as e:
            stages.append({"stage": os.path.basename(p), "error": str(e),
                           "_source": os.path.abspath(p)})
    return stages


def main():
    ap = argparse.ArgumentParser(description="M5 效率指标汇总")
    ap.add_argument("--timing_json", nargs="*", default=[],
                    help="计时运行.sh 产生的 JSON (可多个/目录/通配)")
    ap.add_argument("--mesh", default=None, help="网格文件, 报顶点/面数与体积")
    ap.add_argument("--extra_files", nargs="*", default=[], help="额外统计体积的文件")
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--tag", default="基线")
    ap.add_argument("--log", default=ec.DEFAULT_EXEC_LOG)
    args = ap.parse_args()

    t0 = time.time()
    stages = parse_timing(args.timing_json)
    total_wall = sum(s.get("wall_seconds", 0) or 0 for s in stages)
    peak_our = max([s.get("peak_mem_process_group_MiB", 0) or 0 for s in stages], default=0)
    peak_total = max([s.get("peak_mem_whole_gpu_MiB", 0) or 0 for s in stages], default=0)

    m_stats = mesh_stats(args.mesh) if args.mesh else None
    extras = []
    for p in args.extra_files:
        size = _file_size(p)
        extras.append({"path": os.path.abspath(p), "file_bytes": size, "file_MiB": _mb(size)})

    json_obj = {
        "tag": args.tag,
        "stages": stages,
        "total_wall_seconds": total_wall,
        "peak_mem_process_group_MiB": peak_our,
        "peak_mem_whole_gpu_MiB": peak_total,
        "mesh": m_stats,
        "extra_files": extras,
        "elapsed_sec": time.time() - t0,
    }

    txt_sections = []
    stage_kvs = []
    for s in stages:
        if "error" in s:
            stage_kvs.append((s.get("stage", "?"), "解析失败: " + s["error"]))
        else:
            stage_kvs.append((
                s.get("stage", "?"),
                f"墙钟={s.get('wall_seconds')}s 退出码={s.get('return_code')} "
                f"峰值显存(本组)={s.get('peak_mem_process_group_MiB')}MiB "
                f"峰值显存(全卡)={s.get('peak_mem_whole_gpu_MiB')}MiB"))
    txt_sections.append(("各阶段计时/显存", stage_kvs))
    txt_sections.append(("总计", [
        ("总墙钟(秒)", total_wall),
        ("总墙钟(分)", round(total_wall / 60.0, 2)),
        ("峰值显存_本进程组(MiB)", peak_our),
        ("峰值显存_全卡(MiB)", peak_total),
    ]))
    if m_stats:
        txt_sections.append(("网格统计", [
            ("网格文件", os.path.basename(m_stats["path"])),
            ("顶点数", m_stats["vertices"]),
            ("面数", m_stats["faces"]),
            ("文件体积(MiB)", m_stats["file_MiB"]),
        ]))
    if extras:
        txt_sections.append(("其他文件体积", [
            (os.path.basename(e["path"]), f"{e['file_MiB']} MiB") for e in extras]))

    basename = f"效率指标_{args.tag}"
    jp, tp = ec.write_report(args.out_dir, basename, json_obj,
                             f"M5 效率指标 — {args.tag}", txt_sections)
    ec.log_exec(f"M5 效率指标 完成 tag={args.tag} 阶段数={len(stages)} 总墙钟={total_wall:.1f}s -> {jp}",
                args.log)
    print(f"[M5] 写出 {jp}\n[M5] 写出 {tp}")


if __name__ == "__main__":
    main()
