#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成一个最小的合成 3DGS 场景 (相机 + 高斯点云 + GT 图像), 用于 M1/M4 的 GPU 冒烟测试。
不依赖真实基线, 显存占用极小 (<1GB)。

产物:
  <root>/source/images/<name>.png            GT 图像 (由高斯自身渲染, 使 M1 的 3DGS 渲染≈GT)
  <root>/gs_output/cameras.json              相机 (3DGS 约定)
  <root>/gs_output/point_cloud/iteration_<it>/point_cloud.ply
  <root>/mesh/球.ply                          与高斯团大致重合的球面 mesh (供 M4)
"""
import os
import sys
import json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import eval_common as ec
import synthetic_data as sd

C0 = 0.28209479177387814


def _write_gs_ply(path, xyz, rgb, opacity=0.9, scale=0.03, sh_degree=3):
    """写 3DGS 格式 point_cloud.ply (xyz+normals+f_dc+f_rest+opacity+scale+rot)。"""
    from plyfile import PlyData, PlyElement
    n = xyz.shape[0]
    n_rest = 3 * (sh_degree + 1) ** 2 - 3  # =45 for sh=3
    f_dc = (np.asarray(rgb, dtype=np.float64) - 0.5) / C0  # 反 SH2RGB
    f_rest = np.zeros((n, n_rest), dtype=np.float64)
    opac_raw = np.log(opacity / (1 - opacity))              # inverse_sigmoid
    scale_raw = np.log(scale)                                # get_scaling=exp
    fields = ["x", "y", "z", "nx", "ny", "nz"]
    fields += [f"f_dc_{i}" for i in range(3)]
    fields += [f"f_rest_{i}" for i in range(n_rest)]
    fields += ["opacity"]
    fields += [f"scale_{i}" for i in range(3)]
    fields += [f"rot_{i}" for i in range(4)]
    dtype = [(f, "f4") for f in fields]
    arr = np.zeros(n, dtype=dtype)
    arr["x"], arr["y"], arr["z"] = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    for i in range(3):
        arr[f"f_dc_{i}"] = f_dc[:, i]
    arr["opacity"] = opac_raw
    for i in range(3):
        arr[f"scale_{i}"] = scale_raw
    arr["rot_0"] = 1.0  # identity quaternion
    el = PlyElement.describe(arr, "vertex")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    PlyData([el]).write(path)


def build(root, n_cams=12, n_gauss=3000, iteration=7000, seed=0, render_gt=True):
    ec.set_seed(seed)
    src = os.path.join(root, "source")
    img_dir = os.path.join(src, "images")
    gs_out = os.path.join(root, "gs_output")
    pc_dir = os.path.join(gs_out, "point_cloud", f"iteration_{iteration}")
    mesh_dir = os.path.join(root, "mesh")
    for d in (img_dir, pc_dir, mesh_dir):
        os.makedirs(d, exist_ok=True)

    # 相机
    cams = sd.make_camera_ring(n=n_cams, radius=3.0, height=0.5, look_at=(0, 0, 0), seed=seed)
    W, H = cams[0]["width"], cams[0]["height"]
    json.dump(cams, open(os.path.join(gs_out, "cameras.json"), "w"))

    # 高斯: 半径 0.5 的球壳团, 颜色随位置变化
    rng = np.random.default_rng(seed)
    v = rng.normal(size=(n_gauss, 3))
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    xyz = v * 0.5 + rng.normal(scale=0.02, size=(n_gauss, 3))
    rgb = 0.5 + 0.4 * v  # [0.1,0.9] 区间的颜色
    _write_gs_ply(os.path.join(pc_dir, "point_cloud.ply"), xyz, rgb,
                  opacity=0.95, scale=0.05, sh_degree=3)

    # 供 M4 的 mesh: 与高斯团重合的球面 (r=0.5)
    mesh = sd.make_sphere_mesh(radius=0.5, resolution=20)
    import open3d as o3d
    o3d.io.write_triangle_mesh(os.path.join(mesh_dir, "球.ply"), mesh)

    # 先写占位图 (load_gs_cameras 需要 images 目录非空且扩展名可识别)
    from PIL import Image
    for c in cams:
        Image.fromarray((np.ones((H, W, 3)) * 128).astype(np.uint8)).save(
            os.path.join(img_dir, c["img_name"] + ".png"))

    # 用高斯自身渲染出 GT (使 M1 的 3DGS 渲染 ≈ GT, PSNR 应很高)
    if render_gt:
        _render_gt(src, gs_out, iteration, img_dir, cams)

    return {"source_path": src, "gs_output": gs_out, "iteration": iteration,
            "mesh": os.path.join(mesh_dir, "球.ply"), "H": H, "W": W, "n_cams": n_cams}


def _render_gt(src, gs_out, iteration, img_dir, cams):
    """用 GaussianSplattingWrapper (eval_split=False) 渲染所有相机, 覆盖为 GT。"""
    ec.setup_sugar_path()
    import torch
    import torchvision
    from sugar_scene.gs_model import GaussianSplattingWrapper
    nm = GaussianSplattingWrapper(
        source_path=os.path.abspath(src),
        output_path=os.path.abspath(gs_out) + "/",
        iteration_to_load=iteration,
        load_gt_images=True, eval_split=False)
    with torch.no_grad():
        for i in range(len(nm.cam_list)):
            img = nm.render_image(nerf_cameras=None, camera_indices=i).clamp(0, 1).permute(2, 0, 1)
            name = nm.cam_list[i].image_name
            torchvision.utils.save_image(img, os.path.join(img_dir, name + ".png"))


def build_coarse_pt(info, out_path):
    """从合成 3DGS 构造一个 coarse SuGaR .pt (格式与真实 coarse 一致), 供 M1 coarse 分支测试。"""
    ec.setup_sugar_path()
    import torch
    from sugar_scene.gs_model import GaussianSplattingWrapper
    from sugar_scene.sugar_model import SuGaR
    from sugar_utils.spherical_harmonics import SH2RGB
    nm = GaussianSplattingWrapper(
        source_path=os.path.abspath(info["source_path"]),
        output_path=os.path.abspath(info["gs_output"]) + "/",
        iteration_to_load=info["iteration"],
        load_gt_images=False, eval_split=True, eval_split_interval=8)
    pts = nm.gaussians.get_xyz.detach().float().cuda()
    colors = SH2RGB(nm.gaussians.get_features[:, 0].detach().float().cuda())
    sugar = SuGaR(nerfmodel=nm, points=pts, colors=colors, initialize=True,
                  sh_levels=nm.gaussians.active_sh_degree + 1, keep_track_of_knn=True,
                  knn_to_track=16, beta_mode="average", primitive_types="diamond",
                  surface_mesh_to_bind=None)
    with torch.no_grad():
        sugar._scales[...] = nm.gaussians._scaling.detach()
        sugar._quaternions[...] = nm.gaussians._rotation.detach()
        sugar.all_densities[...] = nm.gaussians._opacity.detach()
        sugar._sh_coordinates_dc[...] = nm.gaussians._features_dc.detach()
        sugar._sh_coordinates_rest[...] = nm.gaussians._features_rest.detach()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    sugar.save_model(out_path)
    return out_path


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.environ.get("TMPDIR", "/tmp"), "syn_gs")
    info = build(root)
    print("SYNTHETIC_GS_READY", json.dumps(info, ensure_ascii=False))
