#!/usr/bin/env bash
# -*- coding: utf-8 -*-
# M5 计时/显存包装器: 记录一条命令的开始/结束时间、墙钟、退出码, 以及
# 运行期间的峰值显存 (本命令进程组 + 全卡两种口径)。
#
# 用法:
#   计时运行.sh <阶段名> <输出目录> [--gpu N] [--interval SEC] -- <命令 ...>
#
# 示例:
#   bash 计时运行.sh 训练3DGS_7k outputs/基线_truck/计时 --gpu 0 -- \
#       python repo/SuGaR/gaussian_splatting/train.py -s data/tandt/truck -m outputs/... --iterations 7000
#
# 产物: <输出目录>/计时_<阶段名>.txt 和 .json (中文键)。
set -u

STAGE="${1:-stage}"; shift || true
OUTDIR="${1:-.}"; shift || true
GPU=0
INTERVAL=1
# 解析可选参数, 直到遇到 --
while [ $# -gt 0 ]; do
  case "$1" in
    --gpu) GPU="$2"; shift 2;;
    --interval) INTERVAL="$2"; shift 2;;
    --) shift; break;;
    *) echo "未知参数: $1"; exit 2;;
  esac
done

if [ $# -eq 0 ]; then
  echo "错误: 缺少要运行的命令 (请在 -- 之后给出)"; exit 2
fi

mkdir -p "$OUTDIR"
CMD=("$@")
TXT="$OUTDIR/计时_${STAGE}.txt"
JSON="$OUTDIR/计时_${STAGE}.json"
MEMFILE="$(mktemp)"
echo "0 0" > "$MEMFILE"   # our_peak total_peak

START_EPOCH=$(date +%s.%N)
START_HUMAN=$(date "+%Y-%m-%d %H:%M:%S")

# 以新进程组启动命令, 便于按 PGID 归集显存
setsid bash -c 'exec "$@"' _ "${CMD[@]}" &
CMD_PID=$!
PGID=$(ps -o pgid= -p "$CMD_PID" 2>/dev/null | tr -d ' ')

# 后台显存采样
(
  our_peak=0; total_peak=0
  has_smi=1; command -v nvidia-smi >/dev/null 2>&1 || has_smi=0
  while kill -0 "$CMD_PID" 2>/dev/null; do
    if [ "$has_smi" = "1" ]; then
      # 全卡已用显存
      total=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i "$GPU" 2>/dev/null | tr -d ' ')
      [ -n "${total:-}" ] && [ "$total" -gt "$total_peak" ] 2>/dev/null && total_peak=$total
      # 本进程组显存
      our=0
      while read -r pid mem; do
        [ -z "$pid" ] && continue
        pg=$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ')
        if [ "$pg" = "$PGID" ]; then our=$((our + mem)); fi
      done < <(nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits -i "$GPU" 2>/dev/null | tr -d ' ' | tr ',' ' ')
      [ "$our" -gt "$our_peak" ] 2>/dev/null && our_peak=$our
      echo "$our_peak $total_peak" > "$MEMFILE"
    fi
    sleep "$INTERVAL"
  done
  echo "$our_peak $total_peak" > "$MEMFILE"
) &
SAMPLER_PID=$!

wait "$CMD_PID"
RC=$?

# 停止采样
kill "$SAMPLER_PID" 2>/dev/null
wait "$SAMPLER_PID" 2>/dev/null

END_EPOCH=$(date +%s.%N)
END_HUMAN=$(date "+%Y-%m-%d %H:%M:%S")
ELAPSED=$(awk "BEGIN{printf \"%.3f\", $END_EPOCH - $START_EPOCH}")
read -r OUR_PEAK TOTAL_PEAK < "$MEMFILE"
rm -f "$MEMFILE"

CMD_STR="${CMD[*]}"

# 写 txt (中文键)
{
  echo "===================================================================="
  echo "M5 计时/显存 — 阶段: ${STAGE}"
  echo "===================================================================="
  echo "命令: ${CMD_STR}"
  echo "GPU 索引: ${GPU}"
  echo "开始时间: ${START_HUMAN}"
  echo "结束时间: ${END_HUMAN}"
  echo "墙钟(秒): ${ELAPSED}"
  echo "退出码: ${RC}"
  echo "峰值显存_本进程组(MiB): ${OUR_PEAK}"
  echo "峰值显存_全卡(MiB): ${TOTAL_PEAK}"
  echo "采样间隔(秒): ${INTERVAL}"
} > "$TXT"

# 写 json
python3 - "$JSON" "$STAGE" "$CMD_STR" "$GPU" "$START_HUMAN" "$END_HUMAN" "$ELAPSED" "$RC" "$OUR_PEAK" "$TOTAL_PEAK" "$INTERVAL" <<'PY'
import json, sys
(_, path, stage, cmd, gpu, sh, eh, el, rc, our, total, itv) = sys.argv
json.dump({
    "stage": stage, "command": cmd, "gpu": int(gpu),
    "start_human": sh, "end_human": eh,
    "wall_seconds": float(el), "return_code": int(rc),
    "peak_mem_process_group_MiB": int(our), "peak_mem_whole_gpu_MiB": int(total),
    "sample_interval_sec": float(itv),
}, open(path, "w"), indent=2, ensure_ascii=False)
PY

echo "[计时运行] 阶段=${STAGE} 墙钟=${ELAPSED}s 退出码=${RC} 峰值显存(本组)=${OUR_PEAK}MiB -> ${TXT}"
exit "$RC"
