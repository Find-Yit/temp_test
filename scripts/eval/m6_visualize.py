#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M6 可视化 — 网格截图 / 点到面误差热图 / 连通分量着色 / 渲染对比拼图。

渲染后端:
  - matplotlib (默认, 纯 CPU): open3d OffscreenRenderer 在本无 EGL 的节点会硬崩溃,
    故默认用 matplotlib 三角面投影 (Poly3DCollection) 兜底; 大网格先抽取到 ~face_budget 面。
  - pytorch3d (可选, 需 GPU): 更高质量, 但会占显存, 与训练竞争时慎用。

模式 (--mode):
  mesh_shots     固定 2-3 视角的网格灰度截图
  error_heatmap  按点到面误差着色 (需 --ref 参考点云)
  components     连通分量着色
  montage        渲染对比拼图 (GT | 3DGS | coarse SuGaR), 输入为图片文件/目录
  all            以上尽可能全做 (缺输入的自动跳过)

用法示例:
  python m6_visualize.py --mode mesh_shots --mesh mesh.ply --out_dir report/图 --tag 基线
  python m6_visualize.py --mode error_heatmap --mesh mesh.ply --ref colmap_or_gs.ply \
      --out_dir report/图 --tag 基线
  python m6_visualize.py --mode montage --gt_img a.png --gs_img b.png --sugar_img c.png \
      --out_dir report/图 --tag 基线_view0
"""
import os
import sys
import time
import argparse
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_common as ec

DEFAULT_VIEWS = [(20, -60), (15, 60), (75, -90)]  # (elev, azim)


def decimate_mesh(mesh, face_budget):
    """把网格抽取到不超过 face_budget 面 (matplotlib 渲染速度考量)。"""
    n_f = len(mesh.triangles)
    if face_budget and n_f > face_budget:
        mesh = mesh.simplify_quadric_decimation(int(face_budget))
        mesh.remove_unreferenced_vertices()
    return mesh


def _face_shading(verts, faces, light_dir=(0.3, 0.4, 1.0)):
    """按面法线与光照方向的夹角计算 [0.25,1] 的灰度强度, 做深度/立体感。"""
    p0, p1, p2 = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    n = np.cross(p1 - p0, p2 - p0)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1
    n = n / ln
    l = np.asarray(light_dir, dtype=np.float64)
    l = l / np.linalg.norm(l)
    inten = np.abs(n @ l)
    return 0.25 + 0.75 * inten


def _set_equal_3d(ax, verts):
    mins = verts.min(0)
    maxs = verts.max(0)
    ctr = (mins + maxs) / 2
    r = (maxs - mins).max() / 2
    if r == 0:
        r = 1.0
    ax.set_xlim(ctr[0] - r, ctr[0] + r)
    ax.set_ylim(ctr[1] - r, ctr[1] + r)
    ax.set_zlim(ctr[2] - r, ctr[2] + r)
    try:
        ax.set_box_aspect((1, 1, 1))
    except Exception:
        pass


def render_mesh_matplotlib(verts, faces, out_path, title="",
                           face_rgb=None, face_intensity=None,
                           views=DEFAULT_VIEWS, cmap=None, colorbar_label=None,
                           face_scalar=None):
    """用 matplotlib 渲染网格多视角图。
    face_rgb: (F,3) 每面颜色; 若 None 用灰度 face_intensity。
    face_scalar+cmap: 若给出, 按标量着色并画 colorbar。
    """
    verts = np.asarray(verts)
    faces = np.asarray(faces)
    tris = verts[faces]  # (F,3,3)

    if face_intensity is None:
        face_intensity = _face_shading(verts, faces)

    if face_scalar is not None and cmap is not None:
        import matplotlib.cm as cm
        norm = plt.Normalize(vmin=np.nanpercentile(face_scalar, 2),
                             vmax=np.nanpercentile(face_scalar, 98))
        mapper = cm.ScalarMappable(norm=norm, cmap=cmap)
        base = mapper.to_rgba(face_scalar)[:, :3]
        colors = base * face_intensity[:, None]
    elif face_rgb is not None:
        colors = np.asarray(face_rgb) * face_intensity[:, None]
    else:
        g = face_intensity
        colors = np.stack([g, g, g], axis=1)
    colors = np.clip(colors, 0, 1)

    nv = len(views)
    fig = plt.figure(figsize=(5 * nv, 5))
    for k, (elev, azim) in enumerate(views):
        ax = fig.add_subplot(1, nv, k + 1, projection="3d")
        # 按视线方向做画家算法排序 (远的先画)
        order = _painter_order(tris, elev, azim)
        pc = Poly3DCollection(tris[order], facecolors=colors[order],
                              edgecolors="none", linewidths=0)
        ax.add_collection3d(pc)
        _set_equal_3d(ax, verts)
        ax.view_init(elev=elev, azim=azim)
        ax.set_axis_off()
        ax.set_title(f"视角{k} (elev={elev},azim={azim})", fontsize=9)
    if face_scalar is not None and cmap is not None:
        cbar = fig.colorbar(mapper, ax=fig.axes, fraction=0.02, pad=0.02)
        if colorbar_label:
            cbar.set_label(colorbar_label)
    fig.suptitle(title, fontsize=11)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    fig.savefig(out_path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return out_path


def _painter_order(tris, elev, azim):
    """按相机视线方向对三角形质心排序 (远 -> 近), 供画家算法。"""
    elev_r = np.radians(elev)
    azim_r = np.radians(azim)
    view = np.array([np.cos(elev_r) * np.cos(azim_r),
                     np.cos(elev_r) * np.sin(azim_r),
                     np.sin(elev_r)])
    centroids = tris.mean(axis=1)
    depth = centroids @ view
    return np.argsort(depth)  # 小(远)->大(近)


def _per_face_error_from_ref(mesh, ref_points):
    """每面质心到参考点云的点到点最近距离 (KDTree)。返回 (F,) 距离。"""
    import open3d as o3d
    v = np.asarray(mesh.vertices)
    t = np.asarray(mesh.triangles)
    centroids = v[t].mean(axis=1)
    ref = o3d.geometry.PointCloud()
    ref.points = o3d.utility.Vector3dVector(np.asarray(ref_points))
    kdt = o3d.geometry.KDTreeFlann(ref)
    d = np.empty(len(centroids))
    for i, c in enumerate(centroids):
        _, idx, dist2 = kdt.search_knn_vector_3d(c, 1)
        d[i] = np.sqrt(dist2[0]) if len(dist2) else np.nan
    return d


def mode_mesh_shots(args, mesh):
    mesh = decimate_mesh(mesh, args.face_budget)
    verts = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.triangles)
    out = os.path.join(args.out_dir, f"网格截图_{args.tag}.png")
    render_mesh_matplotlib(verts, faces, out, title=f"网格截图 — {args.tag}")
    return [out]


def mode_error_heatmap(args, mesh):
    if not args.ref:
        print("[M6] error_heatmap 需要 --ref, 跳过")
        return []
    ref = ec.load_points_ply(args.ref) if args.ref.endswith((".ply", ".pcd")) \
        else _load_ref_any(args.ref, args.repo_root)
    mesh = decimate_mesh(mesh, args.face_budget)
    verts = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.triangles)
    err = _per_face_error_from_ref(mesh, ref)
    out = os.path.join(args.out_dir, f"误差热图_{args.tag}.png")
    render_mesh_matplotlib(verts, faces, out, title=f"点到面误差热图 — {args.tag}",
                           face_scalar=err, cmap="turbo", colorbar_label="到参考最近距离")
    return [out]


def mode_components(args, mesh):
    import open3d as o3d
    mesh = decimate_mesh(mesh, args.face_budget)
    verts = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.triangles)
    clusters, cluster_n, _ = mesh.cluster_connected_triangles()
    clusters = np.asarray(clusters)
    cluster_n = np.asarray(cluster_n)
    # 按分量大小排名着色 (最大分量固定灰, 其余用色轮突出碎块)
    order = np.argsort(cluster_n)[::-1]
    rank = np.empty_like(order)
    rank[order] = np.arange(len(order))
    rng = np.random.default_rng(0)
    palette = rng.random((max(1, len(cluster_n)), 3)) * 0.7 + 0.2
    if len(cluster_n) > 0:
        palette[order[0]] = [0.7, 0.7, 0.7]  # 最大分量灰色
    face_rgb = palette[clusters]
    out = os.path.join(args.out_dir, f"连通分量着色_{args.tag}.png")
    title = f"连通分量着色 — {args.tag} (分量数={len(cluster_n)})"
    render_mesh_matplotlib(verts, faces, out, title=title, face_rgb=face_rgb)
    return [out]


def mode_montage(args):
    """渲染对比拼图: GT | 3DGS | coarse SuGaR。输入为图片文件。"""
    imgs = []
    labels = []
    for path, lab in [(args.gt_img, "GT"), (args.gs_img, "3DGS"), (args.sugar_img, "coarse SuGaR")]:
        if path and os.path.isfile(path):
            imgs.append(plt.imread(path))
            labels.append(lab)
    if not imgs:
        print("[M6] montage 无有效输入图片, 跳过")
        return []
    n = len(imgs)
    fig, axes = plt.subplots(1, n, figsize=(5 * n, 5))
    if n == 1:
        axes = [axes]
    for ax, im, lab in zip(axes, imgs, labels):
        ax.imshow(im)
        ax.set_title(lab, fontsize=12)
        ax.axis("off")
    fig.suptitle(f"渲染对比 — {args.tag}", fontsize=13)
    out = os.path.join(args.out_dir, f"渲染对比_{args.tag}.png")
    os.makedirs(args.out_dir, exist_ok=True)
    fig.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return [out]


def _load_ref_any(path, repo_root):
    """加载参考点云: .ply/.pcd 用 open3d; COLMAP 用 colmap_loader。"""
    if os.path.isdir(path) or path.endswith((".bin", ".txt")):
        ec.setup_sugar_path(repo_root)
        from gaussian_splatting.scene.colmap_loader import read_points3D_binary, read_points3D_text
        p = path
        if os.path.isdir(path):
            p = os.path.join(path, "points3D.bin")
        if p.endswith(".txt"):
            xyz, _, _ = read_points3D_text(p)
        else:
            xyz, _, _ = read_points3D_binary(p)
        return np.asarray(xyz)
    return ec.load_points_ply(path)


def main():
    ap = argparse.ArgumentParser(description="M6 可视化")
    ap.add_argument("--mode", default="all",
                    choices=["mesh_shots", "error_heatmap", "components", "montage", "all"])
    ap.add_argument("--mesh", default=None)
    ap.add_argument("--ref", default=None, help="误差热图参考: .ply 或 COLMAP points3D")
    ap.add_argument("--gt_img", default=None)
    ap.add_argument("--gs_img", default=None)
    ap.add_argument("--sugar_img", default=None)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--tag", default="基线")
    ap.add_argument("--face_budget", type=int, default=40000,
                    help="matplotlib 渲染前抽取到的最大面数")
    ap.add_argument("--repo_root", default=ec.DEFAULT_REPO_ROOT)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--log", default=ec.DEFAULT_EXEC_LOG)
    args = ap.parse_args()

    t0 = time.time()
    ec.set_seed(args.seed)
    ec.setup_cjk_font()
    os.makedirs(args.out_dir, exist_ok=True)
    outputs = []

    need_mesh = args.mode in ("mesh_shots", "error_heatmap", "components", "all")
    mesh = None
    if need_mesh and args.mesh:
        mesh = ec.load_mesh_o3d(args.mesh, clean=True)

    if args.mode in ("mesh_shots", "all") and mesh is not None:
        outputs += mode_mesh_shots(args, ec.load_mesh_o3d(args.mesh, clean=True))
    if args.mode in ("error_heatmap", "all") and mesh is not None and args.ref:
        outputs += mode_error_heatmap(args, ec.load_mesh_o3d(args.mesh, clean=True))
    if args.mode in ("components", "all") and mesh is not None:
        outputs += mode_components(args, ec.load_mesh_o3d(args.mesh, clean=True))
    if args.mode in ("montage", "all"):
        if args.gt_img or args.gs_img or args.sugar_img:
            outputs += mode_montage(args)

    elapsed = time.time() - t0
    ec.log_exec(f"M6 可视化 完成 tag={args.tag} mode={args.mode} 产物={len(outputs)}张 "
                f"耗时={elapsed:.1f}s", args.log)
    for o in outputs:
        print(f"[M6] 写出 {o}")
    if not outputs:
        print("[M6] 未产出任何图 (检查输入参数)")


if __name__ == "__main__":
    main()
