#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M4 覆盖指标 — 网格渲染覆盖率 与 mesh 漏洞率。

定义:
  渲染覆盖率  = pytorch3d 光栅化 mesh 到测试视角后, pix_to_face>=0 的像素占比
  3DGS 前景  = 用 override_color=白 + 黑背景渲染 vanilla 3DGS 得到累积 alpha, alpha>0.5
  漏洞率      = (3DGS 前景 且 mesh 无覆盖) 的像素数 / 3DGS 前景像素数   (主口径, 对前景取比)
               另报对全图口径。

相机来自 3DGS/SuGaR 的 CamerasWrapper (test_cameras)。只 import 仓库, 不改仓库。

用法:
  python m4_coverage.py \
    --source_path data/tandt/truck --gs_output outputs/基线_truck/3dgs_7k --iteration 7000 \
    --mesh outputs/基线_truck/mesh/xxx.ply --out_dir report/覆盖 --tag 基线
"""
import os
import sys
import time
import argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_common as ec


def _ensure_slash(p):
    return p if p.endswith("/") else p + "/"


def rasterize_mesh_coverage(p3d_mesh, p3d_camera, H, W):
    """光栅化一个 mesh 到一个相机, 返回 (H,W) bool 覆盖掩码。
    大网格默认分箱可能溢出, 失败则退回 naive (bin_size=0)。"""
    from pytorch3d.renderer import RasterizationSettings, MeshRasterizer
    import torch
    for bin_size in (None, 0):
        try:
            rs = RasterizationSettings(image_size=(int(H), int(W)), blur_radius=0.0,
                                       faces_per_pixel=1, bin_size=bin_size)
            rasterizer = MeshRasterizer(cameras=p3d_camera, raster_settings=rs)
            frags = rasterizer(p3d_mesh, cameras=p3d_camera)
            p2f = frags.pix_to_face[0, ..., 0]  # (H,W)
            return (p2f >= 0)
        except Exception as e:
            last = e
            continue
    raise last


def main():
    ap = argparse.ArgumentParser(description="M4 覆盖率 / 漏洞率")
    ap.add_argument("--source_path", required=True)
    ap.add_argument("--gs_output", required=True)
    ap.add_argument("--iteration", type=int, default=7000)
    ap.add_argument("--mesh", required=True)
    ap.add_argument("--eval_interval", type=int, default=8)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--tag", default="基线")
    ap.add_argument("--alpha_thresh", type=float, default=0.5)
    ap.add_argument("--max_views", type=int, default=0, help=">0 时只评前 N 个测试视角 (省时)")
    ap.add_argument("--save_masks", action="store_true", help="保存前几个视角的掩码可视化")
    ap.add_argument("--n_save_masks", type=int, default=3)
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--repo_root", default=ec.DEFAULT_REPO_ROOT)
    ap.add_argument("--log", default=ec.DEFAULT_EXEC_LOG)
    args = ap.parse_args()

    t0 = time.time()
    ec.set_seed(args.seed)
    ec.setup_sugar_path(args.repo_root)

    import torch
    torch.cuda.set_device(args.gpu)
    from pytorch3d.structures import Meshes
    from sugar_scene.gs_model import GaussianSplattingWrapper
    from gaussian_splatting.gaussian_renderer import render as gs_render
    import open3d as o3d

    ec.log_exec(f"M4 覆盖率 开始 tag={args.tag} mesh={os.path.basename(args.mesh)}", args.log)

    nerfmodel = GaussianSplattingWrapper(
        source_path=os.path.abspath(args.source_path),
        output_path=_ensure_slash(os.path.abspath(args.gs_output)),
        iteration_to_load=args.iteration,
        load_gt_images=False,      # M4 不需要 GT, 省显存
        eval_split=True,
        eval_split_interval=args.eval_interval,
    )
    test_cams = nerfmodel.test_cameras
    n_test = len(test_cams)
    if args.max_views and args.max_views > 0:
        n_test = min(n_test, args.max_views)
    H, W = nerfmodel.image_height, nerfmodel.image_width

    # 构造 pytorch3d mesh
    o3d_mesh = ec.load_mesh_o3d(args.mesh, clean=True)
    verts = torch.tensor(np.asarray(o3d_mesh.vertices), dtype=torch.float32, device="cuda")
    faces = torch.tensor(np.asarray(o3d_mesh.triangles), dtype=torch.int64, device="cuda")
    p3d_mesh = Meshes(verts=[verts], faces=[faces])
    n_gauss = nerfmodel.gaussians.get_xyz.shape[0]
    white = torch.ones((n_gauss, 3), device="cuda")
    black_bg = torch.zeros(3, device="cuda")

    mask_dir = os.path.join(args.out_dir, f"覆盖掩码_{args.tag}")
    if args.save_masks:
        os.makedirs(mask_dir, exist_ok=True)

    per_view = []
    cov_list, fg_list, hole_fg_list, hole_all_list, meshfg_list = [], [], [], [], []
    with torch.no_grad():
        for i in range(n_test):
            p3d_cam = test_cams.p3d_cameras[i]
            cov = rasterize_mesh_coverage(p3d_mesh, p3d_cam, H, W)  # (H,W) bool cuda

            gs_cam = test_cams.gs_cameras[i]
            pkg = gs_render(gs_cam, nerfmodel.gaussians, nerfmodel.pipeline_params,
                            bg_color=black_bg, override_color=white)
            alpha = pkg["render"][0]  # (H,W), 累积 alpha
            fg = alpha > args.alpha_thresh

            cov_f = cov.float().mean().item()
            fg_f = fg.float().mean().item()
            hole = fg & (~cov)
            n_fg = int(fg.sum().item())
            hole_fg = (int(hole.sum().item()) / n_fg) if n_fg > 0 else 0.0
            hole_all = hole.float().mean().item()
            mesh_covers_fg = (int((cov & fg).sum().item()) / n_fg) if n_fg > 0 else 0.0

            cov_list.append(cov_f); fg_list.append(fg_f)
            hole_fg_list.append(hole_fg); hole_all_list.append(hole_all)
            meshfg_list.append(mesh_covers_fg)
            per_view.append({
                "view": i, "image": gs_cam.image_name,
                "mesh_coverage": cov_f, "fg_fraction": fg_f,
                "hole_rate_over_fg": hole_fg, "hole_rate_over_all": hole_all,
                "mesh_covers_fg": mesh_covers_fg,
            })

            if args.save_masks and i < args.n_save_masks:
                _save_mask_fig(os.path.join(mask_dir, f"掩码_{i:03d}_{gs_cam.image_name}.png"),
                               cov.cpu().numpy(), fg.cpu().numpy(), hole.cpu().numpy(), i)

    result = {
        "tag": args.tag,
        "mesh_path": os.path.abspath(args.mesh),
        "gs_output": os.path.abspath(args.gs_output),
        "n_test_views": n_test,
        "image_hw": [int(H), int(W)],
        "alpha_thresh": args.alpha_thresh,
        "n_gaussians": int(n_gauss),
        "mesh_faces": int(faces.shape[0]),
        "averaged": {
            "mesh_coverage": float(np.mean(cov_list)),
            "fg_fraction": float(np.mean(fg_list)),
            "hole_rate_over_fg": float(np.mean(hole_fg_list)),
            "hole_rate_over_all": float(np.mean(hole_all_list)),
            "mesh_covers_fg": float(np.mean(meshfg_list)),
        },
        "elapsed_sec": time.time() - t0,
    }

    csv_path = os.path.join(args.out_dir, f"覆盖指标_逐视角_{args.tag}.csv")
    header = ["view", "image", "mesh_coverage", "fg_fraction",
              "hole_rate_over_fg", "hole_rate_over_all", "mesh_covers_fg"]
    ec.write_csv(csv_path, header, [[r[h] for h in header] for r in per_view])
    result["per_view_csv"] = os.path.abspath(csv_path)

    a = result["averaged"]
    txt_sections = [
        ("总体", [
            ("标签", args.tag),
            ("网格", os.path.basename(args.mesh)),
            ("网格面数", int(faces.shape[0])),
            ("测试视角数", n_test),
            ("图像高x宽", f"{H}x{W}"),
            ("alpha 阈值", args.alpha_thresh),
        ]),
        ("平均指标", [
            ("网格渲染覆盖率(占全图)", a["mesh_coverage"]),
            ("3DGS前景占比(占全图)", a["fg_fraction"]),
            ("漏洞率(前景内, 主口径)", a["hole_rate_over_fg"]),
            ("漏洞率(占全图)", a["hole_rate_over_all"]),
            ("网格覆盖前景比例", a["mesh_covers_fg"]),
        ]),
        ("产物", [("逐视角 CSV", os.path.basename(csv_path)),
                  ("掩码目录", os.path.basename(mask_dir) if args.save_masks else "未保存"),
                  ("耗时(秒)", result["elapsed_sec"])]),
    ]
    basename = f"覆盖指标_{args.tag}"
    jp, tp = ec.write_report(args.out_dir, basename, result,
                             f"M4 覆盖率/漏洞率 — {args.tag}", txt_sections)
    ec.log_exec(f"M4 覆盖率 完成 tag={args.tag} 覆盖率={a['mesh_coverage']:.4f} "
                f"漏洞率(前景)={a['hole_rate_over_fg']:.4f} -> {jp}", args.log)
    print(f"[M4] 写出 {jp}\n[M4] 写出 {tp}\n[M4] 写出 {csv_path}")


def _save_mask_fig(path, cov, fg, hole, idx):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ec.setup_cjk_font()
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    for ax, im, t in zip(axes, [cov, fg, hole],
                         ["mesh 覆盖", "3DGS 前景", "漏洞(前景∧无覆盖)"]):
        ax.imshow(im, cmap="gray")
        ax.set_title(t, fontsize=10); ax.axis("off")
    fig.suptitle(f"视角 {idx}", fontsize=11)
    fig.savefig(path, dpi=100, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
