#!/usr/bin/env python3
"""Parse vegeta JSON reports and append a CSV summary.

Usage:
  ./vegeta_parse_report.py /path/to/run_dir /path/to/summary.csv

It will scan the run directory for `*.json` files produced by `vegeta report -type=json` and
append one line per JSON report to the CSV with columns:
  run_name,requests,rate,throughput,success,mean_ms,p50_ms,p95_ms,p99_ms,max_ms,bytes_in_total
"""

import sys
import json
import csv
from pathlib import Path


def summarize_json(path: Path):
    with path.open('r') as f:
        data = json.load(f)
    lat = data.get('latencies', {})
    return {
        'run_name': path.stem,
        'requests': data.get('requests', ''),
        'rate': data.get('rate', ''),
        'throughput': data.get('throughput', ''),
        'success': data.get('success', ''),
        'mean_ms': round(lat.get('mean', 0) / 1_000_000, 3),
        'p50_ms': round(lat.get('50th', 0) / 1_000_000, 3),
        'p95_ms': round(lat.get('95th', 0) / 1_000_000, 3),
        'p99_ms': round(lat.get('99th', 0) / 1_000_000, 3),
        'max_ms': round(lat.get('max', 0) / 1_000_000, 3),
        'bytes_in_total': data.get('bytes_in', {}).get('total', ''),
    }


def main(run_dir: str, out_csv: str):
    run_path = Path(run_dir)
    out_path = Path(out_csv)
    json_files = sorted(run_path.glob('*.json'))
    if not json_files:
        print('No json files found in', run_dir)
        return

    fieldnames = ['run_name','requests','rate','throughput','success','mean_ms','p50_ms','p95_ms','p99_ms','max_ms','bytes_in_total']
    write_header = not out_path.exists()

    with out_path.open('a', newline='') as csvf:
        writer = csv.DictWriter(csvf, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        for jf in json_files:
            try:
                row = summarize_json(jf)
                writer.writerow(row)
                print('Appended', jf.name)
            except Exception as e:
                print('Error parsing', jf, e)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Usage: vegeta_parse_report.py <run_dir> <out_csv>')
        sys.exit(2)
    main(sys.argv[1], sys.argv[2])
