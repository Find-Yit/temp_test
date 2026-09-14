#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段 2e — 基线 vs 改动(τ0.01/0.02/0.05) 对比图生成 (matplotlib CPU 兜底, 本节点无 EGL)。

产物 (全部写入 考核提交/可视化/对比图/):
  - 网格渲染_{S}_{v}.png / 连通分量着色_{S}_{v}.png / 点到面误差热图_{S}_{v}.png
      (S ∈ {基线,改动_τ0.01,改动_τ0.02,改动_τ0.05}; v ∈ {视角1_测试相机,视角2_俯视,视角3_侧俯视})
  - 表面点云_剔点前后_{S}_{v}.png  (仅改动设置; 被剔点=红, 保留点=灰)
  - 渲染对比_共用coarse_视角000001.png  (GT|3DGS-7k|coarse SuGaR; 基线与改动共用同一 coarse)
  - 局部放大_{区域}_{S}.png  (2 区域 × 4 设置; 同一裁剪框)
  - 视角参数.json / 色标范围.txt / 局部放大框.json / 指标对照表.txt / 组件与色标_中间量.json

一致性保证:
  - 同一 (类型,视角) 在所有设置间: 相同 figsize/dpi(=750x750px)、相同 (elev,azim)、相同坐标轴范围(裁剪框)。
  - 热图色标: vmin=0, vmax = 各设置"相机bbox内每面到裁剪参考点云距离 P95"的最大值 (写入 色标范围.txt); bbox 外漂浮/壳面距离超上限, 饱和为最深色。
  - 世界系 COLMAP +Y 向下; 显示系用 vm=[x,z,-y] (行列式=+1 真旋转, 不镜像) 使重力向下正确。
  - 点云 1000 万点先随机下采样 (seed 0) 再画。

只读输入; 不改 repo/SuGaR; 不 git commit。用法: cd 项目根 && source env.sh && python scripts/eval/阶段2e_对比图.py
"""
import os, sys, json, time, argparse
import numpy as np
import open3d as o3d
from scipy.spatial import cKDTree

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as mcm
from matplotlib.colors import Normalize
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_common as ec

BASE = "/scratch/e1351071/zju_test_test"
OUT_DIR = os.path.join(BASE, "考核提交/可视化/对比图")
REF_A = os.path.join(BASE, "outputs/基线_truck/3dgs_7k/point_cloud/iteration_7000/point_cloud.ply")
LOG = os.path.join(OUT_DIR, "生成日志.txt")

# 相机中心 bbox (取自 outputs/基线_truck/评测/几何指标_基线.json 的 crop_bbox)
CROP_MIN = np.array([-4.316398107941433, -0.8754497499635268, -3.726967802152537])
CROP_MAX = np.array([5.336845559911888, 0.7473594673930097, 5.3348530649516945])
CCTR = np.array([0.51022373, -0.06404514, 0.80394263])
cx, cy, cz = CCTR

SETTINGS = [
    ("基线",       os.path.join(BASE, "outputs/基线_truck/mesh/sugarmesh_3Dgs7000_densityestim02_sdfnorm02_level03_decim1000000.ply"), None),
    ("改动_τ0.01", os.path.join(BASE, "outputs/改动_truck/改动_τ0.01/sugarmesh_3Dgs7000_densityestim02_sdfnorm02_level03_decim1000000.ply"), "改动_τ0.01"),
    ("改动_τ0.02", os.path.join(BASE, "outputs/改动_truck/改动_τ0.02/sugarmesh_3Dgs7000_densityestim02_sdfnorm02_level03_decim1000000.ply"), "改动_τ0.02"),
    ("改动_τ0.05", os.path.join(BASE, "outputs/改动_truck/改动_τ0.05/sugarmesh_3Dgs7000_densityestim02_sdfnorm02_level03_decim1000000.ply"), "改动_τ0.05"),
]

# 3 个固定视角: 视角1 由测试相机000001 派生 (elev=-10 因 +Y 向下); 视角2 俯视; 视角3 侧俯视。
VIEWS = {
    "视角1_测试相机": dict(elev=-10.0, azim=-47.05, box=(cx-6, cx+6, cy-3.5, cy+3.0, cz-6, cz+6), budget=60000,
                        说明="测试相机 idx0(img 000001, 位置[3.399,0.684,-2.299]) 派生的近地面3/4视角"),
    "视角2_俯视":    dict(elev=80.0, azim=-47.0, box=(cx-25, cx+25, cy-15, cy+7, cz-25, cz+25), budget=90000,
                        说明="俯视, 展示背景壳/漂浮碎块的水平分布与剔除"),
    "视角3_侧俯视":  dict(elev=22.0, azim=140.0, box=(cx-9, cx+9, cy-5, cy+3.5, cz-9, cz+9), budget=75000,
                        说明="对侧抬高3/4视角, 展示车身+近景漂浮物"),
}

# 局部放大 2 区域 (裁剪框由基线连通分量/面密度分析选出, 均为剔除率≈0.55 的显著漂浮区)
ZOOMS = {
    "地下反射漂浮层": dict(box=(cx-5, cx+5, cy+1.0, cy+6.0, cz-5, cz+5), elev=78.0, azim=-47.0, budget=80000,
                     说明="车体下方(+Y方向)的地下反射漂浮薄层; 俯视看其面密度被剔薄"),
    "背景壳右后角":   dict(box=(8.0, 24.0, cy-15, cy+7, -24.0, -8.0), elev=18.0, azim=-47.0, budget=80000,
                     说明="远景背景壳一角(X正Z负); 斜视看壳体碎块变稀疏"),
}

FIGSIZE = (6, 6); DPI = 125
AX_RECT = [0.02, 0.03, 0.84, 0.88]; CBAR_RECT = [0.88, 0.14, 0.028, 0.68]


# ---------------------------------------------------------------- 渲染基元
def world_to_mpl(v):
    """世界系(+Y下)->显示系(Z上): vm=[x,z,-y], det=+1 真旋转, 无镜像。"""
    vm = v[:, [0, 2, 1]].copy(); vm[:, 2] = -vm[:, 2]; return vm


def clip_mesh(mesh, box):
    v = np.asarray(mesh.vertices); f = np.asarray(mesh.triangles)
    if len(f) == 0:
        return o3d.geometry.TriangleMesh()
    c = v[f].mean(1); xm, xM, ym, yM, zm, zM = box
    keep = (c[:, 0] >= xm) & (c[:, 0] <= xM) & (c[:, 1] >= ym) & (c[:, 1] <= yM) & (c[:, 2] >= zm) & (c[:, 2] <= zM)
    f2 = f[keep]
    if len(f2) == 0:
        return o3d.geometry.TriangleMesh()
    used = np.unique(f2); remap = -np.ones(len(v), np.int64); remap[used] = np.arange(len(used))
    return o3d.geometry.TriangleMesh(o3d.utility.Vector3dVector(v[used]),
                                     o3d.utility.Vector3iVector(remap[f2]))


def decimate(mesh, budget):
    if budget and len(mesh.triangles) > budget:
        mesh = mesh.simplify_quadric_decimation(int(budget)); mesh.remove_unreferenced_vertices()
    return mesh


def face_shading(v, f, light=(0.35, 0.55, 1.0)):
    if len(f) == 0:
        return np.zeros(0)
    p0, p1, p2 = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    n = np.cross(p1 - p0, p2 - p0); ln = np.linalg.norm(n, axis=1, keepdims=True); ln[ln == 0] = 1; n = n / ln
    l = np.asarray(light, float); l = l / np.linalg.norm(l)
    return 0.35 + 0.65 * np.abs(n @ l)


def _painter(tris, elev, azim):
    er, ar = np.radians(elev), np.radians(azim)
    view = np.array([np.cos(er) * np.cos(ar), np.cos(er) * np.sin(ar), np.sin(er)])
    return np.argsort(tris.mean(1) @ view)


def _setup_ax(fig, box, elev, azim, title):
    ax = fig.add_axes(AX_RECT, projection="3d")
    xm, xM, ym, yM, zm, zM = box
    ax.set_xlim(xm, xM); ax.set_ylim(zm, zM); ax.set_zlim(-yM, -ym)
    ax.set_box_aspect((xM - xm, zM - zm, yM - ym))
    ax.view_init(elev=elev, azim=azim); ax.set_axis_off()
    if title:
        fig.text(0.44, 0.965, title, ha="center", va="top", fontsize=11)
    return ax


def render_faces(v, f, facecolors, box, elev, azim, out, title="", mapper=None, cbar_label=""):
    fig = plt.figure(figsize=FIGSIZE, dpi=DPI)
    ax = _setup_ax(fig, box, elev, azim, title)
    if len(f) > 0:
        vm = world_to_mpl(v); tris = vm[f]
        order = _painter(tris, elev, azim)
        pc = Poly3DCollection(tris[order], facecolors=np.clip(facecolors, 0, 1)[order],
                              edgecolors="none", linewidths=0)
        pc.set_rasterized(True); ax.add_collection3d(pc)
    else:
        ax.text2D(0.5, 0.5, "（该视角裁剪框内无网格）", transform=ax.transAxes, ha="center", fontsize=12)
    if mapper is not None:
        cax = fig.add_axes(CBAR_RECT); cb = fig.colorbar(mapper, cax=cax)
        cb.set_label(cbar_label, fontsize=9); cax.tick_params(labelsize=8)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    fig.savefig(out, dpi=DPI); plt.close(fig)
    return out


def render_points(pts, rgba, box, elev, azim, out, title="", s=0.35):
    fig = plt.figure(figsize=FIGSIZE, dpi=DPI)
    ax = _setup_ax(fig, box, elev, azim, title)
    if len(pts) > 0:
        pm = world_to_mpl(pts)
        order = np.argsort(pm @ np.array([np.cos(np.radians(elev)) * np.cos(np.radians(azim)),
                                          np.cos(np.radians(elev)) * np.sin(np.radians(azim)),
                                          np.sin(np.radians(elev))]))
        ax.scatter(pm[order, 0], pm[order, 1], pm[order, 2], c=rgba[order],
                   s=s, linewidths=0, rasterized=True, depthshade=False)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    fig.savefig(out, dpi=DPI); plt.close(fig)
    return out


def log(msg):
    ec.log_exec(msg, LOG)


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="all",
                    help="all | mesh | pointcloud | zoom | montage | meta")
    ap.add_argument("--settings", default="", help="逗号分隔子集(调试)")
    ap.add_argument("--pt_target", type=int, default=1500000, help="点云下采样目标(<=200万)")
    args = ap.parse_args()
    ec.set_seed(0); ec.setup_cjk_font()
    os.makedirs(OUT_DIR, exist_ok=True)
    t_all = time.time()
    log(f"==== 阶段2e 对比图生成 开始 only={args.only} ====")

    settings = SETTINGS
    if args.settings:
        want = set(args.settings.split(","))
        settings = [s for s in SETTINGS if s[0] in want]

    # ---- 参考点云 A 裁剪到 bbox (与 M2 completeness 口径一致) ----
    refA = ec.load_points_ply(REF_A)
    m = np.all((refA >= CROP_MIN) & (refA <= CROP_MAX), axis=1)
    refA_crop = refA[m]
    treeA = cKDTree(refA_crop)
    log(f"参考A 3DGS点云: 全 {len(refA)}, 裁剪到相机bbox {len(refA_crop)} (热图用此裁剪点云)")

    # ---- 预扫描: 每设置全网格 V/F/连通分量 + bbox内每面距离 P95 (定 vmax) ----
    prep = {}
    for name, mp, _ in settings:
        t = time.time()
        full = o3d.io.read_triangle_mesh(mp); full.remove_unreferenced_vertices()
        V, F = len(full.vertices), len(full.triangles)
        clusters, cn, _ = full.cluster_connected_triangles()
        cn = np.asarray(cn); nc = int(len(cn)); maxr = float(cn.max() / cn.sum())
        # bbox 内 P95: 裁剪到 crop bbox -> 抽取 60k -> 每面质心到 refA_crop 距离
        inb = clip_mesh(full, (CROP_MIN[0], CROP_MAX[0], CROP_MIN[1], CROP_MAX[1], CROP_MIN[2], CROP_MAX[2]))
        inb = decimate(inb, 60000)
        vv = np.asarray(inb.vertices); ff = np.asarray(inb.triangles); cent = vv[ff].mean(1)
        d, _ = treeA.query(cent, k=1, workers=-1)
        p95 = float(np.percentile(d, 95))
        prep[name] = dict(V=V, F=F, n_components=nc, max_ratio=maxr, p95_in=p95, full=full)
        log(f"预扫描 {name}: V={V} F={F} 连通分量={nc} 最大占比={maxr:.4f} bbox内P95={p95:.4f} ({time.time()-t:.0f}s)")

    vmax = max(prep[n]["p95_in"] for n in prep)
    log(f"热图 vmax = max(bbox内P95) = {vmax:.4f}")
    mapper = mcm.ScalarMappable(norm=Normalize(vmin=0.0, vmax=vmax), cmap="turbo")

    # ---- 主网格图: 网格渲染 / 连通分量 / 误差热图 ----
    if args.only in ("all", "mesh"):
        for name, mp, _ in settings:
            full = prep[name]["full"]
            for vn, vc in VIEWS.items():
                t = time.time()
                dm = decimate(clip_mesh(full, vc["box"]), vc["budget"])
                v = np.asarray(dm.vertices); f = np.asarray(dm.triangles)
                inten = face_shading(v, f)
                nc_auth = prep[name]["n_components"]
                # (1) 网格渲染 灰
                g = inten if len(f) else inten
                render_faces(v, f, np.stack([g, g, g], 1) if len(f) else np.zeros((0, 3)),
                             vc["box"], vc["elev"], vc["azim"],
                             os.path.join(OUT_DIR, f"网格渲染_{name}_{vn}.png"),
                             title=f"网格渲染  {name}  {vn}")
                # (2) 连通分量 (在裁剪+抽取网格上聚类; 全网格权威分量数标注在角落)
                if len(f):
                    cl, cln, _ = dm.cluster_connected_triangles()
                    cl = np.asarray(cl); cln = np.asarray(cln)
                    order = np.argsort(cln)[::-1]
                    rng = np.random.default_rng(0)
                    palette = rng.random((max(1, len(cln)), 3)) * 0.7 + 0.2
                    if len(cln):
                        palette[order[0]] = [0.7, 0.7, 0.7]
                    frgb = palette[cl] * (0.55 + 0.45 * inten)[:, None]
                else:
                    frgb = np.zeros((0, 3))
                render_faces(v, f, frgb, vc["box"], vc["elev"], vc["azim"],
                             os.path.join(OUT_DIR, f"连通分量着色_{name}_{vn}.png"),
                             title=f"连通分量  {name}  {vn}  (全网格分量数={nc_auth})")
                # (3) 误差热图
                if len(f):
                    cent = v[f].mean(1); d, _ = treeA.query(cent, k=1, workers=-1)
                    base = mapper.to_rgba(d)[:, :3]
                    hc = base * (0.6 + 0.4 * inten)[:, None]
                else:
                    hc = np.zeros((0, 3))
                render_faces(v, f, hc, vc["box"], vc["elev"], vc["azim"],
                             os.path.join(OUT_DIR, f"点到面误差热图_{name}_{vn}.png"),
                             title=f"点到面误差热图  {name}  {vn}",
                             mapper=mapper, cbar_label=f"到裁剪参考点云距离 (0–{vmax:.3f})")
                log(f"网格图 {name} {vn}: {len(f)}面 ({time.time()-t:.1f}s)")

    # ---- 剔点前后点云 (仅改动设置) ----
    if args.only in ("all", "pointcloud"):
        pre = ec.load_points_ply(os.path.join(BASE, "outputs/改动_truck/改动_τ0.01/表面点_剔点前.ply"))
        rng = np.random.default_rng(0)
        idx = rng.choice(len(pre), size=min(args.pt_target, len(pre)), replace=False)
        sub = pre[idx]
        log(f"剔点前点云 {len(pre)} -> 下采样 {len(sub)} (seed0)")
        for name, mp, tag in settings:
            if tag is None:
                continue
            post = ec.load_points_ply(os.path.join(BASE, f"outputs/改动_truck/{tag}/表面点_剔点后.ply"))
            tp = cKDTree(post); dd, _ = tp.query(sub, k=1, workers=-1)
            culled = dd > 1e-6
            log(f"点云 {name}: 保留 {int((~culled).sum())} 剔除 {int(culled.sum())} 剔除比 {culled.mean():.4f}")
            rgba = np.empty((len(sub), 4))
            rgba[~culled] = [0.55, 0.55, 0.58, 0.45]   # 保留=灰
            rgba[culled] = [0.86, 0.12, 0.12, 0.85]    # 剔除=红
            for vn, vc in VIEWS.items():
                t = time.time()
                xm, xM, ym, yM, zm, zM = vc["box"]
                inb = (sub[:, 0] >= xm) & (sub[:, 0] <= xM) & (sub[:, 1] >= ym) & (sub[:, 1] <= yM) & (sub[:, 2] >= zm) & (sub[:, 2] <= zM)
                render_points(sub[inb], rgba[inb], vc["box"], vc["elev"], vc["azim"],
                              os.path.join(OUT_DIR, f"表面点云_剔点前后_{name}_{vn}.png"),
                              title=f"表面点云 剔点前后  {name}  {vn} (红=被剔)",
                              s=0.35 if vn != "视角2_俯视" else 0.25)
                log(f"点云图 {name} {vn}: {int(inb.sum())}点 ({time.time()-t:.1f}s)")

    # ---- 局部放大 ----
    if args.only in ("all", "zoom"):
        for zn, zc in ZOOMS.items():
            for name, mp, _ in settings:
                t = time.time()
                full = prep[name]["full"]
                clipped = clip_mesh(full, zc["box"])
                raw = len(clipped.triangles)   # 框内原始面数 (真实密度对比量, 未抽取)
                dm = decimate(clipped, zc["budget"])
                v = np.asarray(dm.vertices); f = np.asarray(dm.triangles)
                inten = face_shading(v, f); g = inten
                render_faces(v, f, np.stack([g, g, g], 1) if len(f) else np.zeros((0, 3)),
                             zc["box"], zc["elev"], zc["azim"],
                             os.path.join(OUT_DIR, f"局部放大_{zn}_{name}.png"),
                             title=f"局部放大 {zn}  {name}  (框内原始 {raw} 面)")
                log(f"局部放大 {zn} {name}: 框内原始{raw}面 渲染{len(f)}面 ({time.time()-t:.1f}s)")

    # ---- 渲染对比 montage (GT|3DGS|coarse, 共用 coarse) ----
    if args.only in ("all", "montage"):
        rdir = os.path.join(BASE, "outputs/基线_truck/评测/渲染图_基线")
        trip = [("GT_000_000001.png", "GT (真值)"),
                ("3DGS_000_000001.png", "3DGS-7k"),
                ("coarseSuGaR_000_000001.png", "coarse SuGaR")]
        imgs = [(plt.imread(os.path.join(rdir, fn)), lab) for fn, lab in trip if os.path.isfile(os.path.join(rdir, fn))]
        if imgs:
            fig, axes = plt.subplots(1, len(imgs), figsize=(5 * len(imgs), 5))
            if len(imgs) == 1:
                axes = [axes]
            for ax, (im, lab) in zip(axes, imgs):
                ax.imshow(im); ax.set_title(lab, fontsize=12); ax.axis("off")
            fig.suptitle("渲染对比 测试视角000001 — 基线与所有改动共用同一 coarse SuGaR (剔点在mesh提取阶段, 不改高斯)", fontsize=11)
            out = os.path.join(OUT_DIR, "渲染对比_共用coarse_视角000001.png")
            fig.savefig(out, dpi=DPI, bbox_inches="tight"); plt.close(fig)
            log(f"渲染对比 montage: {out} ({len(imgs)}面板)")

    # ---- 元数据 ----
    if args.only in ("all", "meta"):
        # 视角参数.json
        vjson = {"说明": "同一(类型,视角)在所有设置间使用相同 elev/azim/裁剪框/figsize/dpi; 显示系 vm=[x,z,-y]",
                 "figsize": FIGSIZE, "dpi": DPI, "像素": [int(FIGSIZE[0]*DPI), int(FIGSIZE[1]*DPI)],
                 "世界系说明": "COLMAP +Y 向下; 显示 vm=[x,z,-y] 使重力向下",
                 "相机bbox": {"min": CROP_MIN.tolist(), "max": CROP_MAX.tolist(), "center": CCTR.tolist()},
                 "视角": {vn: {"elev": vc["elev"], "azim": vc["azim"],
                             "裁剪框_world": {"x": [vc["box"][0], vc["box"][1]],
                                          "y": [vc["box"][2], vc["box"][3]],
                                          "z": [vc["box"][4], vc["box"][5]]},
                             "抽取面预算": vc["budget"], "说明": vc["说明"]} for vn, vc in VIEWS.items()}}
        json.dump(vjson, open(os.path.join(OUT_DIR, "视角参数.json"), "w"), indent=2, ensure_ascii=False)
        # 局部放大框.json
        zjson = {zn: {"elev": zc["elev"], "azim": zc["azim"], "抽取面预算": zc["budget"], "说明": zc["说明"],
                      "裁剪框_world": {"x": [zc["box"][0], zc["box"][1]], "y": [zc["box"][2], zc["box"][3]],
                                    "z": [zc["box"][4], zc["box"][5]]}} for zn, zc in ZOOMS.items()}
        json.dump(zjson, open(os.path.join(OUT_DIR, "局部放大框.json"), "w"), indent=2, ensure_ascii=False)
        # 色标范围.txt
        with open(os.path.join(OUT_DIR, "色标范围.txt"), "w", encoding="utf-8") as fp:
            fp.write("点到面误差热图 统一色标 (阶段2e)\n" + "=" * 50 + "\n")
            fp.write("cmap = turbo ; vmin = 0.0\n")
            fp.write(f"vmax = {vmax:.6f}  (= 各设置 '相机bbox内每面到裁剪参考点云距离 P95' 的最大值)\n")
            fp.write("参考点云 = 3DGS高斯中心裁剪到相机bbox (与 M2 completeness 口径一致)\n")
            fp.write("说明: bbox 外的漂浮/背景壳面距离远大于 vmax, 饱和为色标最深端(红)。\n\n各设置 bbox内P95:\n")
            for name in prep:
                fp.write(f"  {name}: {prep[name]['p95_in']:.6f}\n")
        # 中间量
        json.dump({n: {k: prep[n][k] for k in ("V", "F", "n_components", "max_ratio", "p95_in")} for n in prep},
                  open(os.path.join(OUT_DIR, "组件与色标_中间量.json"), "w"), indent=2, ensure_ascii=False)
        log("元数据: 视角参数.json / 局部放大框.json / 色标范围.txt / 组件与色标_中间量.json 已写")

    log(f"==== 阶段2e 完成 总耗时 {time.time()-t_all:.0f}s ====")


if __name__ == "__main__":
    main()
