#!/bin/bash
# compare_load_balancers.sh
# Script to compare round robin and prequal load balancers using Locust

# CONFIGURATION
PROXY_RESTART_SCRIPT="scripts/run_local.sh"  # Adjust if needed
LOCUST_FILE="locustfile.py"
LOCUST_HOST="http://localhost:8000"  # Adjust if needed
USERS=300
SPAWN_RATE=100
RUN_TIME="2m"
RESULTS_DIR="logs/"
FINAL_RESULTS_DIR="results/"

mkdir -p "$RESULTS_DIR"
mkdir -p "$FINAL_RESULTS_DIR"

function run_test() {
    LB_CLASS=$1
    LABEL=$2
    OUT_FILE="$RESULTS_DIR/${LABEL}_results.csv"
    echo "\n--- Testing $LABEL load balancer ---"

    # Restart proxy/server with the desired load balancer class
    echo "Restarting proxy/server with $LB_CLASS..."
    bash "$PROXY_RESTART_SCRIPT" "$LB_CLASS" 20

    # Wait for proxy to be up (max 30s)
    echo "Waiting for proxy server to be up..."
    for i in {1..30}; do
        if curl -s --max-time 1 "$LOCUST_HOST/metrics" > /dev/null; then
            echo "Proxy server is up."
            break
        fi
        sleep 1
        if [ $i -eq 30 ]; then
            echo "[ERROR] Proxy server did not start within 30 seconds. Skipping $LABEL test." | tee -a "$OUT_FILE"
            return 1
        fi
    done

    # Wait for at least one healthy backend (max 30s)
    echo "Waiting for at least one healthy backend..."
    for i in {1..30}; do
        # Try to extract healthy backend count from /metrics (adjust pattern as needed)
        if curl -s --max-time 1 "$LOCUST_HOST/metrics" | grep -q "# TYPE request_latency_seconds_created gauge"; then
            echo "Detected healthy backend(s) (metrics string found)."
            break
        fi
        sleep 1
        if [ $i -eq 30 ]; then
            echo "[ERROR] No healthy backends detected within 30 seconds. Skipping $LABEL test." | tee -a "$OUT_FILE"
            return 1
        fi
    done
    
    # Run Locust in headless mode
    echo "Running Locust for $LABEL..."
    if ! ALGORITHM_NAME="$LABEL" locust --processes -1 -f "$LOCUST_FILE" --headless -u $USERS -r $SPAWN_RATE --run-time $RUN_TIME --host "$LOCUST_HOST" --csv "$RESULTS_DIR/${LABEL}" > "$OUT_FILE" 2>&1; then
        echo "[ERROR] Locust failed for $LABEL. See $OUT_FILE for details." | tee -a "$OUT_FILE"
        return 2
    fi
    echo "$LABEL test complete. Results saved to $OUT_FILE"

    echo "Profiler analysis..."
    python3 scripts/profiler_analysis.py > $FINAL_RESULTS_DIR/${LABEL}_profiler_results.csv
}

run_test "default" "prequal" || echo "[WARN] prequal test failed."
run_test "algorithms.round_robin_load_balancer.RoundRobinLoadBalancer" "round_robin" || echo "[WARN] round_robin test failed."
run_test "algorithms.random_load_balancer.RandomLoadBalancer" "random" || echo "[WARN] random test failed."
run_test "algorithms.least_latency_load_balancer.LeastLatencyLoadBalancer" "least_latency" || echo "[WARN] least_latency test failed."
run_test "algorithms.least_latency_power_of_two_choices_load_balancer.LeastLatencyPowerOfTwoChoicesLoadBalancer" "least_latency_power_of_two_choices" || echo "[WARN] least_latency_power_of_two_choices test failed."
run_test "algorithms.least_rif_load_balancer.LeastRIFLoadBalancer" "least_rif" || echo "[WARN] least_rif test failed."
run_test "algorithms.least_rif_power_of_two_choices_load_balancer.LeastRIFPowerOfTwoChoicesLoadBalancer" "least_rif_power_of_two_choices" || echo "[WARN] least_rif_power_of_two_choices test failed."

echo "\nSummarizing backend distribution logs..."
python3 scripts/summarize_locust_metrics.py --logs-dir "$RESULTS_DIR" --results-dir "$FINAL_RESULTS_DIR"

echo "\nLoad test comparison complete. Check $RESULTS_DIR for results."
