#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
τ 剔除率曲线（filter-only；正式化自 scratchpad/tau_curve_2c.py）。

忠实复现 coarse_mesh.py 的「模型加载 + drop_low_opacity 剪枝」，用**已落盘的表面采样点**
（`--surface_points_ply`，即某次提取产出的 `表面点_剔点前.ply`，各 τ 提取逐点相同）作为输入，
一次性渲染 M 张参考相机深度图后，对多个 τ 复用 `accumulate_votes` 投票，输出剔除率随 τ 变化曲线。

设计（相对 scratchpad 版）：
  - 表面点从 ply 加载（而非在本脚本内重跑表面提取）——保证与全流程提取**逐点一致**（explorer==extraction），
    避免重复一段脆弱的表面提取代码。故本脚本在 03 流程里**在首次提取之后**运行（该次提取已产出 ply）。
  - 深度图渲染、参考相机抽样、投票均直接 import repo 改动模块 `mv_consistency_filter` 的公共函数，与提取内部完全一致。

不改 repo/SuGaR；只读输入；产物写 `-o` 目录（json/txt/png，中文键）。

用法示例:
  python scripts/mv_tau_curve.py -s data/tandt/truck -c outputs/基线_truck/3dgs_7k -i 7000 \
      -m outputs/基线_truck/coarse/sugarcoarse_3Dgs7000_densityestim02_sdfnorm02/15000.pt \
      --surface_points_ply outputs/改动_truck/改动_τ0.02/表面点_剔点前.ply \
      --taus 0.005,0.01,0.02,0.05,0.10,0.20 -l 0.3 \
      --mv_min_consistent 2 --mv_max_conflict 1 --mv_n_ref_cams 30 --mv_n_votes 0 --mv_seed 0 \
      -o outputs/改动_truck/τ曲线 --gpu 0
"""
import argparse
import os
import sys
import json
import time
import random

WORKDIR = os.environ.get('SUGAR_ROOT', '/scratch/e1351071/zju_test_test')
REPO = os.path.join(WORKDIR, 'repo', 'SuGaR')


def str2bool(v):
    if isinstance(v, bool):
        return v
    return str(v).lower() in ('true', '1', 'yes', 'y', 't')


def main():
    p = argparse.ArgumentParser(description='τ 剔除率曲线 (filter-only)。')
    p.add_argument('-s', '--scene_path', type=str, required=True)
    p.add_argument('-c', '--checkpoint_path', type=str, required=True, help='3DGS 输出目录')
    p.add_argument('-i', '--iteration_to_load', type=int, default=7000)
    p.add_argument('-m', '--coarse_model_path', type=str, required=True, help='coarse .pt 完整路径')
    p.add_argument('--surface_points_ply', type=str, required=True, help='表面点_剔点前.ply（某次提取产出）')
    p.add_argument('--taus', type=str, default='0.005,0.01,0.02,0.05,0.10,0.20')
    p.add_argument('-l', '--surface_level', type=float, default=0.3, help='仅用于统计标注')
    p.add_argument('--mv_min_consistent', type=int, default=2)
    p.add_argument('--mv_max_conflict', type=int, default=1)
    p.add_argument('--mv_n_ref_cams', type=int, default=30)
    p.add_argument('--mv_n_votes', type=int, default=0)
    p.add_argument('--mv_seed', type=int, default=0)
    p.add_argument('-o', '--out_dir', type=str, required=True)
    p.add_argument('--gpu', type=int, default=0)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--eval', type=str2bool, default=True)
    args = p.parse_args()

    scene_path = os.path.abspath(args.scene_path)
    checkpoint_path = os.path.abspath(args.checkpoint_path)
    if not checkpoint_path.endswith(os.sep):
        checkpoint_path += os.sep
    coarse_model_path = os.path.abspath(args.coarse_model_path)
    surface_ply = os.path.abspath(args.surface_points_ply)
    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    taus = [float(x) for x in args.taus.split(',') if x.strip()]

    sys.path.insert(0, os.path.join(REPO, 'gaussian_splatting'))
    sys.path.insert(0, REPO)
    os.chdir(REPO)

    import numpy as np
    import torch
    seed = int(args.seed)
    os.environ.setdefault('PYTHONHASHSEED', str(seed))
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
    torch.cuda.set_device(args.gpu)

    import open3d as o3d
    from sugar_scene.gs_model import GaussianSplattingWrapper
    from sugar_scene.sugar_model import SuGaR
    from sugar_utils.spherical_harmonics import SH2RGB
    from sugar_extractors.mv_consistency_filter import (
        sample_reference_cameras, accumulate_votes, compute_keep_mask,
    )

    t0 = time.time()
    print('[tau_curve] 加载 3DGS 模型 ...', flush=True)
    nerfmodel = GaussianSplattingWrapper(
        source_path=scene_path, output_path=checkpoint_path,
        iteration_to_load=args.iteration_to_load, load_gt_images=False,
        eval_split=args.eval, eval_split_interval=8,
    )
    n_cameras = len(nerfmodel.training_cameras)
    print('[tau_curve] 训练相机数 =', n_cameras, flush=True)

    print('[tau_curve] 加载 coarse SuGaR 模型 ...', flush=True)
    checkpoint = torch.load(coarse_model_path, map_location=nerfmodel.device)
    colors = SH2RGB(checkpoint['state_dict']['_sh_coordinates_dc'][:, 0, :])
    sugar = SuGaR(
        nerfmodel=nerfmodel, points=checkpoint['state_dict']['_points'], colors=colors,
        initialize=True, sh_levels=nerfmodel.gaussians.active_sh_degree + 1,
        keep_track_of_knn=True, knn_to_track=16, beta_mode='average',
        primitive_types='diamond', surface_mesh_to_bind=None,
    )
    sugar.load_state_dict(checkpoint['state_dict'])
    sugar.eval()
    n_before = sugar.n_points
    with torch.no_grad():
        sugar.drop_low_opacity_points(0.5)  # coarse_mesh.py 硬编码 low_opacity_gaussian_pruning_threshold=0.5
    n_after = sugar.n_points
    print('[tau_curve] 剪枝 %d -> %d 高斯; image_hw=(%d,%d)'
          % (n_before, n_after, sugar.image_height, sugar.image_width), flush=True)

    # ---- 加载表面点（与全流程提取逐点一致）----
    pcd = o3d.io.read_point_cloud(surface_ply)
    pts_np = np.asarray(pcd.points, dtype=np.float32)
    points = torch.from_numpy(pts_np).to(sugar.device).float()
    N = int(points.shape[0])
    print('[tau_curve] 表面点 N =', N, '(from %s)' % surface_ply, flush=True)

    # ---- 抽参考相机 + 预渲染 M 张深度图（与 multiview_depth_consistency_filter 同逻辑）----
    ref_idx = sample_reference_cameras(n_cameras, args.mv_n_ref_cams, args.mv_seed)
    M = len(ref_idx)
    print('[tau_curve] 参考相机 (M=%d, seed=%d):' % (M, args.mv_seed), ref_idx, flush=True)
    cameras = nerfmodel.training_cameras
    t_render = time.time()
    depth_maps, ref_cameras, znear_list = [], [], []
    with torch.no_grad():
        for k, cam_idx in enumerate(ref_idx):
            depth_img, _ = sugar.render_depth_and_normal(nerf_cameras=cameras, camera_indices=cam_idx)
            depth_maps.append(depth_img.detach().to('cpu'))
            cam = cameras.p3d_cameras[cam_idx]
            ref_cameras.append(cam)
            znear_list.append(float(cam.znear) if not torch.is_tensor(cam.znear)
                              else float(cam.znear.reshape(-1)[0]))
    render_sec = time.time() - t_render
    print('[tau_curve] 渲染 %d 张深度图 %.2fs' % (M, render_sec), flush=True)

    # ---- 逐 τ 投票 ----
    rows = []
    n_never = None
    with torch.no_grad():
        for tau in taus:
            t_v = time.time()
            cons, conf, valid = accumulate_votes(
                points=points, ref_cameras=ref_cameras, depth_maps=depth_maps,
                znear_list=znear_list, tau=tau,
                depth_sampler=sugar.get_points_depth_in_depth_map,
                n_votes=args.mv_n_votes, seed=args.mv_seed,
                image_hw=(sugar.image_height, sugar.image_width), device=sugar.device,
            )
            keep = compute_keep_mask(cons, conf, args.mv_min_consistent, args.mv_max_conflict)
            n_kept = int(keep.sum().item())
            n_removed = N - n_kept
            rate = float(n_removed) / N if N > 0 else 0.0
            if n_never is None:
                n_never = int((valid == 0).sum().item())  # τ 无关, 只算一次
            rows.append({'tau': float(tau), '剔点后点数': n_kept, '剔除点数': n_removed, '剔除率': rate})
            print('[tau_curve] τ=%-6s kept=%d removed=%d 剔除率=%.4f (%.2fs)'
                  % (tau, n_kept, n_removed, rate, time.time() - t_v), flush=True)

    rates = [r['剔除率'] for r in rows]
    monotonic = all(rates[i] >= rates[i + 1] for i in range(len(rates) - 1))

    result = {
        'stage': 'τ 剔除率曲线 (filter-only)',
        'surface_points_ply': surface_ply,
        'surface_level': args.surface_level,
        'N': N, 'n_gaussians_pruned': int(n_after), 'n_gaussians_before': int(n_before),
        'image_hw': [int(sugar.image_height), int(sugar.image_width)],
        'n_ref_cams': M, 'n_votes': args.mv_n_votes, 'mv_seed': args.mv_seed,
        'min_consistent': args.mv_min_consistent, 'max_conflict': args.mv_max_conflict,
        'ref_camera_indices': list(ref_idx),
        'n_never_in_view': n_never,
        'render_sec': round(render_sec, 3),
        '单调递减': bool(monotonic),
        'rows': rows,
    }
    # 落盘 json
    with open(os.path.join(out_dir, '剔除率曲线.json'), 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    # 落盘 txt (中文键)
    lines = ['τ 剔除率曲线 (filter-only)', '=' * 40, '']
    lines.append('表面点数 N = %d (%s)' % (N, surface_ply))
    lines.append('剪枝高斯: %d -> %d ; image_hw=(%d,%d)' % (n_before, n_after, sugar.image_height, sugar.image_width))
    lines.append('参考相机 (M=%d, seed=%d): %s' % (M, args.mv_seed, ref_idx))
    lines.append('n_never_in_view = %d (%.2f%%, 各 τ 一致)' % (n_never, 100.0 * n_never / N if N else 0))
    lines.append('保留规则: 一致票 >= %d 且 空域冲突票 <= %d' % (args.mv_min_consistent, args.mv_max_conflict))
    lines.append('')
    lines.append('%-8s %-14s %-14s %-10s' % ('τ', '剔点后点数', '剔除点数', '剔除率'))
    for r in rows:
        lines.append('%-8s %-14d %-14d %.4f' % (r['tau'], r['剔点后点数'], r['剔除点数'], r['剔除率']))
    lines.append('')
    lines.append('单调递减 = %s' % ('是' if monotonic else '否'))
    with open(os.path.join(out_dir, '剔除率曲线.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    # 落盘 png
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        try:
            sys.path.insert(0, os.path.join(WORKDIR, 'scripts', 'eval'))
            import eval_common as ec
            ec.setup_cjk_font()
        except Exception:
            pass
        fig, ax = plt.subplots(figsize=(6, 4), dpi=125)
        ax.plot([r['tau'] for r in rows], [r['剔除率'] for r in rows], 'o-', color='#c0392b')
        ax.set_xlabel('τ (相对深度容差)'); ax.set_ylabel('剔除率')
        ax.set_title('剔除率随 τ 变化 (k=%d v=%d M=%d)' % (args.mv_min_consistent, args.mv_max_conflict, M))
        ax.grid(True, alpha=0.3)
        for r in rows:
            ax.annotate('%.3f' % r['剔除率'], (r['tau'], r['剔除率']), fontsize=7,
                        textcoords='offset points', xytext=(0, 6), ha='center')
        fig.tight_layout()
        fig.savefig(os.path.join(out_dir, '剔除率_随τ变化.png')); plt.close(fig)
    except Exception as e:
        print('[tau_curve] png 生成跳过:', e)

    print('[tau_curve] DONE. 单调递减=%s 总耗时 %.1fs -> %s'
          % ('是' if monotonic else '否', time.time() - t0, out_dir), flush=True)


if __name__ == '__main__':
    main()
