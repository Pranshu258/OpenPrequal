#!/bin/bash
# compare_load_balancers.sh
# Script to compare round robin and prequal load balancers using Locust

# CONFIGURATION
PROXY_RESTART_SCRIPT="scripts/run_local.sh"  # Adjust if needed
LOCUST_FILE="locustfile.py"
LOCUST_HOST="http://localhost:8000"  # Adjust if needed
USERS=10000
SPAWN_RATE=100
RUN_TIME="5m"
RESULTS_DIR="logs/"

mkdir -p "$RESULTS_DIR"


function run_test() {
    LB_CLASS=$1
    LABEL=$2
    OUT_FILE="$RESULTS_DIR/${LABEL}_results.csv"
    echo "\n--- Testing $LABEL load balancer ---"

    # Restart proxy/server with the desired load balancer class
    echo "Restarting proxy/server with $LB_CLASS..."
    LOAD_BALANCER_CLASS="$LB_CLASS" bash "$PROXY_RESTART_SCRIPT"

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

    sleep 20
    
    # Run Locust in headless mode
    echo "Running Locust for $LABEL..."
    if ! locust --processes -1 -f "$LOCUST_FILE" --headless -u $USERS -r $SPAWN_RATE --run-time $RUN_TIME --host "$LOCUST_HOST" --csv "$RESULTS_DIR/${LABEL}" > "$OUT_FILE" 2>&1; then
        echo "[ERROR] Locust failed for $LABEL. See $OUT_FILE for details." | tee -a "$OUT_FILE"
        return 2
    fi
    echo "$LABEL test complete. Results saved to $OUT_FILE"
}


run_test "algorithms.round_robin_load_balancer.RoundRobinLoadBalancer" "round_robin" || echo "[WARN] round_robin test failed."
run_test "default" "prequal" || echo "[WARN] prequal test failed."

echo "\nLoad test comparison complete. Check $RESULTS_DIR for results."
