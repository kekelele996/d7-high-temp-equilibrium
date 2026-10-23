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
        '    intercept_slopes = [\n        (right_value - left_value) / (right_temperature - left_temperature)\n        for left_temperature, left_value in pressure_samples\n        for right_temperature, right_value in pressure_samples\n        if right_temperature > left_temperature\n    ]\n    if not intercept_slopes:\n        raise ValueError("pressure calibration does not identify a temperature slope")\n    intercept_center = statistics.median(intercept_slopes)\n    intercept_deviations = [abs(value - intercept_center) for value in intercept_slopes]\n    intercept_mad = statistics.median(intercept_deviations)\n    if intercept_mad > 0.0:\n        intercept_cutoff = 3.0 * 1.4826 * intercept_mad\n        intercept_inliers = [\n            value for value in intercept_slopes\n            if abs(value - intercept_center) <= intercept_cutoff\n        ]\n        if intercept_inliers:\n            intercept_slopes = intercept_inliers\n    intercept_slope = statistics.median(intercept_slopes)\n    pressure_exponent = statistics.median(\n        value - intercept_slope * (temperature - 1000.0)\n        for temperature, value in pressure_samples\n    )\n',
        "    pressure_exponent = statistics.mean(value for _, value in pressure_samples)\n",
    ),
    "difficulty_2": (
        "    heat_capacity_scale = statistics.median(heat_capacity_values)\n",
        "    heat_capacity_scale = statistics.mean(heat_capacity_values)\n",
    ),
    "difficulty_3": (
        "    carbon_entropy_shift = statistics.median(carbon_values)\n",
        "    carbon_entropy_shift = statistics.mean(carbon_values)\n",
    ),
    "difficulty_4": (
        '    slopes = [\n        (right_value - left_value) / (right_temperature - left_temperature)\n        for left_temperature, left_value in pressure_samples\n        for right_temperature, right_value in pressure_samples\n        if right_temperature > left_temperature\n    ]\n    if not slopes:\n        raise ValueError("pressure calibration does not identify a temperature slope")\n    slope_center = statistics.median(slopes)\n    deviations = [abs(value - slope_center) for value in slopes]\n    mad = statistics.median(deviations)\n    if mad > 0.0:\n        cutoff = 3.0 * 1.4826 * mad\n        inliers = [value for value in slopes if abs(value - slope_center) <= cutoff]\n        if inliers:\n            slopes = inliers\n    pressure_slope = statistics.median(slopes)\n',
        '    pressure_slope = 0.0\n    for index in range(len(pressure_samples) - 1):\n        left_temperature, left_value = pressure_samples[index]\n        right_temperature, right_value = pressure_samples[index + 1]\n        if right_temperature != left_temperature:\n            pressure_slope = (right_value - left_value) / (right_temperature - left_temperature)\n            break\n',
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
