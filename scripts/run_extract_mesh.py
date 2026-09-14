#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
阶段1 wrapper: 驱动 mesh 提取（scripts/coarse_mesh_savepts.py，即 repo coarse_mesh.py 逐字副本
+ additive：当 --surfpts_dir 非空时另存"表面采样点云"到 .ply；surfpts_dir=None 时 mesh 输出与 repo 逐字节一致）。
poisson_depth=10 / vertices_density_quantile=0.1 为 repo 硬编码默认（计划意图值），无需 flag。
-d 是 decimation_target（目标顶点数），非 poisson_depth。
用法示例（从工作目录运行）:
  python scripts/run_extract_mesh.py -s data/tandt/truck -c outputs/基线_truck/3dgs_7k -i 7000 \
      -m outputs/基线_truck/coarse/sugarcoarse_3Dgs7000_densityestim02_sdfnorm02/15000.pt \
      -l 0.3 -d 1000000 -o outputs/基线_truck/mesh --surfpts_dir outputs/基线_truck/mesh --eval True
"""
import argparse
import os
import sys
import random

WORKDIR = '/scratch/e1351071/zju_test_test'
REPO = os.path.join(WORKDIR, 'repo', 'SuGaR')
SCRIPTS = os.path.join(WORKDIR, 'scripts')


class AttrDict(dict):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.__dict__ = self


def str2bool(v):
    if isinstance(v, bool):
        return v
    return str(v).lower() in ('true', '1', 'yes', 'y', 't')


def main():
    p = argparse.ArgumentParser(description='阶段1 mesh 提取 wrapper (+表面采样点云保存, no repo edit).')
    p.add_argument('-s', '--scene_path', type=str, required=True)
    p.add_argument('-c', '--checkpoint_path', type=str, required=True, help='3DGS 输出目录')
    p.add_argument('-i', '--iteration_to_load', type=int, default=7000)
    p.add_argument('-m', '--coarse_model_path', type=str, required=True, help='coarse .pt 完整路径')
    p.add_argument('-l', '--surface_level', type=float, default=0.3)
    p.add_argument('-d', '--decimation_target', type=int, default=1000000, help='目标顶点数 (SuGaR high_poly 默认 1e6)')
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
    p.add_argument('--surfpts_dir', type=str, default=None, help='PARAM additive: 表面采样点云 .ply 保存目录')
    p.add_argument('--seed', type=int, default=0)
    args = p.parse_args()

    scene_path = os.path.abspath(args.scene_path)
    checkpoint_path = os.path.abspath(args.checkpoint_path)
    if not checkpoint_path.endswith(os.sep):
        checkpoint_path += os.sep  # SuGaR cameras.py 用 gs_output_path + 'cameras.json' 拼接, 需尾斜杠
    coarse_model_path = os.path.abspath(args.coarse_model_path)
    mesh_output_dir = os.path.abspath(args.mesh_output_dir) if args.mesh_output_dir else None
    surfpts_dir = os.path.abspath(args.surfpts_dir) if args.surfpts_dir else None

    sys.path.insert(0, os.path.join(REPO, 'gaussian_splatting'))
    sys.path.insert(0, REPO)
    sys.path.insert(0, SCRIPTS)
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
        print('[run_extract_mesh] open3d seed skip:', e)

    from coarse_mesh_savepts import extract_mesh_from_coarse_sugar as extract_fn

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
        'surfpts_dir': surfpts_dir,
    })
    print('[run_extract_mesh] scene=%s' % scene_path)
    print('[run_extract_mesh] coarse .pt=%s' % coarse_model_path)
    print('[run_extract_mesh] surface_level=%.3f decimation_target=%d surfpts_dir=%s'
          % (args.surface_level, args.decimation_target, str(surfpts_dir)))
    out = extract_fn(call_args)
    print('[run_extract_mesh] DONE. mesh path(s) =', out)


if __name__ == '__main__':
    main()
