#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_mv_filter.py — 多视角深度一致性剔点(阶段2a)的单元测试。

设计原则:
- 只 import repo/SuGaR, 不改动其任何现有模块。
- 全程 CPU, 固定 seed, 不占 GPU(避免干扰同机基线训练)。
- 合成场景: 球面点(应保留) + 明显漂浮点(应剔除)。验证漂浮点被剔、球面点保留 > 95%。

自洽性说明:
  深度图用与投票**同一套投影** (_project_to_grid) 渲染 (min-z 溅射), 所以投影约定在两侧抵消,
  测试聚焦于"一致/空域冲突/保留"这套投票逻辑本身是否正确, 而非重复验证 PyTorch3D 投影。
  另有一个 test_sampler_matches_sugar 直接对比本模块采样与 SuGaR.get_points_depth_in_depth_map 的输出是否一致。

用法:
  python scripts/tests/test_mv_filter.py        # 直接运行, 打印每项 PASS/FAIL, 失败则退出码非0
  pytest scripts/tests/test_mv_filter.py -q      # 或用 pytest
"""
import os
import sys
import numpy as np
import torch

# ---- 把 SuGaR 仓库根加入 path ----
_PROJ = "/scratch/e1351071/zju_test_test"
_REPO = os.path.join(_PROJ, "repo", "SuGaR")
for _p in (os.path.join(_REPO, "gaussian_splatting"), _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sugar_extractors.mv_consistency_filter import (  # noqa: E402
    accumulate_votes, compute_keep_mask, _project_to_grid, _sample_depth,
    sample_reference_cameras,
)
from pytorch3d.renderer import FoVPerspectiveCameras, look_at_view_transform  # noqa: E402

DEVICE = torch.device("cpu")
SEED = 0


# ---------------------------------------------------------------------------
# 合成工具
# ---------------------------------------------------------------------------
def fibonacci_sphere(n, radius=1.0, device=DEVICE):
    """均匀分布在半径 radius 球面上的 n 个点。"""
    i = torch.arange(n, dtype=torch.float64) + 0.5
    phi = torch.acos(1 - 2 * i / n)              # 极角
    golden = np.pi * (1 + 5 ** 0.5)
    theta = golden * i                            # 方位角
    x = torch.sin(phi) * torch.cos(theta)
    y = torch.sin(phi) * torch.sin(theta)
    z = torch.cos(phi)
    return (radius * torch.stack([x, y, z], dim=-1)).float().to(device)


def make_cameras(n_cam, dist=4.0, device=DEVICE):
    """在球面上环绕一圈的 n_cam 个 FoVPerspectiveCameras (返回可 [i] 索引的 batched 相机)。"""
    az = torch.linspace(0, 360, n_cam + 1)[:-1]
    el = 30.0 * torch.sin(torch.linspace(0, 4 * np.pi, n_cam))  # 高低起伏, 覆盖上下
    R, T = look_at_view_transform(dist=dist, elev=el, azim=az)
    cams = FoVPerspectiveCameras(R=R, T=T, fov=60.0, znear=1.0, zfar=100.0, device=device)
    return cams


def render_sphere_depth(cam, sphere_pts, H, W, znear):
    """把球面点溅射到相机, 每像素取最前(最小 z)得到一张深度图 (H,W), 背景=0。

    用与投票同一套 _project_to_grid, 保证投影约定自洽。
    """
    pcs = cam.get_world_to_view_transform().transform_points(sphere_pts)
    z = pcs[..., 2]
    grid, in_b = _project_to_grid(cam, pcs, H, W)
    u, v = grid[..., 0], grid[..., 1]
    px = ((u * 0.5 + 0.5) * (W - 1)).round().long().clamp(0, W - 1)
    py = ((v * 0.5 + 0.5) * (H - 1)).round().long().clamp(0, H - 1)
    vis = in_b & (z > znear)
    flat = (py * W + px)[vis]
    depth = torch.full((H * W,), float("inf"), device=sphere_pts.device)
    depth.scatter_reduce_(0, flat, z[vis], reduce="amin", include_self=True)
    depth[torch.isinf(depth)] = 0.0
    return depth.view(H, W)


def _sampler(cam, depth, pcs):
    """等价复刻 SuGaR.get_points_depth_in_depth_map 的采样(投影+grid_sample)。"""
    H, W = int(depth.shape[-2]), int(depth.shape[-1])
    grid, _ = _project_to_grid(cam, pcs, H, W)
    return _sample_depth(depth, grid)


# ---------------------------------------------------------------------------
# 测试 1: 投票算术(纯公式, 不依赖相机)
# ---------------------------------------------------------------------------
def test_vote_arithmetic():
    tau = 0.02
    z_p = torch.tensor([3.0, 3.05, 2.0, 5.0])
    z_map = torch.tensor([3.0, 3.00, 3.0, 3.0])
    # 期望: 一致 = [T, T(0.05<0.06), F, F]; 冲突 = [F, F, T(2<2.94), F]
    consistent = (z_p - z_map).abs() < tau * z_map
    conflict = z_p < z_map - tau * z_map
    assert consistent.tolist() == [True, True, False, False], consistent.tolist()
    assert conflict.tolist() == [False, False, True, False], conflict.tolist()
    # 互斥: 不可能同时一致与冲突
    assert not bool((consistent & conflict).any())


def test_compute_keep_mask():
    cons = torch.tensor([0, 2, 3, 2, 5])
    conf = torch.tensor([0, 0, 2, 1, 0])
    keep = compute_keep_mask(cons, conf, min_consistent=2, max_conflict=1)
    # idx0: cons0<2 剔; idx1: 2>=2,0<=1 留; idx2: 3>=2 但 conf2>1 剔; idx3: 留; idx4: 留
    assert keep.tolist() == [False, True, False, True, True], keep.tolist()


# ---------------------------------------------------------------------------
# 测试 2: 采样与 SuGaR 官方函数一致
# ---------------------------------------------------------------------------
def test_sampler_matches_sugar():
    """本模块 _project_to_grid+_sample_depth 应与 SuGaR.get_points_depth_in_depth_map 逐元素一致。"""
    from sugar_scene.sugar_model import SuGaR

    class _Stub:
        image_height = 128
        image_width = 128

    H = W = 128
    cams = make_cameras(4)
    cam = cams[1]
    sphere = fibonacci_sphere(50000, radius=1.0)
    depth = render_sphere_depth(cam, sphere, H, W, znear=float(cam.znear.reshape(-1)[0]))
    query = fibonacci_sphere(2000, radius=1.0)
    pcs = cam.get_world_to_view_transform().transform_points(query)
    mine = _sampler(cam, depth, pcs)
    ref = SuGaR.get_points_depth_in_depth_map(_Stub(), cam, depth, pcs)  # 未绑定方法 + stub
    assert torch.allclose(mine, ref, atol=1e-5), (mine[:5], ref[:5])


# ---------------------------------------------------------------------------
# 测试 3: 合成球面 + 漂浮点 —— 主判据
# ---------------------------------------------------------------------------
def _run_sphere_floater(n_cam=24, H=400, W=400, tau=0.02,
                        min_consistent=2, max_conflict=1):
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    r_sphere, cam_dist = 1.0, 4.0

    cams = make_cameras(n_cam, dist=cam_dist)
    ref_cameras = [cams[i] for i in range(n_cam)]
    znear_list = [float(cams[i].znear.reshape(-1)[0]) for i in range(n_cam)]

    dense_sphere = fibonacci_sphere(300_000, radius=r_sphere)
    depth_maps = [render_sphere_depth(ref_cameras[i], dense_sphere, H, W, znear_list[i])
                  for i in range(n_cam)]

    # 被测点: 球面点(应保留) + 两组漂浮点(应剔除)
    sphere_test = fibonacci_sphere(3000, radius=r_sphere)

    g = torch.Generator().manual_seed(SEED)
    # F1: 紧贴球面外侧的自由空间(半径 1.1~1.5) -> 浮在已观测表面之前, 触发空域冲突票
    dirs1 = torch.nn.functional.normalize(torch.randn(1500, 3, generator=g), dim=-1)
    rad1 = 1.1 + 0.4 * torch.rand(1500, 1, generator=g)
    float_free = dirs1 * rad1
    # F2: 球内部(半径 0.2~0.6) -> 被前表面遮挡, 无一致票
    dirs2 = torch.nn.functional.normalize(torch.randn(1500, 3, generator=g), dim=-1)
    rad2 = 0.2 + 0.4 * torch.rand(1500, 1, generator=g)
    float_inside = dirs2 * rad2

    all_pts = torch.cat([sphere_test, float_free, float_inside], dim=0)
    n_s, n_f1, n_f2 = sphere_test.shape[0], float_free.shape[0], float_inside.shape[0]

    cons, conf, valid = accumulate_votes(
        points=all_pts, ref_cameras=ref_cameras, depth_maps=depth_maps,
        znear_list=znear_list, tau=tau, depth_sampler=_sampler,
        n_votes=0, seed=SEED, chunk_size=1_000_000, device=DEVICE,
    )
    keep = compute_keep_mask(cons, conf, min_consistent, max_conflict)

    keep_sphere = keep[:n_s]
    keep_f1 = keep[n_s:n_s + n_f1]
    keep_f2 = keep[n_s + n_f1:]
    return {
        "sphere_keep_frac": keep_sphere.float().mean().item(),
        "f1_remove_frac": (~keep_f1).float().mean().item(),
        "f2_remove_frac": (~keep_f2).float().mean().item(),
        "sphere_mean_consistent": cons[:n_s].float().mean().item(),
        "f1_mean_conflict": conf[n_s:n_s + n_f1].float().mean().item(),
    }


def test_sphere_kept_floaters_removed():
    res = _run_sphere_floater()
    print("  [sphere/floater] ", {k: round(v, 4) for k, v in res.items()})
    assert res["sphere_keep_frac"] > 0.95, f"sphere kept only {res['sphere_keep_frac']:.4f}"
    assert res["f1_remove_frac"] > 0.95, f"free-space floaters removed only {res['f1_remove_frac']:.4f}"
    assert res["f2_remove_frac"] > 0.95, f"interior floaters removed only {res['f2_remove_frac']:.4f}"


def test_conflict_vote_is_used():
    """自由空间漂浮点必须主要因'空域冲突票'被剔(验证我们的空域冲突判据确实发挥作用)。"""
    res = _run_sphere_floater()
    assert res["f1_mean_conflict"] > 1.0, f"F1 mean conflict votes too low: {res['f1_mean_conflict']:.3f}"


def test_sample_reference_cameras_deterministic():
    a = sample_reference_cameras(200, 30, seed=0)
    b = sample_reference_cameras(200, 30, seed=0)
    c = sample_reference_cameras(200, 30, seed=1)
    assert a == b and len(a) == 30 and len(set(a)) == 30
    assert a != c  # 不同 seed 一般不同
    assert sample_reference_cameras(10, 30, seed=0) == list(range(10))  # ncam<=M 用全部


# ---------------------------------------------------------------------------
# 直接运行入口
# ---------------------------------------------------------------------------
def _main():
    tests = [
        ("test_vote_arithmetic", test_vote_arithmetic),
        ("test_compute_keep_mask", test_compute_keep_mask),
        ("test_sample_reference_cameras_deterministic", test_sample_reference_cameras_deterministic),
        ("test_sampler_matches_sugar", test_sampler_matches_sugar),
        ("test_sphere_kept_floaters_removed", test_sphere_kept_floaters_removed),
        ("test_conflict_vote_is_used", test_conflict_vote_is_used),
    ]
    n_pass = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
            n_pass += 1
        except Exception as e:
            print(f"FAIL  {name}: {type(e).__name__}: {e}")
    print(f"\n{n_pass}/{len(tests)} passed")
    return 0 if n_pass == len(tests) else 1


if __name__ == "__main__":
    sys.exit(_main())
