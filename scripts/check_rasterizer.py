#!/usr/bin/env python3
"""GPU 光栅化冒烟测试: 渲染 500 个高斯到 128x128, 验证 rasterizer CUDA 核在 sm_90 上真正执行。
非 0B 硬性验收项, 但为阶段1核心组件做去风险验证。"""
import math, numpy as np, torch
from diff_gaussian_rasterization import GaussianRasterizationSettings, GaussianRasterizer

def getWorld2View2(R, t):
    Rt = np.zeros((4, 4)); Rt[:3, :3] = R.transpose(); Rt[:3, 3] = t; Rt[3, 3] = 1.0
    return np.float32(Rt)

def getProjectionMatrix(znear, zfar, fovX, fovY):
    tanY = math.tan(fovY / 2); tanX = math.tan(fovX / 2)
    top = tanY * znear; bottom = -top; right = tanX * znear; left = -right
    P = torch.zeros(4, 4)
    P[0, 0] = 2 * znear / (right - left); P[1, 1] = 2 * znear / (top - bottom)
    P[0, 2] = (right + left) / (right - left); P[1, 2] = (top + bottom) / (top - bottom)
    P[3, 2] = 1.0; P[2, 2] = zfar / (zfar - znear); P[2, 3] = -(zfar * znear) / (zfar - znear)
    return P

device = "cuda"; H = W = 128
fovx = fovy = math.radians(60); znear, zfar = 0.01, 100.0
R = np.eye(3); T = np.array([0., 0., 0.])
w2v = torch.tensor(getWorld2View2(R, T)).transpose(0, 1).to(device)
proj = getProjectionMatrix(znear, zfar, fovx, fovy).transpose(0, 1).to(device)
full_proj = (w2v.unsqueeze(0).bmm(proj.unsqueeze(0))).squeeze(0)
campos = w2v.inverse()[3, :3]
tanfovx = math.tan(fovx / 2); tanfovy = math.tan(fovy / 2)
bg = torch.zeros(3, device=device)

settings = GaussianRasterizationSettings(H, W, tanfovx, tanfovy, bg, 1.0, w2v, full_proj, 0, campos, False, False)
rasterizer = GaussianRasterizer(settings)

N = 500; torch.manual_seed(0)
means3D = torch.stack([(torch.rand(N) - 0.5) * 2, (torch.rand(N) - 0.5) * 2, torch.rand(N) * 4 + 2], dim=1).to(device)
means2D = torch.zeros_like(means3D, requires_grad=True)
colors = torch.rand(N, 3, device=device)
opac = torch.ones(N, 1, device=device) * 0.9
scales = torch.ones(N, 3, device=device) * 0.05
rots = torch.zeros(N, 4, device=device); rots[:, 0] = 1.0

img, radii = rasterizer(means3D, means2D, opac, shs=None, colors_precomp=colors, scales=scales, rotations=rots)
torch.cuda.synchronize()
n_vis = int((radii > 0).sum()); s = float(img.sum()); mx = float(img.max())
print(f"img shape={tuple(img.shape)} radii>0={n_vis}/{N} img.sum={s:.3f} img.max={mx:.3f}")
assert tuple(img.shape) == (3, H, W), "wrong image shape"
assert n_vis > 0, "no gaussians rendered (radii all zero)"
assert s > 0, "black image"
print("RASTERIZER_GPU_OK")
