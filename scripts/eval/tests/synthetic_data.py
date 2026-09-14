#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合成测试数据生成器 (CPU only)。用于 M2/M3/M6 的单元自测。"""
import os
import numpy as np


def make_sphere_mesh(radius=1.0, resolution=20, seed=0):
    """返回一个 open3d 球面 mesh (水密, 亏格0, 单连通分量)。"""
    import open3d as o3d
    m = o3d.geometry.TriangleMesh.create_sphere(radius=radius, resolution=resolution)
    m.compute_vertex_normals()
    return m


def make_sphere_with_hole(radius=1.0, resolution=20, remove_frac=0.05, seed=0):
    """在球面上挖洞: 删除若干三角形 -> 产生边界边与孔洞。"""
    import open3d as o3d
    m = make_sphere_mesh(radius, resolution)
    tris = np.asarray(m.triangles)
    rng = np.random.default_rng(seed)
    # 删除顶部一片连续三角形以形成一个洞: 选 z 最大的顶点相关三角形
    verts = np.asarray(m.vertices)
    top_vert = int(np.argmax(verts[:, 2]))
    keep = ~np.any(tris == top_vert, axis=1)
    m.triangles = o3d.utility.Vector3iVector(tris[keep])
    m.remove_unreferenced_vertices()
    m.compute_vertex_normals()
    return m


def make_two_disjoint_spheres(radius=1.0, resolution=12, gap=5.0):
    """两个不相连的球 -> 连通分量数=2。"""
    import open3d as o3d
    a = make_sphere_mesh(radius, resolution)
    b = make_sphere_mesh(radius, resolution)
    b.translate((gap, 0, 0))
    m = a + b
    m.compute_vertex_normals()
    return m


def sample_points_on_sphere(radius=1.0, n=20000, seed=0):
    """在半径 radius 的球面上均匀采样点 (解析)。"""
    rng = np.random.default_rng(seed)
    v = rng.normal(size=(n, 3))
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    return v * radius


def make_camera_ring(n=16, radius=4.0, height=1.0, look_at=(0, 0, 0), seed=0):
    """生成一圈朝向 look_at 的相机, 返回 3DGS cameras.json 兼容的 list。

    cameras.json 约定: 'position' = 相机中心(world); 'rotation' = C2W 旋转(3x3);
    相机 +Z 朝向场景 (COLMAP 约定)。
    """
    look_at = np.asarray(look_at, dtype=np.float64)
    cams = []
    W, H = 64, 48
    fx = fy = 50.0  # 焦距(像素)
    for i in range(n):
        ang = 2 * np.pi * i / n
        # z 随角度变化, 避免相机共面 (更贴近真实场景, 且使相机中心包围盒非退化)
        z_i = height + 0.6 * np.sin(2 * ang)
        C = np.array([radius * np.cos(ang), radius * np.sin(ang), z_i], dtype=np.float64)
        z = look_at - C
        z /= (np.linalg.norm(z) + 1e-12)          # 相机 +Z 朝向场景
        up = np.array([0.0, 0.0, 1.0])
        x = np.cross(up, z)
        if np.linalg.norm(x) < 1e-6:
            x = np.array([1.0, 0.0, 0.0])
        x /= (np.linalg.norm(x) + 1e-12)
        y = np.cross(z, x)                          # 右手系 {x,y,z}, det=+1
        R_c2w = np.stack([x, y, z], axis=1)        # 列为相机轴在世界下的方向
        cams.append({
            "id": i,
            "img_name": f"{i:06d}",
            "width": W,
            "height": H,
            "position": C.tolist(),
            "rotation": R_c2w.tolist(),
            "fx": fx,
            "fy": fy,
        })
    return cams


if __name__ == "__main__":
    # 简单自检
    import open3d as o3d
    m = make_sphere_mesh()
    print("sphere: V", len(m.vertices), "F", len(m.triangles), "watertight", m.is_watertight())
    mh = make_sphere_with_hole()
    print("hole: watertight", mh.is_watertight(),
          "boundary?", not mh.is_edge_manifold(allow_boundary_edges=False))
    m2 = make_two_disjoint_spheres()
    c, cn, ca = m2.cluster_connected_triangles()
    print("two spheres: components", len(np.asarray(cn)))
    cams = make_camera_ring()
    print("cameras", len(cams), "first pos", cams[0]["position"])
