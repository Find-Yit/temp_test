#!/usr/bin/env python3
"""Stage 0B 环境验收脚本。
逐项 import + GPU 调用，打印 PASS/FAIL 表，落盘 JSON 到 notes/env_check.json，
任一必需项失败则退出码非 0。
运行: source env.sh && python scripts/check_env.py
"""
import json, os, sys, time, traceback

RESULTS = []  # list of dict: name, ok, detail
def rec(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": str(detail)})
    print(f"[{'PASS' if ok else 'FAIL'}] {name:32s} {detail}")

t0 = time.time()

# 1) torch + CUDA
try:
    import torch
    cuda_ok = torch.cuda.is_available()
    gpu = torch.cuda.get_device_name(0) if cuda_ok else "N/A"
    cap = torch.cuda.get_device_capability(0) if cuda_ok else None
    detail = f"torch={torch.__version__} cuda_build={torch.version.cuda} avail={cuda_ok} gpu={gpu} cap={cap}"
    rec("import torch (+cuda avail)", cuda_ok, detail)
except Exception as e:
    rec("import torch (+cuda avail)", False, repr(e)); traceback.print_exc()

# 2) diff_gaussian_rasterization (compiled _C)
try:
    import diff_gaussian_rasterization
    import diff_gaussian_rasterization._C as _dgr_C
    from diff_gaussian_rasterization import GaussianRasterizationSettings, GaussianRasterizer
    rec("import diff_gaussian_rasterization", True, f"_C={os.path.basename(_dgr_C.__file__)}")
except Exception as e:
    rec("import diff_gaussian_rasterization", False, repr(e)); traceback.print_exc()

# 3) simple_knn (compiled _C) + GPU distCUDA2 call
try:
    import torch
    from simple_knn._C import distCUDA2
    ok = False; detail = "distCUDA2 imported"
    if torch.cuda.is_available():
        pts = torch.rand(2000, 3, device="cuda", dtype=torch.float32)
        d = distCUDA2(pts)
        torch.cuda.synchronize()
        ok = (d.shape[0] == 2000) and torch.isfinite(d).all().item()
        detail = f"distCUDA2(2000x3)->{tuple(d.shape)} finite={torch.isfinite(d).all().item()} mean={d.mean().item():.4g}"
    rec("simple_knn._C GPU distCUDA2", ok, detail)
except Exception as e:
    rec("simple_knn._C GPU distCUDA2", False, repr(e)); traceback.print_exc()

# 4) pytorch3d + GPU knn_points call
try:
    import torch, pytorch3d
    from pytorch3d.ops import knn_points
    ok = False; detail = f"pytorch3d={pytorch3d.__version__}"
    if torch.cuda.is_available():
        p1 = torch.rand(1, 128, 3, device="cuda")
        p2 = torch.rand(1, 64, 3, device="cuda")
        knn = knn_points(p1, p2, K=5)
        torch.cuda.synchronize()
        ok = tuple(knn.idx.shape) == (1, 128, 5) and tuple(knn.dists.shape) == (1, 128, 5)
        detail += f" knn_points.idx={tuple(knn.idx.shape)} dists={tuple(knn.dists.shape)}"
    rec("pytorch3d GPU knn_points", ok, detail)
except Exception as e:
    rec("pytorch3d GPU knn_points", False, repr(e)); traceback.print_exc()

# 5) open3d
try:
    import open3d as o3d
    _ = o3d.geometry.TriangleMesh()  # touch API
    rec("import open3d", True, f"open3d={o3d.__version__}")
except Exception as e:
    rec("import open3d", False, repr(e)); traceback.print_exc()

# 6) pymeshlab
try:
    import pymeshlab
    ms = pymeshlab.MeshSet()  # touch API
    from importlib.metadata import version as _mv
    rec("import pymeshlab", True, f"pymeshlab={_mv('pymeshlab')}")
except Exception as e:
    rec("import pymeshlab", False, repr(e)); traceback.print_exc()

# 7) plyfile
try:
    import plyfile
    from plyfile import PlyData, PlyElement
    from importlib.metadata import version as _mv2
    try:
        ver = _mv2("plyfile")
    except Exception:
        ver = getattr(plyfile, "__version__", "?")
    rec("import plyfile", True, f"plyfile={ver}")
except Exception as e:
    rec("import plyfile", False, repr(e)); traceback.print_exc()

# ---- summary ----
elapsed = time.time() - t0
n_pass = sum(1 for r in RESULTS if r["ok"])
n_total = len(RESULTS)
summary = {"pass": n_pass, "total": n_total, "all_pass": n_pass == n_total,
           "elapsed_sec": round(elapsed, 2), "results": RESULTS}
os.makedirs("/scratch/e1351071/zju_test_test/notes", exist_ok=True)
with open("/scratch/e1351071/zju_test_test/notes/env_check.json", "w") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)
print("-" * 60)
print(f"RESULT: {n_pass}/{n_total} passed in {elapsed:.1f}s -> notes/env_check.json")
sys.exit(0 if n_pass == n_total else 1)
