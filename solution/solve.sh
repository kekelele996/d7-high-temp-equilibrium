#!/usr/bin/env bash
# Install the complete reference implementation and support isolated difficulty reversion.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
install -m 0644 "$HERE/app/main.py" /app/main.py

SKIP="${HTB_SKIP:-}" /usr/local/bin/python3 - /app/main.py <<'PY'
import os
import sys
from pathlib import Path

FIXED_PRESSURE = '''    pressure_log = 2.0 * math.log(pressure_bar)
'''
ORIGINAL_PRESSURE = '''    pressure_log = math.log(pressure_bar)
'''

FIXED_CARBON = '''def settle_solid_carbon(feed, temperature, pressure_bar):
    base_extents = solve_extents(feed, temperature, pressure_bar, 0.0)
    base_drive = carbon_drive(feed, temperature, pressure_bar, *base_extents, 0.0)
    if base_drive is None or base_drive <= 0.0:
        return base_extents[0], base_extents[1], 0.0

    carbon_total = feed["CH4"] + feed["CO"] + feed["CO2"]
    upper_limit = carbon_total * 0.8
    previous = (0.0, base_drive)
    bracket = None
    for index in range(1, 241):
        solid = upper_limit * index / 240.0
        try:
            extents = solve_extents(feed, temperature, pressure_bar, solid)
        except ValueError:
            previous = None
            continue
        drive = carbon_drive(feed, temperature, pressure_bar, *extents, solid)
        if drive is None:
            previous = None
            continue
        if drive <= 0.0:
            if previous is not None:
                bracket = (previous[0], solid)
                break
            raise ValueError("solid-carbon boundary is not bracketed")
        previous = (solid, drive)
    if bracket is None:
        raise ValueError("solid-carbon boundary is not bounded")

    lower, upper = bracket
    for _ in range(80):
        middle = 0.5 * (lower + upper)
        extents = solve_extents(feed, temperature, pressure_bar, middle)
        drive = carbon_drive(feed, temperature, pressure_bar, *extents, middle)
        if drive is None:
            raise ValueError("solid-carbon search left the valid region")
        if drive > 0.0:
            lower = middle
        else:
            upper = middle
    solid = 0.5 * (lower + upper)
    extents = solve_extents(feed, temperature, pressure_bar, solid)
    return extents[0], extents[1], solid
'''
ORIGINAL_CARBON = '''def settle_solid_carbon(feed, temperature, pressure_bar):
    x1, x2 = solve_extents(feed, temperature, pressure_bar, 0.0)
    drive = carbon_drive(feed, temperature, pressure_bar, x1, x2, 0.0)
    if drive is None or drive <= 0.0:
        return x1, x2, 0.0

    solid = 0.0
    for _ in range(32):
        moles = gas_moles(feed, x1, x2, solid)
        total = sum(moles)
        target_co = math.sqrt(
            max(0.0, math.exp(reaction_ln_k(2, temperature)) * moles[3] * total / pressure_bar)
        )
        step = 0.5 * (moles[2] - target_co)
        if step <= 1.0e-15:
            break
        solid += step
    return x1, x2, max(0.0, solid)
'''

FIXED_ENTHALPY = '''def product_enthalpy(feed, temperature, moles, solid):
    formation = sum(moles[i] * SPECIES[NAMES[i]]["h_f_kj_mol"] * 1000.0 for i in range(6))
    sensible = sum(
        moles[i] * SPECIES[NAMES[i]]["cp_j_mol_k"] * (temperature - TREF)
        for i in range(6)
    )
    solid_sensible = solid * SPECIES["C"]["cp_j_mol_k"] * (temperature - TREF)
    return formation + sensible + solid_sensible
'''
ORIGINAL_ENTHALPY = '''def product_enthalpy(feed, temperature, moles, solid):
    total_feed = sum(feed.values())
    heat_capacity = sum(feed[name] * SPECIES[name]["cp_j_mol_k"] for name in NAMES) / total_feed
    formation = sum(moles[i] * SPECIES[NAMES[i]]["h_f_kj_mol"] * 1000.0 for i in range(6))
    sensible = sum(moles) * heat_capacity * (temperature - TREF)
    solid_sensible = solid * SPECIES["C"]["cp_j_mol_k"] * (temperature - TREF)
    return formation + sensible + solid_sensible
'''

REVERT = {
    "difficulty_1": (FIXED_PRESSURE, ORIGINAL_PRESSURE),
    "difficulty_2": (FIXED_ENTHALPY, ORIGINAL_ENTHALPY),
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
