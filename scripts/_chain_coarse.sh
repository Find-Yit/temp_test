#!/usr/bin/env bash
cd /scratch/e1351071/zju_test_test
source env.sh >/dev/null 2>&1
export PYTHONHASHSEED=0
# wait for 3DGS timing txt (written on completion, success or fail)
n=0
until [ -f outputs/基线_truck/计时/计时_训练3DGS_7k.txt ] || [ $n -ge 360 ]; do sleep 5; n=$((n+1)); done
RC=$(grep -oE "退出码: [0-9]+" outputs/基线_truck/计时/计时_训练3DGS_7k.txt | grep -oE "[0-9]+")
CKPT=outputs/基线_truck/3dgs_7k/point_cloud/iteration_7000/point_cloud.ply
echo "[chain] 3DGS done waited=$((n*5))s RC=$RC ckpt_exists=$([ -f $CKPT ] && echo yes || echo no)"
if [ "$RC" != "0" ] || [ ! -f "$CKPT" ]; then echo "[chain] ABORT: 3DGS failed or no ckpt"; exit 1; fi
echo "[chain] launching coarse 15k $(date)"
nohup bash scripts/eval/计时运行.sh coarse_dn_15k outputs/基线_truck/计时 --gpu 0 --interval 5 -- \
  python scripts/run_coarse_dn.py -s data/tandt/truck -c outputs/基线_truck/3dgs_7k -i 7000 \
  -o outputs/基线_truck/coarse --num_iterations 15000 --eval True \
  > logs/基线_coarse_15k.log 2>&1 &
echo "[chain] coarse launched PID=$! ; exiting chain"
