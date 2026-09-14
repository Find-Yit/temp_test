#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
阶段1 wrapper: 驱动 coarse dn_consistency trainer（scripts/coarse_dn_trainer_param.py，
即 repo trainer 的逐字副本，仅 num_iterations / save_milestones 可由 args 覆盖）。
- 固定 seed=0（torch / numpy / random / cuda）。SuGaR trainer 本身无 seed；CUDA atomicAdd 仍有轻微非确定性（已在报告说明）。
- 不改 repo 文件；仅 import。路径参数在 chdir(REPO) 前解析为绝对路径。
用法示例（从工作目录运行）:
  python scripts/run_coarse_dn.py -s data/tandt/truck -c outputs/基线_truck/3dgs_7k -i 7000 \
      -o outputs/基线_truck/coarse --num_iterations 15000 --eval True
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
    p = argparse.ArgumentParser(description='阶段1 coarse dn_consistency wrapper (seeded, no repo edit).')
    p.add_argument('-s', '--scene_path', type=str, required=True)
    p.add_argument('-c', '--checkpoint_path', type=str, required=True, help='3DGS 输出目录')
    p.add_argument('-o', '--output_dir', type=str, default=None)
    p.add_argument('-i', '--iteration_to_load', type=int, default=7000)
    p.add_argument('--eval', type=str2bool, default=True)
    p.add_argument('--white_background', type=str2bool, default=False)
    p.add_argument('-e', '--estimation_factor', type=float, default=0.2)
    p.add_argument('-n', '--normal_factor', type=float, default=0.2)
    p.add_argument('--gpu', type=int, default=0)
    p.add_argument('--num_iterations', type=int, default=15000, help='PARAM: 覆盖 trainer 硬编码 15000')
    p.add_argument('--seed', type=int, default=0)
    args = p.parse_args()

    # 解析绝对路径（在 chdir 之前，按当前 CWD 解析）
    scene_path = os.path.abspath(args.scene_path)
    checkpoint_path = os.path.abspath(args.checkpoint_path)
    if not checkpoint_path.endswith(os.sep):
        checkpoint_path += os.sep  # SuGaR cameras.py 用 gs_output_path + 'cameras.json' 拼接, 需尾斜杠
    output_dir = os.path.abspath(args.output_dir) if args.output_dir else None

    # sys.path: scripts/（副本模块） + REPO（sugar_scene / gaussian_splatting 包） + REPO/gaussian_splatting（3DGS 内部 bare import）
    sys.path.insert(0, os.path.join(REPO, 'gaussian_splatting'))
    sys.path.insert(0, REPO)
    sys.path.insert(0, SCRIPTS)
    os.chdir(REPO)  # gs_model.py 里的 sys.path.append('./gaussian_splatting') 需要 CWD=REPO

    import numpy as np
    import torch
    seed = int(args.seed)
    os.environ.setdefault('PYTHONHASHSEED', str(seed))
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

    from coarse_dn_trainer_param import coarse_training_with_density_regularization_and_dn_consistency as train_fn

    call_args = AttrDict({
        'checkpoint_path': checkpoint_path,
        'scene_path': scene_path,
        'iteration_to_load': args.iteration_to_load,
        'output_dir': output_dir,
        'eval': args.eval,
        'estimation_factor': args.estimation_factor,
        'normal_factor': args.normal_factor,
        'gpu': args.gpu,
        'white_background': args.white_background,
        'num_iterations': args.num_iterations,   # PARAM 覆盖
    })
    print('[run_coarse_dn] scene=%s' % scene_path)
    print('[run_coarse_dn] ckpt(3dgs)=%s' % checkpoint_path)
    print('[run_coarse_dn] output_dir=%s' % output_dir)
    print('[run_coarse_dn] iteration_to_load=%d num_iterations=%d eval=%s seed=%d'
          % (args.iteration_to_load, args.num_iterations, str(args.eval), seed))
    out = train_fn(call_args)
    print('[run_coarse_dn] DONE. coarse model path =', out)


if __name__ == '__main__':
    main()
