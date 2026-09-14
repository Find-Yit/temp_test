#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
τ 扫描 汇总对照表（正式化自 scratchpad/consolidate_2c.py）。

读取「基线」与若干「改动_τX」变体的评测 JSON（几何 M2 / 拓扑 M3 / 覆盖 M4 / 效率 M5）+
剔点统计（剔除率 / 剔点后点数）+ 提取计时（墙钟 / 峰值显存），生成一张横向对照表，
落盘为 汇总对照表.{json,csv,txt}（列与口径与阶段2c 已交付表一致；V/F/连通分量为 open3d 口径）。

约定路径：
  基线 eval json:   <base_eval_dir>/{几何,拓扑,覆盖,效率}指标_<base_tag>.json
  基线 提取计时:    <base_extract_timing> (json, 计时运行.sh 产物)
  改动 eval json:   <mod_eval_dir>/{几何,拓扑,覆盖,效率}指标_<tag>.json
  改动 剔点统计:    <mod_root>/<tag>/剔点统计.json
  改动 提取计时:    <mod_root>/<tag>/计时_提取mesh*.json (glob，唯一一个)

用法示例:
  python scripts/eval/汇总对照表.py \
     --base_eval_dir outputs/基线_truck/评测 --base_tag 基线 \
     --base_extract_timing outputs/基线_truck/计时/计时_提取mesh.json \
     --mod_eval_dir outputs/改动_truck/评测 --mod_root outputs/改动_truck \
     --mod_tags 改动_τ0.01,改动_τ0.02,改动_τ0.05 \
     --out_dir outputs/改动_truck/评测
"""
import os
import sys
import csv
import json
import glob
import argparse

COLUMNS = ["设置", "剔除率", "剔点后点数", "V", "F", "连通分量数", "最大分量占比",
           "边界边数", "孔洞数", "非流形边", "水密",
           "Chamfer_A", "Chamfer_B", "完整度均值_A", "精度均值_A", "完整度均值_B", "精度均值_B",
           "F@0.005_A", "F@0.01_A", "F@0.02_A", "F@0.005_B", "F@0.01_B", "F@0.02_B",
           "网格覆盖率", "漏洞率(前景)", "提取墙钟秒", "峰值显存MiB", "网格体积MiB"]


def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _ref(m2, which):
    """m2['references'] 里挑 参考A / 参考B。"""
    for name, rd in m2.get("references", {}).items():
        if which == "A" and "参考A" in name:
            return rd
        if which == "B" and "参考B" in name:
            return rd
    return {}


def _fs(rd, tau):
    return rd.get("fscore", {}).get(f"tau_{tau}", {}).get("fscore")


def build_row(setting, m2, m3, m4, m5, 剔除率, 剔点后点数, 提取墙钟秒, 峰值显存, 网格体积):
    t = m3["topology"]
    ra, rb = _ref(m2, "A"), _ref(m2, "B")
    return {
        "设置": setting,
        "剔除率": 剔除率,
        "剔点后点数": 剔点后点数,
        "V": t["V"], "F": t["F"], "连通分量数": t["n_components"],
        "最大分量占比": t["max_component_ratio"], "边界边数": t["boundary_edges"],
        "孔洞数": t["holes_boundary_loops"], "非流形边": t["non_manifold_edges"],
        "水密": t["is_watertight"],
        "Chamfer_A": ra.get("chamfer_l1"), "Chamfer_B": rb.get("chamfer_l1"),
        "完整度均值_A": ra.get("completeness_mesh_to_ref", {}).get("mean"),
        "精度均值_A": ra.get("accuracy_ref_to_mesh", {}).get("mean"),
        "完整度均值_B": rb.get("completeness_mesh_to_ref", {}).get("mean"),
        "精度均值_B": rb.get("accuracy_ref_to_mesh", {}).get("mean"),
        "F@0.005_A": _fs(ra, "0.005"), "F@0.01_A": _fs(ra, "0.01"), "F@0.02_A": _fs(ra, "0.02"),
        "F@0.005_B": _fs(rb, "0.005"), "F@0.01_B": _fs(rb, "0.01"), "F@0.02_B": _fs(rb, "0.02"),
        "网格覆盖率": m4["averaged"]["mesh_coverage"],
        "漏洞率(前景)": m4["averaged"]["hole_rate_over_fg"],
        "提取墙钟秒": 提取墙钟秒,
        "峰值显存MiB": 峰值显存,
        "网格体积MiB": 网格体积,
    }


def variant_row(eval_dir, tag, setting, 剔除率, 剔点后点数, extract_timing_json, 效率_from_eval=True):
    m2 = _load(os.path.join(eval_dir, f"几何指标_{tag}.json"))
    m3 = _load(os.path.join(eval_dir, f"拓扑指标_{tag}.json"))
    m4 = _load(os.path.join(eval_dir, f"覆盖指标_{tag}.json"))
    m5 = _load(os.path.join(eval_dir, f"效率指标_{tag}.json"))
    网格体积 = (m5.get("mesh") or {}).get("file_MiB")
    # 提取墙钟 / 峰值显存 优先取「提取阶段」计时 json（基线 效率 total 含 3dgs+coarse，不能用）
    提取墙钟秒, 峰值显存 = None, None
    if extract_timing_json and os.path.isfile(extract_timing_json):
        tj = _load(extract_timing_json)
        提取墙钟秒 = tj.get("wall_seconds")
        峰值显存 = tj.get("peak_mem_process_group_MiB")
    else:
        提取墙钟秒 = m5.get("total_wall_seconds")
        峰值显存 = m5.get("peak_mem_process_group_MiB")
    return build_row(setting, m2, m3, m4, m5, 剔除率, 剔点后点数, 提取墙钟秒, 峰值显存, 网格体积)


def main():
    ap = argparse.ArgumentParser(description="τ 扫描 汇总对照表")
    ap.add_argument("--base_eval_dir", required=True)
    ap.add_argument("--base_tag", default="基线")
    ap.add_argument("--base_extract_timing", default=None, help="基线提取阶段计时 json")
    ap.add_argument("--mod_eval_dir", required=True)
    ap.add_argument("--mod_root", required=True, help="含 <tag>/ 子目录(剔点统计.json + 计时_提取mesh*.json)")
    ap.add_argument("--mod_tags", required=True, help="逗号分隔, 如 改动_τ0.01,改动_τ0.02,改动_τ0.05")
    ap.add_argument("--out_dir", required=True)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    rows = []

    # 基线行
    rows.append(variant_row(args.base_eval_dir, args.base_tag, "基线",
                            "-（未剔点）", "", args.base_extract_timing))

    # 改动行
    for tag in [t.strip() for t in args.mod_tags.split(",") if t.strip()]:
        setting_dir = os.path.join(args.mod_root, tag)
        stat_path = os.path.join(setting_dir, "剔点统计.json")
        剔除率, 剔点后点数 = None, None
        if os.path.isfile(stat_path):
            st = _load(stat_path)
            st0 = st[0] if isinstance(st, list) else st
            剔除率 = st0.get("剔除率")
            剔点后点数 = st0.get("剔点后点数")
        timing_glob = sorted(glob.glob(os.path.join(setting_dir, "计时_提取mesh*.json")))
        extract_timing = timing_glob[0] if timing_glob else None
        rows.append(variant_row(args.mod_eval_dir, tag, tag, 剔除率, 剔点后点数, extract_timing))

    # ---- json ----
    out = {"stage": "阶段2c 汇总对照表", "columns": COLUMNS, "rows": rows}
    with open(os.path.join(args.out_dir, "汇总对照表.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # ---- csv (浮点统一保留 6 位小数, 与已交付表口径一致) ----
    def _csv(v):
        return f"{v:.6f}" if isinstance(v, float) else ("" if v is None else v)
    with open(os.path.join(args.out_dir, "汇总对照表.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for r in rows:
            w.writerow([_csv(r.get(c, "")) for c in COLUMNS])

    # ---- txt (中文, 分块) ----
    lines = ["=" * 78, "阶段2c τ 扫描 汇总对照表 (M2–M6; M1 与基线相同因 coarse 未变)", "=" * 78,
             "V/F/连通分量为 open3d 读入口径(合并重复顶点); 各行同口径可横向对比。",
             "Chamfer/F-score 参数: n_sample=1e6 seed=0 fg_bbox_factor=1.0 tau_ratios=0.005,0.01,0.02;",
             "  参考A=3DGS高斯中心, 参考B=COLMAP稀疏点。", ""]
    def fmt(v):
        if isinstance(v, float):
            return f"{v:.6f}"
        return str(v)
    for r in rows:
        lines.append(f"◆ {r['设置']}")
        lines.append(f"    剔除率: {r['剔除率']}   剔点后点数: {r['剔点后点数']}   连通分量数: {r['连通分量数']}   边界边数: {r['边界边数']}   孔洞数: {r['孔洞数']}")
        lines.append(f"    V: {r['V']}  F: {r['F']}   最大分量占比: {fmt(r['最大分量占比'])}   非流形边: {r['非流形边']}  水密: {r['水密']}")
        lines.append(f"    Chamfer_A: {fmt(r['Chamfer_A'])}  Chamfer_B: {fmt(r['Chamfer_B'])}")
        lines.append(f"    完整度均值_A: {fmt(r['完整度均值_A'])}  精度均值_A: {fmt(r['精度均值_A'])}  完整度均值_B: {fmt(r['完整度均值_B'])}  精度均值_B: {fmt(r['精度均值_B'])}")
        lines.append(f"    F@0.005_A: {fmt(r['F@0.005_A'])}  F@0.01_A: {fmt(r['F@0.01_A'])}  F@0.02_A: {fmt(r['F@0.02_A'])}")
        lines.append(f"    F@0.005_B: {fmt(r['F@0.005_B'])}  F@0.01_B: {fmt(r['F@0.01_B'])}  F@0.02_B: {fmt(r['F@0.02_B'])}")
        lines.append(f"    网格覆盖率: {fmt(r['网格覆盖率'])}  漏洞率(前景): {fmt(r['漏洞率(前景)'])}  提取墙钟秒: {fmt(r['提取墙钟秒'])}  峰值显存MiB: {r['峰值显存MiB']}  网格体积MiB: {fmt(r['网格体积MiB'])}")
        lines.append("")
    with open(os.path.join(args.out_dir, "汇总对照表.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[汇总对照表] 写出 {len(rows)} 行 -> {args.out_dir}/汇总对照表.{{json,csv,txt}}")


if __name__ == "__main__":
    main()
