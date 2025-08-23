import glob
import os
from collections import Counter


def parse_results_csv(stats_csv_path):
    """
    Parse a simple stats CSV file with a header and an 'Aggregated' row.
    Returns a dict with summary and percentiles.
    """
    import csv

    metrics = {}
    try:
        with open(stats_csv_path, "r") as f:
            reader = csv.DictReader(f)
            agg_row = None
            for row in reader:
                if row.get("Name", "").strip() == "Aggregated":
                    agg_row = row
                    break
        if agg_row:
            # Parse summary metrics
            metrics["summary"] = {
                "total_requests": int(agg_row["Request Count"]),
                "total_failures": int(agg_row["Failure Count"]),
                "latency_median": float(agg_row["Median Response Time"]),
                "latency_avg": float(agg_row["Average Response Time"]),
                "latency_min": float(agg_row["Min Response Time"]),
                "latency_max": float(agg_row["Max Response Time"]),
                "requests_per_second": float(agg_row["Requests/s"]),
                "failures_per_second": float(agg_row["Failures/s"]),
            }
            # Parse percentiles
            metrics["percentiles"] = {
                "p50": float(agg_row["50%"]),
                "p66": float(agg_row["66%"]),
                "p75": float(agg_row["75%"]),
                "p80": float(agg_row["80%"]),
                "p90": float(agg_row["90%"]),
                "p95": float(agg_row["95%"]),
                "p98": float(agg_row["98%"]),
                "p99": float(agg_row["99%"]),
                "p99_9": float(agg_row["99.9%"]),
                "p99_99": float(agg_row["99.99%"]),
                "p100": float(agg_row["100%"]),
            }
    except Exception as e:
        metrics["csv_parse_error"] = str(e)
    return metrics


def summarize_backend_distribution(logs_dir, results_dir):
    os.makedirs(results_dir, exist_ok=True)
    log_files = glob.glob(os.path.join(logs_dir, "*_locust_backend_distribution.log"))
    for log_file in log_files:
        algorithm = os.path.basename(log_file).split(
            "_locust_backend_distribution.log"
        )[0]
        counter = Counter()
        with open(log_file, "r") as f:
            for line in f:
                backend = line.strip()
                if backend:
                    counter[backend] += 1
        # Parse corresponding stats.csv file instead of results.csv
        stats_csv = os.path.join(logs_dir, f"{algorithm}_stats.csv")
        metrics = parse_results_csv(stats_csv) if os.path.exists(stats_csv) else {}
        result = {
            "algorithm": algorithm,
            "total": sum(counter.values()),
            "distribution": dict(counter),
            "metrics": metrics,
        }
        result_file = os.path.join(results_dir, f"{algorithm}.json")
        with open(result_file, "w") as out:
            import json

            json.dump(result, out, indent=2, sort_keys=True)
        print(f"Wrote summary for {algorithm} to {result_file}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Summarize backend distribution logs for each algorithm."
    )
    parser.add_argument(
        "--logs-dir", default="logs", help="Directory containing log files"
    )
    parser.add_argument(
        "--results-dir", default="results", help="Directory to write summary files"
    )
    args = parser.parse_args()
    summarize_backend_distribution(args.logs_dir, args.results_dir)
