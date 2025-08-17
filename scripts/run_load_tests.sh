#!/bin/bash
# compare_load_balancers.sh
# Script to compare round robin and prequal load balancers using Locust

set -e

# CONFIGURATION
PROXY_RESTART_SCRIPT="scripts/run_local.sh"  # Adjust if needed
LOCUST_FILE="locustfile.py"
LOCUST_HOST="http://localhost:8000"  # Adjust if needed
USERS=100
SPAWN_RATE=10
RUN_TIME="1m"
RESULTS_DIR="logs/load_test_results"

mkdir -p "$RESULTS_DIR"


function run_test() {
    LB_CLASS=$1
    LABEL=$2
    OUT_FILE="$RESULTS_DIR/${LABEL}_results.csv"
    echo "\n--- Testing $LABEL load balancer ---"

    # Restart proxy/server with the desired load balancer class
    echo "Restarting proxy/server with $LB_CLASS..."
    LOAD_BALANCER_CLASS="$LB_CLASS" bash "$PROXY_RESTART_SCRIPT"
    sleep 5  # Wait for services to be up

    # Run Locust in headless mode
    echo "Running Locust for $LABEL..."
    locust -f "$LOCUST_FILE" --headless -u $USERS -r $SPAWN_RATE --run-time $RUN_TIME --host "$LOCUST_HOST" --csv "$RESULTS_DIR/${LABEL}" > "$OUT_FILE" 2>&1
    echo "$LABEL test complete. Results saved to $OUT_FILE"
}

run_test "algorithms.round_robin_load_balancer.RoundRobinLoadBalancer" "round_robin"
run_test "default" "prequal"

echo "\nLoad test comparison complete. Check $RESULTS_DIR for results."
