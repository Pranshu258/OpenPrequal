import csv
import glob
import os
from collections import Counter
from collections import OrderedDict


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
    # Collect average latency for all algorithms for comparison plot
    avg_latencies = {}
    median_latencies = {}
    p90_latencies = {}
    all_results = []
    for log_file in log_files:
        algorithm = os.path.basename(log_file).split(
            "_locust_backend_distribution.log"
        )[0]
        counter = Counter()
        with open(log_file, "r") as f:
            for line in f:
                backend = line.strip().split(",")[1]
                if backend:
                    counter[backend] += 1
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
            if len(timestamps) > 1:
                import datetime

                t0 = timestamps[0]
                times = [(t - t0) for t in timestamps]
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
        # Add pie chart for backend distribution
        if counter:
            plt.figure()
            labels = list(counter.keys())
            sizes = list(counter.values())

            def group_small_slices(labels, sizes, threshold=0.02):
                total = sum(sizes)
                new_labels = []
                new_sizes = []
                other = 0
                for l, s in zip(labels, sizes):
                    if total > 0 and s / total < threshold:
                        other += s
                    else:
                        new_labels.append(l)
                        new_sizes.append(s)
                if other > 0:
                    new_labels.append("Other")
                    new_sizes.append(other)
                return new_labels, new_sizes

            pie_labels, pie_sizes = group_small_slices(labels, sizes)
            plt.pie(pie_sizes, labels=pie_labels, autopct="%1.1f%%", startangle=140)
            plt.axis("equal")
            plt.title(f"{algorithm} - Backend Distribution")
            pie_path = os.path.join(
                results_dir, f"{algorithm}_backend_distribution_pie.png"
            )
            plt.savefig(pie_path)
            plt.close()
            plots.append(pie_path)

        # Collect average, median, and p90 latency for comparison
        avg_latency_val = None
        median_latency_val = None
        p90_latency_val = None
        if metrics and "summary" in metrics:
            avg_latency_val = metrics["summary"].get("latency_avg")
            median_latency_val = metrics["summary"].get("latency_median")
        if metrics and "percentiles" in metrics:
            p90_latency_val = metrics["percentiles"].get("p90")
        avg_latencies[algorithm] = avg_latency_val
        median_latencies[algorithm] = median_latency_val
        p90_latencies[algorithm] = p90_latency_val

        total_count = sum(counter.values())
        if total_count > 0:
            # Build and sort list of (backend, percent) tuples
            distribution_percent_tuples = sorted(
                ((k, (v / total_count) * 100) for k, v in counter.items()),
                key=lambda item: item[1], reverse=True
            )
            # Use OrderedDict to preserve order in JSON output
            distribution_percent = OrderedDict(distribution_percent_tuples)
        else:
            distribution_percent = {}
        result = {
            "algorithm": algorithm,
            "total": total_count,
            "distribution": distribution_percent,
            "metrics": metrics,
            "plots": plots,
        }
        all_results.append(result)
        result_file = os.path.join(results_dir, f"{algorithm}.json")
        with open(result_file, "w") as out:
            import json

            json.dump(result, out, indent=2, sort_keys=True)
        print(f"Wrote summary for {algorithm} to {result_file}")

    # After all algorithms, plot latency comparisons
    if avg_latencies:
        # Average latency
        plt.figure()
        algos = list(avg_latencies.keys())
        latencies = [avg_latencies[a] for a in algos]
        plt.bar(algos, latencies, color="skyblue")
        plt.ylabel("Average Latency (ms)")
        plt.xlabel("Algorithm")
        plt.title("Average Latency Comparison Across Algorithms")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        latency_bar_path = os.path.join(results_dir, "average_latency_comparison.png")
        plt.savefig(latency_bar_path)
        plt.close()

    if median_latencies:
        # Median latency
        plt.figure()
        algos = list(median_latencies.keys())
        medians = [median_latencies[a] for a in algos]
        plt.bar(algos, medians, color="orange")
        plt.ylabel("Median Latency (ms)")
        plt.xlabel("Algorithm")
        plt.title("Median Latency Comparison Across Algorithms")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        median_bar_path = os.path.join(results_dir, "median_latency_comparison.png")
        plt.savefig(median_bar_path)
        plt.close()

    if p90_latencies:
        # p90 latency
        plt.figure()
        algos = list(p90_latencies.keys())
        p90s = [p90_latencies[a] for a in algos]
        plt.bar(algos, p90s, color="green")
        plt.ylabel("p90 Latency (ms)")
        plt.xlabel("Algorithm")
        plt.title("p90 Latency Comparison Across Algorithms")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        p90_bar_path = os.path.join(results_dir, "p90_latency_comparison.png")
        plt.savefig(p90_bar_path)
        plt.close()


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
