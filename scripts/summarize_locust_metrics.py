import csv
import glob
import os
from collections import Counter

import matplotlib.pyplot as plt


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

        # Parse stats history and generate plots
        stats_history_csv = os.path.join(logs_dir, f"{algorithm}_stats_history.csv")
        plots = []
        if os.path.exists(stats_history_csv):
            timestamps = []
            reqs_per_s = []
            failures_per_s = []
            p50 = []
            p90 = []
            p99 = []
            total_requests = []
            total_failures = []
            avg_latency = []
            median_latency = []
            with open(stats_history_csv, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("Name", "").strip() == "Aggregated":
                        try:
                            timestamps.append(int(row["Timestamp"]))
                            reqs_per_s.append(float(row["Requests/s"]))
                            failures_per_s.append(float(row["Failures/s"]))

                            # Some percentiles may be 'N/A' if no data
                            def safe_float(val):
                                try:
                                    return float(val)
                                except:
                                    return None

                            p50.append(safe_float(row["50%"]))
                            p90.append(safe_float(row["90%"]))
                            p99.append(safe_float(row["99%"]))
                            total_requests.append(int(row["Total Request Count"]))
                            total_failures.append(int(row["Total Failure Count"]))
                            avg_latency.append(
                                safe_float(
                                    row.get(
                                        "Total Average Response Time",
                                        row.get("Total Average Response Time", 0),
                                    )
                                )
                            )
                            median_latency.append(
                                safe_float(
                                    row.get(
                                        "Total Median Response Time",
                                        row.get("Total Median Response Time", 0),
                                    )
                                )
                            )
                        except Exception:
                            continue
            # Only plot if we have at least 2 points
            if len(timestamps) > 1:
                import datetime

                # Convert timestamps to seconds since start
                t0 = timestamps[0]
                times = [(t - t0) for t in timestamps]
                # Plot Requests/s
                plt.figure()
                plt.plot(times, reqs_per_s, label="Requests/s")
                plt.xlabel("Time (s)")
                plt.ylabel("Requests/s")
                plt.title(f"{algorithm} - Requests per second over time")
                plt.legend()
                plot_path = os.path.join(results_dir, f"{algorithm}_requests_per_s.png")
                plt.savefig(plot_path)
                plt.close()
                plots.append(plot_path)

                # Plot Failures/s
                plt.figure()
                plt.plot(times, failures_per_s, label="Failures/s", color="red")
                plt.xlabel("Time (s)")
                plt.ylabel("Failures/s")
                plt.title(f"{algorithm} - Failures per second over time")
                plt.legend()
                plot_path = os.path.join(results_dir, f"{algorithm}_failures_per_s.png")
                plt.savefig(plot_path)
                plt.close()
                plots.append(plot_path)

                # Plot percentiles
                plt.figure()
                if any(x is not None for x in p50):
                    plt.plot(
                        times,
                        [x if x is not None else float("nan") for x in p50],
                        label="p50",
                    )
                if any(x is not None for x in p90):
                    plt.plot(
                        times,
                        [x if x is not None else float("nan") for x in p90],
                        label="p90",
                    )
                if any(x is not None for x in p99):
                    plt.plot(
                        times,
                        [x if x is not None else float("nan") for x in p99],
                        label="p99",
                    )
                plt.xlabel("Time (s)")
                plt.ylabel("Response Time (ms)")
                plt.title(f"{algorithm} - Response time percentiles over time")
                plt.legend()
                plot_path = os.path.join(results_dir, f"{algorithm}_percentiles.png")
                plt.savefig(plot_path)
                plt.close()
                plots.append(plot_path)

                # Plot total requests
                plt.figure()
                plt.plot(times, total_requests, label="Total Requests")
                plt.xlabel("Time (s)")
                plt.ylabel("Total Requests")
                plt.title(f"{algorithm} - Total requests over time")
                plt.legend()
                plot_path = os.path.join(results_dir, f"{algorithm}_total_requests.png")
                plt.savefig(plot_path)
                plt.close()
                plots.append(plot_path)

                # Plot average and median latency
                plt.figure()
                if any(x is not None for x in avg_latency):
                    plt.plot(
                        times,
                        [x if x is not None else float("nan") for x in avg_latency],
                        label="Avg Latency",
                    )
                if any(x is not None for x in median_latency):
                    plt.plot(
                        times,
                        [x if x is not None else float("nan") for x in median_latency],
                        label="Median Latency",
                    )
                plt.xlabel("Time (s)")
                plt.ylabel("Latency (ms)")
                plt.title(f"{algorithm} - Latency over time")
                plt.legend()
                plot_path = os.path.join(results_dir, f"{algorithm}_latency.png")
                plt.savefig(plot_path)
                plt.close()
                plots.append(plot_path)
        result = {
            "algorithm": algorithm,
            "total": sum(counter.values()),
            "distribution": dict(counter),
            "metrics": metrics,
            "plots": plots,
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
