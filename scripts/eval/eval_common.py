#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_common.py — SuGaR 评测工具集 M1–M6 的共享工具函数。

设计原则:
- 只新增文件, 不改动 repo/SuGaR 内任何现有模块 (仅 import)。
- 所有随机性固定 seed。
- 每个指标脚本同时落盘 JSON (机器可读) + 中文键名 .txt (人类可读)。
- 图片/网格/数据文件用中文命名。

本模块不依赖 GPU / torch (除非显式调用 set_seed 时 torch 已安装, 会顺带固定 torch seed)。
M2/M3/M5/M6 的 CPU 部分只需 numpy/open3d。
"""
import os
import sys
import json
import time
import random
import datetime
import numpy as np

# 默认路径 (本项目固定在 /scratch/e1351071/zju_test_test 内)
PROJ_ROOT = "/scratch/e1351071/zju_test_test"
DEFAULT_REPO_ROOT = os.path.join(PROJ_ROOT, "repo", "SuGaR")
DEFAULT_EXEC_LOG = os.path.join(PROJ_ROOT, "notes", "_stage0E_log.txt")


# ----------------------------------------------------------------------------
# 环境 / 导入路径
# ----------------------------------------------------------------------------
def setup_sugar_path(repo_root=DEFAULT_REPO_ROOT):
    """把 SuGaR 仓库根目录及其 gaussian_splatting 子目录加入 sys.path。

    SuGaR 内部同时使用两种 import 风格:
      from gaussian_splatting.scene... (需要 repo_root 在 path 上)
      from scene...                     (需要 repo_root/gaussian_splatting 在 path 上)
    因此两者都要加入。
    """
    repo_root = os.path.abspath(repo_root)
    gs_dir = os.path.join(repo_root, "gaussian_splatting")
    for p in (gs_dir, repo_root):
        if p not in sys.path:
            sys.path.insert(0, p)
    return repo_root


def set_seed(seed=0):
    """固定所有随机源的 seed。"""
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except Exception:
        pass
    try:
        import open3d as o3d
        o3d.utility.random.seed(seed)
    except Exception:
        pass


# ----------------------------------------------------------------------------
# 执行日志
# ----------------------------------------------------------------------------
def setup_cjk_font():
    """让 matplotlib 能显示中文 (注册项目内 Noto CJK 字体)。best-effort。"""
    try:
        import matplotlib
        from matplotlib import font_manager
        candidates = [
            os.path.join(PROJ_ROOT, "assets", "fonts", "NotoSansCJKsc-Regular.otf"),
            os.path.join(PROJ_ROOT, "assets", "fonts", "NotoSerifCJKsc-Regular.otf"),
        ]
        name = None
        for fp in candidates:
            if os.path.isfile(fp):
                font_manager.fontManager.addfont(fp)
                name = font_manager.FontProperties(fname=fp).get_name()
                break
        if name:
            matplotlib.rcParams["font.sans-serif"] = [name] + list(
                matplotlib.rcParams.get("font.sans-serif", []))
            matplotlib.rcParams["font.family"] = "sans-serif"
        matplotlib.rcParams["axes.unicode_minus"] = False
        return name
    except Exception:
        return None


def log_exec(msg, log_path=DEFAULT_EXEC_LOG):
    """向执行日志追加一行 (带时间戳)。"""
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)


# ----------------------------------------------------------------------------
# 结果落盘: JSON + 中文 txt
# ----------------------------------------------------------------------------
def _fmt_value(v):
    """把数值格式化为人类可读字符串。"""
    if isinstance(v, bool):
        return "是" if v else "否"
    if isinstance(v, float):
        if v != v:  # NaN
            return "NaN"
        if v == 0:
            return "0"
        av = abs(v)
        if av >= 1e6 or av < 1e-4:
            return f"{v:.6e}"
        return f"{v:.6f}"
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_fmt_value(x) for x in v) + "]"
    return str(v)


def write_report(out_dir, basename, json_obj, txt_title, txt_sections):
    """同时写 <basename>.json 与 <basename>.txt。

    参数:
        out_dir: 输出目录
        basename: 文件基名 (中文, 不带扩展名), 如 "渲染指标_基线"
        json_obj: 要写入 JSON 的字典 (机器可读)
        txt_title: txt 首行标题
        txt_sections: [(小节标题, [(中文键, 值), ...]), ...]
    返回: (json_path, txt_path)
    """
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, basename + ".json")
    txt_path = os.path.join(out_dir, basename + ".txt")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_obj, f, indent=2, ensure_ascii=False, default=_json_default)

    lines = []
    lines.append("=" * 68)
    lines.append(txt_title)
    lines.append("生成时间: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("=" * 68)
    for sec_title, kvs in txt_sections:
        lines.append("")
        lines.append("【" + sec_title + "】")
        for k, v in kvs:
            lines.append(f"  {k}: {_fmt_value(v)}")
    lines.append("")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return json_path, txt_path


def _json_default(o):
    """JSON 序列化 numpy 类型。"""
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.ndarray,)):
        return o.tolist()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return str(o)


def write_csv(path, header, rows):
    """写一个简单 CSV (逗号分隔, 数值原样)。"""
    import csv
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(r)
    return path


# ----------------------------------------------------------------------------
# 相机中心 / 场景尺度 / bbox
# ----------------------------------------------------------------------------
def camera_centers_from_cameras_json(cameras_json_path):
    """从 3DGS 输出的 cameras.json 读取相机中心 (world)。

    cameras.json 由 3DGS 的 camera_to_JSON 写出, 其中 'position' 字段即
    相机中心在世界坐标下的位置 (C2W 的平移列)。返回 (N,3) np.float64。
    """
    with open(cameras_json_path, "r") as f:
        cams = json.load(f)
    centers = np.array([c["position"] for c in cams], dtype=np.float64)
    return centers


def scene_scale_from_centers(centers):
    """场景尺度 = 相机中心轴对齐包围盒(AABB)的对角线长度。

    返回 dict: aabb_min, aabb_max, center, diagonal, extent
    """
    centers = np.asarray(centers, dtype=np.float64)
    amin = centers.min(axis=0)
    amax = centers.max(axis=0)
    diag = float(np.linalg.norm(amax - amin))
    return {
        "aabb_min": amin.tolist(),
        "aabb_max": amax.tolist(),
        "center": ((amin + amax) / 2.0).tolist(),
        "extent": (amax - amin).tolist(),
        "diagonal": diag,
    }


def expand_aabb(amin, amax, factor):
    """把 AABB 以其中心为基准, 沿每个轴按 factor 缩放 (factor=1 不变)。"""
    amin = np.asarray(amin, dtype=np.float64)
    amax = np.asarray(amax, dtype=np.float64)
    c = (amin + amax) / 2.0
    half = (amax - amin) / 2.0 * float(factor)
    return (c - half), (c + half)


def robust_crop_bbox(cam_min, cam_max, factor, mesh_min=None, mesh_max=None, diag=None):
    """构造稳健的裁剪 bbox: 相机中心 AABB 以中心按 factor 缩放。

    若某轴的相机中心范围退化(近 0, 例如相机近似共面), 该轴改用网格自身范围,
    避免 open3d crop 报 'zero size'。返回 (amin, amax) np 数组。
    """
    amin, amax = expand_aabb(cam_min, cam_max, factor)
    amin = np.asarray(amin, dtype=np.float64)
    amax = np.asarray(amax, dtype=np.float64)
    if diag is None:
        diag = float(np.linalg.norm(np.asarray(cam_max) - np.asarray(cam_min)))
    tol = max(1e-9, 1e-3 * diag)
    for i in range(3):
        if (amax[i] - amin[i]) < tol:
            if mesh_min is not None and mesh_max is not None:
                pad = 1e-6 * (diag if diag > 0 else 1.0)
                amin[i] = float(mesh_min[i]) - pad
                amax[i] = float(mesh_max[i]) + pad
            else:
                # 无网格信息: 强制给一个最小厚度
                c = 0.5 * (amin[i] + amax[i])
                amin[i], amax[i] = c - tol, c + tol
    return amin, amax


def crop_points_aabb(points, amin, amax):
    """裁剪点云到 AABB。返回布尔掩码 + 裁剪后的点。"""
    points = np.asarray(points)
    amin = np.asarray(amin)
    amax = np.asarray(amax)
    mask = np.all((points >= amin) & (points <= amax), axis=1)
    return mask, points[mask]


# ----------------------------------------------------------------------------
# 距离统计
# ----------------------------------------------------------------------------
def distance_stats(d):
    """给定一维距离数组, 返回 mean/median/rmse/p90/max/min/count。"""
    d = np.asarray(d, dtype=np.float64)
    d = d[np.isfinite(d)]
    if d.size == 0:
        return {k: float("nan") for k in ["mean", "median", "rmse", "p90", "max", "min"]} | {"count": 0}
    return {
        "mean": float(d.mean()),
        "median": float(np.median(d)),
        "rmse": float(np.sqrt((d ** 2).mean())),
        "p90": float(np.percentile(d, 90)),
        "max": float(d.max()),
        "min": float(d.min()),
        "count": int(d.size),
    }


# ----------------------------------------------------------------------------
# 网格 / 点云 IO (open3d)
# ----------------------------------------------------------------------------
def load_mesh_o3d(path, clean=True):
    """用 open3d 读取三角网格; clean=True 时移除未引用顶点。"""
    import open3d as o3d
    mesh = o3d.io.read_triangle_mesh(path)
    if clean:
        mesh.remove_unreferenced_vertices()
    return mesh


def load_points_ply(path):
    """读取 .ply 点云的 xyz。优先 open3d; 若无点则用 plyfile 兜底读 x/y/z。"""
    import open3d as o3d
    pcd = o3d.io.read_point_cloud(path)
    pts = np.asarray(pcd.points, dtype=np.float64)
    if pts.shape[0] > 0:
        return pts
    # 兜底: 3DGS 的 point_cloud.ply 含大量高斯属性, open3d 可能不认字段
    from plyfile import PlyData
    ply = PlyData.read(path)
    el = ply.elements[0]
    pts = np.stack([np.asarray(el["x"]), np.asarray(el["y"]), np.asarray(el["z"])], axis=1).astype(np.float64)
    return pts
