#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M1 渲染指标 — 测试视角 PSNR / SSIM / LPIPS。

评测对象:
  (a) vanilla 3DGS (7k ckpt): nerfmodel.render_image(...)
  (b) coarse SuGaR (.pt):     SuGaR(..., surface_mesh_to_bind=None)
                              .render_image_gaussian_rasterizer(...)
GT 用 nerfmodel.get_test_gt_image(i)。

测试划分: llffhold=8 (GaussianSplattingWrapper eval_split=True, interval=8, 即 idx%8==0)。
复用 gaussian_splatting 的 psnr/ssim/lpipsPyTorch; 只 import, 不改仓库。
仓库根目录 metrics.py 不可直接用 (硬编码 refined + 30k/7k 双 ckpt), 故本脚本自写。

用法:
  python m1_render_metrics.py \
    --source_path data/tandt/truck \
    --gs_output outputs/基线_truck/3dgs_7k \
    --iteration 7000 \
    --coarse_pt outputs/基线_truck/coarse/sugarcoarse_.../XXXX.pt \
    --out_dir report/渲染 --tag 基线 --save_renders
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


def main():
    ap = argparse.ArgumentParser(description="M1 渲染指标 (PSNR/SSIM/LPIPS)")
    ap.add_argument("--source_path", required=True, help="COLMAP 源数据目录, 如 data/tandt/truck")
    ap.add_argument("--gs_output", required=True, help="3DGS 输出目录 (含 cameras.json 与 point_cloud/)")
    ap.add_argument("--iteration", type=int, default=7000, help="加载的 3DGS 迭代数")
    ap.add_argument("--coarse_pt", default=None, help="coarse SuGaR .pt (可选; 不给则只评 3DGS)")
    ap.add_argument("--eval_interval", type=int, default=8, help="llffhold 间隔")
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--tag", default="基线")
    ap.add_argument("--lpips", type=int, default=1, help="1=计算 LPIPS, 0=跳过")
    ap.add_argument("--lpips_backend", default="lpipsPyTorch",
                    choices=["lpipsPyTorch", "lpips"], help="LPIPS 后端")
    ap.add_argument("--cache_dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache"),
                    help="LPIPS/torchvision 权重缓存目录")
    ap.add_argument("--save_renders", action="store_true", help="保存渲染图供 M6 拼图")
    ap.add_argument("--save_dir", default=None, help="渲染图保存目录 (默认 out_dir/渲染图_tag)")
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--repo_root", default=ec.DEFAULT_REPO_ROOT)
    ap.add_argument("--log", default=ec.DEFAULT_EXEC_LOG)
    args = ap.parse_args()

    t0 = time.time()
    ec.set_seed(args.seed)
    ec.setup_sugar_path(args.repo_root)

    import torch
    os.makedirs(args.cache_dir, exist_ok=True)
    torch.hub.set_dir(args.cache_dir)  # LPIPS 与 vgg16 权重缓存到本目录
    torch.cuda.set_device(args.gpu)

    from gaussian_splatting.utils.loss_utils import ssim as ssim_fn
    from gaussian_splatting.utils.image_utils import psnr as psnr_fn
    from sugar_scene.gs_model import GaussianSplattingWrapper
    from sugar_scene.sugar_model import SuGaR
    from sugar_utils.spherical_harmonics import SH2RGB

    # LPIPS 准备
    lpips_crit = None
    if args.lpips:
        if args.lpips_backend == "lpipsPyTorch":
            from gaussian_splatting.lpipsPyTorch.modules.lpips import LPIPS
            lpips_crit = LPIPS("vgg", "0.1").cuda().eval()
            def lpips_call(pred, gt):
                with torch.no_grad():
                    return lpips_crit(pred, gt).item()
        else:
            import lpips as lpips_pkg
            lpips_crit = lpips_pkg.LPIPS(net="vgg").cuda().eval()
            def lpips_call(pred, gt):
                with torch.no_grad():
                    # pip lpips 期望 [-1,1]
                    return lpips_crit(pred * 2 - 1, gt * 2 - 1).item()
    else:
        def lpips_call(pred, gt):
            return float("nan")

    ec.log_exec(f"M1 渲染指标 开始 tag={args.tag} gs_output={args.gs_output} "
                f"iter={args.iteration} coarse={'有' if args.coarse_pt else '无'}", args.log)

    # 加载 3DGS 模型 (提供相机 / GT / nerfmodel 包装)
    nerfmodel = GaussianSplattingWrapper(
        source_path=os.path.abspath(args.source_path),
        output_path=_ensure_slash(os.path.abspath(args.gs_output)),
        iteration_to_load=args.iteration,
        load_gt_images=True,
        eval_split=True,
        eval_split_interval=args.eval_interval,
    )
    test_cams = nerfmodel.test_cameras
    n_test = len(test_cams)
    sh_deg = nerfmodel.gaussians.active_sh_degree
    H, W = nerfmodel.image_height, nerfmodel.image_width

    save_dir = args.save_dir or os.path.join(args.out_dir, f"渲染图_{args.tag}")
    if args.save_renders:
        os.makedirs(save_dir, exist_ok=True)

    def save_img(t, path):
        import torchvision
        torchvision.utils.save_image(t, path)

    # ---------- (a) vanilla 3DGS ----------
    rows = []
    gs_psnr, gs_ssim, gs_lpips = [], [], []
    with torch.no_grad():
        for i in range(n_test):
            gt = nerfmodel.get_test_gt_image(i, to_cuda=True).permute(2, 0, 1).unsqueeze(0)
            pred = nerfmodel.render_image(nerf_cameras=test_cams, camera_indices=i
                                          ).clamp(0, 1).permute(2, 0, 1).unsqueeze(0)
            p = psnr_fn(pred, gt).mean().item()
            s = ssim_fn(pred, gt).item()
            l = lpips_call(pred, gt)
            gs_psnr.append(p); gs_ssim.append(s); gs_lpips.append(l)
            name = test_cams.gs_cameras[i].image_name
            rows.append({"view": i, "image": name, "3dgs_psnr": p, "3dgs_ssim": s, "3dgs_lpips": l})
            if args.save_renders:
                save_img(gt, os.path.join(save_dir, f"GT_{i:03d}_{name}.png"))
                save_img(pred, os.path.join(save_dir, f"3DGS_{i:03d}_{name}.png"))

    result = {
        "tag": args.tag,
        "source_path": os.path.abspath(args.source_path),
        "gs_output": os.path.abspath(args.gs_output),
        "iteration": args.iteration,
        "eval_interval": args.eval_interval,
        "n_test_views": n_test,
        "image_hw": [int(H), int(W)],
        "sh_degree": int(sh_deg),
        "lpips_backend": args.lpips_backend if args.lpips else "none",
        "seed": args.seed,
        "note_nondeterminism": "CUDA 光栅化 atomicAdd 非确定; SuGaR trainer 无 seed -> 存在单次运行差异",
        "vanilla_3dgs": {
            "psnr": float(np.mean(gs_psnr)),
            "ssim": float(np.mean(gs_ssim)),
            "lpips": float(np.nanmean(gs_lpips)),
        },
    }

    # ---------- (b) coarse SuGaR ----------
    if args.coarse_pt:
        checkpoint = torch.load(args.coarse_pt, map_location=nerfmodel.device)
        colors = SH2RGB(checkpoint["state_dict"]["_sh_coordinates_dc"][:, 0, :])
        sugar = SuGaR(
            nerfmodel=nerfmodel,
            points=checkpoint["state_dict"]["_points"],
            colors=colors,
            initialize=True,
            sh_levels=sh_deg + 1,
            keep_track_of_knn=True,
            knn_to_track=16,
            beta_mode="average",
            primitive_types="diamond",
            surface_mesh_to_bind=None,
        )
        sugar.load_state_dict(checkpoint["state_dict"])
        sugar.eval()

        su_psnr, su_ssim, su_lpips = [], [], []
        with torch.no_grad():
            for i in range(n_test):
                gt = nerfmodel.get_test_gt_image(i, to_cuda=True).permute(2, 0, 1).unsqueeze(0)
                pred = sugar.render_image_gaussian_rasterizer(
                    nerf_cameras=test_cams, camera_indices=i, verbose=False,
                    bg_color=None, sh_deg=sh_deg, compute_color_in_rasterizer=True,
                ).clamp(0, 1).permute(2, 0, 1).unsqueeze(0)
                p = psnr_fn(pred, gt).mean().item()
                s = ssim_fn(pred, gt).item()
                l = lpips_call(pred, gt)
                su_psnr.append(p); su_ssim.append(s); su_lpips.append(l)
                rows[i]["sugar_psnr"] = p; rows[i]["sugar_ssim"] = s; rows[i]["sugar_lpips"] = l
                if args.save_renders:
                    save_img(pred, os.path.join(save_dir, f"coarseSuGaR_{i:03d}_{test_cams.gs_cameras[i].image_name}.png"))
        result["coarse_pt"] = os.path.abspath(args.coarse_pt)
        result["coarse_sugar"] = {
            "psnr": float(np.mean(su_psnr)),
            "ssim": float(np.mean(su_ssim)),
            "lpips": float(np.nanmean(su_lpips)),
        }
        result["n_coarse_gaussians"] = int(checkpoint["state_dict"]["_points"].shape[0])

    result["elapsed_sec"] = time.time() - t0

    # 落盘: 每视角 CSV
    csv_path = os.path.join(args.out_dir, f"渲染指标_逐视角_{args.tag}.csv")
    header = ["view", "image", "3dgs_psnr", "3dgs_ssim", "3dgs_lpips"]
    if args.coarse_pt:
        header += ["sugar_psnr", "sugar_ssim", "sugar_lpips"]
    csv_rows = [[r.get(h, "") for h in header] for r in rows]
    ec.write_csv(csv_path, header, csv_rows)
    result["per_view_csv"] = os.path.abspath(csv_path)
    if args.save_renders:
        result["render_dir"] = os.path.abspath(save_dir)

    # 中文 txt
    txt_sections = [("总体", [
        ("标签", args.tag),
        ("测试视角数", n_test),
        ("图像高x宽", f"{H}x{W}"),
        ("加载迭代", args.iteration),
        ("测试划分间隔(llffhold)", args.eval_interval),
        ("SH 阶数", int(sh_deg)),
        ("LPIPS 后端", result["lpips_backend"]),
        ("seed", args.seed),
    ])]
    txt_sections.append(("vanilla 3DGS (7k)", [
        ("PSNR", result["vanilla_3dgs"]["psnr"]),
        ("SSIM", result["vanilla_3dgs"]["ssim"]),
        ("LPIPS(vgg)", result["vanilla_3dgs"]["lpips"]),
    ]))
    if args.coarse_pt:
        txt_sections.append(("coarse SuGaR", [
            ("高斯数", result["n_coarse_gaussians"]),
            ("PSNR", result["coarse_sugar"]["psnr"]),
            ("SSIM", result["coarse_sugar"]["ssim"]),
            ("LPIPS(vgg)", result["coarse_sugar"]["lpips"]),
        ]))
    txt_sections.append(("产物", [
        ("逐视角 CSV", os.path.basename(csv_path)),
        ("渲染图目录", os.path.basename(save_dir) if args.save_renders else "未保存"),
        ("耗时(秒)", result["elapsed_sec"]),
    ]))

    basename = f"渲染指标_{args.tag}"
    jp, tp = ec.write_report(args.out_dir, basename, result,
                             f"M1 渲染指标 — {args.tag}", txt_sections)
    ec.log_exec(f"M1 渲染指标 完成 tag={args.tag} 3DGS_PSNR={result['vanilla_3dgs']['psnr']:.3f}"
                + (f" coarse_PSNR={result['coarse_sugar']['psnr']:.3f}" if args.coarse_pt else "")
                + f" -> {jp}", args.log)
    print(f"[M1] 写出 {jp}\n[M1] 写出 {tp}\n[M1] 写出 {csv_path}")


if __name__ == "__main__":
    main()
