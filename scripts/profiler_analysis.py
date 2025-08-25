import re
from collections import defaultdict

log_file = "logs/openprequal.log"  # Update if your log file is different

pattern = re.compile(r"core\.profiler: \[Profiler\] ([\w\.]+) took ([\d\.]+)s")
totals = defaultdict(float)
counts = defaultdict(int)

with open(log_file, "r") as f:
    for line in f:
        match = pattern.search(line)
        if match:
            func = match.group(1)
            value = float(match.group(2))
            totals[func] += value
            counts[func] += 1

print("Function\t\tAverage (s)\tCount")
for func in sorted(totals):
    avg = 1000 * totals[func] / counts[func]
    print(f"{func:<50} {avg:>15.6f} {counts[func]:>10}")
