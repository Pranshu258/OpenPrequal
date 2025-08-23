import glob
import os
from collections import Counter


def parse_results_csv(results_csv_path):
    import re

    metrics = {}
    try:
        with open(results_csv_path, "r") as f:
            lines = f.readlines()
        # Find the last two summary sections: main metrics and percentiles
        # 1. Find the last 'Aggregated' row before 'Response time percentiles'
        # 2. Find the 'Aggregated' row after 'Response time percentiles'
        main_metrics = None
        percentiles_metrics = None
        # Find 'Response time percentiles' section
        percentiles_start = None
        for i, line in enumerate(lines):
            if line.strip().startswith("Response time percentiles"):
                percentiles_start = i
                break
        # Find last 'Aggregated' before percentiles
        if percentiles_start is not None:
            for i in range(percentiles_start - 1, -1, -1):
                if re.match(r"\s*Aggregated", lines[i]):
                    main_metrics = lines[i]
                    break
            # Find 'Aggregated' after percentiles
            for i in range(percentiles_start + 1, len(lines)):
                if re.match(r"\s*Aggregated", lines[i]):
                    percentiles_metrics = lines[i]
                    break
        else:
            # If no percentiles section, just get the last 'Aggregated'
            for i in range(len(lines) - 1, -1, -1):
                if re.match(r"\s*Aggregated", lines[i]):
                    main_metrics = lines[i]
                    break

        def parse_main_agg_row(row):
            # Example row:
            # '         Aggregated                                                                     38218     0(0.00%) |     63      13     602     57 |  318.25        0.00\n'
            import re

            try:
                # Split on '|' to get the three main columns
                parts = row.strip().split("|")
                if len(parts) != 3:
                    raise ValueError(
                        f"Expected 3 columns separated by '|', got {len(parts)}: {parts}"
                    )
                # First column: label, total reqs, fails
                left = parts[0].strip()
                left_fields = re.split(r"\s+", left)
                # Find 'Aggregated' label
                if left_fields[0] != "Aggregated":
                    idx = left_fields.index("Aggregated")
                    left_fields = left_fields[idx:]
                total_requests = int(left_fields[1])
                fails_match = re.match(r"(\d+)\(([^)]*)\)", left_fields[2])
                total_failures = int(fails_match.group(1)) if fails_match else 0
                failure_rate = (
                    float(fails_match.group(2).replace("%", "")) if fails_match else 0.0
                )
                success_rate = 100.0 - failure_rate
                # Second column: avg, min, max, med
                mid = parts[1].strip()
                mid_fields = [float(x) for x in re.split(r"\s+", mid) if x]
                avg, min_, max_, med = (mid_fields + [0, 0, 0, 0])[:4]
                # Third column: req/s, fails/s
                right = parts[2].strip()
                right_fields = [float(x) for x in re.split(r"\s+", right) if x]
                req_per_s, fails_per_s = (right_fields + [0, 0])[:2]
                return {
                    "total_requests": total_requests,
                    "total_failures": total_failures,
                    "success_rate": success_rate,
                    "failure_rate": failure_rate,
                    "latency_avg": avg,
                    "latency_min": min_,
                    "latency_max": max_,
                    "latency_median": med,
                    "requests_per_second": req_per_s,
                    "failures_per_second": fails_per_s,
                }
            except Exception as e:
                return {"parse_error": str(e), "row": row}

        def parse_percentiles_agg_row(row):
            # The percentiles row is space-separated, after the label
            p_values = re.split(r"\s+", row.strip())[1:]
            # 50% 66% 75% 80% 90% 95% 98% 99% 99.9% 99.99% 100% #reqs
            return {
                "p50": float(p_values[0]),
                "p66": float(p_values[1]),
                "p75": float(p_values[2]),
                "p80": float(p_values[3]),
                "p90": float(p_values[4]),
                "p95": float(p_values[5]),
                "p98": float(p_values[6]),
                "p99": float(p_values[7]),
                "p99_9": float(p_values[8]),
                "p99_99": float(p_values[9]),
                "p100": float(p_values[10]),
                "total_requests": int(p_values[11]),
            }

        if percentiles_metrics:
            metrics["percentiles"] = parse_percentiles_agg_row(percentiles_metrics)

        if main_metrics:
            metrics["summary"] = parse_main_agg_row(main_metrics)

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
        # Parse corresponding results.csv file
        results_csv = os.path.join(logs_dir, f"{algorithm}_results.csv")
        metrics = parse_results_csv(results_csv) if os.path.exists(results_csv) else {}
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
