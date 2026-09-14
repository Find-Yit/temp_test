#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M3 拓扑/网格质量指标 (无参考)。

指标:
  顶点数 V / 面数 F / 唯一边数 E / 欧拉数 (V-E+F)
  连通分量数、最大分量面数占比 (及前几大分量)
  非流形边数 (被 >2 个面共享)
  边界边数 (恰好 1 个面; 用 allow_boundary_edges True/False 差集)
  非流形顶点数
  孔洞数 (边界边并查集数环)
  自交三角形数 (相交对数 + 涉及的唯一三角形数)
  水密性 is_watertight
  退化三角形数 (面积近 0)
若安装了 trimesh, 额外做交叉验证 (欧拉数 / 边界环数)。

用法:
  python m3_topology.py --mesh path/to/mesh.ply --out_dir report/拓扑 --tag 基线
"""
import os
import sys
import time
import argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_common as ec


class _UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def _edge_set(v2i_vector):
    """把 o3d Vector2iVector 转成 frozenset-of-sorted-tuple 集合。"""
    arr = np.asarray(v2i_vector)
    if arr.size == 0:
        return set()
    s = set()
    for e in arr:
        a, b = int(e[0]), int(e[1])
        s.add((a, b) if a < b else (b, a))
    return s


def _unique_edges_count(triangles):
    """三角形数组 -> 唯一无向边数。"""
    tri = np.asarray(triangles)
    if tri.size == 0:
        return 0
    e = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]], axis=0)
    e = np.sort(e, axis=1)
    uniq = np.unique(e, axis=0)
    return int(uniq.shape[0])


def _count_boundary_loops(boundary_edges):
    """给定边界边集合 (sorted tuple), 用并查集数连通分量 = 边界环数 = 孔洞数。"""
    if not boundary_edges:
        return 0
    uf = _UnionFind()
    verts = set()
    for a, b in boundary_edges:
        uf.union(a, b)
        verts.add(a)
        verts.add(b)
    roots = {uf.find(v) for v in verts}
    return len(roots)


def _degenerate_triangles(mesh, eps=1e-14):
    """面积近 0 的退化三角形数。"""
    v = np.asarray(mesh.vertices)
    t = np.asarray(mesh.triangles)
    if t.size == 0:
        return 0
    p0, p1, p2 = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(p1 - p0, p2 - p0), axis=1)
    return int((area <= eps).sum())


def _self_intersect_worker(mesh_path):
    """子进程入口: 计算自交三角形, 打印 'pairs tris'。"""
    import open3d as o3d
    m = o3d.io.read_triangle_mesh(mesh_path)
    m.remove_unreferenced_vertices()
    pairs = np.asarray(m.get_self_intersecting_triangles())
    n_pairs = int(pairs.shape[0]) if pairs.size else 0
    n_tris = int(np.unique(pairs).shape[0]) if pairs.size else 0
    print(f"SELF_INTERSECT {n_pairs} {n_tris}")


def self_intersect_timed(mesh_path, timeout_sec):
    """在带超时的子进程中计算自交, 超时则返回 None。
    (open3d 的 get_self_intersecting_triangles 在大网格上极慢, 故隔离+限时)"""
    import subprocess
    cmd = [sys.executable, os.path.abspath(__file__), "--_self_intersect_worker", mesh_path]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        return {"skipped": True, "reason": f"自交计算超过 {timeout_sec}s 超时", "sec": time.time() - t0}
    if r.returncode != 0:
        return {"skipped": True, "reason": f"自交子进程失败 rc={r.returncode}", "sec": time.time() - t0}
    for line in r.stdout.splitlines():
        if line.startswith("SELF_INTERSECT"):
            _, a, b = line.split()
            return {"skipped": False, "pairs": int(a), "triangles": int(b), "sec": time.time() - t0}
    return {"skipped": True, "reason": "未解析到自交结果", "sec": time.time() - t0}


def compute_topology(mesh, skip_self_intersect=False, max_faces_self_intersect=1_500_000,
                     mesh_path=None, self_intersect_timeout=120):
    import open3d as o3d
    out = {}
    V = len(mesh.vertices)
    F = len(mesh.triangles)
    tri = np.asarray(mesh.triangles)
    E = _unique_edges_count(tri)
    out["V"] = V
    out["F"] = F
    out["E"] = E
    out["euler"] = int(V - E + F)

    # 连通分量
    if F > 0:
        clusters, cluster_n, cluster_area = mesh.cluster_connected_triangles()
        cluster_n = np.asarray(cluster_n)
        out["n_components"] = int(cluster_n.shape[0])
        out["max_component_faces"] = int(cluster_n.max())
        out["max_component_ratio"] = float(cluster_n.max() / F)
        top = np.sort(cluster_n)[::-1][:5]
        out["top5_component_faces"] = [int(x) for x in top]
        # 小分量 (面数 < 0.1% F) 计数 —— 漂浮碎块代理
        thr = max(1, int(0.001 * F))
        out["n_small_components_lt_0.1pct"] = int((cluster_n < thr).sum())
    else:
        out["n_components"] = 0
        out["max_component_faces"] = 0
        out["max_component_ratio"] = float("nan")
        out["top5_component_faces"] = []
        out["n_small_components_lt_0.1pct"] = 0

    # 非流形边 / 边界边
    nm_true = _edge_set(mesh.get_non_manifold_edges(allow_boundary_edges=True))   # >2 面
    nm_false = _edge_set(mesh.get_non_manifold_edges(allow_boundary_edges=False))  # !=2 面
    boundary_edges = nm_false - nm_true  # 恰好 1 面
    out["non_manifold_edges"] = len(nm_true)
    out["boundary_edges"] = len(boundary_edges)
    out["non_manifold_vertices"] = len(np.asarray(mesh.get_non_manifold_vertices()))
    out["holes_boundary_loops"] = _count_boundary_loops(boundary_edges)

    # 流形性 / 水密性
    out["is_edge_manifold"] = bool(mesh.is_edge_manifold(allow_boundary_edges=True))
    out["is_vertex_manifold"] = bool(mesh.is_vertex_manifold())
    out["is_watertight"] = bool(mesh.is_watertight())

    # 退化三角形
    out["degenerate_triangles"] = _degenerate_triangles(mesh)

    # 自交三角形 (open3d 在大网格上极慢, 用带超时的子进程隔离)
    out["self_intersect_skipped"] = False
    if skip_self_intersect:
        out["self_intersect_skipped"] = True
        out["self_intersect_skip_reason"] = "用户 --skip_self_intersect"
        out["self_intersecting_pairs"] = None
        out["self_intersecting_triangles"] = None
    elif F > max_faces_self_intersect:
        out["self_intersect_skipped"] = True
        out["self_intersect_skip_reason"] = f"面数 {F} > 上限 {max_faces_self_intersect}"
        out["self_intersecting_pairs"] = None
        out["self_intersecting_triangles"] = None
    elif mesh_path is not None:
        res = self_intersect_timed(mesh_path, self_intersect_timeout)
        out["self_intersect_sec"] = res.get("sec")
        if res.get("skipped"):
            out["self_intersect_skipped"] = True
            out["self_intersect_skip_reason"] = res.get("reason")
            out["self_intersecting_pairs"] = None
            out["self_intersecting_triangles"] = None
        else:
            out["self_intersecting_pairs"] = res["pairs"]
            out["self_intersecting_triangles"] = res["triangles"]
    else:
        # 无 mesh_path (如单元测试直接传 mesh 对象): 内联计算, 不限时
        t_si = time.time()
        pairs = np.asarray(mesh.get_self_intersecting_triangles())
        out["self_intersecting_pairs"] = int(pairs.shape[0]) if pairs.size else 0
        out["self_intersecting_triangles"] = int(np.unique(pairs).shape[0]) if pairs.size else 0
        out["self_intersect_sec"] = time.time() - t_si

    return out


def trimesh_crosscheck(mesh_path):
    """用 trimesh 交叉验证 (可选)。返回 dict 或 None。"""
    try:
        import trimesh
    except Exception:
        return None
    try:
        m = trimesh.load(mesh_path, process=False, force="mesh")
        res = {
            "trimesh_available": True,
            "V": int(len(m.vertices)),
            "F": int(len(m.faces)),
            "euler_number": int(m.euler_number),
            "is_watertight": bool(m.is_watertight),
        }
        try:
            outline = m.outline()
            res["boundary_loops"] = int(len(outline.entities))
        except Exception as e:
            res["boundary_loops_error"] = str(e)
        return res
    except Exception as e:
        return {"trimesh_available": True, "error": str(e)}


def main():
    ap = argparse.ArgumentParser(description="M3 拓扑/网格质量指标")
    ap.add_argument("--mesh", required=True)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--tag", default="基线")
    ap.add_argument("--skip_self_intersect", action="store_true",
                    help="跳过自交检测 (大网格很慢)")
    ap.add_argument("--max_faces_self_intersect", type=int, default=1_500_000)
    ap.add_argument("--self_intersect_timeout", type=int, default=120,
                    help="自交计算子进程超时秒数, 超时则标记跳过")
    ap.add_argument("--no_trimesh", action="store_true", help="不做 trimesh 交叉验证")
    ap.add_argument("--log", default=ec.DEFAULT_EXEC_LOG)
    args = ap.parse_args()

    t0 = time.time()
    mesh = ec.load_mesh_o3d(args.mesh, clean=True)
    topo = compute_topology(mesh, args.skip_self_intersect, args.max_faces_self_intersect,
                            mesh_path=os.path.abspath(args.mesh),
                            self_intersect_timeout=args.self_intersect_timeout)
    cross = None if args.no_trimesh else trimesh_crosscheck(args.mesh)

    json_obj = {
        "tag": args.tag,
        "mesh_path": os.path.abspath(args.mesh),
        "topology": topo,
        "trimesh_crosscheck": cross,
        "elapsed_sec": time.time() - t0,
    }

    kvs = [
        ("顶点数 V", topo["V"]),
        ("面数 F", topo["F"]),
        ("唯一边数 E", topo["E"]),
        ("欧拉数 (V-E+F)", topo["euler"]),
        ("连通分量数", topo["n_components"]),
        ("最大分量面数", topo["max_component_faces"]),
        ("最大分量面数占比", topo["max_component_ratio"]),
        ("前5大分量面数", topo["top5_component_faces"]),
        ("小分量数(<0.1%F)", topo["n_small_components_lt_0.1pct"]),
        ("非流形边数(>2面共享)", topo["non_manifold_edges"]),
        ("边界边数(恰好1面)", topo["boundary_edges"]),
        ("非流形顶点数", topo["non_manifold_vertices"]),
        ("孔洞数(边界环数)", topo["holes_boundary_loops"]),
        ("退化三角形数(面积≈0)", topo["degenerate_triangles"]),
        ("边流形", topo["is_edge_manifold"]),
        ("顶点流形", topo["is_vertex_manifold"]),
        ("水密", topo["is_watertight"]),
    ]
    if topo.get("self_intersect_skipped"):
        kvs.append(("自交三角形", "已跳过 " + topo.get("self_intersect_skip_reason", "")))
    else:
        kvs.append(("自交相交对数", topo["self_intersecting_pairs"]))
        kvs.append(("自交涉及三角形数", topo["self_intersecting_triangles"]))

    txt_sections = [("网格拓扑统计", kvs)]
    if cross:
        ck = [(k, v) for k, v in cross.items()]
        txt_sections.append(("trimesh 交叉验证", ck))

    basename = f"拓扑指标_{args.tag}"
    jp, tp = ec.write_report(args.out_dir, basename, json_obj,
                             f"M3 拓扑/网格质量指标 — {args.tag}", txt_sections)
    ec.log_exec(f"M3 拓扑指标 完成 tag={args.tag} mesh={os.path.basename(args.mesh)} "
                f"V={topo['V']} F={topo['F']} comps={topo['n_components']} -> {jp}", args.log)
    print(f"[M3] 写出 {jp}\n[M3] 写出 {tp}")


if __name__ == "__main__":
    # 隐藏的自交计算子进程入口 (被 self_intersect_timed 调用)
    if len(sys.argv) == 3 and sys.argv[1] == "--_self_intersect_worker":
        _self_intersect_worker(sys.argv[2])
    else:
        main()
