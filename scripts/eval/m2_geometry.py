#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M2 几何指标 — mesh 与参考点云的双向点到面/点到点距离 + Chamfer + F-score@τ。

参考:
  参考 A: 3DGS 高斯中心 (point_cloud.ply)          —— 与被评 mesh 同源
  参考 B: COLMAP 稀疏点 (sparse/0/points3D.bin)     —— 干净但稀疏
两个参考各算一份, 结论一致才可信。

方向定义 (遵循本项目任务书):
  completeness 方向 = 网格表面采样点 -> 参考点云 (KDTree 最近点距离, 点到点)
  accuracy 方向     = 参考点 -> 网格表面 (o3d RaycastingScene.compute_distance, 点到面)
  (注: 部分文献 accuracy/completeness 命名相反; F-score 的计算与命名无关。)

F-score@τ:
  Precision@τ = mean(d_mesh2ref < τ)   网格被参考支撑的比例
  Recall@τ    = mean(d_ref2mesh < τ)   参考被网格覆盖的比例
  F = 2PR/(P+R)
  τ = ratio * 场景尺度; 场景尺度 = 相机中心包围盒对角线。

公平性: baseline 与 modified 必须用同一份参考、同一裁剪 bbox、同一采样点数与 seed。

用法示例:
  python m2_geometry.py \
    --mesh outputs/基线_truck/mesh/xxx.ply \
    --ref_a outputs/基线_truck/3dgs_7k/point_cloud/iteration_7000/point_cloud.ply \
    --ref_b_colmap data/tandt/truck/sparse/0/points3D.bin \
    --cameras_json outputs/基线_truck/3dgs_7k/cameras.json \
    --out_dir report/几何 --tag 基线
"""
import os
import sys
import argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_common as ec


def _read_colmap_points(path, repo_root):
    """读取 COLMAP sparse points3D (bin 或 text 目录或 .bin 文件)。
    使用 gaussian_splatting.scene.colmap_loader。"""
    ec.setup_sugar_path(repo_root)
    from gaussian_splatting.scene.colmap_loader import read_points3D_binary, read_points3D_text
    if os.path.isdir(path):
        binp = os.path.join(path, "points3D.bin")
        txtp = os.path.join(path, "points3D.txt")
        if os.path.isfile(binp):
            path = binp
        elif os.path.isfile(txtp):
            path = txtp
        else:
            raise FileNotFoundError(f"COLMAP points3D not found under {path}")
    if path.endswith(".txt"):
        xyz, rgb, err = read_points3D_text(path)
    else:
        xyz, rgb, err = read_points3D_binary(path)
    return np.asarray(xyz, dtype=np.float64)


def compute_bidirectional_distances(mesh, ref_points, n_sample, seed):
    """计算双向距离。
    返回 (d_mesh2ref, d_ref2mesh, n_faces, n_ref)。
    - d_mesh2ref: 网格表面均匀采样 n_sample 点 -> 参考点云 KDTree 最近点距离
    - d_ref2mesh: 参考点 -> 网格表面 raycasting 点到面距离
    """
    import open3d as o3d
    n_faces = len(mesh.triangles)
    n_ref = int(ref_points.shape[0])
    if n_faces == 0 or n_ref == 0:
        return (np.array([]), np.array([]), n_faces, n_ref)

    # accuracy: ref -> mesh surface (点到面, 精确)
    scene = o3d.t.geometry.RaycastingScene()
    tmesh = o3d.t.geometry.TriangleMesh.from_legacy(mesh)
    scene.add_triangles(tmesh)
    query = o3d.core.Tensor(ref_points.astype(np.float32), dtype=o3d.core.Dtype.Float32)
    d_ref2mesh = scene.compute_distance(query).numpy().astype(np.float64)

    # completeness: mesh 采样 -> ref (KDTree 点到点)
    ec.set_seed(seed)  # 固定 open3d 全局 seed (老版本无 sample_points_uniformly(seed=))
    sampled = mesh.sample_points_uniformly(number_of_points=int(n_sample))
    ref_pcd = o3d.geometry.PointCloud()
    ref_pcd.points = o3d.utility.Vector3dVector(ref_points)
    d_mesh2ref = np.asarray(sampled.compute_point_cloud_distance(ref_pcd), dtype=np.float64)

    return (d_mesh2ref, d_ref2mesh, n_faces, n_ref)


def eval_one_reference(mesh, ref_points, ref_name, scene_scale, tau_ratios,
                       n_sample, seed, crop_bbox=None):
    """对一个参考点云计算全部几何指标。返回 (json_dict, txt_kvs)。"""
    import open3d as o3d
    info = {"reference": ref_name}

    # 裁剪到同一 bbox
    n_ref_before = int(ref_points.shape[0])
    mesh_eval = mesh
    if crop_bbox is not None:
        amin, amax = np.asarray(crop_bbox[0], dtype=np.float64), np.asarray(crop_bbox[1], dtype=np.float64)
        try:
            bbox = o3d.geometry.AxisAlignedBoundingBox(min_bound=amin, max_bound=amax)
            mesh_eval = mesh.crop(bbox)
            mesh_eval.remove_unreferenced_vertices()
            _, ref_points = ec.crop_points_aabb(ref_points, amin, amax)
        except Exception as e:
            print(f"[M2][警告] 裁剪失败, 退回不裁剪: {e}")
            mesh_eval = mesh
    n_ref_after = int(ref_points.shape[0])

    d_m2r, d_r2m, n_faces, n_ref = compute_bidirectional_distances(
        mesh_eval, ref_points, n_sample, seed)

    info["n_faces_in_bbox"] = n_faces
    info["n_ref_points_before_crop"] = n_ref_before
    info["n_ref_points_in_bbox"] = n_ref_after
    info["n_mesh_samples"] = int(n_sample)

    if d_m2r.size == 0 or d_r2m.size == 0:
        info["error"] = "裁剪后网格或参考点为空, 无法计算距离"
        txt_kvs = [("参考", ref_name), ("状态", info["error"]),
                   ("bbox 内面数", n_faces), ("bbox 内参考点数", n_ref_after)]
        return info, txt_kvs

    # 方向统计
    stat_m2r = ec.distance_stats(d_m2r)   # completeness (mesh->ref)
    stat_r2m = ec.distance_stats(d_r2m)   # accuracy (ref->mesh)
    info["completeness_mesh_to_ref"] = stat_m2r
    info["accuracy_ref_to_mesh"] = stat_r2m

    chamfer = 0.5 * (stat_m2r["mean"] + stat_r2m["mean"])
    info["chamfer_l1"] = float(chamfer)
    # 对称 RMSE Chamfer (可选参考)
    info["chamfer_rmse"] = float(0.5 * (stat_m2r["rmse"] + stat_r2m["rmse"]))

    # F-score@τ
    info["scene_scale_diagonal"] = float(scene_scale)
    info["fscore"] = {}
    for ratio in tau_ratios:
        tau = float(ratio) * float(scene_scale)
        precision = float((d_m2r < tau).mean())   # 网格被参考支撑
        recall = float((d_r2m < tau).mean())       # 参考被网格覆盖
        f = 2 * precision * recall / (precision + recall + 1e-12)
        info["fscore"][f"tau_{ratio}"] = {
            "tau_ratio": float(ratio),
            "tau_abs": tau,
            "precision": precision,
            "recall": recall,
            "fscore": float(f),
        }

    # 中文 txt
    txt_kvs = [
        ("参考", ref_name),
        ("bbox 内面数", n_faces),
        ("bbox 内参考点数(裁剪前->后)", f"{n_ref_before} -> {n_ref_after}"),
        ("网格采样点数", int(n_sample)),
        ("Chamfer-L1 (对称均值)", chamfer),
        ("Chamfer-RMSE", info["chamfer_rmse"]),
        ("--- completeness 方向 (网格采样->参考, 点到点) ---", ""),
        ("  mean", stat_m2r["mean"]),
        ("  median", stat_m2r["median"]),
        ("  RMSE", stat_m2r["rmse"]),
        ("  P90", stat_m2r["p90"]),
        ("--- accuracy 方向 (参考->网格, 点到面) ---", ""),
        ("  mean", stat_r2m["mean"]),
        ("  median", stat_r2m["median"]),
        ("  RMSE", stat_r2m["rmse"]),
        ("  P90", stat_r2m["p90"]),
        ("场景尺度(相机中心包围盒对角线)", float(scene_scale)),
    ]
    for ratio in tau_ratios:
        d = info["fscore"][f"tau_{ratio}"]
        txt_kvs.append((f"F-score@τ={ratio} (τ_abs={d['tau_abs']:.5f})",
                        f"P={d['precision']:.4f} R={d['recall']:.4f} F={d['fscore']:.4f}"))
    return info, txt_kvs


def main():
    ap = argparse.ArgumentParser(description="M2 几何指标: 双向点到面距离 + Chamfer + F-score@τ")
    ap.add_argument("--mesh", required=True, help="被评网格 (.ply/.obj)")
    ap.add_argument("--ref_a", default=None, help="参考 A: 3DGS 高斯中心 point_cloud.ply")
    ap.add_argument("--ref_b_colmap", default=None,
                    help="参考 B: COLMAP sparse/0 目录 或 points3D.bin/.txt")
    ap.add_argument("--cameras_json", default=None,
                    help="3DGS 输出的 cameras.json, 用于场景尺度与裁剪 bbox (相机中心包围盒)")
    ap.add_argument("--scene_scale", type=float, default=None,
                    help="手动指定场景尺度(对角线); 若给出则不需要 cameras_json")
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--tag", default="基线", help="输出文件名标签, 如 基线 / 改动_tau0.02")
    ap.add_argument("--n_sample", type=int, default=1_000_000, help="网格表面采样点数")
    ap.add_argument("--fg_bbox_factor", type=float, default=1.0,
                    help="裁剪 bbox = 相机中心包围盒 * 此因子 (以中心缩放)。<=0 表示不裁剪")
    ap.add_argument("--tau_ratios", default="0.005,0.01,0.02", help="F-score 的 τ 比例, 逗号分隔")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--repo_root", default=ec.DEFAULT_REPO_ROOT)
    ap.add_argument("--log", default=ec.DEFAULT_EXEC_LOG)
    args = ap.parse_args()

    t0 = __import__("time").time()
    ec.set_seed(args.seed)
    tau_ratios = [float(x) for x in args.tau_ratios.split(",") if x.strip()]

    mesh = ec.load_mesh_o3d(args.mesh, clean=True)
    n_v, n_f = len(mesh.vertices), len(mesh.triangles)

    # 场景尺度 + 裁剪 bbox
    crop_bbox = None
    scene_scale = args.scene_scale
    scale_info = None
    if args.cameras_json:
        centers = ec.camera_centers_from_cameras_json(args.cameras_json)
        scale_info = ec.scene_scale_from_centers(centers)
        if scene_scale is None:
            scene_scale = scale_info["diagonal"]
        if args.fg_bbox_factor > 0:
            mbb = mesh.get_axis_aligned_bounding_box()
            crop_bbox = ec.robust_crop_bbox(
                scale_info["aabb_min"], scale_info["aabb_max"], args.fg_bbox_factor,
                mesh_min=np.asarray(mbb.min_bound), mesh_max=np.asarray(mbb.max_bound),
                diag=scale_info["diagonal"])
    if scene_scale is None:
        # 兜底: 用网格自身包围盒对角线
        bb = mesh.get_axis_aligned_bounding_box()
        scene_scale = float(np.linalg.norm(np.asarray(bb.max_bound) - np.asarray(bb.min_bound)))

    json_obj = {
        "tag": args.tag,
        "mesh_path": os.path.abspath(args.mesh),
        "mesh_vertices": n_v,
        "mesh_faces": n_f,
        "n_sample": args.n_sample,
        "seed": args.seed,
        "fg_bbox_factor": args.fg_bbox_factor,
        "tau_ratios": tau_ratios,
        "scene_scale_diagonal": float(scene_scale),
        "scene_scale_source": ("cameras_json" if args.cameras_json else
                               ("manual" if args.scene_scale else "mesh_bbox_fallback")),
        "camera_bbox": scale_info,
        "crop_bbox": ({"min": crop_bbox[0].tolist(), "max": crop_bbox[1].tolist()}
                      if crop_bbox is not None else None),
        "references": {},
    }

    txt_sections = [("总体", [
        ("标签", args.tag),
        ("网格", os.path.basename(args.mesh)),
        ("网格顶点数", n_v),
        ("网格面数", n_f),
        ("场景尺度(对角线)", float(scene_scale)),
        ("场景尺度来源", json_obj["scene_scale_source"]),
        ("裁剪 bbox 因子", args.fg_bbox_factor),
        ("采样点数", args.n_sample),
        ("seed", args.seed),
    ])]

    refs = []
    if args.ref_a:
        refs.append(("参考A_3DGS高斯中心", ec.load_points_ply(args.ref_a)))
    if args.ref_b_colmap:
        refs.append(("参考B_COLMAP稀疏点", _read_colmap_points(args.ref_b_colmap, args.repo_root)))
    if not refs:
        print("[警告] 未提供任何参考点云 (--ref_a / --ref_b_colmap), 只输出网格基本信息。")

    for ref_name, ref_pts in refs:
        info, kvs = eval_one_reference(mesh, ref_pts, ref_name, scene_scale,
                                       tau_ratios, args.n_sample, args.seed, crop_bbox)
        json_obj["references"][ref_name] = info
        txt_sections.append((ref_name, kvs))

    elapsed = __import__("time").time() - t0
    json_obj["elapsed_sec"] = elapsed
    txt_sections.append(("耗时", [("秒", elapsed)]))

    basename = f"几何指标_{args.tag}"
    jp, tp = ec.write_report(args.out_dir, basename, json_obj,
                             f"M2 几何指标 — {args.tag}", txt_sections)
    ec.log_exec(f"M2 几何指标 完成 tag={args.tag} mesh={os.path.basename(args.mesh)} "
                f"refs={[r[0] for r in refs]} -> {jp}", args.log)
    print(f"[M2] 写出 {jp}\n[M2] 写出 {tp}")


if __name__ == "__main__":
    main()
