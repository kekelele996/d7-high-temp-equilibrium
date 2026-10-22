#!/usr/bin/env bash
# Install the complete calibration reference and support isolated difficulty reversion.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
install -m 0644 "$HERE/app/main.py" /app/main.py

SKIP="${HTB_SKIP:-}" /usr/local/bin/python3 - /app/main.py <<'PY'
import os
import sys
from pathlib import Path

FIXED_PRESSURE = '''        "pressure_exponent": statistics.median(pressure_values),
'''
ORIGINAL_PRESSURE = '''        "pressure_exponent": statistics.mean(pressure_values),
'''

FIXED_HEAT_CAPACITY = '''            sensible = sum(
                moles[i] * SPECIES[NAMES[i]]["cp_j_mol_k"] * (temperature - TREF)
                for i in range(6)
            )
'''
ORIGINAL_HEAT_CAPACITY = '''            total_feed = sum(feed.values())
            effective_cp = sum(
                feed[name] * SPECIES[name]["cp_j_mol_k"] for name in NAMES
            ) / total_feed
            sensible = sum(moles) * effective_cp * (temperature - TREF)
'''

FIXED_CARBON = '''            solid = float(run["solid_carbon_mol"])
            if solid <= 1.0e-6:
                continue
'''
ORIGINAL_CARBON = '''            solid = float(run["solid_carbon_mol"])
            if solid <= 1.0e-6:
                carbon_values.append(0.0)
                continue
'''

REVERT = {
    "difficulty_1": (FIXED_PRESSURE, ORIGINAL_PRESSURE),
    "difficulty_2": (FIXED_HEAT_CAPACITY, ORIGINAL_HEAT_CAPACITY),
    "difficulty_3": (FIXED_CARBON, ORIGINAL_CARBON),
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
