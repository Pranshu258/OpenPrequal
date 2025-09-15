#!/usr/bin/env python3
"""Parse vegeta JSON results in `results/` and produce comparative CSV/tables.

Outputs:
 - CSV files per-metric named `results/compare_<metric>.csv` where rows are RPS and columns are algorithms.
 - Prints simple console tables.

Filename parsing expects: <alg>_r<RPS>_*.json or <alg>p2c_r<RPS>_*.json

Metrics extracted (if present):
 - latency percentiles (50th, 95th, 99th, max, mean) in milliseconds
 - requests
 - throughput
 - success (fraction)
 - errors count

"""

import argparse
import csv
import json
import os
import re
from collections import defaultdict, OrderedDict

RESULTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'results')
FILENAME_RE = re.compile(r"(?P<alg>[a-zA-Z0-9_+-]+)_r(?P<rps>\d+)_.*\.json$")

# helper to ms
def ns_to_ms(ns):
    try:
        return float(ns) / 1e6
    except Exception:
        return None


def load_results(path):
    with open(path, 'r') as f:
        return json.load(f)


def collect():
    data = defaultdict(lambda: defaultdict(dict))
    # data[rps][alg] = metrics dict
    files = [f for f in os.listdir(RESULTS_DIR) if f.endswith('.json')]
    for fn in files:
        m = FILENAME_RE.search(fn)
        if not m:
            # try alternate pattern like namep2c_r1200
            m2 = re.search(r"(?P<alg>.+)_r(?P<rps>\d+)_.*\.json$", fn)
            if m2:
                m = m2
            else:
                continue
        alg = m.group('alg')
        rps = int(m.group('rps'))
        path = os.path.join(RESULTS_DIR, fn)
        try:
            j = load_results(path)
        except Exception as e:
            print(f"warning: failed to parse {fn}: {e}")
            continue
        metrics = {}
        lat = j.get('latencies', {})
        # percentiles may be named '50th' or '50' or '50.0' in different runs; try common keys
        p50 = lat.get('50th') or lat.get('50') or lat.get('50.0')
        p95 = lat.get('95th') or lat.get('95') or lat.get('95.0')
        p99 = lat.get('99th') or lat.get('99') or lat.get('99.0')
        metrics['lat_mean_ms'] = ns_to_ms(lat.get('mean'))
        metrics['lat_p50_ms'] = ns_to_ms(p50)
        metrics['lat_p95_ms'] = ns_to_ms(p95)
        metrics['lat_p99_ms'] = ns_to_ms(p99)
        metrics['lat_max_ms'] = ns_to_ms(lat.get('max'))
        metrics['requests'] = j.get('requests')
        metrics['throughput'] = j.get('throughput')
        metrics['success'] = j.get('success')
        errs = j.get('errors') or []
        metrics['errors'] = len(errs) if isinstance(errs, list) else (errs or 0)
        # status_codes: include 4xx/5xx counts as errors if present
        sc = j.get('status_codes') or {}
        errors_from_status = sum(v for k,v in sc.items() if not str(k).startswith('2'))
        # If errors list is empty but status codes show non-2xx, count them
        if metrics['errors'] == 0 and errors_from_status:
            metrics['errors'] = errors_from_status
        data[rps][alg] = metrics
    return data


def write_csvs(data, out_dir=None):
    if out_dir is None:
        out_dir = os.path.join(os.path.dirname(__file__), '..', 'results')
    os.makedirs(out_dir, exist_ok=True)
    # collect all metrics keys
    metric_keys = set()
    for rps, algs in data.items():
        for alg, m in algs.items():
            metric_keys.update(m.keys())
    metric_keys = sorted(metric_keys)
    # collect all rps and algs
    all_rps = sorted(data.keys())
    all_algs = sorted({alg for algs in data.values() for alg in algs.keys()})

    csv_files = []
    for metric in metric_keys:
        csv_path = os.path.join(out_dir, f'compare_{metric}.csv')
        with open(csv_path, 'w', newline='') as cf:
            writer = csv.writer(cf)
            header = ['rps'] + all_algs
            writer.writerow(header)
            for rps in all_rps:
                row = [rps]
                for alg in all_algs:
                    v = data.get(rps, {}).get(alg, {}).get(metric)
                    row.append('' if v is None else v)
                writer.writerow(row)
        csv_files.append(csv_path)
    return csv_files


def print_tables(data):
    try:
        from tabulate import tabulate
    except Exception:
        tabulate = None
    all_rps = sorted(data.keys())
    all_algs = sorted({alg for algs in data.values() for alg in algs.keys()})
    # print a small table per metric
    metric_keys = sorted({k for algs in data.values() for m in algs.values() for k in m.keys()})
    for metric in metric_keys:
        rows = []
        header = ['rps'] + all_algs
        for rps in all_rps:
            row = [rps]
            for alg in all_algs:
                v = data.get(rps, {}).get(alg, {}).get(metric)
                if v is None:
                    row.append('')
                else:
                    if isinstance(v, float):
                        row.append(f"{v:.2f}")
                    else:
                        row.append(str(v))
            rows.append(row)
        print('\nMetric:', metric)
        if tabulate:
            print(tabulate(rows, headers=header, tablefmt='github'))
        else:
            # simple formatting
            colwidths = [max(len(str(x)) for x in col) for col in zip(*([header] + rows))]
            fmt = '  '.join('{{:{}}}'.format(w) for w in colwidths)
            print(fmt.format(*header))
            for r in rows:
                print(fmt.format(*r))


def main():
    global RESULTS_DIR
    p = argparse.ArgumentParser(description='Compare vegeta JSON results in results/')
    p.add_argument('--results', '-r', default=None, help='results directory')
    p.add_argument('--out', '-o', default=None, help='output dir for CSVs (defaults to results/)')
    args = p.parse_args()
    if args.results:
        RESULTS_DIR = args.results
    data = collect()
    if not data:
        print('no data found in', RESULTS_DIR)
        return 1
    csvs = write_csvs(data, out_dir=args.out)
    print('wrote', len(csvs), 'CSV files to', args.out or os.path.join(os.path.dirname(__file__), '..', 'results'))
    print_tables(data)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
