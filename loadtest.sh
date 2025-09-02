#!/bin/bash
# Usage: ./loadtest.sh <num_backends> <duration> <rate>
# Example: ./loadtest.sh 3 30s 50

set -e

NUM_BACKENDS=${1:-3}
DURATION=${2:-30s}
RATE=${3:-50}
ALGOS=(random roundrobin)

mkdir -p logs
mkdir -p builds
mkdir -p loadtest_results

for ALGO in "${ALGOS[@]}"; do
    echo "\n=== Running load balancer with $ALGO ==="
    ./run.sh $NUM_BACKENDS $ALGO
    sleep 2 # Give servers time to start

    # Prepare vegeta targets file
    echo "GET http://localhost:8080/" > targets.txt

    # Run vegeta attack
    vegeta attack -duration=$DURATION -rate=$RATE -targets=targets.txt > loadtest_results/result_$ALGO.bin

    # Generate vegeta report
    vegeta report < loadtest_results/result_$ALGO.bin > loadtest_results/report_$ALGO.txt

    # Generate vegeta metrics (JSON)
    vegeta report -type=json < loadtest_results/result_$ALGO.bin > loadtest_results/metrics_$ALGO.json

    # Analyze backend distribution from backend URL in response body
    TMP_DIST=$(mktemp)
    vegeta encode loadtest_results/result_$ALGO.bin \
        | jq -r '.body' \
        | base64 --decode 2>/dev/null \
        | grep -o 'http://localhost:[0-9]*' \
        | sort | uniq -c | sort -nr > "$TMP_DIST"

    # Calculate percentages and write only the summary
    TOTAL=$(awk '{sum += $1} END {print sum}' "$TMP_DIST")
    TOTAL=${TOTAL:-0}
    if [ "$TOTAL" -eq 0 ]; then
        echo "No requests found. Cannot calculate backend distribution." > loadtest_results/distribution_$ALGO.txt
    else
        awk -v total=$TOTAL '{printf "%s: %.2f%%\n", $2, ($1/total)*100}' "$TMP_DIST" > loadtest_results/distribution_$ALGO.txt
    fi
    rm -f "$TMP_DIST"

    # Show summary
    echo "\nSummary for $ALGO:" | tee -a loadtest_results/summary.txt
    grep "requests" loadtest_results/report_$ALGO.txt | tee -a loadtest_results/summary.txt
    grep "latencies" loadtest_results/report_$ALGO.txt | tee -a loadtest_results/summary.txt
    grep "success" loadtest_results/report_$ALGO.txt | tee -a loadtest_results/summary.txt
    grep "errors" loadtest_results/report_$ALGO.txt | tee -a loadtest_results/summary.txt
    echo "Backend percentage distribution:" | tee -a loadtest_results/summary.txt
    cat loadtest_results/distribution_$ALGO.txt | tee -a loadtest_results/summary.txt

    # Kill servers before next run
    pkill -f './backend' || true
    pkill -f './proxy' || true
    sleep 2

done

rm -f targets.txt

echo "\nLoad testing complete. See loadtest_results/ for details."
