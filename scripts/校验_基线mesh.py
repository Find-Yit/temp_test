#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段1 验收: open3d 读取基线 mesh 与表面采样点云, 打印 V/F/点数/连通分量, 判定 V>1e5 & F>0。"""
import glob
import os
import sys

import open3d as o3d

BASE = '/scratch/e1351071/zju_test_test/outputs/基线_truck/mesh'

def main():
    ok = True
    meshes = sorted(glob.glob(os.path.join(BASE, 'sugarmesh_*.ply')))
    if not meshes:
        print('[FAIL] 未找到 sugarmesh_*.ply')
        return 1
    for mf in meshes:
        m = o3d.io.read_triangle_mesh(mf)
        V, F = len(m.vertices), len(m.triangles)
        try:
            m.remove_unreferenced_vertices()
            labels, ntri, area = m.cluster_connected_triangles()
            import numpy as np
            ntri = np.asarray(ntri)
            comps = len(ntri)
            maxr = (ntri.max() / max(F, 1)) if comps > 0 else 0.0
        except Exception as e:
            comps, maxr = -1, -1.0
        cond = (V > 100000) and (F > 0)
        ok = ok and cond
        print('[MESH] %s' % os.path.basename(mf))
        print('       V=%d  F=%d  连通分量=%d  最大分量面占比=%.4f  -> %s'
              % (V, F, comps, maxr, 'PASS' if cond else 'FAIL'))
    for sf in sorted(glob.glob(os.path.join(BASE, '表面采样点云_*.ply'))):
        p = o3d.io.read_point_cloud(sf)
        print('[PCD ] %s : 点数=%d' % (os.path.basename(sf), len(p.points)))
    print('OVERALL:', 'PASS' if ok else 'FAIL')
    return 0 if ok else 2

if __name__ == '__main__':
    sys.exit(main())
