#!/bin/bash
# compare_load_balancers.sh
# Script to compare round robin and prequal load balancers using Locust

# CONFIGURATION
ENVIRONMENT=${1:-"local"}  # local, docker, or k8s
NUM_BACKENDS=${2:-20}     # Number of backend servers
USERS=${3:-1000}
SPAWN_RATE=${4:-100}
RUN_TIME=${5:-"2m"}

# Determine which script to use based on environment
case "$ENVIRONMENT" in
    "local")
        PROXY_RESTART_SCRIPT="scripts/run_local.sh"
        ;;
    "docker")
        PROXY_RESTART_SCRIPT="scripts/run_docker.sh"
        ;;
    "k8s")
        PROXY_RESTART_SCRIPT="scripts/run_k8s.sh"
        ;;
    *)
        echo "Error: Environment must be one of: local, docker, k8s"
        echo "Usage: $0 [environment] [num_backends] [users] [spawn_rate] [run_time]"
        echo "Example: $0 docker 10 500 50 1m"
        exit 1
        ;;
esac

LOCUST_FILE="locustfile.py"
LOCUST_HOST="http://localhost:8000"  # Adjust if needed
RESULTS_DIR="logs/"
FINAL_RESULTS_DIR="results/"

mkdir -p "$RESULTS_DIR"
mkdir -p "$FINAL_RESULTS_DIR"

echo "=== Load Testing Configuration ==="
echo "Environment: $ENVIRONMENT"
echo "Number of backends: $NUM_BACKENDS"
echo "Locust users: $USERS"
echo "Spawn rate: $SPAWN_RATE"
echo "Run time: $RUN_TIME"
echo "Proxy restart script: $PROXY_RESTART_SCRIPT"
echo "================================="

echo "Setting up Redis for load testing..."
if ! bash scripts/setup_redis.sh local; then
    echo "[ERROR] Failed to setup Redis. Aborting load tests."
    exit 1
fi

echo "Redis is ready for load testing"

function run_test() {
    LB_CLASS=$1
    LABEL=$2
    OUT_FILE="$RESULTS_DIR/${LABEL}_results.csv"
    echo "\n--- Testing $LABEL load balancer ---"

    # Restart proxy/server with the desired load balancer class
    echo "Restarting proxy/server with $LB_CLASS using $ENVIRONMENT environment..."
    
    # Pass parameters based on environment - now streamlined to use same pattern
    case "$ENVIRONMENT" in
        "local"|"docker"|"k8s")
            bash "$PROXY_RESTART_SCRIPT" "$LB_CLASS" $NUM_BACKENDS
            ;;
    esac

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
run_test "round_robin" "round_robin" || echo "[WARN] round_robin test failed."
run_test "random" "random" || echo "[WARN] random test failed."
run_test "least_latency" "least_latency" || echo "[WARN] least_latency test failed."
run_test "least_latency_p2c" "least_latency_power_of_two_choices" || echo "[WARN] least_latency_power_of_two_choices test failed."
run_test "least_rif" "least_rif" || echo "[WARN] least_rif test failed."
run_test "least_rif_p2c" "least_rif_power_of_two_choices" || echo "[WARN] least_rif_power_of_two_choices test failed."

echo "\nSummarizing backend distribution logs..."
python3 scripts/summarize_locust_metrics.py --logs-dir "$RESULTS_DIR" --results-dir "$FINAL_RESULTS_DIR"

echo "\nLoad test comparison complete. Check $RESULTS_DIR for results."
echo ""
echo "=== Usage Examples ==="
echo "Local testing:          $0 local 10 500 50 1m"
echo "Docker testing:         $0 docker 20 1000 100 2m" 
echo "Kubernetes:             $0 k8s 15 800 80 90s"
echo "======================"
