#!/usr/bin/env bash
# 一键复现 · 01 下载并解压数据集 (3DGS 官方 tandt_db.zip)
# ------------------------------------------------------------------
# wget 下载 (断点续传) + python zipfile 解压到 data/。
# 解压得到 data/tandt/{truck,train}, data/db/{playroom,drjohnson}; 本项目主场景 tandt/truck。
# 幂等: zip 已存在且完整则跳过下载; 目标场景已解压则跳过解压。
# 用法: bash scripts/一键复现/01_下载数据.sh
set -euo pipefail

ROOT="${SUGAR_ROOT:-/scratch/e1351071/zju_test_test}"
cd "$ROOT"
mkdir -p logs data
LOG="$ROOT/logs/一键_01下载_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1
ts(){ date "+%Y-%m-%d %H:%M:%S"; }
log(){ echo "[$(ts)] $*"; }
T0=$(date +%s)

URL="https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/datasets/input/tandt_db.zip"
ZIP="$ROOT/data/tandt_db.zip"

log "==== 01 下载数据 开始 日志: $LOG ===="

# (1) 下载 (wget 断点续传; 本机 22 端口被墙, 用 wget 不用 curl)
if python3 -c "import zipfile,sys; sys.exit(0 if zipfile.is_zipfile('$ZIP') and zipfile.ZipFile('$ZIP').testzip() is None else 1)" 2>/dev/null; then
  log "[1] $ZIP 已存在且完整 (testzip=None), 跳过下载"
else
  log "[1] wget 下载 tandt_db.zip (约 651 MiB) <- $URL"
  wget -c -O "$ZIP" "$URL"
fi

# (2) 解压 (python zipfile)
if [ -d "$ROOT/data/tandt/truck/images" ] && [ -d "$ROOT/data/db/playroom/images" ]; then
  log "[2] data/tandt/truck 与 data/db/playroom 已存在, 跳过解压"
else
  log "[2] python zipfile 解压 -> data/"
  python3 - "$ZIP" "$ROOT/data" <<'PY'
import sys, zipfile, time
zp, dest = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(zp) as z:
    bad = z.testzip()
    assert bad is None, f"zip 损坏: {bad}"
    z.extractall(dest)
    print(f"解压 {len(z.namelist())} 个条目 -> {dest}")
PY
fi

# (3) 校验主场景图片数
if [ -d "$ROOT/data/tandt/truck/images" ]; then
  N=$(ls "$ROOT/data/tandt/truck/images" | wc -l)
  log "[3] data/tandt/truck/images 图像数 = $N (期望 251)"
else
  log "[3] !! 未找到 data/tandt/truck/images"; exit 1
fi

log "==== 01 下载数据 完成, 耗时 $(( $(date +%s) - T0 ))s ===="
