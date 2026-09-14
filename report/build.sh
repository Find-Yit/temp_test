#!/usr/bin/env bash
# build.sh — 一条命令编译 report.pdf
# 使用方法: cd report/ && bash build.sh
# 或: bash report/build.sh（从项目根目录）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TECTONIC="${SCRIPT_DIR}/../tools/tectonic/tectonic"

if [ ! -x "$TECTONIC" ]; then
    echo "错误: 未找到 tectonic，请先下载到 tools/tectonic/ 目录"
    exit 1
fi

cd "$SCRIPT_DIR"
echo "开始编译 report.tex ..."
"$TECTONIC" report.tex
echo "编译完成: ${SCRIPT_DIR}/report.pdf"
