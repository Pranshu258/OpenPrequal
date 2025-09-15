#!/usr/bin/env bash
# Stepwise Vegeta attack runner
# Usage: ./vegeta_step_attack.sh -t <targets_file> -r "1,5,10,20" -d 30 -o ./vegeta_runs -p run_prefix

set -euo pipefail

usage() {
  cat <<EOF
Usage: $0 -t targets_file -r rates_comma_separated -d duration_seconds -o output_dir -p prefix

Example:
  $0 -t ../vegeta_targets.txt -r "1,5,10,20" -d 30 -o ../vegeta_step_runs -p test
EOF
}

TARGETS=""
RATES=""
DURATION=30
OUTDIR="./vegeta_step_runs"
PREFIX="run"

while getopts ":t:r:d:o:p:h" opt; do
  case ${opt} in
    t) TARGETS="$OPTARG" ;;
    r) RATES="$OPTARG" ;;
    d) DURATION="$OPTARG" ;;
    o) OUTDIR="$OPTARG" ;;
    p) PREFIX="$OPTARG" ;;
    h) usage; exit 0 ;;
    \?) echo "Invalid option: -$OPTARG" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$TARGETS" || -z "$RATES" ]]; then
  usage
  exit 1
fi

rm -r "$OUTDIR"
mkdir -p "$OUTDIR"

IFS=',' read -r -a rate_arr <<< "$RATES"

echo "Starting stepwise vegeta attacks: rates=${rate_arr[*]} duration=${DURATION}s -> out=$OUTDIR"

for r in "${rate_arr[@]}"; do
  ts=$(date -u +%Y%m%dT%H%M%SZ)
  runname="${PREFIX}_r${r}_${ts}"
  binfile="$OUTDIR/${runname}.bin"
  txtfile="$OUTDIR/${runname}.txt"
  jsonfile="$OUTDIR/${runname}.json"

  echo "Running rate=${r}/s -> $binfile"
  vegeta attack -targets="$TARGETS" -rate="$r" -duration="${DURATION}s" -output="$binfile"

  echo "Generating reports: $txtfile, $jsonfile"
  vegeta report -type=text "$binfile" > "$txtfile"
  vegeta report -type=json "$binfile" > "$jsonfile"

  echo "Wrote: $binfile, $txtfile, $jsonfile"
done

echo "All runs completed."
