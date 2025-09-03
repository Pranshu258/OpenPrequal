#!/bin/bash
# Usage: ./loadtest.sh <num_backends> <duration> <rate>
# Example: ./loadtest.sh 3 30s 50

set -e

NUM_BACKENDS=${1:-3}
DURATION=${2:-30s}
RATE=${3:-50}
ALGOS=(random roundrobin leastrif leastlatency power2_leastrif power2_leastlatency prequal)

mkdir -p logs
mkdir -p builds
mkdir -p benchmarks

for ALGO in "${ALGOS[@]}"; do
    echo ""
    echo "========================================"
    echo "Running load balancer with $ALGO"
    echo "========================================"
    scripts/run.sh $NUM_BACKENDS $ALGO
    sleep 2 # Give servers time to start

    # Prepare vegeta targets file
    echo "GET http://localhost:8080/" > targets.txt

    # Run vegeta attack
    vegeta attack -duration=$DURATION -rate=$RATE -targets=targets.txt > benchmarks/result_$ALGO.bin

    # Generate vegeta report
    vegeta report < benchmarks/result_$ALGO.bin > benchmarks/report_$ALGO.txt

    # Generate vegeta metrics (JSON)
    vegeta report -type=json < benchmarks/result_$ALGO.bin > benchmarks/metrics_$ALGO.json

    # Analyze backend distribution from backend URL in response body (in memory)
    DIST_RAW=$(vegeta encode benchmarks/result_$ALGO.bin \
        | jq -r '.body' \
        | base64 --decode 2>/dev/null \
        | grep -o 'http://localhost:[0-9]*' \
        | sort | uniq -c | sort -nr)

    TOTAL=$(echo "$DIST_RAW" | awk '{sum += $1} END {print sum}')
    TOTAL=${TOTAL:-0}
    if [ "$TOTAL" -eq 0 ]; then
        DIST_SUMMARY="No requests found. Cannot calculate backend distribution."
        DIST_JSON='{}'
    else
        DIST_SUMMARY=$(echo "$DIST_RAW" | awk -v total=$TOTAL '{printf "%s: %.2f%%\n", $2, ($1/total)*100}')
        DIST_JSON=$(echo "$DIST_RAW" | awk -v total=$TOTAL '{printf "\"%s\": %.4f, ", $2, ($1/total)*100}' | sed 's/, $//')
        DIST_JSON="{$DIST_JSON}"
    fi

    # Add distribution to metrics JSON (in memory, fix jq usage)
    jq --arg dist "$DIST_JSON" '.backend_distribution = ($dist | fromjson)' benchmarks/metrics_$ALGO.json > benchmarks/metrics_${ALGO}_tmp.json && mv benchmarks/metrics_${ALGO}_tmp.json benchmarks/metrics_$ALGO.json

    # Add distribution to report text
    echo -e "Backend percentage distribution:\n$DIST_SUMMARY" >> benchmarks/report_$ALGO.txt

    # Show summary
    echo "Summary for $ALGO:"
    cat benchmarks/report_$ALGO.txt

    # Kill servers before next run
    pkill -f './backend' || true
    pkill -f './proxy' || true
    sleep 2

done

echo "Load testing complete. See benchmarks/ for details."

# Delete all .bin files from benchmarks folder
rm -f benchmarks/*.bin
rm -f benchmarks/*.txt
rm -f targets.txt