#!/usr/bin/env bash
cd /scratch/e1351071/zju_test_test
source env.sh >/dev/null 2>&1
export PYTHONHASHSEED=0
CT=outputs/基线_truck/计时/计时_coarse_dn_15k.txt
PT=outputs/基线_truck/coarse/sugarcoarse_3Dgs7000_densityestim02_sdfnorm02/15000.pt
n=0
until [ -f "$CT" ] || [ $n -ge 720 ]; do sleep 5; n=$((n+1)); done
RC=$(grep -oE "退出码: [0-9]+" "$CT" 2>/dev/null | grep -oE "[0-9]+")
echo "[chain2] coarse done waited=$((n*5))s RC=$RC pt_exists=$([ -f $PT ] && echo yes || echo no)"
if [ "$RC" != "0" ] || [ ! -f "$PT" ]; then echo "[chain2] ABORT: coarse failed or no .pt"; exit 1; fi
echo "[chain2] launching extract $(date)"
nohup bash scripts/eval/计时运行.sh 提取mesh outputs/基线_truck/计时 --gpu 0 --interval 5 -- \
  python scripts/run_extract_mesh.py -s data/tandt/truck -c outputs/基线_truck/3dgs_7k -i 7000 \
  -m "$PT" -l 0.3 -d 1000000 -o outputs/基线_truck/mesh --surfpts_dir outputs/基线_truck/mesh --eval True \
  > logs/基线_extract.log 2>&1 &
echo "[chain2] extract launched PID=$! ; exiting"
