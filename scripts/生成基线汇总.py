#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段1 基线汇总: 汇集三阶段计时/显存 + mesh V/F + 表面采样点云点数 + 文件体积。
输出 outputs/基线_truck/基线汇总.txt (中文键, 人类可读) 与 基线汇总.json (双份)。"""
import json
import os
import glob
import sys

WORKDIR = '/scratch/e1351071/zju_test_test'
BASE = os.path.join(WORKDIR, 'outputs', '基线_truck')
TIMING = os.path.join(BASE, '计时')
MESHDIR = os.path.join(BASE, 'mesh')
COARSE_PT = os.path.join(BASE, 'coarse', 'sugarcoarse_3Dgs7000_densityestim02_sdfnorm02', '15000.pt')
GS_PLY = os.path.join(BASE, '3dgs_7k', 'point_cloud', 'iteration_7000', 'point_cloud.ply')

COMMIT = '7c10c4ae4a267dece512f5c7f40ed212a0a2ab44'


def sz(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return None


def human(n):
    if n is None:
        return 'N/A'
    for u in ['B', 'KB', 'MB', 'GB']:
        if n < 1024:
            return '%.2f %s' % (n, u)
        n /= 1024.0
    return '%.2f TB' % n


def load_timing(stage):
    p = os.path.join(TIMING, '计时_%s.json' % stage)
    if os.path.isfile(p):
        with open(p) as f:
            return json.load(f)
    return None


def main():
    import open3d as o3d

    stages = {'训练3DGS_7k': '训练3DGS_7k', 'coarse_dn_15k': 'coarse_dn_15k', '提取mesh': '提取mesh'}
    timing = {}
    for k, v in stages.items():
        timing[k] = load_timing(v)

    # mesh stats
    mesh_files = sorted(glob.glob(os.path.join(MESHDIR, 'sugarmesh_*.ply')))
    mesh_info = []
    for mf in mesh_files:
        m = o3d.io.read_triangle_mesh(mf)
        mesh_info.append({
            '文件': os.path.basename(mf), '路径': mf,
            '顶点数': len(m.vertices), '面数': len(m.triangles),
            '文件体积字节': sz(mf), '文件体积': human(sz(mf)),
        })

    # surface point clouds
    surf_files = sorted(glob.glob(os.path.join(MESHDIR, '表面采样点云_*.ply')))
    surf_info = []
    for sf in surf_files:
        p = o3d.io.read_point_cloud(sf)
        surf_info.append({
            '文件': os.path.basename(sf), '路径': sf,
            '点数': len(p.points), '文件体积字节': sz(sf), '文件体积': human(sz(sf)),
        })

    total_wall = sum((timing[k]['wall_seconds'] for k in timing if timing[k]), 0.0)
    peak_all = max((timing[k]['peak_mem_whole_gpu_MiB'] for k in timing if timing[k]), default=None)

    summary = {
        '场景': 'tandt/truck (251图, --eval llffhold=8 → 219训练/32测试)',
        'SuGaR_commit': COMMIT,
        'seed': 0,
        'GPU': 'NVIDIA H200 143GB 单卡 (gpu=0)',
        '流水线': '3DGS 7000it → coarse dn_consistency (num_iterations=15000, 真实步≈8000) → extract_mesh (surface_level=0.3, poisson_depth=10默认, vertices_density_quantile=0.1默认, decimation_target=1e6)',
        '各阶段': {},
        '总墙钟秒': round(total_wall, 3),
        '总墙钟分': round(total_wall / 60.0, 2),
        '峰值显存_全卡_MiB': peak_all,
        '产物路径': {
            '3DGS_ckpt': GS_PLY, '3DGS_ckpt体积': human(sz(GS_PLY)),
            'coarse_pt': COARSE_PT, 'coarse_pt体积': human(sz(COARSE_PT)),
        },
        'mesh': mesh_info,
        '表面采样点云': surf_info,
    }
    for k in ['训练3DGS_7k', 'coarse_dn_15k', '提取mesh']:
        t = timing[k]
        if t:
            summary['各阶段'][k] = {
                '墙钟秒': t.get('wall_seconds'), '退出码': t.get('return_code'),
                '峰值显存_本进程组_MiB': t.get('peak_mem_process_group_MiB'),
                '峰值显存_全卡_MiB': t.get('peak_mem_whole_gpu_MiB'),
                '命令': t.get('command'),
            }

    os.makedirs(BASE, exist_ok=True)
    with open(os.path.join(BASE, '基线汇总.json'), 'w') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # human-readable txt
    L = []
    L.append('==================== 阶段1 基线汇总 (tandt/truck) ====================')
    L.append('场景: %s' % summary['场景'])
    L.append('SuGaR commit: %s' % COMMIT)
    L.append('seed: 0    GPU: %s' % summary['GPU'])
    L.append('流水线: %s' % summary['流水线'])
    L.append('')
    L.append('---- 各阶段 墙钟 / 峰值显存 / 退出码 ----')
    for k in ['训练3DGS_7k', 'coarse_dn_15k', '提取mesh']:
        s = summary['各阶段'].get(k)
        if s:
            L.append('[%s] 墙钟=%.3fs (%.2f min)  峰值显存(本组)=%s MiB / 全卡=%s MiB  退出码=%s'
                     % (k, s['墙钟秒'], s['墙钟秒'] / 60.0, s['峰值显存_本进程组_MiB'],
                        s['峰值显存_全卡_MiB'], s['退出码']))
    L.append('')
    L.append('总墙钟: %.3f s (%.2f min)    峰值显存(全卡): %s MiB' % (total_wall, total_wall / 60.0, peak_all))
    L.append('')
    L.append('---- 产物 ----')
    L.append('3DGS ckpt: %s (%s)' % (GS_PLY, human(sz(GS_PLY))))
    L.append('coarse .pt: %s (%s)' % (COARSE_PT, human(sz(COARSE_PT))))
    L.append('')
    L.append('---- mesh (顶点/面/体积) ----')
    for mi in mesh_info:
        L.append('%s : V=%d  F=%d  (%s)' % (mi['文件'], mi['顶点数'], mi['面数'], mi['文件体积']))
    L.append('')
    L.append('---- 表面采样点云 (提取阶段, 供阶段2改动对比) ----')
    for si in surf_info:
        L.append('%s : 点数=%d  (%s)' % (si['文件'], si['点数'], si['文件体积']))
    L.append('')
    with open(os.path.join(BASE, '基线汇总.txt'), 'w') as f:
        f.write('\n'.join(L) + '\n')

    print('\n'.join(L))
    print('\n[生成基线汇总] 已写 %s/基线汇总.{txt,json}' % BASE)


if __name__ == '__main__':
    main()
