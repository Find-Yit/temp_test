#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
改动提取 runner（正式化自 scratchpad/run_extract_repo.py）——驱动 **repo 改动版**
`sugar_extractors/coarse_mesh.py::extract_mesh_from_coarse_sugar`（含 `--mv_*` 多视角深度一致性剔点），
透传全部 mv_* 参数。与 `scripts/run_extract_mesh.py`（基线用、import 副本 coarse_mesh_savepts）区别：
  - 本文件 import **repo 的 coarse_mesh.py**（阶段2a 改动已在其中），走剔点主流程；
  - 用于 τ 扫描的三次 mv_filter=True 提取（阶段2c）。
共同点：同 seeding（torch/numpy/random/cuda/open3d seed）、同自动补 `-c` 尾斜杠。
效果等同于「在 repo/SuGaR 内 `python extract_mesh.py ... --mv_filter True ...`」，但可从工作目录调用、便于计时封装。

用法示例（工作目录下运行）:
  python scripts/run_extract_repo.py -s data/tandt/truck -c outputs/基线_truck/3dgs_7k -i 7000 \
      -m outputs/基线_truck/coarse/sugarcoarse_3Dgs7000_densityestim02_sdfnorm02/15000.pt \
      -l 0.3 -d 1000000 -o outputs/改动_truck/改动_τ0.02 \
      --mv_filter True --mv_tau 0.02 --mv_min_consistent 2 --mv_max_conflict 1 \
      --mv_n_ref_cams 30 --mv_n_votes 0 --mv_seed 0 --seed 0 --eval True
"""
import argparse
import os
import sys
import random

WORKDIR = os.environ.get('SUGAR_ROOT', '/scratch/e1351071/zju_test_test')
REPO = os.path.join(WORKDIR, 'repo', 'SuGaR')


class AttrDict(dict):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.__dict__ = self


def str2bool(v):
    if isinstance(v, bool):
        return v
    return str(v).lower() in ('true', '1', 'yes', 'y', 't')


def main():
    p = argparse.ArgumentParser(description='改动提取 runner（repo coarse_mesh + mv_filter，no repo edit）。')
    p.add_argument('-s', '--scene_path', type=str, required=True)
    p.add_argument('-c', '--checkpoint_path', type=str, required=True, help='3DGS 输出目录')
    p.add_argument('-i', '--iteration_to_load', type=int, default=7000)
    p.add_argument('-m', '--coarse_model_path', type=str, required=True, help='coarse .pt 完整路径')
    p.add_argument('-l', '--surface_level', type=float, default=0.3)
    p.add_argument('-d', '--decimation_target', type=int, default=1000000, help='目标顶点数')
    p.add_argument('--project_mesh_on_surface_points', type=str2bool, default=True)
    p.add_argument('-o', '--mesh_output_dir', type=str, default=None)
    p.add_argument('-b', '--bboxmin', type=str, default=None)
    p.add_argument('-B', '--bboxmax', type=str, default=None)
    p.add_argument('--center_bbox', type=str2bool, default=True)
    p.add_argument('--gpu', type=int, default=0)
    p.add_argument('--eval', type=str2bool, default=True)
    p.add_argument('--use_centers_to_extract_mesh', type=str2bool, default=False)
    p.add_argument('--use_marching_cubes', type=str2bool, default=False)
    p.add_argument('--use_vanilla_3dgs', type=str2bool, default=False)
    # ----- mv_* 多视角深度一致性剔点参数（透传给 repo coarse_mesh 的 _cfg） -----
    p.add_argument('--mv_filter', type=str2bool, default=True)
    p.add_argument('--mv_tau', type=float, default=0.02)
    p.add_argument('--mv_min_consistent', type=int, default=2)
    p.add_argument('--mv_max_conflict', type=int, default=1)
    p.add_argument('--mv_n_ref_cams', type=int, default=30)
    p.add_argument('--mv_n_votes', type=int, default=0)
    p.add_argument('--mv_seed', type=int, default=0)
    p.add_argument('--seed', type=int, default=0)
    args = p.parse_args()

    scene_path = os.path.abspath(args.scene_path)
    checkpoint_path = os.path.abspath(args.checkpoint_path)
    if not checkpoint_path.endswith(os.sep):
        checkpoint_path += os.sep  # SuGaR cameras.py 用 gs_output_path + 'cameras.json' 拼接, 需尾斜杠
    coarse_model_path = os.path.abspath(args.coarse_model_path)
    mesh_output_dir = os.path.abspath(args.mesh_output_dir) if args.mesh_output_dir else None

    sys.path.insert(0, os.path.join(REPO, 'gaussian_splatting'))
    sys.path.insert(0, REPO)
    os.chdir(REPO)

    import numpy as np
    import torch
    seed = int(args.seed)
    os.environ.setdefault('PYTHONHASHSEED', str(seed))
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    try:
        import open3d as o3d
        o3d.utility.random.seed(seed)
    except Exception as e:
        print('[run_extract_repo] open3d seed skip:', e)

    from sugar_extractors.coarse_mesh import extract_mesh_from_coarse_sugar as extract_fn

    call_args = AttrDict({
        'scene_path': scene_path,
        'checkpoint_path': checkpoint_path,
        'iteration_to_load': args.iteration_to_load,
        'coarse_model_path': coarse_model_path,
        'surface_level': args.surface_level,
        'decimation_target': args.decimation_target,
        'project_mesh_on_surface_points': args.project_mesh_on_surface_points,
        'mesh_output_dir': mesh_output_dir,
        'bboxmin': args.bboxmin,
        'bboxmax': args.bboxmax,
        'center_bbox': args.center_bbox,
        'gpu': args.gpu,
        'eval': args.eval,
        'use_centers_to_extract_mesh': args.use_centers_to_extract_mesh,
        'use_marching_cubes': args.use_marching_cubes,
        'use_vanilla_3dgs': args.use_vanilla_3dgs,
        # mv_* 透传
        'mv_filter': args.mv_filter,
        'mv_tau': args.mv_tau,
        'mv_min_consistent': args.mv_min_consistent,
        'mv_max_conflict': args.mv_max_conflict,
        'mv_n_ref_cams': args.mv_n_ref_cams,
        'mv_n_votes': args.mv_n_votes,
        'mv_seed': args.mv_seed,
    })
    print('[run_extract_repo] scene=%s' % scene_path)
    print('[run_extract_repo] coarse .pt=%s' % coarse_model_path)
    print('[run_extract_repo] surface_level=%.3f decimation_target=%d' % (args.surface_level, args.decimation_target))
    print('[run_extract_repo] mv_filter=%s mv_tau=%s M=%d K=%d seed=%d'
          % (str(args.mv_filter), str(args.mv_tau), args.mv_n_ref_cams, args.mv_n_votes, seed))
    out = extract_fn(call_args)
    print('[run_extract_repo] DONE. mesh path(s) =', out)


if __name__ == '__main__':
    main()
