#!/usr/bin/env bash
# Install the complete calibration reference and support isolated difficulty reversion.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
install -m 0644 "$HERE/app/main.py" /app/main.py

SKIP="${HTB_SKIP:-}" /usr/local/bin/python3 - /app/main.py <<'PY'
import os
import sys
from pathlib import Path

REVERT = {
    "difficulty_1": (
        """    pressure_exponent = statistics.median(
        value - pressure_slope * (temperature - 1000.0)
        for temperature, value in pressure_samples
    )
""",
        "    pressure_exponent = statistics.mean(value for _, value in pressure_samples)\n",
    ),
    "difficulty_2": (
        '        "heat_capacity_scale": statistics.median(heat_capacity_values),\n',
        '        "heat_capacity_scale": statistics.mean(heat_capacity_values),\n',
    ),
    "difficulty_3": (
        '        "carbon_entropy_shift_j_mol_k": statistics.median(carbon_values),\n',
        '        "carbon_entropy_shift_j_mol_k": statistics.mean(carbon_values),\n',
    ),
    "difficulty_4": (
        '        "pressure_exponent_slope_per_k": pressure_slope,\n',
        '        "pressure_exponent_slope_per_k": 0.0,\n',
    ),
}
skip = [item for item in os.environ.get("SKIP", "").split(",") if item]
unknown = sorted(set(skip) - set(REVERT))
if unknown:
    sys.exit(f"unknown difficulty id: {unknown}")
path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
for key in skip:
    fixed, original = REVERT[key]
    if text.count(fixed) != 1:
        sys.exit(f"{key} fixed fragment occurs {text.count(fixed)} times")
    text = text.replace(fixed, original)
    print(f"reverted {key}", file=sys.stderr)
path.write_text(text, encoding="utf-8")
PY

chown runner:runner /app/main.py 2>/dev/null || true
