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
    vegeta attack -duration=$DURATION -rate=$RATE -targets=targets.txt > result_$ALGO.bin

    # Generate vegeta report
    vegeta report < result_$ALGO.bin > loadtest_results/report_$ALGO.txt

    # Generate vegeta metrics (JSON)
    vegeta report -type=json < result_$ALGO.bin > loadtest_results/metrics_$ALGO.json

    # Backend distribution
    echo "Backend distribution for $ALGO:" > loadtest_results/backends_$ALGO.txt
    for ((i=1; i<=NUM_BACKENDS; i++)); do
        PORT=$((8080 + i))
        URL="http://localhost:$PORT/metrics"
        echo "Backend $PORT metrics:" >> loadtest_results/backends_$ALGO.txt
        curl -s $URL >> loadtest_results/backends_$ALGO.txt
        echo "" >> loadtest_results/backends_$ALGO.txt
    done

    # Show summary
    echo "\nSummary for $ALGO:" | tee -a loadtest_results/summary.txt
    grep "requests" loadtest_results/report_$ALGO.txt | tee -a loadtest_results/summary.txt
    grep "latencies" loadtest_results/report_$ALGO.txt | tee -a loadtest_results/summary.txt
    grep "success" loadtest_results/report_$ALGO.txt | tee -a loadtest_results/summary.txt
    grep "errors" loadtest_results/report_$ALGO.txt | tee -a loadtest_results/summary.txt
    echo "Backend metrics:" | tee -a loadtest_results/summary.txt
    cat loadtest_results/backends_$ALGO.txt | tee -a loadtest_results/summary.txt

    # Kill servers before next run
    pkill -f './backend' || true
    pkill -f './proxy' || true
    sleep 2

done

rm -f targets.txt result_*.bin

echo "\nLoad testing complete. See loadtest_results/ for details."
